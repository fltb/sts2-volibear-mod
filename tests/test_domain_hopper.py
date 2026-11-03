"""Pinned native IL emission + direct production Hopper decisions/adapters, not gameplay."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
PROJECT = ROOT / 'tests/domain_hopper/DomainHopper.Tests.csproj'
DLL = ROOT / 'artifacts/domain-hopper/bin/net9.0/DomainHopper.Tests.dll'


def require_success(result):
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise AssertionError('Hopper output unavailable/undecodable')
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


class DomainHopperTests(unittest.TestCase):
    def test_production_decisions_actual_adapters_and_real_native_emission(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', 'host', root=ROOT)
        sdk = runtime.dotnet
        data = runtime.data
        def invoke(*args):
            return subprocess.run([str(sdk), *args], cwd=ROOT, capture_output=True,
                                  text=True, encoding='utf-8', timeout=180,
                                  env=runtime.environment())
        require_success(invoke('build', str(PROJECT), '-c', 'Release', '--nologo', '-p:Sts2DataDir=' + str(data)))
        result = invoke(str(DLL)); require_success(result)
        self.assertEqual(re.findall(r'^HOPPER_DECISION_NATIVE_IL_PASS checks=(\d+) gameplay=NOT_RUN$', result.stdout, re.MULTILINE), ['36'])
        self.assertEqual(re.findall(r'^HOPPER_ACTUAL_ADAPTER_PASS checks=(\d+) native-world=NOT_RUN$', result.stdout, re.MULTILINE), ['13'])

    def test_source_boundaries_do_not_replace_attack_return_or_global_apply(self):
        source = (ROOT / 'src/Volibear/Core/DomainHopperEffects.cs').read_text(encoding='utf-8')
        patches = (ROOT / 'src/Volibear/Core/DomainHopperEffects.Patches.cs').read_text(encoding='utf-8')
        for denied in ('BeforeDeath', 'RewriteReturn', 'RewriteEscape', 'Observe', 'Quarantine'):
            self.assertNotIn(denied, patches)
        self.assertEqual(patches.count('Bodies.Add('), 4)
        self.assertIn('nameof(CardPileCmd.RemoveFromDeck), typeof(IReadOnlyList<CardModel>)', patches)
        self.assertIn('nameof(MasterPile)', patches)
        self.assertIn('nameof(MasterState)', patches)
        self.assertIn('"BeforeCardRemoved"', patches)
        self.assertIn('m.Name == "GetResult"', patches)
        self.assertIn('try { return native(); }', source)
        self.assertIn('if (theft.Decision.FinishCommitted) card.RemoveFromState();', source)
        self.assertIn('if (theft is null || theft.Decision.FinishCommitted) history.MarkLootStolen(amount);', source)
        self.assertIn('if (!theft.Decision.FinishCommitted) return Task.CompletedTask;', source)
        self.assertNotIn('new HopperLedger', source)
        self.assertNotIn('Tasks.Clear', source)

    def test_build_failure_never_falls_back_to_stale_success(self):
        for result in (subprocess.CompletedProcess([], 1, 'compile failed', ''), subprocess.CompletedProcess([], 0, None, '')):
            with self.subTest(result=result), self.assertRaises(AssertionError):
                require_success(result)


if __name__ == '__main__':
    unittest.main()
