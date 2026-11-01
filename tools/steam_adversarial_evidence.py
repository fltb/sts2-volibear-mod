"""Strict independently specified contracts for explicitly instrumented native challenges."""
from steam_native_protocol import WINDOWS, EXTERNAL, POWERLESS_VETO

EXTRAS = WINDOWS | {"off-veto-followup"} | {"nested-command", "nested-damage", "after-removed-reentry", "veto-source-retained", "veto-powerless", "external-powerless", "foreign-retention", "pending-reset"}
LABELS = {
 "nested-command": "real-untagged-native-invocation-inside-tagged-Damage", "nested-damage": "real-untagged-native-invocation-inside-tagged-Damage",
 "after-removed-reentry": "instrumented-async-native-AfterRemoved-completion-boundary-Domain-reapply",
 "veto-source-retained": "foreign-final-vote-native-restoration",
 "veto-powerless": "real-lethal-Damage-before-Kill;native-BeforeDeath-direct-PowerCmd.Apply;foreign-final-vote-native-restoration",
 "external-powerless": "real-lethal-Damage-before-Kill;native-BeforeDeath-direct-PowerCmd.Apply;native-death-confirmation",
 "foreign-retention": "foreign-final-native-removal-vote",
 "pending-reset": "adapter-only-reset-at-native-Damage-await-not-full-combat-reset-not-Godot-boxing-proof",
}

LABELS.update({v: "real-lethal-"+("SetCurrentHp" if v.endswith("-set-hp") else "Damage")+";native-"+("AfterDamageGiven" if v.endswith("-after-damage") else "AfterCurrentHpChanged")+"-completion-await-before-Kill;direct-PowerCmd.Apply;labelled-final-vote" for v in WINDOWS})
LABELS["off-veto-followup"] = "no-Domain;real-EXPLODE-foreign-veto-native-restoration;real-native-self-followup-EXPLODE"

def exact(value, expected):
    if type(value) is not type(expected): return False
    if isinstance(expected, dict): return value.keys() == expected.keys() and all(exact(value[k], v) for k, v in expected.items())
    if isinstance(expected, list): return len(value) == len(expected) and all(exact(a,b) for a,b in zip(value, expected))
    return value == expected


def receipts(actual, expected):
    return isinstance(actual,list) and len(actual)==len(expected) and all(isinstance(a,dict) and a.keys()==b.keys() and
        all(type(a.get(k)) in (int,float) and a[k]==b[k] for k in ("before","after","delta")) and a.get("part")==b["part"] and a.get("receiver")==b["receiver"] for a,b in zip(actual,expected))

