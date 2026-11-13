"""Frozen native-payment oracle. No production card implementation is imported."""
from collections import Counter
from copy import deepcopy
import json
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX='[Volibear] COUPON_CONTRACT_RESULT '
ACCEPTANCE='native-action-queue-payment-not-OS-input'
ENGAGE=('B04','C04','C10','C11','U28','U35','R09')
COUPON_CASES=tuple('CP-elig-'+c for c in ENGAGE)+('CP-max-preserve','CP-zero-consume','CP-expiry','CP-beast-attack','CP-beast-skill')
COST={'C25':1,'U14':0,'B02':1,'B04':1,'C04':1,'C10':2,'C11':1,'U28':2,'U35':1,'R09':2,'C01':0,'R29':3,'T01':1,'T02':1}
ATTACK={'B04','C04','C10','C01','T01'}


def need(x):
    if not x:raise ValueError('coupon evidence mismatch')


def eq(a,b):
    if type(b) is dict:return type(a) is dict and a.keys()==b.keys() and all(eq(a[k],v) for k,v in b.items())
    if type(b) is list:return type(a) is list and len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    if type(b) in (int,float):return type(a) in (int,float) and a==b
    return type(a) is type(b) and a==b


def same(a,b):need(eq(a,b))
def integer(x):return type(x) is int and x>=0


def profile(case):
    rows=[('attack-coupon','C25',False,'attack-coupon')]
    if case=='CP-max-preserve':rows.append(('attack-coupon-upgrade','C25',True,'attack-coupon-upgrade'))
    rows.append(('engage-coupon','U14',False,'engage-coupon'))
    if case.startswith('CP-elig-'):rows.append(('target',case[8:],False,'target'))
    elif case=='CP-max-preserve':rows += [('engage-coupon-upgrade','U14',True,'engage-coupon-upgrade'),('noneligible','B02',False,'noneligible'),('target','C10',False,'invalid-target'),('target','C10',False,'target')]
    elif case=='CP-zero-consume':rows += [('zero-attack','C01',False,'zero-attack'),('target','B04',False,'target')]
    elif case=='CP-expiry':rows.append(('target','C10',False,'target'))
    else:rows += [('convert','R29',False,'convert'),('target-beast','T01' if case=='CP-beast-attack' else 'T02',False,'target')]
    return rows


def coupon_contract_evidence(log,token,variant):
    rows=[]
    for line in log.splitlines():
        if PREFIX not in line:continue
        try:r=json.loads(line.split(PREFIX,1)[1])
        except (ValueError,TypeError):continue
        if type(r) is dict and r.get('token')==token and r.get('variant')==variant:rows.append(r)
    raw=rows[0] if len(rows)==1 else None
    return raw,raw is not None and validate_coupon_result(raw,token,variant)


def validate_coupon_result(r,token,variant):
    try:_validate(r,token,variant);return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):return False


