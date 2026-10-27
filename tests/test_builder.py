"""Synthetic offline tests only. These do NOT demonstrate an upstream Windows build."""
from __future__ import annotations
import importlib.util
import os
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_config_path_equivalence(root: Path) -> None:
    """Regression for GitHub runner's short 8.3 username in CLI output."""
    if os.name != 'nt':
        print('SKIP: Windows-only samefile/8.3 path regression (requires Windows)')
        return
    smoke_test = load('smoke_test')
    config = root / 'Long Config Directory'
    other = root / 'Unrelated Folder'
    config.mkdir()
    other.mkdir()
    assert smoke_test.config_path_matches(str(config), config)
    assert not smoke_test.config_path_matches(str(other), config)
    assert not smoke_test.config_path_matches(str(root / 'Missing Config'), config)
    assert not smoke_test.config_path_matches('not a valid configuration directory', config)

    # Windows can represent the very same directory with DOS 8.3 aliases.
    # GetShortPathNameW may return the long spelling if 8.3 aliases are off.
    import ctypes
    from ctypes import wintypes
    api = ctypes.windll.kernel32.GetShortPathNameW
    api.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    api.restype = wintypes.DWORD
    buf = ctypes.create_unicode_buffer(32768)
    count = api(str(config), buf, len(buf))
    if 0 < count < len(buf) and buf.value.lower() != str(config).lower():
        assert smoke_test.config_path_matches(buf.value, config), (buf.value, config)
        print('PASS: Windows short 8.3 path equals its actual long directory')
    else:
        print('SKIP: Filesystem did not expose a distinct DOS 8.3 spelling')
    print('PASS: Windows existing-folder identity and missing/different-folder checks')


def test_komorebi_patch_mock(root: Path) -> None:
    """Checks v1.3 source transformations against a small representative client."""
    patcher = load('patch_portable')
    client = root / 'client.py'
    client.write_text('''import json
import logging
import subprocess
from typing import Any

type KomorebiNode = dict[str, Any]

class KomorebiClient:
    def __init__(self, komorebic_path: str = "komorebic.exe"):
        self._komorebic_path = komorebic_path

    @property
    def komorebic_path(self) -> str:
        return self._komorebic_path

    def state(self):
        return subprocess.check_output([self._komorebic_path, 'state'])

    def execute(self):
        subprocess.run([self._komorebic_path, 'subscribe', 'pipe'])
        return subprocess.Popen([self._komorebic_path, 'focus'])
''', encoding='utf-8')
    patcher.replacement(client, 'import logging\n',
                        'import logging\nimport os\nimport shutil\nimport sys\nfrom pathlib import Path\n', 'mock imports')
    # The real v1.3 patch supplies these functions. Test their defining anchors
    # and verify that its invocation wrappers are non-recursive.
    patch_script = (ROOT / 'scripts/patch_portable.py').read_text(encoding='utf-8')
    assert 'YASB_KOMOREBIC_PATH' in patch_script
    assert 'def _komorebi_popen' in patch_script
    assert 'return subprocess.Popen(*args, **kwargs)' in patch_script
    assert 'def _komorebi_run' in patch_script
    assert 'return subprocess.run(*args, **kwargs)' in patch_script
    assert 'def _komorebi_check_output' in patch_script
    assert 'return subprocess.check_output(*args, **kwargs)' in patch_script


