"""History/card contract checks plus the isolated production-helper executable.

The C# project compiles only the three owned files. It does not build/deploy the Mod
or launch the game. Native IL inspection checks adapter shape, not runtime behavior.
"""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class HistoryCardContracts(unittest.TestCase):
    def test_stable_ids_and_base_damage(self):
        source = (ROOT / 'src/Volibear/Content/Cards/HistoryEffects.cs').read_text(encoding='utf-8')
        for code, cost, damage in [('C20', 1, 10), ('U07', 3, 28), ('U20', 1, 10), ('U38', 3, 18)]:
            with self.subTest(card=code):
                self.assertIn('CustomID("VOLIBEAR_' + code + '")', source)
                body = source.split('public sealed class Volibear_' + code, 1)[1].split('[BaseLib.Utils.Attributes.CustomID', 1)[0]
                self.assertIn('base(' + str(cost) + ', CardType.Attack', body)
                self.assertIn('new DamageVar(' + str(damage) + 'm, Move)', body)
        self.assertEqual(1, source.count('CustomID("VOLIBEAR_R14")'))
        self.assertIn('CardType.Power, CardRarity.Rare', source)

    def test_native_preflight_and_payment_not_current_target_or_refund(self):
        source = (ROOT / 'src/Volibear/Core/TargetCosts.cs').read_text(encoding='utf-8')
        # These are adapter contract checks, not native payment acceptance.
        self.assertIn('return card.CanPlay(out reason, out preventer);', source)
        spend = source.split('private static Task<(int, int)> SpendResolved(', 1)[1].split('\n    }', 1)[0]
        self.assertIn('using var scope = Enter(card, target);', spend)
        self.assertEqual(spend.count('card.SpendResources()'), 1)
        self.assertIn('var original = card.SpendResources();', spend)
        self.assertIn('CostPresentationReceipts.ObserveNativePayment(presentation, original);', spend)
        self.assertIn('return original;', spend)
        self.assertLess(spend.index('card.SpendResources()'), spend.index('ObserveNativePayment('))
        self.assertLess(spend.index('ObserveNativePayment('), spend.index('return original;'))
        self.assertNotIn('await ', spend)  # Preserve the native Task identity and completion.
        self.assertNotRegex(source, r'card\s*\.\s*CurrentTarget')
        self.assertNotIn('GainEnergy(', source)
        self.assertIn('canPlayCount != 1 || spendCount != 1', source)
        self.assertIn('VerifyNativePaymentTiming();', source)

    def test_production_ledgers_and_native_il(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', 'mod', root=ROOT)
        dotnet = str(runtime.dotnet)
        game_data = runtime.data
        env = runtime.environment()
        build = subprocess.run([dotnet, 'build', 'tests/history_bookkeeping/HistoryBookkeeping.csproj', '-c', 'Release',
                                '-p:Sts2DataDir=' + str(game_data), '--nologo'], cwd=ROOT, env=env,
                               capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
        self.assertEqual(0, build.returncode, build.stdout + build.stderr)
        run = subprocess.run([dotnet, str(ROOT / 'artifacts/history-bookkeeping/bin/net9.0/HistoryBookkeeping.dll'), '--native-il'],
                             cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertRegex(run.stdout, r'HISTORY_BOOKKEEPING_PASS checks=\d+')
        self.assertRegex(run.stdout, r'NATIVE_CALLSITE_INSPECTION_PASS checks=\d+')


if __name__ == '__main__':
    unittest.main()
