"""Offline checks for YASB v1.5.2 manager and Komorebi bridge overlay.

This checks packaging wiring and source regressions; it cannot validate
Windows WScript.Shell shortcuts or live named-pipe communication.
"""
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1] / 'portable_helpers'

class TestAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = (BASE / 'YASB-Manager.ps1').read_text(encoding='utf-8')
        cls.manager_cmd = (BASE / 'YASB-Manager.cmd').read_text(encoding='utf-8')
        cls.bridge = (BASE / 'YASB-Komorebi-Bridge.ps1').read_text(encoding='utf-8')
        cls.launcher = (BASE / 'YASB-Portable.cmd').read_text(encoding='utf-8')

    def test_all_four_launch_files_present(self):
        self.assertEqual(len([p for p in BASE.iterdir() if p.is_file()]), 4)

    def test_startup_points_at_portable_launcher(self):
        self.assertIn('$link.TargetPath = $launcher', self.manager)
        self.assertIn("$link.Arguments = '--autostart'", self.manager)
        self.assertNotIn('$link.TargetPath = $exe', self.manager)

    def test_old_shortcut_migration(self):
        self.assertIn('YASB Native Portable - opt-in Windows startup shortcut', self.manager)
        self.assertIn("$filename -ine 'yasb.exe'", self.manager)
        self.assertIn("$filename -ine 'YASB-Portable.cmd'", self.manager)

    def test_opt_in_removal_and_status(self):
        for action in ('Enable-Startup','Disable-Startup','Show-StartupStatus','Get-OwnedShortcut'):
            self.assertIn(f'function {action}', self.manager)
        self.assertIn('Remove-Item -LiteralPath $file -Force', self.manager)

    def test_diagnostics_use_bridge(self):
        self.assertIn('-File $bridge -Diagnose', self.manager)
        self.assertIn('function Test-Komorebi', self.manager)

    def test_launcher_routes_autostart_and_diagnostics(self):
        self.assertIn('"--autostart" goto autostart', self.launcher)
        self.assertIn('"--diagnose" goto diagnose', self.launcher)
        self.assertIn('-Autostart', self.launcher)
        self.assertIn('-Diagnose', self.launcher)

    def test_wait_is_bounded_and_manual_mode_not_delayed(self):
        self.assertIn('if ($Autostart -and $null -eq $active)', self.bridge)
        self.assertIn('$attempt -le 30', self.bridge)
        self.assertIn('Start-Sleep -Seconds 2', self.bridge)
        self.assertIn('Configure-ChildEnvironment $active', self.bridge)

    def test_process_local_runtime_and_data(self):
        for var in ('KOMOREBI_PORTABLE_DATA_DIR', 'KOMOREBI_CONFIG_HOME',
                    'YASB_HOST_LOCALAPPDATA','YASB_CONFIG_HOME'):
            self.assertIn(var, self.bridge)
        self.assertIn("Join-Path $komorebi.Root 'Data\\Runtime'", self.bridge)
        self.assertNotIn('SetEnvironmentVariable(', self.bridge)

    def test_no_bypass_or_admin_or_task_creation(self):
        for source in (self.manager, self.manager_cmd, self.bridge, self.launcher):
            for suspicious in ('-ExecutionPolicy Bypass', 'EncodedCommand',
                               'Register-ScheduledTask', 'New-Service', 'Set-MpPreference',
                               'runas', 'schtasks.exe'):
                self.assertNotIn(suspicious.lower(), source.lower())

if __name__ == '__main__':
    unittest.main(verbosity=2)
