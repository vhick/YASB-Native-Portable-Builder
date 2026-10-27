"""Check unsigned frozen CLI in two relocated directories on Windows.
No GUI is launched; registry and filesystem checks are limited to known keys.
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import tempfile
import winreg
from pathlib import Path


def reg_values(subkey: str) -> list[tuple[str, object, int]]:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ)
    except OSError:
        return []
    with k:
        result = []
        index = 0
        while True:
            try:
                result.append(winreg.EnumValue(k, index))
            except OSError:
                break
            index += 1
        return sorted(result, key=lambda x: x[0].lower())


def names(p: Path) -> set[str]:
    return {str(f.relative_to(p)) for f in p.rglob('*')} if p.exists() else set()


def cli(path: Path, *args: str) -> str:
    process = subprocess.run(
        [str(path / 'yasbc.exe'), *args], cwd=path, capture_output=True,
        text=True, encoding='utf-8', errors='replace', timeout=50,
        env=os.environ.copy(),
    )
    if process.returncode != 0:
        raise RuntimeError(f'CLI {args}: rc={process.returncode}, stdout={process.stdout!r}, stderr={process.stderr!r}')
    return process.stdout.strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--stage', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    actual_appdata = Path(os.environ['LOCALAPPDATA']) / 'YASB'
    actual_config = Path.home() / '.config' / 'yasb'
    before_appdata = names(actual_appdata)
    before_config = names(actual_config)
    registry_paths = [r'Software\Microsoft\Windows\CurrentVersion\Run',
                      r'Software\Microsoft\Windows NT\CurrentVersion\Fonts']
    before_regs = {key: reg_values(key) for key in registry_paths}
    lines = ['Windows CLI portability checks (NOT a full GUI/runtime test)']
    with tempfile.TemporaryDirectory(prefix='YASB portable test ') as td:
        root = Path(td)
        paths = [root / 'Portable drive A' / 'YASB', root / 'Portable drive B' / 'Moved YASB']
        for target in paths:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(a.stage, target)
            version = cli(target, '--version')
            output = cli(target, '--config')
            expected = (target / 'Data/Config').resolve()
            # Compare normalized Windows paths (case is not significant).
            if str(expected).casefold() not in output.casefold():
                raise RuntimeError(f'CLI config path wrong for {target}: actual {output!r}, expected {expected}')
            lines += [f'PASS: CLI --version under {target}: {version}',
                      f'PASS: CLI --config under {target}: {output}']
    if before_regs != {key: reg_values(key) for key in registry_paths}:
        raise RuntimeError('Registry Run or Fonts entries changed during relocation CLI smoke tests')
    if names(actual_appdata) != before_appdata:
        raise RuntimeError('Host LOCALAPPDATA/YASB changed during CLI checks')
    if names(actual_config) != before_config:
        raise RuntimeError('Host user .config/yasb changed during CLI checks')
    lines += ['PASS: HKCU Run/Fonts registry values unchanged by these CLI checks',
              'PASS: Host .config/yasb and LOCALAPPDATA/YASB entry names unchanged',
              'NOT TESTED: GUI behavior, complete registry or filesystem writes, removable-drive hardware.',
              'NOT TESTED: actual Windows installation/reformat or cross-machine Cloud credentials.']
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
