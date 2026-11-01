"""Independent native stage, history identity, and chronological protocol contracts."""
WINDOWS = {f"{kind}-{point}" for kind in ("external","veto") for point in ("after-hp","after-damage","set-hp")}
EXTERNAL = {"external-powerless"} | {v for v in WINDOWS if v.startswith("external-")}
POWERLESS_VETO = {"veto-powerless"} | {v for v in WINDOWS if v.startswith("veto-")}
BOUNDARY = {"before-block","after-block","before-hp","after-hp","overflow","nested-command","nested-damage"}

def exact(a,b):
    if type(a)is not type(b): return False
    if isinstance(b,dict): return a.keys()==b.keys() and all(exact(a[k],v) for k,v in b.items())
    if isinstance(b,list): return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b

def stage_plan(v):
    domain="domain-entry:"+v; roots=["move:PRESSURIZE_MOVE"]
    if v in {"on","toggle","ordinary","foreign-retention"}: roots.append(domain)
    if v=="ordinary": roots.append("move:STOMP_MOVE"); return roots,[]
    roots.append("initial-native-kill")
    if v=="veto-source-retained": roots.append("veto-native-kill")
    if v in {"late-phase","after-removed-reentry"}: roots += [domain,"captured-reentry:ABOUT_TO_BLOW_MOVE"]
    elif v not in {"on","pre-max","post-max","post-protected-hp","foreign-retention"}:
        roots.append("move:ABOUT_TO_BLOW_MOVE")
        if v=="late-powerless": roots += [domain,"captured-reentry:EXPLODE_MOVE"]
        elif v in EXTERNAL|POWERLESS_VETO: roots.append("external-set-hp" if v.endswith("-set-hp") else "external-native-damage")
        else:
            roots.append("move:EXPLODE_MOVE")
            if v=="off-veto-followup": roots.append("move:EXPLODE_MOVE")
    children=[]
    if v in {"pre-max","post-max","post-protected-hp"}: children.append((domain,"initial-native-kill"))
    if v in BOUNDARY: children.append((domain,"move:EXPLODE_MOVE"))
    if v in EXTERNAL|POWERLESS_VETO: children.append((domain,roots[-1]))
    if v in {"nested-command","nested-damage"}: children.append(("nested-native-"+v.split("-")[1],"move:EXPLODE_MOVE"))
    if v=="after-removed-reentry": children.append((v,domain))
    if v in POWERLESS_VETO|{"veto-source-retained","off-veto-followup"}:
        children.append(("foreign-native-restoration","veto-native-kill" if v=="veto-source-retained" else "move:EXPLODE_MOVE" if v=="off-veto-followup" else roots[-1]))
    return roots,children

def expected_trace(v):
    initial="initial-death-confirmed"; terminal="terminal-death-confirmed"; cleanup="steam-terminal-cleanup-finished"
    if v=="ordinary": return []
    if v in POWERLESS_VETO|{"pending-reset","foreign-retention"}: return [initial]
    if v in EXTERNAL: return [initial,terminal]
    if v in {"on","pre-max","post-max"}: return [initial,cleanup]
    if v=="off-veto-followup": return [initial,cleanup,"uncancelled-native-veto-move-finished",terminal,cleanup]
    return [initial,terminal,cleanup]

def expected_change_stages(r):
    v=r["variant"]; changes=r["nativeObservation"]["changes"]; names=[]
    for index,row in enumerate(changes):
        if v=="off-veto-followup": name=(["initial-native-kill"]*3+["move:EXPLODE_MOVE"]*3+["foreign-native-restoration"]+["move:EXPLODE_MOVE"]*2)[index] if index<9 else "EXTRA"
        elif v=="ordinary": name="move:STOMP_MOVE"
        elif index< (1 if v in {"on","pre-max","foreign-retention"} else 2 if v=="post-max" else 3): name="initial-native-kill"
        elif v=="post-protected-hp": name="initial-native-kill"
        elif v in EXTERNAL|POWERLESS_VETO:
            name="foreign-native-restoration" if index==4 else "external-set-hp" if v.endswith("-set-hp") else "external-native-damage"
        elif v=="veto-source-retained" and index in (3,4): name="veto-native-kill" if index==3 else "foreign-native-restoration"
        elif v in {"late-phase","late-powerless","after-removed-reentry"}: name="domain-entry:"+v
        elif v in {"nested-command","nested-damage"} and index==3: name="nested-native-"+v.split("-")[1]
        else: name="move:EXPLODE_MOVE"
        names.append(name)
    return names

