"""Static contracts for 33 direct-effect classes; NOT engine/gameplay acceptance.

Render literal DynamicVars + upgrade deltas independently against the frozen JSON
and existing hand-authored face fixture. Do not execute/interpret Chinese effects.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Volibear/Content/Cards/DirectEffects.cs"
IDS = set("""C01 C02 C03 C05 C08 C09 C10 C11 C12 C18 C21 C22 C24 C26
U05 U06 U23 U24 U27 U28 U29 U35 U36 U37 U40 R01 R07 R09 R12 R13 R21 R23 R24""".split())
TARGETS = {"AnyEnemy": "single_enemy", "AllEnemies": "all_enemies", "Self": "self"}


def classes(text: str) -> dict[str, str]:
    return dict(re.findall(r"public sealed class Volibear_([CUR]\d\d) : VolibearCard(?:, INativeLightningSpell)?\s*\{(.*?)(?=\n\[BaseLib|\Z)", text, re.S))


def literal_vars(body: str) -> dict[str, int]:
    result = {}
    pattern = r'new (\w+Var)(?:<\w+>)?\((?:"(\w+)",\s*)?(\d+)(?:m)?(?:\s*[,\)])'
    for kind, explicit, number in re.findall(pattern, body):
        result[explicit or kind.removesuffix("Var")] = int(number)
    return result


def append_native_keywords(text: str, body: str, upgraded: bool) -> str:
    # CardModel.GetDescriptionForPile adds the native Exhaust sentence after body text.
    exhaust = bool(re.search(r'CanonicalKeywords\s*=>\s*\[CardKeyword.Exhaust\]', body))
    if upgraded and 'RemoveKeyword(CardKeyword.Exhaust)' in body:
        exhaust = False
    return text + ('消耗。' if exhaust else '')


def render(body: str, upgraded: bool) -> str:
    values = literal_vars(body)
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[key] += int(delta)
    description = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"\)', body)[1]
    text = re.sub(r"\{(\w+):diff\(\)\}", lambda m: str(values[m[1]]), description)
    return append_native_keywords(text, body, upgraded)


class DirectCardSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.cards = classes(cls.text)
        canonical = json.loads((ROOT / "reference/bear-forge/docs/volibear/cards_s2.json").read_text(encoding="utf-8"))
        cls.canonical = {card["code"]: card for card in canonical["cards"]}
        fixture = json.loads((ROOT / "tests/fixtures/card_expectations.json").read_text(encoding="utf-8"))
        cls.fixture = {card["card_id"]: card for card in fixture["cards"]}

    def test_exact_scope_ids_portraits_and_metadata(self):
        self.assertEqual(len(IDS), 33)
        self.assertEqual(set(self.cards), IDS)
        self.assertEqual(set(re.findall(r'CustomID\("VOLIBEAR_(\w+)"\)', self.text)), IDS)
        for code, body in self.cards.items():
            with self.subTest(card=code):
                cost, kind, rarity, target, portrait = re.search(
                    r'base\((\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+), "(\w+)"\)', body).groups()
                expected = self.fixture[code]
                self.assertEqual(portrait, code.lower())
                self.assertEqual(kind.lower(), expected["type"])
                self.assertEqual(rarity.lower(), expected["rarity"])
                self.assertEqual(TARGETS[target], expected["play_target"])
                delta = sum(map(int, re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body)))
                self.assertEqual([int(cost), int(cost) + delta], self.canonical[code]["cost"])
                title = re.search(r'new CardLoc\("([^"]+)"', body)[1]
                self.assertEqual(title, self.canonical[code]["name"])

    def test_all_66_localized_faces_match_canonical_without_relaxation(self):
        for code, body in self.cards.items():
            for upgraded, key in [(False, "base"), (True, "upgraded")]:
                with self.subTest(card=code, upgraded=upgraded):
                    actual = render(body, upgraded)
                    face = self.fixture[code]["faces"][int(upgraded)]
                    self.assertEqual(face["rules_text_zh"], self.canonical[code][key])
                    self.assertEqual(actual, face["display_text_zh"])
                    self.assertEqual("CardKeyword.Exhaust" in body,
                                     self.fixture[code]["faces"][int(upgraded)]["self_exhaust"])

    def test_exact_native_lightning_skill_markers(self):
        marked = set(re.findall(r'class Volibear_(\w+) : VolibearCard, INativeLightningSpell', self.text))
        self.assertEqual(marked, set('C24 U28 U35 U37 U40 R07 R09 R23'.split()))
        capabilities = (ROOT / 'src/Volibear/Content/CardCapabilities.cs').read_text(encoding='utf-8')
        self.assertNotIn('BeastForms', capabilities)
        self.assertNotIn('BeastShape', capabilities)
        self.assertIn('card.Type == CardType.Skill && card is INativeLightningSpell', capabilities)

    def test_pre_play_snapshots_are_distinct_from_effect_time_counters(self):
        for code in ["C26", "U36", "U40"]:
            self.assertIn("CardResolutionHooks.PriorLightningCount(this)", self.cards[code])
            self.assertNotIn("LightningBatches.GetTurnCount", self.cards[code])
        for code in ["U27", "R21", "R24"]:
            self.assertIn("LightningBatches.GetTurnCount(Owner.Creature)", self.cards[code])
        body = self.cards["U40"]
        self.assertLess(body.index("var prior ="), body.index("await LightningCmd.Deal("))
        self.assertLess(body.index("await LightningCmd.Deal("), body.index("if (prior >="))

    def test_composition_source_order_and_real_receipts(self):
        sequences = {
            "C05": ["await DomainPower.Open", "await DirectEffects.Attack"],
            "C10": ["await DirectEffects.Block", "await DirectEffects.Engage", "await DirectEffects.Attack"],
            "C18": ["await DomainPower.Open", "await DirectEffects.WeakAll"],
            "C21": ["await DirectEffects.Block", "await DomainPower.Open", "await DirectEffects.Draw"],
            "U23": ["await DirectEffects.WeakAll", "await DirectEffects.Block"],
            "U24": ["await DirectEffects.Attack", "await LightningCmd.Deal", "await CreatureCmd.Heal"],
            "U28": ["await DirectEffects.Block", "await DirectEffects.Engage", "await LightningCmd.DealAllEnemies"],
            "U35": ["await DirectEffects.Block", "await LightningCmd.DealAllEnemies", "await DirectEffects.Engage"],
            "U37": ["await LightningCmd.DealAllEnemies", "await DomainPower.Open"],
            "R01": ["await DirectEffects.Block", "await DomainPower.OpenPermanent"],
            "R09": ["await DirectEffects.Block", "await EngageCmd.PerformAll", "await LightningCmd.DealAllEnemies"],
        }
        for code, tokens in sequences.items():
            with self.subTest(card=code):
                positions = [self.cards[code].index(token) for token in tokens]
                self.assertEqual(positions, sorted(positions))
        for code in ["C10", "U28"]:
            self.assertIn("receipt.Taken", self.cards[code])
        self.assertIn("receipts.Sum(receipt => receipt.Taken)", self.cards["R09"])
        self.assertIn("CreatureCmd.Heal(Owner.Creature, hpLost)", self.cards["U24"])
        self.assertIn("var hpLost = await LightningCmd.Deal", self.cards["U24"])
        wave = self.cards["C22"]
        self.assertLess(wave.index("for (var hit"), wave.index("await DirectEffects.AttackAll"))
        self.assertLess(wave.index("await DirectEffects.AttackAll"), wave.index("await LightningCmd.DealAllEnemies"))
        self.assertNotIn("WithHitCount", wave)

    def test_fill_hand_is_one_finite_native_draw_request(self):
        body = re.sub(r"//[^\n]*", "", self.cards["R12"])
        self.assertIn('Math.Max(0m, Value("HandSize") - PileType.Hand.GetPile(Owner).Cards.Count)', body)
        self.assertEqual(body.count("DirectEffects.Draw("), 1)
        self.assertNotRegex(body, r"\b(?:while|for)\s*\(")


if __name__ == "__main__":
    unittest.main()
