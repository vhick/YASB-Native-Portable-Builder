#!/usr/bin/env python3
"""Apply fail-closed, source-level portability changes to the actual YASB source.

Do not substitute a launcher or manipulate a real user profile.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path


def replace_one(data: str, old: str, new: str, label: str) -> str:
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact upstream anchor, found {count}; audit new release")
    return data.replace(old, new, 1)



def suppress_komorebi_console_windows(source: str) -> str:
    """Windowless Komorebi child commands; fail closed if upstream shape changes.

    The YASB GUI executable has no console, so spawning a console-mode
    komorebic.exe (or cmd.exe for the two chained toggle calls) can flash a
    terminal even when the child immediately exits. We don't suppress command
    errors, change the retry cadence, or alter portable/installed app state.
    """
    method_names = {"Popen", "run", "check_output"}

    def relevant_calls(code: str):
        tree = ast.parse(code)
        return [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in method_names
        ]

    calls = relevant_calls(source)
    # Audit all calls, not only query_state or subscribe. Reject unexpected
    # source shapes rather than silently creating console windows.
    if len(calls) < 4:
        raise RuntimeError("Komorebi subprocess audit: unexpectedly few calls; inspect upstream")
    for call in calls:
        names = [kw.arg for kw in call.keywords]
        if "shell" not in names or "creationflags" in names:
            raise RuntimeError("Komorebi subprocess audit: unsupported call signature")

    # Only the audited Komorebi client is modified, not generic subprocesses
    # elsewhere in YASB (some are intended to open user-visible applications).
    pattern = r"\bshell=(?:True|False)\b"
    matches = list(re.finditer(pattern, source))
    if len(matches) != len(calls):
        raise RuntimeError("Komorebi subprocess audit: shell keyword count mismatch")
    patched = re.sub(
        pattern,
        lambda match: match.group(0) + ", creationflags=subprocess.CREATE_NO_WINDOW",
        source,
    )
    final_calls = relevant_calls(patched)
    if len(final_calls) != len(calls) or any(
        sum(kw.arg == "creationflags" for kw in call.keywords) != 1
        for call in final_calls
    ):
        raise RuntimeError("Komorebi windowless subprocess verification failed")
    return patched


def patch_files(root: Path) -> list[dict]:
    src = root / 'src'
    changes = []
    def update(name, transform):
        p = src / name
        original = p.read_text(encoding='utf-8')
        updated = transform(original)
        if original == updated:
            raise RuntimeError(f'{name}: patch made no change')
        p.write_text(updated, encoding='utf-8', newline='\n')
        changes.append({'path': 'src/' + name, 'original_sha256': hashlib.sha256(original.encode()).hexdigest(), 'patched_sha256': hashlib.sha256(updated.encode()).hexdigest()})

    def settings(text):
        text = replace_one(text, 'APP_ID = "YASB.YetAnotherStatusBar"',
            'APP_ID = "YASB.NativePortable.YetAnotherStatusBar"', 'portable AUMID')
        old = 'DEFAULT_CONFIG_DIRECTORY = os.getenv("YASB_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config", "yasb")'
        new = '''# NATIVE PORTABLE: resolve from the executing EXE before any config/log imports.
# No external launcher, global USERPROFILE/APPDATA redirection, or post-exit cleanup.
PORTABLE_ROOT = SCRIPT_PATH if IS_FROZEN else None
if IS_FROZEN:
    DEFAULT_CONFIG_DIRECTORY = os.path.join(PORTABLE_ROOT, "Data", "Config")
    os.makedirs(DEFAULT_CONFIG_DIRECTORY, exist_ok=True)
    # Allow cooperating YASB code and its children to use the same scoped profile.
    os.environ["YASB_CONFIG_HOME"] = DEFAULT_CONFIG_DIRECTORY
else:
    DEFAULT_CONFIG_DIRECTORY = os.getenv("YASB_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config", "yasb")'''
        return replace_one(text, old, new, 'portable config source adapter')
    update('settings.py', settings)

    def system(text):
        old = '    folder = Path(os.environ["LOCALAPPDATA"]) / "YASB"'
        new = '''    # NATIVE PORTABLE: YASB-owned runtime state lives beside the running EXE.
    # Leave other applications' LOCALAPPDATA entirely untouched.
    from settings import IS_FROZEN, SCRIPT_PATH
    folder = (Path(SCRIPT_PATH) / "Data" / "State") if IS_FROZEN else (Path(os.environ["LOCALAPPDATA"]) / "YASB")'''
        return replace_one(text, old, new, 'local application data')
    update('core/utils/system.py', system)

    # Distinct native instance/pipe identities prevent stop/reload/log commands
    # from reaching an installed copy of YASB.
    def main_file(text):
        return replace_one(text, 'def single_instance_lock(name: str = "yasb_reborn"):',
            'def single_instance_lock(name: str = "yasb_native_portable"):',
            'unique portable instance mutex')
    update('main.py', main_file)

    def cli_server(text):
        for suffix in ('cli', 'log'):
            text = replace_one(text,
                f'\\\\.\\pipe\\yasb_pipe_{suffix}',
                f'\\\\.\\pipe\\yasb_native_portable_pipe_{suffix}',
                f'unique portable {suffix} server pipe')
        return text
    update('core/utils/cli_server.py', cli_server)

    def cli(text):
        for suffix in ('cli', 'log'):
            text = replace_one(text,
                f'\\\\.\\pipe\\yasb_pipe_{suffix}',
                f'\\\\.\\pipe\\yasb_native_portable_pipe_{suffix}',
                f'unique portable {suffix} client pipe')
        text = replace_one(text, 'AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None',
            'AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None\n'
            'APP_NAME = "YASB Native Portable"  # never reuse installed YASB startup identity',
            'unique portable startup name')
        text = replace_one(text, '            subprocess.Popen(["yasb.exe"])',
            '            subprocess.Popen([EXE_PATH], cwd=SCRIPT_PATH)',
            'CLI runs sibling portable EXE')
        safe_gate = (
            '        args, passthrough = parser.parse_known_args()\n'
            '        # Source-built NATIVE: reject inherited operations that may modify\n'
            '        # an installed YASB, any machine-wide registry, or unrelated PIDs.\n'
            '        blocked = {"update", "set-channel", "reset", "enable-crash-dumps", "disable-crash-dumps"}\n'
            '        if args.command in blocked or (args.command == "stop" and args.force) or (\n'
            '            args.command in {"enable-autostart", "disable-autostart"} and args.task\n'
            '        ):\n'
            '            print("Unsupported on YASB Native Portable: potentially unsafe host operation.")\n'
            '            sys.exit(2)'
        )
        text = replace_one(text, '        args, passthrough = parser.parse_known_args()',
            safe_gate, 'reject installed app, global task and destructive CLI ops')
        text = replace_one(text,
            '                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f"{AUTOSTART_FILE}")',
            '                if not AUTOSTART_FILE:\n'
            '                    raise RuntimeError("Portable executable was not found")\n'
            '                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f\'"{AUTOSTART_FILE}"\')',
            'quote native startup entry')
        text = replace_one(text,
            '            with self._open_startup_registry(winreg.KEY_ALL_ACCESS) as key:\n'
            '                winreg.DeleteValue(key, APP_NAME)',
            '            with self._open_startup_registry(winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:\n'
            '                recorded, kind = winreg.QueryValueEx(key, APP_NAME)\n'
            '                if kind != winreg.REG_SZ or not AUTOSTART_FILE or recorded != f\'"{AUTOSTART_FILE}"\':\n'
            '                    raise PermissionError("Startup entry belongs to another location; refusing deletion")\n'
            '                winreg.DeleteValue(key, APP_NAME)',
            'protect another instance startup entry from removal')
        return text
    update('cli.py', cli)


    def update_service(text):
        old = '        return is_installed and is_arch_supported and IS_FROZEN and (not is_pr_build)'
        new = '''        # NATIVE PORTABLE: never launch an MSI installer or switch the app to an installed product.
        return False'''
        return replace_one(text, old, new, 'disable installed MSI auto-updater')
    update('core/utils/update_service.py', update_service)

    def client(text):
        text = replace_one(text, 'import subprocess\n',
            'import subprocess\nfrom native_portable.komorebi_socket import discover_komorebic, socket_is_online\n', 'Komorebi module import')
        text = replace_one(text, '        self._komorebic_path = komorebic_path',
            '''        self._komorebic_path = discover_komorebic(komorebic_path)
        # Read-only UDS probe: never create/delete Komorebi's socket or config.
        self._komorebi_socket_seen = socket_is_online()''', 'Komorebi client initialization')
        text = replace_one(text, '    def query_state(self) -> dict | None:\n        try:',
            '''    def query_state(self) -> dict | None:
        # Komorebi may start after YASB. Re-discover a portable sibling executable.
        self._komorebic_path = discover_komorebic(self._komorebic_path)
        self._komorebi_socket_seen = socket_is_online()
        try:''', 'Komorebi state lookup')
        text = replace_one(text, '    def wait_until_subscribed_to_pipe(self, pipe_name: str):\n        proc = subprocess.Popen(',
            '''    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        self._komorebic_path = discover_komorebic(self._komorebic_path)
        self._komorebi_socket_seen = socket_is_online()
        proc = subprocess.Popen(''', 'Komorebi subscription discovery')
        # Fix fragile Windows list + shell invocation when executable is in a Unicode/spaced directory.
        text = replace_one(text,
            '[self._komorebic_path, "subscribe", pipe_name], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE',
            '[self._komorebic_path, "subscribe", pipe_name], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE',
            'Komorebi named pipe subscription')
        text = replace_one(text, '[self._komorebic_path, "state"],\n                timeout=self._timeout_secs,\n                stderr=subprocess.PIPE,\n                shell=True,',
            '[self._komorebic_path, "state"],\n                timeout=self._timeout_secs,\n                stderr=subprocess.PIPE,\n                shell=False,', 'Komorebi state command')
        # All remaining list-based komorebic calls must execute the sibling
        # binary directly, not via cmd.exe (breaks portable paths with spaces).
        # Only the two explicitly composed `command` strings retain a shell,
        # because they use && to chain two upstream commands.
        text = text.replace('shell=True', 'shell=False')
        text = replace_one(text,
            'subprocess.run(command, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)',
            'subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)',
            'Komorebi intentional chained command subprocess.run')
        text = replace_one(text,
            'subprocess.Popen(command, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)',
            'subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)',
            'Komorebi intentional chained command subprocess.Popen')
        # r2: keep r1's proven direct invocation and subscription semantics,
        # but prevent all Komorebi console processes from flashing on Windows.
        return suppress_komorebi_console_windows(text)
    update('core/widgets/services/komorebi/client.py', client)

    nd = src / 'native_portable'
    nd.mkdir(parents=True, exist_ok=True)
    (nd / '__init__.py').write_text('"""Source-built YASB native portability helpers."""\n', encoding='utf-8')
    helper = Path(__file__).resolve().parents[1] / 'patches' / 'komorebi_socket.py'
    (nd / 'komorebi_socket.py').write_bytes(helper.read_bytes())
    changes.append({'path': 'src/native_portable/komorebi_socket.py', 'original_sha256': None,
        'patched_sha256': hashlib.sha256(helper.read_bytes()).hexdigest()})

    # Cloud stores its session, vault, logs and safety backups under AppData in
    # upstream source; in native mode, these are YASB-owned and belong in Data.
    def cloud_session(text):
        original = '    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YASB" / CLOUD_DIR_NAME'
        replacement = '    from core.utils.system import app_data_path\n    base = app_data_path() / CLOUD_DIR_NAME'
        return replace_one(text, original, replacement, 'portable cloud credentials and backup state')
    update('core/cloud/session.py', cloud_session)

    def cloud_app(text):
        return replace_one(text, 'MUTEX_NAME = "Global\\\\YASB.Cloud.SingleInstance"',
            'MUTEX_NAME = "Local\\\\YASB.NativePortable.Cloud.SingleInstance"',
            'portable cloud mutex identity')
    update('core/cloud/app.py', cloud_app)

    def cloud_constants(text):
        return replace_one(text, 'TASK_NAME = "YASB Cloud Automatic Backup"',
            'TASK_NAME = "YASB Native Portable Cloud Automatic Backup"',
            'separate cloud scheduled task identity')
    update('core/cloud/constants.py', cloud_constants)

    # Cloud restore must never assume an installed yasb.exe is ours, or start the
    # installed yasbc.exe found in the system PATH.
    def cloud_restore(text):
        text = replace_one(text, 'from settings import SCRIPT_PATH',
            'from settings import SCRIPT_PATH\nfrom native_portable.native_instance import native_instance_running',
            'portable cloud native mutex reader import')
        text = replace_one(text,
            '        found = shutil.which("yasbc")\n        if found:\n            return found\n        bundled = Path(SCRIPT_PATH) / "yasbc.exe"',
            '        bundled = Path(SCRIPT_PATH) / "yasbc.exe"',
            'cloud only runs sibling portable CLI')
        text = replace_one(text, '        return is_process_running(BAR_PROCESS_NAME)',
            '        return native_instance_running()',
            'cloud only regards this portable instance as running')
        text = replace_one(text,
            '        while is_process_running(BAR_PROCESS_NAME) and time.monotonic() < deadline:',
            '        while native_instance_running() and time.monotonic() < deadline:',
            'cloud waits for portable instance instead of installed one')
        return text
    update('core/cloud/restore.py', cloud_restore)

    inst = Path(__file__).resolve().parents[1] / 'patches' / 'native_instance.py'
    (nd / 'native_instance.py').write_bytes(inst.read_bytes())
    changes.append({'path': 'src/native_portable/native_instance.py', 'original_sha256': None,
        'patched_sha256': hashlib.sha256(inst.read_bytes()).hexdigest()})
    return changes


def pin_css(root: Path, sha: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('css SHA must be a verified 40-character git commit')
    p = root / 'pyproject.toml'
    old = p.read_text(encoding='utf-8')
    new = replace_one(old,
        'qt-css-engine @ git+https://github.com/Video-Nomad/qt-css-engine@dev',
        'qt-css-engine @ git+https://github.com/Video-Nomad/qt-css-engine@' + sha,
        'moving upstream CSS dependency')
    p.write_text(new, encoding='utf-8', newline='\n')
    return {'path': 'pyproject.toml', 'original_sha256': hashlib.sha256(old.encode()).hexdigest(),
            'patched_sha256': hashlib.sha256(new.encode()).hexdigest(), 'css_commit': sha}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream', type=Path, required=True)
    ap.add_argument('--css-sha', required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    results = patch_files(args.upstream)
    results.append(pin_css(args.upstream, args.css_sha.lower()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(f'Applied and verified {len(results)} source adapters (not runtime-tested).')


if __name__ == '__main__':
    main()