def snapshot_cursors(r):
    v=r["variant"]; total=len(r["nativeObservation"]["changes"])
    out={"initial":0,"final":total}
    if v!="ordinary": out["afterDeath"]={"on":1,"pre-max":1,"post-max":2,"post-protected-hp":4,"foreign-retention":1}.get(v,3)
    if r.get("beforeOpen") is not None:
        before=0 if v in {"on","toggle","ordinary","foreign-retention"} else 1 if v=="pre-max" else 2 if v=="post-max" else 4 if v in {"after-block","before-hp"}|EXTERNAL|POWERLESS_VETO else 5 if v in {"after-hp","overflow"} else 3
        out.update(beforeOpen=before,afterOpen=4 if v in {"late-phase","late-powerless","after-removed-reentry"} else before)
    if r.get("challengeState") is not None:
        out["challengeState"]=3 if v=="after-removed-reentry" else 7 if v=="off-veto-followup" else 4 if v in EXTERNAL else 5
    return out

def verify_native_protocol(r,need,domain_applied=True,keeper_nonending=False):
    v=r.get("variant"); native=r.get("nativeObservation"); initial=r.get("initial")
    if not isinstance(native,dict) or not isinstance(initial,dict): need(False,"native protocol dictionaries"); return
    changes=native.get("changes"); edges=native.get("stageEvents")
    if not isinstance(changes,list) or not isinstance(edges,list): need(False,"native event/stage streams"); return
    nodes={}; stack=[]; active_by_cursor={}; roots=[]; children=[]; last=-1
    for edge in edges:
        if not isinstance(edge,dict) or any(type(edge.get(k))is not int for k in ("id","parent","changeCursor")) or not isinstance(edge.get("name"),str): need(False,"typed stage edge"); return
        cursor=edge["changeCursor"]; identity=edge["id"]
        need(last<=cursor<=len(changes),"monotonic native stage cursors"); last=cursor
        if edge.get("kind")=="begin":
            need(identity==len(nodes)+1 and identity not in nodes and edge["parent"]==(stack[-1] if stack else 0),"unique nested native stage identity")
            if identity in nodes: return
            nodes[identity]=dict(edge); stack.append(identity)
            if edge["parent"]==0: roots.append(edge["name"])
            else:
                parent=nodes.get(edge["parent"],{}); children.append((edge["name"],parent.get("name")))
        elif edge.get("kind")=="end":
            need(bool(stack) and stack[-1]==identity and identity in nodes and all(edge[k]==nodes[identity][k] for k in ("parent","name")),"native stage completion identity")
            if not stack or stack[-1]!=identity: return
            nodes[identity]["endCursor"]=cursor
            stack.pop()
        else: need(False,"native stage edge kind"); return
        active_by_cursor[cursor]=stack[-1] if stack else 0
    need(not stack,"all native stage scopes closed")
    expected_roots,expected_children=stage_plan(v)
    need(roots==expected_roots and sorted(children)==sorted(expected_children),"exact real command/challenge stage tree")
    names=expected_change_stages(r); current=0
    for index,row in enumerate(changes):
        if index in active_by_cursor: current=active_by_cursor[index]
        need(isinstance(row,dict),"native change object")
        if not isinstance(row,dict): return
        need(type(row.get("index"))is int and row["index"]==index and type(row.get("stageId"))is int and row["stageId"]==current and current in nodes,"native change belongs to active stage")
        need(row.get("stage")==names[index] and current in nodes and nodes[current]["name"]==names[index],"native change matches the actual operation stage")
    # Every concrete state snapshot is anchored to the event prefix at its actual capture.
    fields={(role,field):key for role,field,key in (("boss","hp","bossHp"),("boss","maxHp","bossMaxHp"),("player","hp","playerHp"),("player","maxHp","playerMaxHp"),("player","block","playerBlock"),("osty","hp","petHp"),("osty","maxHp","petMaxHp"))}
    state={key:initial.get(key) for key in fields.values()}; prefixes=[dict(state)]
    for row in changes:
        key=fields.get((row.get("receiver"),row.get("field")))
        need(key is not None and type(row.get("before"))is int and type(row.get("after"))is int,"native change fields")
        if key is None: return
        need(state[key]==row["before"],"native event before value links to prior state")
        state[key]=row["after"]; prefixes.append(dict(state))
    for name,cursor in snapshot_cursors(r).items():
        value=r.get(name); need(isinstance(value,dict),"anchored snapshot: "+name)
        if not isinstance(value,dict): continue
        need(type(value.get("nativeEventCursor"))is int and value["nativeEventCursor"]==cursor,"exact snapshot event cursor: "+name)
        if cursor>=len(prefixes): need(False,"missing snapshot event prefix"); continue
        need(all(exact(value.get(key),expected) for key,expected in prefixes[cursor].items()),"snapshot equals its actual native event prefix: "+name)
        sid=value.get("nativeStageId"); expected_name="domain-entry:"+v if name in {"beforeOpen","afterOpen"} else "after-removed-reentry" if name=="challengeState" and v=="after-removed-reentry" else None
        need(type(sid)is int and (sid in nodes and nodes[sid]["name"]==expected_name if expected_name else sid==0),"snapshot native stage ownership: "+name)
        if type(sid)is int and sid in nodes:
            node=nodes[sid]
            need(node["changeCursor"]<=cursor<=node.get("endCursor",-1),"snapshot lies inside its real stage interval: "+name)
            if name=="beforeOpen": need(cursor==node["changeCursor"],"Domain before snapshot at stage entry")
            if name=="afterOpen": need(cursor==node.get("endCursor"),"Domain after snapshot at stage completion")
    if isinstance(r.get("beforeOpen"),dict) and isinstance(r.get("afterOpen"),dict):
        need(r["beforeOpen"].get("nativeStageId")==r["afterOpen"].get("nativeStageId"),"Domain snapshots share one actual operation")
    trace=r.get("trace"); markers={"initial-death-confirmed","terminal-death-confirmed","steam-terminal-cleanup-finished","uncancelled-native-veto-move-finished"}
    need(isinstance(trace,list) and [x for x in trace if isinstance(x,str) and x in markers]==expected_trace(v),"actual death/attempt/cleanup chronology")
    verify_history(r,need,nodes,keeper_nonending=keeper_nonending)
    verify_lease_metrics(r,need,nodes,domain_applied)


