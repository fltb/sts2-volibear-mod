"""Synthetic execution tapes only: these are not native observations or acceptance evidence."""
import copy


def protocol_fixture(r):
    v=r["variant"]; n=r["nativeObservation"]; changes=n["changes"]; edges=[]; stack=[]; serial=0; cursor=0; captured=[]; damage_index=0; attack_index=0
    trace=[]; gates=[]
    def begin(name):
        nonlocal serial
        serial+=1; edges.append(dict(kind="begin",id=serial,parent=stack[-1][0] if stack else 0,name=name,changeCursor=cursor)); stack.append((serial,name))
    def end():
        identity,name=stack.pop(); edges.append(dict(kind="end",id=identity,parent=stack[-1][0] if stack else 0,name=name,changeCursor=cursor))
    def change():
        nonlocal cursor
        changes[cursor].update(index=cursor,stageId=stack[-1][0],stage=stack[-1][1]); cursor+=1
    def snap(name):
        if r.get(name) is not None: r[name].update(nativeEventCursor=cursor,nativeStageId=stack[-1][0] if stack else 0)
    def history(data):
        captured.append(dict(index=len(captured)+1,stageId=stack[-1][0],changeCursor=cursor,data=copy.deepcopy(data),finalData=copy.deepcopy(data),sameReferenceAtEnd=True,sameHistoryAtEnd=True))
    def move_record(name): history(dict(type="MonsterPerformedMoveEntry",actor="boss",move=name,targets=["player"]))
    def damage_record():
        nonlocal damage_index
        result=n["damage"][damage_index]["result"]; damage_index+=1
        history(dict(type="DamageReceivedEntry",actor=result["receiver"],dealer="boss",cardSource=None,result=result))
    def attack_record():
        nonlocal attack_index
        result=n["attacks"][attack_index]["results"]; attack_index+=1
        history(dict(type="CreatureAttackedEntry",actor="boss",results=result))
    def open_domain(late=False):
        begin("domain-entry:"+v); snap("beforeOpen")
        if v=="after-removed-reentry": begin("after-removed-reentry"); snap("challengeState"); end()
        if late: change(); trace.extend(["terminal-death-confirmed","steam-terminal-cleanup-finished"])
        snap("afterOpen"); end()
    def restore(): begin("foreign-native-restoration"); change(); end()
    def about(): begin("move:ABOUT_TO_BLOW_MOVE"); move_record("ABOUT_TO_BLOW_MOVE"); end()
    def explode(first_veto=False):
        begin("move:EXPLODE_MOVE")
        if v in {"before-block","nested-command","nested-damage"}: open_domain()
        if v in {"nested-command","nested-damage"}:
            begin("nested-native-"+v.split("-")[1]); change(); damage_record()
            if v=="nested-command": attack_record()
            end()
        else:
            while cursor<len(changes) and changes[cursor]["receiver"]!="boss":
                change()
                if v in {"after-block","before-hp"} and changes[cursor-1]["field"]=="block": open_domain()
            if v in {"after-hp","overflow"}: open_domain()
        for _ in range(2 if v=="overflow" else 1): damage_record()
        attack_record()
        if v!="pending-reset":
            change()
            if first_veto: restore(); trace.append("steam-terminal-cleanup-finished")
            else: trace.extend(["terminal-death-confirmed","steam-terminal-cleanup-finished"])
        move_record("EXPLODE_MOVE")
        if first_veto: trace.append("uncancelled-native-veto-move-finished")
        end()
    begin("move:PRESSURIZE_MOVE"); move_record("PRESSURIZE_MOVE"); end(); snap("initial")
    if v in {"on","toggle","ordinary","foreign-retention"}: open_domain()
    if v=="ordinary":
        begin("move:STOMP_MOVE")
        while cursor<len(changes): change()
        damage_record(); attack_record(); move_record("STOMP_MOVE"); end()
    else:
        begin("initial-native-kill"); change(); trace.append("initial-death-confirmed")
        if v=="pre-max": open_domain()
        if v not in {"on","pre-max","foreign-retention"}:
            change()
            if v=="post-max": open_domain()
            else:
                change()
                if v=="post-protected-hp": open_domain(); change(); trace.append("terminal-death-confirmed")
        if v in {"on","pre-max","post-max","post-protected-hp"}: trace.append("steam-terminal-cleanup-finished")
        end(); snap("afterDeath")
        if v=="veto-source-retained": begin("veto-native-kill"); change(); restore(); end(); snap("challengeState")
        if v in {"late-phase","after-removed-reentry"}: open_domain(late=True)
        elif v not in {"on","pre-max","post-max","post-protected-hp","foreign-retention"}:
            about()
            if v=="late-powerless": open_domain(late=True)
            elif v in {"veto-powerless","external-powerless"} or v.startswith(("external-after-","veto-after-","external-set-","veto-set-")):
                set_hp=v.endswith("-set-hp"); begin("external-set-hp" if set_hp else "external-native-damage"); change()
                if not set_hp: gates.append(dict(isEnding=True,bossHp=0,stageId=stack[-1][0],changeCursor=cursor))
                if v not in {"veto-powerless","external-powerless"}:
                    r["foreignObservation"]["hookWindows"]=[dict(point="AfterDamageGiven" if v.endswith("-after-damage") else "AfterCurrentHpChanged",bossHp=0,deathEntries=1,nativeEventCursor=cursor,stageId=stack[-1][0])]
                open_domain()
                if v.startswith("veto-"): restore()
                else: trace.append("terminal-death-confirmed")
                end(); snap("challengeState")
            elif v=="off-veto-followup": explode(True); snap("challengeState"); explode()
            else: explode()
        if v in {"late-phase","late-powerless","after-removed-reentry"}:
            begin("captured-reentry:"+("EXPLODE_MOVE" if v=="late-powerless" else "ABOUT_TO_BLOW_MOVE")); end()
    snap("final")
    assert cursor==len(changes), (v,cursor,len(changes))
    n["stageEvents"]=edges; r["trace"]=trace
    initial_refs=[dict(index=0,referenceId=1,type="BlockGainedEntry",sameHistory=True)]
    for row in captured: row["referenceId"]=row["index"]+1
    all_refs=copy.deepcopy(initial_refs)+[dict(index=row["index"],referenceId=row["referenceId"],type=row["data"]["type"],sameHistory=True) for row in captured]
    n["historyEvidence"]=dict(initialReferences=initial_refs,allFinalReferences=all_refs,finalContentScope="related-move-attack-damage-subset;all-kinds-reference-inventory-only",initialCount=1,finalCount=1+len(captured),initialReferencesIntact=True,captured=captured,
        actualFinal=[dict(index=row["index"],data=copy.deepcopy(row["data"])) for row in captured],externalPlayerToBoss=[],externalHistoryGates=gates)
    r["foreignObservation"].setdefault("hookWindows",[])
    r.setdefault("windowBefore",None); r.setdefault("windowAfter",None)
    for name in ("observation","beforeChallenge","afterChallenge","windowBefore","windowAfter"):
        o=r.get(name)
        if not isinstance(o,dict): continue
        count=0
        if name=="observation": count=2 if v=="off-veto-followup" else int(o["terminalKillCommitted"])
        elif name=="afterChallenge" and v=="off-veto-followup": count=1
        o.update(ownerHpCommandsActive=int(name in {"windowBefore","windowAfter"}),terminalAttemptCount=count,terminalDeathConfirmed=o["terminalDeaths"]>0)
    return r
