"""Native FossilStalker blocked LATCH and two-unblocked-hit LASH evidence."""
import argparse
import json
from pathlib import Path
MARKER='[Volibear] DOMAIN_SUCK_RESULT '
VARIANTS=('suck-off','suck-on')

def expectations(variant,owner,target):
    on=variant=='suck-on'
    def snap(round=1,side='Player',strength=4,block=0,domain=None,hp=80,player_block=0):
        return dict(ownerId=owner,targetId=target,hp=1000,block=block,strength=strength,strengthInstances=1 if strength else 0,
            suck=3,domain=(5 if on else 0) if domain is None else domain,playerHp=hp,playerBlock=player_block,
            round=round,side=side,targetAttached=True,inProgress=True)
    def hit(blocked,unblocked):return dict(receiverId=owner,blocked=blocked,unblocked=unblocked,overkill=0,total=blocked+unblocked,fullyBlocked=blocked>0,killed=False)
    return dict(controlStrengthInput=4,controlBlockInput=7,controlStrengthResult=4,controlBlockResult=7,
        directBefore=snap(strength=0),directAfter=snap(block=7),blockedStart=snap(block=7,player_block=16),
        blockedEnd=snap(2,domain=4 if on else 0),eventsAfterBlocked=0,hooksAfterBlocked=0,
        lashStart=snap(2,domain=4 if on else 0),final=snap(3,strength=4 if on else 10,domain=3 if on else 0,hp=66),
        attacks=[dict(before=snap(1,'Enemy'),sourceAmount=3,attackerId=target,targetSide='Player',props=8,hits=[[hit(16,0)]]),
                 dict(before=snap(2,'Enemy',domain=4 if on else 0,hp=66),sourceAmount=3,attackerId=target,targetSide='Player',props=8,hits=[[hit(0,7)],[hit(0,7)]])],
        events=[] if on else [dict(kind='display',delta=None,strength=10),dict(kind='increased',delta=6,strength=10)],
        postHooks=[] if on else [dict(amount=6,strength=10,sameIdentity=True)],
        powerHistory=[] if on else [dict(power='StrengthPower',amount=6,targetId=target,applierId=target)],
        moves=[dict(sourceId=target,type='FossilStalker',move=m) for m in ('LATCH_MOVE','LASH_MOVE')],
        sameStrengthIdentity=True,initialMove='LATCH_MOVE',selectedMove='LASH_MOVE',selectionApi='MonsterModel.SetMoveImmediate(existing-native-LASH_MOVE)')

def validate(p,token,variant):
    if not isinstance(p,dict) or not token or variant not in VARIANTS:return ['object/current token/supported variant required']
    errors=[]
    def eq(g,w,path):
        if isinstance(g,dict) and isinstance(w,dict):
            if set(g)!=set(w):errors.append(path+': exact raw fields required')
            for k,v in w.items():eq(g.get(k),v,path+'.'+k)
        elif isinstance(g,list) and isinstance(w,list):
            if len(g)!=len(w):errors.append(path+': exact native receipt count required')
            for i,(gv,wv) in enumerate(zip(g,w)):eq(gv,wv,path+f'[{i}]')
        elif not(type(g) is type(w) or type(g) in (int,float) and type(w) in (int,float)) or g!=w:errors.append(f'{path}: expected {w!r}, observed {g!r}')
    for k,v in dict(schema=1,token=token,scenario='domain-passive-contract',variant=variant,
        acceptance='native-encounter-endturn-controlled-existing-move-not-natural-input',testMode=False,version='v0.107.1',commit='59260271',
        fixture='FossilStalkerNormal',targetType='FossilStalker').items():eq(p.get(k),v,k)
    try:owner=p['directBefore']['ownerId'];target=p['directBefore']['targetId']
    except (KeyError,TypeError):return errors+['actual native identities missing']
    if not all(isinstance(x,str) and x.isdecimal() for x in (owner,target)) or owner==target:return errors+['distinct native identities required']
    for k,v in expectations(variant,owner,target).items():eq(p.get(k),v,k)
    return errors

def check_log(text,token,variant):
    rows=[line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(rows)!=1:return dict(passed=False,errors=['exactly one DOMAIN_SUCK_RESULT required'],result=None)
    try:p=json.loads(rows[0])
    except (ValueError,TypeError) as e:return dict(passed=False,errors=[str(e)],result=None)
    errors=validate(p,token,variant)
    if '[Volibear] DOMAIN_SUCK_ERROR' in text:errors.append('native Suck error emitted')
    if sum(line.strip()=='[Volibear] SHUTDOWN_BEGIN '+token for line in text.splitlines())!=1:errors.append('one current-token shutdown required')
    return dict(passed=not errors,errors=errors,result=p)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('log',type=Path)
    parser.add_argument('--token',required=True);parser.add_argument('--variant',choices=VARIANTS,required=True)
    args=parser.parse_args();result=check_log(args.log.read_text(encoding='utf-8'),args.token,args.variant)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
