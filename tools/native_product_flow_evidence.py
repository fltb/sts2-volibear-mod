"""Independent receipt oracle for an ordinary, unfaked seeded native run.

Parser fixtures test this validator; they are never native gameplay evidence.
The coordinator must additionally pass runtime, isolation, version and cleanup
checks for the same process. The flow covers early gameplay, not a full run win.
"""
from collections import Counter
import json
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX = '[Volibear] NATIVE_PRODUCT_FLOW_RESULT '
SCOPE = 'native-seeded-run-paid-actions-rewards-map-rest-shop'
KINDS = {'run-start', 'room', 'paid-action', 'end-turn', 'battle-win', 'selection',
         'card-reward-choice', 'reward', 'rest', 'shop', 'event', 'treasure',
         'map-choice', 'map-arrived'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value, minimum=0):
    return type(value) in (int, float) and value >= minimum


def deck(snapshot):
    return Counter((card['id'], card['upgrade']) for card in snapshot['deck'])


def state(value):
    need(isinstance(value, dict) and set(value) == {
        'character', 'seed', 'hp', 'maxHp', 'gold', 'floor', 'act', 'room', 'energy',
        'shouldSave', 'deck', 'relics'}, 'native state shape')
    need(value['character'] == 'VOLIBEAR_CHARACTER' and value['seed'] == 'VOLIBEAR-PRODUCT-FLOW' and value['shouldSave'] is False,
         'ordinary Volibear run identity / isolated non-saving mode')
    need(number(value['hp'], 1) and number(value['maxHp'], 1) and value['hp'] <= value['maxHp']
         and integer(value['gold']) and integer(value['floor']) and integer(value['act'])
         and isinstance(value['room'], str) and value['room'], 'native run state values')
    need(value['energy'] is None or number(value['energy']), 'native energy value')
    need(isinstance(value['deck'], list) and 0 < len(value['deck']) <= 1000
         and all(isinstance(c, dict) and set(c) == {'id', 'upgrade'} and
                 isinstance(c['id'], str) and c['id'] and integer(c['upgrade']) for c in value['deck']),
         'native deck card identities')
    need(isinstance(value['relics'], list) and value['relics'] and
         all(isinstance(r, str) and r for r in value['relics']), 'native relic identities')


