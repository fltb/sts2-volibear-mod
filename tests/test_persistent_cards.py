"""Independent frozen-face/source-contract checks for the 12 persistent cards.

These tests do NOT claim engine acceptance, runtime ordering or successful Harmony
patching. Numeric/text expectations come from frozen reference and hand-reviewed
fixture, never generated from the C# being checked.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Volibear/Content/Cards/PersistentEffects.cs"
POWERS = ROOT / "src/Volibear/Core/PersistentPowers.cs"
IDS = set("U02 U03 U04 U19 U21 U25 U26 U32 U34 R02 R16 R18".split())


def classes(text: str) -> dict[str, str]:
    # A card may implement supported contracts such as ITomeCard after its
    # exact VolibearCard base; keep the card identity and body captures intact.
    interfaces = r"(?:\s*,\s*(?:global::)?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)*"
    return dict(re.findall(r"public sealed class Volibear_([UR]\d\d) : VolibearCard" +
                           interfaces + r"\s*\{(.*?)(?=\n\[BaseLib|\Z)", text, re.S))


def render(body: str, upgraded: bool) -> str:
    values = {}
    for kind, explicit, number in re.findall(r'new (\w+Var)(?:<\w+>)?\((?:"(\w+)",\s*)?(\d+)(?:m)?(?:\s*[,\)])', body):
        values[explicit or kind.removesuffix("Var")] = int(number)
    if upgraded:
        for key, delta in re.findall(r'UpgradeVar\("(\w+)",\s*(-?\d+)m\)', body):
            values[key] += int(delta)
    text = re.search(r'new CardLoc\("[^"]+",\s*"([^"]+)"\)', body)[1]
    text = re.sub(r"\{(\w+):diff\(\)\}", lambda m: str(values[m[1]]), text)
    return re.sub(r"\{IfUpgraded:show:([^}]*)\}", lambda m: m[1] if upgraded else "", text)


class PersistentCardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding="utf-8")
        cls.powers = POWERS.read_text(encoding="utf-8")
        cls.cards = classes(cls.text)
        data = json.loads((ROOT / "reference/bear-forge/docs/volibear/cards_s2.json").read_text(encoding="utf-8"))
        cls.canonical = {c["code"]: c for c in data["cards"]}
        fixture = json.loads((ROOT / "tests/fixtures/card_expectations.json").read_text(encoding="utf-8"))
        cls.fixture = {c["card_id"]: c for c in fixture["cards"]}

    def test_exact_owned_card_ids_no_r14(self):
        self.assertEqual(set(self.cards), IDS)
        self.assertEqual(set(re.findall(r'CustomID\("VOLIBEAR_(\w+)"\)', self.text)), IDS)
        self.assertNotIn("Volibear_R14", self.text)

    def test_metadata_and_costs_against_independent_fixture(self):
        for code, body in self.cards.items():
            with self.subTest(card=code):
                cost, kind, rarity, target, portrait = re.search(
                    r'base\((\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+), "(\w+)"\)', body).groups()
                expected = self.fixture[code]
                self.assertEqual(kind.lower(), expected["type"])
                self.assertEqual(rarity.lower(), expected["rarity"])
                self.assertEqual({"Self": "self", "AllEnemies": "all_enemies"}[target], expected["play_target"])
                self.assertEqual(portrait, code.lower())
                delta = sum(map(int, re.findall(r'EnergyCost\.UpgradeBy\((-?\d+)\)', body)))
                self.assertEqual([int(cost), int(cost) + delta], self.canonical[code]["cost"])
                self.assertEqual(re.search(r'new CardLoc\("([^"]+)"', body)[1], self.canonical[code]["name"])

    def test_all_24_faces_match_frozen_text(self):
        for code, body in self.cards.items():
            for upgraded, key in [(False, "base"), (True, "upgraded")]:
                with self.subTest(card=code, upgraded=upgraded):
                    self.assertEqual(render(body, upgraded), self.canonical[code][key])

    def test_executable_source_order_not_prose_order(self):
        # Hand-selected from cards/{uncommon,rare,domain,storm}.ts compositions.
        orders = {
            "U02": ["await LightningCmd.DealAllEnemies", "await PersistentEffects.Deploy<StormConductionPower>"],
            "U03": ["await DirectEffects.Block", "await StandingPower.Deploy"],
            "U04": ["await DirectEffects.Block", "await PersistentEffects.Deploy<BattleScarsPower>"],
            "U19": ["await DirectEffects.Draw", "await DomainPower.Open", "await PersistentEffects.Deploy<LingeringStormPower>"],
            "U25": ["await DirectEffects.Draw", "await PersistentEffects.Deploy<PreyStillStandsPower>"],
            "U26": ["await PersistentEffects.Deploy<GrowingFuryPower>", "await PowerCmd.Apply<StrengthPower>"],
            "U32": ["await DomainPower.Open", "await WelcomeThunderPower.Prepare", "await PersistentEffects.Deploy<WelcomeThunderPower>"],
            "U34": ["await DirectEffects.Block", "await PersistentEffects.Deploy<ThunderArmorPower>"],
            "R02": ["await ImmovableBodyPower.Deploy", "await DirectEffects.Block"],
            "R16": ["await PersistentEffects.Deploy<BattleBodyPower>", "await DirectEffects.Block"],
            "R18": ["await LightningCmd.DealAllEnemies", "await PersistentEffects.Deploy<ThunderPoolPower>"],
        }
        for code, calls in orders.items():
            with self.subTest(card=code):
                positions = [self.cards[code].index(call) for call in calls]
                self.assertEqual(positions, sorted(positions))

    def test_independent_sources_use_native_instanced_powers(self):
        expected = {"StormConductionPower", "BattleScarsPower", "LingeringStormPower", "ThunderAftershockPower",
                    "PreyStillStandsPower", "GrowingFuryPower", "WelcomeThunderPower", "ThunderArmorPower", "ThunderPoolPower"}
        actual = set(re.findall(r"public sealed class (\w+) : InstancedPersistentPower", self.powers))
        self.assertEqual(actual, expected)
        self.assertIn("PowerInstanceType.Instanced", self.powers)
        self.assertIn("protected override object InitInternalData() => new State()", self.powers)
        self.assertIn("Data.Subscription?.Dispose()", self.powers)

    def test_global_even_batches_and_single_deployment_bonus(self):
        body = self.powers.split("public sealed class ThunderAftershockPower", 1)[1].split("[BaseLib", 1)[0]
        self.assertIn("LightningBatches.GetTurnCount(Owner) >= 2", body)
        self.assertIn("receipt.CountThisTurn % 2 == 0", body)
        self.assertNotRegex(body, r"\b(?:for|while)\s*\(")
        self.assertNotIn("UnblockedDamage", body)
        self.assertIn("PlayerCmd.GainEnergy(1m", body)

    def test_no_replay_counting_and_no_stale_card_boolean(self):
        fury = self.powers.split("public sealed class GrowingFuryPower", 1)[1].split("[BaseLib", 1)[0]
        prey = self.powers.split("public sealed class PreyStillStandsPower", 1)[1].split("[BaseLib", 1)[0]
        self.assertIn("BeforeCardPlayed(CardPlay play)", fury)
        self.assertIn("!play.IsFirstInSeries", fury)
        self.assertIn("AttackHistory.CurrentAttackOrdinal(play) != 2", fury)
        self.assertIn("CardResolutionHooks.CurrentChoices(play.Card)", fury)
        self.assertIn("!play.IsLastInSeries", prey)
        self.assertIn("snapshot.IsSingleTargetAttack", prey)
        self.assertIn("AttackHistory.TargetAttackCount(play.Card.Owner, play.Target) != 2", prey)
        self.assertNotIn("snapshot.TargetOrdinal", prey)
        self.assertIn("CardResolutionHooks.DrawObserved", prey)
        self.assertIn("NextPlayDiscount.Grant(card)", prey)
        self.assertNotRegex(fury + prey, r"(?:static )?bool (?:played|triggered|counted)")

    def test_native_block_assignment_only_not_damage_reimplementation(self):
        self.assertIn("Math.Min(existing.Amount, decay) - existing.Amount", self.powers)
        self.assertIn("Math.Max(0, Owner.Block - Amount)", self.powers)
        self.assertIn("GetCustomAttribute<AsyncStateMachineAttribute>()", self.powers)
        self.assertIn("props.HasFlag(ValueProp.Move)", self.powers)
        self.assertNotIn("override bool ShouldClearBlock", self.powers)
        self.assertNotIn("__result = Math.Min", self.powers)
        self.assertNotIn("AttackCommand", self.powers)
        self.assertNotIn("LoseHpInternal", self.powers)

    def test_r16_uses_actual_positive_source_block_and_once_per_play(self):
        body = self.powers.split("public sealed class BattleBodyPower", 1)[1].split("[BaseLib", 1)[0]
        self.assertIn("amount > 0", body)
        self.assertIn("cardSource is not null", body)
        self.assertIn("CardResolutionHooks.CurrentPlayId(cardSource)", body)
        self.assertIn("!play.IsLastInSeries", body)
        self.assertIn("Data.BlockPlays.Remove", body)
        self.assertIn("PowerCmd.Apply<DexterityPower>", body)

    def test_no_text_interpreter_or_placeholder_effects(self):
        self.assertNotRegex(self.text + self.powers, r"TODO|NotImplementedException|if\s*\(testMode\)")
        self.assertNotIn("GetFormattedText", self.powers)
        self.assertNotIn("Regex", self.powers)


if __name__ == "__main__":
    unittest.main()