def _validate(r,token,variant):
    need(variant in COUPON_CASES and type(r) is dict and set(r)==set('token variant scenario completed gameVersion gameCommit testMode acceptance character playerId enemyIds enemyTypes fixture cards generated conversions initial steps transition'.split()))
    for k,v in dict(token=token,variant=variant,scenario='coupon-contract',completed=True,gameVersion=EXPECTED_GAME_VERSION,gameCommit=EXPECTED_GAME_COMMIT,testMode=False,
                    acceptance=ACCEPTANCE,character='VolibearCharacter',fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-explicit').items():same(r[k],v)
    pid=r['playerId'];ids=r['enemyIds'];types=r['enemyTypes']
    need(integer(pid) and type(ids) is list and len(ids)==3 and all(integer(i) for i in ids) and len(set(ids+[pid]))==4)
    # Native SlimesWeak.GenerateMonsters: small A, medium, the other small.
    need(types in [[a,m,b] for a,b in [('LeafSlimeS','TwigSlimeS'),('TwigSlimeS','LeafSlimeS')] for m in ['LeafSlimeM','TwigSlimeM']])
    leaf=types.index('LeafSlimeS');mid=1
    rows=profile(variant);roles={ref:(code,up) for ref,code,up,_ in rows}
    if variant.startswith('CP-beast-'):roles['target']=('C10' if variant.endswith('attack') else 'U28',False)
    originals=[f'starter-{i}' for i in range(10)];lookup={};native=set();masters=set();model_ids=[]
    need(type(r['cards']) is list and len(r['cards'])==10+len(roles))
    for c in r['cards']:
        need(type(c) is dict and set(c)==set('cardRef modelId upgraded combatCardIndex sameObject ownerId masterIndex masterModelId'.split()))
        ref=c['cardRef'];idx=c['combatCardIndex'];need(type(ref) is str and ref not in lookup and integer(idx) and idx not in native)
        same(c['sameObject'],True);same(c['ownerId'],pid)
        if ref in originals:
            need(integer(c['masterIndex']) and c['masterIndex']<10 and c['masterIndex'] not in masters);masters.add(c['masterIndex'])
            same(c['masterModelId'],c['modelId']);same(c['upgraded'],False);model_ids.append(c['modelId'])
        else:
            need(ref in roles);code,up=roles[ref];same(c['modelId'],'VOLIBEAR_'+code);same(c['upgraded'],up);same(c['masterIndex'],-1);same(c['masterModelId'],None)
        lookup[ref]=c;native.add(idx)
    need(set(lookup)==set(originals)|set(roles));need(Counter(model_ids)==Counter(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']))
    conversions=[]
    if variant.startswith('CP-beast-'):
        conversions=[dict(materialRef='target',cardRef='target-beast',sameObject=False,
            materialIndex=lookup['target']['combatCardIndex'],cardIndex=lookup['target-beast']['combatCardIndex'],
            materialExhausted=True,originalPile='Hand',generatedPile='Hand')]
    same(r['conversions'],conversions)
    medium_count=2 if types[mid]=='LeafSlimeM' else 1
    gen_count=(medium_count+1 if variant=='CP-expiry' else medium_count) if variant in ('CP-expiry','CP-elig-R09') else 0
    need(type(r['generated']) is list and len(r['generated'])==gen_count)
    gen_refs=[f'generated-{i}' for i in range(gen_count)]
    for index,g in enumerate(r['generated']):
        idx=g['combatCardIndex'];need(integer(idx) and idx not in native);native.add(idx)
        goop=variant=='CP-expiry' and index==medium_count
        same(g,dict(cardRef=gen_refs[index],modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=idx,sameObject=True,ownerId=pid,
                    masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=ids[leaf] if goop else ids[mid],sourceType='LeafSlimeS' if goop else types[mid],
                    sourceMove='GOOP_MOVE' if goop else 'STICKY_SHOT' if types[mid]=='LeafSlimeM' else 'STICKY_SHOT_MOVE',
                    round=2 if goop else 1,turn=2 if goop else 1,side='Enemy' if variant=='CP-expiry' and not goop else 'Player',
                    window='expiry-engage' if goop else 'end-turn' if variant=='CP-expiry' else 'R09'))
    seed=r['initial']['draw'];need(type(seed) is list and len(seed)==10 and set(seed)==set(originals))
    state=dict(round=1,turn=1,side='Player',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},hand=[],draw=seed[:],discard=[],play=[],exhaust=[],forms=[])
    same(r['initial'],state);need(type(r['steps']) is list and len(r['steps'])==len(rows))
    present=set(originals);action_ids=set();play_ids=set();engaged=False
    def coupons():return dict(attack=state['powers'].get('NextAttackDiscount',0),engage=state['powers'].get('NextEngageDiscount',0))
    def history():return dict(plays=[],draws=[],moves=[],damage=[],generated=[])
    def damage(h,target,amount,blocked=0,source=None,props=8):h['damage'].append(dict(target=target,cardRef=source,hpLost=amount,blocked=blocked,props=props))
    def draw(h,n,normal=False):
        selected=state['draw'][:n];state['draw']=state['draw'][n:];state['hand']+=selected
        h['draws'] += [dict(cardRef=c,fromHandDraw=normal) for c in selected]
    def monster(h,index,amount):
        blocked=min(amount,state['block']);state['block']-=blocked;state['hp']-=amount-blocked
        damage(h,pid,amount-blocked,blocked);h['moves'].append(dict(enemy=ids[index],move='TACKLE_MOVE'))
    def strike(h,amount,ref):state['enemyHp'][leaf]-=amount;damage(h,ids[leaf],amount,source=ref)
    def lightning(h,amount,ref):
        for i in range(3):state['enemyHp'][i]-=amount;damage(h,ids[i],amount,source=ref,props=4)
    def statuses(h):
        state['discard']+=gen_refs[:medium_count];h['generated'] += [dict(cardRef=c,creatorId=None) for c in gen_refs[:medium_count]]
        h['moves'].append(dict(enemy=ids[mid],move='STICKY_SHOT' if types[mid]=='LeafSlimeM' else 'STICKY_SHOT_MOVE'))
    def all_enemies(h,engage=False):
        nonlocal engaged
        for actor,kind in enumerate(types):
            if kind=='LeafSlimeS':monster(h,actor,3)
            elif kind=='TwigSlimeS':monster(h,actor,4)
            else:statuses(h)
            if engage and not engaged:draw(h,1);engaged=True
    for step,(ref,code,up,label) in zip(r['steps'],rows):
        if variant=='CP-expiry' and label=='target':
            before=deepcopy(state);h=history();state['powers'].pop('NextAttackDiscount');state['powers'].pop('NextEngageDiscount')
            all_enemies(h)
            state.update(round=2,turn=2,energy=3,block=0);draw(h,5,True)
            same(r['transition'],dict(before=before,after=state,history=h));engaged=False
        if label=='convert' and 'target' not in present:state['hand'].append('target');present.add('target')
        if ref not in present:state['hand'].append(ref);present.add(ref)
        before=deepcopy(state);h=history();shape='None'
        if ref=='target-beast' and variant.startswith('CP-beast-'):shape='Claw' if variant.endswith('attack') else 'Body'
        card_type='Attack' if shape=='Claw' or shape=='None' and code in ATTACK else 'Skill'
        a=step['action'];aid=a['id'];need(integer(aid) and aid not in action_ids);action_ids.add(aid)
        invalid=label=='invalid-target';target=pid if invalid else ids[leaf] if code in ENGAGE and code!='R09' and shape!='Body' or code in ('C01','T01') else None
        before_coupons=coupons();is_attack=card_type=='Attack';is_engage=code in ENGAGE and shape=='None'
        # Same-kind grants retain their maximum; distinct eligible power kinds each reduce cost.
        discount=(before_coupons['attack'] if is_attack else 0)+(before_coupons['engage'] if is_engage else 0)
        paid=max(0,COST[code]-discount) if shape=='None' else 0
        events=[dict(name='before-executed',state='Executing',id=aid,energy=state['energy'])]
        payments=[];effects=[]
        if invalid:events.append(dict(name='cancelled',state='Canceled',id=aid,energy=state['energy']))
        else:
            state['energy']-=paid
            payments=[dict(cardRef=ref,amount=paid,energy=state['energy'],coupons=before_coupons)]
            if is_attack:state['powers'].pop('NextAttackDiscount',None)
            if is_engage:state['powers'].pop('NextEngageDiscount',None)
            play_id=step['effects'][0]['playId'];need(integer(play_id) and play_id>0 and play_id not in play_ids);play_ids.add(play_id)
            effects=[dict(cardRef=ref,index=0,count=1,autoPlay=False,playId=play_id,spent=paid,energy=state['energy'],cardType=card_type,shape=shape,coupons=coupons())]
            h['plays']=[dict(cardRef=ref,index=0,count=1)];state['hand'].remove(ref)
            if code=='C25':
                state['powers']['StormChargePower']=state['powers'].get('StormChargePower',0)+(2 if up else 1);state['powers']['NextAttackDiscount']=1
            elif code=='U14':state['block']+=8 if up else 5;state['powers']['NextEngageDiscount']=1
            elif code=='B02':state['block']+=5
            elif code=='R29':
                state['hand'].remove('target');state['exhaust'].append('target')
                state['hand'].append('target-beast');present.add('target-beast')
                state['forms']=[dict(cardRef='target-beast',shape='Claw' if variant.endswith('attack') else 'Body',type='Attack' if variant.endswith('attack') else 'Skill')]
                h['generated'].append(dict(cardRef='target-beast',creatorId=pid))
            elif shape=='Claw':strike(h,7,ref);strike(h,7,ref)
            elif shape=='Body':state['block']+=9;lightning(h,2+state['powers']['StormChargePower'],ref)
            elif code=='C01':strike(h,6,ref)
            else:
                state['block'] += dict(B04=10,C04=0,C10=8,C11=12,U28=12,U35=8,R09=15)[code]
                if code in ('B04','C04'):strike(h,6 if code=='B04' else 9,ref)
                if code=='U35':lightning(h,3+state['powers']['StormChargePower'],ref)
                if code=='R09':all_enemies(h,True)
                else:
                    if variant=='CP-expiry':
                        state['discard'].append(gen_refs[-1]);h['generated'].append(dict(cardRef=gen_refs[-1],creatorId=None))
                        h['moves'].append(dict(enemy=ids[leaf],move='GOOP_MOVE'))
                    else:monster(h,leaf,2 if code=='C04' else 3)
                    if not engaged:draw(h,1);engaged=True
                if code=='C10':strike(h,6 if variant=='CP-expiry' else 9,ref)
                if code in ('U28','R09'):lightning(h,7+state['powers']['StormChargePower'],ref)
            exhaust=code in ('C25','R29') or code=='U14' and not up or shape!='None'
            state['exhaust' if exhaust else 'discard'].append(ref)
        events.append(dict(name='after-finished',state='Finished',id=aid,energy=state['energy']))
        expected=dict(label=label,cardRef=ref,cardType=card_type,shape=shape,before=before,after=state,
                      action=dict(id=aid,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context=None if invalid else 'GameActionPlayerChoiceContext',target=target,sameCard=True,events=events),
                      payments=payments,effects=effects,history=h)
        same(step,expected)
    if variant!='CP-expiry':same(r['transition'],None)
