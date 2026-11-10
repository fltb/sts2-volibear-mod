"""Execute production B04/lifecycle sources with command-boundary doubles, not a game."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class BasicCardLifecycleTests(unittest.TestCase):
    def test_actual_b04_stops_at_terminal_block_and_attack_boundaries(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        result = runtime.run('tests/card_lifecycle/CardLifecycle.csproj', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('CARD_LIFECYCLE_UNIT_OK checks=21 engine=STUBBED native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
