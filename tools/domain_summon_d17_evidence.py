"""Independent expectations for exact native summon D17 windows. Synthetic fixtures test this gate only."""
import argparse
import json
from pathlib import Path
MARKER='[Volibear] DOMAIN_SUMMON_D17_RESULT '
COUNTS={'fabricator-attack-open':0,'fabricator-attack-close':1,'fabricator-partial-open':1,'fabricator-cancel-close':0,
    'ovicopter-animation-open':0,'ovicopter-partial-open':1,'ovicopter-post-open':3,'ovicopter-cancel-close':0,
    'infested-wait-open':0,'infested-partial-open':1,'infested-post-open':4}
VARIANTS=tuple(COUNTS)
INFO={'fabricator':('Fabricator','FabricatorNormal','fabricator'),'ovicopter':('Ovicopter','OvicopterNormal','ovicopter'),'infested':('PhrogParasite','PhrogParasiteElite','phrog')}
CHILD={'Zapbot':(18,23,'ZAP'),'Stabbot':(18,23,'STAB_MOVE'),'Guardbot':(16,20,'GUARD_MOVE'),'Noisebot':(18,23,'NOISE_MOVE'),
       'ToughEgg':(14,18,'HATCH_MOVE'),'Wriggler':(17,21,'SPAWNED_MOVE')}

