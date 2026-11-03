"""Pinned native respawn counter guard; IL checks, not gameplay evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class RespawnGuardTests(unittest.TestCase):
    def test_actual_native_counter_guard_and_rejections(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/domain_revival_respawn_guard/DomainRevivalRespawnGuard.Tests.csproj',
                             args=('--nologo',), timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RESPAWN_GUARD_IL_PASS checks=9 negatives=4 native-gameplay=NOT_RUN', result.stdout)
        self.assertIn('REVIVE_AWAIT_GUARD_PASS generic-discard=true negatives=3 native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
