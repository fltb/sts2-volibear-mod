"""Native replacement metadata wiring; executed semantics live in beast_bookkeeping."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BeastNativeMetadataContracts(unittest.TestCase):
    def test_native_definitions_own_type_target_cost_and_capability(self):
        source = (ROOT / 'src/Volibear/Content/Cards/BeastTokens.cs').read_text(encoding='utf-8')
        self.assertIn('base(1, CardType.Attack, CardRarity.Token, TargetType.AnyEnemy', source)
        self.assertIn('base(1, CardType.Skill, CardRarity.Token, TargetType.AllEnemies', source)
        self.assertIn('Volibear_T02 : VolibearCard, INativeLightningSpell', source)
        self.assertEqual(source.count('CanonicalKeywords => [CardKeyword.Exhaust]'), 2)

    def test_narrow_native_inheritance_adapter_is_read_only(self):
        source = (ROOT / 'src/Volibear/Core/BeastFormsNativeCosts.cs').read_text(encoding='utf-8')
        self.assertIn('GetField("_localModifiers"', source)
        self.assertIn('SingleTurnProperty.GetValue(card)', source)
        self.assertIn('GetGetMethod(true)', source)
        for forbidden in ('.SetValue(', 'HarmonyLib', 'k__BackingField', 'SetCustomBaseCost(', 'GetAmountToSpend'):
            self.assertNotIn(forbidden, source)
        for native in ('AddThisCombat', 'AddUntilPlayed', 'AddThisTurn', 'AddThisTurnOrUntilPlayed'):
            self.assertIn(native, source)


if __name__ == '__main__':
    unittest.main()
