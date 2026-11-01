"""Synthetic protocol mutations, never actual native evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import copy
import unittest
from test_domain_steam_evidence import fixture, log
from domain_steam_evidence import domain_steam_evidence
from steam_adversarial_evidence import LABELS
from steam_protocol_fixtures import protocol_fixture


def challenge(mode):
    if mode in {"external-after-hp","veto-after-hp","external-after-damage","veto-after-damage","external-set-hp","veto-set-hp"}:
        r=challenge("veto-powerless" if mode.startswith("veto-") else "external-powerless")
        r.update(variant=mode,challengeInstrumentation=LABELS[mode])
        r["windowBefore"]=dict(copy.deepcopy(r["beforeChallenge"]),ownerHpCommandsActive=1)
        r["windowAfter"]=dict(copy.deepcopy(r["windowBefore"]),cancelled=True,terminalRequested=True)
        if mode.endswith("-set-hp"): r["nativeObservation"]["externalDamageResults"]=[]
        return protocol_fixture(r)
    if mode == "off-veto-followup":
        r=fixture("off"); r.update(variant=mode,challengeInstrumentation=LABELS[mode])
        o=r["observation"]; n=r["nativeObservation"]; hp=r["initial"]["playerHp"]
        first=copy.deepcopy(o["damageResults"][0]); second=dict(receiver="player",blocked=0,hp=15,overkill=0,killed=False,blockBroken=False,fullyBlocked=False)
        r["beforeChallenge"]=dict(copy.deepcopy(o),terminalDeaths=0,retired=False,terminalRequested=False,terminalStarted=False,terminalKillCommitted=False,ownerDeathAttempts=1,attackCommands=0,damageResults=[],writes=copy.deepcopy(o["writes"][:2]))
        r["afterChallenge"]=dict(copy.deepcopy(r["beforeChallenge"]),ownerDeathAttempts=2,unconfirmedDeathHold=True,attackCommands=1,damageResults=[first],writes=copy.deepcopy(o["writes"]))
        r["challengeState"]=dict(r["afterDeath"],sourcePresent=False,nextMove="EXPLODE_MOVE",playerBlock=0,playerHp=hp-9)
        o.update(ownerDeathAttempts=3,attackCommands=2,damageResults=[first,second]); r["final"]["playerHp"]=hp-24
        o["writes"] += [dict(part="block:1",receiver="player",before=0,after=0,delta=0),dict(part="primary-hp:1",receiver="player",before=hp-9,after=hp-24,delta=-15)]
        n["damage"].append(dict(historyAdded=True,result=copy.deepcopy(second))); n["attacks"].append(dict(historyAdded=True,results=[copy.deepcopy(second)]))
        n["changes"] += [dict(receiver="boss",field="hp",before=0,after=999999999),dict(receiver="player",field="hp",before=hp-9,after=hp-24),dict(receiver="boss",field="hp",before=999999999,after=0)]
        n["musicParameterCalls"]=[1,2,1,5,5,5,5]; r["attemptedMoves"].append("EXPLODE_MOVE"); n["completedMoves"].append(dict(id="EXPLODE_MOVE",historyAdded=True))
        r["foreignObservation"].update(beforeDeathCalls=3,vetoes=1,restoreCalls=1,restorations=1,nativeRecursions=[0,0,0],votes=[dict(native=True,final=True,injected=False),dict(native=True,final=False,injected=True),dict(native=True,final=True,injected=False)])
        return protocol_fixture(r)
    if mode == "external-powerless":
        r = challenge("veto-powerless"); r.update(variant=mode,challengeInstrumentation=LABELS[mode],died=2,explicitWinCheck=True,checkResult=True,victories=1,endings=1,inProgress=False)
        r["final"].update(bossHp=0,bossAlive=False,attached=False,listed=False,nodePresent=False,nextMove=None)
        r["challengeState"] = copy.deepcopy(r["final"])
        r["observation"].update(terminalDeaths=1,terminalStarted=True,retired=True,unconfirmedDeathHold=False)
        r["afterChallenge"] = copy.deepcopy(r["observation"])
        r["foreignObservation"].update(vetoes=0,restoreCalls=0,restorations=0,votes=[dict(native=True,final=True,injected=False)]*2)
        r["nativeObservation"]["changes"].pop()
        r["trace"] = ["initial-death-confirmed","terminal-death-confirmed"]
        return protocol_fixture(r)
    base = {"nested-command":"before-block", "nested-damage":"before-block", "after-removed-reentry":"late-phase", "veto-source-retained":"off", "veto-powerless":"late-powerless", "foreign-retention":"on", "pending-reset":"before-block"}[mode]
    r = fixture(base); r["variant"] = mode; r["challengeInstrumentation"] = LABELS[mode]
    o = r["observation"]; n = r["nativeObservation"]; foreign = r["foreignObservation"]
    protected = dict(r["initial"], bossHp=999999999,bossMaxHp=999999999,nextMove="ABOUT_TO_BLOW_MOVE",hpDisplay="InfiniteWithoutNumbers")
    def checkpoint():
        return dict(copy.deepcopy(o), cancelled=False, terminalDeaths=0, retired=False, terminalRequested=False, terminalStarted=False, terminalKillCommitted=False,
            ownerDeathAttempts=1, attackCommands=0, damageResults=[], writes=copy.deepcopy(o["writes"][:2]))
    if mode in ("nested-command","nested-damage"):
        r["nestedCalls"] = 1; r["final"]["playerBlock"] = 4
        o["writes"][2].update(before=4,after=4)
        result = dict(receiver="player",blocked=2,hp=0,overkill=0,killed=False,blockBroken=False,fullyBlocked=True)
        n["damage"].insert(0,dict(historyAdded=True,result=result))
        if mode == "nested-command": n["attacks"].insert(0,dict(historyAdded=True,results=[copy.deepcopy(result)]))
        n["changes"].insert(-1,dict(receiver="player",field="block",before=6,after=4,stage="synthetic-nested"))
    if mode == "after-removed-reentry":
        r["opens"] = 2; r["removalReentries"] = 1
        r["beforeChallenge"] = dict(checkpoint(),cancelled=True,terminalRequested=True,terminalStarted=True)
        r["afterChallenge"] = copy.deepcopy(r["beforeChallenge"])
        r["challengeState"] = dict(protected,sourcePresent=False,domain=3)
    if mode in ("veto-source-retained","veto-powerless"):
        foreign.update(vetoes=1,restoreCalls=1,restorations=1)
        r["beforeChallenge"] = checkpoint()
        r["afterChallenge"] = dict(checkpoint(),ownerDeathAttempts=2,unconfirmedDeathHold=True)
        n["changes"][3:3] = [dict(receiver="boss",field="hp",before=999999999,after=0,stage="actual-lethal"),dict(receiver="boss",field="hp",before=0,after=999999999,stage="fixture-restoration")]
        if mode == "veto-source-retained":
            foreign.update(beforeDeathCalls=3,nativeRecursions=[0,0,0],votes=[dict(native=True,final=True,injected=False),dict(native=True,final=False,injected=True),dict(native=True,final=True,injected=False)])
            o["ownerDeathAttempts"] = 3; r["challengeState"] = copy.deepcopy(protected)
        else:
            foreign["votes"][1].update(final=False,injected=True)
            r.update(died=1,explicitWinCheck=False,checkResult=False,victories=0,endings=0,inProgress=True,reentry=None)
            r["final"] = dict(protected,sourcePresent=False,nextMove="EXPLODE_MOVE",domain=3)
            r["beforeOpen"] = dict(r["final"],bossHp=0,bossAlive=False,domain=0)
            r["afterOpen"] = dict(r["beforeOpen"],domain=3)
            r["challengeState"] = copy.deepcopy(r["final"])
            r["afterChallenge"].update(cancelled=True,terminalRequested=True)
            o.update(terminalDeaths=0,terminalStarted=False,terminalKillCommitted=False,retired=False,unconfirmedDeathHold=True)
            n["changes"].pop(); n["musicParameterCalls"].pop()
            n["externalDamageResults"] = [dict(receiver="boss",blocked=0,hp=999999999,overkill=0,killed=True,blockBroken=False,fullyBlocked=False)]
            r["trace"] = ["initial-death-confirmed"]
    if mode == "foreign-retention":
        foreign["retentionVotes"] = 3
        r.update(explicitWinCheck=False,checkResult=False,victories=0,endings=0,inProgress=True)
        retained = dict(r["initial"],bossHp=0,bossAlive=False,sourcePresent=False,domain=3)
        r["final"] = retained; r["afterDeath"] = copy.deepcopy(retained)
        o.update(retired=False,terminalStarted=False)
        r["trace"] = ["initial-death-confirmed"]; n["musicParameterCalls"].pop()
    if mode == "pending-reset":
        r.update(opens=0,resets=1,died=1,explicitWinCheck=False,checkResult=False,victories=0,endings=0,inProgress=True,beforeOpen=None,afterOpen=None)
        r["beforeChallenge"] = dict(checkpoint(),cancelled=False,moveDepth=1,attackDepth=1,damageDepth=1,attackCommands=1)
        r["afterChallenge"] = dict(copy.deepcopy(r["beforeChallenge"]),currentEpoch=2)
        r["final"] = dict(protected,sourcePresent=False,nextMove="EXPLODE_MOVE")
        o.update(currentEpoch=2,cancelled=False,terminalDeaths=0,terminalRequested=False,terminalStarted=False,terminalKillCommitted=False,retired=False,ownerDeathAttempts=1)
        n["changes"].pop(); n["musicParameterCalls"] = [1,2,1]
        r["trace"] = ["initial-death-confirmed"]
        foreign.update(beforeDeathCalls=1,nativeRecursions=[0],votes=[dict(native=True,final=True,injected=False)])
    return protocol_fixture(r)


class ChallengeTests(unittest.TestCase):
    def check(self,row): return domain_steam_evidence(log(row),"unit-token",row["variant"])["errors"]
    def test_fifteen_explicit_instrumented_variants(self):
        for mode in LABELS:
            with self.subTest(mode=mode): self.assertEqual([],self.check(challenge(mode)))
    def test_mutate_every_stage_field(self):
        for mode in LABELS:
            for stage in ("final","afterDeath","beforeOpen","afterOpen","challengeState"):
                value = challenge(mode)[stage]
                if value is None: continue
                for field,item in value.items():
                    with self.subTest(mode=mode,stage=stage,field=field):
                        row=challenge(mode); row[stage][field]=not item if type(item)is bool else item+1 if type(item)is int else "WRONG"
                        self.assertTrue(self.check(row))
    def test_native_veto_retry_and_generations(self):
        for mode in ("veto-source-retained","veto-powerless"):
            for field,value in (("nativeRecursions",[0,1]),("restoreCalls",0),("restorations",0),("vetoes",True)):
                row=challenge(mode); row["foreignObservation"][field]=value; self.assertTrue(self.check(row))
            row=challenge(mode); row["afterChallenge"]["generation"]+=1; self.assertTrue(self.check(row))
            row=challenge(mode); row["afterChallenge"]["terminalDeaths"]=1; self.assertTrue(self.check(row))
        row=challenge("veto-powerless"); row["nativeObservation"]["externalDamageResults"]=[]; self.assertTrue(self.check(row))
    def test_second_review_false_accept_regressions(self):
        row=challenge("veto-source-retained"); row["beforeChallenge"]["terminalKillCommitted"]=True; self.assertTrue(self.check(row))
        row=challenge("veto-powerless"); row["afterChallenge"]["writes"]=[]; self.assertTrue(self.check(row))
        row=challenge("pending-reset"); row["afterChallenge"]["writes"]=[dict(part="primary-hp:1",receiver="foreign",before=100,after=0,delta=-100)]; self.assertTrue(self.check(row))
        row=challenge("nested-command"); row["trace"]=["terminal-death-confirmed","initial-death-confirmed","steam-terminal-cleanup-finished"]; self.assertTrue(self.check(row))
        row=challenge("nested-command"); row["trace"]=["initial-death-confirmed","steam-terminal-cleanup-finished","terminal-death-confirmed"]; self.assertTrue(self.check(row))
        row=challenge("nested-command")
        for event in row["nativeObservation"]["changes"]: event["stage"]="FOREIGN_AFTER_COMBAT"
        self.assertTrue(self.check(row))
    def test_every_checkpoint_field_and_receipt_component(self):
        for mode in LABELS:
            for name in ("beforeChallenge","afterChallenge","windowBefore","windowAfter"):
                value=challenge(mode).get(name)
                if not isinstance(value,dict): continue
                for field,item in value.items():
                    row=challenge(mode); row[name][field]=not item if type(item)is bool else item+1 if type(item)is int else "WRONG"
                    with self.subTest(mode=mode,checkpoint=name,field=field): self.assertTrue(self.check(row))
                for index,write in enumerate(value["writes"]):
                    for key,item in write.items():
                        row=challenge(mode); row[name]["writes"][index][key]=item+1 if type(item)is int else "foreign"
                        with self.subTest(mode=mode,checkpoint=name,receipt=index,field=key): self.assertTrue(self.check(row))
    def test_third_review_snapshot_stage_interval(self):
        row=fixture("before-block")
        for edge in row["nativeObservation"]["stageEvents"]:
            if edge["name"]=="domain-entry:before-block": edge["changeCursor"]=4
        self.assertIn("snapshot lies inside its real stage interval: beforeOpen",self.check(row))
    def test_third_review_cross_root_history_reordering(self):
        row=fixture("off"); h=row["nativeObservation"]["historyEvidence"]
        h["captured"].sort(key=lambda entry: entry["data"]["type"]=="MonsterPerformedMoveEntry")
        for index,entry in enumerate(h["captured"],h["initialCount"]): entry["index"]=index
        h["actualFinal"]=[dict(index=entry["index"],data=copy.deepcopy(entry["data"])) for entry in h["captured"]]
        h["allFinalReferences"]=copy.deepcopy(h["initialReferences"])+[dict(index=entry["index"],referenceId=entry["referenceId"],type=entry["data"]["type"],sameHistory=True) for entry in h["captured"]]
        self.assertIn("history global cursor and actual root chronology",self.check(row))
    def test_third_review_complete_reference_inventory_count(self):
        row=fixture("off"); row["nativeObservation"]["historyEvidence"]["finalCount"]=999999
        self.assertIn("history counts supported by complete reference inventory",self.check(row))
        for field in ("initialReferences","allFinalReferences","finalContentScope"):
            row=fixture("off"); del row["nativeObservation"]["historyEvidence"][field]; self.assertTrue(self.check(row))
        row=fixture("off"); row["nativeObservation"]["historyEvidence"]["allFinalReferences"][1]["referenceId"]=999999; self.assertTrue(self.check(row))
    def test_direct_nested_history_stage_ownership(self):
        label="direct nested/parent history ownership and child-before-parent continuation"
        for mode in ("nested-command","nested-damage"):
            actions=("child-damage-to-parent","parent-damage-to-child","swap-damage-stages","swap-all-stages","swap-all-stages-rebuild-inventory","swap-physical-records-rebuild-inventory")
            if mode=="nested-command": actions+=("child-attack-to-parent",)
            for action in actions:
                row=challenge(mode); n=row["nativeObservation"]; h=n["historyEvidence"]
                parent=next(e["id"] for e in n["stageEvents"] if e["kind"]=="begin" and e["name"]=="move:EXPLODE_MOVE")
                child=next(e["id"] for e in n["stageEvents"] if e["kind"]=="begin" and e["name"]=="nested-native-"+mode.split("-")[1])
                entries=h["captured"]
                child_d=next(e for e in entries if e["stageId"]==child and e["data"]["type"]=="DamageReceivedEntry")
                parent_d=next(e for e in entries if e["stageId"]==parent and e["data"]["type"]=="DamageReceivedEntry")
                if action=="child-damage-to-parent": child_d["stageId"]=parent
                elif action=="parent-damage-to-child": parent_d["stageId"]=child
                elif action=="child-attack-to-parent":
                    next(e for e in entries if e["stageId"]==child and e["data"]["type"]=="CreatureAttackedEntry")["stageId"]=parent
                elif action=="swap-damage-stages": child_d["stageId"],parent_d["stageId"]=parent,child
                elif action.startswith("swap-all-stages"):
                    for entry in entries:
                        if entry["data"]["type"] in {"DamageReceivedEntry","CreatureAttackedEntry"} and entry["stageId"] in {parent,child}:
                            entry["stageId"]=child if entry["stageId"]==parent else parent
                else:
                    for kind in ("DamageReceivedEntry","CreatureAttackedEntry"):
                        c=[i for i,e in enumerate(entries) if e["stageId"]==child and e["data"]["type"]==kind]
                        p=[i for i,e in enumerate(entries) if e["stageId"]==parent and e["data"]["type"]==kind]
                        if c and p: entries[c[0]],entries[p[0]]=entries[p[0]],entries[c[0]]
                if action.endswith("rebuild-inventory"):
                    for index,entry in enumerate(entries,h["initialCount"]): entry["index"]=index
                    h["actualFinal"]=[dict(index=e["index"],data=copy.deepcopy(e["data"])) for e in entries]
                    h["allFinalReferences"]=copy.deepcopy(h["initialReferences"])+[dict(index=e["index"],referenceId=e["referenceId"],type=e["data"]["type"],sameHistory=True) for e in entries]
                with self.subTest(mode=mode,action=action): self.assertIn(label,self.check(row))
    def test_actual_history_reference_content_and_order(self):
        for field,value in (("sameReferenceAtEnd",False),("sameHistoryAtEnd",False),("changeCursor",999),("stageId",999),("index",999)):
            row=challenge("nested-command"); row["nativeObservation"]["historyEvidence"]["captured"][0][field]=value; self.assertTrue(self.check(row))
        row=challenge("nested-command"); row["nativeObservation"]["historyEvidence"]["captured"][0]["finalData"]["actor"]="foreign"; self.assertTrue(self.check(row))
        row=challenge("nested-command"); row["nativeObservation"]["historyEvidence"]["actualFinal"].pop(); self.assertTrue(self.check(row))
        row=challenge("veto-powerless"); row["nativeObservation"]["historyEvidence"]["externalHistoryGates"]=[]; self.assertTrue(self.check(row))
        row=challenge("veto-powerless"); row["nativeObservation"]["historyEvidence"]["externalPlayerToBoss"]=[dict(type="DamageReceivedEntry",actor="foreign")]; self.assertTrue(self.check(row))
    def test_real_lethal_windows_and_later_native_followup(self):
        for mode in ("external-after-hp","veto-after-hp","external-after-damage","veto-after-damage","external-set-hp","veto-set-hp"):
            for name in ("windowBefore","windowAfter"):
                row=challenge(mode); row[name]["ownerHpCommandsActive"]=0; self.assertTrue(self.check(row))
                row=challenge(mode); row[name]["ownerDeathActive"]=1; self.assertTrue(self.check(row))
            row=challenge(mode); row["foreignObservation"]["hookWindows"][0]["deathEntries"]=2; self.assertTrue(self.check(row))
        row=challenge("off-veto-followup"); row["afterChallenge"]["terminalStarted"]=True; self.assertTrue(self.check(row))
        row=challenge("off-veto-followup"); row["observation"]["terminalAttemptCount"]=1; self.assertTrue(self.check(row))
        row=challenge("off-veto-followup"); row["nativeObservation"]["attacks"].pop(); self.assertTrue(self.check(row))
    def test_external_terminal_confirmation_not_adapter_kill(self):
        for field,value in (("terminalDeaths",0),("terminalKillCommitted",True),("retired",False)):
            row=challenge("external-powerless"); row["observation"][field]=value; self.assertTrue(self.check(row))
        row=challenge("external-powerless"); row["died"]=1; self.assertTrue(self.check(row))
    def test_nested_reset_and_reentry_negative_controls(self):
        row=challenge("nested-command"); row["nativeObservation"]["attacks"].pop(0); self.assertTrue(self.check(row))
        row=challenge("nested-damage"); row["observation"]["writes"][2]["before"]=6; self.assertTrue(self.check(row))
        row=challenge("pending-reset"); row["observation"]["currentEpoch"]=1; self.assertTrue(self.check(row))
        row=challenge("pending-reset"); row["nativeObservation"]["musicParameterCalls"].append(5); self.assertTrue(self.check(row))
        row=challenge("after-removed-reentry"); row["nativeObservation"]["afterRemovedCompleted"]=2; self.assertTrue(self.check(row))
        row=challenge("foreign-retention"); row["foreignObservation"]["retentionVotes"]=0; self.assertTrue(self.check(row))

if __name__ == "__main__": unittest.main()
