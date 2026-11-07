"""Independent frozen U12 snapshot and native extra-turn oracle."""
from collections import Counter
from copy import deepcopy
import json
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')
PREFIX='[Volibear] PRIMAL_CONTRACT_RESULT '
PRIMAL_CASES=('U12-paid-snapshot','U12-native-extra-turn')
ACCEPTANCE='native-paid-snapshot-and-mayhem-extra-turn-not-OS-input'


def need(x):
    if not x:raise ValueError('primal evidence mismatch')
def eq(a,b):
    if type(b) is dict:return type(a) is dict and a.keys()==b.keys() and all(eq(a[k],v) for k,v in b.items())
    if type(b) is list:return type(a) is list and len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    if type(b) in (int,float):return type(a) in (int,float) and a==b
    return type(a) is type(b) and a==b
def same(a,b):need(eq(a,b))
def integer(x):return type(x) is int and x>=0


def primal_contract_evidence(log,token,variant):
    rows=[]
    for line in log.splitlines():
        if PREFIX not in line:continue
        try:r=json.loads(line.split(PREFIX,1)[1])
        except (ValueError,TypeError):continue
        if type(r) is dict and r.get('token')==token and r.get('variant')==variant:rows.append(r)
    raw=rows[0] if len(rows)==1 else None
    return raw,raw is not None and validate_primal_result(raw,token,variant)


def validate_primal_result(r,token,variant):
    try:_validate(r,token,variant);return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):return False


