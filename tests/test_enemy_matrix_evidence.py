"""Synthetic gate tests only: no AI is executed and no numeric intent oracle is built."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_matrix_evidence as evidence


def scopes():
    return dict(activePlays=0, playTasks=0, drawTasks=0, purifications=0, lightningCombatRefs=[],
        targetSubscriptionOwnerRefs=[], lightningOnlyCurrentCombat=True,
        targetSubscriptionsOnlyCurrentCombat=True, engageConsumed=0, engageActionRounds=0)


def make_case(number):
    ref = lambda name: f'case-{number}-{name}'
    identities = {key: ref(key) for key in evidence.FRESH_REFS}
    player = dict(creatureRef=identities['playerCreatureRef'], modelRef=None, combatId=0, modelId=None,
                  side='Player', hp=80, maxHp=80, block=0, nextMove=None, stateLog=None, powers=[])
    enemy_ids = ['MONSTER.LEAF_SLIME_S', 'MONSTER.LEAF_SLIME_M', 'MONSTER.TWIG_SLIME_S']
    enemy_moves = ['TACKLE_MOVE', 'CLUMP_SHOT', 'TACKLE_MOVE']
    enemies = [dict(creatureRef=ref('enemy-' + str(i)), modelRef=ref('model-' + str(i)), combatId=i+1,
        modelId=mid, side='Enemy', hp=evidence.HP_RANGES[mid][0], maxHp=evidence.HP_RANGES[mid][0], block=0, nextMove=enemy_moves[i],
        stateLog=[enemy_moves[i]], powers=[]) for i, mid in enumerate(enemy_ids)]
    card_ids = [mid for mid, count in evidence.DECK.items() for unused in range(count)]
    cards = [dict(cardRef=ref('card-' + str(i)), id=mid, pile='Hand' if i < 5 else 'Draw') for i, mid in enumerate(card_ids)]
    deck = [dict(cardRef=ref('deck-' + str(i)), id=mid) for i, mid in enumerate(card_ids)]
    history, boundaries, signals, inputs = [], [], [], []
    sequence = 0
    def seq():
        nonlocal sequence
        sequence += 1
        return sequence
    def entry(kind, turn, side, actor, **extra):
        row = dict(seq=seq(), entryRef=ref('entry-' + str(len(history))), combatRef=identities['combatRef'],
                   kind=kind, round=turn, side=side, actorRef=actor, actorCombatId=0)
        row.update(extra)
        history.append(row)
    def signal(turn, side):
        signals.append(dict(seq=seq(), combatRef=identities['combatRef'], round=turn, side=side, turn=turn))
    def boundary(turn):
        row = dict(**identities, seq=seq(), historyRef='native-history-singleton', historyVisible=len(history),
            historyExported=len(history), round=turn, turn=turn, side='Player', phase='Play', queueEmpty=True,
            runningActionRef=None, pendingChoices=0, choiceIds=[], energy=3, domain=0, storm=0,
            player=copy.deepcopy(player), enemies=copy.deepcopy(enemies), cards=copy.deepcopy(cards),
            deck=copy.deepcopy(deck), scopes=scopes())
        boundaries.append(row)
    for turn in (1, 2, 3):
        for card in cards[:5]:
            entry('CardDrawnEntry', turn, 'Player', identities['playerCreatureRef'], cardRef=card['cardRef'], cardId=card['id'])
        signal(turn, 'Player')
        boundary(turn)
        if turn == 3:
            break
        inputs.append(dict(seq=seq(), type='EndPlayerTurnAction', actionRef=ref('action-' + str(turn)),
                           turnBefore=turn, turnAfter=turn+1, completionAtNextPlay=True))
        signal(turn, 'Enemy')
        for enemy in enemies:
            player['hp'] -= 5
            entry('DamageReceivedEntry', turn, 'Enemy', identities['playerCreatureRef'],
                receiverRef=identities['playerCreatureRef'], dealerRef=enemy['creatureRef'], hpLost=5,
                blocked=0, props=1, cardRef=None, receiverAfter=copy.deepcopy(player))
            entry('MonsterPerformedMoveEntry', turn, 'Enemy', enemy['creatureRef'], monsterRef=enemy['modelRef'],
                monsterId=enemy['modelId'], move=enemy['nextMove'], targetRefs=[identities['playerCreatureRef']],
                actorAfter=copy.deepcopy(enemy))
    return dict(caseId='NATIVE-SLIMES-' + str(number), processId=54321, seed=evidence.SEED, numericSeed=12345,
        act='ACT.OVERGROWTH', actIndex=0, acts=[dict(id='ACT.OVERGROWTH', index=0), dict(id='ACT.HIVE', index=1), dict(id='ACT.GLORY', index=2)],
        ascension=0, encounter='ENCOUNTER.SLIMES_WEAK', roomType='Monster', totalFloor=2, mapCoord=dict(col=0, row=0),
        turnBudget=2, outcome='BUDGET_EXIT', error=None, initial=copy.deepcopy(boundaries[0]), boundaries=boundaries,
        inputs=inputs, nativeHistory=history,
        historyClears=[dict(seq=seq(), priorVisible=len(history), exported=len(history), duringBudgetExit=True, currentCombatRef=None)],
        turnSignals=signals, afterExit=dict(runIsNull=True, combatIsNull=True, inProgress=False, historyVisible=0,
            queueEmpty=True, runningActionRef=None, scopes=scopes()), naturalTerminal=False, observationError=None)


def manifest():
    return dict(schema=1, processId=54321, token='current', scenario='enemy-matrix-mvp', acceptance='natural-scheduling-isolation-only',
        gameVersion='v0.107.1', gameCommit='59260271', gameAssemblyMvid='12345678-1234-1234-1234-123456789abc',
        modAssemblyMvid='abcdef12-1234-1234-1234-123456789abc', testMode=False, seed=evidence.SEED,
        warmup=dict(combatRef='warmup', includedInCases=False, purpose='bootstrap-install-trigger'),
        enemyHpModified=False, forcedMoves=False, directPerformMoveCalls=0, completeAiCoverage=False,
        cases=[make_case(1), make_case(2)], failure=None)


class EnemyMatrixEvidenceTests(unittest.TestCase):
    def check(self, data):
        return evidence.validate_matrix(data, run_id='current')

    def test_valid_synthetic_isolation_evidence_is_not_full_ai(self):
        data = manifest()
        self.assertEqual(self.check(data), [])
        self.assertFalse(data['completeAiCoverage'])

    def test_exact_case_set_seed_version_and_no_warmup_substitution(self):
        for mutate in (lambda d: d['cases'].pop(), lambda d: d['cases'].append(make_case(3)),
                       lambda d: d.__setitem__('token', 'old'), lambda d: d.__setitem__('gameCommit', 'other'),
                       lambda d: d['cases'][1].__setitem__('seed', 'different'),
                       lambda d: d['cases'][1].__setitem__('processId', 99999),
                       lambda d: d['warmup'].__setitem__('includedInCases', True),
                       lambda d: d['warmup'].__setitem__('combatRef', d['cases'][0]['initial']['combatRef'])):
            data = manifest(); mutate(data)
            self.assertTrue(self.check(data))

    def test_completion_task_without_next_play_or_enemy_turns_fails(self):
        for mutate in (lambda c: c['boundaries'][1].__setitem__('turn', 1),
                       lambda c: c['boundaries'][1].__setitem__('phase', 'Start'),
                       lambda c: c['boundaries'][1].__setitem__('side', 'Enemy'),
                       lambda c: c['turnSignals'].pop(1), lambda c: c['inputs'].pop(),
                       lambda c: c['boundaries'][1].__setitem__('queueEmpty', False)):
            data = manifest(); mutate(data['cases'][0])
            self.assertTrue(self.check(data))

    def test_missing_duplicate_wrong_phase_move_and_damage_receipts_fail(self):
        for mode in ('missing', 'duplicate', 'wrongphase', 'wrongtarget', 'wrongmove', 'damage'):
            data = manifest(); case = data['cases'][0]
            move = next(e for e in case['nativeHistory'] if e['kind'] == 'MonsterPerformedMoveEntry')
            if mode == 'missing': case['nativeHistory'].remove(move)
            elif mode == 'duplicate': case['nativeHistory'].append(copy.deepcopy(move))
            elif mode == 'wrongphase': move['side'] = 'Player'
            elif mode == 'wrongtarget': move['targetRefs'] = ['foreign']
            elif mode == 'wrongmove': move['move'] = 'GUESSED_MOVE'
            else: next(e for e in case['nativeHistory'] if e['kind'] == 'DamageReceivedEntry')['hpLost'] = 999
            self.assertTrue(self.check(data), mode)

    def test_history_clear_export_loss_and_pseudo_victory_fail(self):
        for mutate in (lambda c: c['historyClears'].clear(),
                       lambda c: c['historyClears'][0].__setitem__('exported', 0),
                       lambda c: c['boundaries'][-1].__setitem__('historyExported', 0),
                       lambda c: c.__setitem__('outcome', 'WIN'), lambda c: c.__setitem__('naturalTerminal', True),
                       lambda c: c.__setitem__('observationError', 'copy failed')):
            data = manifest(); mutate(data['cases'][0])
            self.assertTrue(self.check(data))

    def test_fresh_ref_claims_cannot_hide_actual_reuse(self):
        for key in evidence.FRESH_REFS:
            data = manifest()
            old = data['cases'][1]['initial'][key]
            new = data['cases'][0]['initial'][key]
            text = json.dumps(data['cases'][1]).replace(old, new)
            data['cases'][1] = json.loads(text)
            self.assertTrue(self.check(data), key)
        data = manifest()
        old = data['cases'][1]['initial']['cards'][0]['cardRef']
        new = data['cases'][0]['initial']['cards'][0]['cardRef']
        data['cases'][1] = json.loads(json.dumps(data['cases'][1]).replace(old, new))
        self.assertTrue(self.check(data))

    def test_stale_scope_queue_choice_and_enemy_health_edits_fail(self):
        for mutate in (lambda c: c['afterExit'].__setitem__('runIsNull', False),
                       lambda c: c['afterExit']['scopes'].__setitem__('drawTasks', 1),
                       lambda c: c['afterExit']['scopes'].__setitem__('engageActionRounds', 3),
                       lambda c: c['afterExit']['scopes'].__setitem__('lightningCombatRefs', ['old']),
                       lambda c: c['boundaries'][1].__setitem__('pendingChoices', 1),
                       lambda c: c['boundaries'][1]['scopes'].__setitem__('targetSubscriptionsOnlyCurrentCombat', False),
                       lambda c: c['boundaries'][1]['enemies'][0].__setitem__('maxHp', 999)):
            data = manifest(); mutate(data['cases'][0])
            self.assertTrue(self.check(data))

    def test_forced_move_and_coverage_claims_are_rejected(self):
        for key, value in dict(enemyHpModified=True, forcedMoves=True, directPerformMoveCalls=1, completeAiCoverage=True,
                               testMode=True, failure='native timeout').items():
            data = manifest(); data[key] = value
            self.assertTrue(self.check(data), key)

    def test_malformed_nested_data_is_rejected_without_crash(self):
        for mutate in (lambda d: d.__setitem__('cases', None), lambda d: d['cases'].__setitem__(0, []),
                       lambda d: d['cases'][0].__setitem__('nativeHistory', None),
                       lambda d: d['cases'][0]['boundaries'].__setitem__(0, 'fake'),
                       lambda d: d['cases'][0]['initial'].__setitem__('enemies', None)):
            data = manifest(); mutate(data)
            self.assertTrue(self.check(data))

    def test_bound_artifact_rejects_duplicate_stale_hash_and_path_escape(self):
        data = manifest(); raw = json.dumps(data).encode()
        summary = dict(token='current', scenario='enemy-matrix-mvp', acceptance='natural-scheduling-isolation-only',
            manifest='enemy-matrix-mvp.json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            caseCount=2, completed=True, failure=None)
        line = evidence.PREFIX + json.dumps(summary)
        with mock.patch.object(Path, 'is_file', return_value=True), mock.patch.object(Path, 'read_bytes', return_value=raw):
            result, valid = evidence.matrix_evidence(line, 'current', Path.cwd())
            self.assertTrue(valid, result)
            self.assertFalse(result['completeAiCoverage'])
            self.assertFalse(evidence.matrix_evidence(line, 'other', Path.cwd())[1])
            self.assertFalse(evidence.matrix_evidence(line + '\n' + line, 'current', Path.cwd())[1])
            summary['sha256'] = '0'*64
            self.assertFalse(evidence.matrix_evidence(evidence.PREFIX + json.dumps(summary), 'current', Path.cwd())[1])
        summary['manifest'] = '../enemy-matrix-mvp.json'
        self.assertFalse(evidence.matrix_evidence(evidence.PREFIX + json.dumps(summary), 'current', Path.cwd())[1])


if __name__ == '__main__':
    unittest.main()
