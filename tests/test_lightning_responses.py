"""Direct production response dispatch; native world and subscriptions remain separate."""
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
PROJECT = ROOT / 'tests/lightning_responses/LightningResponses.csproj'
DLL = ROOT / 'artifacts/lightning-responses/bin/net9.0/LightningResponses.dll'
CASES = {
    'serial-controlled-await': 4,
    'snapshot-add-next-batch': 3,
    'inactive-removal-and-live-order': 6,
    'closed-scope-after-await': 7,
    'fault-after-counter-commit': 8,
    'cancel-after-counter-commit': 9,
    'same-delegate-distinct-instances': 3,
    'nested-independent-snapshots': 2,
    'empty-snapshot-no-world-read': 2,
}


def configured_sdk(test):
    return fixture_runtime(test, 'sdk', root=ROOT)


def require_success(result):
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise AssertionError('Missing or undecodable subprocess output')
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def validate_case(result, case):
    require_success(result)
    matches = re.findall(r'^LIGHTNING_RESPONSE_PASS name=(\S+) assertions=(\d+) native-gameplay=NOT_RUN$',
                         result.stdout, re.MULTILINE)
    if matches != [(case, str(CASES[case]))]:
        raise AssertionError('Missing/duplicate/changed response sequence result:\n' + result.stdout)


class LightningResponses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = configured_sdk(cls)
        cls.dotnet = str(cls.runtime.dotnet)
        require_success(cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo'))
        result = cls.invoke(str(DLL), '--list')
        require_success(result)
        if result.stdout.splitlines() != list(CASES):
            raise AssertionError('Required response sequences missing/changed:\n' + result.stdout)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([cls.dotnet, *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=cls.runtime.environment())

    def test_serial_controlled_await(self):
        validate_case(self.invoke(str(DLL), 'serial-controlled-await'), 'serial-controlled-await')

    def test_snapshot_add_next_batch(self):
        validate_case(self.invoke(str(DLL), 'snapshot-add-next-batch'), 'snapshot-add-next-batch')

    def test_inactive_removal_and_live_order(self):
        validate_case(self.invoke(str(DLL), 'inactive-removal-and-live-order'), 'inactive-removal-and-live-order')

    def test_closed_scope_after_await(self):
        validate_case(self.invoke(str(DLL), 'closed-scope-after-await'), 'closed-scope-after-await')

    def test_fault_after_counter_commit(self):
        validate_case(self.invoke(str(DLL), 'fault-after-counter-commit'), 'fault-after-counter-commit')

    def test_cancel_after_counter_commit(self):
        validate_case(self.invoke(str(DLL), 'cancel-after-counter-commit'), 'cancel-after-counter-commit')

    def test_same_delegate_distinct_instances(self):
        validate_case(self.invoke(str(DLL), 'same-delegate-distinct-instances'), 'same-delegate-distinct-instances')

    def test_nested_independent_snapshots(self):
        validate_case(self.invoke(str(DLL), 'nested-independent-snapshots'), 'nested-independent-snapshots')

    def test_empty_snapshot_no_world_read(self):
        validate_case(self.invoke(str(DLL), 'empty-snapshot-no-world-read'), 'empty-snapshot-no-world-read')


class LightningResponseContracts(unittest.TestCase):
    def test_actual_notify_uses_dispatch_and_retains_native_guards(self):
        source = (ROOT / 'src/Volibear/Core/LightningBatches.cs').read_text(encoding='utf-8')
        notify = source.split('internal static async Task Notify(', 1)[1].split('public static void ResetCombatState()', 1)[0]
        self.assertIn('await LightningResponseDispatch.Run(scope.Listeners, CanContinue,', notify)
        self.assertIn('listener => listener.Active, listener => listener.Invoke(context, batch)', notify)
        for guard in ('scope.Counter.IsClosed', '!CanUse(batch.Owner, out var combat)',
                      '!ReferenceEquals(batch.Combat, combat)', 'combat!.RoundNumber != batch.RoundNumber',
                      'Turn(batch.Owner) != batch.PlayerTurnNumber'):
            self.assertIn(guard, notify)
        self.assertNotIn('foreach', notify)
        self.assertNotIn('catch', notify)
        self.assertIn('scope.Counter.Close();', source)
        self.assertIn('foreach (var listener in scope.Listeners.ToArray()) listener.Dispose();', source)
        self.assertIn('scope.Listeners.Remove(this);', source)

    def test_absent_sdk_is_explicit_not_run(self):
        with patch.object(Path, 'is_file', return_value=False):
            with patch.dict(os.environ, {'VOLIBEAR_REQUIRE_NATIVE': '0'}):
                with self.assertRaisesRegex(unittest.SkipTest, 'sdk runtime unavailable'):
                    configured_sdk(self)
            with patch.dict(os.environ, {'VOLIBEAR_REQUIRE_NATIVE': '1'}):
                with self.assertRaisesRegex(AssertionError, 'sdk runtime unavailable'):
                    configured_sdk(self)

    def test_failed_build_or_output_does_not_skip(self):
        for result in (subprocess.CompletedProcess([], 1, 'failed build', ''),
                       subprocess.CompletedProcess([], 0, None, '')):
            with self.subTest(result=result), self.assertRaises(AssertionError):
                require_success(result)

    def test_nonzero_missing_wrong_and_duplicate_results_fail_closed(self):
        case = 'serial-controlled-await'
        good = f'LIGHTNING_RESPONSE_PASS name={case} assertions=4 native-gameplay=NOT_RUN\n'
        for code, text in ((1, good), (0, ''), (0, good + good), (0, good.replace(case, 'unknown')),
                           (0, good.replace('assertions=4', 'assertions=0'))):
            with self.subTest(code=code, text=text), self.assertRaises(AssertionError):
                validate_case(subprocess.CompletedProcess([], code, text, ''), case)


if __name__ == '__main__':
    unittest.main()
