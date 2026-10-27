"""Apply guarded, build-time-only YASB native portability patches.

All edits happen inside the cloned upstream source in RUNNER_TEMP.
A missing/changed anchor raises an error, so upstream drift is never silently ignored.
"""
from __future__ import annotations
import argparse
import ast
import re
from pathlib import Path


def replacement(source: Path, old: str, new: str, label: str) -> None:
    if not source.is_file():
        raise RuntimeError(f"{label}: upstream source file missing: {source}")
    original = source.read_text(encoding="utf-8-sig")
    count = original.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one unchanged anchor in {source}, found {count}; update this builder's patch")
    updated = original.replace(old, new, 1)
    ast.parse(updated, filename=str(source))
    source.write_text(updated, encoding="utf-8", newline="\n")
    print(f"[patched] {label}: {source}")


def patch(source_root: Path) -> list[str]:
    src = source_root / "src"
    notes = []
    settings = src / "settings.py"
    old = 'SCRIPT_PATH = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(os.path.abspath(__file__))'
    new = old + '''
# BUILDER PATCH: portable.flag lives beside the frozen executables.
# All four frozen entry points load settings.py and inherit this portable mode.
IS_PORTABLE = IS_FROZEN and os.path.isfile(os.path.join(SCRIPT_PATH, "portable.flag"))
if IS_PORTABLE:
    _portable_root = os.path.join(SCRIPT_PATH, "Data")
    os.environ["YASB_PORTABLE"] = "1"
    os.environ.setdefault("YASB_HOST_LOCALAPPDATA", os.environ.get("LOCALAPPDATA", ""))
    os.environ["YASB_CONFIG_HOME"] = os.path.join(_portable_root, "Config")
    os.environ["YASB_DATA_HOME"] = os.path.join(_portable_root, "YASB")
    # Redirect direct %LOCALAPPDATA% readers inside this process as a fallback.
    # Do not alter the host environment or Registry.
    os.environ["LOCALAPPDATA"] = os.path.join(_portable_root, "LocalAppData")
'''
    replacement(settings, old, new, "frozen portable-mode detection and paths")
    notes.append("YASB_CONFIG_HOME, YASB_DATA_HOME and process LOCALAPPDATA point into Data/.")

    system = src / 'core/utils/system.py'
    old = 'folder = Path(os.environ["LOCALAPPDATA"]) / "YASB"'
    new = 'folder = Path(os.environ["YASB_DATA_HOME"]) if os.getenv("YASB_DATA_HOME") else Path(os.environ["LOCALAPPDATA"]) / "YASB"'
    replacement(system, old, new, "central widget cache and OAuth-token folder")
    notes.append("core.utils.system.app_data_path() writes to Data/YASB/ when portable.")
    # Komorebi uses komorebic.exe plus named-pipe events; neither is bundled in YASB.
    client = src / 'core/widgets/services/komorebi/client.py'
    replacement(client, 'import logging\n', 'import logging\nimport os\nimport shutil\nimport sys\nfrom pathlib import Path\n',
                'Komorebi portable resolver imports')
    resolver = '''def _running_komorebi_cli() -> str | None:
    """Locate the CLI belonging to the active Komorebi, including a portable copy.

    Uses read-only Windows process APIs. Does not query the registry or scan disks.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        enum = psapi.EnumProcesses
        enum.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        enum.restype = wintypes.BOOL
        open_process = kernel.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        query_image = kernel.QueryFullProcessImageNameW
        query_image.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        query_image.restype = wintypes.BOOL
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL

        pids = (wintypes.DWORD * 8192)()
        count_bytes = wintypes.DWORD()
        if not enum(pids, ctypes.sizeof(pids), ctypes.byref(count_bytes)):
            return None
        for pid in pids[:count_bytes.value // ctypes.sizeof(wintypes.DWORD)]:
            if not pid:
                continue
            handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                continue
            try:
                buffer = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buffer))
                if query_image(handle, 0, buffer, ctypes.byref(size)):
                    image = Path(buffer.value)
                    if image.name.lower() == "komorebi.exe":
                        cli = image.with_name("komorebic.exe")
                        if cli.is_file():
                            return str(cli)
            finally:
                close(handle)
    except (OSError, ValueError, AttributeError) as exc:
        logging.debug("Could not inspect running Komorebi path: %s", exc)
    return None


def _portable_komorebi_path(default: str) -> str:
    """Resolve Komorebi without installation or manual path entry when possible.

    The active komorebi.exe takes precedence over PATH, so an installed CLI
    cannot accidentally override a running portable instance. A manually
    chosen path remains a last-resort override only.
    """
    root = Path(sys.executable).resolve().parent

    def cli_at(value: str | Path) -> str | None:
        path = Path(os.path.expandvars(str(value))).expanduser()
        if not path.is_absolute():
            path = root / path
        if path.is_dir():
            path = path / "komorebic.exe"
        if path.name.lower() != "komorebic.exe":
            return None
        return str(path) if path.is_file() else None

    explicit = os.environ.get("YASB_KOMOREBIC_PATH", "").strip().strip('"')
    saved = root / "Data" / "Komorebi.path"
    if not explicit and os.environ.get("YASB_PORTABLE") == "1" and saved.is_file():
        explicit = saved.read_text(encoding="utf-8-sig").strip().strip('"')
    if explicit:
        selected = cli_at(explicit)
        if selected:
            logging.info("Komorebi CLI: explicit override %s", selected)
            return selected
        logging.warning("Komorebi manual CLI selection is missing: %s. Trying automatic discovery.", explicit)

    running = _running_komorebi_cli()
    if running:
        logging.info("Komorebi CLI: matched running instance %s", running)
        return running

    # Fast, bounded checks for nearby portable layouts (no full-drive scan).
    for base in (root, root.parent, root.parent.parent):
        for sub in ("komorebi", "Komorebi", "Komorebi-Portable", "Tools/Komorebi",
                    "Apps/komorebi", "App/Komorebi", "App", ""):
            found = cli_at(base / sub / "komorebic.exe")
            if found:
                logging.info("Komorebi CLI: nearby portable path %s", found)
                return found

    path_hit = shutil.which(default)
    if path_hit and Path(path_hit).is_file():
        logging.info("Komorebi CLI: Windows PATH %s", path_hit)
        return path_hit

    home = Path.home()
    host_local = os.environ.get("YASB_HOST_LOCALAPPDATA") or os.environ.get("LOCALAPPDATA", "")
    candidates = [home / "scoop/shims/komorebic.exe", home / "scoop/apps/komorebi/current/komorebic.exe",
                  home / ".cargo/bin/komorebic.exe"]
    if host_local:
        base = Path(host_local)
        candidates.append(base / "Microsoft/WinGet/Links/komorebic.exe")
        packages = base / "Microsoft/WinGet/Packages"
        if packages.is_dir():
            # WinGet package folder names include changing publisher and version values.
            for package in packages.glob("*komorebi*"):
                candidates.append(package / "komorebic.exe")
                candidates.extend(package.glob("*/komorebic.exe"))
    scoop = os.environ.get("SCOOP")
    if scoop:
        candidates.extend((Path(scoop) / "shims/komorebic.exe",
                           Path(scoop) / "apps/komorebi/current/komorebic.exe"))
    programdata = os.environ.get("ProgramData")
    if programdata:
        candidates.extend((Path(programdata) / "scoop/shims/komorebic.exe",
                           Path(programdata) / "scoop/apps/komorebi/current/komorebic.exe"))
    programfiles = os.environ.get("ProgramFiles")
    if programfiles:
        candidates.extend((Path(programfiles) / "komorebi/komorebic.exe",
                           Path(programfiles) / "LGUG2Z/komorebi/komorebic.exe"))
    for candidate in candidates:
        found = cli_at(candidate)
        if found:
            logging.info("Komorebi CLI: common installation %s", found)
            return found

    logging.warning("Komorebi CLI was not found automatically; start Komorebi or use YASB-Manager.cmd manual override.")
    return default

'''
    replacement(client, 'type KomorebiNode = dict[str, Any]\n', resolver + 'type KomorebiNode = dict[str, Any]\n',
                'Komorebi CLI portable path discovery')
    replacement(client, 'self._komorebic_path = komorebic_path',
                'self._komorebic_path = _portable_komorebi_path(komorebic_path)',
                'Komorebi CLI path selection')
    replacement(client, '        args = [self._komorebic_path, "subscribe", pipe_name]',
                '        if self._komorebic_path == "komorebic.exe" or (os.path.isabs(self._komorebic_path) and not Path(self._komorebic_path).is_file()):\n'
                '            self._komorebic_path = _portable_komorebi_path("komorebic.exe")\n'
                '        args = [self._komorebic_path, "subscribe", pipe_name]',
                'retry Komorebi discovery on event listener reconnection')
    shim = '''    def _komorebi_subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        original = env.get("YASB_HOST_LOCALAPPDATA")
        if original:
            env["LOCALAPPDATA"] = original
        return env

    def _komorebi_check_output(self, *args, **kwargs):
        kwargs.setdefault("env", self._komorebi_subprocess_env())
        return subprocess.check_output(*args, **kwargs)

    def _komorebi_run(self, *args, **kwargs):
        kwargs.setdefault("env", self._komorebi_subprocess_env())
        return subprocess.run(*args, **kwargs)

    def _komorebi_popen(self, *args, **kwargs):
        kwargs.setdefault("env", self._komorebi_subprocess_env())
        return subprocess.Popen(*args, **kwargs)

'''
    replacement(client, '    @property\n    def komorebic_path(self) -> str:',
                shim + '    @property\n    def komorebic_path(self) -> str:',
                'Restore host LOCALAPPDATA only for Komorebi external commands')
    for api, method in [('check_output', '_komorebi_check_output'), ('run', '_komorebi_run'), ('Popen', '_komorebi_popen')]:
        source = client.read_text(encoding='utf-8')
        anchor_call = f'subprocess.{api}('
        count = source.count(anchor_call)
        # The one call inside our wrapper must remain an underlying subprocess call.
        if count < 2:
            raise RuntimeError(f'Komorebi subprocess.{api} upstream calls changed; expected at least one external call')
        changed = source.replace(anchor_call, f'self.{method}(')
        wrapper_start = changed.index(f'    def {method}(')
        wrapper_end = changed.index('\n    def ', wrapper_start + 8)
        section = changed[wrapper_start:wrapper_end]
        if section.count(f'self.{method}(') != 1:
            raise RuntimeError(f'Komorebi wrapper changed unexpectedly: {api}')
        changed = changed[:wrapper_start] + section.replace(f'self.{method}(', anchor_call, 1) + changed[wrapper_end:]
        ast.parse(changed, filename=str(client))
        client.write_text(changed, encoding='utf-8', newline='\n')
        print(f'[patched] Komorebi {api} external calls: {count-1}')
    notes.append('Komorebi auto-discovery: running instance, nearby portable, PATH, Scoop/WinGet/Cargo; manual fallback; reconnect retry and host LOCALAPPDATA preserved.')

    win32 = src / 'core/utils/win32/utils.py'
    old = 'def enable_autostart(app_name: str, executable_path: str) -> bool:\n    """Add application to Windows startup."""'
    new = old + '''
    if os.environ.get("YASB_PORTABLE") == "1":
        logging.warning("Autostart is disabled in native portable mode")
        return False'''
    # Add local import to not assume os is already imported.
    replacement(win32, 'import logging\n', 'import logging\nimport os\n', 'enable-autostart import')
    replacement(win32, old, new, 'prevent tray autostart registry writes')
    notes.append("Tray AutoStart Registry writes are refused in portable mode.")

    cli = src / 'cli.py'
    # The CLI offers machine-changing commands, including installer updates and crash dump keys.
    for name in ('update', 'set-channel', 'enable-autostart', 'disable-autostart',
                 'enable-crash-dumps', 'disable-crash-dumps'):
        old = f'elif args.command == "{name}":'
        new = old + '''
            if os.environ.get("YASB_PORTABLE") == "1":
                print("This command is disabled in the native portable build. Rebuild using GitHub Actions to update.")
                sys.exit(2)'''
        # 'disable-crash-dumps' may not be an explicit elif in future upstream.
        replacement(cli, old, new, f'block CLI machine-changing command {name}')
    notes.append("CLI auto-updater, startup registration, channel switch, crash-dump registry commands blocked.")

    # YASB first-run wizard can register per-user fonts in the Registry. Keep
    # downloaded fonts inside Data/LocalAppData and register only in Qt memory.
    welcome = src / 'core/ui/views/welcome.py'
    old = '    def _register(font_name: str, dest: str) -> None:\n'
    new = old + '''        if os.environ.get("YASB_PORTABLE") == "1":
            return  # No permanent user-font Registry entries in portable mode.
'''
    replacement(welcome, old, new, 'prevent permanent first-run font registration')

    main = src / 'main.py'
    old = '    app = YASBApplication(argv)\n'
    new = old + '''    # Load any fonts downloaded into the portable Data folder on previous runs.
    from pathlib import Path
    from PyQt6.QtGui import QFontDatabase
    from settings import IS_PORTABLE, SCRIPT_PATH
    if IS_PORTABLE:
        fonts = Path(SCRIPT_PATH) / "Data" / "LocalAppData" / "Microsoft" / "Windows" / "Fonts"
        if fonts.is_dir():
            for font_file in fonts.iterdir():
                if font_file.suffix.lower() in (".ttf", ".otf"):
                    QFontDatabase.addApplicationFont(str(font_file))
'''
    replacement(main, old, new, 'load user fonts from portable data on startup')
    notes.append("First-run font downloads stored in Data; Qt reloads fonts without permanent Registry registration.")

    schedule = src / 'core/cloud/schedule.py'
    if schedule.is_file():
        replacement(schedule, 'import datetime\n', 'import datetime\nimport os\n', 'cloud schedule import')
        old = 'def create() -> tuple[bool, str]:\n    """Register the task, replacing any existing one. Returns success and any failure text."""'
        new = old + '''
    if os.environ.get("YASB_PORTABLE") == "1":
        return False, "Automatic backup scheduling is unavailable in native portable mode"'''
        replacement(schedule, old, new, 'avoid persistent Cloud scheduled tasks')
        notes.append("YASB Cloud automatic-backup task creation is blocked; manual cloud operations may work.")
    else:
        notes.append("Cloud automatic-backup task file absent in selected upstream revision; not patched.")
    return notes


