"""Native encounter exploration plus finite paid-card scheduling and effect oracles.
Paid-acceptance checks twelve source-derived slime cycles; formal-paid selects every
Act-root target in finite batches. Formal effect/guard gaps remain explicit, not passes.
No event-only shortcut, branch-completeness claim, or changed MVP schema.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path

from enemy_catalog_evidence import validate_manifest as validate_catalog
from enemy_matrix_evidence import FRESH_REFS

PREFIX = '[Volibear] ENEMY_EXPLORATION_RESULT '
ACT_INDEX = {'ACT.OVERGROWTH': 0, 'ACT.UNDERDOCKS': 0, 'ACT.HIVE': 1, 'ACT.GLORY': 2}
SEED = 'VOLIBEARTEST'


def smoke_cases():
    def row(cid, act, encounter, budget=2, policy='end-turn', expected='ANY'):
        return dict(caseId=cid, act='ACT.'+act, encounter='ENCOUNTER.'+encounter,
                    turnBudget=budget, policy=policy, expectedOutcome=expected)
    return [row('smoke-overgrowth', 'OVERGROWTH', 'SLIMES_WEAK', expected='BUDGET_EXIT'),
            row('terminal-win', 'OVERGROWTH', 'SLIMES_WEAK', 32, 'basic-paid-cards', 'WIN'),
            row('terminal-loss', 'OVERGROWTH', 'SLIMES_WEAK', 32, expected='LOSS'),
            row('smoke-underdocks', 'UNDERDOCKS', 'CORPSE_SLUGS_WEAK'),
            row('smoke-hive', 'HIVE', 'BOWLBUGS_WEAK'),
            row('smoke-glory', 'GLORY', 'DEVOTED_SCULPTOR_WEAK')]


PAID_TARGETS = ('LEAF_SLIME_S', 'LEAF_SLIME_M', 'TWIG_SLIME_S')
PAID_POLICIES = ('paid-natural-off', 'paid-engage-off', 'paid-natural-on', 'paid-engage-on')
# Locked native source: LeafSlimeM alternates STICKY_SHOT/CLUMP_SHOT;
# LeafSlimeS RAND has two CannotRepeat exits; TwigSlimeS self-loops.
PAID_MOVES = {'LEAF_SLIME_S': {'TACKLE_MOVE': (3, 0), 'GOOP_MOVE': (0, 1)},
              'LEAF_SLIME_M': {'CLUMP_SHOT': (8, 0), 'STICKY_SHOT': (0, 2)},
              'TWIG_SLIME_S': {'TACKLE_MOVE': (4, 0)}}


def paid_cases():
    return [dict(caseId=f'paid-{target}-{policy}', act='ACT.OVERGROWTH',
                 encounter='ENCOUNTER.SLIMES_WEAK', turnBudget=4, policy=policy,
                 expectedOutcome='BUDGET_EXIT') for target in PAID_TARGETS for policy in PAID_POLICIES]


def threshold_cases():
    return [dict(caseId='threshold-TUNNELER_WEAK:TUNNELER:'+policy, act='ACT.HIVE',
                 encounter='ENCOUNTER.TUNNELER_WEAK', turnBudget=4 if policy.endswith('-on') else 5,
                 policy=policy, expectedOutcome='BUDGET_EXIT') for policy in PAID_POLICIES]


def registered(catalog):
    return {act['id']: set(act['encounters']) for act in catalog['acts']}


def validate_selection(selection, catalog):
    errors = []
    try:
        roots = registered(catalog)
        if (selection['schema'] != 1 or selection['seed'] != SEED or selection['ascension'] != 0 or
                selection['gameAssemblyMvid'] != catalog['gameAssemblyMvid']):
            errors.append('selection version/seed/ascension mismatch')
        cases = selection['cases']
        if not isinstance(cases, list) or not 1 <= len(cases) <= 80:
            return errors + ['empty/oversized selection']
        if len({case['caseId'] for case in cases}) != len(cases):
            errors.append('duplicate case identity')
        if selection['mode'] == 'smoke':
            if cases != smoke_cases():
                errors.append('four-Act/three-terminal smoke cases changed')
        elif selection['mode'] == 'explore':
            if not selection.get('prerequisiteToken'):
                errors.append('explore has no validated smoke prerequisite')
            if len({c['encounter'] for c in cases}) != len(cases):
                errors.append('explore duplicates encounter')
            if any(c['turnBudget'] != 2 or c['policy'] != 'end-turn' or c['expectedOutcome'] != 'ANY' for c in cases):
                errors.append('unapproved exploration intervention')
        elif selection['mode'] == 'paid-acceptance':
            if cases != paid_cases():
                errors.append('paid acceptance requires exact twelve four-cycle fixtures')
        elif selection['mode'] == 'paid-threshold':
            if cases != threshold_cases():
                errors.append('threshold acceptance requires exact four paid Tunneler fixtures')
            if not any(e['id']=='ENCOUNTER.TUNNELER_WEAK' and 'MONSTER.TUNNELER' in e['monsterIds'] for e in catalog['encounters']):
                errors.append('threshold native catalogue lacks the formal TunnelerWeak target')
        elif selection['mode'] == 'formal-paid':
            allowed = {c['caseId']: c for c in formal_cases(catalog)}
            if any(c != allowed.get(c['caseId']) for c in cases):
                errors.append('unknown/changed formal paid fixture')
        else:
            errors.append('unknown selection mode')
        for case in cases:
            if case['act'] not in ACT_INDEX or case['encounter'] not in roots.get(case['act'], set()):
                errors.append('case not rooted in selected native Act (event/display/debug forbidden)')
    except (TypeError, KeyError, ValueError, AttributeError):
        errors.append('malformed selection/catalog')
    return errors


def formal_cases(catalog):
    roots = registered(catalog)
    return [dict(caseId=f"formal-{e['id'].split('.',1)[1]}:{mid.split('.',1)[1]}:{policy}",
                 act=next(a for a in sorted(roots) if e['id'] in roots[a]), encounter=e['id'],
                 turnBudget=8, policy=policy, expectedOutcome='ANY')
            for e in sorted(catalog['encounters'], key=lambda e:e['id'])
            if e['included'] and any(e['id'] in ids for ids in roots.values())
            for mid in sorted(e['monsterIds']) for policy in PAID_POLICIES]


def prepare_selection(catalog, *, mode='smoke', encounters=None, prerequisite=None, batch_index=0):
    errors = validate_catalog(catalog, run_id=catalog.get('token'))
    if errors:
        raise ValueError('Invalid source catalog: ' + '; '.join(errors))
    selection = dict(schema=1, mode=mode, seed=SEED, ascension=0, gameAssemblyMvid=catalog['gameAssemblyMvid'],
                     cases=smoke_cases(), prerequisiteToken=None)
    if mode == 'paid-acceptance':
        selection['cases'] = paid_cases()
    if mode == 'paid-threshold':
        selection['cases'] = threshold_cases()
    if mode == 'formal-paid':
        required = formal_cases(catalog)
        if encounters:
            if not set(encounters) <= {c['encounter'] for c in required}:
                raise ValueError('Unknown/event-only formal encounter; legal event setup remains NOT_RUN')
            required = [c for c in required if c['encounter'] in encounters]
        if type(batch_index) is not int or batch_index < 0:
            raise ValueError('Invalid finite batch index')
        selection['cases'] = required[batch_index*80:(batch_index+1)*80]
    if mode == 'explore':
        if prerequisite is None or prerequisite.get('selection', {}).get('mode') != 'smoke':
            raise ValueError('A successful native four-Act/three-terminal smoke manifest is required')
        errors = validate_exploration(prerequisite, selection=prerequisite['selection'], catalog=catalog,
                                      run_id=prerequisite.get('token'))
        if errors:
            raise ValueError('Smoke prerequisite failed: ' + '; '.join(errors))
        roots = registered(catalog)
        available = set.union(*roots.values())
        chosen = sorted(set(encounters) if encounters else available)
        if not chosen or not set(chosen) <= available:
            raise ValueError('Selection contains unknown/event-only encounters')
        selection['prerequisiteToken'] = prerequisite['token']
        selection['cases'] = [dict(caseId='explore-'+eid.split('.', 1)[1], act=next(a for a in sorted(roots) if eid in roots[a]),
            encounter=eid, turnBudget=2, policy='end-turn', expectedOutcome='ANY') for eid in chosen]
    errors = validate_selection(selection, catalog)
    if errors:
        raise ValueError('; '.join(errors))
    return selection


def validate_exploration(data, *, selection, catalog, run_id):
    try:
        return _validate(data, selection, catalog, run_id)
    except (TypeError, KeyError, ValueError, AttributeError, IndexError):
        return ['malformed exploration evidence']


def _validate(data, selection, catalog, run_id):
    errors = ['catalog: '+e for e in validate_catalog(catalog, run_id=catalog.get('token'))]
    errors += validate_selection(selection, catalog)
    encounter_rows = {e['id']: e for e in catalog['encounters']}
    def need(condition, message):
        if not condition:
            errors.append(message)
    def exact(actual, expected, message):
        need(type(actual) is type(expected) and actual == expected, message)
    for key, expected in dict(schema=1, token=run_id, scenario='enemy-exploration', acceptance='bounded-native-exploration-only',
        gameVersion='v0.107.1', gameCommit='59260271', gameAssemblyMvid=catalog['gameAssemblyMvid'], testMode=False,
        enemyHpModified=False, playerHpModified=False, forcedMoves=False, directPerformMoveCalls=0,
        completeAiCoverage=False, physicalInputValidated=False, eventOnlyStatus='EVENT_SETUP_REQUIRED_NOT_RUN').items():
        exact(data.get(key), expected, 'invalid '+key)
    need('failure' in data and data['failure'] is None, 'native coordinator failed/missing result')
    need(data.get('selection') == selection, 'executed selection differs from out-of-band input')
    need(type(data.get('processId')) is int and data['processId'] > 0, 'missing process identity')
    need(data.get('warmup', {}).get('includedInCases') is False, 'warmup counted as selected case')
    need(data.get('unexecutedSelectedCases') == [], 'selected cases remain NOT_RUN')
    need(set(data.get('registeredEncounterIds', [])) == set.union(*registered(catalog).values()), 'native registered denominator changed')
    cases = data.get('cases', [])
    need([c.get('caseId') for c in cases] == [c['caseId'] for c in selection['cases']], 'selected case closure/order mismatch')
    seen_refs, history_ref = set(), None
    for case, spec in zip(cases, selection['cases']):
        p = spec['caseId']+': '
        for key in ('caseId', 'policy', 'encounter', 'turnBudget'):
            exact(case.get(key), spec[key], p+key)
        exact(case.get('act'), spec['act'], p+'Act')
        exact(case.get('actIndex'), ACT_INDEX[spec['act']], p+'Act index')
        exact(case.get('seed'), SEED, p+'seed')
        exact(case.get('ascension'), 0, p+'ascension')
        exact(case.get('processId'), data['processId'], p+'different process')
        exact(case.get('roomType'), encounter_rows[spec['encounter']]['roomType'], p+'native room type')
        need(type(case.get('numericSeed')) is int and case['numericSeed'] == cases[0].get('numericSeed'), p+'numeric seed mismatch')
        act0 = 'ACT.UNDERDOCKS' if spec['act'] == 'ACT.UNDERDOCKS' else 'ACT.OVERGROWTH'
        need(case.get('acts') == [dict(id=act0, index=0), dict(id='ACT.HIVE', index=1), dict(id='ACT.GLORY', index=2)], p+'incorrect Act slots')
        need('error' in case and case['error'] is None and case.get('observationError') is None, p+'native/observation error')
        before = case.get('playerBeforeRoom', {})
        need(before.get('hp') == before.get('maxHp') == 80, p+'player fixture is not native starting 80HP')
        terminal = case.get('terminal', {})
        outcome = case.get('outcome')
        need(outcome in ('BUDGET_EXIT', 'WIN', 'LOSS') and terminal.get('outcome') == outcome, p+'unclassified/fake terminal')
        if spec['expectedOutcome'] != 'ANY':
            need(outcome == spec['expectedOutcome'], p+'required terminal fixture did not occur')
        need(terminal.get('queueEmpty') is True and terminal.get('runningActionRef') is None and terminal.get('pendingChoices') == 0,
             p+'terminal/budget boundary not settled')
        signals = case.get('terminalSignals', [])
        kinds = [s.get('kind') for s in signals]
        if outcome == 'BUDGET_EXIT':
            need(kinds == [] and terminal.get('combatEnded') is False and terminal.get('combatWon') is False and
                 terminal.get('inProgress') is True and terminal['player']['alive'] is True, p+'budget exit fabricated victory/loss')
        elif outcome == 'WIN':
            need(kinds == ['CombatWon', 'CombatEnded'] and terminal.get('combatEnded') is True and terminal.get('combatWon') is True and
                 terminal.get('inProgress') is False and terminal['player']['alive'] is True, p+'no actual native win')
        else:
            need(kinds == ['CombatEnded'] and terminal.get('combatEnded') is True and terminal.get('combatWon') is False and
                 terminal.get('inProgress') is False and terminal['player']['alive'] is False and terminal['player']['hp'] == 0,
                 p+'no actual native loss')
        bounds = case.get('boundaries', [])
        initial = case.get('initial')
        refs = {before.get('creatureRef')}
        run_ids = case.get('runIdentities', {})
        for key in ('runRef', 'playerRef', 'playerCreatureRef', 'queueRef', 'executorRef', 'choiceSyncRef', 'runNodeRef'):
            need(isinstance(run_ids.get(key), str) and bool(run_ids[key]), p+'missing run identity '+key)
            refs.add(run_ids.get(key))
        combat_ref = terminal.get('combatRef')
        need(combat_ref and combat_ref != data['warmup'].get('combatRef'), p+'warmup reused')
        refs.add(combat_ref)
        if initial is not None:
            need(bounds and bounds[0] == initial, p+'initial snapshot mismatch')
            need(bool(initial.get('enemies')) and {e['modelId'] for e in initial['enemies']} <=
                 set(encounter_rows[spec['encounter']]['monsterIds']), p+'initial enemy provenance mismatch')
            for key in FRESH_REFS:
                need(isinstance(initial.get(key), str) and initial[key], p+'missing '+key)
                refs.add(initial[key])
            need(initial.get('combatRef') == combat_ref and initial['playerCreatureRef'] == before['creatureRef'], p+'wrong live initial identity')
            need(all(initial.get(key) == value for key, value in run_ids.items() if key != 'runNodeRef'), p+'run identity changed entering combat')
            if history_ref is None:
                history_ref = initial.get('historyRef')
            need(initial.get('historyRef') == history_ref, p+'native singleton history replaced')
        else:
            need(outcome in ('WIN', 'LOSS') and not bounds, p+'missing initial Play without genuine early terminal')
        previous_turn = 0
        for bound in bounds:
            need(bound.get('combatRef') == combat_ref and bound.get('side') == 'Player' and bound.get('phase') == 'Play' and
                 type(bound.get('turn')) is int and bound['turn'] > previous_turn, p+'invalid observed Play boundary')
            previous_turn = bound['turn']
            need(bound.get('queueEmpty') is True and bound.get('runningActionRef') is None and bound.get('pendingChoices') == 0,
                 p+'nonquiescent Play snapshot')
            for key in FRESH_REFS:
                need(bound.get(key) == initial[key], p+'within-case reference replaced')
            scopes = bound.get('scopes', {})
            need(scopes.get('activePlays') == scopes.get('playTasks') == scopes.get('drawTasks') == 0 and
                 scopes.get('lightningOnlyCurrentCombat') is True and scopes.get('targetSubscriptionsOnlyCurrentCombat') is True,
                 p+'active/stale scope')
            for enemy in bound.get('enemies', []):
                refs.update([enemy['creatureRef'], enemy['modelRef']])
            for pile in ('cards', 'deck'):
                refs.update(card['cardRef'] for card in bound[pile])
        inputs = case.get('inputs', [])
        requests = [i for i in inputs if i['type'] == 'EndPlayerTurnAction']
        plays = [i for i in inputs if i['type'] == 'PlayCardAction']
        need(len(requests)+len(plays) == len(inputs), p+'unapproved input')
        paid = selection['mode'] in ('paid-acceptance', 'formal-paid', 'paid-threshold')
        need(paid or spec['policy'] == 'basic-paid-cards' or not plays, p+'player attacks injected in exploration')
        need(all(i.get('completionObserved') is True and i.get('status') in ('RETURNED_TO_PLAY', 'TERMINAL') for i in inputs),
             p+'unsettled native input')
        refs.update(i['actionRef'] for i in inputs)
        need(case.get('requestedTurns') == len(requests) <= spec['turnBudget'], p+'wrong requested turn budget')
        completed = sum(i['status'] == 'RETURNED_TO_PLAY' for i in requests)
        need(case.get('completedCycles') == completed and len(bounds) == completed + (initial is not None), p+'invented next Play')
        for i in requests:
            if i['status'] == 'RETURNED_TO_PLAY':
                need(type(i.get('turnAfter')) is int and i['turnAfter'] > i['turnBefore'] and
                     any(b['turn'] == i['turnAfter'] for b in bounds), p+'CompletionTask masquerading as next turn')
        slots = case.get('turnSlots', [])
        need([s['ordinal'] for s in slots] == list(range(1, spec['turnBudget']+1)), p+'missing turn opportunity slots')
        need([s['status'] for s in slots[:len(requests)]] == [i['status'] for i in requests] and
             all(s['status'] == 'NOT_OBSERVED' for s in slots[len(requests):]), p+'unperformed turns falsely completed')
        if outcome == 'BUDGET_EXIT':
            need(completed == spec['turnBudget'] and len(requests) == spec['turnBudget'], p+'premature budget exit')
        history = case.get('nativeHistory', [])
        need(bool(history) and len({h['entryRef'] for h in history}) == len(history), p+'missing/duplicate native history')
        need([h['seq'] for h in history] == sorted({h['seq'] for h in history}), p+'history append order')
        need(all(h.get('combatRef') == combat_ref for h in history), p+'foreign history combat')
        refs.update(h['entryRef'] for h in history)
        for h in history:
            refs.update(h.get(k) for k in ('actorRef', 'cardRef', 'dealerRef', 'receiverRef', 'monsterRef') if h.get(k))
        need(terminal.get('exportedHistory') <= len(history) and terminal.get('exportedHistory', 0) > 0, p+'terminal history not exported')
        clears = case.get('historyClears', [])
        need(bool(clears) and all(0 < c['exported'] <= len(history) and c['exported'] >= c['priorVisible'] for c in clears), p+'history lost on native clear')
        if outcome == 'BUDGET_EXIT':
            need(all(c['duringBudgetExit'] is True for c in clears) and terminal['nativeHistoryVisible'] == terminal['exportedHistory'], p+'budget history loss')
        if spec['encounter'] == 'ENCOUNTER.SLIMES_WEAK':
            player_damage = [h for h in history if h['kind'] == 'DamageReceivedEntry' and h.get('receiverRef') == before['creatureRef']]
            need(terminal['player']['hp'] == max(0, 80-sum(h['hpLost'] for h in player_damage)), p+'Slimes player HP receipts disagree')
        # Only actual completed-history entries count. No universal six-move or no-spawn rule.
        moves = [h for h in history if h['kind'] == 'MonsterPerformedMoveEntry']
        enemy_turns = [t for t in case.get('turnSignals', []) if t.get('side') == 'Enemy']
        need([t.get('enemyTurnOrdinal') for t in enemy_turns] == list(range(1, len(enemy_turns)+1)), p+'missing/repeated enemy turn ordinal')
        opportunities = case.get('opportunities', [])
        for turn_signal in enemy_turns:
            need(any(s.get('side') == 'Player' and s.get('round') == turn_signal['round'] and s['seq'] < turn_signal['seq']
                     for s in case.get('sideSwitches', [])), p+'missing native pre-switch observation')
            current = [o for o in opportunities if o.get('enemyTurnOrdinal') == turn_signal['enemyTurnOrdinal']]
            need(Counter(o['creatureRef'] for o in current) == Counter(turn_signal.get('enemyCandidateRefs', [])), p+'enemy-start candidate observation lost')
        for opportunity in opportunities:
            need(type(opportunity.get('spawnedThisTurn')) is bool, p+'missing actual spawn flag')
            end_seq = min((t['seq'] for t in enemy_turns if t['enemyTurnOrdinal'] > opportunity['enemyTurnOrdinal']), default=float('inf'))
            actual = any(m['actorRef'] == opportunity['creatureRef'] and m['round'] == opportunity['round'] and
                         m['side'] == 'Enemy' and opportunity['seq'] < m['seq'] < end_seq for m in moves)
            expected = 'COMPLETED_NATIVE_HISTORY' if actual else 'NOT_OBSERVED'
            need(opportunity.get('status') == expected, p+'unobserved/terminal-interrupted action fabricated')
        for index, play in enumerate(plays):
            allowed = ('CARD.VOLIBEAR_B01', 'CARD.VOLIBEAR_B02', 'CARD.VOLIBEAR_C10', 'CARD.VOLIBEAR_C11', 'CARD.VOLIBEAR_C21', 'CARD.VOLIBEAR_C12') if paid else ('CARD.VOLIBEAR_B01', 'CARD.VOLIBEAR_B02')
            need(play.get('cardId') in allowed, p+'unapproved fixture card')
            next_seq = min((i['seq'] for i in inputs if i['seq'] > play['seq']), default=float('inf'))
            window = [h for h in history if play['seq'] < h['seq'] < next_seq]
            for kind in ('CardPlayStartedEntry', 'CardPlayFinishedEntry'):
                need(sum(h['kind'] == kind and h.get('cardRef') == play['cardRef'] for h in window) == 1, p+'native paid card lifecycle absent')
            need(sum(h.get('amount', 0) for h in window if h['kind'] == 'EnergySpentEntry') == 1 and
                 play['energyBefore']-play['energyAfter'] == 1, p+'native payment absent/mismatched')
        if selection['mode'] == 'paid-acceptance':
            errors += [p + e for e in validate_paid_case(case, spec)]
        elif selection['mode'] == 'paid-threshold':
            errors += [p + e for e in validate_threshold_case(case, spec)]
        elif selection['mode'] == 'formal-paid':
            errors += [p + e for e in validate_formal_paid_case(case, spec)]
            semantic_errors, _ = validate_case_semantics(case)
            errors += [p + e for e in semantic_errors]
        if spec['policy'] == 'basic-paid-cards':
            need(bool(plays) and any(h['kind'] == 'DamageReceivedEntry' and h.get('dealerRef') == before['creatureRef'] and
                                    h.get('cardRef') and h.get('hpLost', 0) > 0 for h in history), p+'win without actual player attacks')
        end = case.get('afterExit', {})
        for key, expected in dict(runIsNull=True, combatIsNull=True, inProgress=False, historyVisible=0, queueEmpty=True, runningActionRef=None).items():
            exact(end.get(key), expected, p+'cleanup '+key)
        scopes = end.get('scopes', {})
        for key in ('activePlays', 'playTasks', 'drawTasks', 'purifications', 'engageConsumed', 'engageActionRounds'):
            exact(scopes.get(key), 0, p+'cleanup scope '+key)
        need(scopes.get('lightningCombatRefs') == scopes.get('targetSubscriptionOwnerRefs') == [], p+'subscription cleanup')
        refs.discard(None)
        need(not seen_refs.intersection(refs), p+'prior case references reused')
        seen_refs.update(refs)
    return errors


# Native 0.107.1 source expectations (Ascension 0); no production Mod values are read.
# Each move has actual hit values, actual contribution recipients and legal next moves.
# D09 preserves move-direct Strength and direct block. Other buffs/status/debuff
# contributions are suppressed; passive Strength is a separate D10 requirement.
def _move(hits=(), next=(), powers=(), cards=(), block=(), flags=(), special=None):
    return dict(hits=hits, next=next, powers=powers, cards=cards, block=block, flags=flags, special=special)


SOURCE_MOVES = {
    'LEAF_SLIME_S': { # LeafSlimeS.cs: native two CannotRepeat exits, existing twelve-case oracle.
        'GOOP_MOVE': _move(next=('TACKLE_MOVE',), cards=(('SLIMED','Discard',1),)),
        'TACKLE_MOVE': _move((3,), ('GOOP_MOVE',)),
    },
    'LEAF_SLIME_M': {
        'STICKY_SHOT': _move(next=('CLUMP_SHOT',), cards=(('SLIMED','Discard',2),)),
        'CLUMP_SHOT': _move((8,), ('STICKY_SHOT',)),
    },
    'TWIG_SLIME_S': {'TACKLE_MOVE':_move((4,), ('TACKLE_MOVE',))},
    'CORPSE_SLUG': { # CorpseSlug.cs:43-51,91-133
        'WHIP_SLAP_MOVE': _move((3,3), ('GLOMP_MOVE',)),
        'GLOMP_MOVE': _move((8,), ('GOOP_MOVE',)),
        'GOOP_MOVE': _move(next=('WHIP_SLAP_MOVE',), powers=(('player','FRAIL_POWER',2),)),
    },
    'AXEBOT': { # Axebot.cs:36-42,84-128; stock-dependent BOOT_UP is not constant strength.
        'BOOT_UP_MOVE': _move(next=('HAMMER_UPPERCUT_MOVE',), block=(('actor',10),), special='stock-strength'),
        'HAMMER_UPPERCUT_MOVE': _move((12,), ('ONE_TWO_MOVE',), powers=(('player','WEAK_POWER',2),('player','FRAIL_POWER',2))),
        'ONE_TWO_MOVE': _move((9,9), ('HAMMER_UPPERCUT_MOVE',)),
    },
    'TUNNELER': { # Tunneler.cs:50-54,69-138. TunnelerWeak remains formal.
        'BITE_MOVE': _move((13,), ('BURROW_MOVE',)),
        'BURROW_MOVE': _move(next=('BELOW_MOVE',), powers=(('actor','BURROWED_POWER',1),), block=(('actor',32),)),
        'BELOW_MOVE': _move((23,), ('BELOW_MOVE',)),
        'DIZZY_MOVE': _move(next=('BITE_MOVE',), flags=(('isStunned',False),)),
        'STUNNED': _move(next=('BITE_MOVE',), flags=(('isStunned',False),)), # Creature.cs:537, BurrowedPower.cs:31-33
    },
    'STABBOT': {'STAB_MOVE': _move((11,), ('STAB_MOVE',), powers=(('player','FRAIL_POWER',1),))}, # Stabbot.cs:25,40-54
    'ZAPBOT': {'ZAP': _move((14,), ('ZAP',))}, # Zapbot.cs:25,40-53; HighVoltage response separate.
    'GUARDBOT': {'GUARD_MOVE': _move(next=('GUARD_MOVE',), block=(('fabricators',15),))}, # Guardbot.cs:38-55, including empty recipient set
    'NOISEBOT': {'NOISE_MOVE': _move(next=('NOISE_MOVE',), cards=(('DAZED','Discard',1),('DAZED','Draw',1)))}, # Noisebot.cs:42-64
    'TWIG_SLIME_M': { # TwigSlimeM.cs:29,33-77: attack may repeat, sticky may NOT repeat.
        'POKEY_POUNCE_MOVE': _move((11,), ('POKEY_POUNCE_MOVE','STICKY_SHOT_MOVE')),
        'STICKY_SHOT_MOVE': _move(next=('POKEY_POUNCE_MOVE',), cards=(('SLIMED','Discard',1),)),
    },
    'FUZZY_WURM_CRAWLER': { # FuzzyWurmCrawler.cs:33,48-88
        'FIRST_ACID_GOOP': _move((4,), ('INHALE',), flags=(('isPuffed',False),)),
        'INHALE': _move(next=('ACID_GOOP',), powers=(('actor','STRENGTH_POWER',7),), flags=(('isPuffed',True),)),
        'ACID_GOOP': _move((4,), ('FIRST_ACID_GOOP',), flags=(('isPuffed',False),)),
    },
    'CHOMPER': { # Chomper.cs:32,55-82; initial ScreamFirst is observed separately.
        'CLAMP_MOVE': _move((8,8), ('SCREECH_MOVE',)),
        'SCREECH_MOVE': _move(next=('CLAMP_MOVE',), cards=(('DAZED','Discard',3),)),
    },
    'SCROLL_OF_BITING': { # ScrollOfBiting.cs:41-43,79-125
        'CHOMP': _move((14,), ('MORE_TEETH',)),
        'CHEW': _move((5,5), ('CHOMP','CHEW')),
        'MORE_TEETH': _move(next=('CHEW',), powers=(('actor','STRENGTH_POWER',2),)),
    },
    'SNEAKY_GREMLIN': { # SneakyGremlin.cs:25,46-68
        'SPAWNED_MOVE': _move(next=('TACKLE_MOVE',), flags=(('isAwake',True),)),
        'TACKLE_MOVE': _move((9,), ('TACKLE_MOVE',)),
    },
    'SOUL_FYSH': { # SoulFysh.cs:54-64,110-204
        'BECKON_MOVE': _move(next=('DE_GAS_MOVE',), cards=(('BECKON','Draw',1),('BECKON','Discard',1))),
        'DE_GAS_MOVE': _move((16,), ('GAZE_MOVE',)),
        'GAZE_MOVE': _move((7,), ('FADE_MOVE',), cards=(('BECKON','Discard',1),)),
        'FADE_MOVE': _move(next=('SCREAM_MOVE',), powers=(('actor','INTANGIBLE_POWER',2),), flags=(('isInvisible',True),)),
        'SCREAM_MOVE': _move((13,), ('BECKON_MOVE',), powers=(('player','VULNERABLE_POWER',3),), flags=(('isInvisible',False),)),
    },
    'VINE_SHAMBLER': { # VineShambler.cs:38-85
        'SWIPE_MOVE': _move((6,6), ('GRASPING_VINES_MOVE',)),
        'GRASPING_VINES_MOVE': _move((8,), ('CHOMP_MOVE',), powers=(('player','TANGLED_POWER',1),), special='tangled-affliction'),
        'CHOMP_MOVE': _move((16,), ('SWIPE_MOVE',)),
    },
    'SLUDGE_SPINNER': { # SludgeSpinner.cs:30-78, RAND CannotRepeat for all three exits
        'OIL_SPRAY_MOVE': _move((8,), ('SLAM_MOVE','RAGE_MOVE'), powers=(('player','WEAK_POWER',1),)),
        'SLAM_MOVE': _move((11,), ('OIL_SPRAY_MOVE','RAGE_MOVE')),
        'RAGE_MOVE': _move((6,), ('OIL_SPRAY_MOVE','SLAM_MOVE'), powers=(('actor','STRENGTH_POWER',3),)),
    },
    'GLOBE_HEAD': { # GlobeHead.cs:33-86; Galvanized card response separately required.
        'SHOCKING_SLAP': _move((13,), ('THUNDER_STRIKE',), powers=(('player','FRAIL_POWER',2),)),
        'THUNDER_STRIKE': _move((6,6,6), ('GALVANIC_BURST',)),
        'GALVANIC_BURST': _move((16,), ('SHOCKING_SLAP',), powers=(('actor','STRENGTH_POWER',2),)),
    },
    'DAMP_CULTIST': { # DampCultist.cs:32-34,66-91
        'INCANTATION_MOVE': _move(next=('DARK_STRIKE_MOVE',), powers=(('actor','RITUAL_POWER',5),)),
        'DARK_STRIKE_MOVE': _move((1,), ('DARK_STRIKE_MOVE',)),
    },
    'CALCIFIED_CULTIST': { # CalcifiedCultist.cs:32-34,66-91
        'INCANTATION_MOVE': _move(next=('DARK_STRIKE_MOVE',), powers=(('actor','RITUAL_POWER',2),)),
        'DARK_STRIKE_MOVE': _move((9,), ('DARK_STRIKE_MOVE',)),
    },
    'PUNCH_CONSTRUCT': { # PunchConstruct.cs:37-41,81-118
        'READY_MOVE': _move(next=('FAST_PUNCH_MOVE',), block=(('actor',10),)),
        'FAST_PUNCH_MOVE': _move((5,5), ('STRONG_PUNCH_MOVE',), powers=(('player','FRAIL_POWER',1),)),
        'STRONG_PUNCH_MOVE': _move((14,), ('READY_MOVE',)),
    },
    'CUBEX_CONSTRUCT': { # CubexConstruct.cs:45-47,110-160
        'CHARGE_UP_MOVE': _move(next=('REPEATER_BLAST_MOVE',), powers=(('actor','STRENGTH_POWER',2),), flags=(('isBurrowed',False),('isCharging',True))),
        'REPEATER_BLAST_MOVE': _move((7,), ('REPEATER_BLAST_MOVE_2',), powers=(('actor','STRENGTH_POWER',2),)),
        'REPEATER_BLAST_MOVE_2': _move((7,), ('EXPEL_MOVE',), powers=(('actor','STRENGTH_POWER',2),)),
        'EXPEL_MOVE': _move((5,5), ('REPEATER_BLAST_MOVE',)),
    },
    'EXOSKELETON': { # Exoskeleton.cs:34-38,52-99; CannotRepeat sees last MOVE even across ENRAGE.
        'SKITTER_MOVE': _move((1,1,1), ('MANDIBLES_MOVE',)),
        'MANDIBLES_MOVE': _move((8,), ('ENRAGE_MOVE',)),
        'ENRAGE_MOVE': _move(next=('SKITTER_MOVE','MANDIBLES_MOVE'), powers=(('actor','STRENGTH_POWER',2),)),
    },
    'NIBBIT': { # Nibbit.cs:30-36,68-114
        'BUTT_MOVE': _move((12,), ('SLICE_MOVE',)),
        'SLICE_MOVE': _move((6,), ('HISS_MOVE',), block=(('actor',5),)),
        'HISS_MOVE': _move(next=('BUTT_MOVE',), powers=(('actor','STRENGTH_POWER',2),)),
    },
    'FLYCONID': { # Flyconid.cs:24-82; both INITIAL exits and every RAND CannotRepeat edge.
        'VULNERABLE_SPORES_MOVE': _move(next=('FRAIL_SPORES_MOVE','SMASH_MOVE'), powers=(('player','VULNERABLE_POWER',2),)),
        'FRAIL_SPORES_MOVE': _move((8,), ('VULNERABLE_SPORES_MOVE','SMASH_MOVE'), powers=(('player','FRAIL_POWER',2),)),
        'SMASH_MOVE': _move((11,), ('VULNERABLE_SPORES_MOVE','FRAIL_SPORES_MOVE')),
    },
    'BOWLBUG_SILK': { # BowlbugSilk.cs:32,42-85
        'TOXIC_SPIT_MOVE': _move(next=('THRASH_MOVE',), powers=(('player','WEAK_POWER',1),)),
        'THRASH_MOVE': _move((4,4), ('TOXIC_SPIT_MOVE',)),
    },
    'TOADPOLE': { # Toadpole.cs:49-55,69-110. Negative-Thorns cleanup SPIKE_SPIT remains UNSPECIFIED.
        'WHIRL_MOVE': _move((7,), ('SPIKEN_MOVE',)),
        'SPIKEN_MOVE': _move(next=('SPIKE_SPIT_MOVE',), powers=(('actor','THORNS_POWER',2),)),
    },
    'WRIGGLER': { # Wriggler.cs:34,51-100
        'NASTY_BITE_MOVE': _move((6,), ('WRIGGLE_MOVE',)),
        'WRIGGLE_MOVE': _move(next=('NASTY_BITE_MOVE',), powers=(('actor','STRENGTH_POWER',2),), cards=(('INFECTION','Discard',1),)),
        'SPAWNED_MOVE': _move(next=('NASTY_BITE_MOVE','WRIGGLE_MOVE'), special='wriggler-slot'),
    },
    'AXE_RUBY_RAIDER': { # AxeRubyRaider.cs:24-61
        'SWING_1': _move((5,), ('SWING_2',), block=(('actor',5),)),
        'SWING_2': _move((5,), ('BIG_SWING',), block=(('actor',5),)),
        'BIG_SWING': _move((12,), ('SWING_1',)),
    },
    'CROSSBOW_RUBY_RAIDER': { # CrossbowRubyRaider.cs:28,45-70; reload visual flag is not an AI guard.
        'FIRE_MOVE': _move((14,), ('RELOAD_MOVE',)),
        'RELOAD_MOVE': _move(next=('FIRE_MOVE',), block=(('actor',3),)),
    },
    'TRACKER_RUBY_RAIDER': { # TrackerRubyRaider.cs:23-54
        'TRACK_MOVE': _move(next=('HOUNDS_MOVE',), powers=(('player','FRAIL_POWER',2),)),
        'HOUNDS_MOVE': _move((1,1,1,1,1,1,1,1), ('HOUNDS_MOVE',)),
    },
    'BRUTE_RUBY_RAIDER': { # BruteRubyRaider.cs:25-52
        'BEAT_MOVE': _move((7,), ('ROAR_MOVE',)),
        'ROAR_MOVE': _move(next=('BEAT_MOVE',), powers=(('actor','STRENGTH_POWER',3),)),
    },
    'TWO_TAILED_RAT': { # TwoTailedRat.cs:54-56,117-214
        'SCRATCH_MOVE': _move((8,), ('DISEASE_BITE_MOVE','SCREECH_MOVE','CALL_FOR_BACKUP_MOVE'), special='rat-countdown'),
        'DISEASE_BITE_MOVE': _move((6,), ('SCRATCH_MOVE','SCREECH_MOVE','CALL_FOR_BACKUP_MOVE'), special='rat-countdown'),
        'SCREECH_MOVE': _move(next=('SCRATCH_MOVE','DISEASE_BITE_MOVE','CALL_FOR_BACKUP_MOVE'), powers=(('player','FRAIL_POWER',1),), special='rat-countdown'),
        'CALL_FOR_BACKUP_MOVE': _move(next=('SCRATCH_MOVE','DISEASE_BITE_MOVE','SCREECH_MOVE'), special='rat-summon'),
    },
}


INITIAL_FIXED = {
    'LEAF_SLIME_M':'STICKY_SHOT','TWIG_SLIME_S':'TACKLE_MOVE',
    'TUNNELER':'BITE_MOVE','STABBOT':'STAB_MOVE','ZAPBOT':'ZAP','GUARDBOT':'GUARD_MOVE','NOISEBOT':'NOISE_MOVE',
    'TWIG_SLIME_M':'STICKY_SHOT_MOVE','FUZZY_WURM_CRAWLER':'FIRST_ACID_GOOP','SNEAKY_GREMLIN':'SPAWNED_MOVE',
    'SOUL_FYSH':'BECKON_MOVE','VINE_SHAMBLER':'SWIPE_MOVE','SLUDGE_SPINNER':'OIL_SPRAY_MOVE',
    'GLOBE_HEAD':'SHOCKING_SLAP','DAMP_CULTIST':'INCANTATION_MOVE','CALCIFIED_CULTIST':'INCANTATION_MOVE',
    'CUBEX_CONSTRUCT':'CHARGE_UP_MOVE','BOWLBUG_SILK':'TOXIC_SPIT_MOVE','AXE_RUBY_RAIDER':'SWING_1',
    'CROSSBOW_RUBY_RAIDER':'RELOAD_MOVE','TRACKER_RUBY_RAIDER':'TRACK_MOVE','BRUTE_RUBY_RAIDER':'BEAT_MOVE',
}


def initial_branch(actor):
    model=actor['modelId'].removeprefix('MONSTER.'); g=actor['guards']
    if model in INITIAL_FIXED: return 'fixed', (INITIAL_FIXED[model],)
    if model=='FLYCONID': return 'initial-'+actor['nextMove'], ('FRAIL_SPORES_MOVE','SMASH_MOVE')
    if model=='LEAF_SLIME_S': return 'initial-'+actor['nextMove'], ('GOOP_MOVE','TACKLE_MOVE')
    if model in ('CORPSE_SLUG','SCROLL_OF_BITING'):
        index=g['starterMoveIdx']%3
        moves=('WHIP_SLAP_MOVE','GLOMP_MOVE','GOOP_MOVE') if model=='CORPSE_SLUG' else ('CHOMP','CHEW','MORE_TEETH')
        return 'start-'+str(index),(moves[index],)
    if model=='AXEBOT': return 'stock-override-'+str(g['stockOverridden']).lower(), ('BOOT_UP_MOVE' if g['stockOverridden'] else 'HAMMER_UPPERCUT_MOVE',)
    if model=='CHOMPER': return 'scream-first-'+str(g['screamFirst']).lower(), ('SCREECH_MOVE' if g['screamFirst'] else 'CLAMP_MOVE',)
    if model=='PUNCH_CONSTRUCT': return 'fast-first-'+str(g['startsWithFastPunch']).lower(), ('FAST_PUNCH_MOVE' if g['startsWithFastPunch'] else 'READY_MOVE',)
    if model=='NIBBIT':
        return ('alone',('BUTT_MOVE',)) if g['isAlone'] else ('front',('SLICE_MOVE',)) if g['isFront'] else ('back',('HISS_MOVE',))
    if model=='EXOSKELETON':
        return 'slot-'+actor['slot'], {'first':('SKITTER_MOVE',),'second':('MANDIBLES_MOVE',),'third':('ENRAGE_MOVE',),'fourth':('SKITTER_MOVE','MANDIBLES_MOVE')}[actor['slot']]
    if model=='TWO_TAILED_RAT':
        index=g['starterMoveIndex']; moves=('SCRATCH_MOVE','DISEASE_BITE_MOVE','SCREECH_MOVE')
        return ('random-start',moves) if index==-1 else ('start-'+str(index%3),(moves[index%3],))
    return 'UNSPECIFIED',()


INITIAL_BRANCH_DENOMINATOR = {
    **{m:('fixed',) for m in INITIAL_FIXED},
    'CORPSE_SLUG':('start-0','start-1','start-2'), 'SCROLL_OF_BITING':('start-0','start-1','start-2'),
    'FLYCONID':('initial-FRAIL_SPORES_MOVE','initial-SMASH_MOVE'),
    'LEAF_SLIME_S':('initial-GOOP_MOVE','initial-TACKLE_MOVE'),
    'AXEBOT':('stock-override-false','stock-override-true'), 'CHOMPER':('scream-first-false','scream-first-true'),
    'PUNCH_CONSTRUCT':('fast-first-false','fast-first-true'), 'NIBBIT':('alone','front','back'),
    'EXOSKELETON':('slot-first','slot-second','slot-third','slot-fourth'),
    'TWO_TAILED_RAT':('random-start','start-0','start-1','start-2'),
}


def _powers(creature):
    return {p['id']:p['amount'] for p in creature['powers'] if p['amount'] != 0}


def validate_move_window(window, history, next_actor=None):
    """Real selected native move before/after, not a synthetic damage simulator.

    Fixtures accept baseline damage, native Strength/Weak/Vulnerable and normal block.
    Unspecified defensive/damage modifiers explicitly prevent semantic acceptance.
    """
    errors=[]
    def need(ok,msg):
        if not ok: errors.append(msg)
    model=window.get('monsterId','').removeprefix('MONSTER.'); move=window.get('move')
    rule=SOURCE_MOVES.get(model,{}).get(move)
    if rule is None: return ['UNSPECIFIED_NATIVE_MOVE:'+model+':'+str(move)]
    try:
        before,after=window['before'],window['after']; ref=window['actorRef']
        a=next(c for c in before['enemies'] if c['creatureRef']==ref)
        z=next(c for c in after['enemies'] if c['creatureRef']==ref)
        p,q=before['player'],after['player']; domain=before['domain']>0
        need(window['status']=='COMPLETED_NATIVE_HISTORY' and window['startSeq']<window['historySeq']<window['endSeq'], 'native move did not close')
        completed=[h for h in history if h['seq']==window['historySeq'] and h['kind']=='MonsterPerformedMoveEntry']
        need(len(completed)==1 and completed[0]['actorRef']==ref and completed[0]['move']==move and
             completed[0].get('historyRef')==window['historyRef'], 'move history identity mismatch')
        need(a['modelId']=='MONSTER.'+model and z['creatureRef']==ref and p['creatureRef']==q['creatureRef'], 'world identity mismatch')
        need(a['nextMove']==move, 'selected move/pre-action mismatch')
        if next_actor is not None:
            need(next_actor['nextMove'] in rule['next'], 'source transition mismatch')
            if rule['special']=='wriggler-slot':
                need(next_actor['nextMove']=={'wriggler1':'NASTY_BITE_MOVE','wriggler2':'WRIGGLE_MOVE','wriggler3':'NASTY_BITE_MOVE','wriggler4':'WRIGGLE_MOVE'}[a['slot']],
                     'Wriggler native slot guard selected wrong exit')
        bp,ap=_powers(a),_powers(p)
        # Native combat fixtures must not hide extra modifier branches under a nominal hit formula.
        unsupported={'POWER.INTANGIBLE_POWER','POWER.BUFFER_POWER','POWER.TORIC_TOUGHNESS_POWER','POWER.PLATING_POWER','POWER.BARRICADE_POWER'} & set(ap)
        need(not unsupported, 'UNSPECIFIED_PLAYER_DAMAGE_MODIFIER:'+','.join(sorted(unsupported)))
        strength=bp.get('POWER.STRENGTH_POWER',0)
        multiplier=(0.75 if bp.get('POWER.WEAK_POWER',0)>0 else 1)*(1.5 if ap.get('POWER.VULNERABLE_POWER',0)>0 else 1)
        # Source formula for native ordinary attack: flat strength, Weak/Vulnerable, floor.
        expected_hits=[max(0,int((v+strength)*multiplier)) for v in rule['hits']]
        damage=[h for h in history if window['startSeq']<h['seq']<window['historySeq'] and h['kind']=='DamageReceivedEntry' and
                h.get('dealerRef')==ref and h.get('receiverRef')==p['creatureRef']]
        need([h['blocked']+h['hpLost'] for h in damage]==expected_hits, 'native hit values/count differ from source')
        need(p['hp']-q['hp']==sum(h['hpLost'] for h in damage), 'player HP does not match actual receipts')
        need(q['block']==max(0,p['block']-sum(expected_hits)), 'native per-move block absorption mismatch')
        entities={c['creatureRef']:c for c in before['enemies']+[p]}
        updated={c['creatureRef']:c for c in after['enemies']+[q]}
        expected_power={r:_powers(c).copy() for r,c in entities.items()}
        powers=list(rule['powers'])
        if rule['special']=='stock-strength': powers.append(('actor','STRENGTH_POWER',3*(2-a['guards']['stockAmount'])))
        for target,key,amount in powers:
            r=p['creatureRef'] if target=='player' else ref
            if amount and (not domain or (target=='actor' and key=='STRENGTH_POWER')):
                full='POWER.'+key
                expected_power[r][full]=expected_power[r].get(full,0)+amount
                if expected_power[r][full]==0: del expected_power[r][full]
        for r,old in entities.items():
            need(r in updated, 'unexpected actor removal')
            if r not in updated: continue
            need(_powers(updated[r])==expected_power[r], 'native power contribution/suppression mismatch:'+r)
            if r!=p['creatureRef']:
                expected_block=old['block']
                for target,amount in rule['block']:
                    if (target=='actor' and r==ref) or (target=='fabricators' and old['modelId']=='MONSTER.FABRICATOR'):
                        expected_block+=amount
                need(updated[r]['block']==expected_block, 'direct enemy block must survive Domain:'+r)
                need(updated[r]['hp']==old['hp'], 'unexpected enemy HP change:'+r)
        previous={c['cardRef'] for c in before['cards']}
        added=[c for c in after['cards'] if c['cardRef'] not in previous]
        expected_cards=Counter({('CARD.'+code,pile):count for code,pile,count in rule['cards']}) if not domain else Counter()
        need(Counter((c['id'],c['pile']) for c in added)==expected_cards, 'generated card identity/count/pile or Domain suppression mismatch')
        need(previous <= {c['cardRef'] for c in after['cards']}, 'unexpected existing card loss in enemy move')
        for card in before['cards']:
            later=next(c for c in after['cards'] if c['cardRef']==card['cardRef'])
            expected_affliction=card.get('affliction'); expected_amount=card.get('afflictionAmount')
            if rule['special']=='tangled-affliction' and not domain and card['type']=='Attack':
                expected_affliction='AFFLICTION.ENTANGLED'; expected_amount=1
            need((later.get('affliction'),later.get('afflictionAmount'))==(expected_affliction,expected_amount),
                 'native card affliction contribution/suppression mismatch')
        for key,value in rule['flags']: need(z['guards'][key]==value, 'native non-power state flag must commit:'+key)
        newcomers=[c for c in after['enemies'] if c['creatureRef'] not in entities]
        if rule['special']=='rat-countdown':
            need(z['guards']['turnsUntilSummonable']==a['guards']['turnsUntilSummonable']-1, 'rat countdown incorrectly suppressed or doubled')
        if rule['special']=='rat-summon':
            free=[s for s in before['slots'] if s not in {c['slot'] for c in before['enemies']}]
            need(len(newcomers)==(1 if free and not domain else 0), 'rat summon count/Domain suppression mismatch')
            if newcomers:
                c=newcomers[0]
                need(c['modelId']=='MONSTER.TWO_TAILED_RAT' and c['slot']==free[-1] and 17<=c['hp']<=21 and c['alive'], 'wrong rat spawn identity/slot/HP')
            oldrats=[c for c in before['enemies'] if c['modelId']=='MONSTER.TWO_TAILED_RAT']
            maximum=max(c['guards']['callForBackupCount'] for c in oldrats)+1
            for rat in [c for c in after['enemies'] if c['modelId']=='MONSTER.TWO_TAILED_RAT']:
                prior=entities.get(rat['creatureRef'])
                expected=prior['guards']['callForBackupCount'] if domain and prior else maximum
                need(rat['guards']['callForBackupCount']==expected, 'rat shared backup counter commit mismatch')
        else: need(not newcomers, 'unexpected summoned actor')
    except (KeyError,TypeError,ValueError,StopIteration): errors.append('missing/malformed native semantic window')
    return errors


def validate_case_semantics(case, *, transitions=True):
    errors=[]; rows=[]
    windows=case.get('moveWindows')
    if not isinstance(windows,list): return ['missing native selected-move snapshots'],rows
    moves=[h for h in case['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry']
    if Counter(w.get('historyRef') for w in windows)!=Counter(h['historyRef'] for h in moves):
        errors.append('native move windows are missing/duplicate/incomplete')
    for actor in case.get('initial',{}).get('enemies',[]):
        if actor['modelId'].removeprefix('MONSTER.') not in INITIAL_BRANCH_DENOMINATOR: continue
        try:
            branch,moves=initial_branch(actor)
            first=next((w for w in windows if w['actorRef']==actor['creatureRef']),None)
            ok=actor['nextMove'] in moves and first is not None and first['move']==actor['nextMove']
            rows.append(dict(monster=actor['modelId'],move='@initial:'+branch,status='PASS' if ok else 'FAIL',
                             side='Initial',domain=False,transitionStatus='NOT_OBSERVED',errors=[] if ok else ['source initial guard selection mismatch']))
            if not ok: errors.append(actor['modelId']+': source initial guard selection mismatch')
        except (KeyError,TypeError,ValueError): errors.append(actor['modelId']+': missing native initial guard inputs')
    for w in windows:
        following=next((e for b in case['boundaries'] if b['seq']>w.get('endSeq',float('inf')) for e in b['enemies'] if e['creatureRef']==w.get('actorRef')),None)
        failures=validate_move_window(w,case['nativeHistory'],following if transitions else None)
        unknown=bool(failures) and all(e.startswith('UNSPECIFIED_NATIVE_MOVE:') for e in failures)
        rows.append(dict(monster=w['monsterId'],move=w['move'],side=w['side'],domain=w['before']['domain']>0,
                         status='UNSPECIFIED' if unknown else 'FAIL' if failures else 'PASS',
                         transitionStatus='NOT_OBSERVED' if following is None or not transitions else 'UNSPECIFIED' if unknown else 'FAIL' if failures else 'PASS', errors=failures))
        if not unknown: errors.extend(w['monsterId']+':'+w['move']+':'+e for e in failures)
    return errors,rows


def validate_threshold_case(case, spec):
    """Finite legal damage path, not a full-HP idle trace or injected block break.

    TunnelerWeak source HP87, BITE13, direct BURROW32, BELOW23; B01=6,
    C10=6+actual absorbed, Domain lightning4. Only actual paid actions produce damage.
    """
    errors=[]
    def need(ok,msg):
        if not ok: errors.append(msg)
    try:
        domain=spec['policy'].endswith('-on'); engage='-engage-' in spec['policy']; n=spec['turnBudget']
        need(case.get('paidStrategy')=='C21-if-domain;C10-plus-C12-or-three-B01;fixed-3-energy-budget', 'unbound threshold input strategy')
        need(case['completedCycles']==n and len(case['boundaries'])==n+1, 'threshold finite cycle incomplete; early terminal is not success')
        need(not case.get('paidAttempts'), 'threshold card not playable/target absent')
        if len(case['boundaries'])!=n+1: return errors
        bounds=case['boundaries']; actors=[b['enemies'][0] for b in bounds]; ref=actors[0]['creatureRef']
        need(all(len(b['enemies'])==1 and b['enemies'][0]['creatureRef']==ref and b['enemies'][0]['alive'] for b in bounds), 'threshold requires native single living Tunneler')
        sequence=['BITE_MOVE','BURROW_MOVE','BELOW_MOVE','BELOW_MOVE'] if domain else (
            ['BITE_MOVE','BURROW_MOVE','BELOW_MOVE','BELOW_MOVE','STUNNED'] if engage else ['BITE_MOVE','BURROW_MOVE','BELOW_MOVE','STUNNED','BITE_MOVE'])
        final='BELOW_MOVE' if domain else 'BITE_MOVE' if engage else 'BURROW_MOVE'
        expected_hp=([87,64,64,41,18] if engage else [87,67,47,47,27]) if domain else (
            [87,73,73,73,71,65] if engage else [87,69,51,51,47,29])
        expected_block=([0,0,0,0,0] if engage else [0,0,32,0,0]) if domain else (
            [0,0,26,12,0,0] if engage else [0,0,32,14,0,0])
        need([a['hp'] for a in actors]==expected_hp, 'paid damage/Domain lightning threshold HP path mismatch')
        need([a['block'] for a in actors]==expected_block, 'native 32-block retention/threshold path mismatch')
        need(actors[-1]['nextMove']==final, 'threshold final native transition mismatch')
        histories=case['nativeHistory']; moves=[h for h in histories if h['kind']=='MonsterPerformedMoveEntry']
        need([h['move'] for h in moves]==sequence, 'dynamic STUNNED/return path mismatch')
        need(all(h['actorRef']==ref and h['side']==('Player' if engage else 'Enemy') for h in moves), 'threshold actor/scheduling mismatch')
        breaks=[]
        for cycle in range(n):
            rnd=bounds[cycle]['round']
            plays=[p for p in case['inputs'] if p['type']=='PlayCardAction' and p['turnBefore']==rnd]
            codes=(['C21'] if domain else []) + (['C10']+['C12']*(1 if domain else 2) if engage else ['B01']*(2 if domain else 3))
            need([p['cardId'] for p in plays]==['CARD.VOLIBEAR_'+c for c in codes], 'threshold missing exact legal paid card sequence')
            need([p['energyBefore'] for p in plays]==[3,2,1] and [p['energyAfter'] for p in plays]==[2,1,0], 'threshold three-energy payment chain mismatch')
            need(sum(h['round']==rnd for h in moves)==1, 'threshold early action replay or lost natural opportunity')
            for play in plays:
                interval=[h for h in histories if play['seq']<h['seq']<play['endSeq']]
                need(play['completionObserved'] and play['pileAfter']=='Discard', 'threshold native card completion/destination absent')
                need(sum(h['amount'] for h in interval if h['kind']=='EnergySpentEntry')==1, 'threshold missing actual energy payment')
                need(sum(h['kind']=='CardPlayStartedEntry' and h['cardRef']==play['cardRef'] for h in interval)==1 and
                     sum(h['kind']=='CardPlayFinishedEntry' and h['cardRef']==play['cardRef'] for h in interval)==1, 'threshold native card lifecycle absent')
                inside=[h for h in interval if h['kind']=='MonsterPerformedMoveEntry']
                need(len(inside)==(1 if play['cardId']=='CARD.VOLIBEAR_C10' else 0), 'threshold Engage did not occur inside real paid C10')
                if play['cardId']!='CARD.VOLIBEAR_C21': need(play['domainBefore']==int(domain), 'threshold Domain entry/expiry incorrect')
                else: need(play['domainBefore']==0 and play['domainAfter']==1, 'threshold requires fresh paid Domain each natural cycle')
                before=next(e for e in play['enemiesBefore'] if e['creatureRef']==ref)
                after=next(e for e in play['enemiesAfter'] if e['creatureRef']==ref)
                if not before['guards']['isStunned'] and after['guards']['isStunned']:
                    receipts=[h for h in interval if h['kind']=='DamageReceivedEntry' and h['receiverRef']==ref]
                    need(before['block']>0 and after['block']==0 and sum(h['blocked'] for h in receipts)>=before['block'], 'stun appeared without actual paid block break')
                    need(_powers(before).get('POWER.BURROWED_POWER')==1 and not _powers(after).get('POWER.BURROWED_POWER'), 'native break must remove Burrowed')
                    need(after['nextMove']=='STUNNED', 'native dynamic stun substituted by declared DIZZY_MOVE')
                    breaks.append(play['cardRef'])
        need(len(breaks)==(0 if domain else 1), 'threshold guard outcomes not actually exercised')
        semantic_errors,_=validate_case_semantics(case,transitions=False)
        errors.extend(semantic_errors)
    except (KeyError,TypeError,ValueError,StopIteration): errors.append('missing/malformed threshold native evidence')
    return errors


def validate_formal_paid_case(case, spec):
    """Paid scheduling acceptance only; effects/guards remain separately NOT_RUN."""
    errors = []
    def need(ok, message):
        if not ok: errors.append(message)
    try:
        target_id = 'MONSTER.' + spec['caseId'].split(':')[1]
        need(case.get('paidStrategy')=='C21-if-domain;C11-or-B02;C12-fixed-remaining-3-energy-budget', 'unbound formal defensive input strategy')
        domain = spec['policy'].endswith('-on'); engage = '-engage-' in spec['policy']
        bounds = case['boundaries']; moves = [h for h in case['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry']
        need(case['completedCycles'] == spec['turnBudget'] and len(bounds)==spec['turnBudget']+1,
             'selected finite AI cycles not closed; terminal is not branch completion')
        need(case.get('paidAttempts') == [], 'selected target/payment was NOT_OBSERVED or NOT_PLAYABLE')
        for choice in case.get('choiceInputs', []):
            need(choice.get('api')=='Viewport.PushInput' and choice.get('kind')=='knowledge-disintegration-only' and
                 choice.get('selectedCardId')=='CARD.DISINTEGRATION' and choice.get('pressed')==[True,False] and
                 choice.get('focusMatched') is True and choice.get('physicalInputValidated') is False and
                 len(choice.get('candidates',[]))==2 and 'CARD.DISINTEGRATION' in choice['candidates'],
                 'unknown or bypassed Knowledge choice input')
            need(all(type(choice.get(k)) is int for k in ('seq','pressSeq','releaseSeq','endSeq')) and
                 choice['seq']==choice['pressSeq']<choice['releaseSeq']<choice['endSeq'], 'invalid Knowledge input event order')
            need(any(m.get('monsterId')=='MONSTER.KNOWLEDGE_DEMON' and m['move']=='CURSE_OF_KNOWLEDGE_MOVE' and
                     m['seq']>choice['seq'] for m in moves), 'Knowledge choice did not return to genuine enemy action')
        for before, after in zip(bounds, bounds[1:]):
            plays = [i for i in case['inputs'] if i['type']=='PlayCardAction' and i['turnBefore']==before['turn']]
            expected = (['CARD.VOLIBEAR_C21'] if domain else []) + ['CARD.VOLIBEAR_C11' if engage else 'CARD.VOLIBEAR_B02'] + ['CARD.VOLIBEAR_C12']*(1 if domain else 2)
            need([p['cardId'] for p in plays]==expected, 'missing finite-cycle paid inputs')
            need([p['energyBefore'] for p in plays]==[3,2,1] and [p['energyAfter'] for p in plays]==[2,1,0],
                 'formal fixed three-energy budget/payment chain mismatch')
            candidates = [e for e in before['enemies'] if e['modelId']==target_id and e['alive']]
            need(bool(candidates), 'formal target not live; no spawn/branch coverage inferred')
            for play in plays:
                need(play.get('pileAfter')=='Discard' and play.get('completionObserved') is True, 'native paid completion/destination absent')
                window = [h for h in case['nativeHistory'] if play['seq'] < h['seq'] < play['endSeq']]
                need(play['energyBefore']-play['energyAfter']==1 and
                     sum(h.get('amount',0) for h in window if h['kind']=='EnergySpentEntry')==1, 'payment receipt missing')
                if play['cardId']=='CARD.VOLIBEAR_C21':
                    need(play['domainBefore']==0 and play['domainAfter']==1, 'paid Domain entry missing')
                else:
                    need(play['domainBefore']==int(domain), 'wrong Domain at selected action')
                    if play['cardId']=='CARD.VOLIBEAR_C11':
                        target=play['targetRef']
                        need(target in {e['creatureRef'] for e in candidates}, 'wrong formal target')
                        early=[m for m in moves if m['actorRef']==target and play['seq']<m['seq']<play['endSeq']]
                        need(len(early)==1 and early[0]['side']=='Player', 'paid Engage did not finish genuine native move')
                        need(not any(m['actorRef']==target and m['round']==before['round'] and m['side']=='Enemy' for m in moves),
                             'early-consumed enemy acted again in genuine enemy phase')
            if not engage:
                need(any(m.get('monsterId')==target_id and m['round']==before['round'] and m['side']=='Enemy' for m in moves),
                     'selected target natural action not observed')
            need(any(s['side']=='Enemy' and s['round']==before['round'] for s in case['turnSignals']) and
                 after['turn']>before['turn'], 'genuine enemy/next-player scheduling absent')
            need(after['domain']==0, 'finite Domain did not expire after next-player draw')
    except (KeyError, TypeError, ValueError, IndexError):
        errors.append('malformed formal paid evidence')
    return errors


def validate_paid_case(case, spec):
    """Independent locked-source semantics, not a count-of-traces coverage gate."""
    errors = []
    def need(ok, message):
        if not ok: errors.append(message)
    try:
        policy = spec['policy']; domain = policy.endswith('-on'); engage = '-engage-' in policy
        target_id = next(t for t in PAID_TARGETS if spec['caseId'] == f'paid-{t}-{policy}')
        bounds = case['boundaries']; inputs = case['inputs']; history = case['nativeHistory']
        need(len(bounds) == 5 and case['completedCycles'] == 4, 'four full AI cycles plus next-player boundaries required')
        enemies = {e['creatureRef']: e['modelId'].split('.', 1)[1] for e in bounds[0]['enemies']}
        need(Counter(enemies.values()) == Counter(PAID_TARGETS), 'exact native SlimesWeak actors required')
        target = next(ref for ref, mid in enemies.items() if mid == target_id)
        moves = [h for h in history if h['kind'] == 'MonsterPerformedMoveEntry']
        for ref, mid in enemies.items():
            actual = [m for m in moves if m['actorRef'] == ref]
            need(len(actual) == 4, mid + ': missing/duplicate action across four rounds')
            names = [m['move'] for m in actual]
            if mid == 'LEAF_SLIME_M':
                need(names == ['STICKY_SHOT', 'CLUMP_SHOT'] * 2, 'LeafSlimeM deterministic cycle/transition mismatch')
            elif mid == 'LEAF_SLIME_S':
                need(len(names) == 4 and set(names) == set(PAID_MOVES[mid]) and
                     all(a != b for a, b in zip(names, names[1:])), 'LeafSlimeS RAND CannotRepeat exits not closed')
            else:
                need(names == ['TACKLE_MOVE'] * 4, 'TwigSlimeS self-loop mismatch')
            for cycle, move in enumerate(actual):
                before, after = bounds[cycle:cycle+2]
                need(move['round'] == before['round'], 'action round mismatch')
                need(move['side'] == ('Player' if engage and ref == target else 'Enemy'), 'wrong scheduling side or early opportunity replayed')
                prior = next(e for e in before['enemies'] if e['creatureRef'] == ref)
                following = next(e for e in after['enemies'] if e['creatureRef'] == ref)
                need(prior['nextMove'] == move['move'], 'actual move differs from legal prepared state')
                expected_next = ('STICKY_SHOT' if move['move'] == 'CLUMP_SHOT' else 'CLUMP_SHOT') if mid == 'LEAF_SLIME_M' else (
                    ('GOOP_MOVE' if move['move'] == 'TACKLE_MOVE' else 'TACKLE_MOVE') if mid == 'LEAF_SLIME_S' else 'TACKLE_MOVE')
                need(following['nextMove'] == expected_next, 'next intent advanced incorrectly')
                damage = [h for h in history if h['kind'] == 'DamageReceivedEntry' and h.get('dealerRef') == ref and
                          h.get('receiverRef') == before['playerCreatureRef'] and h['round'] == move['round']]
                expected_damage = PAID_MOVES[mid].get(move['move'], (-1, -1))[0]
                need(sum(h['hpLost'] + h['blocked'] for h in damage) == expected_damage,
                     mid + ': allowed native attack damage changed')
                need(len(damage) == (1 if expected_damage else 0), 'attack/nonattack branch receipt mismatch')
        for cycle in range(4):
            before, after = bounds[cycle:cycle+2]
            plays = [i for i in inputs if i['type'] == 'PlayCardAction' and i['turnBefore'] == before['turn']]
            expected = (['CARD.VOLIBEAR_C21'] if domain else []) + ['CARD.VOLIBEAR_C11' if engage else 'CARD.VOLIBEAR_B02']
            need([i['cardId'] for i in plays] == expected, 'missing/extra paid Domain or Engage/control card')
            for play in plays:
                window = [h for h in history if play['seq'] < h['seq'] < play['endSeq']]
                need(play['energyBefore'] - play['energyAfter'] == 1 and
                     sum(h.get('amount', 0) for h in window if h['kind'] == 'EnergySpentEntry') == 1, 'actual payment missing')
                need(play.get('pileAfter') == 'Discard' and play.get('completionObserved') is True, 'paid card native destination/completion missing')
                for kind in ('CardPlayStartedEntry', 'CardPlayFinishedEntry'):
                    need(sum(h['kind'] == kind and h.get('cardRef') == play['cardRef'] for h in window) == 1, 'paid lifecycle missing')
                if play['cardId'] == 'CARD.VOLIBEAR_C21':
                    need(play['domainBefore'] == 0 and play['domainAfter'] == 1, 'paid C21 failed to establish finite Domain')
                else:
                    need(play['domainBefore'] == play['domainAfter'] == int(domain), 'wrong Domain during native action')
                    if engage:
                        need(play['targetRef'] == target, 'wrong Engage target')
                        early = [m for m in moves if play['seq'] < m['seq'] < play['endSeq']]
                        need(len(early) == 1 and early[0]['actorRef'] == target, 'Engage not inside paid card lifecycle')
                        status_count = PAID_MOVES[target_id][early[0]['move']][1] if len(early) == 1 else -1
                        old = {c['cardRef'] for c in play['cardsBefore']}
                        new_slimed = [c for c in play['cardsAfter'] if c['cardRef'] not in old and c['id'] == 'CARD.SLIMED']
                        need(len(new_slimed) == (0 if domain else status_count), 'Engage status contribution/suppression mismatch')
            need(after['domain'] == 0, 'Domain1 failed to expire after protected next-player draw')
            old = {c['cardRef'] for c in before['cards']}
            slimed = [c for c in after['cards'] if c['cardRef'] not in old and c['id'] == 'CARD.SLIMED']
            expected_status = sum(PAID_MOVES[enemies[m['actorRef']]][m['move']][1] for m in moves if m['round'] == before['round'])
            need(len(slimed) == (0 if domain else expected_status), 'native status creation/Domain suppression mismatch')
    except (KeyError, TypeError, ValueError, StopIteration, IndexError):
        errors.append('missing/malformed paid cycle evidence')
    return errors


SOURCE_UNREACHABLE = {
    'SingleAttackMoveMonster', 'MultiAttackMoveMonster', 'OneHpMonster', 'TenHpMonster',
    'MockAttackMonster', 'MockIntangibleMonster', 'MockReattachMonster',
    'TheAdversaryMkOne', 'TheAdversaryMkTwo', 'TheAdversaryMkThree',
}


def source_classification(catalog):
    # Source-audited absence from normal contents, not a reinterpretation of raw discovery.
    return [dict(id=c['id'], type=c['type'],
                 status='SOURCE_UNREACHABLE' if c['type'].rsplit('.',1)[1] in SOURCE_UNREACHABLE or
                        c['type'].endswith('.TunnelerNormal') else 'REACHABILITY_UNRESOLVED',
                 reason=('definitions-and-AbstractModelSubtypes-only;not-normal-content' if c['type'].rsplit('.',1)[1] in SOURCE_UNREACHABLE
                         else 'unpooled-encounter;TunnelerWeak-remains-formal' if c['type'].endswith('.TunnelerNormal')
                         else 'not-source-classified;not-an-exemption')) for c in catalog['unreachedCandidates']]


def formal_source_requirements(catalog, source_root):
    """Finite source locations for every formal model; never infer guard outcomes from text.

    This augments the existing native catalog, not its source policy. Named states and
    explicit condition/transition sites are lower bounds; complex helper/passive branches
    remain UNKNOWN until independently specified. No source text is executed.
    """
    root = Path(source_root)
    requirements = []
    for monster in catalog['monsters']:
        typename = monster['type']; namespace, name = typename.rsplit('.', 1)
        path = root / namespace / (name + '.cs')
        row = dict(monster=monster['id'], type=typename, status='NOT_RUN',
                   sourceAvailable=path.is_file(), states=[], transitions=[], conditions=[], effects=[],
                   passiveCoverage='NOT_RUN', branchInventoryComplete=False)
        if path.is_file():
            text = path.read_text(encoding='utf-8-sig')
            for number, line in enumerate(text.splitlines(), 1):
                for match in re.finditer(r'new\s+(MoveState|RandomBranchState|ConditionalBranchState)\s*\(\s*"([^"]+)"', line):
                    row['states'].append(dict(id=match[2], kind=match[1], line=number, status='NOT_RUN'))
                if any(marker in line for marker in ('.FollowUpState', '.AddBranch(', '.AddState(', '.SetFollowUpState(', '.TransitionTo(')):
                    row['transitions'].append(dict(line=number, expression=line.strip(), guardEvaluation='UNKNOWN', status='NOT_RUN'))
                if re.search(r'\b(if|switch)\s*\(|\bcase\s|=>.*\?', line):
                    row['conditions'].append(dict(line=number, expression=line.strip(), outcomes=['NOT_RUN','NOT_RUN']))
                if re.search(r'\b\w+Cmd\.|Power<|Apply<', line):
                    row['effects'].append(dict(line=number, expression=line.strip(), domainExpectation='UNSPECIFIED', status='NOT_RUN'))
        entry=monster['id'].removeprefix('MONSTER.')
        row['independentMoveExpectations']=SOURCE_MOVES.get(entry,{})
        row['initialGuardBranches']=[dict(branch=b,status='NOT_RUN') for b in INITIAL_BRANCH_DENOMINATOR.get(entry,())]
        row['dynamicStates']=[dict(id='STUNNED',source='Creature.StunInternal + BurrowedPower.AfterBlockBroken',status='NOT_RUN')] if entry=='TUNNELER' else []
        requirements.append(row)
    return dict(gameAssemblyMvid=catalog['gameAssemblyMvid'], formalMonsters=requirements,
                requiredPaidCases=formal_cases(catalog), completeAiCoverage=False,
                eventOnlyEncounters=[dict(id=e['id'],status='EVENT_SETUP_REQUIRED_NOT_RUN') for e in catalog['encounters']
                                     if e['included'] and not any(e['id'] in ids for ids in registered(catalog).values())],
                unreachedCandidates=catalog['unreachedCandidates'], sourceClassification=source_classification(catalog),
                limitations=['source sites are finite lower bounds, not evaluated semantic oracles',
                             'helper/power/passive and random/threshold outcomes remain explicitly unverified',
                             'TunnelerWeak and every native rooted formal model remain required'])


def formal_paid_coverage(catalog, cases=()):
    required = formal_cases(catalog)
    by_id = {c['caseId']: c for c in cases}
    semantic_rows=[]
    for case in cases:
        _,rows=validate_case_semantics(case)
        semantic_rows.extend(dict(caseId=case['caseId'],**r) for r in rows)
    def move_status(model,move,side,domain):
        found=[r for r in semantic_rows if (r['monster'],r['move'],r['side'],r['domain'])==(model,move,side,domain)]
        return 'FAIL' if any(r['status']=='FAIL' for r in found) else 'PASS' if any(r['status']=='PASS' for r in found) else 'NOT_RUN'
    return dict(completeAiCoverage=False, semanticObservations=semantic_rows,
                independentMoveRequirements=[dict(monster=m['id'],move=move,side=side,domain=domain,status=move_status(m['id'],move,side,domain))
                    for m in catalog['monsters'] for move in SOURCE_MOVES.get(m['id'].removeprefix('MONSTER.'),{})
                    for side in ('Player','Enemy') for domain in (False,True)],
                initialGuardRequirements=[dict(monster=m['id'],branch=branch,status=move_status(m['id'],'@initial:'+branch,'Initial',False))
                    for m in catalog['monsters'] for branch in INITIAL_BRANCH_DENOMINATOR.get(m['id'].removeprefix('MONSTER.'),())],
                requiredCases=[dict(caseId=s['caseId'],
                    schedulingStatus=('PASS' if not validate_formal_paid_case(by_id[s['caseId']],s) else 'FAIL')
                        if s['caseId'] in by_id else 'NOT_RUN',
                    effectBranches='PARTIAL' if any(r['caseId']==s['caseId'] and not r['move'].startswith('@') and r['status']=='PASS' for r in semantic_rows) else 'NOT_RUN',
                    guardOutcomes='PARTIAL' if any(r['caseId']==s['caseId'] and r['move'].startswith('@initial:') and r['status']=='PASS' for r in semantic_rows) else 'NOT_RUN',
                    passiveCoverage='NOT_RUN') for s in required],
                formalMonsters=[dict(id=m['id'], branchInventory='UNKNOWN_NOT_EXHAUSTIVELY_IDENTIFIED') for m in catalog['monsters']],
                formalEncounters=[dict(id=e['id'], terminalAcceptance='NOT_RUN') for e in catalog['encounters'] if e['included']],
                unreachedCandidates=catalog['unreachedCandidates'])


def paid_coverage(catalog, cases=()):
    """Keep all formal catalogue rows and unknown branch denominators, even on subset success."""
    verified = {c['caseId'] for c in cases if c.get('caseId') in {s['caseId'] for s in paid_cases()} and
                not validate_paid_case(c, next(s for s in paid_cases() if s['caseId'] == c['caseId']))}
    return dict(completeAiCoverage=False, requiredCases=[dict(caseId=s['caseId'], status='PASS' if s['caseId'] in verified else 'NOT_RUN') for s in paid_cases()],
                formalMonsters=[dict(id=m['id'], status='PARTIAL' if m['id'].split('.', 1)[1] in PAID_TARGETS and verified else 'NOT_RUN',
                                    effectBranches='UNKNOWN_NOT_EXHAUSTIVELY_IDENTIFIED', passiveCoverage='NOT_RUN') for m in catalog['monsters']],
                formalEncounters=[dict(id=e['id'], terminalAcceptance='NOT_RUN') for e in catalog['encounters'] if e['included']],
                remainingKnownStates=[dict(monster=i['modelId'], state=s['id'], status='NOT_RUN') for i in catalog['liveInstances'] for s in (i.get('states') or [])],
                unreachedCandidates=catalog['unreachedCandidates'], sourceClassification=source_classification(catalog),
                remainingBranches=['LeafSlimeS initial RAND alternative seed', 'all other formal enemy moves/transitions/effect guards',
                                   'all formal enemy passive branches', 'all formal encounter terminal paths'])


def exploration_evidence(log, run_id, evidence_root, *, selection_path, catalog, prerequisite=None):
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        return None, False
    try:
        summary = json.loads(lines[0]); root = Path(evidence_root).resolve()
        if summary.get('manifest') != 'enemy-exploration.json':
            return summary, False
        path = (root/summary['manifest']).resolve()
        if path.parent != root:
            return summary, False
        raw = path.read_bytes(); data = json.loads(raw)
        selection_bytes = Path(selection_path).read_bytes(); selection = json.loads(selection_bytes)
        errors = validate_exploration(data, selection=selection, catalog=catalog, run_id=run_id)
        if data.get('selectionSha256') != hashlib.sha256(selection_bytes).hexdigest():
            errors.append('selection hash mismatch')
        if selection.get('mode') == 'explore':
            if not prerequisite or prerequisite.get('selection', {}).get('mode') != 'smoke' or prerequisite.get('token') != selection.get('prerequisiteToken'):
                errors.append('missing/mismatched native smoke prerequisite')
            else:
                errors += validate_exploration(prerequisite, selection=prerequisite['selection'], catalog=catalog, run_id=prerequisite['token'])
        for key, expected in dict(token=run_id, scenario='enemy-exploration', acceptance='bounded-native-exploration-only',
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), caseCount=len(selection['cases']), completed=True, failure=None).items():
            if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
                errors.append('summary '+key)
        summary['validationErrors'] = errors
        summary['completeAiCoverage'] = False
        if selection.get('mode') == 'paid-acceptance':
            summary['coverage'] = paid_coverage(catalog, data.get('cases', []) if not errors else [])
        elif selection.get('mode') == 'formal-paid':
            summary['coverage'] = formal_paid_coverage(catalog, data.get('cases', []) if not errors else [])
        elif selection.get('mode') == 'paid-threshold':
            summary['coverage'] = formal_paid_coverage(catalog)
            by_id={c['caseId']:c for c in data.get('cases',[])}
            summary['coverage']['thresholdCases']=[dict(caseId=s['caseId'],status='PASS' if not errors and s['caseId'] in by_id and
                not validate_threshold_case(by_id[s['caseId']],s) else 'FAIL' if s['caseId'] in by_id else 'NOT_RUN') for s in threshold_cases()]
        return summary, not errors
    except (OSError, TypeError, KeyError, ValueError, AttributeError):
        return None, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--mode', choices=['smoke', 'explore', 'paid-acceptance', 'formal-paid', 'paid-threshold'], default='smoke')
    parser.add_argument('--batch-index', type=int, default=0, help='formal-paid: select next finite batch of at most 80 cases')
    parser.add_argument('--native-source', type=Path, help='optional locked decompiled native source root')
    parser.add_argument('--requirements-output', type=Path, help='optional ignored artifact with exact still-unverified source sites')
    parser.add_argument('--prerequisite', type=Path)
    parser.add_argument('--encounter', action='append')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
    prerequisite = json.loads(args.prerequisite.read_text(encoding='utf-8')) if args.prerequisite else None
    selection = prepare_selection(catalog, mode=args.mode, encounters=args.encounter, prerequisite=prerequisite, batch_index=args.batch_index)
    if args.requirements_output:
        if not args.native_source:
            parser.error('--requirements-output requires --native-source')
        args.requirements_output.parent.mkdir(parents=True, exist_ok=True)
        args.requirements_output.write_text(json.dumps(formal_source_requirements(catalog, args.native_source), indent=2)+'\n', encoding='utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selection, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(mode=selection['mode'], selected=len(selection['cases']), output=str(args.output),
                         prerequisiteToken=selection['prerequisiteToken'], gameExecuted=False)))


if __name__ == '__main__':
    main()
