"""Comparator negative controls; synthetic reports are NOT engine execution evidence."""
import copy
import json
import unittest
from tools.persistent_evidence import (PERSISTENT_CASES, ADDITIONAL_CASES, ENGAGEMENT_CASES, SPECIAL_CASES, PREFIX, case_statuses,
                                       persistent_contract_evidence, validate_persistent_result)


def report(case):
    r=dict(token='run-test',scenario='persistent-contract',variant=case,completed=True,
           gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           acceptance='mechanism-autoplay-not-payment-not-formal-enemy',character='VolibearCharacter',
           enemyIds=[1,2,3],enemyTypes=['LeafSlimeS','TwigSlimeS','LeafSlimeM'],inputs=[],snapshots=[],beforeEffects=[],batches=[],
           draw=None,engage=None,playHistory=[],drawHistory=[],damageHistory=[])
    def snap(label,energy=3,hp=80,block=0,enemies=(100,100,100),count=0,powers=()):
        r['snapshots'].append(dict(label=label,round=1,turn=1,energy=energy,hp=hp,block=block,enemyHp=list(enemies),lightningCount=count,
                                  powers=[dict(powerRef=ref,type=kind,amount=n) for ref,kind,n in powers]))
    def hit(e,n,card=None,props=8,blocked=0,player=False):
        r['damageHistory'].append(dict(target=e,playerTarget=player,hpLost=n,blocked=blocked,props=props,cardRef=card))
    def batch(n,card=None):
        i=len(r['batches'])+1
        r['batches'].append(dict(id=i,round=1,turn=1,count=i,baseDamage=n,storm=0,amount=n,cardRef=card,targets=[1,2,3],
                                 hits=[dict(target=e,hpLost=n,blocked=0) for e in [1,2,3]]))
        for e in [1,2,3]:hit(e,n,card,4)
    def apply(kind,n):r['inputs'].append(dict(op='PowerCmd.Apply',type=kind,amount=n))
    def play(name,replay):r['inputs'].append(dict(op='CardCmd.AutoPlay',cardRef=name,type='Volibear_B01',replay=replay,target=1))
    def histories(replay,boost=False):
        r['playHistory']=[dict(cardRef='first',index=0,count=1),dict(cardRef='second',index=0,count=1+replay)]
        if replay:r['playHistory'].append(dict(cardRef='second',index=1,count=2))
        r['beforeEffects']=[dict(p,playId=100 if i==0 else 200,ordinal=1 if i==0 else 2,
                                 strength=3 if boost and i>0 else 0,storm=3 if boost and i>0 else 0) for i,p in enumerate(r['playHistory'])]
    if case.startswith('PP-U21'):
        two=case=='PP-U21-two-independent'
        powers=[(1,'ThunderAftershockPower',1)]+([(2,'ThunderAftershockPower',1)] if two else [])
        snap('initial',energy=0);snap('before-deploy',energy=0,count=5 if two else 3)
        snap('after-deploy',energy=2 if two else 1,count=5 if two else 3,powers=powers)
        apply('ThunderAftershockPower',1)
        if two:apply('ThunderAftershockPower',1)
        for n,energy in ([(6,4),(7,4),(8,6)] if two else [(4,2)]):
            snap('batch-'+str(n),energy=energy,count=n,powers=powers)
            r['inputs'].append(dict(op='LightningCmd.DealAllEnemies',baseDamage=0))
        for _ in range(8 if two else 4):batch(0)
    elif case=='PP-U26-before-effects':
        base=[(1,'GrowingFuryPower',1),(2,'GrowingFuryPower',2)]
        snap('initial');snap('after-first',enemies=(94,100,100),powers=base)
        snap('after-second',enemies=(76,100,100),powers=base+[(3,'StrengthPower',3),(4,'StormChargePower',3)])
        apply('GrowingFuryPower',1);apply('GrowingFuryPower',2);play('first',0);play('second',1)
        histories(1,True);hit(1,6,'first');hit(1,9,'second');hit(1,9,'second')
    elif case.startswith('PP-U25'):
        pure=case=='PP-U25-purification';replay=0 if pure else 1
        powers=[(1,'PreyStillStandsPower',1)]+([(2,'DomainPower',1)] if pure else [])
        snap('initial');snap('after-first',enemies=(90,96,96) if pure else (94,100,100),count=int(pure),powers=powers)
        snap('after-second',enemies=(80,92,92) if pure else (82,100,100),count=2 if pure else 0,powers=powers)
        apply('PreyStillStandsPower',1);play('first',0);play('second',replay);histories(replay)
        hit(1,6,'first')
        if pure:batch(4,'first')
        hit(1,6,'second')
        if pure:batch(4,'second')
        else:hit(1,6,'second')
        r['drawHistory']=([dict(cardRef='direct-status',fromHandDraw=False)] if pure else [])+[dict(cardRef='drawn-attack',fromHandDraw=False)]
        r['draw']=dict(attackRef='drawn-attack',type='Volibear_B01',cost=1 if pure else 0,pile='Hand',identityInHand=True,
                       statusRef='direct-status' if pure else None,statusPile='Exhaust' if pure else None,statusIdentityInExhaust=pure,targetCount=2)
    elif case=='PP-R02-no-consumption':
        r['enemyIds']=[1,2];r['enemyTypes']=['Chomper','Chomper']
        snap('initial',enemies=(100,100))
        snap('before-engage',block=5,enemies=(100,100),powers=[(1,'ImmovableBodyPower',1)])
        snap('after-engage',hp=74,block=5,enemies=(100,100),powers=[(1,'ImmovableBodyPower',1)])
        snap('after-duplicate',hp=74,block=5,enemies=(100,100),powers=[(1,'ImmovableBodyPower',1)])
        snap('after-native-phase',hp=74,enemies=(100,100),powers=[(1,'ImmovableBodyPower',1)])
        r['snapshots'][-1]['round']=2;r['snapshots'][-1]['turn']=2
        r['inputs']=[dict(op='ImmovableBodyPower.Deploy',cardRef='engage-source')]*2+[dict(op='EngageCmd.Perform',cardRef='engage-source',target=1),dict(op='PlayerCmd.EndTurn')]
        r['drawHistory']=[dict(cardRef='engage-draw',fromHandDraw=False)]+[dict(cardRef='starting-'+str(i),fromHandDraw=True) for i in range(5)]
        r['engage']=dict(target=1,consumedBefore=False,consumedAfter=True,consumedNextTurn=False,
            movesBefore=['CLAMP_MOVE','SCREECH_MOVE'],movesAfterEngage=['CLAMP_MOVE','SCREECH_MOVE'],
            movesNextTurn=['SCREECH_MOVE','CLAMP_MOVE'],moveCountsBefore=[0,0],moveCountsAfter=[1,0],duplicateCounts=[1,0],moveCountsNextTurn=[1,1],
            receipt=dict(performed=True,completed=True,absorbed=10),duplicate=dict(performed=False,completed=False,absorbed=0),
            absorption=[dict(requested=8,props=8,absorbed=5,blockAfter=5,hpBeforeLoss=80),dict(requested=8,props=8,absorbed=5,blockAfter=5,hpBeforeLoss=77)],
            stateLogs=[['CLAMP_MOVE','SCREECH_MOVE'],['SCREECH_MOVE','CLAMP_MOVE']])
        hit(0,3,None,8,5,True);hit(0,3,None,8,5,True)
    else:
        snap('initial');snap('before-damage',block=5,powers=[(1,'ImmovableBodyPower',1)])
        snap('after-damage',hp=77,powers=[(1,'ImmovableBodyPower',1)])
        apply('ImmovableBodyPower',1);r['inputs'].append(dict(op='CreatureCmd.Damage',amount=8,props=4));hit(0,3,None,4,5,True)
    return r


