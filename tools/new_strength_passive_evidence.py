"""New native Strength Apply: absence/identity/events/history/posthooks, not just Amount zero."""
import argparse
import json
from pathlib import Path
MARKER='[Volibear] DOMAIN_NEW_APPLY_RESULT '
VARIANTS=tuple('newapply-'+x for x in ('off','on','open','close','post'))


def expectations(variant, owner, target, control):
    mode=variant.split('-')[1]; initial=mode in ('on','close'); blocked=mode in ('on','open'); post=mode=='post'
    def creature(id, strength=0, block=0): return dict(id=id,hp=1000,block=block,strength=strength,strengthInstances=1 if strength else 0)
    def snap(round=1, side='Player', strength=0, block=0, domain=0, ritual=3):
        return dict(ownerId=owner,target=creature(target,strength,block),ritual=ritual,domain=domain,playerHp=80,
                    round=round,side=side,targetAttached=True,inProgress=True)
    def candidate(amount=0, attached=False, owned=False):
        return dict(observed=True,amount=amount,ownerId=target if owned else None,applierId=target,attached=attached,currentIdentity=attached)
    empty=candidate(); applied=candidate(3,True,True); enlarged=candidate(5,True,True)
    before_domain=4 if initial else 0; after_domain={'off':0,'on':4,'open':5,'close':0,'post':5}[mode]
    pre=snap(2,'Enemy',strength=3 if post else 0,domain=before_domain)
    gate=dict(stage='after' if post else 'before',before=pre,candidateBefore=applied if post else empty,
        afterYield=dict(pre),afterToggle=snap(2,'Enemy',strength=3 if post else 0,domain=after_domain),
        afterNested=snap(2,'Enemy',strength=5 if post else 0,block=3,domain=after_domain),
        candidateAfterNested=enlarged if post else empty,nestedBlockInput=3,nestedBlockResult=3,
        nestedStrengthInput=2 if post else 0,nestedStrengthResult=5 if post else None)
    events=[]; hooks=[]; history=[]
    if not blocked:
        events=[dict(kind='display',delta=None,candidate=candidate(3,False,True)),
                dict(kind='increased',delta=3,candidate=candidate(3,False,True)),
                dict(kind='applied',delta=None,candidate=applied)]
        hooks=[dict(kind='AfterApplied',amount=3,candidate=applied),dict(kind='AfterPowerAmountChanged',amount=3,candidate=applied)]
        history=[dict(power='StrengthPower',amount=3,targetId=target,applierId=target)]
        if post:
            events += [dict(kind='display',delta=None,candidate=enlarged),dict(kind='increased',delta=2,candidate=enlarged)]
            hooks += [dict(kind='AfterPowerAmountChanged',amount=2,candidate=enlarged)]
            history += [dict(power='StrengthPower',amount=2,targetId=target,applierId=target)]
    return dict(initial=snap(domain=5 if initial else 0,ritual=0),controlBefore=creature(control),controlAfter=creature(control,4,7),
        controlStrengthInput=4,controlBlockInput=7,controlStrengthResult=4,controlBlockResult=7,
        firstTurn=snap(2,domain=before_domain),candidateAfterFirst=False,candidateBefore=empty,
        candidateFinal=empty if blocked else enlarged if post else applied,
        final=snap(3,strength=0 if blocked else 5 if post else 3,block=3,domain={'off':0,'on':3,'open':4,'close':0,'post':4}[mode]),
        events=events,postHooks=hooks,gates=[gate],armedAfter=False,powerHistory=history,
        blockHistory=[dict(targetId=target,amount=3,props=4)])


def validate(p,token,variant):
    if not isinstance(p,dict) or not token or variant not in VARIANTS: return ['object/current token/supported case required']
    errors=[]
    def eq(g,w,path):
        if isinstance(g,dict) and isinstance(w,dict):
            if set(g)!=set(w): errors.append(path+': exact raw fields required')
            for k,v in w.items(): eq(g.get(k),v,path+'.'+k)
        elif isinstance(g,list) and isinstance(w,list):
            if len(g)!=len(w): errors.append(path+': exact native receipt count required')
            for i,(gv,wv) in enumerate(zip(g,w)): eq(gv,wv,path+f'[{i}]')
        elif not (type(g) is type(w) or type(g) in (int,float) and type(w) in (int,float)) or g!=w:
            errors.append(f'{path}: expected {w!r}, observed {g!r}')
    meta=dict(schema=1,token=token,scenario='domain-passive-contract',variant=variant,
        acceptance='controlled-native-new-apply-await-not-natural-input',testMode=False,version='v0.107.1',commit='59260271',
        fixture='SlimesWeak+Ritual3+separate-TwigSlimeS-direct-controls',targetType='LeafSlimeS',controlType='TwigSlimeS')
    for k,v in meta.items(): eq(p.get(k),v,k)
    try: owner=p['initial']['ownerId']; target=p['initial']['target']['id']; control=p['controlBefore']['id']
    except (KeyError,TypeError): return errors+['missing raw native identities']
    if not all(isinstance(x,str) and x.isdecimal() for x in (owner,target,control)) or len({owner,target,control})!=3:
        return errors+['owner/target/control must be distinct actual native identities']
    for k,v in expectations(variant,owner,target,control).items(): eq(p.get(k),v,k)
    moves=p.get('moves')
    if not isinstance(moves,list) or len(moves)!=3 or not all(isinstance(m,dict) for m in moves): errors.append('three actual native moves required')
    else:
        identities=[m.get('sourceId') for m in moves]
        if not all(isinstance(x,str) and x.isdecimal() for x in identities) or len(set(identities))!=3 or owner in identities:
            errors.append('native move identities invalid')
        target_rows=[m for m in moves if m.get('sourceId')==target]
        control_rows=[m for m in moves if m.get('sourceId')==control]
        if len(target_rows)!=1 or target_rows[0].get('type')!='LeafSlimeS' or target_rows[0].get('move') not in ('TACKLE_MOVE','GOOP_MOVE'):
            errors.append('actual Ritual owner native move missing')
        if len(control_rows)!=1 or control_rows[0].get('type')!='TwigSlimeS' or not control_rows[0].get('move'): errors.append('actual direct-control enemy move missing')
        if sum(m.get('type') in ('LeafSlimeM','TwigSlimeM') for m in moves)!=1: errors.append('actual native medium slime move missing')
    return errors


def check_log(text,token,variant):
    rows=[line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(rows)!=1: return dict(passed=False,errors=['exactly one DOMAIN_NEW_APPLY_RESULT required'],result=None)
    try: p=json.loads(rows[0])
    except (ValueError,TypeError) as e: return dict(passed=False,errors=[str(e)],result=None)
    errors=validate(p,token,variant)
    if '[Volibear] DOMAIN_NEW_APPLY_ERROR' in text: errors.append('native new-Apply error emitted')
    if sum(line.strip()=='[Volibear] SHUTDOWN_BEGIN '+token for line in text.splitlines())!=1: errors.append('one current-token shutdown required')
    return dict(passed=not errors,errors=errors,result=p)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('log',type=Path)
    parser.add_argument('--token',required=True); parser.add_argument('--variant',choices=VARIANTS,required=True)
    args=parser.parse_args(); result=check_log(args.log.read_text(encoding='utf-8'),args.token,args.variant)
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['passed'] else 1)
