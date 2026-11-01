"""Source contracts for controlled cards, not native selection/gameplay acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from test_direct_cards import classes, literal_vars, append_native_keywords

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Volibear/Content/Cards/ControlledEffects.cs"
IDS = set("C04 C06 C07 C13 C15 C17 U13 U15 U17 R05 R08 R10 R17 R25 R31 U31".split())
TARGETS = {"AnyEnemy": "single_enemy", "AllEnemies": "all_enemies", "Self": "self", "RandomEnemy": "random_enemy"}


def render(body: str, upgraded: bool) -> str:
    values = literal_vars(body)
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[key] += int(delta)
    description = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"', body)[1]
    description = re.sub(r"\{IfUpgraded:show:([^{}]+)\}", lambda m: m[1] if upgraded else "", description)
    text = re.sub(r"\{(\w+):diff\(\)\}", lambda m: str(values[m[1]]), description)
    return append_native_keywords(text, body, upgraded)


class ControlledCardSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.cards = classes(cls.text)
        cls.canonical = {c["code"]: c for c in json.loads((ROOT / "reference/bear-forge/docs/volibear/cards_s2.json").read_text(encoding="utf-8"))["cards"]}
        cls.fixture = {c["card_id"]: c for c in json.loads((ROOT / "tests/fixtures/card_expectations.json").read_text(encoding="utf-8"))["cards"]}

    def test_exact_16_ids_metadata_and_native_x_cost(self):
        self.assertEqual(set(self.cards), IDS)
        self.assertEqual(set(re.findall(r'CustomID\("VOLIBEAR_(\w+)"\)', self.text)), IDS)
        for code, body in self.cards.items():
            with self.subTest(card=code):
                cost, kind, rarity, target, portrait = re.search(r'base\((\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+), "(\w+)"\)', body).groups()
                expected = self.fixture[code]
                self.assertEqual(kind.lower(), expected["type"])
                self.assertEqual(rarity.lower(), expected["rarity"])
                self.assertEqual(TARGETS[target], expected["play_target"])
                self.assertEqual(portrait, code.lower())
                if code in {"R17", "U31"}:
                    self.assertIn("protected override bool HasEnergyCostX => true", body)
                    costs = [-1, -1]  # Frozen JSON's X sentinel; native flag above owns X behavior.
                else:
                    delta = sum(map(int, re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body)))
                    costs = [int(cost), int(cost) + delta]
                self.assertEqual(costs, self.canonical[code]["cost"])
                self.assertEqual(re.search(r'new CardLoc\("([^"]+)"', body)[1], self.canonical[code]["name"])
        self.assertEqual(set(re.findall(r'class Volibear_(\w+) : VolibearCard, INativeLightningSpell', self.text)), {"R17"})

    def test_all_32_faces_and_exhaust_bits_match_frozen_contracts(self):
        for code, body in self.cards.items():
            for upgraded, key in [(False, "base"), (True, "upgraded")]:
                with self.subTest(card=code, upgraded=upgraded):
                    actual = render(body, upgraded)
                    self.assertEqual(actual, self.canonical[code][key])
                    self.assertEqual(actual, self.fixture[code]["faces"][int(upgraded)]["rules_text_zh"])
                    self.assertEqual("CardKeyword.Exhaust" in body, self.fixture[code]["faces"][int(upgraded)]["self_exhaust"])

    def test_native_selections_capacity_identity_and_scry_order(self):
        self.assertIn("CardSelectCmd.FromHand", self.text)
        self.assertIn("CardSelectCmd.FromCombatPile", self.text)
        self.assertIn("CardSelectCmd.FromSimpleGrid", self.text)
        self.assertIn("optional ? 0 : count, count", self.text)
        self.assertIn("CardPile.MaxCardsInHand - hand.Cards.Count", self.text)
        self.assertIn("hand.Cards.Count >= CardPile.MaxCardsInHand", self.text)
        self.assertIn("original.Where(selected.Contains)", self.text)
        self.assertIn("await CardPileCmd.Add(card, PileType.Hand)", self.text)
        self.assertNotRegex(self.text, r"\.First(?:OrDefault)?\(")
        scry = self.text.split("internal static async Task Scry", 1)[1].split('[BaseLib.Utils.Attributes.CustomID', 1)[0]
        self.assertIn("draw.Cards.Take(count).ToArray()", scry)
        self.assertIn("new CardSelectorPrefs(prompt, 0, looked.Length)", scry)
        self.assertIn("foreach (var card in looked)", scry)
        self.assertIn("await CardPileCmd.Add(card, PileType.Discard)", scry)
        self.assertNotIn("await CardCmd.Discard", scry)
        self.assertNotRegex(scry, r"(?:Shuffle|Reverse)\(")
        self.assertIn("CardCapabilities.IsThunderSpell(card)", self.cards["C15"])

    def test_coupon_is_shared_nonstacking_native_lifetime_and_clone_safe(self):
        coupon = self.text.split("public sealed class NextPlayDiscount", 1)[1].split("public sealed class VolibearChargeStrengthPower", 1)[0]
        self.assertIn(": CardModifier, ICustomModel", coupon)
        self.assertIn("Modifiers(card).OfType<NextPlayDiscount>().Any()", coupon)
        self.assertEqual(coupon.count("EnergyCost.AddThisTurnOrUntilPlayed(-1)"), 1)
        self.assertIn("play.PlayIndex == play.PlayCount - 1", coupon)
        self.assertIn("participants.Contains(card.Owner.Creature)", coupon)
        self.assertIn("RemoveModifier(card, this)", coupon)
        self.assertNotIn("override void OnInitialApplication", coupon)
        self.assertNotIn("SetThisTurn", coupon)
        self.assertNotIn("SetUntilPlayed", coupon)

    def test_temporary_strength_is_granted_once_and_positive_only_reclaimed(self):
        self.assertIn(": TemporaryStrengthPower, ICustomPower", self.text)
        self.assertIn("PowerCmd.Apply<VolibearChargeStrengthPower>", self.cards["C17"])
        self.assertNotIn("PowerCmd.Apply<StrengthPower>", self.cards["C17"])
        reclaim = self.cards["U13"]
        self.assertIn("power.Type == PowerType.Buff && power.Amount > 0", reclaim)
        self.assertIn("await PowerCmd.Remove(power)", reclaim)
        self.assertNotIn("-power.Amount", reclaim)
        self.assertLess(reclaim.index("PowerCmd.Apply<StrengthPower>"), reclaim.index("Owner.Creature.Powers.OfType"))

    def test_native_x_rng_and_formula_order(self):
        self.assertIn("var iterations = ResolveEnergyXValue()", self.cards["U31"])
        self.assertIn('var effectiveX = EnergyCost.CapturedXValue + (int)Value("Bonus")', self.cards["R17"])
        self.assertNotIn("ResolveEnergyXValue", self.cards["R17"])
        for code in ["R17", "U31"]:
            self.assertNotIn("PlayerCombatState.Energy", self.cards[code])
            self.assertNotIn("UseEnergy", self.cards[code])
        self.assertLess(self.cards["R17"].index("StormChargePower.Gain"), self.cards["R17"].index("for (var hit"))
        wave = self.cards["R08"]
        self.assertIn("Owner.RunState.Rng.CombatTargets.NextItem(candidates)", wave)
        self.assertIn('DirectEffects.Attack(context, this, target, Value("Damage"))', wave)
        self.assertIn('LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this)', wave)
        self.assertIn("ValueProp.Unpowered | Move", self.cards["R05"])
        self.assertIn('Owner.Creature.Block * (Value("Multiplier") - 1m)', self.cards["R05"])
        c06 = self.cards["C06"]
        self.assertLess(c06.index("Monster?.IntendsToAttack"), c06.index("await DirectEffects.Attack"))
        c31 = self.cards["R31"]
        sequence = ["await DirectEffects.Block", "await DomainPower.Open", "await CreatureCmd.LoseBlock", "await DirectEffects.Attack", "await LightningCmd.DealAllEnemies"]
        positions = [c31.index(token) for token in sequence]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
