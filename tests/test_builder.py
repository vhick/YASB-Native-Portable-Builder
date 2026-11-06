"""Offline self-tests (non-GUI); genuine Windows runtime tests are manual."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    path=ROOT/'scripts'/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

patch=load('patch_upstream')
resolver=load('resolve_source')
pack=load('package_native')

class PatchUnitTests(unittest.TestCase):
    def setup_fixture(self, root):
        targets={
          'settings.py': '''import os\nimport sys\nAPP_ID = "YASB.YetAnotherStatusBar"\nIS_FROZEN = getattr(sys, "frozen", False)\nSCRIPT_PATH = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(os.path.abspath(__file__))\nDEFAULT_CONFIG_DIRECTORY = os.getenv("YASB_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config", "yasb")\n''',
          'core/utils/system.py': '''import os\nfrom pathlib import Path\ndef app_data_path(filename=None):\n    folder = Path(os.environ["LOCALAPPDATA"]) / "YASB"\n    folder.mkdir(parents=True, exist_ok=True)\n    return folder / filename if filename else folder\n''',
          'core/utils/update_service.py': '''def is_update_supported():\n        return is_installed and is_arch_supported and IS_FROZEN and (not is_pr_build)\n''',
          'core/widgets/services/komorebi/client.py': '''import subprocess\nclass KomorebiClient:\n    def __init__(self):\n        self._komorebic_path = komorebic_path\n    def query_state(self) -> dict | None:\n        try:\n            x = subprocess.check_output(\n                [self._komorebic_path, "state"],\n                timeout=self._timeout_secs,\n                stderr=subprocess.PIPE,\n                shell=True,\n            )\n        except Exception:\n            pass\n    def toggle(self):\n        subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)\n        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n    def wait_until_subscribed_to_pipe(self, pipe_name: str):\n        proc = subprocess.Popen(\n            [self._komorebic_path, "subscribe", pipe_name], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE\n        )\n''',
        }
        targets.update({
          'main.py': 'def single_instance_lock(name: str = "yasb_reborn"):\n    pass\n',
          'core/utils/cli_server.py': ('CLI_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_cli"\n'
                                       'LOG_SERVER_PIPE_NAME = r"\\\\.\\pipe\\yasb_pipe_log"\n'),
          'cli.py': (r'''
CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"
AUTOSTART_FILE = EXE_PATH if os.path.exists(EXE_PATH) else None
            subprocess.Popen(["yasb.exe"])
        args, passthrough = parser.parse_known_args()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f"{AUTOSTART_FILE}")
            with self._open_startup_registry(winreg.KEY_ALL_ACCESS) as key:
                winreg.DeleteValue(key, APP_NAME)
'''),
          'core/cloud/session.py': '''    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "YASB" / CLOUD_DIR_NAME
''',
          'core/cloud/app.py': 'MUTEX_NAME = "Global\\\\YASB.Cloud.SingleInstance"\n',
          'core/cloud/constants.py': 'TASK_NAME = "YASB Cloud Automatic Backup"\n',
          'core/cloud/restore.py': '''from settings import SCRIPT_PATH
        found = shutil.which("yasbc")
        if found:
            return found
        bundled = Path(SCRIPT_PATH) / "yasbc.exe"
        return is_process_running(BAR_PROCESS_NAME)
        while is_process_running(BAR_PROCESS_NAME) and time.monotonic() < deadline:
''',
        })
        for key,data in targets.items():
            path=root/'src'/key
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data,encoding='utf-8')
        (root/'pyproject.toml').write_text('qt-css-engine @ git+https://github.com/Video-Nomad/qt-css-engine@dev',encoding='utf-8')

    def test_patches_anchor_and_containment(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            self.setup_fixture(root)
            result=patch.patch_files(root)
            self.assertEqual(len(result),13)
            css=patch.pin_css(root,'a'*40)
            self.assertIn('css_commit',css)
            settings=(root/'src/settings.py').read_text(encoding='utf-8')
            self.assertIn('PORTABLE_ROOT = SCRIPT_PATH if IS_FROZEN else None',settings)
            self.assertIn('Data", "Config"',settings)
            self.assertIn('YASB.NativePortable',settings)
            self.assertIn('Data" / "State"', (root/'src/core/utils/system.py').read_text())
            self.assertIn('return False',(root/'src/core/utils/update_service.py').read_text())
            client=(root/'src/core/widgets/services/komorebi/client.py').read_text()
            self.assertIn('socket_is_online()',client)
            self.assertIn('shell=False',client)
            self.assertIn('yasb_native_portable_pipe_cli',(root/'src/cli.py').read_text())
            self.assertIn('native_instance_running()', (root/'src/core/cloud/restore.py').read_text())
            self.assertEqual(len(list((root/'src/native_portable').glob('*.py'))),3)
            with self.assertRaises(RuntimeError):
                patch.patch_files(root)  # fail closed, not double-patch

    def test_patch_mismatch_fails_closed(self):
        with self.assertRaises(RuntimeError):
            patch.replace_one('missing','expected','replace','anchor')
        with self.assertRaises(ValueError):
            patch.pin_css(Path('.'),'not-a-commit')

class IdentityTests(unittest.TestCase):
    def test_numeric_semver_and_preview_filter(self):
        fake=[
            {'tag_name':'v2.0.9','draft':False,'prerelease':False},
            {'tag_name':'v2.0.10','draft':False,'prerelease':False},
            {'tag_name':'preview','draft':False,'prerelease':True},
            {'tag_name':'v9.0.0','draft':True,'prerelease':False},
            {'tag_name':'v3.0.0-rc1','draft':False,'prerelease':True},
        ]
        with mock.patch.object(resolver,'releases',return_value=iter(fake)):
            self.assertEqual(resolver.choose('latest')['tag_name'],'v2.0.10')
        with mock.patch.object(resolver,'releases',return_value=iter(fake)):
            with self.assertRaises(RuntimeError): resolver.choose('v3.0.0-rc1')

class PackageTests(unittest.TestCase):
    @staticmethod
    def fake_pe(path):
        content=bytearray(128)
        content[0:2]=b'MZ'
        struct.pack_into('<I',content,0x3c,80)
        content[80:84]=b'PE\x00\x00'
        struct.pack_into('<H',content,84,0x8664)
        path.write_bytes(content)

    def test_native_zip_contains_empty_directories(self):
        import zipfile
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'YASB-NativePortable'
            (root/'lib').mkdir(parents=True)
            (root/'assets/images').mkdir(parents=True)
            (root/'Data/Config').mkdir(parents=True)
            (root/'Data/State').mkdir(parents=True)
            (root/'LICENSES').mkdir(parents=True)
            for exe in pack.REQUIRED_EXES:self.fake_pe(root/exe)
            (root/'lib/library.zip').write_bytes(b'zip-data')
            (root/'assets/images/app_icon.png').write_bytes(b'icon')
            (root/'SOURCE-IDENTITY.json').write_text('{}')
            (root/'UPSTREAM-PATCHES.json').write_text('[]')
            (root/'DEPENDENCIES-PINNED.txt').write_text('package==1.0')
            (root/'LICENSES/DEPENDENCY-LICENSE-MANIFEST.json').write_text('[]')
            pack.validate(root)
            zpath=Path(t)/'native.zip'
            with zipfile.ZipFile(zpath,'w') as z:
                for folder in ('Data/','Data/Config/','Data/State/'):
                    z.writestr(root.name+'/'+folder,'')
                for p in root.rglob('*'):
                    if p.is_file():z.write(p,(Path(root.name)/p.relative_to(root)).as_posix())
            self.assertTrue(pack.verify_zip(zpath,root.name))
            self.assertEqual(pack.machine(root/'yasb.exe'),0x8664)
            (root/'AppNamePortable.exe').write_bytes(b'x')
            with self.assertRaises(ValueError):pack.validate(root)

class WorkflowTests(unittest.TestCase):
    def test_native_separation_and_release_policy(self):
        flow=(ROOT/'.github/workflows/build-native.yml').read_text(encoding='utf-8')
        self.assertIn('workflow_dispatch:',flow)
        self.assertIn('portable-release-publisher@v1.1.1',flow)
        self.assertIn("dry-run: 'true'",flow)
        self.assertIn("dry-run: 'false'",flow)
        self.assertNotIn('Portable-Package-Builder',flow)
        self.assertNotIn('PortableApps',flow)
        self.assertNotIn('upload-artifact',flow)

if __name__=='__main__':unittest.main()
