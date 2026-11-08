"""Independent frozen oracle for three controlled native GUI-choice cases, not OS input."""
from collections import Counter
from copy import deepcopy
from math import isfinite
import json
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX = '[Volibear] PREPARED_CHOICE_RESULT '
ACCEPTANCE = 'controlled-native-viewport-action-not-OS-input'
PREPARED_CHOICE_CASES = ('PC-C19-fixed-replay', 'PC-C19-dynamic-replay', 'PC-U39-native-search')


def _need(value):
    if not value:
        raise ValueError('choice evidence mismatch')


def _int(value, minimum=0):
    return type(value) is int and value >= minimum


def _eq(actual, expected):
    if type(expected) is dict:
        return type(actual) is dict and actual.keys() == expected.keys() and all(_eq(actual[k],v) for k,v in expected.items())
    if type(expected) is list:
        return type(actual) is list and len(actual)==len(expected) and all(_eq(a,b) for a,b in zip(actual,expected))
    if type(expected) in (int,float):
        return type(actual) in (int,float) and actual==expected
    return type(actual) is type(expected) and actual==expected


def _same(actual, expected):
    _need(_eq(actual,expected))


def validate_prepared_choice_result(r, token, variant):
    try:
        _validate(r,token,variant)
        return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        return False


def _validate(r, token, variant):
    _need(variant in PREPARED_CHOICE_CASES)
    keys = 'token variant scenario completed gameVersion gameCommit testMode acceptance character playerId enemyIds enemyTypes cards initial choice steps returned played payments beforeEffects requestCount'.split()
    _need(type(r) is dict and set(r)==set(keys))
    for key,value in dict(token=token,variant=variant,scenario='prepared-choice',completed=True,gameVersion=EXPECTED_GAME_VERSION,gameCommit=EXPECTED_GAME_COMMIT,
                          testMode=False,acceptance=ACCEPTANCE,character='VolibearCharacter',requestCount=1).items():
        _same(r[key],value)
    search=variant=='PC-U39-native-search'; dynamic=variant=='PC-C19-dynamic-replay'
    pid=r['playerId']; ids=r['enemyIds']
    _need(_int(pid) and type(ids) is list and len(ids)==3 and all(_int(i) for i in ids) and len(set(ids+[pid]))==4)
    _need(type(r['enemyTypes']) is list and len(r['enemyTypes'])==3)
    _need(Counter(r['enemyTypes']) in [Counter(['LeafSlimeS','TwigSlimeS',m]) for m in ('LeafSlimeM','TwigSlimeM')])
    expected_models={'selected':'VOLIBEAR_R07' if search else 'VOLIBEAR_U05' if dynamic else 'VOLIBEAR_B01',
                     'alternate':'VOLIBEAR_R09' if search else 'VOLIBEAR_B01' if dynamic else 'VOLIBEAR_U05',
                     'source':'VOLIBEAR_U39' if search else 'VOLIBEAR_C19'}
    if not search: expected_models.update(ineligible='VOLIBEAR_B02',replay='VOLIBEAR_U11')
    originals=[f'starter-{i}' for i in range(10)]
    _need(type(r['cards']) is list and len(r['cards'])==10+len(expected_models))
    lookup={}; native=set(); masters=set(); originals_models=[]
    for c in r['cards']:
        _need(type(c) is dict and set(c)==set('cardRef modelId combatCardIndex sameObject ownerId masterIndex masterModelId upgraded'.split()))
        ref=c['cardRef']; idx=c['combatCardIndex']
        _need(type(ref) is str and ref not in lookup and _int(idx) and idx not in native)
        _same(c['sameObject'],True);_same(c['ownerId'],pid);_same(c['upgraded'],False)
        if ref in originals:
            _need(_int(c['masterIndex']) and c['masterIndex']<10 and c['masterIndex'] not in masters)
            masters.add(c['masterIndex']); _same(c['masterModelId'],c['modelId']); originals_models.append(c['modelId'])
        else:
            _need(ref in expected_models);_same(c['modelId'],expected_models[ref]);_same(c['masterIndex'],-1);_same(c['masterModelId'],None)
        lookup[ref]=c;native.add(idx)
    _need(set(lookup)==set(originals)|set(expected_models))
    _same(Counter(originals_models),Counter(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']))
    seed=r['initial']['draw']
    _need(type(seed) is list and len(seed)==(12 if search else 10) and set(seed[:10])==set(originals))
    if search:_same(seed[10:],['selected','alternate'])
    initial=dict(round=1,turn=1,energy=10,hp=80,block=10 if dynamic else 0,enemyHp=[500]*3,
                 hand=['source'] if search else ['selected','alternate','ineligible','source'],draw=seed,
                 discard=[],play=[],exhaust=[],prepared=0,retain=False,enhanced=[],powers=[])
    _same(r['initial'],initial)
    choice=r['choice'];_need(type(choice) is dict and set(choice)==set('request uiType visible excluded exclusionClaim beforeWrongId rejected afterWrongId wrongBoundary inputs sync'.split()))
    _same(choice['exclusionClaim'],'native-filter-and-ui-exclusion-not-illegal-card-submit')
    request=choice['request'];_need(type(request) is dict and set(request)==set('actionId actionState choiceId source pile min max manualConfirmation available eligible ineligible synced'.split()))
    aid=request['actionId'];cid=request['choiceId'];_need(_int(aid) and _int(cid))
    pile='Draw' if search else 'Hand'
    def identity(ref, location):
        c=lookup[ref]
        return {key:c[key] for key in ['modelId','combatCardIndex','sameObject','ownerId','masterIndex']} | {'pile':location}
    available=seed if search else ['selected','alternate','ineligible']
    eligible=[c for c in available if c in ('selected','alternate')]
    ineligible=[c for c in available if c not in eligible]
    _same(request,dict(actionId=aid,actionState='GatheringPlayerChoice',choiceId=cid,source=identity('source','Play'),pile=pile,min=1,max=1,
                       manualConfirmation=False,available=[identity(c,pile) for c in available],eligible=[identity(c,pile) for c in eligible],
                       ineligible=[identity(c,pile) for c in ineligible],synced=[]))
    _same(choice['uiType'],'NCombatPileCardSelectScreen' if search else 'NPlayerHand')
    _need(type(choice['visible']) is list and len(choice['visible'])==2 and set(choice['visible'])==set(eligible))
    _same(choice['excluded'],[dict(cardRef=c,filterAccepted=False,holderCount=0 if search else 1,visibleHolderCount=0) for c in ineligible])
    pending=deepcopy(initial);pending['hand'].remove('source');pending['play']=['source'];pending['energy']=9 if search else 10
    if search:pending.update(block=4,powers=[dict(type='DomainPower',amount=1)])
    _same(choice['beforeWrongId'],pending);_same(choice['afterWrongId'],pending)
    _same(choice['rejected'],dict(kind='unreserved-future-choice-id-not-card-eligibility',requested=cid,attempted=cid+1,
                                 exception='InvalidOperationException',syncBefore=0,syncAfter=0,counterBefore=cid+1,counterAfter=cid+1,actionState='GatheringPlayerChoice'))
    boundary=choice['wrongBoundary']; h=boundary['historyBefore'];_need(_int(h,1))
    _same(boundary,dict(historyBefore=h,historyAfter=h,paymentsBefore=1,paymentsAfter=1,effectsBefore=1,effectsAfter=1,playedBefore=0,playedAfter=0))
    def input_row(control):return dict(api='Viewport.PushInput',action='ui_select',controlType=control,visible=True,focusMatched=True,pressed=[True,False])
    if search:
        _same(choice['inputs'],[input_row('NGridCardHolder')])
    else:
        _need(type(choice['inputs']) is list and len(choice['inputs'])==2)
        _same(choice['inputs'][0],input_row('NHandCardHolder'))
        pointer=choice['inputs'][1]; position=pointer['position']; size=pointer['viewportSize']; mode=pointer['focusModeBefore']
        _need(type(position) is list and type(size) is list and len(position)==len(size)==2)
        _need(all(type(p) in (int,float) and type(s) in (int,float) and isfinite(p) and isfinite(s) and 0<=p<s for p,s in zip(position,size)))
        _need(mode in ('None','Click','All'))
        _same(pointer,dict(api='Viewport.PushInput',action='viewport-left-pointer-confirm',controlType='NConfirmButton',
                           insideTree=True,visible=True,enabled=True,stableFrames=3,hoverMatched=True,nativeFocused=True,
                           focusModeBefore=mode,focusModeAfter=mode,position=position,viewportSize=size,pressed=[True,False]))
    _same(choice['sync'],[dict(choiceId=cid,actionId=aid,actionState='GatheringPlayerChoice',selected=[identity('selected',pile)],selectedSameObjects=[True])])
    steps=r['steps'];_need(type(steps) is list and len(steps)==(1 if search else 4))
    expected_before=[];expected_after=[]
    after=deepcopy(pending);after['play']=[];after['discard']=['source']
    if search:
        after['draw'].remove('selected');after['hand'].append('selected')
    else:after.update(prepared=3,retain=True,enhanced=[dict(cardRef='selected',prepared=3,retain=True)])
    expected_before.append(initial);expected_after.append(after)
    if not search:
        before=deepcopy(after);before['hand'].append('replay');expected_before.append(before)
        after=deepcopy(before);after['hand'].remove('replay');after['discard'].append('replay');after.update(energy=9,powers=[dict(type='NextAttackReplayPower',amount=1)])
        expected_after.append(after);expected_before.append(after)
        after=deepcopy(after);after['hand'].remove('selected');after['discard'].append('selected')
        after.update(energy=8,powers=[],prepared=0,enhanced=[dict(cardRef='selected',prepared=0,retain=True)],enemyHp=[480 if dynamic else 482,500,500])
        expected_after.append(after)
        returned=deepcopy(after);returned['discard'].remove('selected');returned['hand'].append('selected')
        _same(r['returned'],dict(operation='CardPileCmd.Add-same-instance-fixture-return',before=after,after=returned,cardRef='selected'))
        expected_before.append(returned)
        after=deepcopy(returned);after['hand'].remove('selected');after['discard'].append('selected');after.update(energy=7,enemyHp=[470 if dynamic else 476,500,500])
        expected_after.append(after)
        _same(r['played'],[dict(cardRef='selected',prepared=n,retain=True,enemyHp=hp) for n,hp in [(3,[480 if dynamic else 482,500,500]),(0,[470 if dynamic else 476,500,500])]])
    else:_same(r['returned'],None);_same(r['played'],[])
    roles=['source'] if search else ['source','replay','selected','selected']
    costs=[1] if search else [0,1,1,1]
    energies=[9] if search else [10,9,8,7]
    action_ids=[];play_ids=[];effects=[];payments=[];cursor=0
    for i,(step,role,cost,energy) in enumerate(zip(steps,roles,costs,energies)):
        _need(type(step) is dict and set(step)==set('cardRef before after action plays draws moves damage'.split()))
        _same(step['cardRef'],role);_same(step['before'],expected_before[i]);_same(step['after'],expected_after[i])
        a=step['action']; _need(type(a) is dict and _int(a['id']) and a['id'] not in action_ids);action_ids.append(a['id'])
        if i==0:_need(a['id']>=aid)
        _same({k:v for k,v in a.items() if k!='events'},
              dict(id=a['id'],state='Finished',target=ids[0] if role=='selected' else None,type='PlayCardAction',context='GameActionPlayerChoiceContext',
                   actionType='CombatPlayPhaseOnly',sameCard=True))
        _need(len(a['events'])==2 and a['events'][0]['name']=='before-executed' and a['events'][1]['name']=='after-finished'
              and a['events'][1]['id']==a['id'] and type(a['events'][0]['id']) is int and a['events'][0]['id']>=0
              and a['events'][0]['energy']==expected_before[i]['energy'] and a['events'][1]['energy']==energy)
        count=2 if i==2 else 1
        _same(step['plays'],[dict(cardRef=role,index=j,count=count) for j in range(count)])
        _same(step['draws'],[]);_same(step['moves'],[])
        amount=10 if dynamic else 9 if i==2 else 6
        _same(step['damage'],[dict(target=ids[0],cardRef='selected',hpLost=amount,blocked=0,props=8) for _ in range(count)] if role=='selected' else [])
        payments.append(dict(cardRef=role,amount=cost,energy=energy))
        play_id=r['beforeEffects'][cursor]['playId'];_need(_int(play_id,1) and play_id not in play_ids);play_ids.append(play_id)
        for j in range(count):
            effects.append(dict(cardRef=role,index=j,count=count,playId=play_id,autoPlay=False,energy=energy,spent=cost,
                                prepared=3 if i==2 else 0,retain=role=='selected',replay=0))
        cursor+=count
    _same(r['payments'],payments);_same(r['beforeEffects'],effects)


def prepared_choice_evidence(log, token, variant):
    results=[]
    for line in log.splitlines():
        if PREFIX not in line:continue
        try:r=json.loads(line.split(PREFIX,1)[1])
        except (ValueError,TypeError):continue
        if type(r) is dict and r.get('token')==token and r.get('variant')==variant:results.append(r)
    raw=results[0] if len(results)==1 else None
    return raw, raw is not None and validate_prepared_choice_result(raw,token,variant)
