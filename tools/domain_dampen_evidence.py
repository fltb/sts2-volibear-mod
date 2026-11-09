"""Strict native Dampen pair evidence; synthetic fixtures validate this gate, not gameplay."""
from __future__ import annotations
import json
import math
import re
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = "[Volibear] DOMAIN_DAMPEN_TRANSACTIONS_RESULT "
LEVELS = {"off": [0, 0], "on": [1, 1], "enter-await": [1, 1], "exit-await": [0, 0],
          "enter-pair": [1, 1], "exit-pair": [0, 0], "departure": [1, 1]}
ADMISSIONS = {"off": [False, False], "on": [True, True], "enter-await": [True, True],
              "exit-await": [False, False], "enter-pair": [False, True], "exit-pair": [True, False], "departure": [True, True]}
NUMERIC = {"schema", "sourceId", "ownerId", "id", "oldLevel", "level", "value", "cost", "amount",
           "nativeMoveCalls", "directPowerCallbackCalls", "invocationNonce", "applyNonce", "moveNonce", "outerNonce",
           "ledgerBefore", "ledgerAfter", "SourceCalls", "SuccessCloses", "FailureCloses", "EntryBindings", "ReturnBindings", "AwaitRegistrations", "epoch", "outer", "applies", "powerSlots"}