def validate(raw, token, pid):
    need(isinstance(raw, dict) and set(raw) == {
        'schema', 'token', 'pid', 'gameVersion', 'gameCommit', 'scope', 'osInput',
        'simulatedClicks', 'stateFixtures', 'testMode', 'rewardDecisionBoundary', 'outcome', 'error', 'events'}, 'flow receipt shape')
    need(type(raw['schema']) is int and raw['schema'] == 1 and token and raw['token'] == token
         and integer(pid, 1) and type(raw['pid']) is int and raw['pid'] == pid, 'flow invocation binding')
    need(raw['gameVersion'] == '0.107.1' and raw['gameCommit'] == EXPECTED_GAME_COMMIT, 'flow pinned game build')
    need(raw['scope'] == SCOPE and raw['osInput'] is False and raw['simulatedClicks'] is False
         and raw['stateFixtures'] is False and raw['testMode'] is False,
         'flow cannot claim input simulation, TestMode or injected gameplay state')
    need(raw['rewardDecisionBoundary'] == 'NCardRewardSelectionScreen.OptionSelected',
         'actual native reward decision boundary required; Selector alone cannot drive this screen')
    need(raw['outcome'] == 'completed' and raw['error'] is None, 'flow did not complete normally')
    events = raw['events']
    need(isinstance(events, list) and 1 <= len(events) <= 20000, 'finite native event stream')
    counts, pending_map, card_choices = Counter(), None, []
    for index, event in enumerate(events):
        need(isinstance(event, dict) and set(event) == {'seq', 'kind', 'data'} and
             type(event['seq']) is int and event['seq'] == index and event['kind'] in KINDS
             and isinstance(event['data'], dict), 'ordered native event shape')
        kind, data = event['kind'], event['data']
        counts[kind] += 1
        if kind in ('run-start', 'room'):
            state(data)
        for key in ('before', 'after', 'state'):
            if key in data and isinstance(data[key], dict):
                state(data[key])
        if kind == 'run-start':
            need(index == 0 and data['hp'] == data['maxHp'] == 80 and data['gold'] == 99
                 and data['relics'] == ['VOLIBEAR_HUNTERS_HEART'] and deck(data) == Counter({
                     ('VOLIBEAR_B01', 0): 4, ('VOLIBEAR_B02', 0): 4,
                     ('VOLIBEAR_B03', 0): 1, ('VOLIBEAR_B04', 0): 1}), 'unmodified native starter run')
        elif kind == 'paid-action':
            need(data['type'] == 'PlayCardAction' and data['state'] == 'Finished' and
                 data['context'] == 'GameActionPlayerChoiceContext' and data['exception'] is None
                 and integer(data['actionId']) and isinstance(data['id'], str), 'native paid action contract')
            plays, spent = data['history']['plays'], data['history']['energy']
            need(isinstance(plays, list) and plays and isinstance(spent, list) and all(number(e) for e in spent),
                 'native payment history')
            need(all(isinstance(p, dict) and set(p) == {'id', 'autoPlay', 'spent', 'index', 'count'}
                     and isinstance(p['id'], str) and type(p['autoPlay']) is bool and number(p['spent'])
                     and integer(p['index']) and integer(p['count'], 1) for p in plays), 'native card play history shape')
            source = [p for p in plays if p['id'] == data['id'] and p['autoPlay'] is False]
            need(source, 'queued action did not produce a non-autoplay source card')
            # Energy-changing cards/relics make final-energy arithmetic insufficient;
            # native energy history is the payment witness, including genuine zero cost.
            # Echoed/repeated play entries share the original paid resources.
            paid = max(p['spent'] for p in source)
            need(paid == 0 or sum(spent) >= paid, 'paid energy missing from native history')
        elif kind == 'battle-win':
            need(integer(data['number'], 1) and data['number'] == counts[kind] and
                 isinstance(data['encounter'], str) and data['encounter'], 'native combat victory sequence')
        elif kind == 'selection':
            need(integer(data['min']) and integer(data['max']) and data['min'] <= data['max'] and
                 isinstance(data['available'], list) and isinstance(data['selected'], list) and
                 data['min'] <= len(data['selected']) <= data['max'] and
                 not (Counter(data['selected']) - Counter(data['available'])), 'native selection membership / cardinality')
        elif kind == 'card-reward-choice':
            need(isinstance(data['available'], list) and data['available'] and data['selected'] in data['available'],
                 'native reward candidate membership')
            card_choices.append(data['selected'])
        elif kind == 'reward':
            need(data['selected'] is True and data['nativeSelected'] is True, 'native synchronized reward commit')
            if data['type'] == 'CardReward':
                added = deck(data['after']) - deck(data['before'])
                need(card_choices and sum(added.values()) == 1 and not (deck(data['before']) - deck(data['after']))
                     and next(iter(added))[0] == card_choices.pop(0), 'selected reward card absent from master deck')
                counts['committed-card-reward'] += 1
        elif kind == 'shop':
            need(data['type'] == 'MerchantCardEntry' and data['bought'] is True and data['stockedBefore'] is True
                 and integer(data['cost'], 1) and data['before']['gold'] - data['after']['gold'] == data['cost'],
                 'native shop purchase / exact gold payment')
            need(sum((deck(data['after']) - deck(data['before'])).values()) == 1 and
                 not (deck(data['before']) - deck(data['after'])), 'native purchased card absent from master deck')
        elif kind == 'rest':
            need(data['ok'] is True and integer(data['index']) and isinstance(data['available'], list)
                 and all(integer(i) for i in data['available']) and data['index'] in data['available'], 'native rest option')
            if data['option'] == 'HEAL':
                need(data['after']['hp'] > data['before']['hp'], 'native rest did not heal')
            elif data['option'] == 'SMITH':
                before, after = data['before']['deck'], data['after']['deck']
                need(Counter(c['id'] for c in before) == Counter(c['id'] for c in after) and
                     sum(c['upgrade'] for c in after) > sum(c['upgrade'] for c in before), 'native smith did not upgrade')
            else:
                raise ValueError('required normal rest coverage must heal or smith')
        elif kind == 'map-choice':
            need(pending_map is None and integer(data['act']) and integer(data['row']) and integer(data['col'])
                 and isinstance(data['legal'], list) and {'row': data['row'], 'col': data['col']} in data['legal'],
                 'native map choice must be a reachable enabled child')
            pending_map = (data['act'], data['row'], data['col'])
        elif kind == 'map-arrived':
            need(pending_map == (data['act'], data['row'], data['col']), 'native map vote did not reach its selected room')
            pending_map = None
    need(counts['run-start'] == 1 and counts['paid-action'] >= 1 and counts['battle-win'] >= 3
         and counts['committed-card-reward'] >= 1 and counts['rest'] >= 1 and counts['shop'] >= 1
         and counts['map-arrived'] >= 5 and pending_map is None and not card_choices,
         'ordinary run is missing required combat / reward / map / rest / shop evidence')
    return dict(counts)


def check_log(log, token, pid):
    errors, raw, counts = [], None, {}
    try:
        lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
        need(len(lines) == 1, 'exactly one native product flow receipt required')
        raw = json.loads(lines[0])
        counts = validate(raw, token, pid)
    except (ValueError, TypeError, KeyError, IndexError, StopIteration) as error:
        errors.append(str(error))
    return {'errors': errors, 'counts': counts, 'raw': raw, 'scope': SCOPE}
