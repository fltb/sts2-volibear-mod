"""Two independent R28 choices and pinned source-card lifetime, without game launch."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BeastPowerLifecycle(unittest.TestCase):
    def run_fixture(self, directory, marker):
        config_path = ROOT / '.local/config.json'
        if not config_path.exists():
            self.skipTest('Configured SDK unavailable; fixture NOT RUN')
        config = json.loads(config_path.read_text())
        dotnet = Path(config['dotnet'])
        if not dotnet.is_file():
            self.skipTest('Configured SDK unavailable; fixture NOT RUN')
        result = subprocess.run([str(dotnet), 'run', '--project', str(ROOT / 'tests' / directory)],
                                cwd=ROOT, text=True, capture_output=True, timeout=90,
                                env=dict(os.environ, DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    def test_two_instanced_power_choices_and_commit_guards(self):
        self.run_fixture('beast_power_lifecycle', 'BEAST_POWER_LIFECYCLE_OK checks=12')

    def test_pinned_native_source_lifetime_and_hook_iteration(self):
        if not (ROOT / '.local/game/data_sts2_linuxbsd_x86_64/sts2.dll').is_file():
            self.skipTest('Pinned native assemblies unavailable; native IL NOT RUN')
        self.run_fixture('beast_native_lifecycle', 'BEAST_NATIVE_LIFETIME_IL_OK checks=5')
