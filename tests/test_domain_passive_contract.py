"""Passive source/commit boundaries + actual native IL emission, not gameplay acceptance."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DomainPassiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'src/Volibear/Core/DomainPassiveEffects.cs').read_text(encoding='utf-8')

    def test_source_callbacks_remain_native(self):
        for pair in ('typeof(RitualPower), "AfterSideTurnEnd"', 'typeof(SuckPower), "AfterAttack"',
                     'typeof(PlatingPower), "BeforeSideTurnStart"', 'typeof(PlatingPower), "BeforeSideTurnEndEarly"',
                     'typeof(CurlUpPower), "AfterCardPlayed"', 'typeof(SkittishPower), "AfterAttack"'):
            self.assertIn(pair, self.source)
        self.assertEqual(self.source.count('prefix:'), 1)
        self.assertIn('harmony.Patch(nativeReset, prefix: new HarmonyMethod(Handler(nameof(BeforeNativeReset))))', self.source)
        self.assertIn('private static void BeforeNativeReset() => Reset();', self.source)
        self.assertNotIn('HasGainedBlockThisTurn =', self.source)
        self.assertNotIn('Curled =', self.source)
        self.assertNotIn('PowerCmd.Remove(', self.source)
        self.assertNotIn('PowerCmd.Decrement(', self.source)
        self.assertIn('MoveNext(method)', self.source)
        self.assertIn('Strength source now consumes its result', self.source)

    def test_only_owned_positive_commit_can_cancel(self):
        for expression in ('ReferenceEquals(receipt.Target, target)', 'ReferenceEquals(receipt.Source.Owner, target)',
                           'ReferenceEquals(receipt.Combat, target.CombatState)', 'receipt.Input <= 0 || contribution <= 0',
                           'receipt.Generation != _generation', 'DomainEnemyEffects.ActiveFor(target)',
                           'ticket.Claimed = true', 'candidate.Target, target'):
            self.assertIn(expression, self.source)
        self.assertIn('Source is not (RitualPower or SuckPower)', self.source)
        self.assertIn('Source is not (PlatingPower or CurlUpPower or SkittishPower)', self.source)

    def test_native_commit_and_return_anchors_are_fail_closed(self):
        for anchor in ('Block precommit/await anchor changed', 'New power precommit/await anchor changed',
                       'Stacked power prehistory anchor changed', 'Native successful completion changed',
                       'Native result local changed', 'Unexpected EH boundary at passive insertion'):
            self.assertIn(anchor, self.source)
        self.assertIn('new(OpCodes.Leave, complete)', self.source)
        self.assertIn('new(OpCodes.Stloc_1)', self.source)

    def test_actual_task_rebind_reset_and_nested_ownership(self):
        for expression in ('ReferenceEquals(frame.Native, actualNative)', '_tasks.Remove(frame.Native)',
                           '_tasks.Add(actualNative, receipt)', 'frame.Generation != _generation',
                           'CombatSetUp += OnCombatSetUp', 'CombatEnded += OnCombatEnded',
                           'Pending.Value = previous', 'ForwardStack'):
            self.assertIn(expression, self.source)
        self.assertNotIn('AsyncLocal<Receipt', self.source)  # No broad ambient receipt inherited by nested effects.

    def test_real_assembly_transpilers_compile_and_reject_drift(self):
        config_file = ROOT / '.local/config.json'
        if not config_file.exists(): self.skipTest('Pinned native assemblies unavailable; native IL checks NOT RUN')
        config = json.loads(config_file.read_text(encoding='utf-8'))
        dotnet = Path(config.get('dotnet', ''))
        data = Path(config.get('game_dir', '')) / 'data_sts2_windows_x86_64'
        mod = ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll'
        if not dotnet.is_file() or not (data / 'sts2.dll').is_file() or not mod.is_file():
            self.skipTest('Actual game/built mod missing; no fake model substitution')
        result = subprocess.run([str(dotnet), 'run', '--project',
            str(ROOT / 'tests/domain_passive_effects/DomainPassiveEffects.Tests.csproj'), '-c', 'Release',
            '-p:Sts2DataDir=' + str(data)], cwd=ROOT, capture_output=True, text=True,
            timeout=120, env=dict(os.environ, DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS 26 production-decision/native-IL checks', result.stdout)
        self.assertIn('native passive behavior and D17 gameplay NOT RUN', result.stdout)


if __name__ == '__main__': unittest.main()
