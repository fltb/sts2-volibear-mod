"""Synthetic gate tests ONLY; these fixtures are not engine evidence."""
import copy
import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from domain_dampen_evidence import MARKER, validate, check_log

# Independent literal rules oracle: never derive fixture results from the validator's expected table.
RULE_LEVELS = {"off": (0, 0), "on": (1, 1), "enter-await": (1, 1), "exit-await": (0, 0),
               "enter-pair": (0, 1), "exit-pair": (1, 0), "departure": (1, 1)}

TOKEN = "synthetic-dampen-gate-token"


def fixture(variant):
    after = list(RULE_LEVELS[variant])
    refs = ["c0", "c1"]
    debt = {refs[i]: 1 for i in range(2) if after[i] == 0}
    skipped = [i for i in range(2) if after[i] == 1]
    independent = skipped[0] if skipped else None
    modified = after.copy()
    if independent is not None:
        modified[independent] = 0
    restored = [1 if refs[i] in debt else modified[i] for i in range(2)]
    control_debt = {refs[i]: 1 for i in range(2) if restored[i] == 1}
    departed = variant == "departure"
    def entries(mapping):
        return [{"card": ref, "id": refs.index(ref) + 10, "oldLevel": level} for ref, level in mapping.items()]
    def cards(levels):
        return [{"id": i + 10, "reference": refs[i], "type": ["StrikeIronclad", "DefendIronclad"][i],
                 "level": level, "value": [6, 5][i] + 3 * level, "cost": 1, "pile": ["Hand", "Draw"][i], "owner": "owner"}
                for i, level in enumerate(levels)]
    names = ["baseline", "source", "off-no-replay"] + ([] if departed else ["joined"]) + ["independent"] + ([] if departed else ["first-death"]) + ["restored", "player-control", "player-restored"]
    steps = []
    for name in names:
        baseline = name == "baseline"
        player = name.startswith("player-")
        level = [1, 1] if baseline else [0, 0] if name == "player-control" else restored if name in ("restored", "player-restored") else modified if name in ("independent", "first-death") else after
        attached = baseline or (not departed and name in ("source", "off-no-replay", "joined", "independent"))
        casters = [] if baseline or player else ["source"] if departed else [] if name == "restored" else ["second"] if name == "first-death" else ["source", "second"] if name in ("joined", "independent") else ["source"]
        domain = variant in ("on", "enter-await", "enter-pair", "departure") if name == "source" else name in ("independent", "first-death", "restored", "player-control", "player-restored")
        steps.append(dict(name=name, phase={"baseline":"setup","source":"source","off-no-replay":"no-replay","joined":"no-replay","independent":"independent","first-death":"restoration","restored":"restoration","player-control":"player","player-restored":"player"}[name], domain=domain, ending=False, sourceAttached=attached,
            sourceCombat="combat" if attached else None, combat="combat", power=None if baseline else "control" if player else "power",
            present=not baseline and name not in ("restored", "player-restored"), amount=None if baseline else 1,
            applier=None if baseline else "owner" if player else "source", casters=casters,
            ledger=entries({} if baseline else control_debt if player else debt), cards=cards(level)))
    pairs = []
    running = {}
    for i in range(2):
        before = len(running)
        if after[i] == 0:
            running[refs[i]] = 1
        pairs.append(dict(phase="source", power="power", card=refs[i], id=i+10, source="source", combat="combat",
            invocationNonce=4, applyNonce=3, moveNonce=2, outerNonce=1, before=1, after=after[i], ledgerBefore=before,
            ledgerAfter=len(running), sourceDomainAtAdmission=bool(after[i]), domainAfter=True if variant == "enter-pair" else bool(after[i]),
            suppressed=bool(after[i]), provenance="native-magi", sourceAttached=not departed, nativeLedger=entries(running), sameNativeLedger=True))
    running = {}
    for ref in control_debt:
        before = len(running); running[ref] = 1
        pairs.append(dict(phase="player", power="control", card=ref, id=refs.index(ref)+10, source=None, combat=None,
            invocationNonce=7, applyNonce=0, moveNonce=0, outerNonce=0, before=1, after=0, ledgerBefore=before, ledgerAfter=len(running),
            sourceDomainAtAdmission=False, domainAfter=True, suppressed=False, provenance="player", sourceAttached=False,
            nativeLedger=entries(running), sameNativeLedger=True))
    events = [("source", refs[i], 1, 0) for i in range(2) if after[i] == 0]
    if independent is not None:
        events.append(("independent", refs[independent], 1, 0))
    events += [("restoration", ref, 0, 1) for ref in debt]
    events += [("player", ref, 1, 0) for ref in control_debt] + [("player", ref, 0, 1) for ref in control_debt]
    events = [dict(phase=phase, card=ref, id=refs.index(ref)+10, before=before, after=after_, domain=phase != "source") for phase, ref, before, after_ in events]
    boundaries = []
    if departed:
        boundaries.append(dict(kind="instrumented-native-outer-wait-departure", attachedBefore=True, attachedAfter=False, sourceCombatNull=True, after=True, originalWaitCompleted=True))
    elif variant not in ("on", "off"):
        entering = variant.startswith("enter-")
        boundary = dict(kind="instrumented-native-power-wait-continuation" if variant.endswith("await") else "native-card-Upgraded-event" if entering else "instrumented-post-pair", before=not entering, after=entering)
        if variant.endswith("await"):
            boundary["originalWaitCompleted"] = True
        else:
            boundary["card"] = refs[0]
        boundaries.append(boundary)
    sources = [{"reference": "source", "id": 2, "type": "MagiKnight"}] + ([] if departed else [{"reference": "second", "id": 4, "type": "MagiKnight"}])
    sites = {"Outer": "MegaCrit.Sts2.Core.Models.MonsterModel+<PerformMove>d__103.MoveNext", "Move": "MegaCrit.Sts2.Core.Models.Monsters.MagiKnight+<DampenMove>d__25.MoveNext",
             "Apply": "MegaCrit.Sts2.Core.Commands.PowerCmd+<Apply>d__2.MoveNext", "Pair": "MegaCrit.Sts2.Core.Models.Powers.DampenPower.AfterApplied", "Reset": "MegaCrit.Sts2.Core.Combat.CombatManager.Reset(System.Boolean)"}
    received = [dict(phase=phase, power=power, target="owner", applier=applier, amount=1, domain=phase == "player" or variant in ("on","exit-await","exit-pair","departure"))
                for phase, power, applier in (("source", "power", "source"), ("player", "control", "owner"))]
    return dict(schema=1, token=TOKEN, scenario="domain-dampen-transactions", variant=variant, version="v0.107.1", commit="59260271", encounter="KnightsElite",
        acceptance="native-source-ledger-card-pairs-not-power-admission-or-ordinary-input", testMode=False, sourceId=2, ownerId=1,
        sourceRef="source", ownerRef="owner", combatRef="combat", nativeMoveCalls=len(sources), directPowerCallbackCalls=0,
        initialCards=[{key: card[key] for key in ("id", "reference", "type")} for card in cards([1, 1])], independentCard=None if independent is None else refs[independent],
        cleanupKind="native-remove-after-escape" if departed else "native-last-caster-death",
        ilSites=[dict(Method=name, Kind=kind, SourceCalls=0 if kind == "Reset" else 1, SuccessCloses=0 if kind in ("Pair","Reset") else 1, FailureCloses=0 if kind in ("Pair","Reset") else 1, EntryBindings=0 if kind == "Reset" else 1, ReturnBindings=0 if kind in ("Pair","Reset") else 1, AwaitRegistrations={"Outer":3,"Move":2,"Apply":8,"Pair":0,"Reset":0}[kind], PatchType="Prefix" if kind == "Reset" else "Transpiler") for kind, name in sites.items()],
        patchTargets=[dict(Method=name,PatchType="Prefix" if kind=="Reset" else "Transpiler",PrefixOwners=["Volibear.DomainDampenTransactions"] if kind=="Reset" else [],TranspilerOwners=[] if kind=="Reset" else ["Volibear.DomainDampenTransactions"]) for kind,name in sites.items()],
        initialRoster=[{"reference": "flail", "id": 5, "type": "FlailKnight"}, {"reference": "keeper", "id": 3, "type": "SpectralKnight"}, sources[0]], rawSources=sources,
        moves=[dict(source=s["reference"], id=s["id"], type=s["type"], move="DAMPEN_MOVE") for s in sources], received=received,
        nativeReceived=[dict(power=r["power"], type="DampenPower", amount=1, applier=r["applier"], target="owner") for r in received],
        pairs=pairs, cardEvents=events, boundaries=boundaries, steps=steps, lifetimeAfter=dict(epoch=1, outer=0, moves=0, applies=0, powerSlots=0),
        admissionSuppression=False, artifactSuppression=False, endingRepair=False, exceptionRollback=False, escapeRestitutionRepair=False)


