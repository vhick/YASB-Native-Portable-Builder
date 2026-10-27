"""v1.5.1 auto-discovery tests using the exact Python source injected into upstream.

Works offline on Linux and Windows. The actual running-process Win32 API remains
an integration check requiring a Windows machine with Komorebi running.
"""
from __future__ import annotations
import ast
import os
import shutil
import sys
import tempfile
import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'scripts' / 'patch_portable.py'


def load_resolver():
    code = ast.parse(PATCH.read_text(encoding='utf-8'))
    patch_fn = next(n for n in code.body if isinstance(n, ast.FunctionDef) and n.name == 'patch')
    resolver = next(ast.literal_eval(n.value) for n in patch_fn.body
                    if isinstance(n, ast.Assign) and any(isinstance(target, ast.Name)
                    and target.id == 'resolver' for target in n.targets))
    scope = {'os': os, 'sys': sys, 'logging': __import__('logging'), 'shutil': shutil, 'Path': Path}
    ast.parse(resolver)
    exec(compile(resolver, '<injected client auto-discovery>', 'exec'), scope)
    return scope


def run():
    code = PATCH.read_text(encoding='utf-8')
    assert 'retry Komorebi discovery on event listener reconnection' in code
    assert 'YASB_HOST_LOCALAPPDATA' in code
    assert 'komorebic.exe' in code
    # Confirm the guarded client modifications still apply to the upstream API shape.
    spec = importlib.util.spec_from_file_location('v15_patch_portable', PATCH)
    assert spec and spec.loader
    patch_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(patch_mod)
    scope = load_resolver()
    with tempfile.TemporaryDirectory() as fixture:
        client = Path(fixture) / 'client.py'
        client.write_text('''import logging
import subprocess
from typing import Any

type KomorebiNode = dict[str, Any]
class KomorebiClient:
    def __init__(self, komorebic_path: str = "komorebic.exe"):
        self._komorebic_path = komorebic_path
    @property
    def komorebic_path(self) -> str:
        return self._komorebic_path
    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        args = [self._komorebic_path, "subscribe", pipe_name]
        return subprocess.run(args)
    def query_state(self):
        return subprocess.check_output([self._komorebic_path, "state"])
    def cycle(self):
        return subprocess.Popen([self._komorebic_path, "cycle-workspace", "next"])
''', encoding='utf-8')
        patch_mod.replacement(client, 'import logging\n', 'import logging\nimport os\nimport shutil\nimport sys\nfrom pathlib import Path\n', 'test imports')
        patch_mod.replacement(client, 'type KomorebiNode = dict[str, Any]\n',
                              next(ast.literal_eval(n.value) for n in ast.parse(PATCH.read_text()).body
                                   if isinstance(n, ast.FunctionDef) and n.name == 'patch'
                                   for n in n.body if isinstance(n, ast.Assign)
                                   and any(isinstance(t, ast.Name) and t.id == 'resolver' for t in n.targets))
                              + 'type KomorebiNode = dict[str, Any]\n', 'test resolver insertion')
        patch_mod.replacement(client, 'self._komorebic_path = komorebic_path',
                              'self._komorebic_path = _portable_komorebi_path(komorebic_path)', 'test path selection')
        patch_mod.replacement(client, '        args = [self._komorebic_path, "subscribe", pipe_name]',
                              '        if self._komorebic_path == "komorebic.exe":\n'
                              '            self._komorebic_path = _portable_komorebi_path("komorebic.exe")\n'
                              '        args = [self._komorebic_path, "subscribe", pipe_name]', 'test reconnect')
        ast.parse(client.read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        portable_yasb = t / 'PortableApps' / 'YASB' / 'yasb.exe'
        portable_yasb.parent.mkdir(parents=True)
        portable_yasb.touch()
        nearby_cli = t / 'PortableApps' / 'komorebi' / 'komorebic.exe'
        nearby_cli.parent.mkdir(parents=True)
        nearby_cli.touch()
        running_cli = t / 'Other Portable Tools' / 'komorebic.exe'
        running_cli.parent.mkdir(parents=True)
        running_cli.touch()
        saved = portable_yasb.parent / 'Data' / 'Komorebi.path'
        saved.parent.mkdir()
        saved.write_text(str(nearby_cli), encoding='utf-8')
        with patch.object(sys, 'executable', str(portable_yasb)), \
             patch.dict(os.environ, {'YASB_PORTABLE': '1', 'YASB_KOMOREBIC_PATH': ''}), \
             patch.object(shutil, 'which', return_value=None):
            fn = scope['_portable_komorebi_path']
            scope['_running_komorebi_cli'] = lambda: str(running_cli)
            assert fn('komorebic.exe') == str(nearby_cli), 'Saved manual override should have priority'
            saved.unlink()
            assert fn('komorebic.exe') == str(running_cli), 'Running portable Komorebi should override installed PATH'
            scope['_running_komorebi_cli'] = lambda: None
            # Windows hosted runners can provide a DOS 8.3 alias (RUNNER~1)
            # for the same directory that Path.resolve() reports by its long name.
            # Compare actual file identity rather than textual path spelling.
            detected_nearby = fn('komorebic.exe')
            assert detected_nearby != 'komorebic.exe', 'Nearby Komorebi CLI must be discovered'
            assert Path(detected_nearby).is_file(), f'Detected CLI does not exist: {detected_nearby}'
            assert os.path.samefile(detected_nearby, nearby_cli), (
                f'Nearby CLI must be the correct file, found {detected_nearby!r}; expected {str(nearby_cli)!r}'
            )
            if os.path.normcase(os.path.normpath(detected_nearby)) != os.path.normcase(os.path.normpath(str(nearby_cli))):
                print('PASS: nearby Komorebi discovery handles distinct Windows short/long aliases of the same executable')
            nearby_cli.unlink()
            assert fn('komorebic.exe') == 'komorebic.exe', 'Unlocated app should not invent a binary'
            explicit = t / 'Special Folder' / 'komorebic.exe'
            explicit.parent.mkdir()
            explicit.touch()
            with patch.dict(os.environ, {'YASB_KOMOREBIC_PATH': str(explicit)}):
                assert fn('komorebic.exe') == str(explicit)
    print('PASS: v1.5.1 auto-discovery source parses; manual, running portable, nearby portable, missing and env override decisions')
    print('NOT TESTED: real Windows process enumeration, PowerShell execution, named-pipe events or GUI startup')


if __name__ == '__main__':
    run()
