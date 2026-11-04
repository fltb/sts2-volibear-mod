"""Read-only projections against pinned native model types; no game or UI launch."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class PowerStackPresentationTests(unittest.TestCase):
    def test_all_rules_membership_and_no_mutation(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/power_stack_presentation/PowerStackPresentation.Tests.csproj',
                             args=('--nologo',), timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'POWER_STACK_PRESENTATION_PASS models=26 checks=\d+ readonly=true native-model-fixtures=true gameplay=NOT_RUN')
        rules = [line for line in result.stdout.splitlines() if line.startswith('STACK_RULE ')]
        self.assertEqual(len(rules), 26, output)
        self.assertIn('STACK_RULE ThunderArmorPower single=3 pair=7', rules)
        self.assertIn('STACK_RULE WelcomeThunderPower single=3 pair=4', rules)
        self.assertIn('STACK_RULE StandingPower single=3 pair=3', rules)
        self.assertIn('STACK_RULE StormConductionPower single=1 pair=2', rules)
        self.assertIn('STACK_RULE DomainPower single=3 changed=4 permanent=""', rules)
        print(next(line for line in result.stdout.splitlines() if line.startswith('POWER_STACK_PRESENTATION_PASS')))


if __name__ == '__main__':
    unittest.main()
