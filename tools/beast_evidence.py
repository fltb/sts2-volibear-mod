"""Independent finite beast mechanism comparator; never manual-payment acceptance.

Expected numbers are fixed from T01/T02 and native material rules. The probe reports
raw card snapshots, actual native history and reference labels; completed is not a
verdict. No runtime dynamic variable is used to calculate expected damage/block.
"""
import json
from collections import Counter

BEAST_CASES = ('f01', 'f02')
PREFIX = '[Volibear] BEAST_CONTRACT_RESULT '
SNAP_KEYS = set('cardRef nativeType modelId ownerRef masterRef cloneRef costObjectRef shape type target upgrade canonicalCost costsX localCost allCost amountToSpend retain keywords pile presence vars title'.split())


def _equal(actual, expected):
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _need(condition):
    if not condition:
        raise ValueError('Beast observation violates independent fixture')


def _is_ref(value):
    return type(value) is int and value != 0


def _original(actual, name, native, card_type, target, cost, variables, *, upgrade=False,
              retain=False, keywords=(), local=None, costs_x=False, master=None, pile='Hand', owner=None):
    _need(type(actual) is dict and actual.keys() == SNAP_KEYS)
    _need(type(actual['modelId']) is str and bool(actual['modelId']))
    _need(type(actual['title']) is str and bool(actual['title']))
    _need(_is_ref(actual['ownerRef']) and _is_ref(actual['costObjectRef']))
    if owner is not None:
        _need(actual['ownerRef'] == owner)
    value = cost if local is None else local
    _need(actual['cloneRef'] is None or master is not None and actual['cloneRef'] == master)
    expected = dict(actual, cardRef=name, nativeType=native, masterRef=master, shape='None',
                    type=card_type, target=target, upgrade=upgrade, canonicalCost=cost, costsX=costs_x,
                    localCost=value, allCost=value, amountToSpend=3 if costs_x else max(0, value),
                    retain=retain, keywords=sorted(keywords), pile=pile, presence=1, vars=variables)
    _need(_equal(actual, expected))
    return actual


def _form(original, identity, *, shape='Claw', upgraded=False, cost=1, retain=False, local_retain=False, pile='Hand'):
    _need(type(identity) is dict and identity.keys() == SNAP_KEYS)
    _need(_is_ref(identity['costObjectRef']) and identity['costObjectRef'] != original['costObjectRef'])
    return dict(original, cardRef=original['cardRef'] + '-beast',
                nativeType='Volibear_T01' if shape == 'Claw' else 'Volibear_T02',
                modelId='VOLIBEAR_T01' if shape == 'Claw' else 'VOLIBEAR_T02',
                masterRef=None, cloneRef=None, costObjectRef=identity['costObjectRef'],
                shape=shape, type='Attack' if shape == 'Claw' else 'Skill',
                target='AnyEnemy' if shape == 'Claw' else 'AllEnemies', upgrade=upgraded,
                canonicalCost=1, costsX=False, localCost=cost, allCost=cost, amountToSpend=cost,
                retain=retain, keywords=['Exhaust', 'Retain'] if local_retain else ['Exhaust'],
                pile=pile, presence=1,
                vars={'Damage': 11 if upgraded else 7, 'Hits': 2} if shape == 'Claw'
                else {'Block': 12 if upgraded else 9, 'Lightning': 3 if upgraded else 2},
                title=('裂骨之爪' if shape == 'Claw' else '风暴之躯') + ('+' if upgraded else ''))


def _conversion(before, after_material, form, history, new_entity):
    _need(_equal(new_entity, True))
    _need(_equal(after_material, dict(before, pile='Exhaust')))
    _need(_equal(history, dict(exhausted=[before['cardRef']], generated=[form['cardRef']])))
    _need(form['ownerRef'] == before['ownerRef'] and form['cardRef'] != before['cardRef'])
    _need(form['masterRef'] is None and form['cloneRef'] is None)


def _play(actual, snapshot, enemies, *, shape='Claw', upgraded=False, count=0):
    damage = 11 if upgraded else 7
    lightning = 3 if upgraded else 2
    ref = snapshot['cardRef']
    def hit(target, amount, props):
        return dict(target=target, hpLost=amount, blocked=0, props=props, cardRef=ref)
    expected = dict(beforeHp=[100, 100, 100], afterHp=[100 - 2 * damage, 100, 100] if shape == 'Claw'
                    else [100 - lightning] * 3, blockBefore=0,
                    blockAfter=0 if shape == 'Claw' else 12 if upgraded else 9,
                    energyBefore=3, energyAfter=3, lightningBefore=count,
                    lightningAfter=count + (shape == 'Body'), playerStrength=0,
                    enemyVulnerable=[0, 0, 0], autoPlayCalls=1, after=snapshot,
                    playHistory=[dict(cardRef=ref, index=0, count=1)],
                    damageHistory=[hit(enemies[0], damage, 8), hit(enemies[0], damage, 8)] if shape == 'Claw'
                    else [hit(enemy, lightning, 4) for enemy in enemies])
    _need(_equal(actual, expected))


