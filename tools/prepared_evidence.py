"""Independent frozen prepared-card oracle. Native mechanism/action payment, never mouse acceptance.

Authority: reference volibear mechanics/damage-training.ts (all own damage), repeat.ts
(full effects, one actual play), thunder-guard.ts (independent 3/5 reactions); cards_s2.json.
U08 separate segments follow the user-approved 2026-11-10 adjustment.
No production C# is read to derive expected outcomes. Unimplemented cases stay NOT_RUN.
"""
import json
from collections import Counter
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX = '[Volibear] PREPARED_CONTRACT_RESULT '
PREPARED_CASES = ('PR-training-dynamic-spells', 'PR-training-native-domain', 'PR-guard-instances', 'PR-replay-paid', 'PR-bite-segments')
ALL_CASES = PREPARED_CASES + ('PR-C19-fixed-dynamic-complete-replay', 'PR-C25-coupon', 'PR-U12-round-bonus',
                             'PR-U14-engage-coupon', 'PR-U39-native-choice', 'PR-C14-expiry')
PREPARED_CARD_IDS = ('C14', 'C19', 'C25', 'U08', 'U10', 'U11', 'U12', 'U14', 'U39', 'R06')
ACCEPTANCE = 'native-action-queue-mechanism-not-mouse'


def case_statuses(results=None):
    results = results or {}
    return {case: results.get(case, 'NOT_RUN') if case in PREPARED_CASES else 'NOT_RUN' for case in ALL_CASES}


def _need(value):
    if not value:
        raise ValueError('Prepared native observations disagree with frozen oracle')


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