PATTERNS = {
    'Local appdata/home/config paths': re.compile(r'LOCALAPPDATA|APPDATA|PROGRAMDATA|expanduser|YASB_CONFIG_HOME|YASB_DATA_HOME|QStandardPaths', re.I),
    'Registry/startup/tasks/fonts': re.compile(r'winreg\.|SetValueEx\(|CreateKey\(|RegisterTaskDefinition|schtasks|AddFontResourceEx', re.I),
    'Temp / potentially machine-specific': re.compile(r'tempfile\.|gettempdir\(|mkstemp\(|C:\\\\|D:\\\\', re.I),
}


def audit(root: Path, notes: list[str], target: Path) -> None:
    lines = [
        'YASB NATIVE PORTABLE - BUILD-TIME STATIC PATH/REGISTRY SCAN',
        'This scan is heuristic. It is NOT proof of zero system writes.',
        'Entries can be reads, comments, optional features or host integrations.',
        '', 'APPLIED PATCHES:', *[' - ' + n for n in notes], '',
    ]
    counts = {}
    for label, pattern in PATTERNS.items():
        lines.append(f'[{label}]')
        matches = []
        for file in sorted((root / 'src').rglob('*.py')):
            if any(x in file.parts for x in ('dist', 'build', '__pycache__')):
                continue
            for no, text in enumerate(file.read_text(encoding='utf-8-sig', errors='replace').splitlines(), 1):
                if pattern.search(text):
                    matches.append(f'  {file.relative_to(root)}:{no}: {text.strip()[:220]}')
        counts[label] = len(matches)
        lines.extend(matches[:400])
        if len(matches) > 400:
            lines.append(f'  ... {len(matches)-400} additional matches omitted')
        lines.append('')
    lines.append('COUNTS: ' + '; '.join(f'{k}: {v}' for k,v in counts.items()))
    lines.append('')
    lines.append('Windows Registry, task scheduler, system integrations, temporary files,')
    lines.append('and some credentials may remain machine-bound. Review before broad redistribution.')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Static audit saved:', target, 'counts:', counts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    args = parser.parse_args()
    notes = patch(args.source)
    audit(args.source, notes, args.audit)


if __name__ == '__main__':
    main()