def _deck(result):
    before, after = result['deckBefore'], result['deckAfter']
    _need(type(before) is list and len(before) == 10 and _equal(before, after))
    refs = [c['cardRef'] for c in before]
    _need(all(type(ref) is str and ref.startswith('master-') for ref in refs) and len(set(refs)) == 10)
    _need(Counter(c['nativeType'] for c in before) == Counter(Volibear_B01=4, Volibear_B02=4, Volibear_B03=1, Volibear_B04=1))
    expected_vars = {'Volibear_B01': {'Damage': 6}, 'Volibear_B02': {'Block': 5},
                     'Volibear_B03': {'Damage': 8, 'Lightning': 3}, 'Volibear_B04': {'Damage': 6, 'Block': 8}}
    for card in before:
        _need(_equal(card, dict(cardRef=card['cardRef'], modelId=card['nativeType'].upper(),
                               nativeType=card['nativeType'], upgrade=False, cost=1, shape='None',
                               vars=expected_vars[card['nativeType']])))
    return {c['cardRef']: c for c in before}


def _f01(result, masters):
    data = result['data']
    _need(type(data) is dict and set(data) == {'rows', 'voidControl'})
    rows = data['rows']
    _need(type(rows) is list and len(rows) == 7)
    specs = [
        ('starter-claw', 'Volibear_B01', 'Attack', 'AnyEnemy', 1, {'Damage': 6}, 'Claw', False, True, False, False, []),
        ('native-bash', 'Bash', 'Attack', 'AnyEnemy', 2, {'Damage': 8, 'VulnerablePower': 2}, 'Claw', False, False, False, False, []),
        ('native-defend', 'DefendIronclad', 'Skill', 'Self', 1, {'Block': 5}, 'Body', False, False, False, False, []),
        ('native-power', 'Inflame', 'Power', 'Self', 1, {'StrengthPower': 3}, 'Body', True, False, False, False, []),
        ('native-status', 'Void', 'Status', 'None', -1, {'Energy': 1}, 'Body', False, False, True, False, ['Ethereal', 'Unplayable']),
        ('native-curse', 'Injury', 'Curse', 'None', -1, {}, 'Body', False, False, False, False, ['Unplayable']),
        ('native-x', 'Whirlwind', 'Attack', 'AllEnemies', 0, {'Damage': 5}, 'Claw', False, False, False, True, []),
    ]
    owner, count, cost_refs, changes = None, 0, [], []
    for row, spec in zip(rows, specs):
        name, native, card_type, target, cost, variables, shape, upgraded, retain, draw, costs_x, keywords = spec
        _need(type(row) is dict and set(row) == set('name before returnedShape afterMaterial newEntity conversionHistory afterConversion drawCalls beforeDrawEnergy afterDrawEnergy afterDraw play'.split()))
        master = row['before']['masterRef'] if name == 'starter-claw' else None
        if name == 'starter-claw':
            _need(master in masters and masters[master]['nativeType'] == 'Volibear_B01' and master != name)
        before = _original(row['before'], name, native, card_type, target, cost, variables,
                           upgrade=upgraded, retain=retain, keywords=keywords, costs_x=costs_x,
                           master=master, pile='Draw' if draw else 'Hand', owner=owner)
        owner = before['ownerRef']
        cost_refs.extend([before['costObjectRef'], row['afterConversion']['costObjectRef']])
        _need(_equal(row['name'], name) and _equal(row['returnedShape'], shape))
        _need(_equal(row['afterConversion'], _form(before, row['afterConversion'], shape=shape, upgraded=upgraded, retain=retain,
                                                   pile='Draw' if draw else 'Hand')))
        _conversion(before, row['afterMaterial'], row['afterConversion'], row['conversionHistory'], row['newEntity'])
        _need(_equal(row['drawCalls'], int(draw)) and _equal(row['beforeDrawEnergy'], 3) and _equal(row['afterDrawEnergy'], 3))
        _need(_equal(row['afterDraw'], _form(before, row['afterConversion'], shape=shape, upgraded=upgraded, retain=retain)))
        _play(row['play'], _form(before, row['afterConversion'], shape=shape, upgraded=upgraded, retain=retain, pile='Exhaust'),
              result['enemyIds'], shape=shape, upgraded=upgraded, count=count)
        count += shape == 'Body'
        changes.append(dict(cardRef=name + '-beast', shape=shape, ownerRef=owner, sameCombat=True))
    control = data['voidControl']
    _need(type(control) is dict and set(control) == {'beforeEnergy', 'afterEnergy', 'restoredEnergy', 'drawCalls', 'snapshot'})
    _need(all(_equal(control[key], value) for key, value in dict(beforeEnergy=3, afterEnergy=2, restoredEnergy=3, drawCalls=1).items()))
    original = _original(control['snapshot'], 'native-void-control', 'Void', 'Status', 'None', -1,
                         {'Energy': 1}, keywords=['Ethereal', 'Unplayable'], owner=owner)
    cost_refs.append(original['costObjectRef'])
    _need(len(set(cost_refs)) == len(cost_refs))
    _need(_equal(result['changes'], changes))


