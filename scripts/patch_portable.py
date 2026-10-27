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