def validate(payload, token: str, variant: str) -> list[str]:
    errors = []
    def need(ok, label):
        if not ok:
            errors.append(label)
    def number(value):
        return type(value) is int or (type(value) is float and math.isfinite(value))
    def integer(value):
        return type(value) is int
    def numeric_tree(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in NUMERIC and item is not None:
                    need(number(item) if key in {"value", "amount"} else integer(item), "numeric type: " + key)
                numeric_tree(item)
        elif isinstance(value, list):
            for item in value:
                numeric_tree(item)
    try:
        p = payload
        need(type(p) is dict and variant in LEVELS, "payload/variant")
        if type(p) is not dict or variant not in LEVELS:
            return errors
        numeric_tree(p)
        need(type(token) is str and bool(token.strip()), "nonempty isolation token")
        for key, expected in {"schema": 2, "token": token, "scenario": "domain-dampen-transactions", "variant": variant,
            "suppressionPolicy": "native-debt-temporary-upgrade-loan",
            "version": EXPECTED_GAME_VERSION, "commit": EXPECTED_GAME_COMMIT, "encounter": "KnightsElite",
            "acceptance": "native-source-ledger-card-pairs-not-power-admission-or-ordinary-input", "directPowerCallbackCalls": 0}.items():
            need(p.get(key) == expected, "root " + key)
        for key in ("testMode", "admissionSuppression", "artifactSuppression", "endingRepair", "exceptionRollback", "escapeRestitutionRepair"):
            need(p.get(key) is False, "scope " + key)
        need(integer(p["sourceId"]) and integer(p["ownerId"]) and p["sourceId"] != p["ownerId"], "native source/owner IDs")
        source, owner, combat = p["sourceRef"], p["ownerRef"], p["combatRef"]
        need(all(type(x) is str and x for x in (source, owner, combat)) and len({source, owner, combat}) == 3, "identity roots")
        initial = p["initialCards"]
        need(len(initial) == 2 and [c["type"] for c in initial] == ["StrikeIronclad", "DefendIronclad"], "two native subjects")
        ids, refs = [c["id"] for c in initial], [c["reference"] for c in initial]
        need(all(integer(x) and 0 <= x <= 4294967295 for x in ids) and len(set(ids)) == 2 and len(set(refs)) == 2, "unique card identities")
        roster = p["initialRoster"]
        need(len(roster) == 3 and [r["type"] for r in roster] == ["FlailKnight", "SpectralKnight", "MagiKnight"], "formal initial roster")
        need(any(r == {"id": p["sourceId"], "reference": source, "type": "MagiKnight"} for r in roster), "formal source identity")
        count = 1 if variant == "departure" else 2
        need(p["nativeMoveCalls"] == count and len(p["moves"]) == count and len(p["rawSources"]) == count, "native move count")
        for move, raw in zip(p["moves"], p["rawSources"]):
            need(move["type"] == raw["type"] == "MagiKnight" and move["move"] == "DAMPEN_MOVE" and
                 move["source"] == raw["reference"] and move["id"] == raw["id"], "actual move/source continuity")
        need(p["moves"][0]["source"] == source and p["moves"][0]["id"] == p["sourceId"], "first actual move source")
        second = None if count == 1 else p["moves"][1]["source"]
        if second is not None:
            need(second != source and p["moves"][1]["id"] != p["sourceId"], "second real caster")
        sites = {row["Kind"]: row for row in p["ilSites"]}
        need(len(p["ilSites"]) == 5 and set(sites) == {"Outer", "Move", "Apply", "Pair", "Reset"}, "exact five native method inventory including Reset")
        def normalize(name):
            return re.sub(r'd__\d+', 'd__#', name)
        names = {"Outer": "MegaCrit.Sts2.Core.Models.MonsterModel+<PerformMove>d__103.MoveNext",
                 "Move": "MegaCrit.Sts2.Core.Models.Monsters.MagiKnight+<DampenMove>d__25.MoveNext",
                 "Apply": "MegaCrit.Sts2.Core.Commands.PowerCmd+<Apply>d__2.MoveNext",
                 "Pair": "MegaCrit.Sts2.Core.Models.Powers.DampenPower.AfterApplied",
                 "Reset": "MegaCrit.Sts2.Core.Combat.CombatManager.Reset(System.Boolean)"}
        for kind, name in names.items():
            row = sites[kind]
            need(normalize(row["Method"]) == normalize(name) and row["SourceCalls"] == (0 if kind == "Reset" else 1) and
                 row["SuccessCloses"] == row["FailureCloses"] == (0 if kind in ("Pair", "Reset") else 1) and
                 row["EntryBindings"] == (0 if kind == "Reset" else 1) and row["ReturnBindings"] == (0 if kind in ("Pair", "Reset") else 1) and
                 row["AwaitRegistrations"] == {"Outer": 3, "Move": 2, "Apply": 8, "Pair": 0, "Reset": 0}[kind] and
                 row["PatchType"] == ("Prefix" if kind == "Reset" else "Transpiler"), "IL anchors " + kind)
        patches = p["patchTargets"]
        need(len(patches) == 5 and {normalize(row["Method"]) for row in patches} == {normalize(name) for name in names.values()}, "actual five patched native methods")
        module = "Volibear.DomainDampenTransactions"
        for row in patches:
            is_reset = normalize(row["Method"]) == normalize(names["Reset"])
            need(all(type(row[key]) is list and all(type(owner_id) is str for owner_id in row[key]) for key in ("PrefixOwners", "TranspilerOwners")), "actual patch owner array types")
            need(row["PatchType"] == ("Prefix" if is_reset else "Transpiler") and
                 row["PrefixOwners"].count(module) == (1 if is_reset else 0) and row["TranspilerOwners"].count(module) == (0 if is_reset else 1), "actual own patch kind/owner")
        names = ["baseline", "source", "off-no-replay"] + ([] if count == 1 else ["joined"]) + ["independent"] + ([] if count == 1 else ["first-death"]) + ["restored", "player-control", "player-restored"]
        need([s["name"] for s in p["steps"]] == names, "exact ordered snapshots")
        steps = {s["name"]: s for s in p["steps"]}
        # Build a typed identity domain independently of producer 'same...' receipts.
        identities, creature_ids = {}, {}
        def identity(ref, kind, model, native_id=None):
            need(type(ref) is str and bool(ref), "nonempty typed reference")
            signature = (kind, model, native_id)
            need(ref not in identities or identities[ref] == signature, "reference crosses type/identity domain")
            identities[ref] = signature
            if kind == "Creature":
                need(integer(native_id) and 0 <= native_id <= 4294967295, "creature ID type")
                need(native_id not in creature_ids or creature_ids[native_id] == ref, "creature ID aliases another object")
                creature_ids[native_id] = ref
        identity(combat, "Combat", "CombatState")
        identity(owner, "Creature", "Player", p["ownerId"])
        for actor in roster + p["rawSources"]:
            identity(actor["reference"], "Creature", actor["type"], actor["id"])
        for card in initial:
            identity(card["reference"], "Card", card["type"], card["id"])
        identity(steps["source"]["power"], "Power", "DampenPower")
        identity(steps["player-control"]["power"], "Power", "DampenPower")
        need(len(identities) == 9 + (0 if count == 1 else 1), "distinct combat/owner/enemies/cards/two powers")
        phase_by_name = {"baseline": "setup", "source": "source", "off-no-replay": "no-replay", "joined": "no-replay",
                         "independent": "independent", "first-death": "restoration", "restored": "restoration",
                         "player-control": "player", "player-restored": "player"}
        def levels(step):
            return [c["level"] for c in step["cards"]]
        def ledger(step):
            entries = step["ledger"]
            need(len({e["card"] for e in entries}) == len(entries), "duplicate native ledger card")
            for e in entries:
                need(e["card"] in refs and e["id"] == ids[refs.index(e["card"])] and integer(e["oldLevel"]) and e["oldLevel"] == 1, "native old-level ledger identity")
            return {e["card"]: e["oldLevel"] for e in entries}
        for step in p["steps"]:
            need(step["phase"] == phase_by_name[step["name"]], "snapshot exact lifecycle phase")
            need(step["ending"] is False and step["combat"] == combat and type(step["domain"]) is bool, "live combat snapshot")
            need(len(step["cards"]) == 2, "snapshot subject count")
            for i, card in enumerate(step["cards"]):
                need(card["id"] == ids[i] and card["reference"] == refs[i] and card["type"] == initial[i]["type"] and card["owner"] == owner, "card reference continuity")
                need(integer(card["level"]) and card["level"] in (0, 1) and card["cost"] == 1 and card["pile"] == ("Hand" if i == 0 else "Draw"), "card level/cost/pile")
                need(number(card["value"]) and card["value"] == ([6, 5][i] + 3 * card["level"]), "real native dynamic var reset/restoration")
            ledger(step)
            attached = step["name"] == "baseline" or (variant != "departure" and step["name"] in ("source", "off-no-replay", "joined", "independent"))
            need(step["sourceAttached"] is attached and step["sourceCombat"] == (combat if attached else None), "native source departure continuity")
        after = LEVELS[variant]
        debt = {ref: 1 for ref in refs}
        independent = 0
        need(p["independentCard"] == refs[0], "independent downgrade chooses temporarily restored first card")
        modified = [0, 1]
        restored = [1, 1]
        need(levels(steps["baseline"]) == [1, 1] and not steps["baseline"]["present"] and steps["baseline"]["power"] is None and not ledger(steps["baseline"]) and steps["baseline"]["domain"] is False, "upgraded native baseline")
        need(steps["baseline"]["casters"] == [] and steps["baseline"]["applier"] is None and steps["baseline"]["amount"] is None and steps["baseline"]["present"] is False, "baseline has no power data")
        source_power = steps["source"]["power"]
        need(type(source_power) is str and source_power not in refs + [source, owner], "actual native power identity")
        for name in names[1:names.index("player-control")]:
            step = steps[name]
            need(step["power"] == source_power and step["amount"] == 1 and step["applier"] == source, "source power continuity " + name)
            need(ledger(step) == debt, "only genuinely admitted card debt " + name)
            need(step["present"] is (name != "restored"), "native power lifetime " + name)
            expected = restored if name == "restored" else modified if name in ("independent", "first-death") else after if name == "source" else [0, 0]
            need(levels(step) == expected, "card result " + name)
            expected_casters = ([source] if count == 1 else [] if name == "restored" else [second] if name == "first-death" else [source, second] if name in ("joined", "independent") else [source])
            need(sorted(step["casters"]) == sorted(expected_casters), "native caster lifetime " + name)
            expected_domain = variant in ("on", "enter-await", "enter-pair", "departure") if name == "source" else name in ("independent", "first-death", "restored")
            need(step["domain"] is expected_domain, "live domain " + name)
        need(p["cleanupKind"] == ("native-remove-after-escape" if count == 1 else "native-last-caster-death"), "honest cleanup kind")
        control = steps["player-control"]
        control_power = control["power"]
        control_debt = {refs[i]: 1 for i, level in enumerate(restored) if level == 1}
        for name in ("player-control", "player-restored"):
            row = steps[name]
            need(row["power"] == control_power and control_power != source_power and row["applier"] == owner and row["amount"] == 1 and row["domain"] is True and row["casters"] == [], "untracked player control identity")
            need(row["present"] is (name == "player-control") and ledger(row) == control_debt and levels(row) == restored, "player-source temporary restoration and native restitution")
        need(len(p["received"]) == len(p["nativeReceived"]) == 2, "native admission and application history preserved")
        for i, (power, applier) in enumerate(((source_power, source), (control_power, owner))):
            event, history = p["received"][i], p["nativeReceived"][i]
            need(event["phase"] == ("source" if i == 0 else "player") and event["domain"] is (variant in ("on", "exit-await", "exit-pair", "departure") if i == 0 else True), "PowerApplied actual pre-wait phase/domain")
            need(event["power"] == history["power"] == power and event["applier"] == history["applier"] == applier and
                 event["target"] == history["target"] == owner and event["amount"] == history["amount"] == 1 and history["type"] == "DampenPower", "real PowerApplied/history continuity")
        rows = p["pairs"]
        source_pairs = [r for r in rows if r["phase"] == "source"]
        player_pairs = [r for r in rows if r["phase"] == "player"]
        need(len(rows) == 2 + len(control_debt) and len(source_pairs) == 2 and len(player_pairs) == len(control_debt), "no replay/foreign pair injection")
        for key in ("invocationNonce", "applyNonce", "moveNonce", "outerNonce"):
            need(all(integer(r[key]) and r[key] > 0 for r in source_pairs) and len({r[key] for r in source_pairs}) == 1, "single exact source task/invocation " + key)
        need([r["phase"] for r in rows] == ["source", "source"] + ["player"] * len(control_debt), "total pair chronology source before player")
        first_source = source_pairs[0]
        need(0 < first_source["outerNonce"] < first_source["moveNonce"] < first_source["applyNonce"] < first_source["invocationNonce"], "ordered distinct source scope nonces")
        running = {}
        for i, row in enumerate(source_pairs):
            need(row["power"] == source_power and row["source"] == source and row["combat"] == combat and row["card"] == refs[i] and row["id"] == ids[i] and row["provenance"] == "native-magi", "exact source pair identity")
            admitted = ADMISSIONS[variant][i]
            pair_level = 1 if variant == "enter-pair" else int(admitted)
            need(integer(row["before"]) and integer(row["after"]) and row["before"] == 1 and row["after"] == pair_level, "actual per-card result after loan")
            need(row["suppressed"] is admitted and row["sourceDomainAtAdmission"] is admitted, "source admission receipt remains separate from loan result")
            need(row["ledgerBefore"] == len(running), "ledger before pair")
            running[refs[i]] = 1
            need(row["ledgerAfter"] == len(running) and row["sameNativeLedger"] is True and ledger({"ledger": row["nativeLedger"]}) == running, "atomic native ledger pair")
            need(row["sourceAttached"] is (variant != "departure"), "captured departed source remains proven")
            need(row["domainAfter"] is (True if variant == "enter-pair" else admitted), "actual domain after native card callback")
        need([r["card"] for r in player_pairs] == [ref for ref in refs if ref in control_debt], "ordered player native pairs")
        need(all(integer(r["invocationNonce"]) and r["invocationNonce"] > first_source["invocationNonce"] for r in player_pairs) and len({r["invocationNonce"] for r in player_pairs}) == 1, "separate player callback invocation")
        running = {}
        for row in player_pairs:
            need(integer(row["before"]) and integer(row["after"]), "player levels are integers")
            need(row["id"] == ids[refs.index(row["card"])] and row["sourceDomainAtAdmission"] is False and row["sourceAttached"] is False, "player pair typed card identity and no source eligibility")
            need(row["card"] in control_debt and row["power"] == control_power and row["provenance"] == "player" and row["suppressed"] is False and row["domainAfter"] is True and row["before"] == 1 and row["after"] == 1, "player debit temporarily restored without borrowing enemy provenance")
            need(row["applyNonce"] == row["moveNonce"] == row["outerNonce"] == 0 and row["source"] is None and row["combat"] is None, "player cannot inherit source capability")
            need(row["ledgerBefore"] == len(running), "player ledger before")
            running[row["card"]] = 1
            need(row["ledgerAfter"] == len(running) and row["sameNativeLedger"] is True and ledger({"ledger": row["nativeLedger"]}) == running, "native player ledger")
        expected_events = []
        for i, ref in enumerate(refs):
            live = ADMISSIONS[variant][i]
            expected_events.append(("source", ref, 1, 0, live))
            if live or variant == "enter-pair":
                expected_events.append(("source", ref, 0, 1, True))
            if variant == "exit-pair" and i == 0:
                expected_events.append(("source", ref, 1, 0, False))
        if after == [1, 1]:
            expected_events += [("no-replay", ref, 1, 0, False) for ref in refs]
        expected_events += [("no-replay", ref, 0, 1, True) for ref in refs]
        expected_events.append(("independent", refs[0], 1, 0, True))
        expected_events += [("restoration", refs[0], 0, 0, True), ("restoration", refs[1], 1, 0, True)]
        expected_events += [("restoration", ref, 0, 1, True) for ref in refs]
        for ref in refs:
            expected_events += [("player", ref, 1, 0, True), ("player", ref, 0, 1, True)]
        expected_events += [("player", ref, 1, 0, True) for ref in refs]
        expected_events += [("player", ref, 0, 1, True) for ref in refs]
        need([(e["phase"], e["card"], e["before"], e["after"], e["domain"]) for e in p["cardEvents"]] == expected_events,
             "exact native downgrade/loan/exit/independent/restitution event sequence")
        for event in p["cardEvents"]:
            need(integer(event["before"]) and integer(event["after"]) and type(event["domain"]) is bool and event["id"] == ids[refs.index(event["card"])], "raw card event numeric identity")
        boundaries = p["boundaries"]
        need(len(boundaries) == (0 if variant in ("off", "on") else 1), "explicit instrumentation boundaries")
        if boundaries:
            b = boundaries[0]
            kind = "instrumented-native-power-wait-continuation" if variant in ("enter-await", "exit-await") else "native-card-Upgraded-event" if variant == "enter-pair" else "instrumented-post-pair" if variant == "exit-pair" else "instrumented-native-outer-wait-departure"
            need(b["kind"] == kind, "truthful boundary kind")
            if variant == "departure":
                need(b["attachedBefore"] is True and b["attachedAfter"] is False and b["sourceCombatNull"] is True and b["after"] is True and b["originalWaitCompleted"] is True, "actual departure before source callback")
            else:
                entering = variant.startswith("enter-")
                need(b["before"] is (not entering) and b["after"] is entering, "actual live Domain switch")
                if variant.endswith("await"):
                    need(b["originalWaitCompleted"] is True, "preserved actual native wait")
                else:
                    need(b["card"] == refs[0], "between-card switch after first pair")
        life = p["lifetimeAfter"]
        need(integer(life["epoch"]) and life["epoch"] >= 0 and all(integer(life[key]) and life[key] == 0 for key in ("outer", "moves", "applies", "powerSlots")), "no source receipts survive original tasks")
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration) as exc:
        errors.append("malformed raw evidence: " + str(exc))
    return errors


