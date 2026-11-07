"""Independent pinned-version Steam mechanism oracle; no normal-card/turn claim."""
import json
import math
from steam_adversarial_evidence import EXTRAS, adversarial, foreign_contract, application_fixture
from steam_native_protocol import verify_native_protocol
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX = "[Volibear] DOMAIN_STEAM_RESULT "
SCOPE = "formal-native-steam-mechanism-with-labelled-instrumented-boundaries-not-normal-card-or-enemy-turn"
POINTS = {"pre-max": "before-protected-max-hp:instrumented", "post-max": "after-protected-max-hp:instrumented", "post-protected-hp": "after-protected-current-hp", "before-block": "before-block", "after-block": "after-block-before-primary-modifiers", "before-hp": "before-primary-hp", "after-hp": "after-hp-hooks", "overflow": "before-overflow-hp"}
KEEPER_VARIANTS = {f'keeper-{kind}-{point}': f'{kind}-{point}' for kind in ('external','veto') for point in ('after-hp','after-damage','set-hp')}
ENDING_VARIANTS = {f'sole-ending-external-{point}': f'external-{point}' for point in ('after-hp','after-damage','set-hp')}
VARIANTS = set(POINTS) | {"off", "on", "toggle", "late-phase", "late-powerless", "ordinary"} | EXTRAS | set(KEEPER_VARIANTS) | set(ENDING_VARIANTS)
SNAPSHOT = {"bossHp", "bossMaxHp", "bossAlive", "attached", "listed", "nodePresent", "sourcePresent", "hpDisplay", "nextMove", "playerHp", "playerMaxHp", "playerBlock", "petType", "petHp", "petMaxHp", "domain"}


