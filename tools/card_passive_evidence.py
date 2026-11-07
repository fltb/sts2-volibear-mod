"""Raw native encounter/card evidence for CurlUp and Skittish, not natural-input acceptance."""
import argparse
import json
from pathlib import Path
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = '[Volibear] DOMAIN_CARD_PASSIVE_RESULT '
VARIANTS = ('curlup-off', 'curlup-on', 'skittish-off', 'skittish-on')


def expectations(variant):
    family, mode = variant.split('-'); on = mode == 'on'; curl = family == 'curlup'
    s = dict(hp=1000, block=0, strength=0, curlup=14 if curl else 0, skittish=0 if curl else 6,
        curled=False if curl else None, latch=None if curl else False, domain=5 if on else 0,
        playerHp=80, round=1, side='Player', targetAttached=True, inProgress=True)
    result = {'directBefore': dict(s)}
    s.update(strength=4, block=7); result['directAfter'] = dict(s)
    s['block'] = 0; result['beforeCards'] = dict(s)
    s.update(hp=990 if on else 994, block=0 if on else 14 if curl else 6,
        curlup=0, curled=True if curl else None, latch=None if curl else True)
    result['firstCard'] = dict(s)
    s['block'] = 0; result['beforeSecond'] = dict(s)
    s['hp'] = 980 if on else 988; result['secondCard'] = dict(s)
    s.update(round=2, domain=4 if on else 0, curled=False if curl else None, latch=None if curl else False)
    result['nextTurn'] = dict(s)
    if curl: s.update(round=3, domain=3 if on else 0, block=14, strength=9, curled=True)
    else: s.update(hp=970 if on else 982, block=0 if on else 6, latch=True)
    result['final'] = dict(s)
    first = dict(result['firstCard'], block=0)
    if curl: first.update(curlup=14, curled=False)
    result['attempts'] = [first] if curl else [first, dict(s, block=0)]
    return result