def validate_prepared_result(r, token, variant):
    try:
        _need(variant in PREPARED_CASES and type(token) is str and bool(token.strip()))
        fixed = dict(token=token, scenario='prepared-contract', variant=variant, completed=True,
                     gameVersion=EXPECTED_GAME_VERSION, gameCommit=EXPECTED_GAME_COMMIT, testMode=False, acceptance=ACCEPTANCE,
                     character='VolibearCharacter')
        _need(type(r) is dict and set(r) == set(fixed) | set('enemyIds enemyTypes playerId cards initial actions steps batches payments beforeEffects trigger'.split()))
        _need(all(_eq(r[k], v) for k, v in fixed.items()))
        ids, types, pid = r['enemyIds'], r['enemyTypes'], r['playerId']
        _need(type(ids) is list and len(ids) == 3 and all(type(i) is int and i >= 0 for i in ids) and len(set(ids)) == 3)
        _need(type(pid) is int and pid >= 0 and pid not in ids)
        _need(type(types) is list and len(types) == 3 and types.count('LeafSlimeS') == types.count('TwigSlimeS') == 1
              and sum(x in ('LeafSlimeM', 'TwigSlimeM') for x in types) == 1)
        medium = 8 if 'LeafSlimeM' in types else 11
        absorbed = 3 + 4 + medium
        # Entries are (identity, stable model, cost, upgraded). These are independently authored.
        unify = ('unify', 'R06', 2, False)
        training = ('training', 'U10', 1, False)
        if variant == 'PR-training-dynamic-spells':
            sequence = [unify, training, ('thunder-block', 'R07', 2, False), ('thunder-absorb', 'R09', 2, False), ('attack', 'U05', 1, False)]
        elif variant == 'PR-training-native-domain':
            sequence = [unify, training, ('guard', 'C14', 2, False), ('attack', 'B03', 1, False)]
        elif variant == 'PR-guard-instances':
            sequence = [unify, ('guard-base', 'C14', 2, False), ('guard-upgrade', 'C14', 2, True)]
        elif variant == 'PR-bite-segments':
            sequence = [unify, ('guard', 'C14', 2, False), ('conduction', 'U02', 1, False),
                        ('bite-mark', 'U08', 1, False), training, ('replay', 'U11', 1, False),
                        ('bite-trained', 'U08', 1, False), ('bite-upgrade', 'U08', 1, True)]
        else:
            sequence = [('replay', 'U11', 1, False), ('bite-first', 'U08', 1, False), ('bite-next', 'U08', 1, False)]
        cards = r['cards']; _need(type(cards) is list and len(cards) == 10 + len(sequence))
        lookup = {}
        for row in cards:
            _need(type(row) is dict and set(row) == {'cardRef', 'modelId', 'upgraded', 'masterIndex'})
            ref = row['cardRef']; _need(type(ref) is str and ref not in lookup)
            _need(type(row['upgraded']) is bool and type(row['masterIndex']) is int)
            lookup[ref] = row
        original = [row for row in cards if row['cardRef'].startswith('starter-')]
        _need(len(original) == 10 and {x['masterIndex'] for x in original} == set(range(10)))
        _need(Counter(x['modelId'] for x in original) == Counter({'VOLIBEAR_B01': 4, 'VOLIBEAR_B02': 4, 'VOLIBEAR_B03': 1, 'VOLIBEAR_B04': 1}))
        _need(all(not x['upgraded'] for x in original))
        for label, model, _, upgraded in sequence:
            _need(_eq(lookup[label], dict(cardRef=label, modelId='VOLIBEAR_' + model, upgraded=upgraded, masterIndex=-1)))
        power_ids = {}
        def snap(actual, energy, block, hp, marks, count, powers):
            _need(type(actual) is dict and set(actual) == set('round turn energy hp block enemyHp marks lightningCount hand draw powers'.split()))
            _need(_eq(actual, dict(round=1, turn=1, energy=energy, hp=80, block=block, enemyHp=hp, marks=marks,
                                  lightningCount=count, hand=actual['hand'], draw=actual['draw'], powers=actual['powers'])))
            for pile in ('hand', 'draw'):
                _need(type(actual[pile]) is list and all(type(x) is str and x in lookup for x in actual[pile]))
            merged = actual['hand'] + actual['draw']; _need(len(merged) == len(set(merged)))
            rows = actual['powers']; _need(type(rows) is list and len(rows) == len(powers))
            pairs = []; refs = []
            for p in rows:
                _need(type(p) is dict and set(p) == {'powerRef', 'type', 'amount'})
                identity = p['powerRef']; _need(type(identity) is int and identity > 0 and type(p['amount']) is int)
                _need(identity not in power_ids or power_ids[identity] == p['type'])
                power_ids[identity] = p['type']; refs.append(identity); pairs.append((p['type'], p['amount']))
            _need(len(set(refs)) == len(refs) and Counter(pairs) == Counter(powers))
        hp, marks, block, count, energy, powers = [500]*3, [0]*3, 0, 0, 10, []
        snap(r['initial'], energy, block, hp, marks, count, powers)
        _need(r['initial']['hand'] == [] and set(r['initial']['draw']) == {x['cardRef'] for x in original})
        steps = r['steps']; actions = r['actions']
        _need(type(steps) is list and type(actions) is list and len(steps) == len(actions) == len(sequence))
        expected_payments, expected_pre, expected_batches = [], [], []
        prior = r['initial']; action_ids = []; play_ids = []
        def hit(target, amount, source, props=4, blocked=0):
            return dict(target=target, playerTarget=target == pid, hpLost=amount, blocked=blocked, props=props, cardRef=source)
        for index, (label, model, cost, upgraded) in enumerate(sequence):
            s = steps[index]; a = actions[index]
            _need(type(s) is dict and set(s) == set('cardRef before after finalPile training plays draws moves damage'.split()))
            _need(s['cardRef'] == label)
            expected_before = dict(prior, hand=prior['hand'] + [label])
            _need(_eq(s['before'], expected_before))
            target = ids[0] if model in ('U05', 'B03', 'U08') else None
            aid = a['id']; _need(type(aid) is int and aid >= 0); action_ids.append(aid)
            _need(_eq(a, dict(cardRef=label, id=aid, target=target, state='Finished', type='PlayCardAction',
                             actionType='CombatPlayPhaseOnly', sameCard=True, context='GameActionPlayerChoiceContext',
                             events=[dict(label='before-executed', state='Executing', id=aid, energy=energy),
                                     dict(label='after-finished', state='Finished', id=aid, energy=energy-cost)])))
            energy -= cost
            expected_payments.append(dict(cardRef=label, amount=cost, energy=energy))
            repeats = 2 if label in ('bite-first', 'bite-trained') else 1
            plays = [dict(cardRef=label, index=i, count=repeats) for i in range(repeats)]
            _need(_eq(s['plays'], plays))
            trained = 3 if label in ('attack', 'bite-trained') else 0
            _need(_eq(s['training'], trained))
            pending = next((n for kind, n in powers if kind == 'NextAttackTrainingPower'), 0)
            if model in ('U05', 'B03', 'U08'): pending = 0
            bite_preview = None
            if model == 'U08':
                bonus = (6 if variant == 'PR-bite-segments' else 0) + trained
                bite_preview = dict(type='DamageVar', amount=(9 if upgraded else 6) + bonus)
            for i in range(repeats):
                expected_pre.append(dict(cardRef=label, index=i, count=repeats, autoPlay=False,
                                         energy=energy, spent=cost, block=block + ((9 if upgraded else 6)*i if model == 'U08' else 0),
                                         pendingTraining=pending, training=trained, replay=0, bitePreview=bite_preview))
            damage, moves, draw_count = [], [], 0
            if model == 'R06':
                block += 10; powers = [('StrengthPower', 3), ('UnifyPower', 3)]
            elif model == 'U10':
                draw_count = 1; powers += [('NextAttackTrainingPower', 3)]
            elif model == 'R07':
                damage = [hit(e, 13, label) for e in ids]; hp = [x-13 for x in hp]
                expected_batches.append((10, 13, label, ids)); count += 1
            elif model == 'R09':
                block += 15 - absorbed; draw_count = 1
                for eid, kind in zip(ids, types):
                    move = 'CLUMP_SHOT' if kind == 'LeafSlimeM' else 'POKEY_POUNCE_MOVE' if kind == 'TwigSlimeM' else 'TACKLE_MOVE'
                    amount = {'LeafSlimeS':3, 'TwigSlimeS':4}.get(kind, medium)
                    moves.append(dict(enemy=eid, move=move)); damage.append(hit(pid, 0, None, 8, amount))
                damage += [hit(e, absorbed+3, label) for e in ids]; hp = [x-absorbed-3 for x in hp]
                expected_batches.append((absorbed, absorbed+3, label, ids)); count += 1
            elif model == 'U05':
                amount = block + 3 + 3 + 3  # dynamic block + Strength + R06 + trained U10 card.
                hp[0] -= amount; damage = [hit(ids[0], amount, label, 8)]
                powers = [p for p in powers if p[0] != 'NextAttackTrainingPower']
            elif model == 'C14':
                block += 11 if upgraded else 8
                domain = next((p[1] for p in powers if p[0] == 'DomainPower'), 0)
                powers = [p for p in powers if p[0] != 'DomainPower'] + [('DomainPower', domain+1), ('ThunderGuardPower', 5 if upgraded else 3)]
            elif model == 'B03':
                hp[0] -= 17; hp = [x-4-9 for x in hp]
                damage = [hit(ids[0], 17, label, 8)] + [hit(e, amount, label) for amount in (4,9) for e in ids]
                expected_batches += [(4,4,label,ids), (3,9,label,ids)]; count += 2
                powers = [p for p in powers if p[0] != 'NextAttackTrainingPower']
            elif model == 'U02':
                hp = [x-6 for x in hp]; damage = [hit(e, 6, label) for e in ids]
                expected_batches.append((6,6,label,ids)); count += 1
                powers += [('StormConductionPower', 3)]
            elif model == 'U11':
                powers += [('NextAttackReplayPower', 1)]
            elif model == 'U08':
                block += (9 if upgraded else 6) * repeats
                # Eligibility is frozen before the paid card, including its replays.
                had_bite = bool(marks[0])
                bonus = (6 if variant == 'PR-bite-segments' else 0) + trained
                segments = [14 if upgraded else 10] + ([9 if upgraded else 6] if had_bite else [])
                segments = [n + bonus for n in segments] * repeats
                damage = [hit(ids[0], n, label, 8) for n in segments]
                hp[0] -= sum(segments); marks[0] = 1
                powers = [p for p in powers if p[0] not in ('NextAttackTrainingPower', 'NextAttackReplayPower')]
                if variant == 'PR-bite-segments':
                    # One Domain batch per actual card; one U02 batch per ordinary hit.
                    batches_for_card = [(4,4,label,ids)] + [(3,3,None,ids)] * len(segments)
                    expected_batches += batches_for_card; count += len(batches_for_card)
                    hp = [x - 4 - 3*len(segments) for x in hp]
                    damage += [hit(e, amount, source) for _, amount, source, _ in batches_for_card for e in ids]
            expected_draw = s['before']['draw'][:draw_count]
            _need(_eq(s['draws'], [dict(cardRef=c, modelId=lookup[c]['modelId'], fromHandDraw=False) for c in expected_draw]))
            _need(_eq(s['moves'], moves))
            _need(type(s['damage']) is list and len(s['damage']) == len(damage))
            # History may insert the owner receipt before/after awaited retaliation hooks.
            def same_hits(rows, expected):
                if type(rows) is not list or len(rows) != len(expected): return False
                remaining = list(expected)
                for row in rows:
                    match = next((i for i, item in enumerate(remaining) if _eq(row, item)), None)
                    if match is None: return False
                    remaining.pop(match)
                return not remaining
            _need(same_hits(s['damage'], damage))
            if model == 'U08':
                # Ordered ordinary receipts distinguish 10 then 6 from a merged hit
                # even when the total HP loss happens to match.
                _need(_eq([row for row in s['damage'] if row['props'] == 8],
                          [row for row in damage if row['props'] == 8]))
            snap(s['after'], energy, block, hp, marks, count, powers)
            _need(_eq(s['after']['hand'], prior['hand'] + expected_draw) and _eq(s['after']['draw'], prior['draw'][draw_count:]))
            _need(s['finalPile'] == (None if model == 'U02' else 'Exhaust' if model == 'R06' or model == 'C14' and not upgraded else 'Discard'))
            prior = s['after']
        _need(action_ids == sorted(set(action_ids)))
        _need(_eq(r['payments'], expected_payments))
        pre = r['beforeEffects']; _need(type(pre) is list and len(pre) == len(expected_pre))
        seen = {}
        for actual, expected in zip(pre, expected_pre):
            identity = actual['playId']; _need(type(identity) is int and identity > 0)
            label = expected['cardRef']
            if label in seen: _need(seen[label] == identity)
            else: _need(identity not in seen.values()); seen[label] = identity
            _need(_eq(actual, dict(expected, playId=identity)))
        if variant == 'PR-guard-instances':
            t = r['trigger']; leaf = ids[types.index('LeafSlimeS')]
            _need(type(t) is dict and set(t) == set('operation dealer before after damage'.split()))
            _need(t['operation'] == 'DamageCmd.Attack.FromMonster.Execute' and _eq(t['dealer'], leaf) and _eq(t['before'], prior))
            expected = [hit(pid,0,None,8,3), hit(leaf,3,None), hit(leaf,5,None)]
            _need(same_hits(t['damage'], expected))
            hp[ids.index(leaf)] -= 8
            snap(t['after'], energy, block-3, hp, marks, 2, powers)
            _need(_eq(t['after']['hand'], prior['hand']) and _eq(t['after']['draw'], prior['draw']) and _eq(t['after']['powers'], prior['powers']))
            expected_batches += [(3,3,None,[leaf]), (5,5,None,[leaf])]
        else:
            _need(r['trigger'] is None)
        batches = r['batches']; _need(type(batches) is list and len(batches) == len(expected_batches))
        batch_ids = []
        for i, (row, (base, amount, card, targets)) in enumerate(zip(batches, expected_batches), 1):
            identity = row['id']; _need(type(identity) is int and identity > 0); batch_ids.append(identity)
            _need(_eq(row, dict(id=identity, round=1, turn=1, count=i, baseDamage=base, amount=amount, cardRef=card,
                               targets=targets, hits=[dict(target=e, hpLost=amount, blocked=0) for e in targets])))
        _need(batch_ids == sorted(set(batch_ids)))
        return True
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, StopIteration):
        return False


def prepared_contract_evidence(log, run_id, variant):
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1 or variant not in PREPARED_CASES:
        return None, False
    try:
        result = json.loads(lines[0])
    except (ValueError, TypeError):
        return None, False
    return result, validate_prepared_result(result, run_id, variant)
