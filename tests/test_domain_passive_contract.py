"""Passive source/commit boundaries + actual native IL emission, not gameplay acceptance."""
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


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
        for expression in ('ReferenceEquals(receipt.Target, target)', 'ReferenceEquals(receipt.Source.Owner, receipt.SourceOwner)',
                           'ReferenceEquals(receipt.Combat, target.CombatState)', 'receipt.Input <= 0 || contribution <= 0',
                           'receipt.Generation != _generation', 'DomainEnemyEffects.ActiveFor(target)',
                           'ticket.Claimed = true', 'candidate.Target, target'):
            self.assertIn(expression, self.source)
        # Preserve the exact source allowlists and owner/combat identity checks.
        # Rampart intentionally grants block to its TurretOperator teammate; every
        # other source must still target its own snapshotted owner.
        strength, block = re.findall(r'receipt.Source is not\s*\(([^)]+)\)', self.source)
        self.assertEqual(re.findall(r'\w+Power', strength), [
            'RitualPower', 'SuckPower', 'TerritorialPower', 'HighVoltagePower',
            'EnragePower', 'RavenousPower', 'CrabRagePower'])
        self.assertEqual(re.findall(r'\w+Power', block), [
            'PlatingPower', 'CurlUpPower', 'SkittishPower', 'CrabRagePower', 'RampartPower'])
        for expression in ('ReferenceEquals(receipt.SourceCombat, receipt.Combat)',
                           'if (receipt.Source is RampartPower)',
                           'receipt.Strength || !receipt.SourceOwner.IsEnemy || receipt.SourceOwner.IsPlayer',
                           'target.Monster is not TurretOperator || !target.IsEnemy || target.IsPlayer',
                           'ReferenceEquals(receipt.SourceOwner.CombatState, receipt.Combat)',
                           'else if (!ReferenceEquals(receipt.SourceOwner, target)) return false;'):
            self.assertIn(expression, self.source)

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
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', 'mod', root=ROOT)
        result = runtime.run('tests/domain_passive_effects/DomainPassiveEffects.Tests.csproj', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS 38 production-decision/native-IL checks', result.stdout)
        self.assertIn('native passive behavior and D17 gameplay NOT RUN', result.stdout)


if __name__ == '__main__': unittest.main()
