"""Frozen standalone U03 native extra/normal player-start oracle. No production imports."""
from collections import Counter
from copy import deepcopy
import json
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')
PREFIX='[Volibear] STANDING_EXTRA_TURN_RESULT '
STANDING_CASES=('U03-base-extra-turn','U03-upgraded-extra-turn')
ACCEPTANCE='native-mayhem-standing-extra-and-normal-player-start-not-OS-input'

def need(value):
    if not value:raise ValueError('standing extra-turn mismatch')
def integer(value):return type(value) is int and value>=0
def eq(a,b,key=None):
    if type(b) is dict:return type(a) is dict and a.keys()==b.keys() and all(eq(a[k],v,k) for k,v in b.items())
    if type(b) is list:return type(a) is list and len(a)==len(b) and all(eq(x,y,key) for x,y in zip(a,b))
    if type(b) in (int,float) and key in {"amount","hpLost","blocked","blockGains","requested"}:return type(a) in (int,float) and a==b
    return type(a) is type(b) and a==b
def same(a,b,key=None):need(eq(a,b,key))
def standing_extra_turn_evidence(log,token,variant):
    rows=[]
    for line in log.splitlines():
        if PREFIX not in line:continue
        try:r=json.loads(line.split(PREFIX,1)[1])
        except (ValueError,TypeError):continue
        if type(r) is dict and r.get('token')==token and r.get('variant')==variant:rows.append(r)
    raw=rows[0] if len(rows)==1 else None
    return raw,raw is not None and validate_result(raw,token,variant)
def validate_result(r,token,variant):
    try:_validate(r,token,variant);return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):return False

