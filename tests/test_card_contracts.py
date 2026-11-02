"""Independent rule fixtures and observation-comparator SELF-TESTS, not gameplay.

Run: python -m unittest discover -s tests -p test_card_contracts.py -v
Fixture: tests/fixtures/card_expectations.json (UTF-8, schema_version 1).

Future runner interface: import this module and call
compare_actual_results(load_fixture(), report, expected_run_id=..., expected_build=...,
                       evidence_root=Path(...)). Returns mismatch strings; [] means
only that supplied observations match these 16 finite contracts. This cannot prove
that a producer actually used the engine, and is NOT a G2/G3/G4 release gate.

Report shape:
  schema_version: 1; run_id: str; execution_kind: "real_engine";
  build: {game_version, game_commit, framework_version, package_version,
          source_commit, source_dirty}; command: [str, ...];
  exit_code: 0; timed_out: false;
  cases: [{case_id, run_id, status: "PASS", fixture_inputs:
           {card_id, upgrade, fixture_seed, initial_state, player_inputs, choices},
           actual_events: [...], actual_state: {...}, evidence:
           {engine_history: relative_path, engine_state: relative_path,
            readonly_trace: relative_path}}]

Events/state are normalized EXACT projections specified by each fixture. Preserve
ordered event arrays and stable instance IDs; do not emit inferred observations or
copy expectations as actuals. Store raw engine evidence separately under the run's
artifact directory. Missing cases, repeated IDs, other runs, nonzero exit, timeout,
non-PASS status, wrong values/types/order, and absent evidence fail comparison.
Build identity is supplied by the invoking runner, not trusted from the report.
The comparator checks evidence files exist/nonempty, not their authenticity.

Static card fields are semantic contracts, NOT engine enum names. numeric_literals
are ordered numerals in rules_text_zh, NOT named DynamicVars. keywords are lexical
mentions, NOT a complete engine keyword registration contract. Gameplay fixtures
are hand-specified examples; they neither parse Chinese to execute effects nor
simulate engine damage. E cases require binding real enemy moves before execution.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests/fixtures/card_expectations.json"
REFERENCE = ROOT / "reference/bear-forge/docs/volibear"
CARD_IDS = set("""
B01 B02 B03 B04 C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 C13 C14
C15 C17 C18 C19 C20 C21 C22 C24 C25 C26 U02 U03 U04 U05 U06 U07 U08 U10
U11 U12 U13 U14 U15 U17 U19 U20 U21 U23 U24 U25 U26 U27 U28 U29 U31 U32
U34 U35 U36 U37 U38 U39 U40 U41 U42 U43 R01 R02 R05 R06 R07 R08 R09 R10
R12 R13 R14 R16 R17 R18 R21 R23 R24 R25 R27 R28 R29 R30 R31 T01 T02
""".split())
CASE_IDS = set("""E01 E02 E03 E04 D01 D02 D03 L02 L05
F01-B01-base F01-B01-upgraded F01-B02-base F01-B02-upgraded
F02-discount-retain C10-base C10-upgraded""".split())
TEXT_OVERRIDE_IDS = {"U41", "U42", "U43", "R27", "R29", "R30"}
BUILD_FIELDS = {"game_version", "game_commit", "framework_version", "package_version",
                "source_commit", "source_dirty"}
INPUT_FIELDS = ("card_id", "upgrade", "fixture_seed", "initial_state", "player_inputs", "choices")
CARD_FIELDS = {"card_id", "name_zh", "type", "rarity", "reward_pool", "play_target",
               "requirement_refs", "faces"}
FACE_FIELDS = {"face_id", "upgrade", "cost", "rules_text_zh", "display_text_zh",
               "numeric_literals", "self_exhaust", "keywords"}
CASE_FIELDS = {"case_id", "requirement_refs", "fixture_kind", "card_id", "upgrade",
               *INPUT_FIELDS, "expected_events", "expected_state",
               "expected_identity_relations", "comparison_mode", "timeout_seconds",
               "evidence_requirements", "execution_status"}


def load_fixture(path: Path = FIXTURE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def validate_fixture(data: dict) -> None:
    """Validate schema and frozen coverage; raises ValueError on invalid data."""
    _require(isinstance(data, dict), "fixture must be an object")
    _require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
             "unsupported schema_version")
    _require(set(data) == {"schema_version", "authority", "scope", "cards", "mechanism_cases"},
             "unexpected top-level fields")
    _require(isinstance(data["authority"], dict) and
             data["authority"].get("independent_of_runtime") is True, "independence declaration")
    _require(_strings(data["authority"].get("sources")), "authority sources")
    scope = data["scope"]
    _require(isinstance(scope, dict) and scope.get("card_count") == 89 and
             scope.get("face_count") == 178 and scope.get("reward_count") == 83 and
             scope.get("evidence_level") == "fixture_contract_only", "scope declaration")
    cards = data["cards"]
    _require(isinstance(cards, list) and len(cards) == 89, "89 card records required")
    seen = set()
    for card in cards:
        _require(isinstance(card, dict) and set(card) == CARD_FIELDS, "card schema")
        cid = card["card_id"]
        _require(isinstance(cid, str) and cid in CARD_IDS and cid not in seen, "card ID coverage/uniqueness")
        seen.add(cid)
        _require(isinstance(card["name_zh"], str) and bool(card["name_zh"]), cid + " name")
        _require(card["type"] in ("attack", "skill", "power"), cid + " type")
        _require(card["rarity"] == dict(B="basic", C="common", U="uncommon", R="rare", T="token")[cid[0]], cid + " rarity")
        _require(type(card["reward_pool"]) is bool and card["reward_pool"] == (cid[0] in "CUR"), cid + " reward pool")
        _require(card["play_target"] in ("single_enemy", "all_enemies", "random_enemy", "self"), cid + " target")
        _require(_strings(card["requirement_refs"]) and bool(card["requirement_refs"]), cid + " refs")
        _require(isinstance(card["faces"], list) and len(card["faces"]) == 2, cid + " two faces required")
        for index, face in enumerate(card["faces"]):
            _require(isinstance(face, dict) and set(face) == FACE_FIELDS, cid + " face schema")
            _require(type(face["upgrade"]) is bool and face["upgrade"] == bool(index), cid + " upgrade order")
            _require(face["face_id"] == cid + ("+" if index else ""), cid + " face ID")
            _require(face["cost"] == "X" or (type(face["cost"]) is int and 0 <= face["cost"] <= 3), cid + " cost")
            for key in ("rules_text_zh", "display_text_zh"):
                _require(isinstance(face[key], str) and bool(face[key]), cid + " " + key)
            _require(isinstance(face["numeric_literals"], list) and
                     all(type(n) is int for n in face["numeric_literals"]), cid + " numeric literals")
            _require(face["numeric_literals"] == [int(n) for n in re.findall(r"\d+", face["rules_text_zh"])], cid + " numeric literal order")
            _require(type(face["self_exhaust"]) is bool, cid + " exhaust bool")
            _require(_strings(face["keywords"]) and len(set(face["keywords"])) == len(face["keywords"]), cid + " keywords")
    _require(seen == CARD_IDS, "card coverage")
    cases = data["mechanism_cases"]
    _require(isinstance(cases, list) and len(cases) == len(CASE_IDS), "mechanism case count")
    seen = set()
    for case in cases:
        _require(isinstance(case, dict) and set(case) == CASE_FIELDS, "case schema")
        cid = case["case_id"]
        _require(isinstance(cid, str) and cid in CASE_IDS and cid not in seen, "case coverage/uniqueness")
        seen.add(cid)
        _require(case["card_id"] is None or case["card_id"] in CARD_IDS, cid + " card ID")
        _require(case["upgrade"] is None if case["card_id"] is None else type(case["upgrade"]) is bool, cid + " upgrade")
        _require(_strings(case["requirement_refs"]) and bool(case["requirement_refs"]), cid + " refs")
        _require(type(case["fixture_seed"]) is int, cid + " seed")
        _require(case["fixture_kind"] == "mechanism_contract" and case["execution_status"] == "NOT_RUN", cid + " not gameplay evidence")
        for key in ("initial_state", "expected_state"):
            _require(isinstance(case[key], dict) and bool(case[key]), cid + " " + key)
        for key in ("player_inputs", "expected_events"):
            _require(isinstance(case[key], list) and bool(case[key]) and all(isinstance(x, dict) for x in case[key]), cid + " " + key)
        _require(all(isinstance(x.get("action"), str) and x["action"] for x in case["player_inputs"]), cid + " actions")
        _require(all(isinstance(x.get("event"), str) and x["event"] for x in case["expected_events"]), cid + " events")
        _require(isinstance(case["choices"], list), cid + " choices")
        _require(case["comparison_mode"] == "exact_projection", cid + " comparison mode")
        _require(type(case["timeout_seconds"]) is int and 0 < case["timeout_seconds"] <= 300, cid + " timeout")
        _require(case["evidence_requirements"] == ["engine_history", "engine_state", "readonly_trace"], cid + " evidence requirements")
        _require(isinstance(case["expected_identity_relations"], list), cid + " identities")
        for relation in case["expected_identity_relations"]:
            _require(isinstance(relation, dict) and set(relation) == {"left", "relation", "right"}, cid + " identity schema")
            _require(relation["relation"] == "equal" and isinstance(relation["left"], str) and isinstance(relation["right"], str), cid + " identity relation")
            _resolve({"initial_state": case["initial_state"], "actual_state": case["expected_state"]}, relation["left"])
            _resolve({"initial_state": case["initial_state"], "actual_state": case["expected_state"]}, relation["right"])
    _require(seen == CASE_IDS, "mechanism coverage")


def _resolve(data: dict, dotted: str):
    for part in dotted.split("."):
        if not isinstance(data, dict) or part not in data:
            raise ValueError("missing identity path: " + dotted)
        data = data[part]
    return data


def _equal(a, b) -> bool:
    """JSON equality without Python's True == 1 loophole."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def compare_actual_results(fixture: dict, report: dict, *, expected_run_id: str,
                           expected_build: dict, evidence_root: Path) -> list[str]:
    """Compare supplied engine projections; never run/simulate gameplay here."""
    validate_fixture(fixture)
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    if not isinstance(report, dict):
        return ["report must be an object"]
    check(type(report.get("schema_version")) is int and report["schema_version"] == 1, "report schema_version")
    check(bool(expected_run_id) and report.get("run_id") == expected_run_id, "run_id mismatch")
    check(report.get("execution_kind") == "real_engine", "not real_engine observations")
    check(isinstance(expected_build, dict) and set(expected_build) == BUILD_FIELDS, "expected build identity schema")
    check(_equal(report.get("build"), expected_build), "build identity mismatch")
    if isinstance(expected_build, dict):
        check(expected_build.get("game_version") == "0.107.1" and expected_build.get("game_commit") == "59260271", "unsupported game version")
        check(type(expected_build.get("source_dirty")) is bool and all(isinstance(expected_build.get(k), str) and expected_build[k] for k in BUILD_FIELDS - {"source_dirty"}), "build identity values")
    check(_strings(report.get("command")) and bool(report.get("command")), "missing command")
    check(type(report.get("exit_code")) is int and report["exit_code"] == 0, "exit_code")
    check(report.get("timed_out") is False, "timeout or missing timeout status")
    actual_cases = report.get("cases")
    if not isinstance(actual_cases, list):
        return errors + ["missing cases"]
    by_id = {}
    for actual in actual_cases:
        if not isinstance(actual, dict) or not isinstance(actual.get("case_id"), str):
            errors.append("invalid case record")
            continue
        cid = actual["case_id"]
        check(cid not in by_id, cid + ": duplicate case")
        by_id[cid] = actual
    check(set(by_id) == CASE_IDS, "required case set mismatch")
    root = Path(evidence_root).resolve()
    for case in fixture["mechanism_cases"]:
        cid = case["case_id"]
        actual = by_id.get(cid)
        if actual is None:
            continue
        check(actual.get("run_id") == expected_run_id, cid + ": cross-run observation")
        check(actual.get("status") == "PASS", cid + ": not PASS")
        check(_equal(actual.get("fixture_inputs"), {k: case[k] for k in INPUT_FIELDS}), cid + ": fixture input mismatch")
        check(_equal(actual.get("actual_events"), case["expected_events"]), cid + ": event order/value mismatch")
        check(_equal(actual.get("actual_state"), case["expected_state"]), cid + ": state mismatch")
        for relation in case["expected_identity_relations"]:
            try:
                context = {"initial_state": case["initial_state"], "actual_state": actual.get("actual_state")}
                check(_equal(_resolve(context, relation["left"]), _resolve(context, relation["right"])), cid + ": identity mismatch")
            except ValueError as error:
                errors.append(cid + ": " + str(error))
        evidence = actual.get("evidence", {})
        for key in case["evidence_requirements"]:
            value = evidence.get(key) if isinstance(evidence, dict) else None
            if not isinstance(value, str) or not value:
                errors.append(cid + ": missing " + key)
                continue
            try:
                relative = Path(value)
                path = (root / relative).resolve()
                check(not relative.is_absolute() and path.is_relative_to(root) and
                      path.is_file() and path.stat().st_size > 0, cid + ": invalid evidence " + key)
            except (OSError, ValueError):
                errors.append(cid + ": unreadable evidence " + key)
    return errors


class CardFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()
        cls.cards = {c["card_id"]: c for c in cls.fixture["cards"]}
        cls.cases = {c["case_id"]: c for c in cls.fixture["mechanism_cases"]}

    def test_schema_and_exact_coverage(self):
        validate_fixture(self.fixture)
        self.assertEqual(sum(c["reward_pool"] for c in self.cards.values()), 83)
        self.assertEqual({r: sum(c["rarity"] == r for c in self.cards.values()) for r in ("basic", "common", "uncommon", "rare", "token")},
                         dict(basic=4, common=24, uncommon=36, rare=23, token=2))
        self.assertEqual(sum(len(c["faces"]) for c in self.cards.values()), 178)

    def test_frozen_faces_match_both_independent_reference_documents(self):
        reference = load_fixture(REFERENCE / "cards_s2.json")
        markdown = (REFERENCE / "CARDS.md").read_text(encoding="utf-8")
        rows = {}
        for line in markdown.splitlines():
            cells = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(cells) == 6 and cells[0] in CARD_IDS:
                self.assertNotIn(cells[0], rows)
                rows[cells[0]] = cells
        self.assertEqual(set(rows), CARD_IDS)
        self.assertEqual({c["code"] for c in reference["cards"]}, CARD_IDS)
        for source in reference["cards"]:
            cid = source["code"]
            card = self.cards[cid]
            row = rows[cid]
            with self.subTest(card=cid):
                self.assertEqual(card["name_zh"], source["name"])
                self.assertEqual(row[1:3], [source["name"], source["type"]])
                self.assertEqual(card["type"], {"攻击": "attack", "技能": "skill", "能力": "power"}[source["type"]])
                self.assertEqual(row[3], "／".join("X" if x == -1 else str(x) for x in source["cost"]))
                for index, key in enumerate(("base", "upgraded")):
                    face = card["faces"][index]
                    self.assertEqual(face["rules_text_zh"], source[key])
                    self.assertEqual(face["rules_text_zh"], row[index + 4])
                    self.assertEqual(face["cost"], "X" if source["cost"][index] == -1 else source["cost"][index])

    def test_chinese_cost_zero_override_is_scoped_and_timed(self):
        changed = set()
        for cid, card in self.cards.items():
            for face in card["faces"]:
                raw, display = face["rules_text_zh"], face["display_text_zh"]
                if cid in TEXT_OVERRIDE_IDS:
                    changed.add(cid)
                    self.assertRegex(display, r"本回合[^。；]*下次打出时为0费")
                    self.assertNotIn("减费1", display)
                    # Approved display grammar changes, independent rule remains.
                    self.assertIn("减费1", raw)
                    if cid == "R27":
                        self.assertIn("爪形本回合下次打出时为0费；每张躯形使你获得4格挡", display)
                    if cid == "R30":
                        self.assertIn("每回合首次打出爪形时", display)
                        self.assertIn("每次打出躯形时，获得1能量", display)
                else:
                    self.assertNotIn("下次打出时为0费", display)
        self.assertEqual(changed, TEXT_OVERRIDE_IDS)
        for cid in ("C15", "R10", "U25", "U32"):
            self.assertIn("减费", self.cards[cid]["faces"][0]["display_text_zh"])
        for cid in ("T01", "T02"):
            self.assertEqual([f["cost"] for f in self.cards[cid]["faces"]], [1, 1])

    def test_self_exhaust_not_confused_with_consuming_material(self):
        for cid in ("C13", "U15"):
            self.assertEqual([f["self_exhaust"] for f in self.cards[cid]["faces"]], [False, False])
        for cid in ("C14", "U14"):
            self.assertEqual([f["self_exhaust"] for f in self.cards[cid]["faces"]], [True, False])
        for cid in ("T01", "T02", "R17", "U43"):
            self.assertTrue(all(f["self_exhaust"] for f in self.cards[cid]["faces"]))

    def test_engage_examples_are_explicit_not_a_block_difference_simulator(self):
        for cid, hp, block, absorbed, segments in [
            ("E01", 77, 0, 5, [5]), ("E02", 80, 12, 8, [8]),
            ("E03", 72, 0, 10, [6, 4, 0]), ("E04", 74, 5, 10, [5, 5])]:
            case = self.cases[cid]
            self.assertEqual(case["expected_state"], dict(player_hp=hp, player_block=block,
                             absorbed=absorbed, enemy_moves_executed=1, engage_completions=1))
            self.assertEqual([e["absorbed"] for e in case["expected_events"] if e["event"] == "enemy_attack_resolved"], segments)
            self.assertEqual([e["event"] for e in case["expected_events"]][-2:], ["enemy_move_finished", "engage_completed"])
        self.assertEqual(self.cases["C10-base"]["expected_state"]["enemy_hp"], 86)
        self.assertEqual(self.cases["C10-upgraded"]["expected_state"]["enemy_hp"], 83)

    def test_domain_batch_and_replay_examples(self):
        for cid, batches, hp in [("D01", 2, 76), ("D02", 1, 86), ("D03", 1, 76)]:
            self.assertEqual(self.cases[cid]["expected_state"]["lightning_count"], batches)
            self.assertEqual(self.cases[cid]["expected_state"]["enemy_hp"], hp)
        self.assertEqual(self.cases["D03"]["expected_state"]["payments"], 1)
        self.assertEqual(self.cases["D03"]["expected_state"]["actual_plays"], 1)
        self.assertEqual(self.cases["L02"]["expected_state"], dict(enemy_hp=[30, 30, 30], enemy_block=[7, 7, 7], lightning_count=1, player_block=6))
        self.assertEqual(self.cases["L05"]["expected_state"], dict(enemy_hp=85, thunder=2, lightning_count=1))

    def test_beast_form_numbers_identity_and_upgrade_are_explicit(self):
        for cid, segments, block, lightning in [("B01-base", [7, 7], 0, 0), ("B01-upgraded", [11, 11], 0, 0), ("B02-base", [], 9, 2), ("B02-upgraded", [], 12, 3)]:
            state = self.cases["F01-" + cid]["expected_state"]
            self.assertEqual((state["ordinary_damage_segments"], state["block"], state["lightning_base_damage"]), (segments, block, lightning))
            self.assertEqual(state["base_cost"], 1)
            self.assertTrue(state["self_exhaust"])
            self.assertEqual(state["upgrade"], cid.endswith("upgraded"))
        state = self.cases["F02-discount-retain"]["expected_state"]
        self.assertEqual(state["preview_cost"], 0)
        self.assertTrue(state["retain"])
        self.assertEqual(state["master_card_id"], "C02")

    def test_schema_rejects_missing_duplicate_and_bad_types(self):
        mutations = [
            lambda f: f["cards"].pop(),
            lambda f: f["cards"].__setitem__(1, copy.deepcopy(f["cards"][0])),
            lambda f: f["cards"][0]["faces"].pop(),
            lambda f: f["cards"][0]["faces"][0].__setitem__("cost", True),
            lambda f: f["cards"][0]["faces"][0].__setitem__("numeric_literals", [9]),
            lambda f: f["mechanism_cases"].pop(),
            lambda f: f["mechanism_cases"][0].__setitem__("expected_events", []),
            lambda f: f["mechanism_cases"][0].__setitem__("execution_status", "PASS"),
            lambda f: f["mechanism_cases"][0].__setitem__("timeout_seconds", True),
        ]
        for mutate in mutations:
            fixture = copy.deepcopy(self.fixture)
            mutate(fixture)
            with self.assertRaises(ValueError):
                validate_fixture(fixture)