def verify_lease_metrics(r,need,nodes,domain_applied=True):
    v=r["variant"]; external=v in EXTERNAL; powerless=v in POWERLESS_VETO; follow=v=="off-veto-followup"
    no_terminal={"ordinary","on","pre-max","post-max","foreign-retention","pending-reset"}|POWERLESS_VETO
    ledger_keys=set("generation epoch currentEpoch ownerDeathActive ownerDeathAttempts unconfirmedDeathHold ownerHpCommandsActive terminalAttemptCount terminalDeathConfirmed sourceType monsterType initialDeaths terminalDeaths confirmed cancelled terminalRequested terminalStarted terminalKillCommitted retired deathDepth phaseDepth moveDepth attackDepth damageDepth writes attackCommands damageResults".split())
    for name in ("observation","beforeChallenge","afterChallenge"):
        o=r.get(name)
        if not isinstance(o,dict): continue
        need(o.keys()==ledger_keys,name+" complete owned ledger schema")
        final=name=="observation"; external_after=name=="afterChallenge" and external
        attempts=(2 if follow else 0 if external or v in no_terminal else 1) if final else int(follow and name=="afterChallenge")
        for key,value in (("ownerHpCommandsActive",0),("terminalAttemptCount",attempts),("terminalDeathConfirmed",v not in no_terminal if final else external_after)):
            need(exact(o.get(key),value),name+" native lease/attempt metric: "+key)
    foreign=r.get("foreignObservation"); windows=foreign.get("hookWindows") if isinstance(foreign,dict) else None
    if v not in WINDOWS:
        need(exact(windows,[]) and r.get("windowBefore") is None and r.get("windowAfter") is None,"no undeclared native hook window")
        return
    need(isinstance(windows,list) and len(windows)==1,"one real post-HP native await window")
    if isinstance(windows,list) and len(windows)==1:
        row=windows[0]; sid=row.get("stageId") if isinstance(row,dict) else None
        expected_name="external-set-hp" if v.endswith("-set-hp") else "external-native-damage"
        need(isinstance(row,dict) and row.get("point")==("AfterDamageGiven" if v.endswith("-after-damage") else "AfterCurrentHpChanged") and exact(row.get("bossHp"),0) and exact(row.get("deathEntries"),1) and exact(row.get("nativeEventCursor"),4) and type(sid)is int and sid in nodes and nodes[sid]["name"]==expected_name,"actual lethal hook precedes second native Kill entry")
    baseline=r.get("beforeChallenge")
    if not isinstance(baseline,dict): need(False,"hook window baseline ownership"); return
    for name in ("windowBefore","windowAfter"):
        expected=dict(baseline,ownerHpCommandsActive=1,cancelled=name=="windowAfter" and domain_applied,terminalRequested=name=="windowAfter" and domain_applied)
        need(exact(r.get(name),expected),name+" full independent owner state with ordinary damage untagged")

