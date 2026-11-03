"""Read-only projections against pinned native model types; no game or UI launch."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PowerStackPresentationTests(unittest.TestCase):
    def test_all_rules_membership_and_no_mutation(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native SDK configuration unavailable')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        if not all(path.is_file() for path in (Path(config['dotnet']), baselib, data / 'sts2.dll', data / 'GodotSharp.dll', data / '0Harmony.dll')):
            self.skipTest('Pinned native references unavailable')
        result = subprocess.run([config['dotnet'], 'run', '--project', str(ROOT / 'tests/power_stack_presentation/PowerStackPresentation.Tests.csproj'),
            '-c', 'Release', '-p:Sts2DataDir=' + str(data), '-p:BaseLibPath=' + str(baselib), '--nologo'],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'POWER_STACK_PRESENTATION_PASS models=26 checks=\d+ readonly=true native-model-fixtures=true gameplay=NOT_RUN')
        rules = [line for line in result.stdout.splitlines() if line.startswith('STACK_RULE ')]
        self.assertEqual(len(rules), 26, output)
        self.assertIn('STACK_RULE ThunderArmorPower single=3 pair=7', rules)
        self.assertIn('STACK_RULE WelcomeThunderPower single=3 pair=4', rules)
        self.assertIn('STACK_RULE StandingPower single=3 pair=3', rules)
        self.assertIn('STACK_RULE StormConductionPower single=1 pair=2', rules)
        self.assertIn('STACK_RULE DomainPower single=3 changed=4 permanent=本战', rules)
        print(next(line for line in result.stdout.splitlines() if line.startswith('POWER_STACK_PRESENTATION_PASS')))


if __name__ == '__main__':
    unittest.main()