def application_fixture(r, need, base, keeper):
    f = r.get('applicationFixture')
    need(isinstance(f, dict), 'explicit independent application fixture')
    if not isinstance(f, dict): return
    need(f.get('kind') == ('native-primary-keeper' if keeper else 'sole-primary-ending-negative'), 'application fixture kind')
    for key in ('keeperAddCalls', 'keeperAddCompleted', 'keeperCleanupCalls', 'keeperDied'):
        need(exact(f.get(key), int(keeper)), 'native keeper count: ' + key)
    veto = keeper and base.startswith('veto-')
    for key in ('bossCleanupCalls', 'bossCleanupDeaths'):
        need(exact(f.get(key), int(veto)), 'separate native boss cleanup: ' + key)
    need(f.get('beforeCleanupInProgress') is True, 'no premature victory before independent cleanup')
    initial = f.get('keeperAfterAdd')
    for name in ('keeperAfterAdd', 'keeperBeforeApply', 'keeperAfterApply', 'keeperAfterAction'):
        state = f.get(name); need(isinstance(state, dict), 'keeper snapshot: ' + name)
        if not isinstance(state, dict): continue
        need(state.get('present') is keeper and state.get('minion') is False and state.get('osty') is False, 'keeper is not a minion/pet: ' + name)
        if keeper:
            need(state.get('model') == 'Stabbot' and type(state.get('combatId')) is int and state['combatId'] != f.get('bossCombatId'), 'actual distinct native keeper identity: ' + name)
            need(type(state.get('hp')) is int and state['hp'] > 0 and all(state.get(k) is True for k in ('alive','primary','attached','listed','nodePresent')), 'active primary keeper: ' + name)
            need(exact(state, initial), 'same unchanged keeper across measured window: ' + name)
        else:
            need(all(state.get(k) is False for k in ('alive','primary','attached','listed','nodePresent')) and all(state.get(k) is None for k in ('combatId','model','hp')), 'sole-boss negative has no hidden keeper: ' + name)
    apply = f.get('applyEvidence'); need(isinstance(apply, dict), 'native Apply/AfterApplied observation')
    if isinstance(apply, dict):
        expected = dict(api='PowerCmd.Apply<DomainPower>', nativeIsEndingBefore=not keeper, activePrimaryBefore=int(keeper),
                        returnedPower='DomainPower' if keeper else None, returnedMatchesOwnerPower=keeper,
                        afterAppliedCalls=int(keeper), afterAppliedInstanceMatches=keeper, afterAppliedTaskCompleted=keeper, domainAfter=3 if keeper else 0)
        need(exact(apply, expected), 'real Apply return/AfterApplied original Task and native ending precondition')
    if keeper:
        need(exact(f.get('keeperBeforeCleanup'), initial), 'keeper survives source cleanup and still supplies primary')
        retired = dict(r['final'], bossHp=0, bossAlive=False, attached=False, listed=False, nodePresent=False,
                       sourcePresent=False, nextMove=None, nativeEventCursor=0, nativeStageId=0)
        need(exact(f.get('bossAfterCleanup'), retired), 'independent actual boss snapshot after native cleanup, before keeper death')
        end = f.get('keeperAfterCleanup'); need(isinstance(end, dict), 'native keeper cleanup snapshot')
        if isinstance(end, dict):
            need(end.get('present') is True and end.get('hp') == 0 and type(end.get('hp')) is int and all(end.get(k) is False for k in ('alive','attached','listed','nodePresent')), 'keeper dies/removes only in separate native cleanup')
        source = f.get('sourceAfterCleanup'); need(isinstance(source, dict), 'source retirement after independent cleanup')
        if isinstance(source, dict) and isinstance(r.get('observation'),dict):
            expected = dict(r['observation'], retired=True, terminalDeaths=1, terminalStarted=True, terminalDeathConfirmed=True,
                            unconfirmedDeathHold=False, ownerDeathAttempts=3 if veto else 2)
            need(exact(source, expected), 'complete source ledger retires through separate native death, no new effect or authority')
        trace = f.get('cleanupTrace'); need(isinstance(trace,list) and all(isinstance(x,str) for x in trace), 'separate cleanup trace')
        if isinstance(trace,list): need(trace.count('terminal-death-confirmed') == int(veto), 'veto native terminal death occurs only in separate cleanup')
    else:
        need(all(f.get(k) is None for k in ('keeperBeforeCleanup','keeperAfterCleanup','sourceAfterCleanup','bossAfterCleanup')) and exact(f.get('cleanupTrace'),[]), 'negative has no hidden rescue or cleanup action')


def foreign_contract(r, need, attempts, veto=False, retention=False):
    foreign = r.get("foreignObservation")
    need(isinstance(foreign, dict), "independent native foreign-vote observations")
    if not isinstance(foreign, dict): return
    for field, count in (("beforeDeathCalls", attempts), ("vetoes", int(veto)), ("restoreCalls", int(veto)), ("restorations", int(veto))):
        need(exact(foreign.get(field), count), "foreign actual count: " + field)
    need(foreign.get("instrumentation") == "foreign-final-hook-vote-and-native-AfterPreventingDeath-HP-restoration-not-mock-power", "foreign fixture scope")
    need(exact(foreign.get("nativeRecursions"), [0]*attempts), "actual native entries, no native recursive retry")
    votes = [dict(native=True, final=not (veto and index == 1), injected=veto and index == 1) for index in range(attempts)]
    need(exact(foreign.get("votes"), votes), "native and final death votes")
    count = foreign.get("retentionVotes")
    need(type(count) is int and (count >= 3 if retention else count == 0), "foreign final retention vote count")