class GateTests(unittest.TestCase):
    def test_seven_synthetic_positive_shapes(self):
        for variant in RULE_LEVELS:
            with self.subTest(variant=variant):
                self.assertEqual(validate(fixture(variant), TOKEN, variant), [])

    def test_numeric_booleans_and_fractional_ids(self):
        for value in (True, 2.0):
            data=fixture("on"); data["sourceId"]=value
            self.assertTrue(validate(data,TOKEN,"on"))
        data=fixture("off"); data["pairs"][-1]["before"]=True
        self.assertTrue(validate(data,TOKEN,"off"))
        data=fixture("on"); data["pairs"][0]["applyNonce"]=True
        self.assertTrue(validate(data,TOKEN,"on"))

    def test_negative_mutations(self):
        mutations = [
            ("fake phantom debt", "on", lambda p: p["steps"][1]["ledger"].append(dict(card="c0",id=10,oldLevel=1))),
            ("only downgrade veto", "on", lambda p: p["pairs"][0].update(ledgerAfter=1,nativeLedger=[dict(card="c0",id=10,oldLevel=1)])),
            ("free upgrade after independent downgrade", "on", lambda p: next(s for s in p["steps"] if s["name"]=="restored")["cards"][0].update(level=1,value=9)),
            ("global downgrade veto", "on", lambda p: next(s for s in p["steps"] if s["name"]=="independent")["cards"][0].update(level=1,value=9)),
            ("entry cache instead of per-card live", "enter-pair", lambda p: p["pairs"][1].update(suppressed=False,sourceDomainAtAdmission=False,after=0)),
            ("rollback admitted first card", "enter-pair", lambda p: p["steps"][1]["cards"][0].update(level=1,value=9)),
            ("backfill skipped first card", "exit-pair", lambda p: p["steps"][1]["cards"][0].update(level=0,value=6)),
            ("domain exit replay", "on", lambda p: p["steps"][2]["cards"][0].update(level=0,value=6)),
            ("second caster reapplies", "on", lambda p: p["pairs"].append(copy.deepcopy(p["pairs"][0]))),
            ("first death restores", "off", lambda p: next(s for s in p["steps"] if s["name"]=="first-death")["cards"][0].update(level=1,value=9)),
            ("cleanup blocked by Domain", "off", lambda p: next(s for s in p["steps"] if s["name"]=="restored")["cards"][0].update(level=0,value=6)),
            ("power admission blocked", "on", lambda p: p["nativeReceived"].pop(0)),
            ("second caster identity fake", "off", lambda p: p["moves"][1].update(source="source",id=2)),
            ("private callback bypass", "on", lambda p: p.update(directPowerCallbackCalls=1)),
            ("wrong native move", "off", lambda p: p["moves"][0].update(move="POWER_SHIELD")),
            ("stale power authority", "on", lambda p: p["pairs"][1].update(power="old-power")),
            ("wrong combat authority", "on", lambda p: p["pairs"][1].update(combat="old-combat")),
            ("ambient nested invocation", "on", lambda p: p["pairs"][1].update(invocationNonce=99)),
            ("player inherits receipt", "on", lambda p: p["pairs"][-1].update(source="source",applyNonce=3)),
            ("player gets suppressed", "on", lambda p: p["pairs"][-1].update(suppressed=True)),
            ("source departure unproven", "departure", lambda p: p["pairs"][0].update(sourceAttached=True)),
            ("source inferred from victim", "departure", lambda p: p["pairs"][0].update(source="owner")),
            ("fake escape restitution", "departure", lambda p: p.update(cleanupKind="native-last-caster-death")),
            ("swallowed original wait", "enter-await", lambda p: p["boundaries"][0].update(originalWaitCompleted=False)),
            ("wrong live await switch", "exit-await", lambda p: p["boundaries"][0].update(after=True)),
            ("fake card event for blocked card", "exit-pair", lambda p: p["boundaries"][0].update(kind="native-card-Upgraded-event")),
            ("task receipt leak", "off", lambda p: p["lifetimeAfter"].update(applies=1)),
            ("missing pre-completion close", "off", lambda p: p["ilSites"][2].update(SuccessCloses=0)),
            ("native dynamic vars not reset", "off", lambda p: p["steps"][1]["cards"][0].update(value=9)),
            ("missing real restitution event", "off", lambda p: p["cardEvents"].pop(2)),
            ("mutation during ending", "off", lambda p: p["steps"][1].update(ending=True)),
            ("inflated scope", "off", lambda p: p.update(artifactSuppression=True)),
        ]
        for name, variant, mutate in mutations:
            with self.subTest(name=name):
                data=fixture(variant); mutate(data)
                self.assertTrue(validate(data,TOKEN,variant),name)

    def test_review_eleven_false_accept_classes(self):
        def replace(value, old, new):
            if isinstance(value,dict):
                for key,item in value.items():
                    value[key]=new if item==old else replace(item,old,new)
            elif isinstance(value,list):
                for index,item in enumerate(value):
                    value[index]=new if item==old else replace(item,old,new)
            return value
        cases = [
            ("enter-pair", lambda p:p["cardEvents"][0].update(domain=True)),
            ("on", lambda p:p["received"][0].update(phase="restoration",domain=False)),
            ("on", lambda p:[s.update(phase="wrong-epoch") for s in p["steps"]]),
            ("on", lambda p:p["pairs"][-1].update(id=99999)),
            ("on", lambda p:replace(p,"power","combat")),
            ("on", lambda p:replace(p,"c0","owner")),
            ("on", lambda p:(replace(p,"second","owner"),replace(p,4,1))),
            ("on", lambda p:replace(p,"keeper","source")),
            ("on", lambda p:p["steps"][0].update(casters=["source"])),
            ("on", lambda p:p["pairs"][-1].update(sourceDomainAtAdmission=True)),
        ]
        for index,(variant,mutate) in enumerate(cases):
            with self.subTest(index=index):
                p=fixture(variant);mutate(p);self.assertTrue(validate(p,TOKEN,variant))
        line=MARKER+json.dumps(fixture("on"))
        self.assertTrue(check_log(line+"\nUnhandled exception. System.InvalidOperationException: late failure",TOKEN,"on"))

    def test_exact_reset_owner_and_registration_anchors(self):
        for mutate in (
            lambda p:p["ilSites"].pop(),
            lambda p:p["ilSites"][2].update(AwaitRegistrations=7),
            lambda p:p["patchTargets"][-1].update(PrefixOwners=[]),
            lambda p:p["patchTargets"][-1].update(Method="wrong.Reset"),
            lambda p:p["patchTargets"][-1].update(PatchType="Transpiler"),
        ):
            p=fixture("on");mutate(p);self.assertTrue(validate(p,TOKEN,"on"))

    def test_independent_literal_oracle_detects_production_table_mutation(self):
        import domain_dampen_evidence as gate
        from unittest.mock import patch
        baseline=fixture("on")
        self.assertEqual([c["level"] for c in baseline["steps"][1]["cards"]],[1,1])
        with patch.dict(gate.LEVELS,{"on":[0,0]}):
            self.assertEqual(fixture("on"),baseline)
            # The independent positive-contract assertion must fail when the gate's rule is corrupted.
            with self.assertRaises(AssertionError):
                self.assertEqual(validate(fixture("on"),TOKEN,"on"),[])
        self.assertEqual(validate(fixture("on"),TOKEN,"on"),[])

    def test_global_nonce_order_pair_chronology_and_epoch(self):
        for value in (0,1,2,3,4):
            with self.subTest(player_nonce=value):
                p=fixture("on")
                for row in p["pairs"]:
                    if row["phase"]=="player": row["invocationNonce"]=value
                self.assertTrue(validate(p,TOKEN,"on"))
        p=fixture("off");p["pairs"]=p["pairs"][2:]+p["pairs"][:2]
        self.assertTrue(validate(p,TOKEN,"off"))
        p=fixture("on");p["lifetimeAfter"]["epoch"]=-1
        self.assertTrue(validate(p,TOKEN,"on"))
        p=fixture("on");p["lifetimeAfter"]["epoch"]=0
        for row in p["pairs"]:
            if row["phase"]=="source":row.update(outerNonce=10,moveNonce=30,applyNonce=50,invocationNonce=90)
            else:row["invocationNonce"]=700
        self.assertEqual(validate(p,TOKEN,"on"),[]) # Extra native allocations may create arbitrary positive gaps.
        p["pairs"][-1]["invocationNonce"]=5
        self.assertTrue(validate(p,TOKEN,"on")) # Rollback is illegal even without a collision.

    def test_exact_native_three_knights_roster_and_flail_identity(self):
        for variant in ("off","departure"):
            mutations = [
                lambda p:p["initialRoster"].pop(0),
                lambda p:p["initialRoster"][0].update(type="MagiKnight"),
                lambda p:p["initialRoster"].reverse(),
                lambda p:p["initialRoster"][0].update(reference="source"),
                lambda p:p["initialRoster"][0].update(reference="owner"),
                lambda p:p["initialRoster"][0].update(reference="combat"),
                lambda p:p["initialRoster"][0].update(reference="keeper"),
                lambda p:p["initialRoster"][0].update(reference="power"),
                lambda p:p["initialRoster"][0].update(reference="c0"),
                lambda p:p["initialRoster"][0].update(id=2),
                lambda p:p["initialRoster"][0].update(id=1),
                lambda p:p["initialRoster"][0].update(id=3),
            ]
            for i,mutate in enumerate(mutations):
                with self.subTest(variant=variant,mutation=i):
                    p=fixture(variant);mutate(p)
                    self.assertTrue(validate(p,TOKEN,variant))
        p=fixture("off");p["initialRoster"][0].update(reference="second",id=4)
        self.assertTrue(validate(p,TOKEN,"off"))

    def test_log_isolation_and_malformed_payloads(self):
        line=MARKER+json.dumps(fixture("on"))
        self.assertEqual(check_log(line,TOKEN,"on"),[])
        self.assertTrue(check_log(line,"other","on"))
        self.assertTrue(check_log(line+"\n"+line,TOKEN,"on"))
        self.assertTrue(check_log(line+"\nDOMAIN_DAMPEN_SOURCE_UNSUPPORTED",TOKEN,"on"))
        self.assertTrue(check_log(MARKER+'{"schema":1,"schema":1}',TOKEN,"on"))
        self.assertTrue(validate({},TOKEN,"on"))
        self.assertTrue(validate(None,TOKEN,"on"))


if __name__ == "__main__":
    unittest.main()