def expected(case,token,parent,player,counter,initial,next_move,children):
    family=case.split('-')[0];death=family=='infested';n=COUNTS[case]
    strike=case.startswith('fabricator-attack-');close=case.endswith('-close');cancel_close=case.endswith('-cancel-close')
    initial_domain=5 if close else 0;final_domain=0 if close else 5
    parent_type,encounter,slot=INFO[family]
    selected='INFECT_MOVE' if death else 'LAY_EGGS_MOVE' if family=='ovicopter' else 'FABRICATING_STRIKE_MOVE' if strike else 'FABRICATE_MOVE'
    def child(i,minion=None):
        c=dict(children[i])
        if minion is not None:c['minion']=minion
        return c
    def snap(count=0,domain=0,dead=False,removed=False,ending=False,progress=True,move=None,damaged=None,last_uninitialized=False):
        hp=62 if (strike if damaged is None else damaged) else 80
        rows=[] if removed else [dict(id=parent,type=parent_type,slot=slot,hp=0 if dead else 100,maxHp=100,block=0,minion=0,
            infested=4 if death else 0,hatch=0,nextMove=move or selected,startStunned=None)]
        rows += [child(i,0 if last_uninitialized and i==count-1 else None) for i in range(count)]
        return dict(parentId=parent,playerId=player,parentHp=0 if dead else 100,parentAttached=not removed,parentInfested=4 if death and not removed else 0,
            playerHp=hp,playerBlock=0,domain=domain,inProgress=progress,isEnding=ending,round=1,side='Player',nextCreatureId=counter+count,enemies=rows)
    before=snap(domain=initial_domain,move=initial,damaged=False)
    done=snap(n,final_domain,dead=death,removed=death,ending=death and n==0)
    final=snap(n,0 if death and n==0 else final_domain,dead=death,removed=death,progress=not(death and n==0),move=next_move)
    # Actual source guards, including allowed guards. A move's Domain observation does not reserve later benefits.
    F='SpawnBot.entry-pre-selection';E='LayEggs.entry';P='LayEggs.pre-create';D='Infested.confirmed-entry';W='Infested.post-wait-pre-music';C='Infested.pre-create'
    seq={
        'fabricator-attack-open':[(F,True,5,5,0)],'fabricator-attack-close':[(F,False,0,0,0)],
        'fabricator-partial-open':[(F,False,0,0,0),(F,True,5,5,1)],'fabricator-cancel-close':[(F,True,5,0,0),(F,True,0,0,0)],
        'ovicopter-animation-open':[(E,False,0,0,0),(P,True,5,5,0)],
        'ovicopter-partial-open':[(E,False,0,0,0),(P,False,0,0,0),(P,True,5,5,1)],
        'ovicopter-post-open':[(E,False,0,0,0)]+[(P,False,0,0,i) for i in range(3)],'ovicopter-cancel-close':[(E,True,5,0,0)],
        'infested-wait-open':[(D,False,0,0,0),(W,True,5,5,0)],
        'infested-partial-open':[(D,False,0,0,0),(W,False,0,0,0),(C,False,0,0,0),(C,True,5,5,1)],
        'infested-post-open':[(D,False,0,0,0),(W,False,0,0,0)]+[(C,False,0,0,i) for i in range(4)]}[case]
    gates=[dict(boundary=b,cancelled=cancel,sameBatch=True,domainBefore=d0,domainAfter=d1,
        snapshot=snap(count,d0,dead=death,ending=death and cancel and count==0)) for b,cancel,d0,d1,count in seq]
    if strike:point='native-attack-completed-before-first-SpawnBot';window_count=0
    elif case=='ovicopter-animation-open':point='native-animation-before-first-create';window_count=0
    elif case=='infested-wait-open':point='native-death-wait-before-music-create';window_count=0
    elif cancel_close:point='actual-consumed-cancellation-before-source-return';window_count=0
    else:point='native-child-attached-before-Add-return';window_count=n
    window_before=snap(window_count,initial_domain,dead=death,last_uninitialized=window_count>0)
    window_after=snap(window_count,final_domain,dead=death,last_uninitialized=window_count>0)
    windows=[dict(point=point,open=not close,suspended=not cancel_close,before=window_before,after=window_after)]
    births=[];creates=[]
    for i in range(n):
        births.append(dict(ordinal=i+1,before=child(i,0),after=child(i,0),domain=final_domain if i==n-1 else 0,attached=True,sameCombat=True))
        row=children[i]
        creates.append(dict(point='Add<ToughEgg>.return-after-sync-attach' if family=='ovicopter' else 'CreateCreature.return-before-Add',
            id=row['id'],type=row['type'],slot=row['slot'],side='Enemy',hp=row['hp'],maxHp=row['hp'],combatAssigned=True,
            inRoster=family=='ovicopter',domain=0,counterBefore=counter+i,counterAfter=counter+i+1))
    damage=[dict(sourceId=parent,receiverId=player,hpLost=18,blocked=0,overkill=0,cardSource=None)] if strike else [dict(sourceId=player,receiverId=parent,hpLost=100,blocked=0,overkill=0,cardSource=None)] if death else []
    moves=[] if death else [dict(sourceId=parent,move=selected,targets=[player])]
    if death:
        action=dict(api='CreatureCmd.Damage+native-Kill/AfterDeath+CombatManager.CheckWinCondition',input=dict(amount=100,props=6,sourceId=player,targetId=parent),
            results=[dict(receiverId=parent,hpLost=100,blocked=0,overkill=0)],afterDeath=done,winResult=n==0,wonCount=1 if n==0 else 0,endedCount=1 if n==0 else 0)
    else:
        action=dict(api='MonsterModel.PerformMove+MonsterModel.RollMove',initialMove=initial,selected=selected,performingBefore=False,performingAfter=False,
            stateLogBefore=[initial],stateLogAfter=[initial,next_move],nextMove=next_move,lastSpawnedBefore=None,
            lastSpawnedAfter=children[0]['type'] if family=='fabricator' and n else None,afterMove=done)
    return dict(schema=1,token=token,scenario='domain-summon-contract',variant=case,
        acceptance='native-async-window-probe-not-natural-input-or-full-enemy-coverage',testMode=False,version='v0.107.1',commit='59260271',
        encounter=encounter,parentType=parent_type,fixtureHp=100,ascension=0,before=before,action=action,final=final,damage=damage,moves=moves,
        gates=gates,windows=windows,births=births,creates=creates,childrenFinal=children,
        deathCallbacks=[dict(ownerId=parent,targetId=parent,prevented=False,sourceAmount=4,snapshot=snap(dead=True))] if death else [],
        died=[dict(targetId=parent,hp=0,sameParent=True,domain=0)] if death else [],musicCalls=1 if death and n else 0,windowUsed=True)