def verify_sole_audio_tail(r, need):
    native=r['nativeObservation']; tail=r.get('soleAudioTail')
    fields={'scope','nodeId','exitNodeId','treeExited','originalAnimationCompleted','finalLoopRegistered','events','worldAtExit','nativeAtExit'}
    need(isinstance(tail,dict) and tail.keys()==fields, 'complete separately measured sole audio tail')
    if not isinstance(tail,dict) or tail.keys()!=fields: return
    need(tail['scope']=='sole-native-node-exit-after-action-before-wincheck', 'sole tail before explicit victory/room cleanup')
    need(type(tail['nodeId'])is int and tail['nodeId']>0 and exact(tail['exitNodeId'],tail['nodeId']), 'same original removed native node exits')
    need(tail['treeExited'] is True and tail['originalAnimationCompleted'] is True and tail['finalLoopRegistered'] is False, 'original animation and natural TreeExited complete with cleared loop')
    need(exact(tail['events'],['exit-enter','effective-stop-in-exit','exit-body-finished','tree-exited']), 'native exit owns exactly one effective stop, not premature or manual stop')
    need(exact(tail['worldAtExit'],r['final']), 'sole tail preserves action-end world and event prefix')
    need(native.get('initialAmbientRegistered') is True and native.get('finalAmbientRegistered') is True and exact(native.get('stops'),[]) and exact(native.get('ambientParameterCalls'),[1,3,1]), 'sole action-end audio remains the original unfinished snapshot')
    expected=dict(native,finalAmbientRegistered=False,stops=[dict(before=True,after=False,nodeStillInRoom=False)],ambientParameterCalls=[1,3,1,2])
    need(exact(tail['nativeAtExit'],expected), 'sole tail only appends native exit audio; original history/reference/property prefixes unchanged')


