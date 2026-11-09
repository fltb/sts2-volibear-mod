"""Starter-upgrade source contracts; native Orobas acquisition/gameplay needs engine tests."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImmortalHeartContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upgrade = (ROOT / 'src/Volibear/Content/ImmortalHeart.cs').read_text(encoding='utf-8')
        cls.starter = (ROOT / 'src/Volibear/Content/VolibearRelicPool.cs').read_text(encoding='utf-8')
        cls.character = (ROOT / 'src/Volibear/Content/VolibearCharacter.cs').read_text(encoding='utf-8')
        cls.icons = (ROOT / 'src/Volibear/Presentation/VolibearIcons.cs').read_text(encoding='utf-8')
        cls.frozen = (ROOT / 'reference/bear-forge/examples/sts/src/content/characters/volibear/relics/heart.ts').read_text(encoding='utf-8')

    def test_native_starter_upgrade_extension_not_fake_boss_pool(self):
        self.assertIn('GetUpgradeReplacement() => ModelDb.Relic<ImmortalHeart>()', self.starter)
        self.assertIn('RelicRarity.Starter', self.upgrade)
        self.assertNotIn('RelicRarity.Boss', self.upgrade)
        self.assertIn('CustomID("VOLIBEAR_IMMORTAL_HEART")', self.upgrade)
        self.assertIn('CustomID("VOLIBEAR_HUNTERS_HEART")', self.starter)
        self.assertIn('[BaseLib.Utils.Pool(typeof(VolibearRelicPool))]', self.upgrade)
        self.assertIn('GenerateAllRelics() => []', self.starter)
        starting = re.search(r'StartingRelics\s*=>\s*\[([^]]+)\]', self.character)[1]
        self.assertEqual(re.findall(r'ModelDb.Relic<(\w+)>', starting), ['HuntersHeart'])
        self.assertIn('replaces:HuntersHeart', self.frozen)
        self.assertIn('Owner.Relics.OfType<HuntersHeart>().ToArray()', self.upgrade)
        self.assertIn('await RelicCmd.Remove(starter)', self.upgrade)
        self.assertNotIn('AddRelicInternal', self.upgrade)
        self.assertNotIn('RemoveRelicInternal', self.upgrade)

    def test_every_engage_draws_and_only_the_first_turn_engage_pays_energy(self):
        # Starter: every engage draws; the first engage of each player turn also pays energy.
        self.assertIn('AfterEngageCompleted(', self.starter)
        self.assertIn('Owner.PlayerCombatState?.TurnNumber', self.starter)
        self.assertIn('ReferenceEquals(lastCombat, completion.Combat) && lastTurn == turn', self.starter)
        self.assertIn('Draw(completion.Choices, 1m, Owner, false)', self.starter)
        self.assertIn('if (firstThisTurn) await MegaCrit.Sts2.Core.Commands.PlayerCmd.GainEnergy(1m, Owner)', self.starter)
        self.assertLess(self.starter.index('Draw(completion.Choices, 1m, Owner, false)'),
                        self.starter.index('GainEnergy(1m, Owner)'))
        # Upgrade: every engage pays energy and draws, with no per-turn gate.
        self.assertIn('AfterEngageCompleted(', self.upgrade)
        self.assertIn('PlayerCmd.GainEnergy(1m, Owner)', self.upgrade)
        self.assertIn('Draw(completion.Choices, 1m, Owner, false)', self.upgrade)
        self.assertNotIn('TurnNumber', self.upgrade)
        self.assertNotIn('lastCombat', self.upgrade)
        self.assertLess(self.upgrade.index('PlayerCmd.GainEnergy(1m, Owner)'),
                        self.upgrade.index('Draw(completion.Choices'))
        self.assertNotIn('override Task AfterRemoved()', self.upgrade)
        self.assertNotIn('+=', self.upgrade)  # No orphaned global event subscription.
        self.assertIn('hunter=install(1),immortal=install(2)', self.frozen)

    def test_existing_packaged_icons_and_localized_upgrade(self):
        for suffix in ['', 'Outline', 'Big']:
            self.assertIn(f'Presentation.VolibearIcons.StormCrown{suffix}', self.upgrade)
            self.assertIn(f'const string StormCrown{suffix} =', self.icons)
            self.assertIn(f'Presentation.VolibearIcons.LightningHeart{suffix}', self.starter)
        self.assertTrue((ROOT / 'src/Volibear/Presentation/icons/storm_crown.svg').is_file())
        self.assertIn('new RelicLoc(', self.upgrade)
        self.assertIn('"万古不灭", "每次完成迎战后，获得1能量并抽1张牌。"', self.upgrade)


if __name__ == '__main__':
    unittest.main()
