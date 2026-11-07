"""Raw-value gate for supported Ritual/Plating controlled native-await probes only.
CurlUp, Skittish, initial-round Plating and new-Strength Apply are not accepted cases.
"""
import argparse
import json
from pathlib import Path
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = '[Volibear] DOMAIN_PASSIVE_RESULT '
VARIANTS = tuple(f'{family}-{mode}' for family in ('ritual', 'plating') for mode in ('off', 'on', 'open', 'close', 'post'))


def expectations(variant):
    family, mode = variant.split('-')
    initial = mode in ('on', 'close')
    blocked = mode in ('on', 'open')
    post = mode == 'post'
    def snap(round=1, side='Player', strength=0, block=0, domain=0, applied=True):
        return dict(hp=1000, block=block, strength=strength,
            ritual=3 if applied and family == 'ritual' else 0,
            plating=(5 if round < 3 and side == 'Player' else 4) if applied and family == 'plating' else 0,
            domain=domain, playerHp=80, round=round, side=side, targetAttached=True, inProgress=True)
    before_domain = 4 if initial else 0
    after_domain = {'off': 0, 'on': 4, 'open': 5, 'close': 0, 'post': 5}[mode]
    pre_strength = 7 if post and family == 'ritual' else 4
    pre_block = 4 if post and family == 'plating' else 0
    return dict(
        directBefore=snap(domain=5 if initial else 0, applied=False),
        directAfter=snap(strength=4, block=7, domain=5 if initial else 0, applied=False),
        firstTurn=snap(round=2, strength=4, block=5 if family == 'plating' and not initial else 0, domain=before_domain),
        before=snap(round=2, side='Enemy', strength=pre_strength, block=pre_block, domain=before_domain),
        afterYield=snap(round=2, side='Enemy', strength=pre_strength, block=pre_block, domain=before_domain),
        afterToggle=snap(round=2, side='Enemy', strength=pre_strength, block=pre_block, domain=after_domain),
        afterNested=snap(round=2, side='Enemy', strength=pre_strength+2, block=pre_block+3, domain=after_domain),
        secondTurn=snap(round=3, strength=(6 if blocked else 9) if family == 'ritual' else 6,
            block=3 if family == 'ritual' or blocked else 7, domain={'off':0, 'on':3, 'open':4, 'close':0, 'post':4}[mode]))


