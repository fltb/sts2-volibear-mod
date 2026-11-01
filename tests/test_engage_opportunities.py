"""Direct production opportunity-kernel sequences; native gameplay is NOT_RUN."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tests/engage_opportunities/EngageOpportunities.csproj'
DLL = ROOT / 'artifacts/engage-opportunities/bin/net9.0/EngageOpportunities.dll'
CASES = {
    'reserve-reentry-partial-failure': 8,
    'natural-versus-early-skip': 10,
    'round-and-separate-enemies': 11,
    'reference-equality-collisions': 9,
    'combat-and-enemy-membership-guards': 11,
    'reset-and-combat-aba': 14,
    'diagnostic-entry-counts': 11,
    'suspended-interleaving': 11,
}


def configured_sdk():
    config = ROOT / '.local/config.json'
    if not config.is_file():
        raise unittest.SkipTest('Local SDK configuration absent; engage opportunities NOT_RUN')
    value = json.loads(config.read_text(encoding='utf-8')).get('dotnet')
    if value is None:
        raise unittest.SkipTest('SDK not configured; engage opportunities NOT_RUN')
    dotnet = Path(value)
    if not dotnet.is_file():
        raise unittest.SkipTest('Configured SDK unavailable; engage opportunities NOT_RUN')
    return dotnet


def require_success(result):
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise AssertionError('Subprocess output unavailable or undecodable')
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def validate_case(result, case):
    require_success(result)
    matches = re.findall(r'^ENGAGE_SEQUENCE_PASS name=(\S+) assertions=(\d+) native-gameplay=NOT_RUN$',
                         result.stdout, re.MULTILINE)
    if matches != [(case, str(CASES[case]))]:
        raise AssertionError('Missing, duplicate or changed sequence result:\n' + result.stdout + result.stderr)


class EngageOpportunities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = configured_sdk()
        # No prebuilt Mod, native dependencies or fallback to stale output after build failure.
        require_success(cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo'))
        listed = cls.invoke(str(DLL), '--list')
        require_success(listed)
        names = listed.stdout.splitlines()
        if len(names) != len(CASES) or set(names) != set(CASES):
            raise AssertionError('Required opportunity sequences missing/changed:\n' + listed.stdout)

    @classmethod
    def invoke(cls, *arguments):
        return subprocess.run([str(cls.dotnet), *arguments], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8', timeout=180,
                              env=dict(os.environ, DOTNET_NOLOGO='1'))

    def test_reserve_reentry_partial_failure(self):
        validate_case(self.invoke(str(DLL), 'reserve-reentry-partial-failure'), 'reserve-reentry-partial-failure')

    def test_natural_versus_early_skip(self):
        validate_case(self.invoke(str(DLL), 'natural-versus-early-skip'), 'natural-versus-early-skip')

    def test_round_and_separate_enemies(self):
        validate_case(self.invoke(str(DLL), 'round-and-separate-enemies'), 'round-and-separate-enemies')

    def test_reference_equality_collisions(self):
        validate_case(self.invoke(str(DLL), 'reference-equality-collisions'), 'reference-equality-collisions')

    def test_combat_and_enemy_membership_guards(self):
        validate_case(self.invoke(str(DLL), 'combat-and-enemy-membership-guards'), 'combat-and-enemy-membership-guards')

    def test_reset_and_combat_aba(self):
        validate_case(self.invoke(str(DLL), 'reset-and-combat-aba'), 'reset-and-combat-aba')

    def test_diagnostic_entry_counts(self):
        validate_case(self.invoke(str(DLL), 'diagnostic-entry-counts'), 'diagnostic-entry-counts')

    def test_suspended_interleaving(self):
        validate_case(self.invoke(str(DLL), 'suspended-interleaving'), 'suspended-interleaving')


class EngageRunnerContracts(unittest.TestCase):
    def test_absent_sdk_is_explicit_not_run(self):
        with patch.object(Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(unittest.SkipTest, 'NOT_RUN'):
                configured_sdk()

    def test_compile_failure_is_not_skip_or_stale_success(self):
        with self.assertRaises(AssertionError):
            require_success(subprocess.CompletedProcess([], 1, 'compile error', ''))

    def test_unavailable_output_fails_closed(self):
        with self.assertRaises(AssertionError):
            require_success(subprocess.CompletedProcess([], 0, None, ''))

    def test_nonzero_exit_rejects_pass_text(self):
        case = 'reserve-reentry-partial-failure'
        text = f'ENGAGE_SEQUENCE_PASS name={case} assertions=8 native-gameplay=NOT_RUN\n'
        with self.assertRaises(AssertionError):
            validate_case(subprocess.CompletedProcess([], 1, text, ''), case)

    def test_missing_wrong_duplicate_or_short_result_fails_closed(self):
        case = 'reserve-reentry-partial-failure'
        good = f'ENGAGE_SEQUENCE_PASS name={case} assertions=8 native-gameplay=NOT_RUN\n'
        for text in ('', good + good, good.replace(case, 'unknown'), good.replace('assertions=8', 'assertions=1')):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                validate_case(subprocess.CompletedProcess([], 0, text, ''), case)


if __name__ == '__main__':
    unittest.main()
