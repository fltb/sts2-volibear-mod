"""Static lifecycle wiring checks; native optimized-consumer checks are separate C# tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BeastMetadataLifecycleContracts(unittest.TestCase):
    def test_conversion_captures_original_before_overlay_and_applies_same_card(self):
        source = (ROOT / 'src/Volibear/Core/BeastForms.cs').read_text(encoding='utf-8')
        self.assertLess(source.index('Metadata = BeastCardMetadata.Capture(card)'), source.index('forms.Add(card, form)'))
        self.assertIn('form.Metadata.Apply(card, shape == BeastShape.Claw)', source)
        self.assertIn('entry.Value.Metadata.Restore(entry.Key)', source)
        self.assertIn('Metadata = source.Metadata', source)
        self.assertIn('form.Metadata.Apply(clone, form.Shape == BeastShape.Claw)', source)
        self.assertNotIn('BeastCardMetadata.Capture(clone)', source)
        # Concrete virtual overrides still require the pre-existing getter adapters.
        self.assertIn('new[] { "Type" }, nameof(TypeProperty)', source)
        self.assertIn('new[] { "TargetType" }, nameof(TargetProperty)', source)

    def test_helper_changes_only_native_type_target_metadata(self):
        source = (ROOT / 'src/Volibear/Core/BeastFormsMetadata.cs').read_text(encoding='utf-8')
        self.assertIn('Required("<Type>k__BackingField")', source)
        self.assertIn('Required("<TargetType>k__BackingField")', source)
        self.assertIn('private readonly CardType originalType', source)
        self.assertIn('private readonly TargetType originalTarget', source)
        self.assertIn('TypeField.SetValue(card, originalType)', source)
        self.assertIn('TargetField.SetValue(card, originalTarget)', source)
        self.assertIn('claw ? CardType.Attack : CardType.Skill', source)
        self.assertIn('claw ? TargetType.AnyEnemy : TargetType.AllEnemies', source)
        for unrelated in ('_keywords', '_hasSingleTurnRetain', '_owner', '_deckVersion',
                          'SpendEnergy', 'SpendResources', 'GetAmountToSpend', 'SetCustomBaseCost'):
            self.assertNotIn(unrelated, source)


if __name__ == '__main__':
    unittest.main()
