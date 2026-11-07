"""Strict evidence gate for two same-seed native scheduling/isolation cases.

PASS here is only this bounded MVP, never complete AI/move/branch coverage.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

PREFIX = '[Volibear] ENEMY_MATRIX_RESULT '
SEED = 'VOLIBEARTEST'
DECK = {'CARD.VOLIBEAR_B01': 4, 'CARD.VOLIBEAR_B02': 4, 'CARD.VOLIBEAR_B03': 1, 'CARD.VOLIBEAR_B04': 1}
MOVES = {
    'MONSTER.LEAF_SLIME_S': {'TACKLE_MOVE', 'GOOP_MOVE'},
    'MONSTER.TWIG_SLIME_S': {'TACKLE_MOVE'},
    'MONSTER.LEAF_SLIME_M': {'CLUMP_SHOT', 'STICKY_SHOT'},
    'MONSTER.TWIG_SLIME_M': {'POKEY_POUNCE_MOVE', 'STICKY_SHOT_MOVE'},
}
HP_RANGES = {'MONSTER.LEAF_SLIME_S': (11, 15), 'MONSTER.TWIG_SLIME_S': (7, 11),
             'MONSTER.LEAF_SLIME_M': (32, 35), 'MONSTER.TWIG_SLIME_M': (26, 28)}
FRESH_REFS = ('runRef', 'combatRef', 'encounterRef', 'playerRef', 'playerCreatureRef',
              'playerCombatRef', 'queueRef', 'executorRef', 'choiceSyncRef')


def validate_matrix(data, *, run_id):
    try:
        return _validate(data, run_id)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as error:
        return ['malformed matrix evidence: ' + type(error).__name__]


def _validate(data, run_id):
    errors = []
    def need(value, message):
        if not value:
            errors.append(message)
        return bool(value)
    def eq(actual, expected, message):
        return need(type(actual) is type(expected) and actual == expected, message)
    if not need(isinstance(data, dict), 'matrix manifest must be object'):
        return errors
    fixed = dict(schema=1, token=run_id, scenario='enemy-matrix-mvp', acceptance='natural-scheduling-isolation-only',
                 gameVersion=EXPECTED_GAME_VERSION, gameCommit=EXPECTED_GAME_COMMIT, testMode=False, seed=SEED,
                 enemyHpModified=False, forcedMoves=False, directPerformMoveCalls=0, completeAiCoverage=False)
    for key, expected in fixed.items():
        eq(data.get(key), expected, 'invalid ' + key)
    need('failure' in data and data['failure'] is None, 'native coordinator failed/missing result')
    need(type(data.get('processId')) is int and data['processId'] > 0, 'missing native process ID')
    for key in ('gameAssemblyMvid', 'modAssemblyMvid'):
        need(isinstance(data.get(key), str) and len(data[key]) == 36, 'missing actual loaded ' + key)
    warmup = data.get('warmup', {})
    need(warmup.get('includedInCases') is False and warmup.get('purpose') == 'bootstrap-install-trigger', 'warmup miscounted')
    cases = data.get('cases')
    if not need(isinstance(cases, list) and len(cases) == 2, 'exactly two fresh-run cases required'):
        return errors
    all_case_refs, history_ref, normalized = [], None, []
    for index, case in enumerate(cases, 1):
        prefix = 'case ' + str(index) + ': '
        for key, expected in dict(caseId='NATIVE-SLIMES-' + str(index), seed=SEED, act='ACT.OVERGROWTH',
                                 actIndex=0, ascension=0, encounter='ENCOUNTER.SLIMES_WEAK', roomType='Monster',
                                 turnBudget=2, outcome='BUDGET_EXIT', naturalTerminal=False).items():
            eq(case.get(key), expected, prefix + key)
        eq(case.get('processId'), data.get('processId'), prefix + 'different native process')
        need('error' in case and 'observationError' in case and case['error'] is None and case['observationError'] is None,
             prefix + 'native/observer exception or missing result')
        need(type(case.get('numericSeed')) is int and case['numericSeed'] >= 0, prefix + 'numeric seed missing')
        need(case.get('acts') == [dict(id='ACT.OVERGROWTH', index=0), dict(id='ACT.HIVE', index=1),
                                  dict(id='ACT.GLORY', index=2)], prefix + 'wrong Act slot mapping')
        initial, boundaries = case.get('initial'), case.get('boundaries')
        if not need(isinstance(initial, dict) and isinstance(boundaries, list) and len(boundaries) == 3,
                    prefix + 'requires start and two subsequent Play boundaries'):
            continue
        need(initial == boundaries[0], prefix + 'initial boundary mismatch')
        refs = set()
        for key in FRESH_REFS:
            value = initial.get(key)
            need(isinstance(value, str) and bool(value), prefix + 'missing ' + key)
            refs.add(value)
        need(len(refs) == len(FRESH_REFS), prefix + 'distinct native objects share identity')
        need(initial['combatRef'] != warmup.get('combatRef'), prefix + 'warmup counted as case')
        if history_ref is None:
            history_ref = initial.get('historyRef')
        else:
            need(initial.get('historyRef') == history_ref, prefix + 'singleton history was substituted')
        enemies = initial.get('enemies', [])
        enemy_map = {enemy['creatureRef']: enemy for enemy in enemies}
        need(len(enemy_map) == len(enemies) == 3, prefix + 'native SlimesWeak must have three unique enemies')
        models = Counter(enemy['modelId'] for enemy in enemies)
        need(models['MONSTER.LEAF_SLIME_S'] == models['MONSTER.TWIG_SLIME_S'] == 1 and
             models['MONSTER.LEAF_SLIME_M'] + models['MONSTER.TWIG_SLIME_M'] == 1,
             prefix + 'native SlimesWeak composition differs')
        for enemy in enemies:
            low, high = HP_RANGES[enemy['modelId']]
            need(enemy.get('side') == 'Enemy' and low <= enemy.get('hp', -1) == enemy.get('maxHp') <= high,
                 prefix + 'native ascension-zero enemy HP range/side violated')
        refs.update(enemy_map)
        refs.update(enemy['modelRef'] for enemy in enemies)
        for pile in ('cards', 'deck'):
            cards = initial.get(pile, [])
            need(Counter(card['id'] for card in cards) == DECK, prefix + 'wrong fresh starting ' + pile)
            need(len({card['cardRef'] for card in cards}) == 10, prefix + 'duplicate card instances')
        need(initial.get('player', {}).get('hp') == initial.get('player', {}).get('maxHp') == 80, prefix + 'unexpected player health fixture')
        need(initial.get('historyVisible') == initial.get('historyExported') and initial.get('historyVisible', 0) >= 5,
             prefix + 'initial native history not fully copied')
        for turn, boundary in enumerate(boundaries, 1):
            for key in FRESH_REFS:
                need(boundary.get(key) == initial[key], prefix + 'instance changed within case: ' + key)
            need(boundary.get('side') == 'Player' and boundary.get('phase') == 'Play' and
                 boundary.get('turn') == boundary.get('round') == turn, prefix + 'not actual next player Play phase')
            need(boundary.get('queueEmpty') is True and boundary.get('runningActionRef') is None and
                 boundary.get('pendingChoices') == 0, prefix + 'boundary not quiescent')
            need(boundary.get('domain') == boundary.get('storm') == 0, prefix + 'unexpected Domain/storm carryover')
            scopes = boundary.get('scopes', {})
            for key in ('activePlays', 'playTasks', 'drawTasks', 'purifications', 'engageConsumed'):
                eq(scopes.get(key), 0, prefix + 'active/stale scope ' + key)
            need(scopes.get('lightningOnlyCurrentCombat') is True and scopes.get('targetSubscriptionsOnlyCurrentCombat') is True,
                 prefix + 'bookkeeping belongs to prior combat')
            need(set(scopes.get('lightningCombatRefs', [])) <= {initial['combatRef']} and
                 set(scopes.get('targetSubscriptionOwnerRefs', [])) <= {initial['playerCreatureRef']}, prefix + 'old scope identities')
            if turn == 1:
                eq(scopes.get('engageActionRounds'), 0, prefix + 'prior normal actions leaked')
            need({enemy['creatureRef'] for enemy in boundary.get('enemies', [])} == set(enemy_map) and
                 len(boundary.get('enemies', [])) == 3, prefix + 'enemy boundary observations missing/reused')
            for enemy in boundary.get('enemies', []):
                original = enemy_map[enemy['creatureRef']]
                need(enemy['maxHp'] == original['maxHp'] and enemy['hp'] == original['hp'], prefix + 'enemy HP modified')
                need(enemy.get('nextMove') in MOVES[enemy['modelId']], prefix + 'unknown native next move')
            for pile in ('cards', 'deck'):
                refs.update(card['cardRef'] for card in boundary[pile])
        inputs = case.get('inputs', [])
        need(len(inputs) == 2 and [item.get('turnBefore') for item in inputs] == [1, 2] and
             [item.get('turnAfter') for item in inputs] == [2, 3], prefix + 'missing/duplicate queued inputs')
        need(all(item.get('type') == 'EndPlayerTurnAction' and item.get('completionAtNextPlay') is True for item in inputs),
             prefix + 'not native queued EndTurn actions')
        need(len({item.get('actionRef') for item in inputs}) == 2, prefix + 'reused action instance')
        refs.update(item.get('actionRef') for item in inputs)
        signals = case.get('turnSignals', [])
        need([(item.get('round'), item.get('side'), item.get('turn')) for item in signals] ==
             [(1, 'Player', 1), (1, 'Enemy', 1), (2, 'Player', 2), (2, 'Enemy', 2), (3, 'Player', 3)],
             prefix + 'native turn progression missing/repeated')
        need(all(item.get('combatRef') == initial['combatRef'] for item in signals), prefix + 'foreign turn signal')
        history = case.get('nativeHistory', [])
        need(isinstance(history, list) and bool(history), prefix + 'no native history')
        need(len({entry['entryRef'] for entry in history}) == len(history), prefix + 'duplicate history entry')
        need(all(entry.get('combatRef') == initial['combatRef'] and
                 entry.get('actorRef') in set(enemy_map) | {initial['playerCreatureRef'], None} for entry in history),
             prefix + 'foreign native history actor/combat')
        seq = [entry['seq'] for entry in history]
        need(seq == sorted(set(seq)), prefix + 'history not copied in native append order')
        refs.update(entry['entryRef'] for entry in history)
        refs.update(entry['cardRef'] for entry in history if entry.get('cardRef') is not None)
        need(not any(entry['kind'] in ('CardPlayStartedEntry', 'CardPlayFinishedEntry', 'EnergySpentEntry') for entry in history),
             prefix + 'unexpected player card/action input')
        moves = [entry for entry in history if entry['kind'] == 'MonsterPerformedMoveEntry']
        need(len(moves) == 6, prefix + 'not three actual native moves per enemy turn')
        for round_number in (1, 2):
            round_moves = [entry for entry in moves if entry.get('round') == round_number]
            need(Counter(entry['actorRef'] for entry in round_moves) == Counter(enemy_map.keys()), prefix + 'omitted/duplicated enemy opportunity')
            for entry in round_moves:
                enemy = enemy_map[entry['actorRef']]
                need(entry.get('side') == 'Enemy' and entry.get('monsterRef') == enemy['modelRef'] and
                     entry.get('monsterId') == enemy['modelId'] and entry.get('move') in MOVES[enemy['modelId']] and
                     entry.get('targetRefs') == [initial['playerCreatureRef']], prefix + 'incorrect native move identity')
        damage = [entry for entry in history if entry['kind'] == 'DamageReceivedEntry' and entry.get('receiverRef') == initial['playerCreatureRef']]
        need(len(damage) >= 2 and all(entry.get('dealerRef') in enemy_map and entry.get('cardRef') is None
                                     and entry.get('side') == 'Enemy' for entry in damage), prefix + 'no real native enemy damage')
        need(initial['player']['hp'] - sum(entry['hpLost'] for entry in damage) == boundaries[-1]['player']['hp'] > 0,
             prefix + 'native damage receipts do not reconcile player HP')
        need(boundaries[-1].get('historyExported') == boundaries[-1].get('historyVisible') == len(history),
             prefix + 'history lost before budget reset')
        for turn, boundary in enumerate(boundaries, 1):
            need(boundary['player']['maxHp'] == 80 and boundary['player']['hp'] ==
                 80 - sum(entry['hpLost'] for entry in damage if entry['round'] < turn), prefix + 'intermediate HP receipt mismatch')
            need(boundary.get('historyExported') == sum(entry['seq'] < boundary['seq'] for entry in history),
                 prefix + 'boundary history cursor disagrees')
        clears = case.get('historyClears', [])
        need(bool(clears) and all(item.get('duringBudgetExit') is True and item.get('exported') == len(history)
                                 for item in clears), prefix + 'missing native history-clear observation')
        exit_state = case.get('afterExit', {})
        for key, expected in dict(runIsNull=True, combatIsNull=True, inProgress=False, historyVisible=0,
                                 queueEmpty=True, runningActionRef=None).items():
            eq(exit_state.get(key), expected, prefix + 'exit ' + key)
        exit_scopes = exit_state.get('scopes', {})
        for key in ('activePlays', 'playTasks', 'drawTasks', 'purifications', 'engageConsumed', 'engageActionRounds'):
            eq(exit_scopes.get(key), 0, prefix + 'exit scope ' + key)
        need(exit_scopes.get('lightningCombatRefs') == [] and exit_scopes.get('targetSubscriptionOwnerRefs') == [],
             prefix + 'subscriptions retained after native reset')
        all_case_refs.append(refs)
        # Repeat-seed relation is a reproducibility/isolation check, not an AI oracle.
        normalize_enemy = lambda enemy: (enemy['modelId'], enemy['hp'], enemy['maxHp'], enemy['block'], enemy['nextMove'])
        normalized.append(dict(numericSeed=case['numericSeed'], totalFloor=case.get('totalFloor'), mapCoord=case.get('mapCoord'),
            enemies=[normalize_enemy(enemy) for enemy in enemies],
            initialCards=[(card['id'], card['pile']) for card in initial['cards']],
            moves=[(entry['round'], entry['monsterId'], entry['move']) for entry in moves],
            damage=[(entry['round'], enemy_map[entry['dealerRef']]['modelId'], entry['hpLost'], entry['blocked']) for entry in damage],
            endHp=boundaries[-1]['player']['hp']))
    need(len(all_case_refs) == 2 and not (all_case_refs[0] & all_case_refs[1]), 'old run/player/card/enemy/action/history references reused')
    need(len(normalized) == 2 and normalized[0] == normalized[1], 'same-seed fresh-run observations diverged')
    return errors


def matrix_evidence(log, run_id, evidence_root):
    lines = [line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines) != 1:
        return None, False
    try:
        summary = json.loads(lines[0])
        if not isinstance(summary, dict) or summary.get('manifest') != 'enemy-matrix-mvp.json':
            return None, False
        root = Path(evidence_root).resolve()
        path = (root / summary['manifest']).resolve()
        if path.parent != root or not path.is_file():
            return summary, False
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError, TypeError):
        return None, False
    errors = validate_matrix(data, run_id=run_id)
    for key, expected in dict(token=run_id, scenario='enemy-matrix-mvp', acceptance='natural-scheduling-isolation-only',
                              bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), caseCount=2,
                              completed=True, failure=None).items():
        if type(summary.get(key)) is not type(expected) or summary.get(key) != expected:
            errors.append('summary mismatch: ' + key)
    summary['validationErrors'] = errors
    summary['completeAiCoverage'] = False
    return summary, not errors