def adversarial(r, need, errors, snapshot_fields, scope, fixture_variant=None, domain_applied=True, keeper=False, sole_ending=False):
    v = fixture_variant or r["variant"]; i = r.get("initial")
    need(isinstance(i, dict) and snapshot_fields <= i.keys(), "complete initial snapshot")
    if not isinstance(i, dict) or not snapshot_fields <= i.keys(): return {"errors": errors, "observation": r}
    need(all(type(i[k]) is int and i[k] >= 0 for k in ("bossHp", "bossMaxHp", "playerHp", "playerMaxHp", "playerBlock", "domain")), "initial native integer fields")
    if not all(type(i[k]) is int for k in ("bossHp", "bossMaxHp", "playerHp", "playerMaxHp", "playerBlock", "domain")): return {"errors": errors, "observation": r}
    need(0 < i["bossHp"] == i["bossMaxHp"] < 999999999 and i["playerHp"] == i["playerMaxHp"] > 15, "initial natural full HP")
    need(all(i[k] is True for k in ("bossAlive", "attached", "listed", "nodePresent", "sourcePresent")) and i["nextMove"] == "STOMP_MOVE" and i["hpDisplay"] == "Normal", "fresh native pressurize")
    need(i["domain"] == 0 and i["playerBlock"] == 6 and all(i[k] is None for k in ("petType", "petHp", "petMaxHp")), "clean challenge fixture")
    nested = v in {"nested-command", "nested-damage"}; reset = v == "pending-reset"; retention = v == "foreign-retention"
    external = v in EXTERNAL; follow = v == "off-veto-followup"
    powerless = v in POWERLESS_VETO; veto = powerless or v == "veto-source-retained" or follow; reentry = v == "after-removed-reentry"
    ended = not (reset or retention or powerless); full = nested or reset or v == "veto-source-retained" or follow
    deaths = 2 if ended else 1; attempts = deaths + int(veto)
    opens = 2 if reentry else 1 if nested or powerless or external or retention else 0
    def field(name, expected): need(exact(r.get(name), expected), "challenge field: " + name)
    for name, expected in (("died", deaths), ("sourceRemoved", 1), ("opens", opens), ("resets", int(reset)), ("nestedCalls", int(nested)), ("removalReentries", int(reentry)),
        ("explicitWinCheck", ended or keeper), ("checkResult", ended or keeper), ("victories", int(ended or keeper)), ("endings", int(ended or keeper)), ("inProgress", not (ended or keeper)), ("reentry", "ABOUT_TO_BLOW_MOVE" if reentry else None)):
        field(name, expected)
    field("challengeInstrumentation", LABELS[v] + (";native-primary-keeper" if keeper else ";sole-primary-ending-negative" if not domain_applied else "")); field("boundary", "before-block" if nested or reset else "none"); field("boundaryHits", int(nested or reset))
    field("boundaryMode", "instrumented-domain-open-at-native-command-or-hook-completion" if nested or reset else "none")
    protected = dict(i, bossHp=999999999, bossMaxHp=999999999, nextMove="ABOUT_TO_BLOW_MOVE", hpDisplay="InfiniteWithoutNumbers")
    powerless_state = dict(protected, sourcePresent=False, nextMove="EXPLODE_MOVE")
    retired = dict(protected, bossHp=0, bossAlive=False, attached=False, listed=False, nodePresent=False, sourcePresent=False, nextMove=None)
    retained = dict(i, bossHp=0, bossAlive=False, sourcePresent=False, domain=3)
    final = dict(retained if retention else powerless_state if reset or powerless else retired)
    domain = 3 if domain_applied else 0
    final.update(domain=domain if nested or powerless or external or retention else 0, playerBlock=4 if nested else 0 if v == "veto-source-retained" or follow else 6,
        playerHp=i["playerHp"] - (24 if follow else 9 if v == "veto-source-retained" else 0))
    def stage(name, expected):
        actual = r.get(name)
        if expected is None: need(actual is None, name + " absent"); return
        need(isinstance(actual, dict) and all(exact(actual.get(k), expected[k]) for k in snapshot_fields), name + " fixed independent stage")
    stage("final", final); stage("afterDeath", retained if retention else protected)
    before = (dict(i) if retention else dict(protected) if reentry else dict(powerless_state, bossHp=0, bossAlive=False) if powerless or external else dict(powerless_state) if nested else None)
    stage("beforeOpen", before); stage("afterOpen", dict(retired, domain=3) if reentry else dict(before, domain=domain) if before is not None else None)
    stage("challengeState", dict(powerless_state,playerBlock=0,playerHp=i["playerHp"]-9) if follow else dict(protected, sourcePresent=False, domain=3) if reentry else dict(retired, domain=domain) if external else dict(powerless_state, domain=3) if powerless else protected if veto else None)
    moves = ["PRESSURIZE_MOVE"] + (["ABOUT_TO_BLOW_MOVE", "EXPLODE_MOVE"] if full else ["ABOUT_TO_BLOW_MOVE"] if powerless or external else [])
    if follow: moves.append("EXPLODE_MOVE")
    field("attemptedMoves", moves)
    o = r.get("observation"); native = r.get("nativeObservation")
    need(isinstance(o, dict) and isinstance(native, dict), "episode and independent native observation")
    if not isinstance(o, dict) or not isinstance(native, dict): return {"errors": errors, "observation": r}
    need(o.get("sourceType") == "SteamEruptionPower" and o.get("monsterType") == "WaterfallGiant", "owned source identities")
    need(type(o.get("generation")) is int and o["generation"] > 0 and type(o.get("epoch")) is int, "generation/epoch integer")
    if type(o.get("epoch")) is not int: return {"errors": errors, "observation": r}
    for key, expected in (("currentEpoch", o["epoch"] + int(reset)), ("initialDeaths",1), ("terminalDeaths",deaths-1), ("confirmed",True),
        ("cancelled", domain_applied and (nested or retention or powerless or external or reentry)), ("retired",ended), ("terminalRequested",not reset), ("terminalStarted",ended),
        ("terminalKillCommitted",ended and not external), ("ownerDeathActive",0), ("ownerDeathAttempts",attempts), ("unconfirmedDeathHold",powerless)):
        need(exact(o.get(key),expected), "episode state: " + key)
    for key in ("deathDepth", "phaseDepth", "moveDepth", "attackDepth", "damageDepth"): need(exact(o.get(key),0), "closed depth: " + key)
    for name in ("beforeChallenge", "afterChallenge"):
        value = r.get(name)
        if not (veto or reset or reentry or external): need(value is None, name + " absent"); continue
        need(isinstance(value, dict), name + " ownership snapshot")
        if not isinstance(value, dict): continue
        for key in ("generation", "epoch", "initialDeaths", "sourceType", "monsterType"):
            need(exact(value.get(key),o[key]), name + " stable confirmed ownership: " + key)
        observed_external = external and name == "afterChallenge"
        need(value.get("confirmed") is True and value.get("retired") is observed_external and exact(value.get("terminalDeaths"),int(observed_external)), name + " actual terminal Died only")
        need(exact(value.get("currentEpoch"),o["epoch"] + int(reset and name == "afterChallenge")), name + " reset epoch")
        need(value.get("unconfirmedDeathHold") is (veto and name == "afterChallenge"), name + " veto retention hold")
        need(value.get("terminalStarted") is (reentry or observed_external), name + " cleanup ancestry")
        after_entry = name == "afterChallenge" and (powerless or external)
        need(value.get("cancelled") is (domain_applied and (reentry or after_entry)) and value.get("terminalRequested") is (reentry or after_entry), name + " exact cancellation stage")
        for key, expected in (("ownerDeathActive",0),("ownerDeathAttempts",2 if name == "afterChallenge" and (veto or external) else 1),
                              ("deathDepth",0),("phaseDepth",0),("moveDepth",int(reset)),("attackDepth",int(reset)),("damageDepth",int(reset)),("attackCommands",int(reset or follow and name == "afterChallenge"))):
            need(exact(value.get(key),expected), name + " exact native scope: " + key)
        first_result=[dict(receiver="player",blocked=6,hp=9,overkill=0,killed=False,blockBroken=True,fullyBlocked=False)] if follow and name=="afterChallenge" else []
        need(exact(value.get("damageResults"),first_result), name + " exact committed native results")
        need(value.get("terminalKillCommitted") is False, name + " no fabricated adapter terminal kill")
        expected_writes=[dict(part="protected-max-hp",receiver="boss",before=i["bossMaxHp"],after=999999999,delta=999999999-i["bossMaxHp"]),
                         dict(part="protected-current-hp",receiver="boss",before=0,after=999999999,delta=999999999)]
        if follow and name=="afterChallenge": expected_writes += [dict(part="block:1",receiver="player",before=6,after=0,delta=-6),dict(part="primary-hp:1",receiver="player",before=i["playerHp"],after=i["playerHp"]-9,delta=-9)]
        need(receipts(value.get("writes"),expected_writes), name + " exact ordered source write receipts")
    def result(blocked=0, hp=0, fully=False): return dict(receiver="player",blocked=blocked,hp=hp,overkill=0,killed=False,blockBroken=blocked==6,fullyBlocked=fully)
    parent = result(6,9) if v == "veto-source-retained" or follow else result()
    own_results = ([parent,result(0,15)] if follow else [parent]) if full else []
    need(exact(o.get("attackCommands"),2 if follow else int(full)) and exact(o.get("damageResults"),own_results), "only genuine tagged command/result")
    writes = []
    def write(part,receiver,a,b): writes.append(dict(part=part,receiver=receiver,before=a,after=b,delta=b-a))
    if not retention:
        write("protected-max-hp","boss",i["bossMaxHp"],999999999); write("protected-current-hp","boss",0,999999999)
    if full:
        write("block:1","player",4 if nested else 6,4 if nested else 0 if veto else 6)
        write("primary-hp:1","player",i["playerHp"],i["playerHp"]-9 if follow else final["playerHp"])
        if follow:
            write("block:1","player",0,0); write("primary-hp:1","player",i["playerHp"]-9,i["playerHp"]-24)
    actual_writes = o.get("writes")
    need(isinstance(actual_writes,list) and len(actual_writes)==len(writes) and all(isinstance(a,dict) and a.keys()==b.keys() and
        all(type(a.get(k)) in (int,float) and a[k]==b[k] for k in ("before","after","delta")) and a.get("part")==b["part"] and a.get("receiver")==b["receiver"] for a,b in zip(actual_writes,writes)), "genuine parent write receipts, never attribute nested untagged writes")
    need(exact(native.get("externalDamageResults"),[dict(receiver="boss",blocked=0,hp=999999999,overkill=0,killed=True,blockBroken=False,fullyBlocked=False)] if (powerless or external) and not v.endswith("-set-hp") else []), "real lethal external Damage returned result, distinct from actual Died")
    need(exact(native.get("completedMoves"),[dict(id=move,historyAdded=True) for move in moves]), "native completed move history")
    damage = ([result(2,0,True)] if nested else []) + own_results
    attacks = ([result(2,0,True)] if v == "nested-command" else []) + own_results
    need(exact(native.get("damage"),[dict(historyAdded=True,result=value) for value in damage]), "independent native damage history")
    need(exact(native.get("attacks"),[dict(historyAdded=True,results=[value]) for value in attacks]), "independent native command history")
    changes = []
    def change(receiver,field,a,b): changes.append(dict(receiver=receiver,field=field,before=a,after=b))
    change("boss","hp",i["bossHp"],0)
    if not retention: change("boss","maxHp",i["bossMaxHp"],999999999); change("boss","hp",0,999999999)
    if follow:
        change("player","block",6,0); change("player","hp",i["playerHp"],i["playerHp"]-9)
        change("boss","hp",999999999,0); change("boss","hp",0,999999999)
        change("player","hp",i["playerHp"]-9,i["playerHp"]-24)
    elif veto: change("boss","hp",999999999,0); change("boss","hp",0,999999999)
    if nested: change("player","block",6,4)
    if v == "veto-source-retained": change("player","block",6,0); change("player","hp",i["playerHp"],i["playerHp"]-9)
    if ended: change("boss","hp",999999999,0)
    actual = native.get("changes")
    need(isinstance(actual,list), "native actual property events")
    if isinstance(actual,list):
        need(all(isinstance(row,dict) and isinstance(row.get("stage"),str) for row in actual), "event stage labels")
        need(exact([{k:row.get(k) for k in ("receiver","field","before","after")} if isinstance(row,dict) else None for row in actual],changes), "native ordered commits and explicit fixture restoration, no refund/replay")
    for key in ("afterRemovedStarted", "afterRemovedCompleted"): need(exact(native.get(key),1), "one real source removal: " + key)
    need(native.get("audioScope") == "native-loop-registration-and-parameter-calls-not-listening", "audio observation scope")
    if sole_ending:
        verify_sole_audio_tail(r,need)
    else:
        need(r.get('soleAudioTail') is None, 'non-sole case forbids tail substitution')
        need(native.get("initialAmbientRegistered") is True and native.get("finalAmbientRegistered") is False, "real ambient registry lifecycle")
        stops = native.get("stops")
        need(isinstance(stops,list), "native loop stops")
        if isinstance(stops,list):
            need(all(isinstance(stop,dict) and type(stop.get("before")) is bool and stop.get("after") is False and stop.get("nodeStillInRoom") is True for stop in stops), "node-backed stop, no replay")
            need(sum(stop.get("before") is True for stop in stops if isinstance(stop,dict)) == 1, "one effective loop stop")
    music = [1,2,1,5,5,5,5] if follow else [1,5] if retention else [1,2,1] if reset else [1,2,1,5] if powerless or external else [1,2,5,5] if reentry else [1,2,1,5,5]
    ambient = [1,2] if retention else [1,3,2] if reentry else [1,3,1,2]
    need(native.get("musicParameterCalls") == music and all(type(x) in (int,float) for x in native.get("musicParameterCalls",[])), "native music lifecycle")
    if not sole_ending:
        need(native.get("ambientParameterCalls") == ambient and all(type(x) in (int,float) for x in native.get("ambientParameterCalls",[])), "native ambient lifecycle")
    trace = r.get("trace")
    need(isinstance(trace,list) and all(isinstance(x,str) for x in trace), "observed source trace")
    if isinstance(trace,list):
        need(trace.count("initial-death-confirmed")==1 and trace.count("terminal-death-confirmed")==deaths-1 and trace.count("steam-terminal-cleanup-finished")==(2 if follow else int(ended and not external)), "actual source trace contribution counts")
    foreign_contract(r,need,attempts,veto,retention)
    return {"errors":errors,"observation":r,"scope":scope,"exit_and_leak_baseline_gate":"runner-required"}
