"""Prepared10 static source/face contracts. Not native engine/gameplay acceptance."""
from pathlib import Path
import json
import re
import unittest
from test_direct_cards import append_native_keywords

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/Content/Cards/PreparedEffects.cs'
CORE = ROOT / 'src/Volibear/Core/PreparedEffects.cs'
LIGHTNING = ROOT / 'src/Volibear/Content/LightningCmd.cs'
IDS = set('C14 C19 C25 U08 U10 U11 U12 U14 U39 R06'.split())


def bodies(text):
    return dict(re.findall(r'public sealed class Volibear_([CUR]\d\d) : VolibearCard\s*\{(.*?)(?=\n\[BaseLib|\Z)', text, re.S))


def render(body, upgrade):
    values = {}
    for kind, name, value in re.findall(r'new (\w+Var)(?:<\w+>)?\((?:"(\w+)",\s*)?(\d+)m?(?:\s*[,\)])', body):
        values[name or kind.removesuffix('Var')] = int(value)
    if upgrade:
        for name, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[name] += int(delta)
    text = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"', body)[1]
    def conditional(match):
        parts = match[1].split('|')
        return parts[0] if upgrade else (parts[1] if len(parts) > 1 else '')
    text = re.sub(r'\{IfUpgraded:show:([^{}]*)\}', conditional, text)
    text = re.sub(r'\{(\w+):diff\(\)\}', lambda m: str(values[m[1]]), text)
    return append_native_keywords(text, body, upgrade)


class PreparedCardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding='utf-8')
        cls.cards = bodies(cls.text)
        cls.core = CORE.read_text(encoding='utf-8')
        cls.lightning = LIGHTNING.read_text(encoding='utf-8')
        cls.canonical = {c['code']: c for c in json.loads((ROOT / 'reference/bear-forge/docs/volibear/cards_s2.json').read_text(encoding='utf-8'))['cards']}
        cls.fixture = {c['card_id']: c for c in json.loads((ROOT / 'tests/fixtures/card_expectations.json').read_text(encoding='utf-8'))['cards']}

    def test_all_20_faces_and_exhaust_variants(self):
        self.assertEqual(set(self.cards), IDS)
        self.assertEqual(set(re.findall(r'CustomID\("VOLIBEAR_(\w+)"\)', self.text)), IDS)
        for code, body in self.cards.items():
            for upgrade, face in [(False, 'base'), (True, 'upgraded')]:
                with self.subTest(code=code, upgrade=upgrade):
                    text = render(body, upgrade)
                    expected = self.fixture[code]['faces'][int(upgrade)]
                    self.assertEqual(expected['rules_text_zh'], self.canonical[code][face])
                    self.assertEqual(text, expected['display_text_zh'])
                    exhaust = 'CanonicalKeywords => [CardKeyword.Exhaust]' in body
                    if upgrade and 'RemoveKeyword(CardKeyword.Exhaust)' in body:
                        exhaust = False
                    self.assertEqual(exhaust, expected['self_exhaust'])

    def test_native_metadata_and_costs(self):
        for code, body in self.cards.items():
            with self.subTest(code=code):
                cost, kind, rarity, target, portrait = re.search(r'base\((\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+), "(\w+)"\)', body).groups()
                expected = self.fixture[code]
                self.assertEqual(kind.lower(), expected['type'])
                self.assertEqual(rarity.lower(), expected['rarity'])
                self.assertEqual({'Self': 'self', 'AnyEnemy': 'single_enemy'}[target], expected['play_target'])
                self.assertEqual(portrait, code.lower())
                delta = sum(map(int, re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body)))
                self.assertEqual([int(cost), int(cost) + delta], self.canonical[code]['cost'])
                self.assertEqual(re.search(r'new CardLoc\("([^"]+)"', body)[1], self.canonical[code]['name'])

    def test_real_choice_retention_and_full_native_replay(self):
        self.assertIn('CardSelectCmd.FromHand', self.cards['C19'])
        self.assertIn('card.Type == CardType.Attack', self.cards['C19'])
        self.assertIn('CardCmd.ApplyKeyword(card, CardKeyword.Retain)', self.core)
        self.assertIn('completionCard.Played += Complete', self.core)
        self.assertIn('card.Played -= Complete', self.core)
        self.assertIn('BeforeAttack(AttackCommand command)', self.core)
        self.assertIn('"_calculatedDamageVar"', self.core)
        self.assertIn('Calculated.GetValue(active.Command) is null', self.core)
        self.assertIn('commands.RemoveAll(entry => entry.Play != play)', self.core)
        self.assertIn('playCount + Amount', self.core)
        self.assertNotIn('OnPlayWrapper(', self.core)
        self.assertNotIn('SpendResources(', self.core)
        self.assertIn('CardCapabilities.IsThunderSpell, 1, false, false', self.cards['U39'])

    def test_next_cost_coupons_actual_play_and_current_forms(self):
        self.assertIn('amount - current', self.core)
        self.assertIn('if (amount > current)', self.core)
        self.assertIn('card.EnergyCost.CostsX || originalCost < 0', self.core)
        self.assertIn('!spent && play.IsFirstInSeries', self.core)
        self.assertIn('spent = true;', self.core)
        self.assertIn('participants.Contains(Owner)', self.core)
        declare = self.core.split('public static bool DeclaresEngage', 1)[1].split('protected override bool Eligible', 1)[0]
        self.assertNotIn('BeastForms', declare)
        self.assertEqual(set(re.findall(r'Volibear_([BCUR]\d\d)', declare)), set('B04 C04 C10 C11 U28 U35 R09'.split()))

    def test_training_includes_dynamic_but_only_c19_fixed(self):
        training = self.core.split('public sealed class CardDamageTraining', 1)[1].split('public sealed class NextAttackTrainingPower', 1)[0]
        unify = self.core.split('public sealed class UnifyPower', 1)[1].split('public sealed class PrimalThunderPower', 1)[0]
        self.assertIn('props.IsPoweredAttack() ? Amount : 0m', training)
        self.assertIn('props.IsPoweredAttack() ? Amount : 0m', unify)
        for body in [training, unify]:
            self.assertNotIn('HasFixedAttack', body)
            self.assertNotIn('Volibear_U05', body)
            self.assertNotIn('CalculatedDamageVar', body)
        self.assertIn('CardCapabilities.IsThunderSpell(card)', unify)
        self.assertNotIn('Volibear_R07', unify)
        self.assertNotIn('Volibear_R09', unify)
        self.assertIn('CardModifier.AddModifier<CardDamageTraining>(play.Card, Amount)', self.core)
        self.assertIn('ApplyStacked(CardModifier incoming) { Amount += incoming.Amount;', training)

    def test_lightning_origin_snapshot_native_accounting_and_round_expiry(self):
        light = self.lightning
        self.assertEqual(light.count('nativeCardOrigin: true'), 2)
        # Explicit-owner passive calls retain false both with and without hit receipts.
        self.assertEqual(light.count('nativeCardOrigin: false'), 2)
        for callback in ('', ', onResolved'):
            self.assertIn(
                'DealCore(choiceContext, owner, targets, amount, card, nativeCardOrigin: false' + callback + ')', light)
        self.assertIn('CardDamageTraining.Current(card) + UnifyPower.NativeThunderBonus(card)', light)
        self.assertIn('amount + charge + cardBonus + roundBonus', light)
        self.assertLess(light.index('var roundBonus ='), light.index('await CreatureCmd.Damage'))
        self.assertLess(light.index('var living ='), light.index('await CreatureCmd.Damage'))
        self.assertIn('ValueProp.Unpowered, owner, card', light)
        self.assertIn('results.Sum(result => result.HpLost)', light)
        self.assertIn('scope.Counter.Abort(ticket)', light)
        self.assertRegex(light, r'public static Task<int> Deal\(PlayerChoiceContext choiceContext, Creature owner,\s*IEnumerable<Creature> targets, decimal amount, CardModel\? card = null\)')
        self.assertRegex(light, r'public static Task<int> DealAllEnemies\(PlayerChoiceContext choiceContext, Creature owner,\s*decimal amount, CardModel\? card = null,\s*ICombatState\? state = null\)')
        primal = self.core.split('public sealed class PrimalThunderPower', 1)[1].split('public sealed class ThunderGuardPower', 1)[0]
        self.assertIn('if (side == CombatSide.Enemy)', primal)
        self.assertIn('Math.Max(0, DomainPlayerStatContributions.EffectiveStrength(Owner.Creature))', self.cards['U12'])
        self.assertLess(self.cards['U12'].index('var strength ='), self.cards['U12'].index('await PowerCmd.Apply<PrimalThunderPower>'))
        guard = self.core.split('public sealed class ThunderGuardPower', 1)[1].split('public sealed class PreparedAttackBonus', 1)[0]
        self.assertIn('PowerInstanceType.Instanced', guard)
        self.assertIn('AfterDamageReceived', guard)
        self.assertIn('!Owner.IsHittable', guard)
        self.assertIn('LightningCmd.Deal(context, Owner, new[] { dealer }, Amount, null, hits =>', guard)
        self.assertIn('BeforeSideTurnStart', guard)
        self.assertNotIn('result.UnblockedDamage > 0', guard)

    def test_bite_identity_uses_real_hit_and_actual_play(self):
        bite = self.core.split('public static class BiteMarks', 1)[1]
        self.assertIn('ConditionalWeakTable<ICombatState', bite)
        self.assertIn('TryAdd(target, play)', bite)
        self.assertIn('CardResolutionHooks.CurrentPlayId(card) != first', bite)
        self.assertIn('PowerType.None', bite)
        self.assertIn('AfterDamageGiven', self.cards['U08'])
        self.assertIn('props.IsPoweredAttack()', self.cards['U08'])
        self.assertNotIn('result.UnblockedDamage > 0', self.cards['U08'])
        self.assertLess(self.cards['U08'].index('DirectEffects.Block'), self.cards['U08'].index('DirectEffects.Attack'))


if __name__ == '__main__':
    unittest.main()
