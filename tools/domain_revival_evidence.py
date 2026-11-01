"""Independent oracle for the deliberately mechanism-only formal revival probe.
No normal-card, whole enemy-turn, Steam, Adaptable or Stock acceptance is inferred.
"""
from __future__ import annotations
import json
import math

PREFIX = "[Volibear] DOMAIN_REVIVAL_RESULT "
SCOPE = "formal-native-revival-mechanism-not-normal-card-or-enemy-turn"
API = "CreatureCmd.Kill;MonsterModel.PerformMove;Creature.PrepareForNextTurn;DomainPower.Open;PowerCmd.Remove"
MODES = {"off", "on", "late", "cached", "toggle"}


def domain_revival_errors(report: dict, token: str) -> list[str]:
    errors: list[str] = []
    def need(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)
    if not isinstance(report, dict):
        return ["missing object result"]
    required = set("token scenario variant completed testMode gameVersion gameCommit acceptance discovery fixtureApi encounter nativeType sourceType sourceAmount setupMoves initial initialFatal minionFatalBefore minionFatalAfter livePowerSurvivedOpen fatalWithInitialDomain beforeCachedOpen afterDeath afterOpen afterExitOrRevive normalMoves reentry died callbackCount sourceRemoved afterRemoved managerNotifications nativeBodiesExecuted deathDepthAfterKill trace explicitWinCheck checkResult victories endings inProgress".split())
    need(required <= report.keys(), "missing observation fields")
    need(bool(token) and report.get("token") == token, "token mismatch")
    need(report.get("scenario") == "domain-revival", "scenario mismatch")
    need(report.get("completed") is True and report.get("testMode") is False, "not completed outside TestMode")
    need(report.get("gameVersion") == "0.107.1" and report.get("gameCommit") == "59260271", "unpinned native version")
    need(report.get("acceptance") == SCOPE, "wrong acceptance scope")
    need(report.get("discovery") == "native encounter and native deployed power", "fabricated discovery")
    need(report.get("fixtureApi") == API, "wrong fixture API")
    need(not any(key in report for key in ("expected", "passed", "pass", "verdict")), "runtime verdict/expectation is not evidence")
    parts = str(report.get("variant", "")).split("-")
    if len(parts) != 2 or parts[0] not in ("reattach", "illusion") or parts[1] not in MODES:
        return errors + ["unsupported variant"]
    family, mode = parts
    reattach = family == "reattach"
    control = mode in ("off", "toggle")
    need(report.get("encounter") == ("DecimillipedeElite" if reattach else "TheObscuraNormal"), "wrong formal encounter")
    need(report.get("nativeType") == ("DecimillipedeSegmentFront" if reattach else "Parafright"), "wrong formal monster")
    need(report.get("sourceType") == ("ReattachPower" if reattach else "IllusionPower"), "wrong native power")
    need(type(report.get("sourceAmount")) in (int, float) and report.get("sourceAmount") == (25 if reattach else 1), "wrong native power amount")
    need(report.get("setupMoves") == ([] if reattach else ["ILLUSION_MOVE"]), "non-native setup sequence")
    need(report.get("livePowerSurvivedOpen") is True, "unconsumed live source destroyed")
    need(report.get("initialFatal") is False, "initial native Fatal semantics changed")
    need(report.get("fatalWithInitialDomain") is (reattach and mode in ("on", "toggle")), "typed Fatal vote mismatch")
    need(report.get("minionFatalBefore") is (None if reattach else False) and
         report.get("minionFatalAfter") is (None if reattach else False), "independent Minion fatal veto lost")
    pending_move = "DEAD_MOVE" if reattach else "REVIVE_MOVE"
    def snap(name: str, state: str) -> dict:
        data = report.get(name)
        if not isinstance(data, dict):
            errors.append(f"missing snapshot {name}")
            return {}
        need(set("hp maxHp alive attached listed nodePresent sourcePresent nextMove".split()) <= data.keys(), f"{name} missing fields")
        for key in ("hp", "maxHp"):
            value = data.get(key)
            need(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value), f"{name}.{key} not finite")
        need(isinstance(data.get("maxHp"), (int, float)) and data.get("maxHp", 0) > 0, f"{name} bad max HP")
        retired = state == "retired"
        alive = state in ("initial", "revived")
        for key in ("attached", "listed", "nodePresent", "sourcePresent"):
            need(data.get(key) is (not retired), f"{name}.{key} lifecycle mismatch")
        need(data.get("alive") is alive, f"{name} alive mismatch")
        if not alive:
            need(type(data.get("hp")) in (int, float) and data["hp"] == 0, f"{name} ghost HP")
        else:
            need(type(data.get("hp")) in (int, float) and data["hp"] > 0, f"{name} missing live HP")
        if state == "pending":
            need(data.get("nextMove") == pending_move, f"{name} missing actual pending native state")
        if retired:
            need(data.get("nextMove") is None, f"{name} stale state machine")
        return data
    initial = snap("initial", "initial")
    snap("afterDeath", "pending" if mode in ("off", "toggle", "late") else "retired")
    snap("afterOpen", "pending" if control else "retired")
    last = snap("afterExitOrRevive", "revived" if control else "retired")
    if control and initial and last:
        need(last.get("maxHp") == initial.get("maxHp"), "control changed max HP")
        if type(initial.get("maxHp")) in (int, float):
            need(last.get("hp") == (min(25, initial["maxHp"]) if reattach else initial["maxHp"]), "native revive amount mismatch")
    if mode == "cached":
        snap("beforeCachedOpen", "pending")
    else:
        need(report.get("beforeCachedOpen") is None, "spurious cached-window fixture")
    need(report.get("normalMoves") == ((["DEAD_MOVE", "REATTACH_MOVE"] if reattach else ["REVIVE_MOVE"]) if control else []), "control bypassed native move sequence")
    need(report.get("reentry") == ("captured-native-callback-after-cancel" if mode == "late" else "none"), "missing explicit stale-callback label")
    for key, expected in (("deathDepthAfterKill", 0), ("died", 1), ("callbackCount", 1), ("nativeBodiesExecuted", 0 if mode == "on" else 1), ("sourceRemoved", 0 if control else 1),
                          ("afterRemoved", 0 if control else 1), ("managerNotifications", 0 if control else 1)):
        need(type(report.get(key)) is int and report[key] == expected, f"{key}: duplicate/missing native lifecycle")
    expected_trace = ["cached-removal-repaired"] if mode == "cached" else ["late-corpse-retired"] if mode == "late" else []
    need(report.get("trace") == expected_trace, "wrong cleanup branch or repeated cleanup")
    need(report.get("explicitWinCheck") is (not control), "win probe mislabeled")
    need(report.get("checkResult") is (not control), "native win check result mismatch")
    need(report.get("inProgress") is control, "combat lifecycle stuck/ended early")
    for key in ("victories", "endings"):
        need(type(report.get(key)) is int and report[key] == (0 if control else 1), f"{key} not exactly once")
    return errors


def domain_revival_evidence(log: str, token: str, expected_variant: str | None = None) -> tuple[dict, bool]:
    payloads = [line.split(PREFIX, 1)[1] for line in log.splitlines() if PREFIX in line]
    if len(payloads) != 1:
        return {"errors": ["expected exactly one revival payload"]}, False
    try:
        report = json.loads(payloads[0])
    except (ValueError, TypeError):
        return {"errors": ["invalid revival JSON"]}, False
    errors = domain_revival_errors(report, token)
    if expected_variant is not None and (not isinstance(report, dict) or report.get('variant') != expected_variant):
        errors.append('requested variant mismatch')
    marker = "[Volibear] SHUTDOWN_BEGIN " + token
    if log.count(marker) != 1 or log.find(marker) < log.find(PREFIX):
        errors.append("missing/early/duplicate shutdown marker")
    for marker in ("DOMAIN_REVIVAL_PROBE_ERROR", "Unhandled exception", "InvalidProgramException", "NullReferenceException"):
        if marker in log:
            errors.append("full-window failure: " + marker)
    # Headless runner must additionally apply its shared exit/leak/native-baseline gates.
    return {"observation": report, "errors": errors, "scope": SCOPE}, not errors