def validate(p,token,case):
    if not isinstance(p,dict) or not token or case not in VARIANTS:return ['object/current token/known case required']
    errors=[]
    def require(ok,message):
        if not ok:errors.append(message)
    try:
        parent=p['before']['parentId'];player=p['before']['playerId'];counter=p['before']['nextCreatureId'];initial=p['before']['enemies'][0]['nextMove'];children=p['childrenFinal']
        family=case.split('-')[0];next_move=None if family=='infested' else p['action']['nextMove']
    except (KeyError,TypeError,IndexError):return ['missing native initial identities/action/children']
    require(all(isinstance(x,str) and x.isdecimal() for x in (parent,player)) and parent!=player,'distinct native identities required')
    require(type(counter) is int and counter>=2,'native creation counter required')
    if errors:return errors
    legal_initial=('FABRICATE_MOVE','FABRICATING_STRIKE_MOVE') if family=='fabricator' else ('LAY_EGGS_MOVE',) if family=='ovicopter' else ('INFECT_MOVE',)
    require(initial in legal_initial,'native initial move')
    if family!='infested':require(next_move in (('FABRICATE_MOVE','FABRICATING_STRIKE_MOVE') if family=='fabricator' else ('SMASH_MOVE',)),'native follow-up move')
    if not isinstance(children,list) or len(children)!=COUNTS[case]:return errors+['exact committed children count required']
    allowed=('Zapbot','Stabbot') if case=='fabricator-attack-close' else ('Guardbot','Noisebot') if family=='fabricator' else ('ToughEgg',) if family=='ovicopter' else ('Wriggler',)
    normalized=[]
    for i,c in enumerate(children):
        if not isinstance(c,dict) or c.get('type') not in allowed:return errors+['actual native child type required']
        typ=c['type'];lo,hi,move=CHILD[typ];hp=c.get('hp');require(type(hp) is int and lo<=hp<=hi,'native child HP range')
        slot='bot1' if family=='fabricator' else f'egg{5-i}' if family=='ovicopter' else f'wriggler{i+1}'
        normalized.append(dict(id=str(counter+i),type=typ,slot=slot,hp=hp,maxHp=hp,block=0,minion=0 if family=='infested' else 1,
            infested=0,hatch=1 if family=='ovicopter' else 0,nextMove=move,startStunned=True if family=='infested' else None))
    want=expected(case,token,parent,player,counter,initial,next_move,normalized)
    def eq(g,w,path):
        if isinstance(g,dict) and isinstance(w,dict):
            if set(g)!=set(w):errors.append(path+': exact fields required')
            for k,v in w.items():eq(g.get(k),v,path+'.'+k)
        elif isinstance(g,list) and isinstance(w,list):
            if len(g)!=len(w):errors.append(path+': exact native receipt count required')
            if path.endswith('.enemies') and all(isinstance(x,dict) and isinstance(x.get('id'),str) for x in g+w):
                g=sorted(g,key=lambda x:x['id']);w=sorted(w,key=lambda x:x['id'])
            for i,(a,b) in enumerate(zip(g,w)):eq(a,b,path+f'[{i}]')
        elif not(type(g) is type(w) or type(g) in (int,float) and type(w) in (int,float)) or g!=w:errors.append(f'{path}: expected {w!r}, observed {g!r}')
    eq(p,want,'result')
    return errors

def check_log(text,token,variant):
    rows=[line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(rows)!=1:return dict(passed=False,errors=['exactly one DOMAIN_SUMMON_D17_RESULT required'],result=None)
    try:p=json.loads(rows[0])
    except (ValueError,TypeError) as error:return dict(passed=False,errors=[str(error)],result=None)
    errors=validate(p,token,variant)
    if '[Volibear] DOMAIN_SUMMON_D17_ERROR' in text:errors.append('native D17 probe error')
    if sum(line.strip()=='[Volibear] SHUTDOWN_BEGIN '+token for line in text.splitlines())!=1:errors.append('one matching shutdown required')
    return dict(passed=not errors,errors=errors,result=p)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('log',type=Path);parser.add_argument('--token',required=True);parser.add_argument('--variant',choices=VARIANTS,required=True)
    args=parser.parse_args();result=check_log(args.log.read_text(encoding='utf-8'),args.token,args.variant)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
