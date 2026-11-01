"""Initial native Plating.BeforeSideTurnStart, observed before first TurnStarted."""
import argparse
import json
from pathlib import Path
MARKER='[Volibear] DOMAIN_INITIAL_PLATING_RESULT '
VARIANTS=('plating-initial-off','plating-initial-on')

def expectations(variant,owner,target):
    on=variant=='plating-initial-on'
    def snap(block=0,strength=0):return dict(ownerId=owner,targetId=target,hp=1000,block=block,strength=strength,
        strengthInstances=1 if strength else 0,plating=15,domain=5 if on else 0,playerHp=80,round=1,side='Player',
        targetAttached=True,inProgress=True,sameSourceIdentity=True)
    return dict(callback='PlatingPower.BeforeSideTurnStart',callbackRound=1,callbackSide='Player',participants=[owner],
        before=snap(),afterSource=snap(0 if on else 15),afterControls=snap(7 if on else 22,4),final=snap(7 if on else 22,4),
        controlBlockInput=7,controlStrengthInput=4,controlBlockResult=7,controlStrengthResult=4,
        blockHistory=[dict(targetId=target,amount=x,props=4) for x in ([7] if on else [15,7])],
        powerHistory=[dict(targetId=target,power='StrengthPower',amount=4,applierId=target)],
        nativeMoveCount=0,callbackObserved=True,callbackCompleted=True)

def validate(p,token,variant):
    if not isinstance(p,dict) or not token or variant not in VARIANTS:return ['object/current token/supported case required']
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
        acceptance='native-first-side-dispatch-controlled-domain-fixture',testMode=False,version='v0.107.1',commit='59260271',
        fixture='FrogKnightNormal',targetType='FrogKnight').items():eq(p.get(k),v,k)
    try:owner=p['before']['ownerId'];target=p['before']['targetId']
    except (KeyError,TypeError):return errors+['actual native identities missing']
    if not all(isinstance(x,str) and x.isdecimal() for x in (owner,target)) or owner==target:return errors+['distinct native identities required']
    for k,v in expectations(variant,owner,target).items():eq(p.get(k),v,k)
    return errors

def check_log(text,token,variant):
    rows=[line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(rows)!=1:return dict(passed=False,errors=['exactly one DOMAIN_INITIAL_PLATING_RESULT required'],result=None)
    try:p=json.loads(rows[0])
    except (ValueError,TypeError) as e:return dict(passed=False,errors=[str(e)],result=None)
    errors=validate(p,token,variant)
    if '[Volibear] DOMAIN_INITIAL_PLATING_ERROR' in text:errors.append('native initial Plating error emitted')
    if sum(line.strip()=='[Volibear] SHUTDOWN_BEGIN '+token for line in text.splitlines())!=1:errors.append('one current-token shutdown required')
    return dict(passed=not errors,errors=errors,result=p)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('log',type=Path)
    parser.add_argument('--token',required=True);parser.add_argument('--variant',choices=VARIANTS,required=True)
    args=parser.parse_args();result=check_log(args.log.read_text(encoding='utf-8'),args.token,args.variant)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