def _f02(result):
    data = result['data']
    keys = set('before firstShape afterMaterial newEntity conversionHistory afterConversion secondShape sameOnRepeat repeatHistory afterRepeat afterNewSet firstPlay recycled afterUpgrade afterZero upgradedPlay beforeTurn afterTurn roundBefore turnBefore roundAfter turnAfter energyAfterTurn hpAfterTurn'.split())
    _need(type(data) is dict and set(data) == keys)
    before = _original(data['before'], 'native-bludgeon', 'Bludgeon', 'Attack', 'AnyEnemy', 3,
                       {'Damage': 32}, retain=True, keywords=['Retain'], local=2)
    _need(_equal(data['firstShape'], 'Claw') and _equal(data['secondShape'], 'Claw'))
    def form(**kwargs):
        return _form(before, data['afterConversion'], retain=True, local_retain=True, **kwargs)
    for key, expected in {
        'afterConversion': form(cost=0), 'afterRepeat': form(cost=0), 'afterNewSet': form(cost=1),
        'recycled': form(), 'afterUpgrade': form(upgraded=True), 'afterZero': form(upgraded=True, cost=0),
        'beforeTurn': form(upgraded=True, cost=0), 'afterTurn': form(upgraded=True),
    }.items():
        _need(_equal(data[key], expected))
    _conversion(before, data['afterMaterial'], data['afterConversion'], data['conversionHistory'], data['newEntity'])
    _need(_equal(data['sameOnRepeat'], True) and _equal(data['repeatHistory'], dict(exhausted=[], generated=[])))
    _play(data['firstPlay'], form(pile='Exhaust'), result['enemyIds'])
    _play(data['upgradedPlay'], form(upgraded=True, pile='Exhaust'), result['enemyIds'], upgraded=True)
    for key, expected in dict(roundBefore=1, turnBefore=1, roundAfter=2, turnAfter=2,
                              energyAfterTurn=3, hpAfterTurn=80).items():
        _need(_equal(data[key], expected))
    _need(_equal(result['changes'], [dict(cardRef='native-bludgeon-beast', shape='Claw', ownerRef=before['ownerRef'], sameCombat=True)]))


def validate_beast_result(result, run_id, variant):
    """Return bool for a parsed current-run report; no flag-only success path."""
    try:
        _need(variant in BEAST_CASES and type(result) is dict and type(run_id) is str and bool(run_id))
        required = dict(token=run_id, scenario='beast-contract', variant=variant, completed=True,
                        testMode=False, acceptance='effect-only-not-payment', character='VolibearCharacter',
                        gameVersion='v0.107.1', gameCommit='59260271',
                        fixtureApi='CombatState.CreateCard;CardPileCmd.Add;CardCmd.Upgrade;CreatureCmd.SetMaxAndCurrentHp',
                        api='BeastForms.Convert;CardCmd.Exhaust;CardPileCmd.AddGeneratedCardToCombat;CardCmd.AutoPlay;CardPileCmd.Draw;PlayerCmd.EndTurn')
        _need(set(result) == set(required) | {'enemyIds', 'enemyTypes', 'deckBefore', 'deckAfter', 'changes', 'data'})
        _need(all(_equal(result[key], value) for key, value in required.items()))
        ids, enemies = result['enemyIds'], result['enemyTypes']
        _need(type(ids) is list and len(ids) == 3 and all(type(i) is int and i >= 0 for i in ids) and len(set(ids)) == 3)
        _need(type(enemies) is list and len(enemies) == 3 and all(type(e) is str for e in enemies)
              and enemies.count('LeafSlimeS') == 1 and enemies.count('TwigSlimeS') == 1
              and sum(e in ('LeafSlimeM', 'TwigSlimeM') for e in enemies) == 1)
        masters = _deck(result)
        if variant == 'f01':
            _f01(result, masters)
        else:
            _f02(result)
        return True
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return False


def beast_contract_evidence(log, run_id, variant):
    """Headless-runner adapter: (parsed_report_or_None, independently_passed)."""
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1 or variant not in BEAST_CASES:
        return None, False
    try:
        result = json.loads(lines[0])
    except (json.JSONDecodeError, ValueError):
        return None, False
    return result, validate_beast_result(result, run_id, variant)