def domain_steam_evidence(text, token, expected_variant=None):
    errors = []
    def need(ok, label):
        if not ok:
            errors.append(label)
    def number(value):
        return type(value) is int or type(value) is float and math.isfinite(value)
    def integer(value, expected):
        return type(value) is int and value == expected
    def no_verdict(value):
        if isinstance(value, dict):
            return not ({"expected", "pass", "passed", "verdict"} & value.keys()) and all(no_verdict(v) for v in value.values())
        return not isinstance(value, list) or all(no_verdict(v) for v in value)
    rows = []
    for line in text.splitlines():
        if PREFIX in line:
            try:
                row = json.loads(line.split(PREFIX, 1)[1])
                if isinstance(row, dict) and row.get("token") == token:
                    rows.append(row)
            except (ValueError, TypeError):
                errors.append("malformed result line")
    need(isinstance(token, str) and bool(token), "missing token")
    need(len(rows) == 1, "require exactly one matching-token result")
    if len(rows) != 1 or not isinstance(token, str) or not token:
        return {"errors": errors}
    r = rows[0]; variant = r.get("variant")
    if not isinstance(variant, str) or variant not in VARIANTS:
        errors.append("unknown variant")
        return {"errors": errors, "observation": r}
    need(expected_variant is None or variant == expected_variant, "requested variant mismatch")
    need(no_verdict(r), "runtime verdict/expectation forbidden")
    need(r.get("scenario") == "domain-steam" and r.get("completed") is True and r.get("testMode") is False, "native completion identity")
    need(r.get("gameVersion") == "0.107.1" and r.get("gameCommit") == EXPECTED_GAME_COMMIT, "pinned game metadata")
    need(r.get("acceptance") == SCOPE, "acceptance scope")
    need((r.get("encounter"), r.get("nativeType"), r.get("sourceType")) == ("WaterfallGiantBoss", "WaterfallGiant", "SteamEruptionPower"), "formal native provenance")
    need(integer(r.get("sourceAmount"), 15), "native default-ascension pressurize amount")
    need("SHUTDOWN_BEGIN " + token in text, "shutdown token")
    for marker in ("DOMAIN_STEAM_PROBE_ERROR", "Unhandled exception", "NullReferenceException", "InvalidProgramException", "Stack overflow", "System.InvalidOperationException"):
        need(marker not in text, "full-window error: " + marker)
    if variant not in VARIANTS:
        return {"errors": errors, "observation": r}
    if variant in KEEPER_VARIANTS or variant in ENDING_VARIANTS:
        keeper = variant in KEEPER_VARIANTS
        base = (KEEPER_VARIANTS if keeper else ENDING_VARIANTS)[variant]
        need(r.get('fixtureVariant') == base, 'explicit new fixture/base contract, never rename historical evidence')
        try:
            application_fixture(r, need, base, keeper)
            # Only the declared variant name is normalized; all real stages/events/receipts remain unchanged.
            verify_native_protocol(dict(r, variant=base), need, domain_applied=keeper, keeper_nonending=keeper)
            return adversarial(r, need, errors, SNAPSHOT, SCOPE, fixture_variant=base, domain_applied=keeper, keeper=keeper, sole_ending=not keeper)
        except (KeyError, TypeError, ValueError, IndexError):
            need(False, 'malformed application-precondition fixture')
            return {'errors': errors, 'observation': r}
    need(r.get('applicationFixture') is None and r.get('fixtureVariant') is None, 'original variants forbid hidden keeper/negative reinterpretation')
    need(r.get('soleAudioTail') is None, 'original variants forbid sole audio tail')
    try: verify_native_protocol(r, need)
    except (KeyError, TypeError, ValueError, IndexError): need(False, "malformed native protocol")
    if variant in EXTRAS:
        return adversarial(r, need, errors, SNAPSHOT, SCOPE)
    foreign_contract(r, need, 0 if variant == "ordinary" else 1 if variant in {"on", "pre-max", "post-max"} else 2)
    for field in ("resets", "nestedCalls", "removalReentries"):
        need(integer(r.get(field), 0), "no undeclared challenge: " + field)
    need(r.get("challengeInstrumentation") == "none", "no undeclared instrumentation")
    for field in ("beforeChallenge", "afterChallenge", "challengeState"):
        need(r.get(field) is None, "no undeclared challenge snapshot: " + field)
    snapshots = {}
    for key in ("initial", "final", "beforeOpen", "afterOpen", "afterDeath"):
        value = r.get(key)
        optional = key in ("beforeOpen", "afterOpen") and variant == "off" or key == "afterDeath" and variant == "ordinary"
        if optional:
            need(value is None, key + " must be absent")
            continue
        need(isinstance(value, dict) and SNAPSHOT <= value.keys(), key + " complete snapshot")
        if not isinstance(value, dict) or not SNAPSHOT <= value.keys():
            return {"errors": errors, "observation": r}
        snapshots[key] = value
        for field in ("bossHp", "bossMaxHp", "playerHp", "playerMaxHp", "playerBlock", "domain"):
            need(type(value[field]) is int and value[field] >= 0, key + "." + field + " native integer")
            if type(value[field]) is not int:
                return {"errors": errors, "observation": r}
        for field in ("bossAlive", "attached", "listed", "nodePresent", "sourcePresent"):
            need(type(value[field]) is bool, key + "." + field + " boolean")
    i = snapshots["initial"]; f = snapshots["final"]
    need(i["bossAlive"] and i["attached"] and i["listed"] and i["nodePresent"] and i["sourcePresent"], "fresh live boss")
    need(i["playerHp"] == i["playerMaxHp"] and i["playerBlock"] == 6 and i["domain"] == 0, "clean native player setup")
    need(r.get("boundary") == POINTS.get(variant, "none"), "exact boundary")
    need(integer(r.get("boundaryHits"), int(variant in POINTS)), "boundary hit count")
    need(integer(r.get("opens"), int(variant != "off")), "actual domain open count")
    need(r.get("boundaryMode") == ("instrumented-domain-open-at-native-command-or-hook-completion" if variant in POINTS else "none"), "instrumentation label")
    late = variant in {"late-phase", "late-powerless"}
    need(r.get("reentry") == ({"late-phase": "ABOUT_TO_BLOW_MOVE", "late-powerless": "EXPLODE_MOVE"}.get(variant)), "captured native reentry")
    full = variant in {"off", "toggle", "before-block", "after-block", "before-hp", "after-hp", "overflow"}
    expected_moves = ["PRESSURIZE_MOVE"] + (["STOMP_MOVE"] if variant == "ordinary" else ["ABOUT_TO_BLOW_MOVE", "EXPLODE_MOVE"] if full else ["ABOUT_TO_BLOW_MOVE"] if variant == "late-powerless" else [])
    need(r.get("attemptedMoves") == expected_moves, "declared attempts (not completion evidence)")
    hp_damage = 9 if variant in {"off", "toggle", "after-hp", "ordinary"} else 0
    block_spent = 6 if full and variant != "before-block" or variant == "ordinary" else 0
    need(f["playerHp"] == i["playerHp"] - hp_damage and f["playerBlock"] == 6 - block_spent, "committed player HP/block, no refund/replay")
    if variant == "ordinary":
        need(r.get("observation") is None and integer(r.get("died"), 0) and integer(r.get("sourceRemoved"), 0), "ordinary attack untagged")
        need(all(f[k] is True for k in ("bossAlive", "attached", "listed", "nodePresent", "sourcePresent")), "ordinary boss remains native")
        need(r.get("explicitWinCheck") is False and r.get("checkResult") is False and r.get("inProgress") is True, "ordinary combat ongoing")
    else:
        zero = variant in {"on", "pre-max", "post-max"}
        need(integer(r.get("died"), 1 if zero else 2) and integer(r.get("sourceRemoved"), 1), "actual native death/source removal counts")
        need(f["bossHp"] == 0 and all(f[k] is False for k in ("bossAlive", "attached", "listed", "nodePresent", "sourcePresent")), "no corpse/node/protected-HP ghost")
        need(r.get("explicitWinCheck") is True and r.get("checkResult") is True and r.get("inProgress") is False, "native action-boundary victory")
        o = r.get("observation")
        need(isinstance(o, dict), "owned episode observation")
        if not isinstance(o, dict):
            return {"errors": errors, "observation": r}
        need(o.get("sourceType") == "SteamEruptionPower" and o.get("monsterType") == "WaterfallGiant", "episode identities")
        need(type(o.get("generation")) is int and o["generation"] > 0 and type(o.get("epoch")) is int, "generation/epoch types")
        need(type(o.get("currentEpoch")) is int and o["currentEpoch"] == o.get("epoch"), "current owned epoch")
        need(integer(o.get("ownerDeathActive"), 0) and integer(o.get("ownerDeathAttempts"), 1 if zero else 2) and o.get("unconfirmedDeathHold") is False, "real native death lease settled")
        need(integer(o.get("initialDeaths"), 1) and integer(o.get("terminalDeaths"), 0 if zero else 1), "episode death contributions")
        need(o.get("confirmed") is True and o.get("retired") is True and o.get("terminalRequested") is True and o.get("terminalStarted") is True, "consumed episode")
        need(o.get("cancelled") is (variant not in {"off", "toggle"}), "cancellation vs unconsumed exit")
        need(o.get("terminalKillCommitted") is (not zero), "no zero-HP rekill; positive terminal kill retained")
        for key in ("deathDepth", "phaseDepth", "moveDepth", "attackDepth", "damageDepth"):
            need(integer(o.get(key), 0), "depth must close before caller continuation: " + key)
        expected_writes = []
        if variant not in {"on", "pre-max"}:
            expected_writes.append(("protected-max-hp", "boss", i["bossMaxHp"], 999999999))
        if not zero:
            expected_writes.append(("protected-current-hp", "boss", 0, 999999999))
        if full:
            expected_writes.append(("block:1", "player", 6, 6 - block_spent))
            if variant == "overflow":
                expected_writes += [("primary-hp:1", "osty", 5, 0), ("overflow-hp:1", "player", i["playerHp"], i["playerHp"])]
            else:
                expected_writes.append(("primary-hp:1", "player", i["playerHp"], i["playerHp"] - hp_damage))
        writes = o.get("writes")
        need(isinstance(writes, list) and len(writes) == len(expected_writes), "complete actual write receipts")
        if isinstance(writes, list):
            for actual, expected in zip(writes, expected_writes):
                need(isinstance(actual, dict) and all(k in actual for k in ("part", "receiver", "before", "after", "delta")), "write schema")
                if isinstance(actual, dict):
                    need((actual.get("part"), actual.get("receiver"), actual.get("before"), actual.get("after")) == expected, "exact native write")
                    need(all(number(actual.get(k)) for k in ("before", "after", "delta")), "receipt numeric types")
                    need(actual.get("delta") == expected[3] - expected[2], "receipt delta")
        need(integer(o.get("attackCommands"), int(full)), "tagged command count")
        results = o.get("damageResults")
        expected_results = ([{"receiver": "osty", "blocked": 0, "hp": 5, "overkill": 4, "killed": True, "blockBroken": False, "fullyBlocked": False}, {"receiver": "player", "blocked": 6, "hp": 0, "overkill": 0, "killed": False, "blockBroken": True, "fullyBlocked": False}] if variant == "overflow" else [{"receiver": "player", "blocked": block_spent, "hp": hp_damage, "overkill": 0, "killed": False, "blockBroken": block_spent == 6, "fullyBlocked": False}] if full else [])
        need(results == expected_results, "native DamageResult flags, not fabricated fully-blocked")
    need(integer(r.get("victories"), int(variant != "ordinary")) and integer(r.get("endings"), int(variant != "ordinary")), "single victory/end")
    need(f["domain"] == (0 if variant in {"off", "toggle"} or late else 3), "domain final state")
    if variant == "overflow":
        need((i["petType"], i["petHp"], i["petMaxHp"], f["petHp"]) == ("Osty", 5, 5, 0), "actual native redirected pet death")
    else:
        need(all(i[k] is None and f[k] is None for k in ("petType", "petHp", "petMaxHp")), "unexpected pet fixture")
    need(f["bossMaxHp"] == (i["bossMaxHp"] if variant in {"on", "pre-max", "ordinary"} else 999999999), "never refund committed max HP")
    need(f["hpDisplay"] == ("Normal" if variant in {"on", "pre-max", "post-max", "post-protected-hp", "ordinary"} else "InfiniteWithoutNumbers"), "future display gated, committed display retained")
    if variant != "off":
        before = snapshots["beforeOpen"]; after = snapshots["afterOpen"]
        need(before["domain"] == 0 and after["domain"] == 3, "actual domain entry")
        if late:
            need(before["bossHp"] == 999999999 and before["sourcePresent"] is (variant == "late-phase"), "pending phase provenance after real power removal")
            need(after["bossHp"] == 0 and all(after[k] is False for k in ("attached", "listed", "nodePresent")), "external entry drains before return without rescue")
        elif variant in POINTS:
            need(all(after[k] is True for k in ("attached", "listed", "nodePresent")), "in-flight ancestor not retired inside entry")
            need(after["bossHp"] == (0 if variant in {"pre-max", "post-max"} else 999999999), "in-flight committed HP retained")
            if full:
                need(before["sourcePresent"] is False and after["sourcePresent"] is False, "damage provenance survives power removal")
                need(before["playerBlock"] == (6 if variant == "before-block" else 0), "real block commit position")
                need(before["playerHp"] == i["playerHp"] - (9 if variant == "after-hp" else 0), "real HP commit position")
                if variant == "overflow":
                    need(before["petHp"] == 0 and after["petHp"] == 0, "overflow follows committed native pet HP")
    if variant != "ordinary":
        raw_results = r["observation"].get("damageResults")
        for result in raw_results if isinstance(raw_results, list) else []:
            need(isinstance(result, dict), "damage result object")
            if isinstance(result, dict):
                need(all(type(result.get(k)) is bool for k in ("killed", "blockBroken", "fullyBlocked")), "damage result boolean types")
                need(all(number(result.get(k)) for k in ("blocked", "hp", "overkill")), "damage result numeric types")
        trace = r.get("trace")
        need(isinstance(trace, list) and all(isinstance(item, str) for item in trace), "observed trace")
        if isinstance(trace, list):
            need(trace.count("initial-death-confirmed") == 1 and trace.count("terminal-death-confirmed") == (0 if variant in {"on", "pre-max", "post-max"} else 1), "native trace contribution counts")
            need(trace.count("steam-terminal-cleanup-finished") == 1, "single cleanup completion")
    # Every stage has its own fixed contract. Never derive an earlier stage from
    # the final snapshot: a refund followed by another debit is not preservation.
    need(i["bossHp"] == i["bossMaxHp"] and 0 < i["bossHp"] < 999999999, "initial natural full boss HP")
    need(i["nextMove"] == "STOMP_MOVE" and i["hpDisplay"] == "Normal", "initial natural state after pressurize")
    def stage(name, expected):
        actual = snapshots[name]
        for field in SNAPSHOT:
            need(actual[field] == expected[field] and type(actual[field]) is type(expected[field]), name + " fixed stage: " + field)
    protected = dict(i, bossHp=999999999, bossMaxHp=999999999, nextMove="ABOUT_TO_BLOW_MOVE", hpDisplay="InfiniteWithoutNumbers")
    retired = dict(i, bossHp=0, bossAlive=False, attached=False, listed=False, nodePresent=False, sourcePresent=False, nextMove=None,
                   bossMaxHp=i["bossMaxHp"] if variant in {"on", "pre-max"} else 999999999,
                   hpDisplay="Normal" if variant in {"on", "pre-max", "post-max", "post-protected-hp"} else "InfiniteWithoutNumbers")
    if variant != "ordinary":
        phase_cancel = variant in {"on", "pre-max", "post-max", "post-protected-hp"}
        stage("afterDeath", dict(retired, domain=3) if phase_cancel else protected)
    if variant != "off":
        expected_before = dict(i)
        if late:
            expected_before = dict(protected)
            if variant == "late-powerless": expected_before.update(sourcePresent=False, nextMove="EXPLODE_MOVE")
        elif variant in {"pre-max", "post-max", "post-protected-hp"}:
            expected_before.update(bossHp=999999999 if variant == "post-protected-hp" else 0,
                bossAlive=variant == "post-protected-hp", bossMaxHp=i["bossMaxHp"] if variant == "pre-max" else 999999999)
        elif variant in POINTS:
            expected_before = dict(protected, sourcePresent=False, nextMove="EXPLODE_MOVE",
                playerBlock=6 if variant == "before-block" else 0,
                playerHp=i["playerHp"] - (9 if variant == "after-hp" else 0))
            if variant == "overflow": expected_before["petHp"] = 0
        stage("beforeOpen", expected_before)
        stage("afterOpen", dict(retired, domain=3) if late else dict(expected_before, domain=3))
    expected_final = dict(i, nextMove="RAM_MOVE") if variant == "ordinary" else dict(retired)
    expected_final.update(playerHp=i["playerHp"] - hp_damage, playerBlock=6-block_spent,
        domain=0 if variant in {"off", "toggle"} or late else 3)
    if variant == "overflow": expected_final["petHp"] = 0
    stage("final", expected_final)
    native = r.get("nativeObservation")
    need(isinstance(native, dict), "independent native observations required")
    if isinstance(native, dict):
        need(native.get("externalDamageResults") == [], "no undeclared external damage")
        def exact(value, expected):
            if type(value) is not type(expected): return False
            if isinstance(expected, dict): return value.keys() == expected.keys() and all(exact(value[key], item) for key, item in expected.items())
            if isinstance(expected, list): return len(value) == len(expected) and all(exact(a, b) for a, b in zip(value, expected))
            return value == expected
        need(exact(native.get("completedMoves"), [{"id": move, "historyAdded": True} for move in expected_moves]), "actual completed native move history")
        native_results = ([{"receiver": "player", "blocked": 6, "hp": 9, "overkill": 0, "killed": False, "blockBroken": True, "fullyBlocked": False}]
                          if variant == "ordinary" else expected_results)
        need(exact(native.get("attacks"), ([{"historyAdded": True, "results": native_results}] if native_results else [])),  "actual native attack history")
        need(exact(native.get("damage"), [{"historyAdded": True, "result": result} for result in native_results]), "actual native damage history")
        for field in ("afterRemovedStarted", "afterRemovedCompleted"):
            need(type(native.get(field)) is int and native[field] == int(variant != "ordinary"), "actual source AfterRemoved completion: " + field)
        need(native.get("audioScope") == "native-loop-registration-and-parameter-calls-not-listening", "explicit native audio observation scope")
        need(native.get("initialAmbientRegistered") is True and native.get("finalAmbientRegistered") is (variant == "ordinary"), "actual loop registry lifecycle")
        stops = native.get("stops")
        need(isinstance(stops, list), "actual node stop observations")
        if isinstance(stops, list):
            need(all(isinstance(stop, dict) and type(stop.get("before")) is bool and stop.get("after") is False and type(stop.get("nodeStillInRoom")) is bool for stop in stops), "stop schema and no loop reactivation")
            active_stops = [stop for stop in stops if isinstance(stop, dict) and stop.get("before") is True]
            need(active_stops == ([] if variant == "ordinary" else [{"before": True, "after": False, "nodeStillInRoom": True}]), "one real stop while node still exists")
        music = [1, 1] if variant == "ordinary" else [1, 5, 5, 5] if variant == "post-protected-hp" else [1, 5, 5] if variant in {"on", "pre-max", "post-max"} else [1, 2, 5, 5] if variant == "late-phase" else [1, 2, 1, 5, 5]
        ambient = [1, 1] if variant == "ordinary" else [1, 2] if variant in {"on", "pre-max", "post-max", "post-protected-hp"} else [1, 3, 2] if variant == "late-phase" else [1, 3, 1, 2]
        need(native.get("musicParameterCalls") == music and all(number(v) for v in native.get("musicParameterCalls", [])), "real music calls preserve native cleanup")
        need(native.get("ambientParameterCalls") == ambient and all(number(v) for v in native.get("ambientParameterCalls", [])), "real ambient parameter calls")
        changes = native.get("changes")
        expected_changes = []
        def change(receiver, field, before, after): expected_changes.append({"receiver": receiver, "field": field, "before": before, "after": after})
        if variant != "ordinary":
            change("boss", "hp", i["bossHp"], 0)
            if variant not in {"on", "pre-max"}: change("boss", "maxHp", i["bossMaxHp"], 999999999)
            if variant not in {"on", "pre-max", "post-max"}: change("boss", "hp", 0, 999999999)
        if block_spent: change("player", "block", 6, 0)
        if hp_damage: change("player", "hp", i["playerHp"], i["playerHp"] - hp_damage)
        if variant == "overflow": change("osty", "hp", 5, 0)
        if variant not in {"ordinary", "on", "pre-max", "post-max"}: change("boss", "hp", 999999999, 0)
        need(isinstance(changes, list), "native creature change events")
        if isinstance(changes, list):
            need(all(isinstance(row, dict) and isinstance(row.get("stage"), str) and type(row.get("before")) is int and type(row.get("after")) is int for row in changes), "native change types and stage")
            need([{key: row.get(key) for key in ("receiver", "field", "before", "after")} if isinstance(row, dict) else None for row in changes] == expected_changes, "native event order: no transient refund or extra write")
    return {"errors": errors, "observation": r, "scope": SCOPE, "exit_and_leak_baseline_gate": "runner-required"}
