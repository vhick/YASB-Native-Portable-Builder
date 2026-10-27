"""Stage cx_Freeze output as a native portable folder, then make one ZIP."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BINARY_NAMES = ('yasb.exe', 'yasb_themes.exe', 'yasbc.exe', 'yasb_cloud.exe')

PORTABLE_README = '''YASB NATIVE PORTABLE - Read before running

This is an UNOFFICIAL, UNSIGNED build. Original project: https://github.com/amnweb/yasb

1. Unzip the complete YASB-Native-Portable folder to any writable drive.
2. Double-click yasb.exe (the upstream icon), or YASB-Portable.cmd.
3. On first launch, complete the official YASB setup wizard.
4. Keep the Data directory when replacing the application with a newer build.

Paths in this modified build:
- Main config, styles, .env, and logs: Data\\Config
- YASB widget data and tokens: Data\\YASB
- Fallback for direct LOCALAPPDATA use: Data\\LocalAppData
- Other native entry points (yasbc, themes, cloud) use the portable.flag marker.

The original icons and cx_Freeze executables are preserved.
No installer is run. Existing Windows settings/other installed YASB versions
are not migrated or modified by the builder.

IMPORTANT CAVEATS:
- Do not use auto-start, CLI installer update, crash dump registration, or
  automatic Cloud backup scheduling. These are disabled in portable mode.
- Nerd Fonts can be downloaded by the first-run wizard into portable Data,
  but not registered persistently. Other apps won't see them as installed fonts.
- YASB Cloud uses Windows DPAPI for certain encrypted session data. Such data
  may not be usable after a Windows reinstall or on another PC; sign in again.
- Widgets may read or modify system settings, run external apps, launch UIs,
  use temporary files or depend on registry/native Windows features.
- Windows notification / tray functionality may differ without MSI registration.
- Not a fully audited no-trace runtime; use ProcMon and Registry snapshots if
  strict no-host-write behavior is required.
- Python runtime is bundled but system Windows support is still required.
- Portable ZIP and its executables are not code signed by upstream.
- Full third-party licensing obligations still apply before redistributing.

Use SOURCE_INFO.txt and PORTABILITY_AUDIT.txt to identify source revision.
'''

CMD = '''@echo off
setlocal
set "YASB_PORTABLE=1"
set "YASB_CONFIG_HOME=%~dp0Data\\Config"
set "YASB_DATA_HOME=%~dp0Data\\YASB"
set "LOCALAPPDATA=%~dp0Data\\LocalAppData"
if not exist "%YASB_CONFIG_HOME%" mkdir "%YASB_CONFIG_HOME%"
if not exist "%YASB_DATA_HOME%" mkdir "%YASB_DATA_HOME%"
start "" "%~dp0yasb.exe" %*
endlocal
'''

CLI_CMD = '''@echo off
setlocal
set "YASB_PORTABLE=1"
set "YASB_CONFIG_HOME=%~dp0Data\\Config"
set "YASB_DATA_HOME=%~dp0Data\\YASB"
set "LOCALAPPDATA=%~dp0Data\\LocalAppData"
"%~dp0yasbc.exe" %*
exit /b %errorlevel%
'''


def get_version(src: Path) -> str:
    content = (src / 'src/settings.py').read_text(encoding='utf-8')
    m = re.search(r'^BUILD_VERSION\s*=\s*[\'\"]([^\'\"]+)[\'\"]', content, re.M)
    if not m:
        raise RuntimeError('Upstream BUILD_VERSION not found: adjust parser for new upstream source.')
    if not re.fullmatch(r'[0-9A-Za-z.+_-]+', m.group(1)):
        raise RuntimeError('Unexpected upstream version string; refusing unsafe ZIP filename.')
    return m.group(1)


def init_stage(src: Path, dest: Path, args: argparse.Namespace) -> None:
    dist = src / 'src/dist'
    for filename in BINARY_NAMES:
        if not (dist / filename).is_file():
            raise RuntimeError(f'cx_Freeze output is missing {filename} in {dist}; build may be incomplete')
    # cx_Freeze versions/layouts may place the Python archive under lib/.
    # Preserve that layout exactly: the frozen executables expect relative paths.
    library_candidates = (dist / 'lib' / 'library.zip', dist / 'library.zip')
    library = next((file for file in library_candidates if file.is_file()), None)
    if library is None:
        observed = sorted(p.name for p in dist.iterdir()) if dist.is_dir() else []
        lib_observed = sorted(p.name for p in (dist / 'lib').iterdir()) if (dist / 'lib').is_dir() else []
        raise RuntimeError(
            f'cx_Freeze Python archive not found at lib/library.zip or library.zip in {dist}. '
            f'dist entries: {observed[:30]}; lib entries: {lib_observed[:30]}. '
            'Inspect the current upstream cx_Freeze output before updating the builder.'
        )
    if not zipfile.is_zipfile(library):
        raise RuntimeError(f'cx_Freeze archive exists but is not a valid ZIP: {library}')
    print('Verified cx_Freeze Python library archive:', library.relative_to(dist))
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(dist, dest)
    (dest / 'Data/Config').mkdir(parents=True)
    (dest / 'Data/YASB').mkdir(parents=True)
    (dest / 'Data/LocalAppData').mkdir(parents=True)
    (dest / 'Data/.keep').write_text('Preserve the entire Data folder during upgrades.\n', encoding='utf-8')
    (dest / 'portable.flag').write_text('YASB independent native portable builder - marker activates Data/ paths\n', encoding='utf-8')
    (dest / 'YASB-Portable.cmd').write_text(CMD, encoding='utf-8', newline='\r\n')
    (dest / 'YASB-CLI.cmd').write_text(CLI_CMD, encoding='utf-8', newline='\r\n')
    (dest / 'README_PORTABLE.txt').write_text(PORTABLE_README, encoding='utf-8')
    shutil.copy2(src / 'LICENSE', dest / 'LICENSE')
    shutil.copy2(args.audit, dest / 'PORTABILITY_AUDIT.txt')
    version = get_version(src)
    metadata = {
        'upstream_repository': 'https://github.com/amnweb/yasb',
        'upstream_default_branch_at_build': args.branch,
        'upstream_requested_ref': args.requested_ref or None,
        'upstream_commit': args.commit,
        'upstream_source_version': version,
        'build_timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'build_type': 'Native Portable x64; cx_Freeze build (no MSI)',
        'builder_license_notice': 'Unofficial; upstream MIT LICENSE is included.',
    }
    (dest / 'SOURCE_INFO.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    (dest / 'SOURCE_INFO.txt').write_text('\n'.join(f'{k}: {v}' for k, v in metadata.items()) + '\n', encoding='utf-8')
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            (dest / 'BUILD_DEPENDENCIES.txt').write_text(result.stdout, encoding='utf-8')
    except (OSError, subprocess.TimeoutExpired):
        pass
    print('Staged native portable executable folder:', dest)


def make_zip(dest: Path, out_dir: Path) -> Path:
    metadata = json.loads((dest / 'SOURCE_INFO.json').read_text(encoding='utf-8'))
    version = metadata['upstream_source_version']
    short_sha = metadata['upstream_commit'][:12]
    date = metadata['build_timestamp_utc'][:10].replace('-', '')
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f'YASB-Native-Portable-v{version}-{short_sha}-{date}-x64.zip'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for file in sorted(dest.rglob('*')):
            if file.is_file():
                z.write(file, arcname=(Path('YASB-Native-Portable') / file.relative_to(dest)).as_posix())
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad is not None:
            raise RuntimeError(f'ZIP CRC error: {bad}')
    print('Wrote verified ZIP:', zip_path, f'({zip_path.stat().st_size:,} bytes)')
    return zip_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--commit', required=True)
    p.add_argument('--branch', required=True)
    p.add_argument('--requested-ref', default='')
    p.add_argument('--audit', required=True, type=Path)
    p.add_argument('--smoke', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--stage', required=True, type=Path)
    p.add_argument('--finalize-only', action='store_true')
    args = p.parse_args()
    if not args.finalize_only:
        init_stage(args.source, args.stage, args)
    else:
        if not (args.stage / 'SOURCE_INFO.json').is_file():
            raise RuntimeError('Missing staged build. Must stage first.')
        if not args.smoke or not args.smoke.is_file():
            raise RuntimeError('Smoke-test report required for final ZIP.')
        shutil.copy2(args.smoke, args.stage / 'SMOKE_TEST.txt')
        make_zip(args.stage, args.output)


if __name__ == '__main__':
    main()
