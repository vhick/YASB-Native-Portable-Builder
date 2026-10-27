"""Synthetic offline tests only. These do NOT demonstrate an upstream Windows build."""
from __future__ import annotations
import importlib.util
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


def run() -> None:
    patch = load('patch_portable')
    package = load('package_native')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
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
            # Missing archive must fail; a build artifact must not be emitted.
            archive_path.unlink()
            try:
                package.init_stage(src, root / f'missing_{layout}', args)
            except RuntimeError as exc:
                assert 'Python archive not found' in str(exc)
            else:
                raise AssertionError('A missing library.zip must be rejected')
    print('PASS: patch drift, both cx_Freeze library layouts, missing-archive rejection, staging, provenance and ZIP tests')
    print('NOT TESTED: actual upstream clone, Windows freeze build, real YASB execution')


if __name__ == '__main__':
    run()
