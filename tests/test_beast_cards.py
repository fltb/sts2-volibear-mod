"""Independent static seven-card/fourteen-face contracts, NOT engine acceptance.

The native renderer appends canonical Exhaust text after the card localization.
These sources deliberately omit a duplicate literal Exhaust sentence; the semantic
face composed here must equal the complete independently authored display fixture.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
IDS = {'U41', 'U42', 'U43', 'R27', 'R28', 'R29', 'R30'}
OVERRIDES = {'U41', 'U42', 'U43', 'R27', 'R29', 'R30'}
EXHAUST = {'U43', 'R27', 'R29'}


def variables(body, upgraded):
    values = {}
    for kind, explicit, value in re.findall(r'new (\w+Var)\((?:"(\w+)",\s*)?(\d+)m?(?=\s*[,\)])', body):
        values[explicit or kind.removesuffix('Var')] = int(value)
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[key] += int(delta)
    return values


def localized_face(body, upgraded):
    text = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"', body)[1]
    vals = variables(body, upgraded)
    text = re.sub(r'\{(\w+):diff\(\)\}', lambda match: str(vals[match[1]]), text)
    # CardModel.GetDescriptionForPile appends afterDescription keywords separately.
    if 'CanonicalKeywords => [CardKeyword.Exhaust]' in body:
        text += '消耗。'
    return text


class BeastCardStaticContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'src/Volibear/Content/Cards/BeastEffects.cs').read_text(encoding='utf-8')
        cls.powers = (ROOT / 'src/Volibear/Core/BeastPowers.cs').read_text(encoding='utf-8')
        cls.cards = dict(re.findall(r'public sealed class Volibear_([UR]\d\d) : VolibearCard\s*\{(.*?)(?=\n\[BaseLib|\Z)', cls.text, re.S))
        cls.fixture = {c['card_id']: c for c in json.loads((ROOT / 'tests/fixtures/card_expectations.json').read_text(encoding='utf-8'))['cards']}
        cls.canonical = {c['code']: c for c in json.loads((ROOT / 'reference/bear-forge/docs/volibear/cards_s2.json').read_text(encoding='utf-8'))['cards']}

    def test_exact_seven_ids_fourteen_costs_and_metadata(self):
        self.assertEqual(set(self.cards), IDS)
        self.assertEqual(set(re.findall(r'CustomID\("VOLIBEAR_(\w+)"\)', self.text)), IDS)
        target_map = {'AnyEnemy': 'single_enemy', 'Self': 'self'}
        face_count = 0
        for code, body in self.cards.items():
            with self.subTest(card=code):
                cost, kind, rarity, target, portrait = re.search(
                    r'base\((\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+), "(\w+)"\)', body).groups()
                fixture = self.fixture[code]
                self.assertEqual(kind.lower(), fixture['type'])
                self.assertEqual(rarity.lower(), fixture['rarity'])
                self.assertEqual(target_map[target], fixture['play_target'])
                self.assertEqual(portrait, code.lower())
                self.assertTrue(fixture['reward_pool'])
                self.assertNotIn('showInCardLibrary: false', body)
                title = re.search(r'new CardLoc\("([^"]+)"', body)[1]
                self.assertEqual(title, fixture['name_zh'])
                self.assertEqual(title, self.canonical[code]['name'])
                delta = sum(map(int, re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body)))
                costs = [int(cost), int(cost) + delta]
                self.assertEqual(costs, self.canonical[code]['cost'])
                self.assertEqual(costs, [f['cost'] for f in fixture['faces']])
                face_count += len(costs)
        self.assertEqual(face_count, 14)

    def test_fourteen_full_display_faces_and_native_keyword_bits(self):
        for code, body in self.cards.items():
            for index, key in enumerate(('base', 'upgraded')):
                with self.subTest(card=code, upgrade=bool(index)):
                    face = self.fixture[code]['faces'][index]
                    self.assertEqual(face['rules_text_zh'], self.canonical[code][key])
                    self.assertEqual(localized_face(body, bool(index)), face['display_text_zh'])
                    self.assertEqual('CanonicalKeywords => [CardKeyword.Exhaust]' in body, code in EXHAUST)
                    self.assertEqual(code in EXHAUST, face['self_exhaust'])
                    raw = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"', body)[1]
                    self.assertNotIn('消耗。', raw, 'Native Exhaust keyword must not be rendered twice')
                    self.assertNotRegex(body, r'CardKeyword\.(Retain|Unplayable|Ethereal)')

    def test_exact_six_display_overrides_never_rewrite_discount_semantics(self):
        changed = set()
        for code in IDS:
            for face in self.fixture[code]['faces']:
                if face['display_text_zh'] != face['rules_text_zh']:
                    changed.add(code)
                    self.assertIn('减费1', face['rules_text_zh'])
                    self.assertIn('本回合下次打出时设为0费', face['display_text_zh'])
        self.assertEqual(changed, OVERRIDES)
        self.assertEqual(self.text.count('NextPlayDiscount.Grant(card)'), 1)
        self.assertIn('if (discount && (!oldDays || shape == BeastShape.Claw))', self.text)
        self.assertNotRegex(self.text, r'(?:SetZero|SetThisTurn|SetUntilPlayed|SetToFree|AddThisTurnOrUntilPlayed)\(')
        self.assertIn('optional: true, discount: false', self.cards['R28'])
        self.assertIn('NextPlayDiscount', self.text)

    def test_independent_numeric_var_pairs(self):
        expected = {'U41': ({'Damage': 3}, {'Damage': 6}), 'U42': ({'Block': 3}, {'Block': 6}),
                    'U43': ({}, {}), 'R27': ({'Convert': 2}, {'Convert': 3}),
                    'R28': ({'Cards': 1}, {'Cards': 2}), 'R29': ({}, {}),
                    'R30': ({'Block': 6}, {'Block': 9})}
        for code, pair in expected.items():
            for upgraded in (False, True):
                with self.subTest(card=code, upgraded=upgraded):
                    self.assertEqual(variables(self.cards[code], upgraded), pair[int(upgraded)])

    def test_native_selection_capacity_frozen_batch_and_effect_order(self):
        helper = self.text.split('[BaseLib.Utils.Attributes.CustomID', 1)[0]
        for required in ('CardSelectCmd.FromHand', 'CardSelectCmd.FromCombatPile',
                         'optional ? 0 : count, count', 'hand.Cards.Count >= CardPile.MaxCardsInHand',
                         'draw.Cards.Count == 0', '!ReferenceEquals(c, source)',
                         'ReferenceEquals(card.Pile, hand)', 'ReferenceEquals(card.Pile, draw)',
                         'await CardPileCmd.Add(card, PileType.Hand)', 'var selected = all ? candidates',
                         'await CreatureCmd.GainBlock(source.Owner.Creature, 4m, ValueProp.Move, play)'):
            self.assertIn(required, helper)
        self.assertLess(helper.index('var candidates = hand.Cards.Where'), helper.index('await BeastForms.Convert'))
        self.assertNotRegex(helper, r'\.First(?:OrDefault)?\(')
        self.assertIn('c => c.Type == CardType.Attack', self.cards['U41'])
        self.assertIn('c => c.Type != CardType.Attack', self.cards['U42'])
        self.assertLess(self.cards['U41'].index('DamageCmd.Attack'), self.cards['U41'].index('BeastSelection.Transform'))
        self.assertLess(self.cards['U42'].index('CreatureCmd.GainBlock'), self.cards['U42'].index('BeastSelection.Transform'))
        self.assertLess(self.cards['U43'].index('BeastSelection.Search'), self.cards['U43'].index('BeastSelection.Transform'))
        self.assertIn('optional: true, oldDays: true, play: play', self.cards['R27'])
        self.assertIn('CardPile.MaxCardsInHand, all: true', self.cards['R29'])
        self.assertLess(self.cards['R28'].index('PowerCmd.Apply<BearSpiritPower>'), self.cards['R28'].index('BeastSelection.Transform'))
        self.assertLess(self.cards['R30'].index('BeastSelection.Transform'), self.cards['R30'].index('PowerCmd.Apply<WildernessPower>'))

    def test_instanced_powers_replay_guards_source_and_native_context(self):
        self.assertEqual(self.powers.count('PowerInstanceType.Instanced'), 2)
        self.assertEqual(self.powers.count('protected override object InitInternalData() => new Data()'), 2)
        self.assertEqual(self.powers.count('State.Source = cardSource ?? throw'), 2)
        self.assertEqual(self.powers.count('play.PlayIndex != 0'), 2)
        self.assertIn('AfterPlayerTurnStart(PlayerChoiceContext context, Player player)', self.powers)
        self.assertNotIn('override Task AfterPlayerTurnStartEarly', self.powers)
        self.assertNotIn('ThrowingPlayerChoiceContext', self.powers)
        self.assertIn('StormChargePower.Gain(CardResolutionHooks.CurrentChoices(play.Card), Owner, 1, State.Source)', self.powers)
        self.assertNotIn('CurrentChoices(State.Source)', self.powers)
        self.assertIn('State.ConversionTurn = BeastPowers.Turn(this)', self.powers)
        self.assertLess(self.powers.index('State.ConversionTurn = BeastPowers.Turn(this)'), self.powers.index('await CardPileCmd.Draw(context, Amount'))
        self.assertIn('case BeastShape.Claw when State.ClawTurn != BeastPowers.Turn(this)', self.powers)
        self.assertIn('case BeastShape.Body:', self.powers)
        self.assertIn('await PlayerCmd.GainEnergy(1, Owner.Player!)', self.powers)
        self.assertIn('change.Card.Owner.Creature.Powers.OfType<BearSpiritPower>().ToArray()', self.powers)

    def test_body_lightning_uses_card_facing_training_overload(self):
        source = (ROOT / 'src/Volibear/Core/BeastForms.cs').read_text(encoding='utf-8')
        self.assertIn('LightningCmd.DealAllEnemies(context, card.DynamicVars["Lightning"].BaseValue, card)', source)
        self.assertNotIn('LightningCmd.DealAllEnemies(context, card.Owner.Creature', source)


if __name__ == '__main__':
    unittest.main()