def verify_history(r,need,nodes,keeper_nonending=False):
    # Only the separately named keeper fixture may retain external lethal history.
    # CreatureCmd.Damage commits it after HP loss, BEFORE post-HP hooks and Kill.
    keeper_damage=keeper_nonending and r["variant"] in WINDOWS and not r["variant"].endswith("-set-hp")
    external_entry=dict(type="DamageReceivedEntry",actor="boss",dealer="player",cardSource=None,
        result=dict(receiver="boss",blocked=0,hp=999999999,overkill=0,killed=True,blockBroken=False,fullyBlocked=False))
    external_records=[]
    native=r["nativeObservation"]; history=native.get("historyEvidence")
    if not isinstance(history,dict): need(False,"actual native history evidence"); return
    start=history.get("initialCount"); final=history.get("finalCount"); records=history.get("captured"); actual=history.get("actualFinal")
    need(type(start)is int and type(final)is int and 0<=start<=final and history.get("initialReferencesIntact") is True,"native initial history references retained")
    if type(start)is not int or type(final)is not int or not isinstance(records,list) or not isinstance(actual,list): need(False,"native history streams"); return
    initial_refs=history.get("initialReferences"); final_refs=history.get("allFinalReferences")
    need(history.get("finalContentScope")=="related-move-attack-damage-subset;all-kinds-reference-inventory-only","history content proof scope")
    if not isinstance(initial_refs,list) or not isinstance(final_refs,list): need(False,"complete history reference inventory"); return
    need(len(initial_refs)==start and len(final_refs)==final and exact(initial_refs,final_refs[:start]),"history counts supported by complete reference inventory")
    seen=set()
    for index,row in enumerate(final_refs):
        if not isinstance(row,dict): need(False,"history reference row"); return
        identity=row.get("referenceId")
        need(exact(row.get("index"),index) and type(identity)is int and identity>0 and identity not in seen and isinstance(row.get("type"),str) and bool(row["type"]) and row.get("sameHistory") is True,"all-kind actual history reference/index/owner")
        if type(identity)is int: seen.add(identity)
    previous=start-1; previous_cursor=-1; previous_root=0; projected=[]; moves=[]; attacks=[]; damage=[]; kinds_by_root={}
    def root_id(sid):
        seen=set()
        while sid in nodes and nodes[sid]["parent"] and sid not in seen:
            seen.add(sid); sid=nodes[sid]["parent"]
        return sid
    for row in records:
        if not isinstance(row,dict) or type(row.get("index"))is not int: need(False,"typed actual history entry"); return
        index=row["index"]; data=row.get("data"); sid=row.get("stageId")
        need(previous<index<final and row.get("sameReferenceAtEnd") is True and row.get("sameHistoryAtEnd") is True,"native entry identity/index/history retained")
        previous=index; need(exact(data,row.get("finalData")),"actual history content retained to final snapshot")
        need(type(sid)is int and sid in nodes,"actual history native stage")
        if not isinstance(data,dict) or type(sid)is not int or sid not in nodes: need(False,"native history data"); return
        need(0<=index<len(final_refs) and exact(row.get("referenceId"),final_refs[index].get("referenceId")) and data.get("type")==final_refs[index].get("type"),"captured entry is the actual all-kind reference at its final index")
        projected.append(dict(index=index,data=data)); name=nodes[sid]["name"]
        kind=data.get("type"); kinds_by_root.setdefault(root_id(sid),[]).append(kind)
        if kind=="MonsterPerformedMoveEntry":
            need(data.get("actor")=="boss" and exact(data.get("targets"),["player"]) and name=="move:"+str(data.get("move")),"actual move entry actor/targets/action")
            moves.append(dict(id=data.get("move"),historyAdded=True))
        elif kind=="CreatureAttackedEntry":
            need(data.get("actor")=="boss" and name in {"move:EXPLODE_MOVE","move:STOMP_MOVE","nested-native-command"},"actual attack source stage")
            attacks.append(dict(historyAdded=True,results=data.get("results")))
        elif kind=="DamageReceivedEntry":
            if keeper_damage and name=="external-native-damage":
                need(exact(data,external_entry),"keeper external player-to-boss native lethal receipt")
                external_records.append(data)
            else:
                result=data.get("result"); need(isinstance(result,dict) and data.get("actor")==result.get("receiver") and data.get("dealer")=="boss" and data.get("cardSource") is None,"actual damage source/receiver/card")
                need(name in {"move:EXPLODE_MOVE","move:STOMP_MOVE","nested-native-command","nested-native-damage"},"actual damage stage")
                damage.append(dict(historyAdded=True,result=result))
        else: need(False,"actual entry concrete type")
        cursor=row.get("changeCursor"); expected_cursor=nodes[sid].get("endCursor",-1)
        if keeper_damage and kind=="DamageReceivedEntry" and name=="external-native-damage":
            expected_cursor=nodes[sid]["changeCursor"]+1
            change=native["changes"][expected_cursor-1] if 0<expected_cursor<=len(native["changes"]) else {}
            need(nodes[sid]["parent"]==0 and exact(change.get("stageId"),sid) and
                 change.get("receiver")=="boss" and change.get("field")=="hp" and
                 exact(change.get("before"),999999999) and exact(change.get("after"),0),
                 "keeper external history follows its command's actual lethal HP write")
        if kind!="MonsterPerformedMoveEntry" and name=="move:EXPLODE_MOVE":
            lethal=[change["index"] for change in native["changes"] if change.get("receiver")=="boss" and change.get("field")=="hp" and change.get("after")==0 and nodes[sid]["changeCursor"]<=change.get("index",-1)<expected_cursor]
            if lethal: expected_cursor=lethal[0]
        need(type(cursor)is int and cursor==expected_cursor,"actual history exact commit/terminal boundary")
        rid=root_id(sid)
        need(type(cursor)is int and cursor>=previous_cursor and rid>=previous_root,"history global cursor and actual root chronology")
        if type(cursor)is int: previous_cursor=cursor
        previous_root=rid
    for sid,node in nodes.items():
        if node["parent"]: continue
        name=node["name"]; m="MonsterPerformedMoveEntry"; d="DamageReceivedEntry"; a="CreatureAttackedEntry"
        expected=[m] if name in {"move:PRESSURIZE_MOVE","move:ABOUT_TO_BLOW_MOVE"} else [d,a,m] if name in {"move:EXPLODE_MOVE","move:STOMP_MOVE"} else []
        if keeper_damage and name=="external-native-damage": expected=[d]
        if name=="move:EXPLODE_MOVE":
            if r["variant"]=="nested-command": expected=[d,a,d,a,m]
            elif r["variant"] in {"nested-damage","overflow"}: expected=[d,d,a,m]
        need(kinds_by_root.get(sid,[])==expected,"native history damage/attack/move chronology")
    if r["variant"] in {"nested-command","nested-damage"}:
        # Bind to the producer's actual Begin/Dispose identities, not to root grouping,
        # cancellation flags, or a stage guessed from the observed damage amount.
        child_name="nested-native-"+r["variant"].split("-")[1]
        parents=[sid for sid,node in nodes.items() if node["name"]=="move:EXPLODE_MOVE"]
        children=[sid for sid,node in nodes.items() if node["name"]==child_name]
        need(len(parents)==len(children)==1,"one actual nested command and EXPLODE stage")
        if len(parents)==len(children)==1:
            parent,child=parents[0],children[0]
            need(nodes[child]["parent"]==parent,"nested command directly belongs to actual EXPLODE stage")
            nested_result=dict(receiver="player",blocked=2,hp=0,overkill=0,killed=False,blockBroken=False,fullyBlocked=True)
            parent_result=dict(receiver="player",blocked=0,hp=0,overkill=0,killed=False,blockBroken=False,fullyBlocked=False)
            def received(result): return dict(type="DamageReceivedEntry",actor="player",dealer="boss",cardSource=None,result=result)
            def attacked(result): return dict(type="CreatureAttackedEntry",actor="boss",results=[result])
            expected=[dict(stageId=child,data=received(nested_result))]
            if r["variant"]=="nested-command": expected.append(dict(stageId=child,data=attacked(nested_result)))
            expected.extend([dict(stageId=parent,data=received(parent_result)),dict(stageId=parent,data=attacked(parent_result)),
                dict(stageId=parent,data=dict(type="MonsterPerformedMoveEntry",actor="boss",move="EXPLODE_MOVE",targets=["player"]))])
            observed=[dict(stageId=row["stageId"],data=row["data"]) for row in records if root_id(row["stageId"])==parent]
            need(exact(observed,expected),"direct nested/parent history ownership and child-before-parent continuation")
    need(exact(projected,actual),"all relevant actual final entries captured, no input-argument substitute")
    for observed,field in ((moves,"completedMoves"),(attacks,"attacks"),(damage,"damage")): need(exact(observed,native.get(field)),"history-derived records: "+field)
    expected_external=[external_entry] if keeper_damage else []
    need(exact(external_records,expected_external),"exact keeper external captured history" if keeper_damage else "original external captured history remains absent")
    need(exact(history.get("externalPlayerToBoss"),expected_external),"keeper external history matches actual captured entry" if keeper_damage else "actual external lethal history absent under native ending branch")
    gates=history.get("externalHistoryGates"); external_damage=r["variant"] in EXTERNAL|POWERLESS_VETO and not r["variant"].endswith("-set-hp")
    need(isinstance(gates,list) and len(gates)==int(external_damage),"native external history branch observed")
    if external_damage and isinstance(gates,list) and len(gates)==1:
        gate=gates[0]; sid=gate.get("stageId") if isinstance(gate,dict) else None
        need(isinstance(gate,dict) and gate.get("isEnding") is (not keeper_damage) and type(gate.get("bossHp"))is int and gate["bossHp"]==0 and type(gate.get("changeCursor"))is int and gate["changeCursor"]==4 and type(sid)is int and sid in nodes and nodes[sid]["name"]=="external-native-damage","observed keeper non-ending history admission" if keeper_damage else "observed native lethal-history suppression, not fabricated returned result")
        if keeper_damage and type(sid)is int and sid in nodes:
            need(gate.get("changeCursor")==nodes[sid]["changeCursor"]+1 and
                 len([row for row in records if row.get("stageId")==sid and row.get("data",{}).get("type")=="DamageReceivedEntry" and row.get("changeCursor")==gate.get("changeCursor")])==1,
                 "keeper history gate and concrete entry share command/commit cursor")
