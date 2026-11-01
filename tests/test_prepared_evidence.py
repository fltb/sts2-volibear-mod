"""Synthetic strict-gate tests. Passing these is NOT execution of any native case."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools/prepared_evidence.py'
PROBE = ROOT / 'src/Volibear/PreparedContractProbe.cs'
spec = importlib.util.spec_from_file_location('prepared_evidence_under_test', MODULE)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def specimen(case, medium='LeafSlimeM'):
    base = [('StrengthPower',3), ('UnifyPower',3)]
    pending = base + [('NextAttackTrainingPower',3)]
    domain = pending + [('DomainPower',1), ('ThunderGuardPower',3)]
    guard1 = base + [('DomainPower',1), ('ThunderGuardPower',3)]
    guard2 = base + [('DomainPower',2), ('ThunderGuardPower',3), ('ThunderGuardPower',5)]
    # Hand-authored post-effect values: no production implementation is imported.
    if case == 'PR-training-dynamic-spells':
        absorbed, block, hit = (15,10,19) if medium == 'LeafSlimeM' else (18,7,16)
        rest = 469 if medium == 'LeafSlimeM' else 466
        rows = [('unify','R06',2,10,[500]*3,base,0,0), ('training','U10',1,10,[500]*3,pending,1,0),
                ('thunder-block','R07',2,10,[487]*3,pending,0,1),
                ('thunder-absorb','R09',2,block,[rest]*3,pending,1,2), ('attack','U05',1,block,[450,rest,rest],base,0,2)]
    elif case == 'PR-training-native-domain':
        rows = [('unify','R06',2,10,[500]*3,base,0,0), ('training','U10',1,10,[500]*3,pending,1,0),
                ('guard','C14',2,18,[500]*3,domain,0,0), ('attack','B03',1,18,[470,487,487],guard1,0,2)]
    elif case == 'PR-guard-instances':
        rows = [('unify','R06',2,10,[500]*3,base,0,0), ('guard-base','C14',2,18,[500]*3,guard1,0,0),
                ('guard-upgrade','C14',2,29,[500]*3,guard2,0,0)]
    else:
        rows = [('replay','U11',1,0,[500]*3,[('NextAttackReplayPower',1)],0,0),
                ('bite-first','U08',1,12,[480,500,500],[],0,0), ('bite-next','U08',1,18,[464,500,500],[],0,0)]
    ids = [11,12,13]; pid = 10; power_ids = {}
    def power_rows(powers):
        result=[]
        for kind, amount in powers:
            key=(kind,amount) if kind == 'ThunderGuardPower' else kind
            if key not in power_ids: power_ids[key]=len(power_ids)+1
            result.append(dict(powerRef=power_ids[key],type=kind,amount=amount))
        return result
    models = ['VOLIBEAR_B01']*4 + ['VOLIBEAR_B02']*4 + ['VOLIBEAR_B03','VOLIBEAR_B04']
    cards = [dict(cardRef=f'starter-{i}', modelId=m, upgraded=False, masterIndex=i) for i,m in enumerate(models)]
    initial = dict(round=1,turn=1,energy=10,hp=80,block=0,enemyHp=[500]*3,marks=[0]*3,lightningCount=0,
                   hand=[],draw=[c['cardRef'] for c in cards],powers=[])
    r = dict(token='run-token',scenario='prepared-contract',variant=case,completed=True,gameVersion='v0.107.1',gameCommit='59260271',
             testMode=False,acceptance=evidence.ACCEPTANCE,character='VolibearCharacter',enemyIds=ids,
             enemyTypes=['LeafSlimeS','TwigSlimeS',medium],playerId=pid,cards=cards,initial=copy.deepcopy(initial),
             actions=[],steps=[],batches=[],payments=[],beforeEffects=[],trigger=None)
    def damage(target,amount,card,props=4,blocked=0):
        return dict(target=target,playerTarget=target==pid,hpLost=amount,blocked=blocked,props=props,cardRef=card)
    def batch(base,amount,card,targets=ids):
        count=len(r['batches'])+1
        r['batches'].append(dict(id=count,round=1,turn=1,count=count,baseDamage=base,amount=amount,cardRef=card,targets=list(targets),
                                 hits=[dict(target=e,hpLost=amount,blocked=0) for e in targets]))
    previous = initial
    for i,(label,code,cost,block,enemy_hp,powers,n_draw,count) in enumerate(rows,1):
        upgraded=label=='guard-upgrade'
        cards.append(dict(cardRef=label,modelId='VOLIBEAR_'+code,upgraded=upgraded,masterIndex=-1))
        before=copy.deepcopy(previous);before['hand'].append(label)
        energy=before['energy']-cost
        after=copy.deepcopy(previous)
        new=before['draw'][:n_draw]
        after.update(energy=energy,block=block,enemyHp=list(enemy_hp),powers=power_rows(powers),lightningCount=count,
                     hand=previous['hand']+new,draw=previous['draw'][n_draw:])
        if code=='U08': after['marks']=[1,0,0]
        repeat=2 if label=='bite-first' else 1
        trained=3 if label=='attack' else 0
        pending_amount=next((p['amount'] for p in before['powers'] if p['type']=='NextAttackTrainingPower'),0)
        if code in ('U05','B03','U08'): pending_amount=0
        for j in range(repeat):
            r['beforeEffects'].append(dict(cardRef=label,index=j,count=repeat,playId=100+i,autoPlay=False,energy=energy,spent=cost,
                                          block=before['block']+(6*j if code=='U08' else 0),pendingTraining=pending_amount,training=trained,replay=0))
        r['payments'].append(dict(cardRef=label,amount=cost,energy=energy))
        r['actions'].append(dict(cardRef=label,id=i,target=11 if code in ('B03','U05','U08') else None,state='Finished',
                                 type='PlayCardAction',actionType='CombatPlayPhaseOnly',sameCard=True,context='GameActionPlayerChoiceContext',
                                 events=[dict(label='before-executed',state='Executing',id=i,energy=before['energy']),
                                         dict(label='after-finished',state='Finished',id=i,energy=energy)]))
        hits=[];moves=[]
        if code=='R07':
            hits=[damage(e,13,label) for e in ids];batch(10,13,label)
        elif code=='R09':
            hits=[damage(10,0,None,8,n) for n in (3,4,8 if medium=='LeafSlimeM' else 11)]
            hits += [damage(e,absorbed+3,label) for e in ids];batch(absorbed,absorbed+3,label)
            moves=[dict(enemy=11,move='TACKLE_MOVE'),dict(enemy=12,move='TACKLE_MOVE'),
                   dict(enemy=13,move='CLUMP_SHOT' if medium=='LeafSlimeM' else 'POKEY_POUNCE_MOVE')]
        elif code=='U05': hits=[damage(11,hit,label,8)]
        elif code=='B03':
            hits=[damage(11,17,label,8)]+[damage(e,n,label) for n in (4,9) for e in ids]
            batch(4,4,label);batch(3,9,label)
        elif code=='U08': hits=[damage(11,10 if repeat==2 else 16,label,8) for _ in range(repeat)]
        lookup={c['cardRef']:c['modelId'] for c in cards}
        r['steps'].append(dict(cardRef=label,before=before,after=copy.deepcopy(after),finalPile='Exhaust' if code=='R06' or code=='C14' and not upgraded else 'Discard',
                               training=trained,plays=[dict(cardRef=label,index=j,count=repeat) for j in range(repeat)],
                               draws=[dict(cardRef=c,modelId=lookup[c],fromHandDraw=False) for c in new],moves=moves,damage=hits))
        previous=after
    if case=='PR-guard-instances':
        after=copy.deepcopy(previous);after.update(block=26,enemyHp=[492,500,500],lightningCount=2)
        r['trigger']=dict(operation='DamageCmd.Attack.FromMonster.Execute',dealer=11,before=copy.deepcopy(previous),after=after,
                          damage=[damage(10,0,None,8,3),damage(11,3,None),damage(11,5,None)])
        batch(3,3,None,[11]);batch(5,5,None,[11])
    return r


class PreparedEvidenceTests(unittest.TestCase):
    def test_all_initial_synthetic_cases_for_both_native_medium_slimes(self):
        for medium in ['LeafSlimeM','TwigSlimeM']:
            for case in evidence.PREPARED_CASES:
                with self.subTest(case=case,medium=medium):
                    self.assertTrue(evidence.validate_prepared_result(specimen(case,medium),'run-token',case))

    def test_unimplemented_cases_and_ten_card_denominator_are_not_erased(self):
        self.assertEqual(len(evidence.PREPARED_CARD_IDS),10)
        self.assertTrue(all(x=='NOT_RUN' for x in evidence.case_statuses().values()))
        for case in set(evidence.ALL_CASES)-set(evidence.PREPARED_CASES):
            self.assertEqual(evidence.case_statuses({case:'PASS'})[case],'NOT_RUN')
            self.assertFalse(evidence.validate_prepared_result({},'run-token',case))

    def test_replay_full_effects_first_bite_snapshot_and_single_native_payment(self):
        for mutate in [lambda r:r['payments'].append(copy.deepcopy(r['payments'][1])),
                       lambda r:r['beforeEffects'][2].update(autoPlay=True),
                       lambda r:r['beforeEffects'][2].update(playId=999),
                       lambda r:r['beforeEffects'][2].update(block=0),
                       lambda r:r['steps'][1]['damage'][1].update(hpLost=16),
                       lambda r:r['steps'][1]['after'].update(block=6),
                       lambda r:r['actions'][1].update(context='ThrowingPlayerChoiceContext'),
                       lambda r:r['steps'][2]['damage'][0].update(hpLost=10)]:
            r=specimen('PR-replay-paid');mutate(r)
            self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))

    def test_dynamic_damage_and_skill_training_nonconsumption(self):
        for mutate in [lambda r:r['steps'][4]['damage'][0].update(hpLost=10),
                       lambda r:r['beforeEffects'][2].update(pendingTraining=0),
                       lambda r:r['beforeEffects'][3].update(training=3),
                       lambda r:r['batches'][0].update(amount=10),
                       lambda r:r['batches'][1].update(amount=15),
                       lambda r:r['steps'][3]['moves'].clear()]:
            r=specimen('PR-training-dynamic-spells');mutate(r)
            self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))

    def test_native_lightning_is_trained_but_domain_and_passive_are_not(self):
        for case,index,wrong in [('PR-training-native-domain',0,10),('PR-training-native-domain',1,3),('PR-guard-instances',0,6),('PR-guard-instances',1,8)]:
            r=specimen(case);r['batches'][index]['amount']=wrong
            self.assertFalse(evidence.validate_prepared_result(r,'run-token',case))
        r=specimen('PR-guard-instances');r['batches'][1]['id']=r['batches'][0]['id']
        self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))
        r=specimen('PR-guard-instances');r['trigger']['damage'][0]['blocked']=0
        self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))
        r=specimen('PR-guard-instances');r['steps'][2]['after']['powers'][-1]['powerRef']=r['steps'][2]['after']['powers'][-2]['powerRef']
        self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))

    def test_provenance_unknown_fields_identity_boolean_and_log_duplicates_rejected(self):
        for key,value in [('token','stale'),('testMode',True),('passed',True),('completed',False),('acceptance','mouse-accepted')]:
            r=specimen('PR-replay-paid');r[key]=value
            self.assertFalse(evidence.validate_prepared_result(r,'run-token','PR-replay-paid'))
        r=specimen('PR-replay-paid');r['payments'][0]['amount']=True
        self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))
        r=specimen('PR-replay-paid');r['cards'][1]['masterIndex']=0
        self.assertFalse(evidence.validate_prepared_result(r,'run-token',r['variant']))
        line=evidence.PREFIX+json.dumps(specimen('PR-replay-paid'))
        self.assertTrue(evidence.prepared_contract_evidence(line,'run-token','PR-replay-paid')[1])
        for log in ['',line+'\n'+line,evidence.PREFIX+'{']:
            self.assertFalse(evidence.prepared_contract_evidence(log,'run-token','PR-replay-paid')[1])

    def test_native_action_queue_and_read_only_observers_no_direct_power_injection(self):
        source=PROBE.read_text(encoding='utf-8')
        for required in ['new PlayCardAction(card, target)','ActionQueueSynchronizer.RequestEnqueue(action)',
                         'await action.CompletionTask','Hook.AfterEnergySpent','Hook.BeforeCardPlayed','await original;',
                         'CardPlayStartedEntry','DamageReceivedEntry','CardDrawnEntry',
                         'await DamageCmd.Attack(3m).FromMonster(leaf.Monster!).Execute(choices)']:
            self.assertIn(required,source)
        for forbidden in ['FromMonster(leaf.Monster!).Targeting(', 'CardCmd.AutoPlay','OnPlay(', 'PowerCmd.Apply<', 'CardModifier.AddModifier', 'PreparedAttackBonus.Prepare', 'passed =']:
            self.assertNotIn(forbidden,source)


if __name__=='__main__':
    unittest.main()
