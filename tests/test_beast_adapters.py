"""Compiled production native-replacement orchestration; command boundaries are stubs."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class BeastNativeReplacement(unittest.TestCase):
    def test_native_replacement_responses_cost_lifetimes_and_owner_boundaries(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        dotnet = str(runtime.dotnet)
        generated = ROOT / 'artifacts/beast-bookkeeping'
        generated.mkdir(parents=True, exist_ok=True)
        selections = (ROOT / 'src/Volibear/Content/Cards/BeastEffects.cs').read_text(encoding='utf-8')
        (generated / 'ProductionSelections.cs').write_text(selections.split('[BaseLib.Utils.Attributes.CustomID', 1)[0], encoding='utf-8')
        controlled = (ROOT / 'src/Volibear/Content/Cards/ControlledEffects.cs').read_text(encoding='utf-8')
        coupon = controlled.split('public sealed class NextPlayDiscount', 1)[1].split('/// <summary>Native temporary-strength', 1)[0]
        imports = ['System', 'System.Linq', 'System.Collections.Generic', 'System.Threading.Tasks',
                   'BaseLib.Abstracts', 'MegaCrit.Sts2.Core.Combat', 'MegaCrit.Sts2.Core.Entities.Cards',
                   'MegaCrit.Sts2.Core.Entities.Creatures', 'MegaCrit.Sts2.Core.GameActions.Multiplayer',
                   'MegaCrit.Sts2.Core.Models', 'MegaCrit.Sts2.Core.Rooms', 'Volibear.Core']
        (generated / 'ProductionCoupon.cs').write_text(''.join('using ' + name + ';\n' for name in imports) +
            'namespace Volibear.Content;\npublic sealed class NextPlayDiscount' + coupon, encoding='utf-8')
        project = ROOT / 'tests/beast_bookkeeping/BeastBookkeeping.csproj'
        build = subprocess.run([dotnet, 'build', str(project), '-c', 'Release', '--nologo'],
                               cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180, env=runtime.environment())
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        dll = ROOT / 'artifacts/beast-bookkeeping/bin/net9.0/BeastBookkeeping.dll'
        result = subprocess.run([dotnet, str(dll)], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', timeout=60, env=runtime.environment())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'BEAST_NATIVE_REPLACEMENT_OK assertions=\d+; native-gameplay=NOT_RUN')
        self.assertEqual(result.stdout.count('BEAST_PRODUCTION_CASE_PASS'), 8)

    def test_no_card_type_overlay_or_private_metadata_writes_remain(self):
        source = (ROOT / 'src/Volibear/Core/BeastForms.cs').read_text(encoding='utf-8')
        self.assertIn('await CardCmd.Exhaust(context, card)', source)
        self.assertIn('CardPileCmd.AddGeneratedCardToCombat', source)
        self.assertNotIn('Harmony', source.replace('no beast Harmony patches', 'no patches'))
        for obsolete in ('forms.TryGetValue', 'PatchCardMembers', 'NativeCanonical.SetValue', 'IsConverted(', 'FilterOriginalHooks'):
            self.assertNotIn(obsolete, source)
        self.assertFalse((ROOT / 'src/Volibear/Core/BeastFormsAdapters.cs').exists())
        self.assertFalse((ROOT / 'src/Volibear/Core/BeastFormsMetadata.cs').exists())


if __name__ == '__main__':
    unittest.main()