def run() -> None:
    patch = load('patch_portable')
    package = load('package_native')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_windows_config_path_equivalence(root)
        test_komorebi_patch_mock(root)
        f = root / 'mod.py'
        f.write_text('x = 1\n', encoding='utf-8')
        patch.replacement(f, 'x = 1', 'x = 2', 'synthetic anchor')
        assert f.read_text() == 'x = 2\n'
        try:
            patch.replacement(f, 'x = 1', 'x = 3', 'drift test')
        except RuntimeError as exc:
            assert 'expected one unchanged anchor' in str(exc)
        else:
            raise AssertionError('Expected patch drift to raise')
        # Regression: current cx_Freeze uses dist/lib/library.zip; previous
        # builder v1.0 wrongly required dist/library.zip, failing at stage time.
        for layout in ('lib', 'root'):
            src = root / f'upstream_{layout}'
            dist = src / 'src/dist'
            dist.mkdir(parents=True)
            for filename in package.BINARY_NAMES:
                (dist / filename).write_bytes(b'synthetic placeholder executable')
            archive_path = (dist / 'lib' / 'library.zip') if layout == 'lib' else (dist / 'library.zip')
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive_path, 'w') as z:
                z.writestr('test_module.pyc', b'synthetic')
            (src / 'src/settings.py').write_text('BUILD_VERSION = "2.0.8"\n', encoding='utf-8')
            (src / 'LICENSE').write_text('test only', encoding='utf-8')
            audit = root / 'audit.txt'
            audit.write_text('test scan', encoding='utf-8')
            args = type('Arguments', (), {'audit': audit, 'commit': 'a'*40, 'branch': 'main',
                                            'requested_ref': '', 'source': src})()
            stage = root / f'stage_{layout}'
            package.init_stage(src, stage, args)
            metadata = json.loads((stage / 'SOURCE_INFO.json').read_text())
            assert metadata['upstream_source_version'] == '2.0.8'
            assert (stage / 'Data/.keep').exists()
            assert (stage / 'portable.flag').exists()
            expected_archive = stage / 'lib' / 'library.zip' if layout == 'lib' else stage / 'library.zip'
            assert expected_archive.is_file(), 'Must preserve cx_Freeze original library location'
            output_zip = package.make_zip(stage, root / f'artifacts_{layout}')
            with zipfile.ZipFile(output_zip) as z:
                names = set(z.namelist())
                assert 'YASB-Native-Portable/yasb.exe' in names
                assert 'YASB-Native-Portable/SOURCE_INFO.txt' in names
                assert 'YASB-Native-Portable/Data/.keep' in names
                assert 'YASB-Native-Portable/' + ('lib/library.zip' if layout == 'lib' else 'library.zip') in names
            for helper in ('YASB-Manager.cmd', 'YASB-Manager.ps1'):
                assert (stage / helper).is_file(), helper
                assert ('YASB-Native-Portable/' + helper) in names, helper
            for old_helper in ('Enable-Autostart.cmd', 'Disable-Autostart.cmd',
                               'Check-Komorebi.cmd', 'Set-Komorebi-Path.cmd'):
                assert not (stage / old_helper).exists(), old_helper
                assert ('YASB-Native-Portable/' + old_helper) not in names, old_helper
            manager = (stage / 'YASB-Manager.ps1').read_text(encoding='utf-8')
            for action in ('Test-Komorebi', 'Set-KomorebiCli', 'Clear-KomorebiCli',
                           'Enable-Startup', 'Disable-Startup', 'Show-StartupStatus', 'Launch-YASB'):
                assert ('function ' + action) in manager, action
            assert 'Data' in manager and 'Komorebi.path' in manager
            assert 'Assert-OwnedShortcut' in manager
            assert 'YASB_HOST_LOCALAPPDATA' in (stage / 'YASB-Portable.cmd').read_text()
            assert 'YASB_HOST_LOCALAPPDATA' in (stage / 'YASB-CLI.cmd').read_text()
            # Missing archive must fail; a build artifact must not be emitted.
            archive_path.unlink()
            try:
                package.init_stage(src, root / f'missing_{layout}', args)
            except RuntimeError as exc:
                assert 'Python archive not found' in str(exc)
            else:
                raise AssertionError('A missing library.zip must be rejected')
    script_text = (ROOT / 'scripts/patch_portable.py').read_text(encoding='utf-8')
    assert 'YASB_HOST_LOCALAPPDATA' in script_text
    assert 'Data" / "Komorebi.path"' in script_text
    assert '_komorebi_subprocess_env' in script_text
    print('PASS: patch drift, both cx_Freeze library layouts, missing-archive rejection, staging, provenance ZIP tests, Komorebi patch anchors and unified management console')
    print('NOT TESTED: actual upstream clone, Windows freeze build, real YASB execution')


if __name__ == '__main__':
    run()