class PersistentEvidenceTests(unittest.TestCase):
    def test_seven_hand_authored_positive_controls(self):
        for case in (c for c in PERSISTENT_CASES if c not in ADDITIONAL_CASES + ENGAGEMENT_CASES + SPECIAL_CASES):
            with self.subTest(case=case):self.assertTrue(validate_persistent_result(report(case),'run-test',case))

    def test_full_denominator_stays_not_run(self):
        status=case_statuses()
        self.assertEqual(len(status),len(PERSISTENT_CASES))
        self.assertEqual(set(status.values()),{'NOT_RUN'})
        self.assertIn('PP-R02-no-consumption',status)
        self.assertIn('PP-R02-no-consumption',PERSISTENT_CASES)
        self.assertEqual(set(status),set(PERSISTENT_CASES))
        self.assertEqual(len(PERSISTENT_CASES),21)

    def test_no_trusted_passed_or_completed_or_foreign_token(self):
        for case in (c for c in PERSISTENT_CASES if c not in ADDITIONAL_CASES + ENGAGEMENT_CASES + SPECIAL_CASES):
            for field,value in [('passed',True),('completed',False),('token','old'),('testMode',True),('gameCommit','wrong'),('acceptance','payment')]:
                with self.subTest(case=case,field=field):
                    r=report(case);r[field]=value
                    self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_every_snapshot_scalar_and_instance_mutation_rejected(self):
        for case in (c for c in PERSISTENT_CASES if c not in ADDITIONAL_CASES + ENGAGEMENT_CASES + SPECIAL_CASES):
            original=report(case)
            for i,snapshot in enumerate(original['snapshots']):
                for field in ('round','turn','energy','hp','block','lightningCount'):
                    with self.subTest(case=case,row=i,field=field):
                        r=copy.deepcopy(original);r['snapshots'][i][field]+=1
                        self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=copy.deepcopy(original);r['snapshots'][-1]['powers'][0]['powerRef']=999
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_batch_duplicates_missing_scope_and_parity_rejected(self):
        case='PP-U21-two-independent';original=report(case)
        for field,value in [('id',1),('count',7),('round',2),('amount',1),('targets',[1,2])]:
            r=copy.deepcopy(original);r['batches'][-1][field]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=copy.deepcopy(original);r['snapshots'][4]['energy']=6
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=copy.deepcopy(original);r['snapshots'][2]['powers'][1]['powerRef']=1
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_fury_must_precede_effect_and_replay_share_identity(self):
        case='PP-U26-before-effects'
        for field,value in [('strength',0),('storm',0),('ordinal',3),('playId',300)]:
            r=report(case);r['beforeEffects'][2][field]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=report(case);r['damageHistory'][1]['hpLost']=6
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_purification_native_history_keeps_direct_status_then_replacement(self):
        case='PP-U25-purification'
        for rows in ([dict(cardRef='drawn-attack',fromHandDraw=False)],
                     [dict(cardRef='drawn-attack',fromHandDraw=False),dict(cardRef='direct-status',fromHandDraw=False)],
                     [dict(cardRef='direct-status',fromHandDraw=False)],
                     [dict(cardRef='direct-status',fromHandDraw=False),dict(cardRef='drawn-attack',fromHandDraw=False),dict(cardRef='drawn-attack',fromHandDraw=False)],
                     [dict(cardRef='fake-status',fromHandDraw=False),dict(cardRef='drawn-attack',fromHandDraw=False)]):
            r=report(case);r['drawHistory']=rows
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_draw_observer_does_not_leak_into_replacement(self):
        for case,bad in [('PP-U25-replay',1),('PP-U25-purification',0)]:
            r=report(case);r['draw']['cost']=bad
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=report(case);r['drawHistory'].append(dict(cardRef='other',fromHandDraw=False))
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_nonattack_still_consumes_block(self):
        case='PP-R02-unpowered';r=report(case);r['snapshots'][-1]['block']=5
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_native_clamp_absorption_action_consumption_and_transition(self):
        case='PP-R02-no-consumption'
        mutations=[('receipt',dict(performed=True,completed=True,absorbed=6)),
                   ('duplicate',dict(performed=True,completed=True,absorbed=10)),
                   ('moveCountsNextTurn',[2,1]),('movesNextTurn',['CLAMP_MOVE','CLAMP_MOVE']),
                   ('consumedBefore',True),('consumedAfter',False),('consumedNextTurn',True)]
        for key,value in mutations:
            r=report(case);r['engage'][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        for key,value in [('absorbed',3),('blockAfter',0),('requested',9),('props',4),('hpBeforeLoss',80)]:
            r=report(case);r['engage']['absorption'][1][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_log_adapter_rejects_duplicates_partial_and_bad_case(self):
        case=PERSISTENT_CASES[0];line=PREFIX+json.dumps(report(case))
        self.assertTrue(persistent_contract_evidence(line,'run-test',case)[1])
        for log in ('',PREFIX+'{',line+'\n'+line):self.assertFalse(persistent_contract_evidence(log,'run-test',case)[1])
        self.assertFalse(persistent_contract_evidence(line,'run-test','PP-R02-no-consumption')[1])

    def test_boolean_numeric_impersonation_and_missing_observations_rejected(self):
        for case in (c for c in PERSISTENT_CASES if c not in ADDITIONAL_CASES + ENGAGEMENT_CASES + SPECIAL_CASES):
            r=report(case);r['snapshots'][0]['round']=True
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            for key in ('inputs','snapshots','beforeEffects','damageHistory','batches'):
                r=report(case);del r[key]
                self.assertFalse(validate_persistent_result(r,'run-test',case))


def additional_report(case):
    two=case.startswith('PP-U02');standing=case.startswith('PP-U03');ids=[1,2] if two else [1,2,3]
    specs={
        'PP-U02-instances':([('StormConductionPower',3),('StormConductionPower',4)],[87,93],0,2,[(3,0,None,0),(4,0,None,0)],[],0),
        'PP-U02-domain-order':([('DomainPower',1),('StormConductionPower',3),('StormChargePower',2)],[83,89],0,2,[(4,2,'played',0),(3,2,None,0)],[],0),
        'PP-U03-min-stack':([('StandingPower',3)],[100,100,100],17,0,[],[],0),
        'PP-U03-other-retention':([('StandingPower',3),('BarricadePower',1)],[100,100,100],20,0,[],[],0),
        'PP-U03-clamp-priority':([('StandingPower',3)],[100,100,100],17,0,[],[],0),
        'PP-U34-per-batch':([('ThunderArmorPower',3),('ThunderArmorPower',4)],[100,100,100],7,1,[(1,0,None,1)],[],0),
        'PP-R16-positive-own-block':([('BattleBodyPower',2)],[100,100,100],10,0,[],[('DexterityPower',2)],1),
        'PP-R16-attack-block-excluded':([('BattleBodyPower',2)],[90,100,100],10,0,[],[('StrengthPower',2)],1),
        'PP-R16-passive-block-excluded':([('BattleBodyPower',1),('ThunderArmorPower',3),('DomainPower',1)],[90,96,96],3,1,[(4,0,'played',0)],[('StrengthPower',1)],0),
    }
    powers,hp,block,count,batches,extra,replay=specs[case]
    power_rows=lambda values:[dict(powerRef=i+1,type=t,amount=n) for i,(t,n) in enumerate(values)]
    before=dict(round=1,turn=1,hp=80,block=20 if standing else 0,energy=3,enemyHp=[100]*len(ids),
                enemyBlock=[10]*3 if case=='PP-U34-per-batch' else [0]*len(ids),count=0,powers=power_rows(powers))
    after=dict(round=2 if standing else 1,turn=2 if standing else 1,hp=80,block=block,energy=3,enemyHp=hp,
               enemyBlock=[9]*3 if case=='PP-U34-per-batch' else [0]*len(ids),count=count,powers=power_rows(powers+extra))
    app=lambda t,n:dict(type=t,amount=n)
    setups={
        'PP-U02-instances':[app('StormConductionPower',3),app('StormConductionPower',4)],
        'PP-U02-domain-order':[app('StormConductionPower',3)],
        'PP-U03-min-stack':[app('StandingPower.Deploy',6),app('StandingPower.Deploy',3),app('StandingPower.Deploy',6)],
        'PP-U03-other-retention':[app('StandingPower.Deploy',3),app('BarricadePower',1)],
        'PP-U03-clamp-priority':[app('StandingPower.Deploy',3),app('SturdyClamp.Obtain',1)],
        'PP-U34-per-batch':[app('ThunderArmorPower',3),app('ThunderArmorPower',4)],
        'PP-R16-positive-own-block':[app('BattleBodyPower',2)],
        'PP-R16-attack-block-excluded':[app('BattleBodyPower',2)],
        'PP-R16-passive-block-excluded':[app('BattleBodyPower',1),app('ThunderArmorPower',3)],
    }
    hit=lambda e,n,props=8,card='played',b=0,player=False:dict(target=e,playerTarget=player,hpLost=n,blocked=b,props=props,cardRef=card)
    r=dict(token='run-test',scenario='persistent-contract',variant=case,completed=True,schema='additional-v1',gameVersion='v0.107.1',gameCommit='59260271',
           testMode=False,acceptance='mechanism-autoplay-not-payment-not-formal-enemy',character='VolibearCharacter',enemyIds=ids,
           enemyTypes=['Chomper','Chomper'] if two else ['LeafSlimeS','TwigSlimeS','LeafSlimeM'],setup=setups[case],before=before,after=after,
           batches=[],beforeEffects=[],finishedEffects=[],played=None,phaseBlockGains=[],clearPreventers=['BarricadePower'] if case=='PP-U03-other-retention' else (['StandingPower'] if standing else []),
           movesAfterBoundary=[],consumedAfterBoundary=[False]*len(ids),drawHistory=[],playHistory=[],damageHistory=[],
           fixturePreparation=dict(removedRelics=['HuntersHeart'],restoredHpAfterPreparation=standing,preparations=[],moves=[],damage=[],measurementHistoryBoundary=50,preparationHistoryStart=10))
    if standing:
        r['fixturePreparation']['preparations']=[dict(enemy=e,move=m,performed=True,completed=True,absorbed=0,consumed=True) for e,m in zip(ids,['TACKLE_MOVE','TACKLE_MOVE','CLUMP_SHOT'])]
        r['fixturePreparation']['moves']=ids
        r['fixturePreparation']['damage']=[hit(0,n,8,None,0,True) for n in [3,4,8]]
        r['drawHistory']=[dict(cardRef='starting-'+str(i),fromHandDraw=True) for i in range(5)]
    elif case!='PP-U34-per-batch':
        skill=case=='PP-R16-positive-own-block'
        played_type='Volibear_B02' if skill else 'IronWave' if replay else 'Volibear_B01'
        r['played']=dict(cardRef='played',type=played_type,replay=replay)
        r['playHistory']=[dict(cardRef='played',index=i,count=1+replay) for i in range(1+replay)]
        stats=dict(extra);strength=stats.get('StrengthPower',0);dex=stats.get('DexterityPower',0)
        for i,p in enumerate(r['playHistory']):
            r['beforeEffects'].append(dict(p,playId=100,ordinal=0 if skill else 1,strength=0,storm=2 if case=='PP-U02-domain-order' else 0))
            r['finishedEffects'].append(dict(p,playId=100,actualCompleted=i==replay,strength=strength if i==replay else 0,dexterity=dex if i==replay else 0))
        r['damageHistory']=[] if skill else [hit(1,5),hit(1,5)] if replay else [hit(1,6)]
    for i,(base,storm,card,blocked) in enumerate(batches,1):
        n=base+storm;lost=0 if blocked else n
        r['batches'].append(dict(id=i,round=1,turn=1,count=i,baseDamage=base,storm=storm,amount=n,cardRef=card,targets=ids,
                                 hits=[dict(target=e,hpLost=lost,blocked=blocked) for e in ids]))
        r['damageHistory'] += [hit(e,lost,4,card,blocked) for e in ids]
    return r


class AdditionalPersistentEvidenceTests(unittest.TestCase):
    def test_additional_literal_controls(self):
        for case in ADDITIONAL_CASES:
            with self.subTest(case=case):self.assertTrue(validate_persistent_result(additional_report(case),'run-test',case))

    def test_snapshot_mutations_never_pass(self):
        for case in ADDITIONAL_CASES:
            for side in ('before','after'):
                for field in ('round','turn','hp','block','energy','count'):
                    r=additional_report(case);r[side][field]+=1
                    self.assertFalse(validate_persistent_result(r,'run-test',case),(case,side,field))
            r=additional_report(case);r['after']['powers'][0]['powerRef']=999
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_domain_must_precede_each_conduction_instance(self):
        case='PP-U02-domain-order';r=additional_report(case);r['batches'].reverse()
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        case='PP-U02-instances';r=additional_report(case);r['after']['powers'][1]['powerRef']=1
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_standing_preparation_and_boundary_are_not_omitted(self):
        for case in ('PP-U03-min-stack','PP-U03-other-retention','PP-U03-clamp-priority'):
            for field,value in [('preparations',[]),('moves',[]),('damage',[]),('restoredHpAfterPreparation',False),('measurementHistoryBoundary',0)]:
                r=additional_report(case);r['fixturePreparation'][field]=value
                self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['phaseBlockGains']=[17]
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        case='PP-U03-other-retention';r=additional_report(case);r['clearPreventers']=[]
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        # Our retention must remain the active preventer instead of a cap-style relic clamping to 10.
        for case in ('PP-U03-min-stack','PP-U03-clamp-priority'):
            r=additional_report(case);r['clearPreventers']=[]
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=additional_report('PP-U03-clamp-priority');r['after']['block']=10
        self.assertFalse(validate_persistent_result(r,'run-test','PP-U03-clamp-priority'))

    def test_r16_skill_attack_passive_block_and_actual_finish_not_interchangeable(self):
        # A stack amount of 2 rewards two stats only once, after the whole actual
        # play; two native effect repetitions must neither split nor double it.
        controls=(('PP-R16-positive-own-block','dexterity','strength'),
                  ('PP-R16-attack-block-excluded','strength','dexterity'))
        for case,reward,excluded in controls:
            r=additional_report(case);r['finishedEffects'][0][reward]=2
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['finishedEffects'][1][reward]=4
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['finishedEffects'][1][excluded]=2
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['finishedEffects'][1]['playId']=101
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        case='PP-R16-passive-block-excluded';r=additional_report(case);r['finishedEffects'][0]['dexterity']=1
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_fully_blocked_aoe_counts_one_batch_not_three(self):
        case='PP-U34-per-batch';r=additional_report(case);r['after']['block']=21
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=additional_report(case);r['batches'][0]['hits'][0]['blocked']=0
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_additional_required_fields_and_token_gate(self):
        for case in ADDITIONAL_CASES:
            for key in ('fixturePreparation','setup','before','after','finishedEffects','phaseBlockGains','damageHistory'):
                r=additional_report(case);del r[key]
                self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['passed']=True
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=additional_report(case);r['token']='old'
            self.assertFalse(validate_persistent_result(r,'run-test',case))


def engagement_report(case):
    lingering=case=='PP-U19-draw-before-extend';pool=case=='PP-R18-independent-batches'
    r=dict(token='run-test',scenario='persistent-contract',variant=case,completed=True,schema='engagement-v1',gameVersion='v0.107.1',gameCommit='59260271',
           testMode=False,acceptance='mechanism-autoplay-not-payment-not-formal-enemy',character='VolibearCharacter',enemyIds=[1,2,3],
           enemyTypes=['LeafSlimeS','TwigSlimeS','LeafSlimeM'],removedRelics=['HuntersHeart'],initialMoves=['TACKLE_MOVE','TACKLE_MOVE','CLUMP_SHOT'],
           stages=[],receipts=[],batches=[],drawResponses=[],consumed=[True,False,False] if lingering else [False]*3 if pool else [True,True,False],
           status=None,playHistory=[],drawHistory=[],moveHistory=[1] if lingering else [1,2,3] if pool else [1,2],damageHistory=[])
    def stage(label,hp,energy,enemyhp,count,powers,turn=1):
        r['stages'].append(dict(label=label,round=turn,turn=turn,hp=hp,block=0,energy=energy,enemyHp=[enemyhp]*3,count=count,
                               powers=[dict(powerRef=i+1,type=t,amount=n) for i,(t,n) in enumerate(powers)]))
    if lingering:
        p=[('LingeringStormPower',1)]
        stage('before',80,3,100,0,p);stage('after-first',77,2,100,0,p+[('DomainPower',1)])
        r['status']=dict(cardRef='direct-status',pile='Hand',inHand=True,inExhaust=False)
        r['drawHistory']=[dict(cardRef='direct-status',fromHandDraw=False)]
        r['drawResponses']=[dict(cardRef='direct-status',fromHandDraw=False,domain=0,energy=2,pile='Hand')]
    elif pool:
        p=[('ThunderPoolPower',4),('ThunderPoolPower',6)]
        stage('before',80,3,100,0,p);stage('after-first',77,3,90,2,p);stage('after-second',73,3,90,2,p);stage('after-native-phase',65,3,80,0,p,2)
        r['drawHistory']=[dict(cardRef='starting-'+str(i),fromHandDraw=True) for i in range(5)]
        r['drawResponses']=[dict(d,domain=0,energy=3,pile='Hand') for d in r['drawHistory']]
    else:
        p=[('BattleScarsPower',1)]
        stage('before',80,3,100,0,p)
        p=p+[('StrengthPower',1),('StormChargePower',1)];stage('after-first',77,3,100,0,p)
        p=p+[('BattleScarsPower',2)];stage('after-second-deploy',77,3,100,0,p)
        stage('after-second',73,3,100,0,[('BattleScarsPower',1),('StrengthPower',3),('StormChargePower',2),('BattleScarsPower',2)])
    r['receipts']=[dict(target=e,performed=True,completed=True,absorbed=0,consumed=True) for e in ([1] if lingering else [1,2])]
    def enemyhit(n):r['damageHistory'].append(dict(target=0,playerTarget=True,hpLost=n,blocked=0,props=8,cardRef=None))
    def lightning(n):
        i=len(r['batches'])+1
        r['batches'].append(dict(id=i,round=1,turn=1,count=i,baseDamage=n,storm=0,amount=n,cardRef=None,targets=[1,2,3],
                                 hits=[dict(target=e,hpLost=n,blocked=0) for e in [1,2,3]]))
        r['damageHistory'].extend(dict(target=e,playerTarget=False,hpLost=n,blocked=0,props=4,cardRef=None) for e in [1,2,3])
    enemyhit(3)
    if pool:lightning(4);lightning(6)
    if not lingering:enemyhit(4)
    if pool:lightning(4);lightning(6);enemyhit(8)
    return r


class EngagementPersistentEvidenceTests(unittest.TestCase):
    def test_three_independent_engagement_controls(self):
        for case in ENGAGEMENT_CASES:self.assertTrue(validate_persistent_result(engagement_report(case),'run-test',case),case)

    def test_snapshots_and_receipts_cannot_be_forged(self):
        for case in ENGAGEMENT_CASES:
            original=engagement_report(case)
            for i in range(len(original['stages'])):
                for key in ('hp','energy','count','round','turn','block'):
                    r=copy.deepcopy(original);r['stages'][i][key]+=1
                    self.assertFalse(validate_persistent_result(r,'run-test',case),(case,i,key))
            r=copy.deepcopy(original);r['receipts'][0]['completed']=False
            self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=copy.deepcopy(original);r['initialMoves'][0]='invented'
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_lingering_must_draw_before_opening_domain(self):
        case='PP-U19-draw-before-extend'
        for key,value in [('domain',1),('energy',3),('pile','Exhaust')]:
            r=engagement_report(case);r['drawResponses'][0][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_scars_independent_deployment_does_not_reset_existing_copy(self):
        case='PP-U04-independent-first';r=engagement_report(case);r['stages'][-1]['powers'][1]['amount']=4
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=engagement_report(case);r['stages'][-1]['powers'][-1]['powerRef']=1
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_pool_first_engage_and_turn_end_are_separate_batches(self):
        case='PP-R18-independent-batches'
        r=engagement_report(case);r['stages'][2]['count']=4
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=engagement_report(case);r['batches'][1]['baseDamage']=4
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=engagement_report(case);r['moveHistory']=[1,2,1,2,3]
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_required_raw_event_fields_and_no_trusted_passed(self):
        for case in ENGAGEMENT_CASES:
            for key in ('removedRelics','initialMoves','receipts','stages','batches','drawResponses','damageHistory','moveHistory'):
                r=engagement_report(case);del r[key]
                self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=engagement_report(case);r['passed']=True
            self.assertFalse(validate_persistent_result(r,'run-test',case))


def special_report(case):
    nested=case=='PP-U25-live-finish-count'
    r=dict(token='run-test',scenario='persistent-contract',variant=case,completed=True,schema='special-v1',gameVersion='v0.107.1',gameCommit='59260271',
           testMode=False,character='VolibearCharacter',acceptance='native-nested-autoplay-not-payment' if nested else 'native-action-queue-not-mouse',
           enemyIds=[1,2,3],enemyTypes=['LeafSlimeS','TwigSlimeS','LeafSlimeM'],removedRelics=['HuntersHeart'],eliminated=[],special={},
           beforeEffects=[],playHistory=[],drawHistory=[],energyHistory=[],damageHistory=[])
    def snap(hp,energy,enemyhp,count,powers):
        return dict(round=1,turn=1,hp=hp,block=0,energy=energy,enemyHp=enemyhp,targetCount=count,lightning=0,
                    powers=[dict(powerRef=i+1,type=t,amount=n) for i,(t,n) in enumerate(powers)])
    def pre(names):
        r['beforeEffects']=[dict(cardRef=name,index=0,count=1,playId=100+i,ordinal=i+1,strength=0,storm=0) for i,name in enumerate(names)]
    def hit(e,n,card,player=False):return dict(target=e,playerTarget=player,hpLost=n,blocked=0,props=8,cardRef=card)
    if nested:
        r['eliminated']=[dict(enemy=e,hp=0,dead=True,stillHittable=False) for e in [2,3]]
        p=[('PreyStillStandsPower',1),('HellraiserPower',1)]
        r['special']=dict(before=snap(80,3,[100,0,0],0,p),after=snap(80,3,[79,0,0],3,p),
                          allowanceBefore=dict(powerRef=1,usedRound=-1,usedTurn=-1),allowanceAfter=dict(powerRef=1,usedRound=-1,usedTurn=-1),
                          finishes=[dict(cardRef=name,playId=identity,capturedTargetOrdinal=ordinal,liveTargetCount=live,actualCompleted=True) for name,identity,ordinal,live in
                                    [('first',100,1,1),('inner',102,3,3),('outer',101,2,3)]],
                          cards=[dict(cardRef=name,type=t,cost=1,pile='Discard',isStrike=strike) for name,t,strike in
                                 [('first','Volibear_B01',False),('outer','PommelStrike',True),('inner','StrikeIronclad',True)]])
        pre(['first','outer','inner']);r['playHistory']=[dict(cardRef=name,index=0,count=1,autoPlay=True,spent=0) for name in ['first','outer','inner']]
        r['drawHistory']=[dict(cardRef='inner',fromHandDraw=False)]
        r['damageHistory']=[hit(1,n,name) for n,name in [(6,'first'),(9,'outer'),(6,'inner')]]
    else:
        p=[('WelcomeThunderPower',1),('WelcomeThunderPower',2),('NextAttackDiscount',2)]
        unpaid=dict(energy=3,coupon=2,canonicalCost=3,cost=1,pile='Hand',hp=100,paymentEvents=0)
        d=dict(initialMove='TACKLE_MOVE',receipt=dict(performed=True,completed=True,absorbed=0),before=snap(77,3,[100,100,100],0,p),after=snap(77,2,[68,100,100],1,p[:2]),
               beforeInvalid=copy.deepcopy(unpaid),afterInvalid=copy.deepcopy(unpaid),afterValid=dict(energy=2,coupon=0,canonicalCost=3,cost=3,pile='Discard',hp=68,paymentEvents=1),
               actions=[],paymentEvents=[dict(cardRef='paid',amount=1,energy=2,coupon=2)],paymentBeforeEffects=[dict(cardRef='paid',energy=2,coupon=0,spent=1,autoPlay=False)])
        for i in range(2):
            identity=i+4
            events=[dict(label='before-executed',state='Executing',id=identity,energy=3,coupon=2,pile='Hand')]
            if i==0:events.append(dict(label='cancelled',state='Canceled',id=identity,energy=3,coupon=2,pile='Hand'))
            events.append(dict(label='after-finished',state='Finished',id=identity,energy=3 if i==0 else 2,coupon=2 if i==0 else 0,pile='Hand' if i==0 else 'Discard'))
            d['actions'].append(dict(role='invalid-self-target' if i==0 else 'valid-enemy-target',id=identity,target=0 if i==0 else 1,state='Finished',type='PlayCardAction',
                                     actionType='CombatPlayPhaseOnly',sameCard=True,context=None if i==0 else 'GameActionPlayerChoiceContext',events=events))
        r['special']=d;pre(['paid']);r['playHistory']=[dict(cardRef='paid',index=0,count=1,autoPlay=False,spent=1)]
        r['energyHistory']=[1];r['damageHistory']=[hit(0,3,None,True),hit(1,32,'paid')]
    return r


class SpecialPersistentEvidenceTests(unittest.TestCase):
    def test_native_nested_and_action_queue_literal_controls(self):
        for case in SPECIAL_CASES:self.assertTrue(validate_persistent_result(special_report(case),'run-test',case),case)

    def test_nested_live_count_cannot_use_captured_outer_ordinal(self):
        case='PP-U25-live-finish-count'
        for key,value in [('liveTargetCount',2),('actualCompleted',False),('playId',102)]:
            r=special_report(case);r['special']['finishes'][2][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['allowanceAfter']['usedTurn']=1
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['drawHistory'].append(dict(cardRef='starting-1',fromHandDraw=False))
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['cards'][2]['cost']=0
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_real_payment_cannot_be_autoplay_or_manual_resource_mutation(self):
        case='PP-U32-max-coupon'
        for key,value in [('autoPlay',True),('spent',0),('spent',3)]:
            r=special_report(case);r['playHistory'][0][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['energyHistory']=[]
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['actions'][1]['context']=None
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['actions'][1]['sameCard']=False
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_coupon_survives_invalid_preflight_and_consumes_after_payment(self):
        case='PP-U32-max-coupon'
        for path,key,value in [('afterInvalid','coupon',0),('afterInvalid','energy',2),('afterValid','coupon',2),('afterValid','energy',0),('beforeInvalid','cost',3)]:
            r=special_report(case);r['special'][path][key]=value
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['paymentEvents'][0]['coupon']=0
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['paymentBeforeEffects'][0]['coupon']=2
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_native_action_cancel_and_finish_events_required(self):
        case='PP-U32-max-coupon'
        for i in (0,1):
            r=special_report(case);r['special']['actions'][i]['events']=[]
            self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['special']['actions'][1]['id']=4
        self.assertFalse(validate_persistent_result(r,'run-test',case))
        r=special_report(case);r['acceptance']='mouse-payment'
        self.assertFalse(validate_persistent_result(r,'run-test',case))

    def test_new_cases_are_not_run_without_real_log_evidence(self):
        self.assertEqual(set(case_statuses().values()),{'NOT_RUN'})
        for case in SPECIAL_CASES:
            self.assertFalse(persistent_contract_evidence('', 'run-test',case)[1])
            for field in ('special','beforeEffects','playHistory','energyHistory','damageHistory'):
                r=special_report(case);del r[field]
                self.assertFalse(validate_persistent_result(r,'run-test',case))
            r=special_report(case);r['passed']=True
            self.assertFalse(validate_persistent_result(r,'run-test',case))


if __name__=='__main__':unittest.main()
