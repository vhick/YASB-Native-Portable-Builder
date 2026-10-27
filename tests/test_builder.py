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
        src = root / 'upstream'
        dist = src / 'src/dist'
        dist.mkdir(parents=True)
        for filename in (*package.BINARY_NAMES, 'library.zip'):
            (dist / filename).write_bytes(b'test fake binary - not executable')
        (src / 'src/settings.py').write_text('BUILD_VERSION = "2.0.8"\n', encoding='utf-8')
        (src / 'LICENSE').write_text('test only', encoding='utf-8')
        audit = root / 'audit.txt'
        audit.write_text('test scan', encoding='utf-8')
        args = type('Arguments', (), {'audit': audit, 'commit': 'a'*40, 'branch': 'main',
                                        'requested_ref': '', 'source': src})()
        stage = root / 'stage'
        package.init_stage(src, stage, args)
        metadata = json.loads((stage / 'SOURCE_INFO.json').read_text())
        assert metadata['upstream_source_version'] == '2.0.8'
        assert (stage / 'Data/.keep').exists()
        assert (stage / 'portable.flag').exists()
        archive = package.make_zip(stage, root / 'artifacts')
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            assert 'YASB-Native-Portable/yasb.exe' in names
            assert 'YASB-Native-Portable/SOURCE_INFO.txt' in names
            assert 'YASB-Native-Portable/Data/.keep' in names
    print('PASS: synthetic patch drift, staging, provenance, license and ZIP test')
    print('NOT TESTED: actual upstream clone, Windows freeze build, real YASB execution')


if __name__ == '__main__':
    run()
