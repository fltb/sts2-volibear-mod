"""History/card contract checks plus the isolated production-helper executable.

The C# project compiles only the three owned files. It does not build/deploy the Mod
or launch the game. Native IL inspection checks adapter shape, not runtime behavior.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertIn('return card.SpendResources();', source)
        self.assertNotRegex(source, r'card\s*\.\s*CurrentTarget')
        self.assertNotIn('GainEnergy(', source)
        self.assertIn('canPlayCount != 1 || spendCount != 1', source)
        self.assertIn('VerifyNativePaymentTiming();', source)

    def test_production_ledgers_and_native_il(self):
        config_path = ROOT / '.local/config.json'
        parent_build = ROOT / 'src/Volibear/bin/Release/net9.0/Volibear.dll'
        if not config_path.is_file() or not parent_build.is_file():
            self.skipTest('Requires configured native references and existing parent build; never builds the whole Mod here.')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        dotnet = config['dotnet']
        if not Path(dotnet).is_file():
            self.skipTest('Configured .NET SDK unavailable.')
        data_name = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
        game_data = Path(config['game_dir']) / data_name
        env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1')
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