def validate(payload, token, variant):
    errors = []
    if not isinstance(payload, dict) or not token or variant not in VARIANTS:
        return ['object result/current token/supported variant required']
    family, mode = variant.split('-')
    def eq(got, want, path):
        if isinstance(got, dict) and isinstance(want, dict):
            if set(got) != set(want): errors.append(path + ': exact raw fields required')
            for k, v in want.items(): eq(got.get(k), v, path + '.' + k)
        elif isinstance(got, list) and isinstance(want, list):
            if len(got) != len(want): errors.append(path + ': exact receipt count required')
            for i, (g, w) in enumerate(zip(got, want)): eq(g, w, path + f'[{i}]')
        elif not (type(got) is type(want) or (type(got) in (int, float) and type(want) in (int, float))) or got != want:
            errors.append(f'{path}: expected {want!r}, observed {got!r}')
    meta = dict(schema=1, token=token, scenario='domain-passive-contract', variant=variant,
        acceptance='controlled-native-await-mechanism-not-full-enemy-coverage', testMode=False,
        version=EXPECTED_GAME_VERSION, commit=EXPECTED_GAME_COMMIT, targetType='LeafSlimeS',
        fixture='native-SlimesWeak+native-fixture-powers',
        api='PowerCmd+CreatureCmd+PlayerCmd.EndTurn+actual-command-MoveNext-await-boundary',
        directStrengthInput=4, directBlockInput=7, directStrengthResult=4, directBlockResult=7, armedAfter=False)
    for k, v in meta.items(): eq(payload.get(k), v, k)
    direct = payload.get('directBefore')
    if not isinstance(direct, dict): return errors + ['missing actual direct-control baseline']
    ids = {k: direct.get(k) for k in ('ownerId', 'targetId')}
    if not all(isinstance(x, str) and x.isdecimal() for x in ids.values()) or ids['ownerId'] == ids['targetId']:
        errors.append('distinct native owner/target identities required')
    expected = expectations(variant)
    for field in ('directBefore', 'directAfter', 'firstTurn', 'secondTurn'):
        eq(payload.get(field), dict(expected[field], **ids), field)
    receipts = payload.get('receipts')
    if not isinstance(receipts, list) or len(receipts) != 1 or not isinstance(receipts[0], dict):
        return errors + ['exactly one actual await boundary receipt required; missing/unhit path is failure']
    r = receipts[0]
    for field in ('before', 'afterYield', 'afterToggle', 'afterNested'):
        eq(r.get(field), dict(expected[field], **ids), 'receipt.' + field)
    for k, v in dict(stage='after' if mode == 'post' else 'before', amount=3 if family == 'ritual' else 4,
                     nestedBlockInput=3, nestedStrengthInput=2, nestedBlockResult=3,
                     nestedStrengthResult=expected['afterNested']['strength']).items():
        eq(r.get(k), v, 'receipt.' + k)
    target = ids['targetId']
    block_amounts = [3] if family == 'ritual' or mode in ('on', 'open') else ([4, 3] if mode == 'post' else [3, 4])
    eq(payload.get('blockHistory'), [dict(targetId=target, amount=x, props=4) for x in block_amounts], 'actual target block history')
    if family == 'ritual':
        offsets = [2] if mode in ('on', 'open') else ([3, 2] if mode == 'post' else [2, 3])
        powers = [dict(targetId=target, power='StrengthPower', amount=x, applierId=target) for x in offsets]
    else:
        powers = [dict(targetId=target, power='PlatingPower', amount=-1, applierId=None),
                  dict(targetId=target, power='StrengthPower', amount=2, applierId=target)]
    eq(payload.get('powerHistory'), powers, 'actual positive/negative target power history')
    history = payload.get('history')
    if not isinstance(history, list) or len(history) != 3 or not all(isinstance(e, dict) for e in history):
        errors.append('three actual native monster moves required for second cycle')
    else:
        target_rows = [e for e in history if e.get('sourceId') == target]
        if len(target_rows) != 1 or target_rows[0].get('type') != 'LeafSlimeS' or target_rows[0].get('move') not in ('TACKLE_MOVE', 'GOOP_MOVE'):
            errors.append('actual target native move receipt missing')
        types = [e.get('type') for e in history]
        if types.count('LeafSlimeS') != 1 or types.count('TwigSlimeS') != 1 or sum(x in ('LeafSlimeM', 'TwigSlimeM') for x in types) != 1:
            errors.append('native SlimesWeak roster mismatch')
        sources = [e.get('sourceId') for e in history]
        if not all(isinstance(x, str) and x.isdecimal() for x in sources) or len(set(sources)) != 3:
            errors.append('native move identities must be distinct')
    return errors


def check_log(text, token, variant):
    matches = [line.split(MARKER, 1)[1] for line in text.splitlines() if MARKER in line]
    if len(matches) != 1: return dict(passed=False, errors=['exactly one DOMAIN_PASSIVE_RESULT required'], result=None)
    try: payload = json.loads(matches[0])
    except (ValueError, TypeError) as e: return dict(passed=False, errors=[str(e)], result=None)
    errors = validate(payload, token, variant)
    if '[Volibear] DOMAIN_PASSIVE_ERROR' in text: errors.append('native fixture error emitted')
    if sum(line.strip() == '[Volibear] SHUTDOWN_BEGIN ' + token for line in text.splitlines()) != 1:
        errors.append('exactly one current-token shutdown required')
    return dict(passed=not errors, errors=errors, result=payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--token', required=True)
    parser.add_argument('--variant', choices=VARIANTS, required=True)
    args = parser.parse_args()
    result = check_log(args.log.read_text(encoding='utf-8'), args.token, args.variant)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