def _validate(r,token,variant):
    need(variant in PRIMAL_CASES and type(r) is dict and set(r)==set('token variant scenario completed gameVersion gameCommit testMode acceptance fixture character playerId enemyIds enemyTypes cards generated initial actions setups transitions final payments effects boundaries extraTurns autoPhases'.split()))
    for k,v in dict(token=token,variant=variant,scenario='primal-contract',completed=True,gameVersion=EXPECTED_GAME_VERSION,gameCommit=EXPECTED_GAME_COMMIT,testMode=False,
                    acceptance=ACCEPTANCE,character='VolibearCharacter',fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-and-deck-order-explicit').items():same(r[k],v)
    extra=variant=='U12-native-extra-turn';pid=r['playerId'];ids=r['enemyIds'];types=r['enemyTypes']
    need(integer(pid) and type(ids) is list and len(ids)==3 and all(integer(i) for i in ids) and len(set(ids+[pid]))==4)
    # Native SlimesWeak.GenerateMonsters: small A, medium, the other small (four exact layouts).
    need(types in [[a,m,b] for a,b in [('LeafSlimeS','TwigSlimeS'),('TwigSlimeS','LeafSlimeS')] for m in ['LeafSlimeM','TwigSlimeM']])
    leaf=types.index('LeafSlimeS');mid=1
    roles={'strength-a':'VOLIBEAR_R06','primal':'VOLIBEAR_U12'}
    if extra:
        roles.update(mayhem='MAYHEM',**{'extra-thunder':'VOLIBEAR_C24','expired-thunder':'VOLIBEAR_C24'})
        for label in ['turn2','extra','turn4']:
            for i in range(5):roles[f'{label}-padding-{i}']='VOLIBEAR_B02'
    else:roles.update({'strength-b':'VOLIBEAR_R06','native-thunder':'VOLIBEAR_C24','ordinary-attack':'VOLIBEAR_B01'})
    originals=[f'starter-{i}' for i in range(10)];lookup={};native=set();masters=set();models=[]
    need(type(r['cards']) is list and len(r['cards'])==10+len(roles))
    for c in r['cards']:
        need(type(c) is dict and set(c)==set('cardRef modelId upgraded combatCardIndex sameObject ownerId masterIndex masterModelId'.split()))
        ref=c['cardRef'];idx=c['combatCardIndex'];need(type(ref) is str and ref not in lookup and integer(idx) and idx not in native)
        same(c['sameObject'],True);same(c['ownerId'],pid);same(c['upgraded'],False)
        if ref in originals:
            need(integer(c['masterIndex']) and c['masterIndex']<10 and c['masterIndex'] not in masters);masters.add(c['masterIndex'])
            same(c['masterModelId'],c['modelId']);models.append(c['modelId'])
        else:need(ref in roles);same(c['modelId'],roles[ref]);same(c['masterIndex'],-1);same(c['masterModelId'],None)
        lookup[ref]=c;native.add(idx)
    need(set(lookup)==set(originals)|set(roles));need(Counter(models)==Counter(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']))
    medium_count=2 if types[mid]=='LeafSlimeM' else 1
    n=medium_count+1 if extra else 0;gen_refs=[f'generated-{i}' for i in range(n)]
    need(type(r['generated']) is list and len(r['generated'])==n)
    for i,g in enumerate(r['generated']):
        idx=g['combatCardIndex'];need(integer(idx) and idx not in native);native.add(idx)
        goop=i==medium_count
        same(g,dict(cardRef=gen_refs[i],modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=idx,sameObject=True,ownerId=pid,
                    masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=ids[leaf] if goop else ids[mid],sourceType='LeafSlimeS' if goop else types[mid],
                    sourceMove='GOOP_MOVE' if goop else 'STICKY_SHOT' if types[mid]=='LeafSlimeM' else 'STICKY_SHOT_MOVE',round=2 if goop else 1,turn=3 if goop else 1,side='Enemy'))
    seed=r['initial']['draw'];need(type(seed) is list and len(seed)==10 and set(seed)==set(originals))
    state=dict(round=1,turn=1,side='Player',phase='Play',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},
               relics=['HuntersHeart','PaelsEye'] if extra else ['HuntersHeart'],eyeUsed=False if extra else None,
               hand=[],draw=seed[:],discard=[],play=[],exhaust=[],removed=[])
    same(r['initial'],state)
    paid_all=[];effects_all=[];boundaries_all=[];extras_all=[];autos_all=[];play_ids=set();action_ids=set()
    def window():return dict(round=state['round'],turn=state['turn'],side=state['side'],strength=state['powers'].get('StrengthPower',0),
                             primal=state['powers'].get('PrimalThunderPower',0),unify=state['powers'].get('UnifyPower',0),eyeUsed=state['eyeUsed'])
    def history():return dict(plays=[],finished=[],exhausts=[],draws=[],moves=[],damage=[],generated=[])
    def draw(h,count,normal=False):
        take=state['draw'][:count];state['draw']=state['draw'][count:];state['hand']+=take
        h['draws'] += [dict(cardRef=c,fromHandDraw=normal) for c in take]
    def effect(ref,cost,auto):
        index=len(effects_all);play_id=r['effects'][index]['playId'];need(integer(play_id) and play_id>0 and play_id not in play_ids);play_ids.add(play_id)
        row=dict(cardRef=ref,index=0,count=1,autoPlay=auto,playId=play_id,spent=cost,energy=state['energy'],window=window());effects_all.append(row);return row
    def damage(h,target,amount,blocked=0,ref=None,props=8):h['damage'].append(dict(target=target,cardRef=ref,hpLost=amount,blocked=blocked,props=props))
    def lightning(h,amount,ref):
        for i in range(3):state['enemyHp'][i]-=amount;damage(h,ids[i],amount,ref=ref,props=4)
    def finish(h,ref,auto,exhaust=False):
        h['plays']=[dict(cardRef=ref,index=0,count=1,autoPlay=auto)];h['finished']=[dict(cardRef=ref,autoPlay=auto)]
        if exhaust:state['exhaust'].append(ref);h['exhausts'].append(ref)
        elif ref=='mayhem':state['removed'].append(ref)
        else:state['discard'].append(ref)
    action_specs=[('strength-a',2),('mayhem',2)] if extra else [('strength-a',2),('primal',1),('strength-b',2),('native-thunder',1),('ordinary-attack',1)]
    need(type(r['actions']) is list and len(r['actions'])==len(action_specs))
    for row,(ref,cost) in zip(r['actions'],action_specs):
        state['hand'].append(ref);before=deepcopy(state);aid=row['action']['id'];need(integer(aid) and aid not in action_ids);action_ids.add(aid)
        state['energy']-=cost;pay=dict(cardRef=ref,amount=cost,energy=state['energy'],window=window());paid_all.append(pay)
        fx=effect(ref,cost,False);state['hand'].remove(ref);h=history()
        if ref.startswith('strength-'):
            state['powers']['StrengthPower']=state['powers'].get('StrengthPower',0)+3
            state['powers']['UnifyPower']=state['powers'].get('UnifyPower',0)+3;state['block']+=10
        elif ref=='primal':state['powers']['PrimalThunderPower']=3;draw(h,1)
        elif ref=='mayhem':state['powers']['MayhemPower']=1
        elif ref=='native-thunder':lightning(h,15,ref);draw(h,1)
        else:state['enemyHp'][leaf]-=18;damage(h,ids[leaf],18,ref=ref)
        finish(h,ref,False,ref.startswith('strength-') or ref=='primal')
        same(row,dict(label=ref,cardRef=ref,before=before,after=state,
                      action=dict(id=aid,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context='GameActionPlayerChoiceContext',target=ids[leaf] if ref=='ordinary-attack' else None,sameCard=True,
                                  events=[dict(name='before-executed',state='Executing',id=aid,energy=before['energy']),dict(name='after-finished',state='Finished',id=aid,energy=state['energy'])]),
                      payments=[pay],effects=[fx],history=h))
    need(type(r['setups']) is list and len(r['setups'])==(3 if extra else 0));need(type(r['transitions']) is list and len(r['transitions'])==(3 if extra else 0))
    def boundary(side):
        before=window()
        if side=='Enemy':state['powers'].pop('PrimalThunderPower',None)
        row=dict(hook='Hook.AfterTurnEnd',side=side,participants=[pid] if side=='Player' else ids,before=before,after=window());boundaries_all.append(row);return row
    def monster(h,i,amount,move):
        blocked=min(amount,state['block']);state['block']-=blocked;state['hp']-=amount-blocked
        damage(h,pid,amount-blocked,blocked);h['moves'].append(dict(enemy=ids[i],move=move))
    if extra:
        for i,(label,ref,trans_label) in enumerate([('turn2','primal','natural-enemy-before-primal'),('extra','extra-thunder','paels-eye-extra-player-turn'),('turn4','expired-thunder','natural-enemy-expiry')]):
            before=deepcopy(state);padding=[f'{label}-padding-{j}' for j in range(5)];state['draw']=padding+[ref]+state['draw']
            same(r['setups'][i],dict(label=label,operation='CardPileCmd.Add-Top-five-padding-before-native-auto-target',target=ref,before=before,after=state))
            before=deepcopy(state);h=history();ends=[];extras=[]
            if i==1:
                h['exhausts']+=state['hand'];state['exhaust']+=state['hand']
            else:state['discard']+=state['hand']
            state['hand']=[];ends.append(boundary('Player'))
            if i==1:
                state['turn']=3;previous=window();state['eyeUsed']=True
                event=dict(hook='Hook.AfterTakingExtraTurn',playerId=pid,before=previous,after=window());extras.append(event);extras_all.append(event)
            else:
                state['side']='Enemy'
                for actor,kind in enumerate(types):
                    if kind=='LeafSlimeS' and i==2:
                        state['discard'].append(gen_refs[-1]);h['generated'].append(dict(cardRef=gen_refs[-1],creatorId=None))
                        h['moves'].append(dict(enemy=ids[actor],move='GOOP_MOVE'))
                    elif kind=='LeafSlimeS':monster(h,actor,3,'TACKLE_MOVE')
                    elif kind=='TwigSlimeS':monster(h,actor,4,'TACKLE_MOVE')
                    elif i==0:
                        state['discard']+=gen_refs[:medium_count];h['generated']=[dict(cardRef=c,creatorId=None) for c in gen_refs[:medium_count]]
                        h['moves'].append(dict(enemy=ids[actor],move='STICKY_SHOT' if kind=='LeafSlimeM' else 'STICKY_SHOT_MOVE'))
                    else:monster(h,actor,8 if kind=='LeafSlimeM' else 11,'CLUMP_SHOT' if kind=='LeafSlimeM' else 'POKEY_POUNCE_MOVE')
                ends.append(boundary('Enemy'));state['side']='Player';state['round']+=1;state['turn']+=1
            state.update(energy=3,block=0,phase='AutoPrePlay');draw(h,5,True);auto_before=deepcopy(state)
            ah=history();fx=effect(ref,0,True);same(state['draw'][0],ref);state['draw'].pop(0)
            if i==0:state['powers']['PrimalThunderPower']=3
            else:lightning(ah,12 if i==1 else 9,ref)
            draw(ah,1);finish(ah,ref,True,i==0)
            phase=dict(hook='MayhemPower.AfterAutoPrePlayPhaseEntered',context='HookPlayerChoiceContext',before=auto_before,after=deepcopy(state),history=ah,payments=[],effects=[fx]);autos_all.append(phase)
            for key in h:h[key]+=ah[key]
            state['phase']='Play'
            same(r['transitions'][i],dict(label=trans_label,before=before,after=state,history=h,payments=[],effects=[fx],boundaries=ends,extraTurns=extras,autoPhases=[phase]))
    same(r['final'],state);same(r['payments'],paid_all);same(r['effects'],effects_all);same(r['boundaries'],boundaries_all);same(r['extraTurns'],extras_all);same(r['autoPhases'],autos_all)