def validate(payload, token, variant):
    if not isinstance(payload, dict) or not token or variant not in VARIANTS:
        return ['object payload/current token/supported case required']
    errors = []
    family, mode = variant.split('-'); on = mode == 'on'; curl = family == 'curlup'
    def eq(got, want, path):
        if isinstance(got, dict) and isinstance(want, dict):
            if set(got) != set(want): errors.append(path + ': exact raw fields required')
            for k, v in want.items(): eq(got.get(k), v, path + '.' + k)
        elif isinstance(got, list) and isinstance(want, list):
            if len(got) != len(want): errors.append(path + ': exact raw receipt count required')
            for i, (g, w) in enumerate(zip(got, want)): eq(g, w, path + f'[{i}]')
        elif not (type(got) is type(want) or type(got) in (int,float) and type(want) in (int,float)) or got != want:
            errors.append(f'{path}: expected {want!r}, observed {got!r}')
    meta = dict(schema=1, token=token, scenario='domain-passive-contract', variant=variant,
        acceptance='native-encounter-card-autoplay-contract-not-natural-input', testMode=False,
        version=EXPECTED_GAME_VERSION, commit=EXPECTED_GAME_COMMIT, targetType='LouseProgenitor' if curl else 'PhantasmalGardener',
        fixture='LouseProgenitorNormal' if curl else 'PhantasmalGardenersElite',
        api='native-encounter-powers+CardCmd.AutoPlay<StrikeIronclad>+PlayerCmd.EndTurn',
        directStrengthInput=4, directBlockInput=7, directStrengthResult=4, directBlockResult=7,
        attemptsAfterFirst=1, attemptsAfterSecond=1, cardCount=2 if curl else 3)
    for k, v in meta.items(): eq(payload.get(k), v, k)
    baseline = payload.get('directBefore')
    if not isinstance(baseline, dict): return errors + ['missing real baseline']
    ids = {k: baseline.get(k) for k in ('ownerId','targetId')}
    if not all(isinstance(x, str) and x.isdecimal() for x in ids.values()) or ids['ownerId'] == ids['targetId']:
        return errors + ['distinct actual native identities required']
    target = ids['targetId']; owner = ids['ownerId']; expected = expectations(variant)
    for k in ('directBefore','directAfter','beforeCards','firstCard','beforeSecond','secondCard','nextTurn','final'):
        eq(payload.get(k), dict(expected[k], **ids), k)
    eq(payload.get('attempts'), [dict(amount=14 if curl else 6, props=4, cardSource=None, before=dict(s, **ids))
                               for s in expected['attempts']], 'native source contribution attempts')
    blocks = ([dict(targetId=target, amount=14, props=4)] if not on else []) + [dict(targetId=target, amount=14, props=8)] if curl else (
             [dict(targetId=target, amount=6, props=4), dict(targetId=target, amount=6, props=4)] if not on else [])
    eq(payload.get('blockHistory'), blocks, 'actual passive vs direct-move block history')
    eq(payload.get('powerHistory'), [dict(targetId=target, power='StrengthPower', amount=5, applierId=target)] if curl else [],
       'actual direct-move strength history')
    roster = payload.get('rosterAfterTurn')
    expected_count = 1 if curl else 4
    if not isinstance(roster, list) or len(roster) != expected_count or not all(isinstance(r,dict) for r in roster):
        return errors + ['exact actual native encounter roster required']
    native_ids = [r.get('id') for r in roster]
    if not all(isinstance(x,str) and x.isdecimal() for x in native_ids) or len(set(native_ids)) != expected_count or owner in native_ids or target not in native_ids:
        return errors + ['invalid/duplicate actual enemy identities']
    moves = payload.get('moves')
    if curl:
        eq(roster, [dict(id=target, type='LouseProgenitor', slot=None, hp=980 if on else 988, strength=4, enlarge=None)], 'native louse after WEB')
        eq(moves, [dict(sourceId=target,type='LouseProgenitor',slot=None,move=x) for x in ('WEB_CANNON_MOVE','CURL_AND_GROW_MOVE')], 'actual louse moves')
    else:
        slots = ('first','second','third','fourth')
        if set(r.get('slot') for r in roster) != set(slots): return errors + ['four native gardener slots required']
        by_slot = {r['slot']: r for r in roster}
        if by_slot['first']['id'] != target: errors.append('first-slot target identity mismatch')
        for slot in slots:
            eq(by_slot[slot], dict(id=by_slot[slot]['id'], type='PhantasmalGardener', slot=slot,
                hp=(980 if on else 988) if slot == 'first' else (992 if on else 1000),
                strength=4 if slot == 'first' else 2 if slot == 'fourth' else 0,
                enlarge=1 if slot == 'fourth' else 0), 'native gardener ' + slot)
        if not isinstance(moves,list) or len(moves)!=4 or not all(isinstance(m,dict) for m in moves):
            errors.append('four actual native gardener moves required')
        else:
            got = {m.get('slot'):m for m in moves}
            if set(got) != set(slots): errors.append('native move slots mismatch')
            for slot, move in zip(slots,('FLAIL_MOVE','BITE_MOVE','LASH_MOVE','ENLARGE_MOVE')):
                eq(got.get(slot),dict(sourceId=by_slot[slot]['id'],type='PhantasmalGardener',slot=slot,move=move),'native move '+slot)
    batches = payload.get('batches')
    if not isinstance(batches,list) or len(batches) != ((2 if curl else 3) if on else 0):
        return errors + ['exact real Domain lightning batch count required']
    for i, batch in enumerate(batches):
        if not isinstance(batch,dict): errors.append('batch object required'); continue
        for k,v in dict(cardRef='strike-'+str(i+1),baseDamage=4,amount=4,count=1 if i==2 else i+1).items():
            eq(batch.get(k),v,'actual lightning '+k)
        targets = batch.get('targetIds'); hits = batch.get('hits')
        if not isinstance(targets,list) or len(targets)!=expected_count or set(targets)!=set(native_ids): errors.append('actual lightning target identities mismatch')
        if not isinstance(hits,list) or len(hits)!=expected_count or not all(isinstance(h,dict) for h in hits): errors.append('actual lightning hits required')
        else:
            by_id = {h.get('targetId'):h for h in hits}
            if set(by_id)!=set(native_ids): errors.append('actual lightning hit identities mismatch')
            for native_id in native_ids: eq(by_id.get(native_id),dict(targetId=native_id,hpLost=4,blocked=0,overkill=0),'actual lightning hit')
    return errors


def check_log(text, token, variant):
    rows = [line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(rows)!=1: return dict(passed=False,errors=['exactly one DOMAIN_CARD_PASSIVE_RESULT required'],result=None)
    try: payload=json.loads(rows[0])
    except (ValueError,TypeError) as e: return dict(passed=False,errors=[str(e)],result=None)
    errors=validate(payload,token,variant)
    if '[Volibear] DOMAIN_CARD_PASSIVE_ERROR' in text: errors.append('native card-passive fixture error')
    if sum(line.strip()=='[Volibear] SHUTDOWN_BEGIN '+token for line in text.splitlines())!=1: errors.append('current-token shutdown required exactly once')
    return dict(passed=not errors,errors=errors,result=payload)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path); parser.add_argument('--token',required=True); parser.add_argument('--variant',choices=VARIANTS,required=True)
    args=parser.parse_args(); result=check_log(args.log.read_text(encoding='utf-8'),args.token,args.variant)
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0 if result['passed'] else 1)
