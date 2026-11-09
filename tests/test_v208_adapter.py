"""Regression fixtures for upstream 2.0.8 refactor; not a Windows build test."""
from pathlib import Path
import ast
import tempfile
import unittest
import test_builder
patch = test_builder.patch

# Main, single_instance.py, cli/pipe.py, and Komorebi shapes based on the
# 2.0.8 tagged source. The rest use the original 2.0.7 fixtures where the
# checked text anchors are unchanged in the audited 2.0.8 source.
MODERN_KOMOREBI = '''import subprocess
class KomorebiClient:
    def __init__(self, komorebic_path='komorebic.exe'):
        self._komorebic_path = komorebic_path
    def query_state(self) -> KomorebiNode | None:
        try:
            output = subprocess.check_output([self._komorebic_path, "state"], timeout=self._timeout_secs,
                stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            return None
    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        args = [self._komorebic_path, "subscribe", pipe_name]
        proc = subprocess.run(args, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return proc
    def toggle(self):
        subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def workspace_actions(self):
        subprocess.run([self._komorebic_path, 'focus'], creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([self._komorebic_path, 'focus'], creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([self._komorebic_path, 'state'], creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([self._komorebic_path, 'state'], creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([self._komorebic_path, 'next'], creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([self._komorebic_path, 'previous'], creationflags=subprocess.CREATE_NO_WINDOW)
'''

class V208AdapterTests(unittest.TestCase):
    def make_fixture(self, root):
        test_builder.PatchUnitTests().setup_fixture(root)
        src = root / 'src'
        (src/'main.py').write_text('from core.utils.single_instance import single_instance_lock\n',encoding='utf8')
        (src/'core/utils/cli_server.py').unlink()
        (src/'core/utils/single_instance.py').write_text(
            'BAR_MUTEX_NAME = "yasb_reborn"\ndef single_instance_lock(name: str = BAR_MUTEX_NAME):\n    pass\n',encoding='utf8')
        (src/'core/cli').mkdir(parents=True)
        (src/'core/cli/pipe.py').write_text(
            'CLI_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_cli"\n'
            'LOG_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_log"\n',encoding='utf8')
        c = (src/'cli.py')
        client = c.read_text(encoding='utf8')
        client = client.replace('CLI_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_cli"\n','')
        client = client.replace('LOG_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_log"\n','')
        c.write_text(client,encoding='utf8')
        (src/'core/widgets/services/komorebi/client.py').write_text(MODERN_KOMOREBI,encoding='utf8')

    def test_modern_paths_and_windowless_subprocesses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_fixture(root)
            changed = patch.patch_files(root)
            paths = {x['path'] for x in changed}
            self.assertIn('src/core/utils/single_instance.py', paths)
            self.assertIn('src/core/cli/pipe.py', paths)
            self.assertNotIn('src/main.py', paths)
            self.assertNotIn('src/core/utils/cli_server.py', paths)
            mutex = (root/'src/core/utils/single_instance.py').read_text()
            pipe = (root/'src/core/cli/pipe.py').read_text()
            client = (root/'src/core/widgets/services/komorebi/client.py').read_text()
            self.assertIn('BAR_MUTEX_NAME = "yasb_native_portable"',mutex)
            self.assertIn('yasb_native_portable_pipe_cli',pipe)
            self.assertIn('yasb_native_portable_pipe_log',pipe)
            self.assertIn('discover_komorebic(self._komorebic_path)',client)
            self.assertIn('socket_is_online()',client)
            patch.verify_komorebi_no_windows(client,min_calls=10)
            self.assertEqual(client.count('creationflags=subprocess.CREATE_NO_WINDOW'), 10)
            with self.assertRaises(RuntimeError):patch.patch_files(root)

    def test_unexpected_new_subprocess_stops_build(self):
        source = MODERN_KOMOREBI + '\nsubprocess.Popen(["surprise.exe"])\n'
        with self.assertRaises(RuntimeError):
            patch.verify_komorebi_no_windows(source,min_calls=10)

    def test_ambiguous_refactor_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_fixture(root)
            main=root/'src/main.py'
            main.write_text('def single_instance_lock(name: str = "yasb_reborn"):\n    pass\n')
            with self.assertRaisesRegex(RuntimeError,'Ambiguous'):
                patch.patch_files(root)

if __name__ == '__main__':unittest.main()