def check_log(text: str, token: str, variant: str) -> list[str]:
    # Only the engine's shutdown task-id race is waived; every other pre/post-shutdown error stays strict.
    # Only the engine's shutdown task-id race and the Windows engine root-store condition are
    # waived here; teardown noise stays gated by the runner's matched stock control.
    cleaned = '\n'.join(line for line in text.splitlines() if line.strip() != 'ERROR: Invalid Task ID'
                        and 'Failed to read the root certificate store' not in line
                        and 'get_system_ca_certificates (platform/windows/os_windows.cpp' not in line)
    if re.search(r"DOMAIN_DAMPEN_TRANSACTIONS_ERROR|DOMAIN_DAMPEN_SOURCE_UNSUPPORTED|Unhandled\s+exception|unhandled\s+error|FATAL|SCRIPT ERROR|\bERROR\s*:", cleaned, re.IGNORECASE):
        return ["native Dampen error/unsupported provenance"]
    lines = [line.split(MARKER, 1)[1] for line in text.splitlines() if MARKER in line]
    if len(lines) != 1:
        return ["expected exactly one Dampen result"]
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result
        return validate(json.loads(lines[0], object_pairs_hook=unique), token, variant)
    except (ValueError, TypeError) as exc:
        return ["invalid Dampen JSON: " + str(exc)]
