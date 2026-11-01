"""Strict raw native relic-chain/engage comparator; never dialogue/payment acceptance."""
import json
from collections import Counter

PREFIX = '[Volibear] RELIC_CONTRACT_RESULT '
RELIC_CASES = ('RH-starter-turns', 'RH-upgrade-turns', 'RH-starter-death', 'RH-upgrade-death')
ACCEPTANCE = 'native-upgrade-chain-effects-not-orobas-dialogue-not-payment'


def _need(value):
    if not value:
        raise ValueError('Relic observation violates native fixture oracle')


def _eq(a, b):
    if type(b) in (int, float):
        return type(a) in (int, float) and a == b
    if type(a) is not type(b):
        return False
    if isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], v) for k, v in b.items())
    if isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    return a == b


def validate_relic_result(r, token, variant):
    try:
        _need(variant in RELIC_CASES and type(token) is str and bool(token.strip()))
        fixed = dict(token=token, scenario='relic-contract', variant=variant, completed=True,
                     gameVersion='v0.107.1', gameCommit='59260271', testMode=False,
                     acceptance=ACCEPTANCE, character='VolibearCharacter')
        _need(type(r) is dict and set(r) == set(fixed) | set('enemyIds enemyTypes playerId cards generated sourceCardRef initialRelics upgrade finalRelics steps transition'.split()))
        _need(all(_eq(r[k], v) for k, v in fixed.items()))
        ids, types = r['enemyIds'], r['enemyTypes']
        _need(type(ids) is list and len(ids) == 3 and all(type(x) is int and x >= 0 for x in ids) and len(set(ids)) == 3)
        _need(type(types) is list and len(types) == 3 and types.count('LeafSlimeS') == types.count('TwigSlimeS') == 1
              and sum(x in ('LeafSlimeM', 'TwigSlimeM') for x in types) == 1)
        player = r['playerId']
        _need(type(player) is int and player >= 0 and player not in ids)
        first, second = ids[types.index('LeafSlimeS')], ids[types.index('TwigSlimeS')]
        third = next(x for x in ids if x not in (first, second))
        cards = r['cards']
        _need(type(cards) is list and len(cards) == 10)
        lookup, masters, combat_ids = {}, [], set()
        for row in cards:
            _need(type(row) is dict and set(row) == {'cardRef', 'modelId', 'masterIndex', 'masterModelId', 'combatCardIndex', 'sameObject', 'ownerId'})
            native_id = row['combatCardIndex']
            _need(type(native_id) is int and native_id >= 0 and native_id not in combat_ids)
            combat_ids.add(native_id)
            _need(row['sameObject'] is True and _eq(row['ownerId'], player))
            ref = row['cardRef']
            _need(type(ref) is int and ref > 0 and ref not in lookup)
            _need(type(row['masterIndex']) is int and 0 <= row['masterIndex'] < 10)
            _need(row['modelId'] == row['masterModelId'])
            lookup[ref] = row['modelId']; masters.append(row['masterIndex'])
        _need(set(masters) == set(range(10)))
        _need(Counter(lookup.values()) == Counter({'VOLIBEAR_B01': 4, 'VOLIBEAR_B02': 4, 'VOLIBEAR_B03': 1, 'VOLIBEAR_B04': 1}))
        _need(type(r['sourceCardRef']) is int and lookup[r['sourceCardRef']] == 'VOLIBEAR_B04')
        original_refs = set(lookup)
        generated = r['generated']
        medium_type = types[ids.index(third)]
        sticky_move = 'STICKY_SHOT' if medium_type == 'LeafSlimeM' else 'STICKY_SHOT_MOVE'
        expected_generated = (2 if medium_type == 'LeafSlimeM' else 1) if variant.endswith('turns') else 0
        _need(type(generated) is list and len(generated) == expected_generated)
        generated_refs = []
        for row in generated:
            ref, native_id = row['cardRef'], row['combatCardIndex']
            _need(type(ref) is int and ref > 0 and ref not in lookup)
            _need(type(native_id) is int and native_id >= 0 and native_id not in combat_ids)
            _need(_eq(row, dict(cardRef=ref, modelId='SLIMED', type='Slimed', cardType='Status',
                               combatCardIndex=native_id, sameObject=True, ownerId=player, masterModelId=None, masterIndex=-1,
                               sourceEnemy=third, sourceType=medium_type, sourceMove=sticky_move, pile='Discard', creatorId=None,
                               round=1, turn=1, side='Enemy')))
            combat_ids.add(native_id); generated_refs.append(ref); lookup[ref] = 'SLIMED'
        starter = [dict(type='HuntersHeart', modelId='VOLIBEAR_HUNTERS_HEART')]
        upgraded = [dict(type='ImmortalHeart', modelId='VOLIBEAR_IMMORTAL_HEART'), dict(type='TouchOfOrobas', modelId='TOUCH_OF_OROBAS')]
        _need(_eq(r['initialRelics'], starter))
        is_upgrade = 'upgrade' in variant
        if is_upgrade:
            _need(_eq(r['upgrade'], dict(setupSucceeded=True, selectedStarter='VOLIBEAR_HUNTERS_HEART',
                                         selectedUpgrade='VOLIBEAR_IMMORTAL_HEART', originalStillOwned=False, inventory=upgraded)))
        else:
            _need(r['upgrade'] is None)
        _need(_eq(r['finalRelics'], upgraded if is_upgrade else starter))
        amount = 2 if is_upgrade else 1

        def snapshot(s, turn, hp=None, block=None, alive=True):
            _need(type(s) is dict and set(s) == set('round turn hp block hand draw discard play exhaust'.split()))
            _need(_eq(s['round'], turn) and _eq(s['turn'], turn))
            _need(type(s['hp']) is int and (0 < s['hp'] <= 80 if alive else s['hp'] == 0))
            _need(type(s['block']) in (int, float) and s['block'] >= 0)
            if hp is not None: _need(_eq(s['hp'], hp))
            if block is not None: _need(_eq(s['block'], block))
            merged = []
            for pile in ('hand', 'draw', 'discard', 'play', 'exhaust'):
                _need(type(s[pile]) is list and all(type(c) is int and c in lookup for c in s[pile]))
                merged += s[pile]
            _need(len(merged) == len(set(merged)))
            expected_refs = original_refs if turn == 1 else set(lookup)
            _need(set(merged) == expected_refs if alive else set(merged) in (set(), expected_refs))
            _need(s['play'] == [] and s['exhaust'] == [])

        def draws(rows, expected, hand_draw=False):
            _need(_eq(rows, [dict(cardRef=c, modelId=lookup[c], fromHandDraw=hand_draw) for c in expected]))

        def step(s, label, target, turn, count, damage, performed=True, completed=True, block_before=100):
            _need(type(s) is dict and set(s) == set('label target before after result draws moves damage'.split()))
            _need(_eq(s['label'], label) and _eq(s['target'], target))
            before, after = s['before'], s['after']
            snapshot(before, turn, hp=80, block=block_before)
            snapshot(after, turn, hp=80, block=block_before - damage)
            _need(_eq(s['result'], dict(performed=performed, completed=completed, absorbed=damage)))
            expected = before['draw'][:count]
            _need(len(expected) == count)
            draws(s['draws'], expected)
            _need(_eq(after['hand'], before['hand'] + expected) and _eq(after['draw'], before['draw'][count:]) and _eq(after['discard'], before['discard']))
            _need(_eq(s['moves'], [dict(enemy=target, move='TACKLE_MOVE')] if performed else []))
            _need(_eq(s['damage'], [dict(target=player, playerTarget=True, hpLost=0, blocked=damage, props=8)] if performed else []))

        steps = r['steps']
        _need(type(steps) is list)
        if variant.endswith('turns'):
            _need(len(steps) == 4)
            step(steps[0], 'first', first, 1, amount, 3)
            _need(steps[0]['before']['hand'] == [] and steps[0]['before']['discard'] == [])
            step(steps[1], 'duplicate', first, 1, 0, 0, False, False, 97)
            _need(_eq(steps[1]['before'], steps[0]['after']))
            step(steps[2], 'second-enemy', second, 1, 0, 4, block_before=97)
            _need(_eq(steps[2]['before'], steps[1]['after']))
            t = r['transition']
            _need(type(t) is dict and set(t) == set('before after draws moves firstNextMove generatedHistory damage'.split()))
            _need(_eq(t['before'], steps[2]['after']))
            snapshot(t['after'], 2, hp=80, block=0)
            _need(_eq(t['generatedHistory'], [dict(cardRef=c, modelId='SLIMED', creatorId=None) for c in generated_refs]))
            _need(t['damage'] == [])
            _need(t['firstNextMove'] == 'GOOP_MOVE')
            expected = t['before']['draw'][:5]
            draws(t['draws'], expected, True)
            _need(_eq(t['after']['hand'], expected) and _eq(t['after']['draw'], t['before']['draw'][5:]))
            _need(set(t['after']['discard']) == set(t['before']['hand']) | set(generated_refs))
            _need(_eq(t['moves'], [dict(enemy=third, move=sticky_move)]))
            step(steps[3], 'next-turn-first', first, 2, amount, 3)
            _need(all(_eq(steps[3]['before'][p], t['after'][p]) for p in ('hand', 'draw', 'discard')))
        else:
            _need(len(steps) == 2 and r['transition'] is None)
            step(steps[0], 'invalid-target', player, 1, 0, 0, False, False, 0)
            _need(steps[0]['before']['hand'] == [] and steps[0]['before']['discard'] == [])
            s = steps[1]
            _need(set(s) == set('label target before after result draws moves damage'.split()))
            _need(_eq(s['label'], 'receiver-death') and _eq(s['target'], first) and _eq(s['before'], steps[0]['after']))
            snapshot(s['after'], 1, hp=0, block=0, alive=False)
            _need(_eq(s['result'], dict(performed=True, completed=False, absorbed=0)))
            draws(s['draws'], [])
            _need(s['after']['hand'] == [])
            _need(_eq(s['moves'], [dict(enemy=first, move='TACKLE_MOVE')]))
            _need(_eq(s['damage'], [dict(target=player, playerTarget=True, hpLost=80, blocked=0, props=8)]))
        return True
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, StopIteration):
        return False


def relic_contract_evidence(log, run_id, variant):
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1 or variant not in RELIC_CASES:
        return None, False
    try:
        result = json.loads(lines[0])
    except (ValueError, TypeError):
        return None, False
    return result, validate_relic_result(result, run_id, variant)
