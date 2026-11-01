"""Exact raw-evidence gate for native summon/death probes, not full enemy coverage.

No producer passed/completed flag is trusted. The launcher must separately enforce
isolation, pinned deploy, exit/error policy and its own current run token.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

MARKER = '[Volibear] DOMAIN_SUMMON_RESULT '
VARIANTS = ('fabricator-off', 'fabricator-on', 'ovicopter-off', 'ovicopter-on',
            'infested-off', 'infested-on', 'infested-expire')


def validate(payload, token: str, variant: str) -> list[str]:
    errors = []
    if not isinstance(payload, dict) or not token or variant not in VARIANTS:
        return ['object payload/current token/known variant required']
    family = variant.split('-')[0]
    on = not variant.endswith('-off')
    expire = variant == 'infested-expire'
    domain = 2 if on else 0
    parent_type, encounter, slot = {
        'fabricator': ('Fabricator', 'FabricatorNormal', 'fabricator'),
        'ovicopter': ('Ovicopter', 'OvicopterNormal', 'ovicopter'),
        'infested': ('PhrogParasite', 'PhrogParasiteElite', 'phrog')}[family]

    def eq(actual, expected, path):
        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(actual) != set(expected): errors.append(path + ': exact raw fields required')
            for key, value in expected.items(): eq(actual.get(key), value, path + '.' + key)
            return
        if isinstance(expected, list) and isinstance(actual, list):
            if len(actual) != len(expected): errors.append(path + ': exact raw receipt count required')
            for index, (got, want) in enumerate(zip(actual, expected)): eq(got, want, path + f'[{index}]')
            return
        typed = type(actual) is type(expected) or (type(actual) in (int, float) and type(expected) in (int, float))
        if not typed or actual != expected:
            errors.append(f'{path}: expected {expected!r}, observed {actual!r}')

    def require(condition, path):
        if not condition: errors.append(path)

    for key, value in dict(schema=1, token=token, scenario='domain-summon-contract', variant=variant,
            acceptance='native-mechanism-probe-not-complete-enemy-coverage', testMode=False,
            version='v0.107.1', commit='59260271', encounter=encounter, parentType=parent_type,
            fixtureHp=100, fixtureApi='CreatureCmd.SetMaxAndCurrentHp').items():
        eq(payload.get(key), value, key)
    data = payload.get('data')
    if not isinstance(data, dict): return errors + ['missing raw data object']
    before, after = data.get('before'), data.get('after')
    if not isinstance(before, dict) or not isinstance(after, dict):
        return errors + ['missing raw before/after snapshots']
    parent_id, player_id = before.get('parentId'), before.get('playerId')
    require(all(isinstance(v, str) and v.isdecimal() for v in (parent_id, player_id)) and parent_id != player_id,
            'distinct numeric native parent/player identities required')
    for phase, snapshot in (('before', before), ('after', after)):
        death_after = family == 'infested' and phase == 'after'
        values = dict(parentId=parent_id, playerId=player_id, parentHp=0 if death_after else 100,
            parentMaxHp=100, parentAttached=not death_after,
            parentInfested=4 if family == 'infested' and not death_after else 0,
            playerHp=62 if family == 'fabricator' and phase == 'after' else 80,
            playerBlock=0, domain=0 if expire and phase == 'after' else domain,
            inProgress=True, isEnding=death_after and on, round=1, side='Player')
        for key, value in values.items(): eq(snapshot.get(key), value, phase + '.' + key)
        if not isinstance(snapshot.get('enemies'), list):
            return errors + [phase + '.enemies must be raw array']
    eq(len(before['enemies']), 1, 'initial actual enemy count')
    child_count = 0 if on else {'fabricator': 1, 'ovicopter': 3, 'infested': 4}[family]
    expected_after_count = child_count + (0 if family == 'infested' else 1)
    eq(len(after['enemies']), expected_after_count, 'after actual enemy count')

    def parent_row(row, phase):
        if not isinstance(row, dict):
            errors.append(phase + ': missing native parent row'); return
        values = dict(id=parent_id, type=parent_type, slot=slot, hp=100, maxHp=100,
            block=0, minion=0, infested=4 if family == 'infested' else 0, hatch=0, startStunned=None)
        for key, value in values.items(): eq(row.get(key), value, phase + '.' + key)
        legal = {'fabricator': ('FABRICATE_MOVE', 'FABRICATING_STRIKE_MOVE'),
                 'ovicopter': ('LAY_EGGS_MOVE',), 'infested': ('INFECT_MOVE',)}[family]
        require(row.get('nextMove') in legal, phase + ': expected actual legal native move')
    if len(before['enemies']) == 1: parent_row(before['enemies'][0], 'before.parent')
    if family != 'infested':
        parents = [row for row in after['enemies'] if isinstance(row, dict) and row.get('id') == parent_id]
        eq(len(parents), 1, 'same parent retained')
        if len(parents) == 1:
            parent_row(parents[0], 'after.parent')
            eq(parents[0].get('nextMove'), 'FABRICATING_STRIKE_MOVE' if family == 'fabricator' else 'LAY_EGGS_MOVE',
               'parent selected move after native PerformMove before roll')
    children = [row for row in after['enemies'] if isinstance(row, dict) and row.get('id') != parent_id]
    eq(len(children), child_count, 'native children count')
    ids = [row.get('id') for row in after['enemies'] if isinstance(row, dict)]
    require(len(ids) == len(after['enemies']) and all(isinstance(v, str) and v.isdecimal() for v in ids)
            and len(set(ids)) == len(ids) and player_id not in ids, 'unique actual enemy/child identities required')
    child_slots = []
    for index, child in enumerate(children):
        prefix = f'child[{index}]'
        typ = child.get('type')
        allowed = {'fabricator': ('Zapbot', 'Stabbot'), 'ovicopter': ('ToughEgg',), 'infested': ('Wriggler',)}[family]
        require(typ in allowed, prefix + ': wrong native child type')
        for key, value in dict(block=0, minion=0 if family == 'infested' else 1, infested=0,
                hatch=1 if family == 'ovicopter' else 0, startStunned=True if family == 'infested' else None).items():
            eq(child.get(key), value, prefix + '.' + key)
        hp_min, hp_max = {'fabricator': (18, 23), 'ovicopter': (14, 18), 'infested': (17, 21)}[family]
        hp = child.get('hp')
        require(type(hp) is int and hp_min <= hp <= hp_max, prefix + ': native HP range')
        eq(child.get('maxHp'), hp, prefix + '.maxHp')
        next_move = {'Zapbot': 'ZAP', 'Stabbot': 'STAB_MOVE', 'ToughEgg': 'HATCH_MOVE', 'Wriggler': 'SPAWNED_MOVE'}.get(typ)
        eq(child.get('nextMove'), next_move, prefix + '.nextMove')
        child_slots.append(child.get('slot'))
    if children:
        if family == 'fabricator':
            require(child_slots[0] in ('bot1', 'bot2', 'bot3', 'bot4'), 'bot allocated native legal slot')
        else:
            eq(sorted(child_slots, key=str), ['egg3', 'egg4', 'egg5'] if family == 'ovicopter'
                else ['wriggler1', 'wriggler2', 'wriggler3', 'wriggler4'], 'native child slots')

    damage_expected = []
    if family == 'fabricator':
        damage_expected = [dict(sourceId=parent_id, receiverId=player_id, hpLost=18, blocked=0, overkill=0, cardSource=None)]
    elif family == 'infested':
        damage_expected = [dict(sourceId=player_id, receiverId=parent_id, hpLost=100, blocked=0, overkill=0, cardSource=None)]
    eq(data.get('damage'), damage_expected, 'actual native damage history')
    if family != 'infested':
        requested = 'FABRICATING_STRIKE_MOVE' if family == 'fabricator' else 'LAY_EGGS_MOVE'
        eq(data.get('api'), 'MonsterModel.PerformMove+MonsterModel.RollMove', 'api')
        eq(data.get('setup'), 'forced-existing-legal-reachable-FABRICATING_STRIKE_MOVE' if family == 'fabricator'
            else 'native-initial-LAY_EGGS_MOVE', 'setup disclosure')
        eq(data.get('selected'), requested, 'selected actual native move')
        eq(data.get('performingBefore'), False, 'native IsPerformingMove before')
        eq(data.get('performingAfter'), False, 'native IsPerformingMove completion')
        eq(data.get('moves'), [dict(sourceId=parent_id, move=requested, targets=[player_id])], 'native performed move history')
        if len(before['enemies']) == 1 and isinstance(before['enemies'][0], dict):
            eq(data.get('initialMove'), before['enemies'][0].get('nextMove'), 'raw initial move identity')
        require(data.get('nextMove') in (('FABRICATE_MOVE', 'FABRICATING_STRIKE_MOVE') if family == 'fabricator'
                else ('SMASH_MOVE',)), 'native follow-up move must advance without replacement')
        old_log, new_log = data.get('stateLogBefore'), data.get('stateLogAfter')
        require(isinstance(old_log, list) and isinstance(new_log, list) and len(new_log) == len(old_log) + 1
                and new_log[:-1] == old_log and new_log[-1] == data.get('nextMove'), 'native state log advance')
    else:
        eq(data.get('api'), 'CreatureCmd.Damage+native-Kill/AfterDeath+CombatManager.CheckWinCondition', 'api')
        eq(data.get('setup'), 'controlled-native-Died-domain-removal-not-natural-draw-expiry' if expire
            else 'native-PhrogParasite-InfestedPower', 'setup disclosure')
        eq(data.get('input'), dict(amount=100, props=6, sourceId=player_id, targetId=parent_id), 'fixed native lethal input')
        eq(data.get('results'), [dict(receiverId=parent_id, hpLost=100, blocked=0, overkill=0)], 'native lethal DamageResult')
        eq(data.get('moves'), [], 'death must not counterfeit a performed monster move')
        eq(data.get('diedReceipts'), [dict(targetId=parent_id, sameParent=True, hp=0,
            domainBefore=domain, domainAfter=0 if expire else domain, removedByFixture=expire)], 'actual Died boundary receipt')
        receipts = data.get('callbackReceipts')
        if not isinstance(receipts, list) or len(receipts) != 1 or not isinstance(receipts[0], dict):
            errors.append('exactly one ACTUAL native Infested callback receipt required; unhit async detour is failure')
        else:
            for key, value in dict(ownerId=parent_id, targetId=parent_id, prevented=False, ownerHp=0,
                    attached=True, infested=4, domain=0 if expire else domain, isEnding=on).items():
                eq(receipts[0].get(key), value, 'actual Infested boundary.' + key)
            if on: eq(receipts[0].get('taskCompleted'), True, 'cancelled callback completed without spawning')
            else: require(type(receipts[0].get('taskCompleted')) is bool, 'baseline native task completion observation')
        eq(data.get('winResult'), on, 'native CheckWinCondition result')
        eq(data.get('wonCount'), 1 if on else 0, 'actual CombatWon event count')
        eq(data.get('endedCount'), 1 if on else 0, 'actual CombatEnded event count')
        eq(data.get('finalInProgress'), not on, 'combat must not remain stuck after cancelled death summon')
        eq(data.get('finalEnemies'), after['enemies'], 'no delayed summon replay across actual combat-end check')
    return errors


def check_log(text: str, token: str, variant: str) -> dict:
    matches = [line.split(MARKER, 1)[1] for line in text.splitlines() if MARKER in line]
    if len(matches) != 1: return dict(passed=False, errors=['exactly one DOMAIN_SUMMON_RESULT required'], result=None)
    try:
        payload = json.loads(matches[0])
    except (ValueError, TypeError) as error:
        return dict(passed=False, errors=['invalid JSON: ' + str(error)], result=None)
    errors = validate(payload, token, variant)
    if '[Volibear] DOMAIN_SUMMON_ERROR' in text: errors.append('native probe emitted DOMAIN_SUMMON_ERROR')
    if sum(line.strip() == '[Volibear] SHUTDOWN_BEGIN ' + token for line in text.splitlines()) != 1:
        errors.append('exactly one matching shutdown marker required')
    return dict(passed=not errors, errors=errors, result=payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--token', required=True)
    parser.add_argument('--variant', required=True, choices=VARIANTS)
    args = parser.parse_args()
    result = check_log(args.log.read_text(encoding='utf-8'), args.token, args.variant)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
