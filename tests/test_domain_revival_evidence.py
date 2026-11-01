"""Synthetic adversarial ORACLE tests; never native gameplay evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
module_path = root / "tools" / "domain_revival_evidence.py"
if not module_path.exists():
    module_path = Path(__file__).with_name("domain_revival_evidence.py")
spec = importlib.util.spec_from_file_location("domain_revival_evidence", module_path)
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def fixture(family="reattach", mode="late"):
    reattach = family == "reattach"
    control = mode in ("off", "toggle")
    def snapshot(state):
        alive = state in ("initial", "revived")
        return dict(hp=60 if state == "initial" or state == "revived" and not reattach else 25 if state == "revived" else 0,
                    maxHp=60, alive=alive, attached=state != "retired", listed=state != "retired",
                    nodePresent=state != "retired", sourcePresent=state != "retired",
                    nextMove=None if state == "retired" else ("DEAD_MOVE" if reattach else "REVIVE_MOVE") if state == "pending" else "IDLE")
    return dict(token="unit-token", scenario="domain-revival", variant=family + "-" + mode, completed=True,
                testMode=False, gameVersion="0.107.1", gameCommit="59260271", acceptance=oracle.SCOPE,
                discovery="native encounter and native deployed power", fixtureApi=oracle.API,
                encounter="DecimillipedeElite" if reattach else "TheObscuraNormal",
                nativeType="DecimillipedeSegmentFront" if reattach else "Parafright",
                sourceType="ReattachPower" if reattach else "IllusionPower", sourceAmount=25 if reattach else 1,
                setupMoves=[] if reattach else ["ILLUSION_MOVE"], initial=snapshot("initial"), initialFatal=False,
                minionFatalBefore=None if reattach else False, minionFatalAfter=None if reattach else False,
                livePowerSurvivedOpen=True, fatalWithInitialDomain=reattach and mode in ("on", "toggle"),
                beforeCachedOpen=snapshot("pending") if mode == "cached" else None,
                afterDeath=snapshot("pending" if mode in ("off", "toggle", "late") else "retired"),
                afterOpen=snapshot("pending" if control else "retired"),
                afterExitOrRevive=snapshot("revived" if control else "retired"),
                normalMoves=(["DEAD_MOVE", "REATTACH_MOVE"] if reattach else ["REVIVE_MOVE"]) if control else [],
                reentry="captured-native-callback-after-cancel" if mode == "late" else "none",
                died=1, callbackCount=1, deathDepthAfterKill=0, nativeBodiesExecuted=0 if mode == "on" else 1,
                sourceRemoved=0 if control else 1, afterRemoved=0 if control else 1,
                managerNotifications=0 if control else 1,
                trace=["cached-removal-repaired"] if mode == "cached" else ["late-corpse-retired"] if mode == "late" else [],
                explicitWinCheck=not control, checkResult=not control, victories=0 if control else 1,
                endings=0 if control else 1, inProgress=control)


def log(report):
    return oracle.PREFIX + json.dumps(report) + "\n[Volibear] SHUTDOWN_BEGIN unit-token\n"


class RevivalOracleTests(unittest.TestCase):
    def test_requested_variant_is_bound(self):
        raw = log(fixture('reattach', 'off'))
        self.assertTrue(oracle.domain_revival_evidence(raw, 'unit-token', 'reattach-off')[1])
        for other in ('reattach-on', 'illusion-off', 'unknown'):
            with self.subTest(other=other):
                self.assertFalse(oracle.domain_revival_evidence(raw, 'unit-token', other)[1])

    def test_all_ten_independent_branches(self):
        for family in ("reattach", "illusion"):
            for mode in oracle.MODES:
                with self.subTest(family=family, mode=mode):
                    report, ok = oracle.domain_revival_evidence(log(fixture(family, mode)), "unit-token")
                    self.assertTrue(ok, report)

    def test_missing_every_field(self):
        for family in ("reattach", "illusion"):
            for mode in oracle.MODES:
                base = fixture(family, mode)
                for key in base:
                    altered = copy.deepcopy(base)
                    del altered[key]
                    with self.subTest(family=family, mode=mode, missing=key):
                        self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_lifecycle_counts_are_exact_integers(self):
        for field in ("died", "callbackCount", "sourceRemoved", "afterRemoved", "managerNotifications", "victories", "endings"):
            for value in (0, 2, True, 1.0, "1", None):
                altered = fixture(); altered[field] = value
                with self.subTest(field=field, value=value):
                    self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_death_depth_released_before_caller_resumes(self):
        for mode in oracle.MODES:
            for value in (1, -1, None, "0", False, 0.0):
                altered = fixture("illusion", mode); altered["deathDepthAfterKill"] = value
                with self.subTest(mode=mode, depth=value):
                    self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_no_ghosts_or_stale_nodes(self):
        for field, value in (("hp", 25), ("alive", True), ("attached", True), ("listed", True),
                             ("nodePresent", True), ("sourcePresent", True), ("nextMove", "REVIVE_MOVE")):
            altered = fixture(); altered["afterExitOrRevive"][field] = value
            with self.subTest(field=field):
                self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_bad_hp_types_never_crash_or_pass(self):
        for mode in oracle.MODES:
            for value in ("60", None, True, [], {}, float("nan"), float("inf"), -2):
                altered = fixture("reattach", mode); altered["initial"]["maxHp"] = value
                with self.subTest(mode=mode, value=value):
                    self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_scope_and_source_not_interchangeable(self):
        for field, value in (("nativeType", "MockMonster"), ("sourceType", "SteamEruptionPower"),
                             ("acceptance", "normal-card"), ("encounter", "SlimesNormal"),
                             ("gameCommit", "other"), ("gameVersion", "0.107.2"), ("token", "stale"),
                             ("sourceAmount", 99), ("fixtureApi", "fake-executor"), ("setupMoves", ["forced-state"]),
                             ("discovery", "source scan"), ("expected", {}), ("passed", True)):
            altered = fixture(); altered[field] = value
            with self.subTest(field=field):
                self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_no_posthoc_cached_window_claim(self):
        altered = fixture("illusion", "cached"); altered["beforeCachedOpen"] = altered["afterOpen"]
        self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])
        altered = fixture("reattach", "cached"); altered["trace"] = []
        self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_independent_minion_vote_and_live_source_survive(self):
        for field in ("minionFatalBefore", "minionFatalAfter"):
            altered = fixture("illusion", "on"); altered[field] = True
            self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])
        altered = fixture("reattach", "toggle"); altered["livePowerSurvivedOpen"] = False
        self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_native_control_cannot_be_replaced_by_noop(self):
        for family in ("reattach", "illusion"):
            altered = fixture(family, "off"); altered["afterExitOrRevive"]["hp"] = 1
            self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])
            altered = fixture(family, "off"); altered["normalMoves"] = []
            self.assertFalse(oracle.domain_revival_evidence(log(altered), "unit-token")[1])

    def test_complete_window_and_uniqueness(self):
        good = log(fixture())
        bad_logs = ["", good + good, good.replace("unit-token", "stale"), good.split("\n")[0],
                    good + "\nUnhandled exception\n", good + "\nDOMAIN_REVIVAL_PROBE_ERROR\n",
                    good + "\nNullReferenceException\n", "[Volibear] SHUTDOWN_BEGIN unit-token\n" + good.split("\n")[0],
                    oracle.PREFIX + "{bad-json}\n", oracle.PREFIX + "[]\n"]
        for bad in bad_logs:
            with self.subTest(log=bad[-60:]):
                self.assertFalse(oracle.domain_revival_evidence(bad, "unit-token")[1])


if __name__ == "__main__":
    unittest.main()
