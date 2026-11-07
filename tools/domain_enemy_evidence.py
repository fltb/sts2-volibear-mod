"""Independent exact-value gate for the native Domain enemy mechanism probe.

This is not a native enemy coverage claim. Expected inputs/outputs below come from
pinned power semantics and explicit fixture constants, never a producer passed flag.
The shared runner remains responsible for isolation, exit status and engine errors.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = '[Volibear] DOMAIN_ENEMY_RESULT '
VARIANTS = ('flutter', 'soar', 'intangible', 'slippery', 'hard-to-kill', 'shell',
            'artifact', 'thorns', 'reflect', 'heal')


def _snapshot(**overrides):
    value = dict(enemyHp=1000, enemyMaxHp=1000, enemyBlock=0, enemyPower=0,
                 enemyPowerDisplay=0, enemyWeak=0, enemyArtifact=0, playerHp=80,
                 playerMaxHp=80, playerBlock=0, playerPower=0, playerWeak=0,
                 playerArtifact=0, domain=0, round=1, turn=1, active=False,
                 enemyAttached=True, playerAttached=True, samePowerInstance=True)
    value.update(overrides)
    return value


def expected_steps(variant: str):
    """Declarative oracle for controlled native-command inputs, not game execution."""
    if variant not in VARIANTS:
        raise ValueError('Unknown domain enemy variant: ' + str(variant))
    rows = []

    def row(name, before, after, *, amount=8, props=4, target='enemy',
            api='CreatureCmd.Damage', blocked=0, hp=None):
        damage = api == 'CreatureCmd.Damage'
        if damage and hp is None:
            hp = before[target + 'Hp'] - after[target + 'Hp']
        rows.append(dict(id=name, api=api, amount=amount, props=props, target=target,
                         source=None if api == 'CreatureCmd.Heal' else ('player' if target == 'enemy' else 'enemy'),
                         before=before, after=after,
                         hit=None if not damage else dict(hpLost=hp, blocked=blocked, overkill=0)))

    def snap(power=0, hp=1000, player_hp=80, domain=0, **kw):
        return _snapshot(enemyPower=power, enemyPowerDisplay=power, enemyHp=hp,
                         playerHp=player_hp, domain=domain, active=domain > 0, **kw)

    def next_turn(before, after):
        row('next-turn', before, after, amount=0, props=0, target='player', api='PlayerCmd.EndTurn')
        rows[-1]['source'] = 'player'

    if variant in ('flutter', 'soar', 'slippery', 'hard-to-kill'):
        power, reduced, final_power = {'flutter': (5, 4, 3), 'soar': (1, 4, 1),
                                       'slippery': (5, 1, 3), 'hard-to-kill': (3, 3, 3)}[variant]
        middle = power - 1 if variant in ('flutter', 'slippery') else power
        props = 8 if variant in ('flutter', 'soar') else 4
        row('off', snap(power), snap(middle, 1000 - reduced), props=props)
        row('on', snap(middle, 1000 - reduced, domain=2), snap(final_power, 992 - reduced, domain=2), props=props)
    elif variant == 'intangible':
        row('off-block', snap(3, enemyBlock=5), snap(3, enemyBlock=4), amount=10, blocked=1, hp=0)
        row('on-block', snap(3, domain=2, enemyBlock=5), snap(3, 995, domain=2), amount=10, blocked=5, hp=5)
        row('off-hp', snap(3, 995), snap(3, 994), amount=10, hp=1)
        row('on-hp', snap(3, 994, domain=2), snap(3, 984, domain=2), amount=10, hp=10)
        next_turn(snap(3, 984, domain=2, playerBlock=100), snap(2, 984, domain=1, round=2, turn=2))
        row('player-control', snap(2, 984, domain=1, round=2, turn=2, playerPower=2),
            snap(2, 984, player_hp=79, domain=1, round=2, turn=2, playerPower=2), target='player', hp=1)
    elif variant == 'shell':
        def shell(hp, display, domain=0, **kw):
            return _snapshot(enemyPower=5, enemyPowerDisplay=display, enemyHp=hp,
                             domain=domain, active=domain > 0, **kw)
        row('off', shell(1000, 5), shell(995, 0), hp=5)
        row('on', shell(995, 0, 2), shell(987, 0, 2), hp=8)
        row('expired-quota', shell(987, 0), shell(987, 0), hp=0)
        next_turn(shell(987, 0, playerBlock=100), shell(987, 5, round=2, turn=2))
        row('reset-quota', shell(987, 5, round=2, turn=2), shell(982, 0, round=2, turn=2), hp=5)
    elif variant == 'artifact':
        def artifact(power, domain=0, **kw):
            return snap(power, domain=domain, enemyArtifact=power, **kw)
        row('off', artifact(3), artifact(2), amount=2, props=0, api='PowerCmd.Apply:WeakPower')
        row('on', artifact(2, 2), artifact(2, 2, enemyWeak=2), amount=2, props=0, api='PowerCmd.Apply:WeakPower')
        row('player-control', artifact(2, 2, enemyWeak=2, playerArtifact=3, playerPower=3),
            artifact(2, 2, enemyWeak=2, playerArtifact=2, playerPower=2),
            amount=2, props=0, target='player', api='PowerCmd.Apply:WeakPower')
        row('restored', artifact(2, playerArtifact=2, playerPower=2),
            artifact(1, playerArtifact=2, playerPower=2), amount=2, props=0, api='PowerCmd.Apply:WeakPower')
    elif variant == 'thorns':
        row('off', snap(3), snap(3, 992, 77), props=8)
        row('on', snap(3, 992, 77, 2), snap(3, 984, 77, 2), props=8)
        row('restored', snap(3, 984, 77), snap(3, 976, 74), props=8)
    elif variant == 'reflect':
        row('off', snap(3, enemyBlock=5), snap(3, 997, 75), props=8, blocked=5, hp=3)
        row('on', snap(3, 997, 75, 2, enemyBlock=5), snap(3, 994, 75, 2), props=8, blocked=5, hp=3)
        next_turn(snap(3, 994, 75, 2, playerBlock=100), snap(2, 994, 75, 1, round=2, turn=2))
        row('restored', snap(2, 994, 75, enemyBlock=5, round=2, turn=2),
            snap(2, 991, 70, round=2, turn=2), props=8, blocked=5, hp=3)
    elif variant == 'heal':
        row('enemy-off', snap(hp=500, player_hp=40), snap(hp=507, player_hp=40),
            amount=7, props=0, api='CreatureCmd.Heal')
        row('player-off', snap(hp=507, player_hp=40), snap(hp=507, player_hp=47),
            amount=7, props=0, target='player', api='CreatureCmd.Heal')
        row('enemy-on', snap(hp=507, player_hp=47, domain=2), snap(hp=507, player_hp=47, domain=2),
            amount=7, props=0, api='CreatureCmd.Heal')
        row('player-on', snap(hp=507, player_hp=47, domain=2), snap(hp=507, player_hp=54, domain=2),
            amount=7, props=0, target='player', api='CreatureCmd.Heal')
    return rows


def validate(payload, token: str, variant: str) -> list[str]:
    """Return concrete failures; an empty list means raw probe evidence matched the oracle."""
    errors = []
    if not isinstance(payload, dict):
        return ['result must be an object']
    if not token or variant not in VARIANTS:
        return ['caller must provide nonempty run token and known variant']

    def equal(actual, expected, path):
        # bool is a subclass of int in Python: prohibit false-as-0 evidence.
        same_type = type(actual) is type(expected) or (type(actual) in (int, float) and type(expected) in (int, float))
        if not same_type or actual != expected:
            errors.append(f'{path}: expected {expected!r}, observed {actual!r}')

    for key, expected in dict(schema=1, token=token, scenario='domain-enemy-contract', variant=variant,
            acceptance='mechanism-probe-not-native-enemy-coverage', testMode=False,
            version=EXPECTED_GAME_VERSION, commit=EXPECTED_GAME_COMMIT, enemyType='LeafSlimeS',
            fixtureApi='native-PowerCmd+CreatureCmd;starting-LeafSlimeS;no-replaced-actions').items():
        equal(payload.get(key), expected, key)
    start = payload.get('start')
    if not isinstance(start, dict):
        return errors + ['missing raw start snapshot']
    ids = {side: start.get(side + 'Id') for side in ('enemy', 'player')}
    if any(not isinstance(value, str) or not value.isdecimal() for value in ids.values()) or ids['enemy'] == ids['player']:
        errors.append('distinct numeric native enemy/player identities required')
    for key, value in _snapshot().items():
        equal(start.get(key), value, 'start.' + key)
    actual_steps = payload.get('steps')
    expected = expected_steps(variant)
    if not isinstance(actual_steps, list) or len(actual_steps) != len(expected):
        return errors + [f'steps: expected exactly {len(expected)} ordered steps']
    for index, (step, want) in enumerate(zip(actual_steps, expected)):
        where = f'steps[{index}]({want["id"]})'
        if not isinstance(step, dict):
            errors.append(where + ': must be an object')
            continue
        for key in ('id', 'api', 'amount', 'props'):
            equal(step.get(key), want[key], where + '.' + key)
        equal(step.get('targetId'), ids[want['target']], where + '.targetId')
        equal(step.get('sourceId'), None if want['source'] is None else ids[want['source']], where + '.sourceId')
        for phase in ('before', 'after'):
            snapshot = step.get(phase)
            if not isinstance(snapshot, dict):
                errors.append(where + '.' + phase + ': missing raw snapshot')
                continue
            for key, value in want[phase].items():
                equal(snapshot.get(key), value, where + '.' + phase + '.' + key)
            for side in ('enemy', 'player'):
                equal(snapshot.get(side + 'Id'), ids[side], where + '.' + phase + '.' + side + 'Id')
        results = step.get('results')
        if want['hit'] is None:
            equal(results, [], where + '.results')
        elif not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
            errors.append(where + ': exactly one native damage result required')
        else:
            equal(results[0].get('receiverId'), ids[want['target']], where + '.receiverId')
            for key, value in want['hit'].items():
                equal(results[0].get(key), value, where + '.' + key)
    return errors


def check_log(text: str, token: str, variant: str) -> dict:
    matches = [line.split(MARKER, 1)[1] for line in text.splitlines() if MARKER in line]
    if len(matches) != 1:
        return dict(passed=False, errors=['exactly one DOMAIN_ENEMY_RESULT required'], result=None)
    try:
        payload = json.loads(matches[0])
    except (ValueError, TypeError) as error:
        return dict(passed=False, errors=['invalid result JSON: ' + str(error)], result=None)
    errors = validate(payload, token, variant)
    if '[Volibear] DOMAIN_ENEMY_ERROR' in text:
        errors.append('native probe emitted DOMAIN_ENEMY_ERROR')
    shutdown = '[Volibear] SHUTDOWN_BEGIN ' + token
    if sum(line.strip() == shutdown for line in text.splitlines()) != 1:
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
