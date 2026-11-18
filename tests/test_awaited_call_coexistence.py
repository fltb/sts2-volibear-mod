"""Real Harmony exercises production awaited-call composition and capability yielding.

The foreign matcher and async combat-shaped target are explicit fixtures, not an
installed community framework or the native game.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime

CASES = ('own-first', 'foreign-first', 'yield-and-restore', 'legacy-producer-conflict', 'awaiter-padding', 'committed-capability', 'validation')
PROJECT = ROOT / 'tests/awaited_call_coexistence/AwaitedCallCoexistence.Tests.csproj'
DLL = ROOT / 'artifacts/awaited-call-coexistence/bin/net9.0/AwaitedCallCoexistence.Tests.dll'


class AwaitedCallCoexistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', 'harmony', root=ROOT)
        built = cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo',
                           '-p:HarmonyPath=' + str(cls.runtime.harmony.resolve()))
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        listed = cls.invoke(str(DLL), '--list')
        if listed.returncode or tuple(listed.stdout.splitlines()) != CASES:
            raise AssertionError(listed.stdout + listed.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.runtime.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180, env=cls.runtime.environment())

    def run_case(self, case):
        result = self.invoke(str(DLL), case)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        receipt = re.findall(r'^AWAITED_CALL_COEXISTENCE_PASS name=(\S+) assertions=(\d+) '
                             r'real-harmony=2\.4\.2\.0 foreign-matcher=fixture native-gameplay=NOT_RUN$',
                             result.stdout, re.MULTILINE)
        self.assertEqual(len(receipt), 1, output)
        self.assertEqual(receipt[0][0], case, output)
        self.assertGreaterEqual(int(receipt[0][1]), 4, output)

    def test_async_segments_in_both_installation_orders(self):
        for case in ('own-first', 'foreign-first'):
            with self.subTest(case=case):
                self.run_case(case)

    def test_precise_binding_yields_and_restores_after_recomposition(self):
        self.run_case('yield-and-restore')

    def test_old_task_wrapper_fails_the_independent_matcher(self):
        self.run_case('legacy-producer-conflict')

    def test_invalid_contracts_are_rejected(self):
        self.run_case('validation')

    def test_harmless_awaiter_padding_keeps_the_foreign_matcher_working(self):
        self.run_case('awaiter-padding')

    def test_capability_reports_only_the_committed_patch_chain(self):
        self.run_case('committed-capability')


if __name__ == '__main__':
    unittest.main()
