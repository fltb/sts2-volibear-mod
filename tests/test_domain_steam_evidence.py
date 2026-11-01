"""Synthetic oracle-unit fixtures only. These are NOT native-game evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import copy
import json
import unittest
from steam_protocol_fixtures import protocol_fixture
from domain_steam_evidence import domain_steam_evidence, PREFIX, SCOPE

# Independent fixture table: deaths, HP lost, block lost, protected-write count, attack count, cancellation.
CASES = {
    "off": (2, 9, 6, 2, 1, False), "on": (1, 0, 0, 0, 0, True),
    "toggle": (2, 9, 6, 2, 1, False), "late-phase": (2, 0, 0, 2, 0, True),
    "late-powerless": (2, 0, 0, 2, 0, True), "pre-max": (1, 0, 0, 0, 0, True),
    "post-max": (1, 0, 0, 1, 0, True), "post-protected-hp": (2, 0, 0, 2, 0, True),
    "before-block": (2, 0, 0, 2, 1, True), "after-block": (2, 0, 6, 2, 1, True),
    "before-hp": (2, 0, 6, 2, 1, True), "after-hp": (2, 9, 6, 2, 1, True),
    "overflow": (2, 0, 6, 2, 1, True), "ordinary": (0, 9, 6, 0, 0, False),
}
BOUNDARIES = {"pre-max": "before-protected-max-hp:instrumented", "post-max": "after-protected-max-hp:instrumented", "post-protected-hp": "after-protected-current-hp", "before-block": "before-block", "after-block": "after-block-before-primary-modifiers", "before-hp": "before-primary-hp", "after-hp": "after-hp-hooks", "overflow": "before-overflow-hp"}


def fixture(mode):
    deaths, hp, block, protected, attack, cancelled = CASES[mode]
    initial = dict(bossHp=240, bossMaxHp=240, bossAlive=True, attached=True, listed=True, nodePresent=True, sourcePresent=True, hpDisplay="Normal", nextMove="STOMP_MOVE", playerHp=100, playerMaxHp=100, playerBlock=6, petType=None, petHp=None, petMaxHp=None, domain=0)
    if mode == "overflow":
        initial.update(petType="Osty", petHp=5, petMaxHp=5)
    final = dict(initial, playerHp=100-hp, playerBlock=6-block, domain=0 if mode in ("off", "toggle", "late-phase", "late-powerless") else 3)
    if mode != "ordinary":
        final.update(bossHp=0, bossMaxHp=999999999 if protected else 240, bossAlive=False, attached=False, listed=False, nodePresent=False, sourcePresent=False, nextMove=None, hpDisplay="Normal" if mode in ("on", "pre-max", "post-max", "post-protected-hp") else "InfiniteWithoutNumbers")
    else:
        final["nextMove"] = "RAM_MOVE"
    if mode == "overflow":
        final["petHp"] = 0
    revived = dict(initial, bossHp=999999999, bossMaxHp=999999999, hpDisplay="InfiniteWithoutNumbers", nextMove="ABOUT_TO_BLOW_MOVE")
    before = copy.deepcopy(initial)
    if mode in ("late-phase", "late-powerless") or mode in BOUNDARIES:
        before = copy.deepcopy(revived)
    if mode == "late-powerless" or attack and mode in BOUNDARIES:
        before.update(sourcePresent=False, nextMove="EXPLODE_MOVE", playerBlock=6-block, playerHp=100-hp)
    if mode in ("pre-max", "post-max"):
        before.update(bossHp=0, bossAlive=False, bossMaxHp=240 if mode == "pre-max" else 999999999, hpDisplay="Normal", nextMove="STOMP_MOVE")
    if mode == "post-protected-hp":
        before.update(hpDisplay="Normal", nextMove="STOMP_MOVE")
    if mode == "overflow":
        before["petHp"] = 0
    after = dict(before, domain=3)
    if mode in ("late-phase", "late-powerless"):
        after = dict(final, domain=3)
    writes = []
    def write(part, receiver, a, b):
        writes.append(dict(part=part, receiver=receiver, before=a, after=b, delta=b-a))
    if protected:
        write("protected-max-hp", "boss", 240, 999999999)
    if protected == 2:
        write("protected-current-hp", "boss", 0, 999999999)
    results = []
    if attack:
        write("block:1", "player", 6, 6-block)
        if mode == "overflow":
            write("primary-hp:1", "osty", 5, 0); write("overflow-hp:1", "player", 100, 100)
            results.append(dict(receiver="osty", blocked=0, hp=5, overkill=4, killed=True, blockBroken=False, fullyBlocked=False))
        else:
            write("primary-hp:1", "player", 100, 100-hp)
        results.append(dict(receiver="player", blocked=block, hp=hp, overkill=0, killed=False, blockBroken=block == 6, fullyBlocked=False))
    observation = dict(generation=1, epoch=1, currentEpoch=1, ownerDeathActive=0, ownerDeathAttempts=deaths, unconfirmedDeathHold=False, sourceType="SteamEruptionPower", monsterType="WaterfallGiant", initialDeaths=1, terminalDeaths=deaths-1, confirmed=True, cancelled=cancelled, terminalRequested=True, terminalStarted=True, terminalKillCommitted=deaths == 2, retired=True, deathDepth=0, phaseDepth=0, moveDepth=0, attackDepth=0, damageDepth=0, writes=writes, attackCommands=attack, damageResults=results)
    moves = ["PRESSURIZE_MOVE"] + (["STOMP_MOVE"] if mode == "ordinary" else ["ABOUT_TO_BLOW_MOVE", "EXPLODE_MOVE"] if attack else ["ABOUT_TO_BLOW_MOVE"] if mode == "late-powerless" else [])
    actual_results = results if mode != "ordinary" else [dict(receiver="player", blocked=6, hp=9, overkill=0, killed=False, blockBroken=True, fullyBlocked=False)]
    changes = []
    def changed(receiver, field, a, b): changes.append(dict(receiver=receiver, field=field, before=a, after=b, stage="synthetic-unit-only"))
    if deaths: changed("boss", "hp", 240, 0)
    if protected: changed("boss", "maxHp", 240, 999999999)
    if protected == 2: changed("boss", "hp", 0, 999999999)
    if block: changed("player", "block", 6, 0)
    if hp: changed("player", "hp", 100, 100-hp)
    if mode == "overflow": changed("osty", "hp", 5, 0)
    if deaths == 2: changed("boss", "hp", 999999999, 0)
    music = {"ordinary": [1,1], "on": [1,5,5], "pre-max": [1,5,5], "post-max": [1,5,5], "post-protected-hp": [1,5,5,5], "late-phase": [1,2,5,5]}.get(mode, [1,2,1,5,5])
    ambient = {"ordinary": [1,1], "on": [1,2], "pre-max": [1,2], "post-max": [1,2], "post-protected-hp": [1,2], "late-phase": [1,3,2]}.get(mode, [1,3,1,2])
    native = dict(completedMoves=[dict(id=move, historyAdded=True) for move in moves], attacks=[dict(historyAdded=True, results=actual_results)] if actual_results else [],
        damage=[dict(historyAdded=True, result=result) for result in actual_results], changes=changes,
        externalDamageResults=[], afterRemovedStarted=int(mode != "ordinary"), afterRemovedCompleted=int(mode != "ordinary"), initialAmbientRegistered=True, finalAmbientRegistered=mode == "ordinary",
        stops=[] if mode == "ordinary" else [dict(before=True, after=False, nodeStillInRoom=True)], musicParameterCalls=music, ambientParameterCalls=ambient,
        audioScope="native-loop-registration-and-parameter-calls-not-listening")
    return protocol_fixture(dict(token="unit-token", scenario="domain-steam", variant=mode, completed=True, testMode=False, gameVersion="0.107.1", gameCommit="59260271", acceptance=SCOPE, encounter="WaterfallGiantBoss", nativeType="WaterfallGiant", sourceType="SteamEruptionPower", sourceAmount=15,
                initial=initial, final=final, beforeOpen=None if mode == "off" else before, afterOpen=None if mode == "off" else after,
                afterDeath=None if mode == "ordinary" else copy.deepcopy(final if mode in ("on", "pre-max", "post-max", "post-protected-hp") else revived), observation=None if mode == "ordinary" else observation,
                foreignObservation=dict(beforeDeathCalls=deaths, vetoes=0, restoreCalls=0, restorations=0, retentionVotes=0, nativeRecursions=[0]*deaths,
                    votes=[dict(native=True, final=True, injected=False) for _ in range(deaths)], instrumentation="foreign-final-hook-vote-and-native-AfterPreventingDeath-HP-restoration-not-mock-power"),
                resets=0, nestedCalls=0, removalReentries=0, beforeChallenge=None, afterChallenge=None, challengeState=None, challengeInstrumentation="none",
                attemptedMoves=moves, nativeObservation=native, trace=[] if mode == "ordinary" else ["initial-death-confirmed", "steam-terminal-cleanup-finished"] + (["terminal-death-confirmed"] if deaths == 2 else []),
                boundary=BOUNDARIES.get(mode, "none"), boundaryMode="instrumented-domain-open-at-native-command-or-hook-completion" if mode in BOUNDARIES else "none", opens=int(mode != "off"), boundaryHits=int(mode in BOUNDARIES),
                reentry={"late-phase": "ABOUT_TO_BLOW_MOVE", "late-powerless": "EXPLODE_MOVE"}.get(mode), died=deaths, sourceRemoved=int(mode != "ordinary"), explicitWinCheck=mode != "ordinary", checkResult=mode != "ordinary", victories=int(mode != "ordinary"), endings=int(mode != "ordinary"), inProgress=mode == "ordinary"))


def log(row):
    return PREFIX + json.dumps(row) + "\n[Volibear] SHUTDOWN_BEGIN unit-token"


class SteamEvidenceTests(unittest.TestCase):
    def accept(self, row):
        errors = domain_steam_evidence(log(row), "unit-token", row["variant"])["errors"]
        self.assertEqual([], errors)
    def reject(self, row):
        self.assertTrue(domain_steam_evidence(log(row), "unit-token")["errors"])
    def test_all_explicit_variants(self):
        for variant in CASES:
            with self.subTest(variant=variant): self.accept(fixture(variant))
    def test_missing_every_snapshot_field(self):
        for field in fixture("after-block")["final"]:
            row = fixture("after-block"); del row["final"][field]; self.reject(row)
    def test_top_level_missing_and_wrong_types(self):
        for field in ("token", "scenario", "variant", "completed", "testMode", "gameVersion", "gameCommit", "acceptance", "encounter", "nativeType", "sourceType", "sourceAmount", "initial", "final", "observation", "died", "opens", "boundaryHits", "attemptedMoves", "nativeObservation", "trace"):
            row = fixture("after-block"); row.pop(field); self.reject(row)
        for value in (None, [], {}, True, 1):
            row = fixture("after-block"); row["variant"] = value; self.reject(row)
    def test_version_and_scope_not_relaxed(self):
        for field, value in (("gameVersion", "v0.107.1"), ("gameCommit", "other"), ("testMode", True), ("acceptance", "normal-card-pass"), ("encounter", "MockEncounter"), ("sourceType", "OtherPower"), ("sourceAmount", 20)):
            row = fixture("off"); row[field] = value; self.reject(row)
    def test_depth_types_and_inline_boundary(self):
        for field in ("deathDepth", "phaseDepth", "moveDepth", "attackDepth", "damageDepth"):
            for value in (True, False, None, 0.0, "0", -1, 1):
                row = fixture("after-block"); row["observation"][field] = value; self.reject(row)
    def test_committed_block_and_hp_never_refunded(self):
        for mode, field, value in (("after-block", "playerBlock", 6), ("after-hp", "playerHp", 100), ("post-max", "bossMaxHp", 240), ("overflow", "petHp", 5)):
            row = fixture(mode); row["final"][field] = value; self.reject(row)
    def test_future_writes_and_zero_hp_rekill(self):
        for mode in ("before-block", "after-block", "before-hp", "overflow"):
            row = fixture(mode); row["final"]["playerHp"] -= 1; self.reject(row)
        row = fixture("on"); row["died"] = 2; self.reject(row)
        row = fixture("late-powerless"); row["died"] = 3; self.reject(row)
    def test_receipts_flags_and_foreign_source(self):
        for field, value in (("fullyBlocked", True), ("killed", 0), ("hp", False), ("receiver", "foreign")):
            row = fixture("after-block"); row["observation"]["damageResults"][0][field] = value; self.reject(row)
        row = fixture("overflow"); row["observation"]["writes"].pop(); self.reject(row)
        row = fixture("after-block"); row["observation"]["writes"][2]["delta"] = 0; self.reject(row)
    def test_no_runtime_expected_or_verdict(self):
        row = fixture("off"); row["expected"] = {}; self.reject(row)
        row = fixture("off"); row["observation"]["passed"] = True; self.reject(row)
    def test_nonfinite_and_bool_snapshots(self):
        for value in (False, True, None, "100", float("nan"), float("inf"), 100.0):
            row = fixture("off"); row["initial"]["playerHp"] = value; self.reject(row)
    def test_token_variant_duplicate_and_late_exception(self):
        text = log(fixture("off"))
        self.assertTrue(domain_steam_evidence(text, "wrong")["errors"])
        self.assertTrue(domain_steam_evidence(text, "unit-token", "on")["errors"])
        self.assertTrue(domain_steam_evidence(text + "\n" + text, "unit-token")["errors"])
        self.assertTrue(domain_steam_evidence(text + "\nSystem.NullReferenceException late", "unit-token")["errors"])
    def test_independent_history_cleanup_and_transient_refund(self):
        for field in fixture("off")["nativeObservation"]:
            row = fixture("off"); del row["nativeObservation"][field]; self.reject(row)
        row = fixture("off"); row["nativeObservation"]["completedMoves"].pop(); self.reject(row)
        row = fixture("off"); row["nativeObservation"]["damage"] = []; self.reject(row)
        row = fixture("off"); row["nativeObservation"]["attacks"][0]["historyAdded"] = 1; self.reject(row)
        row = fixture("off"); row["nativeObservation"]["afterRemovedCompleted"] = 0; self.reject(row)
        row = fixture("off"); row["nativeObservation"]["musicParameterCalls"].pop(); self.reject(row)
        row = fixture("off"); row["nativeObservation"]["stops"][0]["nodeStillInRoom"] = False; self.reject(row)
        row = fixture("after-block"); row["nativeObservation"]["changes"].extend([
            dict(receiver="player", field="block", before=0, after=6, stage="refund"),
            dict(receiver="player", field="block", before=6, after=0, stage="redebit")]); self.reject(row)
    def test_review_six_false_accept_regressions(self):
        for mode, stage, key, value in (("off", "afterDeath", "bossHp", 0), ("on", "afterDeath", "bossHp", 999999999),
                ("after-block", "afterOpen", "playerHp", 1), ("after-block", "afterOpen", "playerBlock", 6),
                ("off", "final", "nextMove", "EXPLODE_MOVE"), ("off", "initial", "nextMove", "UNRELATED")):
            row = fixture(mode); row[stage][key] = value; self.reject(row)
    def test_each_stage_single_field_mutation(self):
        for mode in CASES:
            for stage in ("afterDeath", "beforeOpen", "afterOpen", "final"):
                original = fixture(mode)[stage]
                if original is None: continue
                for key, value in original.items():
                    with self.subTest(mode=mode, stage=stage, key=key):
                        row = fixture(mode)
                        row[stage][key] = not value if type(value) is bool else value + 1 if type(value) is int else "MUTATED"
                        self.reject(row)
    def test_no_early_ancestor_retirement_or_power_lookup_fallback(self):
        row = fixture("before-hp"); row["afterOpen"]["listed"] = False; self.reject(row)
        row = fixture("overflow"); row["beforeOpen"]["petHp"] = 5; self.reject(row)
        row = fixture("late-powerless"); row["beforeOpen"]["sourcePresent"] = True; self.reject(row)
        row = fixture("late-phase"); row["reentry"] = None; self.reject(row)


if __name__ == "__main__": unittest.main()
