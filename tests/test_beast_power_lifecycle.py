"""Two independent R28 choices and pinned source-card lifetime, without game launch."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class BeastPowerLifecycle(unittest.TestCase):
    def run_fixture(self, directory, marker, requirements=()):
        runtime = fixture_runtime(self, 'sdk', *requirements, root=ROOT)
        result = runtime.run(ROOT / 'tests' / directory, timeout=90, configuration='Debug')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    def test_two_instanced_power_choices_and_commit_guards(self):
        self.run_fixture('beast_power_lifecycle', 'BEAST_POWER_LIFECYCLE_OK checks=12')

    def test_pinned_native_source_lifetime_and_hook_iteration(self):
        self.run_fixture('beast_native_lifecycle', 'BEAST_NATIVE_LIFETIME_IL_OK checks=5', ('native',))
