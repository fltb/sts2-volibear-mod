"""Execute production hint selection/merging against native API boundaries, not a game render."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class MechanicHintsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', root=ROOT)
        cls.dotnet = str(cls.runtime.dotnet)
        cls.output = ROOT / 'artifacts/mechanic-hints'
        cls.output.mkdir(parents=True, exist_ok=True)
        cls.env = cls.runtime.environment()
        result = subprocess.run([cls.dotnet, 'build', str(ROOT / 'tests/mechanic_hints/MechanicHints.csproj'),
                                 '-c', 'Release', '--nologo',
                                 f'-p:BaseIntermediateOutputPath={cls.output}/obj/',
                                 f'-p:OutputPath={cls.output}/bin/'], cwd=ROOT, env=cls.env,
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, case):
        result = subprocess.run([self.dotnet, str(self.output / 'bin/MechanicHints.dll'), case],
                                cwd=ROOT, env=self.env, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('MECHANIC_HINTS_PASS ' + case, result.stdout)
        self.assertIn('native-rendering=NOT_RUN', result.stdout)

    def test_rules_and_deduplicated_glossary(self): self.run_case('glossary')
    def test_actual_card_getter_preserves_existing_tips(self): self.run_case('compose')
    def test_beast_hints_show_current_form_only(self): self.run_case('forms')
    def test_language_reload_and_foreign_strings(self): self.run_case('reload')
    def test_current_shared_opportunities_are_read_only(self): self.run_case('live')


if __name__ == '__main__':
    unittest.main()
