"""Structural evidence mutations only; synthetic traces are not native AI tests."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_exploration_evidence as gate
from test_enemy_matrix_evidence import make_case
from test_enemy_catalog_evidence import manifest as catalog_fixture


def catalog():
    data = catalog_fixture()
    text = json.dumps(data)
    for index, name in enumerate(('SLIMES_WEAK', 'CORPSE_SLUGS_WEAK', 'BOWLBUGS_WEAK', 'DEVOTED_SCULPTOR_WEAK')):
        text = text.replace('"ENCOUNTER.ENCOUNTER_'+str(index)+'"', '"ENCOUNTER.'+name+'"')
    for index, name in enumerate(('LEAF_SLIME_S', 'LEAF_SLIME_M', 'TWIG_SLIME_S')):
        text = text.replace('"MONSTER.MONSTER_'+str(index)+'"', '"MONSTER.'+name+'"')
    data = json.loads(text)
    mids = [m['id'] for m in data['monsters'][:3]]
    eids = [e['id'] for e in data['encounters'][:4]]
    for row in data['encounters'][:4]:
        row['monsterIds'] = sorted(set(row['monsterIds']) | set(mids))
    for row in data['monsters'][:3]:
        row['encounterIds'] = sorted(set(row['encounterIds']) | set(eids))
    return data


def fixture():
    cat = catalog()
    selection = gate.prepare_selection(cat)
    cases = []
    for number, spec in enumerate(selection['cases'], 1):
        c = make_case(number)
        for collection in ('boundaries','nativeHistory','inputs','turnSignals','historyClears'):
            for row in c[collection]: row['seq'] *= 10
        c.update(caseId=spec['caseId'], act=spec['act'], actIndex=gate.ACT_INDEX[spec['act']], encounter=spec['encounter'],
                 policy=spec['policy'], turnBudget=spec['turnBudget'])
        c['acts'][0]['id'] = 'ACT.UNDERDOCKS' if spec['act'] == 'ACT.UNDERDOCKS' else 'ACT.OVERGROWTH'
        c['playerBeforeRoom'] = dict(creatureRef=c['initial']['playerCreatureRef'], hp=80, maxHp=80)
        c['runIdentities'] = {key: c['initial'][key] for key in ('runRef','playerRef','playerCreatureRef','queueRef','executorRef','choiceSyncRef')}
        c['runIdentities']['runNodeRef'] = f'case-{number}-run-node'
        for b in c['boundaries']:
            b['player']['alive'] = True
            for e in b['enemies']:
                e['alive'] = True; e['spawnedThisTurn'] = False
        c['initial'] = copy.deepcopy(c['boundaries'][0])
        for i in c['inputs']:
            i['completionObserved'] = True; i['status'] = 'RETURNED_TO_PLAY'
        outcome = spec['expectedOutcome'] if spec['expectedOutcome'] in ('WIN','LOSS') else 'BUDGET_EXIT'
        if outcome == 'LOSS':
            # Native loss after first actor of round two: later enemies are NOT_OBSERVED.
            moves = [h for h in c['nativeHistory'] if h['kind'] == 'MonsterPerformedMoveEntry' and h['round'] == 2]
            cutoff = moves[0]['seq']
            c['nativeHistory'] = [h for h in c['nativeHistory'] if h['seq'] <= cutoff]
            c['boundaries'].pop()
            c['turnSignals'] = [s for s in c['turnSignals'] if s['round'] < 3]
            c['inputs'][1]['status'] = 'TERMINAL'; c['inputs'][1]['turnAfter'] = 2
            receipts = [h for h in c['nativeHistory'] if h['kind']=='DamageReceivedEntry']
            receipts[-1]['hpLost'] = 80-sum(h['hpLost'] for h in receipts[:-1])
        last_seq = max([h['seq'] for h in c['nativeHistory']] + [b['seq'] for b in c['boundaries']])
        if outcome == 'WIN':
            card = c['initial']['cards'][0]
            inp = dict(seq=last_seq+1, type='PlayCardAction', actionRef=f'case-{number}-paid-action', cardRef=card['cardRef'],
                       cardId=card['id'], targetRef=c['initial']['enemies'][0]['creatureRef'], turnBefore=3,
                       energyBefore=3, energyAfter=2, status='TERMINAL', completionObserved=True)
            c['inputs'].append(inp)
            for offset, kind in enumerate(('EnergySpentEntry','CardPlayStartedEntry','DamageReceivedEntry','CardPlayFinishedEntry'), 2):
                h = dict(seq=last_seq+offset, entryRef=f'case-{number}-paid-entry-{offset}', combatRef=c['initial']['combatRef'],
                         kind=kind, round=3, side='Player', actorRef=c['initial']['playerCreatureRef'])
                if kind == 'EnergySpentEntry': h['amount'] = 1
                elif kind == 'DamageReceivedEntry': h.update(dealerRef=c['initial']['playerCreatureRef'], cardRef=card['cardRef'], hpLost=6)
                else: h.update(cardRef=card['cardRef'], cardId=card['id'])
                c['nativeHistory'].append(h)
            last_seq += 5
        c['outcome'] = outcome
        c['requestedTurns'] = 2
        c['completedCycles'] = 1 if outcome == 'LOSS' else 2
        c['turnSlots'] = [dict(ordinal=i+1, status=c['inputs'][i]['status'] if i < 2 else 'NOT_OBSERVED') for i in range(spec['turnBudget'])]
        player = copy.deepcopy(c['boundaries'][-1]['player'])
        if outcome == 'LOSS': player.update(hp=0, alive=False)
        c['terminal'] = dict(seq=last_seq+1, outcome=outcome, combatRef=c['initial']['combatRef'], combatEnded=outcome!='BUDGET_EXIT',
            combatWon=outcome=='WIN', inProgress=outcome=='BUDGET_EXIT', player=player,
            presentEnemies=[] if outcome=='WIN' else c['boundaries'][-1]['enemies'],
            nativeHistoryVisible=0 if outcome=='WIN' else len(c['nativeHistory']), exportedHistory=len(c['nativeHistory']),
            queueEmpty=True, runningActionRef=None, pendingChoices=0)
        c['terminalSignals'] = [] if outcome=='BUDGET_EXIT' else [dict(kind=k, seq=last_seq+2+j, combatRef=c['initial']['combatRef'])
            for j,k in enumerate(('CombatWon','CombatEnded') if outcome=='WIN' else ('CombatEnded',))]
        c['historyClears'] = [dict(seq=last_seq+6, exported=len(c['nativeHistory']), priorVisible=len(c['nativeHistory']), duringBudgetExit=outcome=='BUDGET_EXIT')]
        c['opportunities'] = []; c['sideSwitches'] = []; c['creatureChanges'] = []
        for ordinal, signal in enumerate((s for s in c['turnSignals'] if s['side']=='Enemy'),1):
            rnd=signal['round']; signal['enemyTurnOrdinal']=ordinal
            signal['enemyCandidateRefs']=[e['creatureRef'] for e in c['initial']['enemies']]
            c['sideSwitches'].append(dict(seq=signal['seq']-4,round=rnd,side='Player'))
            for j, enemy in enumerate(c['initial']['enemies']):
                observed = any(h['kind']=='MonsterPerformedMoveEntry' and h['round']==rnd and h['actorRef']==enemy['creatureRef'] for h in c['nativeHistory'])
                c['opportunities'].append(dict(seq=signal['seq']-3+j, enemyTurnOrdinal=ordinal, round=rnd,
                    creatureRef=enemy['creatureRef'], spawnedThisTurn=False,
                    status='COMPLETED_NATIVE_HISTORY' if observed else 'NOT_OBSERVED'))
        cases.append(c)
    data = dict(schema=1, token='current', scenario='enemy-exploration', acceptance='bounded-native-exploration-only', processId=54321,
        gameVersion='v0.107.1', gameCommit='59260271', gameAssemblyMvid=cat['gameAssemblyMvid'],
        testMode=False, selection=selection, warmup=dict(combatRef='warmup',includedInCases=False),
        registeredEncounterIds=sorted(set.union(*gate.registered(cat).values())), eventOnlyStatus='EVENT_SETUP_REQUIRED_NOT_RUN',
        enemyHpModified=False, playerHpModified=False, forcedMoves=False, directPerformMoveCalls=0, completeAiCoverage=False, physicalInputValidated=False,
        unexecutedSelectedCases=[], cases=cases, failure=None)
    return data, selection, cat


class ExplorationEvidenceTests(unittest.TestCase):
    def check(self, data, selection, cat):
        return gate.validate_exploration(data, selection=selection, catalog=cat, run_id='current')

    def test_valid_structural_smoke_with_interrupted_loss(self):
        data, selection, cat = fixture()
        self.assertEqual(self.check(data, selection, cat), [])
        loss = next(c for c in data['cases'] if c['outcome']=='LOSS')
        self.assertEqual(sum(o['status']=='NOT_OBSERVED' for o in loss['opportunities']), 2)
        self.assertEqual(sum(s['status']=='NOT_OBSERVED' for s in loss['turnSlots']), 30)

    def test_all_act_indices_and_slot_zero_alternative_are_enforced(self):
        for index in (3,4,5):
            data, selection, cat = fixture(); data['cases'][index]['actIndex'] = 99
            self.assertTrue(self.check(data,selection,cat))
        data, selection, cat = fixture(); data['cases'][4]['acts'][0]['id']='ACT.HIVE'
        self.assertTrue(self.check(data,selection,cat))

    def test_loss_is_not_six_moves_and_cannot_fabricate_unreached_actions(self):
        data, selection, cat = fixture()
        loss=data['cases'][2]
        next(o for o in loss['opportunities'] if o['status']=='NOT_OBSERVED')['status']='COMPLETED_NATIVE_HISTORY'
        self.assertTrue(self.check(data,selection,cat))
        data, selection, cat = fixture(); data['cases'][2]['turnSlots'][-1]['status']='RETURNED_TO_PLAY'
        self.assertTrue(self.check(data,selection,cat))

    def test_spawn_flag_does_not_invent_a_skip_policy(self):
        data, selection, cat = fixture()
        data['cases'][0]['opportunities'][0]['spawnedThisTurn']=True
        # Actual native completed history, not an invented blanket summon rule, determines this status.
        self.assertEqual(self.check(data,selection,cat), [])

    def test_win_requires_paid_native_card_lifecycle_and_damage(self):
        for mode in ('payment','finished','damage','input'):
            data, selection, cat = fixture(); win=data['cases'][1]
            if mode=='payment': next(h for h in win['nativeHistory'] if h['kind']=='EnergySpentEntry')['amount']=0
            elif mode=='finished': win['nativeHistory']=[h for h in win['nativeHistory'] if h['kind']!='CardPlayFinishedEntry']
            elif mode=='damage': win['nativeHistory']=[h for h in win['nativeHistory'] if h.get('side')!='Player' or h['kind']!='DamageReceivedEntry']
            else: win['policy']='end-turn'
            self.assertTrue(self.check(data,selection,cat),mode)

    def test_fake_terminal_nonquiescence_and_cleanup_leaks_fail(self):
        for mutate in (lambda d: d['cases'][2]['terminal'].__setitem__('inProgress',True),
            lambda d: d['cases'][2]['terminal']['player'].__setitem__('alive',True),
            lambda d: d['cases'][1].__setitem__('terminalSignals',[]),
            lambda d: d['cases'][3]['afterExit']['scopes'].__setitem__('activePlays',1),
            lambda d: d['cases'][4]['terminal'].__setitem__('pendingChoices',1),
            lambda d: d['cases'][0]['historyClears'].clear()):
            data, selection, cat=fixture(); mutate(data)
            self.assertTrue(self.check(data,selection,cat))

    def test_reference_reuse_input_changes_and_partial_batches_fail(self):
        data, selection, cat=fixture()
        old=data['cases'][3]['runIdentities']['runRef']; new=data['cases'][2]['runIdentities']['runRef']
        data['cases'][3]=json.loads(json.dumps(data['cases'][3]).replace(old,new))
        self.assertTrue(self.check(data,selection,cat))
        for mutate in (lambda d: d['cases'].pop(), lambda d: d.__setitem__('completeAiCoverage',True),
                       lambda d: d['cases'][3].__setitem__('processId',42),
                       lambda d: d['cases'][0].__setitem__('playerBeforeRoom',dict(hp=1000,maxHp=1000)),
                       lambda d: d['cases'][0]['initial']['enemies'][0].__setitem__('modelId','MONSTER.UNKNOWN')):
            data, selection, cat=fixture(); mutate(data)
            self.assertTrue(self.check(data,selection,cat))

    def test_eighty_preparation_requires_successful_native_smoke(self):
        data, selection, cat=fixture()
        with self.assertRaises(ValueError): gate.prepare_selection(cat,mode='explore')
        expanded=gate.prepare_selection(cat,mode='explore',prerequisite=data)
        self.assertEqual(len(expanded['cases']),80)
        self.assertEqual(expanded['prerequisiteToken'],'current')
        data['cases'][2]['outcome']='BUDGET_EXIT'
        with self.assertRaises(ValueError): gate.prepare_selection(cat,mode='explore',prerequisite=data)

    def test_artifact_and_external_selection_are_bound(self):
        data, selection, cat=fixture()
        selection_bytes=json.dumps(selection).encode()
        data['selectionSha256']=hashlib.sha256(selection_bytes).hexdigest()
        raw=json.dumps(data).encode()
        summary=dict(token='current',scenario='enemy-exploration',acceptance='bounded-native-exploration-only',
            manifest='enemy-exploration.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            caseCount=6,completed=True,failure=None)
        line=gate.PREFIX+json.dumps(summary)
        def payload(path):
            return selection_bytes if path.name=='selection.json' else raw
        with mock.patch.object(Path,'read_bytes',autospec=True,side_effect=payload):
            args=dict(selection_path=Path('selection.json'),catalog=cat)
            result,valid=gate.exploration_evidence(line,'current',Path.cwd(),**args)
            self.assertTrue(valid,result)
            self.assertFalse(gate.exploration_evidence(line,'old',Path.cwd(),**args)[1])
            self.assertFalse(gate.exploration_evidence(line+'\n'+line,'current',Path.cwd(),**args)[1])
            changed=copy.deepcopy(summary);changed['manifest']='../enemy-exploration.json'
            self.assertFalse(gate.exploration_evidence(gate.PREFIX+json.dumps(changed),'current',Path.cwd(),**args)[1])
            selection_bytes=b' '+selection_bytes
            self.assertFalse(gate.exploration_evidence(line,'current',Path.cwd(),**args)[1])

    def test_event_roots_and_malformed_payloads_fail_closed(self):
        data, selection, cat=fixture()
        for key,value in [('cases',None),('terminal',[]),('boundaries',None)]:
            broken=copy.deepcopy(data)
            if key=='cases': broken[key]=value
            else: broken['cases'][0][key]=value
            self.assertTrue(self.check(broken,selection,cat))
        bad=copy.deepcopy(selection); bad['cases'][0]['encounter']='ENCOUNTER.ENCOUNTER_80'
        self.assertTrue(gate.validate_selection(bad,cat))


if __name__=='__main__': unittest.main()