def _validate(r,token,variant):
    need(variant in STANDING_CASES and type(r) is dict and set(r)==set('token variant scenario schema completed gameVersion gameCommit testMode acceptance fixture character playerId enemyIds enemyTypes cards generated initial actions setups blockFixture transitions final payments effects boundaries extraTurns autoPhases blockGains clearPreventers blockTrace powerLifecycle'.split()))
    for k,v in dict(token=token,variant=variant,scenario='standing-extra-turn',schema='standing-extra-turn-v1',completed=True,gameVersion=EXPECTED_GAME_VERSION,gameCommit=EXPECTED_GAME_COMMIT,testMode=False,
                    acceptance=ACCEPTANCE,fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-five-padding-native-block40-explicit',character='VolibearCharacter').items():same(r[k],v)
    up=variant==STANDING_CASES[1];decay,entry=(3,12) if up else (6,8)
    pid=r['playerId'];ids=r['enemyIds'];types=r['enemyTypes']
    need(integer(pid) and type(ids) is list and len(ids)==3 and all(integer(i) for i in ids) and len(set(ids+[pid]))==4)
    need(types in [[a,m,b] for a,b in [('LeafSlimeS','TwigSlimeS'),('TwigSlimeS','LeafSlimeS')] for m in ('LeafSlimeM','TwigSlimeM')])
    leaf=types.index('LeafSlimeS');mid=1;medium_count=2 if types[mid]=='LeafSlimeM' else 1
    originals=[f'starter-{i}' for i in range(10)];roles={'mayhem':'MAYHEM','standing':'VOLIBEAR_U03','extra-thunder':'VOLIBEAR_C24','normal-thunder':'VOLIBEAR_C24'}
    for label in ('turn2','extra','turn4'):
        for i in range(5):roles[f'{label}-padding-{i}']='VOLIBEAR_B02'
    need(type(r['cards']) is list and len(r['cards'])==29)
    refs=set();native=set();masters=set();models=[]
    for c in r['cards']:
        need(type(c) is dict and set(c)==set('cardRef modelId upgraded combatCardIndex sameObject ownerId masterIndex masterModelId'.split()))
        ref=c['cardRef'];idx=c['combatCardIndex'];need(type(ref) is str and ref not in refs and integer(idx) and idx not in native);refs.add(ref);native.add(idx)
        same(c['sameObject'],True);same(c['ownerId'],pid)
        same(c['upgraded'],ref=='standing' and up)
        if ref in originals:
            need(integer(c['masterIndex']) and c['masterIndex']<10 and c['masterIndex'] not in masters);masters.add(c['masterIndex']);models.append(c['modelId']);same(c['masterModelId'],c['modelId']);same(c['modelId'],(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04'])[c['masterIndex']])
        else:need(ref in roles);same(c['modelId'],roles[ref]);same(c['masterIndex'],-1);same(c['masterModelId'],None)
    need(refs==set(originals)|set(roles));need(Counter(models)==Counter(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']))
    gen=[f'generated-{i}' for i in range(medium_count+1)]
    need(type(r['generated']) is list and len(r['generated'])==len(gen))
    for i,g in enumerate(r['generated']):
        idx=g['combatCardIndex'];need(integer(idx) and idx not in native);native.add(idx);goop=i==medium_count
        same(g,dict(cardRef=gen[i],modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=idx,sameObject=True,ownerId=pid,masterModelId=None,creatorId=None,pile='Discard',
                    sourceEnemy=ids[leaf] if goop else ids[mid],sourceType='LeafSlimeS' if goop else types[mid],
                    sourceMove='GOOP_MOVE' if goop else 'STICKY_SHOT' if types[mid]=='LeafSlimeM' else 'STICKY_SHOT_MOVE',round=2 if goop else 1,turn=3 if goop else 1,side='Enemy'))
    seed=r['initial']['draw'];need(type(seed) is list and len(seed)==10 and set(seed)==set(originals))
    s=dict(round=1,turn=1,side='Player',phase='Play',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},relics=['HuntersHeart','PaelsEye'],eyeUsed=False,standingSame=None,
           hand=[],draw=seed[:],discard=[],play=[],exhaust=[],removed=[])
    same(r['initial'],s)
    def window():return dict(round=s['round'],turn=s['turn'],side=s['side'],block=s['block'],standing=s['powers'].get('StandingPower',0),standingSame=s['standingSame'],eyeUsed=s['eyeUsed'])
    def hist():return dict(plays=[],finished=[],exhausts=[],draws=[],moves=[],damage=[],generated=[],ordered=[])
    def draw(h,n,normal=False):
        cards=s['draw'][:n];s['draw']=s['draw'][n:];s['hand']+=cards;h['draws'] += [dict(cardRef=c,fromHandDraw=normal) for c in cards]
    block_trace=[]
    def trace(kind,before,after,clear_id=None):
        block_trace.append(dict(sequence=len(block_trace)+1,kind=kind,clearId=clear_id,before=before,after=after,ownerId=pid,combatSame=True,round=s['round'],turn=s['turn'],side=s['side']))
    def write_block(value,clear_id=None):
        old=s['block'];trace('block-write',old,value,clear_id)
        if old!=value:trace('block-changed',old,value,clear_id)
        s['block']=value
    def clear_block(value,clear_id):
        old=s['block'];trace('clear-enter',old,old,clear_id);write_block(value,clear_id);trace('clear-complete',old,value,clear_id)
    def damage(h,target,amount,blocked=0,ref=None,props=8,dealer=None):
        row=dict(target=target,cardRef=ref,hpLost=amount,blocked=blocked,props=props,dealer=dealer,combatSame=True,round=s['round'],turn=s['turn'],side=s['side'])
        h['damage'].append(row);h['ordered'].append(dict(kind='damage',data=deepcopy(row)))
    def move_event(h,actor,name):
        h['moves'].append(dict(enemy=ids[actor],move=name));h['ordered'].append(dict(kind='move',data=dict(enemy=ids[actor],move=name,combatSame=True,round=s['round'],turn=s['turn'],side=s['side'])))
    def generated(h,refs):
        for ref in refs:
            s['discard'].append(ref);h['generated'].append(dict(cardRef=ref,creatorId=None))
            h['ordered'].append(dict(kind='generated',data=dict(cardRef=ref,creatorId=None,ownerId=pid,combatSame=True,round=s['round'],turn=s['turn'],side=s['side'])))
    effects=[];play_ids=set();ends_all=[];extras_all=[];autos_all=[]
    def effect(ref,spent,auto):
        play_id=r['effects'][len(effects)]['playId'];need(integer(play_id) and play_id>0 and play_id not in play_ids and (not play_ids or play_id>max(play_ids)));play_ids.add(play_id)
        row=dict(cardRef=ref,index=0,count=1,autoPlay=auto,playId=play_id,spent=spent,energy=s['energy'],window=window());effects.append(row);return row
    def finished(h,ref,auto):
        h['plays']=[dict(cardRef=ref,index=0,count=1,autoPlay=auto)];h['finished']=[dict(cardRef=ref,autoPlay=auto)]
        s['removed' if ref in ('mayhem','standing') else 'discard'].append(ref)
    need(type(r['actions']) is list and len(r['actions'])==1)
    row=r['actions'][0];aid=row['action']['id'];need(integer(aid));s['hand']=['mayhem'];before=deepcopy(s);s['energy']=28
    pay=dict(cardRef='mayhem',amount=2,energy=28,window=window());fx=effect('mayhem',2,False);s['hand']=[];s['powers']={'MayhemPower':1};h=hist();finished(h,'mayhem',False)
    same(row,dict(label='mayhem',cardRef='mayhem',before=before,after=s,action=dict(id=aid,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context='GameActionPlayerChoiceContext',target=None,sameCard=True,
                  events=[dict(name='before-executed',state='Executing',id=aid,energy=30),dict(name='after-finished',state='Finished',id=aid,energy=28)]),payments=[pay],effects=[fx],history=h))
    need(type(r['setups']) is list and len(r['setups'])==3);need(type(r['transitions']) is list and len(r['transitions'])==3)
    def boundary(side):
        w=window();row=dict(hook='Hook.AfterTurnEnd',side=side,participants=[pid] if side=='Player' else ids,before=w,after=deepcopy(w));ends_all.append(row);return row
    def monster(h,actor,amount,move):
        blocked=min(amount,s['block']);write_block(s['block']-blocked);s['hp']-=amount-blocked;damage(h,pid,amount-blocked,blocked,dealer=ids[actor]);move_event(h,actor,move)
    for i,(label,ref,transition) in enumerate([('turn2','standing','natural-enemy-before-standing'),('extra','extra-thunder','paels-eye-extra-player-turn'),('turn4','normal-thunder','natural-enemy-after-extra')]):
        if i==1:
            before=deepcopy(s);write_block(40)
            same(r['blockFixture'],dict(operation='CreatureCmd.GainBlock-Unpowered-to40',amount=40-entry,before=before,after=s,blockGains=[40-entry],clearPreventers=[]))
        before=deepcopy(s);padding=[f'{label}-padding-{j}' for j in range(5)];s['draw']=padding+[ref]+s['draw']
        same(r['setups'][i],dict(label=label,operation='CardPileCmd.Add-Top-five-padding-before-native-auto-target',target=ref,before=before,after=s))
        before=deepcopy(s);h=hist();extras=[]
        if i==1:h['exhausts']+=s['hand'];s['exhaust']+=s['hand']
        else:s['discard']+=s['hand']
        s['hand']=[];ends=[boundary('Player')]
        if i==1:
            s['turn']=3;w=window();s['eyeUsed']=True;event=dict(hook='Hook.AfterTakingExtraTurn',playerId=pid,before=w,after=window());extras=[event];extras_all.append(event)
        else:
            s['side']='Enemy'
            for actor,kind in enumerate(types):
                if kind=='LeafSlimeS' and i==2:
                    generated(h,[gen[-1]]);move_event(h,actor,'GOOP_MOVE')
                elif kind=='LeafSlimeS':monster(h,actor,3,'TACKLE_MOVE')
                elif kind=='TwigSlimeS':monster(h,actor,4,'TACKLE_MOVE')
                elif i==0:
                    generated(h,gen[:medium_count]);move_event(h,actor,'STICKY_SHOT' if kind=='LeafSlimeM' else 'STICKY_SHOT_MOVE')
                else:monster(h,actor,8 if kind=='LeafSlimeM' else 11,'CLUMP_SHOT' if kind=='LeafSlimeM' else 'POKEY_POUNCE_MOVE')
            ends.append(boundary('Enemy'));s['side']='Player';s['round']+=1;s['turn']+=1
        clear_block(max(0,s['block']-decay) if i else 0,i+1);s.update(energy=3,phase='AutoPrePlay')
        draw(h,5,True);auto_before=deepcopy(s);ah=hist();fx=effect(ref,0,True);same(s['draw'][0],ref);s['draw'].pop(0)
        if i==0:write_block(entry);s['powers']['StandingPower']=decay;s['standingSame']=True
        else:
            for j in range(3):s['enemyHp'][j]-=6;damage(ah,ids[j],6,ref=ref,props=4,dealer=pid)
            draw(ah,1)
        finished(ah,ref,True)
        gains=[entry] if i==0 else []
        phase=dict(hook='MayhemPower.AfterAutoPrePlayPhaseEntered',context='HookPlayerChoiceContext',before=auto_before,after=deepcopy(s),history=ah,payments=[],effects=[fx],blockGains=gains,clearPreventers=[]);autos_all.append(phase)
        for k in h:h[k]+=ah[k]
        s['phase']='Play'
        same(r['transitions'][i],dict(label=transition,before=before,after=s,history=h,payments=[],effects=[fx],boundaries=ends,extraTurns=extras,autoPhases=[phase],blockGains=gains,clearPreventers=[]))
    same(r['final'],s);same(r['payments'],[pay]);same(r['effects'],effects);same(r['boundaries'],ends_all);same(r['extraTurns'],extras_all);same(r['autoPhases'],autos_all)
    same(r['blockGains'],[entry,40-entry],'blockGains');same(r['clearPreventers'],[])

    same(r['blockTrace'],block_trace)
    lifecycle=[]
    for kind,amount,before,requested,source in [('apply-enter',0,None,decay,False),('amount-write',decay,0,None,False),('collection-added',decay,None,None,False),('apply-complete',decay,None,None,False),('after-applied-enter',decay,None,None,True),('after-applied-complete',decay,None,None,True)]:
        lifecycle.append(dict(sequence=len(lifecycle)+1,kind=kind,powerRef='standing-power-1',epoch=1,type='StandingPower',ownerId=pid,ownerSame=True,combatSame=True,round=2,turn=2,side='Player',
            amount=amount,before=before,requested=requested,sourceCard='standing' if source else None,sourceOwnerId=pid if source else None,sourceSame=True if source else None,sourceUpgraded=up if source else None,sourceOwnerSame=True if source else None,applierId=pid if source else None,applierSame=True if source else None))
    same(r['powerLifecycle'],lifecycle)