class ObservationComparatorSelfTests(unittest.TestCase):
    """All reports here are SYNTHETIC test doubles, never gameplay evidence."""
    def setUp(self):
        self.fixture = load_fixture()
        self.temp = tempfile.TemporaryDirectory(prefix="volibear-contract-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "synthetic.txt").write_text(
            "Comparator unit-test double; NOT real engine evidence.", encoding="utf-8")
        self.build = dict(game_version="0.107.1", game_commit="59260271", framework_version="synthetic",
                          package_version="synthetic", source_commit="synthetic", source_dirty=True)
        self.report = dict(schema_version=1, run_id="synthetic-run", execution_kind="real_engine", build=self.build,
                           command=["synthetic-comparator-test"], exit_code=0, timed_out=False, cases=[])
        for case in self.fixture["mechanism_cases"]:
            self.report["cases"].append(dict(case_id=case["case_id"], run_id="synthetic-run", status="PASS",
                fixture_inputs={k: copy.deepcopy(case[k]) for k in INPUT_FIELDS},
                actual_events=copy.deepcopy(case["expected_events"]), actual_state=copy.deepcopy(case["expected_state"]),
                evidence={k: "synthetic.txt" for k in case["evidence_requirements"]}))

    def compare(self):
        return compare_actual_results(self.fixture, self.report, expected_run_id="synthetic-run",
                                      expected_build=self.build, evidence_root=self.root)

    def test_matching_synthetic_projection_checks_comparator_only(self):
        self.assertEqual(self.compare(), [])

    def test_passed_flag_cannot_replace_observations(self):
        self.report["cases"][0] = dict(case_id="E01", run_id="synthetic-run", status="PASS", passed=True)
        self.assertTrue(self.compare())

    def test_required_case_omission_duplicate_and_cross_run_rejected(self):
        original = copy.deepcopy(self.report)
        for mutate in [lambda r: r["cases"].pop(), lambda r: r["cases"].append(copy.deepcopy(r["cases"][0])),
                       lambda r: r["cases"][0].__setitem__("run_id", "another-run")]:
            self.report = copy.deepcopy(original)
            mutate(self.report)
            self.assertTrue(self.compare())

    def test_semantic_mutations_are_detected_by_actual_value_comparison(self):
        # Mirrors selected TEST_SPEC mutations; does not inject into production.
        mutations = [("E01", "absorbed", 3), ("E02", "absorbed", 0), ("E04", "absorbed", 0),
                     ("D01", "lightning_count", 1), ("D02", "lightning_count", 2),
                     ("D03", "payments", 2), ("L02", "lightning_count", 3),
                     ("L02", "lightning_count", 0), ("L05", "thunder", 0),
                     ("F01-B01-upgraded", "upgrade", False),
                     ("F02-discount-retain", "instance_id", "clone"),
                     ("F02-discount-retain", "temporary_discount", 0)]
        for cid, key, value in mutations:
            record = next(c for c in self.report["cases"] if c["case_id"] == cid)
            before = record["actual_state"][key]
            record["actual_state"][key] = value
            self.assertTrue(self.compare(), (cid, key))
            record["actual_state"][key] = before

    def test_events_are_ordered_and_boolean_is_not_integer(self):
        events = self.report["cases"][0]["actual_events"]
        events[-2], events[-1] = events[-1], events[-2]
        self.assertTrue(self.compare())
        events[-2], events[-1] = events[-1], events[-2]
        self.report["cases"][0]["actual_state"]["engage_completions"] = True
        self.assertTrue(self.compare())

    def test_timeout_failure_missing_evidence_and_changed_input_rejected(self):
        original = copy.deepcopy(self.report)
        mutations = [lambda r: r.__setitem__("timed_out", True), lambda r: r.__setitem__("exit_code", 1),
                     lambda r: r.__setitem__("build", {**self.build, "package_version": "old"}),
                     lambda r: r["cases"][0].__setitem__("status", "NOT_RUN"),
                     lambda r: r["cases"][0]["evidence"].__setitem__("engine_history", "missing.txt"),
                     lambda r: r["cases"][0]["evidence"].__setitem__("engine_history", "../outside.txt"),
                     lambda r: r["cases"][0]["fixture_inputs"].__setitem__("fixture_seed", 99)]
        for mutate in mutations:
            self.report = copy.deepcopy(original)
            mutate(self.report)
            self.assertTrue(self.compare())


if __name__ == "__main__":
    unittest.main()
