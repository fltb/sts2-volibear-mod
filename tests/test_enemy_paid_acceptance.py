"""Offline oracle mutations, never advertised as native enemy execution."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_exploration_evidence as gate
from test_enemy_exploration_evidence import catalog


def paid_fixture(spec, cycles=4):
    domain = spec['policy'].endswith('-on'); engage = '-engage-' in spec['policy']
    target = spec['caseId'].split(':')[1] if spec['caseId'].startswith('formal-') else next(t for t in gate.PAID_TARGETS if spec['caseId'] == f"paid-{t}-{spec['policy']}")
    sequences = {'LEAF_SLIME_S': ['GOOP_MOVE', 'TACKLE_MOVE'] * 9,
                 'LEAF_SLIME_M': ['STICKY_SHOT', 'CLUMP_SHOT'] * 9,
                 'TWIG_SLIME_S': ['TACKLE_MOVE'] * 18}
    case = dict(caseId=spec['caseId'], completedCycles=cycles, boundaries=[], inputs=[], nativeHistory=[], paidAttempts=[], turnSignals=[])
    formal=spec['caseId'].startswith('formal-')
    if formal: case['paidStrategy']='C21-if-domain;C11-or-B02;C12-fixed-remaining-3-energy-budget'
    cards = []; seq = 0
    def history(kind, **kw):
        nonlocal seq
        seq += 1
        case['nativeHistory'].append(dict(seq=seq, kind=kind, **kw))
    for cycle in range(cycles+1):
        rnd = cycle+1
        enemies = [dict(creatureRef=t, modelId='MONSTER.'+t, nextMove=sequences[t][cycle], alive=True) for t in gate.PAID_TARGETS]
        case['boundaries'].append(dict(turn=rnd, round=rnd, domain=0, playerCreatureRef='player', cards=copy.deepcopy(cards), enemies=enemies))
        if cycle == cycles: break
        case['turnSignals'].append(dict(side='Enemy',round=rnd))
        def move(t, side):
            name = sequences[t][cycle]; attack, status = gate.PAID_MOVES[t][name]
            if attack: history('DamageReceivedEntry', dealerRef=t, receiverRef='player', round=rnd, hpLost=0, blocked=attack)
            if not domain:
                for j in range(status): cards.append(dict(cardRef=f'{t}-{rnd}-{j}', id='CARD.SLIMED'))
            history('MonsterPerformedMoveEntry', actorRef=t, monsterId='MONSTER.'+t, round=rnd, side=side, move=name)
        codes=(['C21'] if domain else []) + ['C11' if engage else 'B02'] + (['C12']*(1 if domain else 2) if formal else [])
        for ordinal,code in enumerate(codes):
            seq += 1
            card = f'card-{rnd}-{code}-{ordinal}'
            play = dict(seq=seq, type='PlayCardAction', cardId='CARD.VOLIBEAR_'+code, cardRef=card,
                        targetRef=target if code=='C11' else 'player', turnBefore=rnd,
                        energyBefore=3-ordinal, energyAfter=2-ordinal, pileAfter='Discard', completionObserved=True,
                        domainBefore=0 if code=='C21' else int(domain), domainAfter=int(domain),
                        cardsBefore=copy.deepcopy(cards))
            case['inputs'].append(play)
            history('EnergySpentEntry', amount=1)
            history('CardPlayStartedEntry', cardRef=card)
            if code=='C11': move(target, 'Player')
            history('CardPlayFinishedEntry', cardRef=card)
            seq += 1; play['endSeq']=seq; play['cardsAfter']=copy.deepcopy(cards)
        for t in gate.PAID_TARGETS:
            if not engage or t != target: move(t, 'Enemy')
    return case


def semantic_fixture(model, move, hits=(), *, domain=False, player_powers=(), actor_powers=(), cards=(), block=0,
                     before_guards=None, after_guards=None, strength=0):
    actor=dict(creatureRef='actor',modelId='MONSTER.'+model,hp=70,block=0,powers=[],nextMove=move,alive=True,slot='one',guards=before_guards or {})
    if strength: actor['powers']=[dict(id='POWER.STRENGTH_POWER',amount=strength)]
    player=dict(creatureRef='player',modelId=None,hp=80,block=5,powers=[],alive=True)
    before=dict(player=player,enemies=[actor],cards=[],domain=int(domain),slots=['one','two'])
    after=copy.deepcopy(before); after['enemies'][0]['block']=block
    after['enemies'][0]['guards'].update(after_guards or {})
    for key,amount in actor_powers: after['enemies'][0]['powers'].append(dict(id='POWER.'+key,amount=amount))
    for key,amount in player_powers: after['player']['powers'].append(dict(id='POWER.'+key,amount=amount))
    for index,(code,pile) in enumerate(cards): after['cards'].append(dict(cardRef='new-'+str(index),id='CARD.'+code,pile=pile))
    history=[]
    for index,value in enumerate(hits):
        absorbed=min(after['player']['block'],value); lost=value-absorbed
        after['player']['block']-=absorbed; after['player']['hp']-=lost
        history.append(dict(seq=index+2,kind='DamageReceivedEntry',dealerRef='actor',receiverRef='player',blocked=absorbed,hpLost=lost))
    history.append(dict(seq=20,kind='MonsterPerformedMoveEntry',actorRef='actor',monsterId='MONSTER.'+model,move=move,historyRef='history'))
    window=dict(startSeq=1,historySeq=20,endSeq=21,status='COMPLETED_NATIVE_HISTORY',actorRef='actor',monsterId='MONSTER.'+model,
                move=move,historyRef='history',before=before,after=after,side='Player')
    return window,history


def threshold_fixture(spec):
    """Hand-authored native-source event simulation ONLY for offline gate mutations."""
    domain=spec['policy'].endswith('-on'); engage='-engage-' in spec['policy']; seq=0
    actor=dict(creatureRef='actor',modelId='MONSTER.TUNNELER',hp=87,block=0,powers=[],nextMove='BITE_MOVE',alive=True,slot='one',guards={'isStunned':False})
    player=dict(creatureRef='player',modelId=None,hp=80,block=0,powers=[],alive=True)
    cards=[]; active_domain=0; next_move='BITE_MOVE'; history=[]; windows=[]; inputs=[]; bounds=[]
    def tick():
        nonlocal seq
        seq+=1; return seq
    def world(): return copy.deepcopy(dict(enemies=[actor],player=player,cards=cards,domain=active_domain,slots=['one']))
    def boundary(rnd):
        b=world(); b.update(seq=tick(),round=rnd,turn=rnd); bounds.append(b)
    def add(kind,**fields):
        row=dict(seq=tick(),kind=kind,**fields); row['historyRef']='h-'+str(row['seq']); history.append(row); return row
    def damage(amount,receiver,dealer,card_ref=None):
        blocked=min(receiver['block'],amount); lost=amount-blocked
        receiver['block']-=blocked; receiver['hp']-=lost
        add('DamageReceivedEntry',round=rnd,receiverRef=receiver['creatureRef'],dealerRef=dealer,cardRef=card_ref,blocked=blocked,hpLost=lost)
        if receiver is actor and blocked and not actor['block'] and actor['powers']:
            actor['powers']=[]; actor['guards']['isStunned']=True; actor['nextMove']='STUNNED'
        return blocked
    def enemy_move():
        nonlocal next_move
        move=actor['nextMove']; w=dict(startSeq=tick(),before=world(),actorRef='actor',monsterId='MONSTER.TUNNELER',move=move,side='Player' if engage else 'Enemy')
        absorbed=0
        if move=='BITE_MOVE': absorbed=damage(13,player,'actor'); next_move='BURROW_MOVE'
        elif move=='BURROW_MOVE':
            actor['block']+=32
            if not domain: actor['powers']=[dict(id='POWER.BURROWED_POWER',amount=1)]
            next_move='BELOW_MOVE'
        elif move=='BELOW_MOVE': absorbed=damage(23,player,'actor'); next_move='BELOW_MOVE'
        elif move=='STUNNED': actor['guards']['isStunned']=False; next_move='BITE_MOVE'
        else: raise AssertionError(move)
        h=add('MonsterPerformedMoveEntry',round=rnd,actorRef='actor',monsterId='MONSTER.TUNNELER',move=move,side=w['side'])
        w.update(historySeq=h['seq'],historyRef=h['historyRef'],endSeq=tick(),after=world(),status='COMPLETED_NATIVE_HISTORY'); windows.append(w)
        return absorbed
    boundary(1)
    initial=copy.deepcopy(bounds[0])
    for rnd in range(1,spec['turnBudget']+1):
        player['block']=0; active_domain=0
        codes=(['C21'] if domain else [])+(['C10']+['C12']*(1 if domain else 2) if engage else ['B01']*(2 if domain else 3))
        for index,code in enumerate(codes):
            cr='card-'+str(rnd)+'-'+str(index)
            card=dict(cardRef=cr,id='CARD.VOLIBEAR_'+code,pile='Play',type='Attack' if code in ('B01','C10') else 'Skill',affliction=None,afflictionAmount=None)
            cards.append(card)
            play=dict(seq=tick(),type='PlayCardAction',cardId=card['id'],cardRef=cr,turnBefore=rnd,
                      energyBefore=3-index,energyAfter=2-index,completionObserved=True,pileAfter='Discard',domainBefore=active_domain,
                      enemiesBefore=copy.deepcopy([actor]),targetRef='actor' if code in ('B01','C10') else 'player')
            add('EnergySpentEntry',amount=1); add('CardPlayStartedEntry',cardRef=cr)
            if code=='C21': active_domain=1; player['block']+=5
            elif code=='C12': player['block']+=10
            else:
                absorbed=0
                if code=='C10': player['block']+=8; absorbed=enemy_move()
                damage(6+absorbed,actor,'player',cr)
                if domain: damage(4,actor,'player',cr)
            add('CardPlayFinishedEntry',cardRef=cr)
            card['pile']='Discard'
            play.update(endSeq=tick(),domainAfter=active_domain,enemiesAfter=copy.deepcopy([actor])); inputs.append(play)
        if not actor['powers']: actor['block']=0
        if not engage: enemy_move()
        if not actor['guards']['isStunned']: actor['nextMove']=next_move
        active_domain=0; player['block']=0; boundary(rnd+1)
    return dict(caseId=spec['caseId'],paidStrategy='C21-if-domain;C10-plus-C12-or-three-B01;fixed-3-energy-budget',
                completedCycles=spec['turnBudget'],initial=initial,boundaries=bounds,inputs=inputs,nativeHistory=history,moveWindows=windows,paidAttempts=[])


class NonSlimeSemanticTests(unittest.TestCase):
    def test_four_finite_paid_threshold_paths_and_mutations(self):
        specs=gate.threshold_cases()
        self.assertEqual([s['turnBudget'] for s in specs],[5,5,4,4])
        for spec in specs:
            with self.subTest(policy=spec['policy']):
                c=threshold_fixture(spec)
                self.assertEqual(gate.validate_threshold_case(c,spec),[])
                for mutation in ('damage','block','payment','replay','fake-stun','window','strategy','early-death'):
                    bad=copy.deepcopy(c)
                    if mutation=='damage': bad['boundaries'][-1]['enemies'][0]['hp']+=1
                    if mutation=='block': bad['boundaries'][2]['enemies'][0]['block']+=1
                    if mutation=='payment': next(h for h in bad['nativeHistory'] if h['kind']=='EnergySpentEntry')['amount']=0
                    if mutation=='replay': bad['nativeHistory'].append(copy.deepcopy(next(h for h in bad['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry')))
                    if mutation=='fake-stun': next(h for h in bad['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry')['move']='DIZZY_MOVE'
                    if mutation=='window': bad['moveWindows'].pop()
                    if mutation=='strategy': bad['paidStrategy']='idle-end-turn'
                    if mutation=='early-death': bad['completedCycles']-=1
                    with self.subTest(mutation=mutation): self.assertTrue(gate.validate_threshold_case(bad,spec))

    def test_source_initial_guard_branches_not_inferred_from_next_move(self):
        fixtures=[('CORPSE_SLUG',{'starterMoveIdx':2},'GOOP_MOVE'),('SCROLL_OF_BITING',{'starterMoveIdx':1},'CHEW'),
                  ('AXEBOT',{'stockOverridden':True},'BOOT_UP_MOVE'),('AXEBOT',{'stockOverridden':False},'HAMMER_UPPERCUT_MOVE'),
                  ('CHOMPER',{'screamFirst':True},'SCREECH_MOVE'),('PUNCH_CONSTRUCT',{'startsWithFastPunch':False},'READY_MOVE'),
                  ('NIBBIT',{'isAlone':True,'isFront':False},'BUTT_MOVE'),('NIBBIT',{'isAlone':False,'isFront':True},'SLICE_MOVE'),
                  ('NIBBIT',{'isAlone':False,'isFront':False},'HISS_MOVE')]
        for model,guards,move in fixtures:
            actor=dict(modelId='MONSTER.'+model,guards=guards,nextMove='WRONG')
            _,expected=gate.initial_branch(actor)
            self.assertEqual(expected,(move,))
        for slot,move in [('first','SKITTER_MOVE'),('second','MANDIBLES_MOVE'),('third','ENRAGE_MOVE')]:
            self.assertEqual(gate.initial_branch(dict(modelId='MONSTER.EXOSKELETON',slot=slot,guards={}))[1],(move,))

    def test_tangled_affliction_is_not_just_power_count(self):
        for domain in (False,True):
            w,h=semantic_fixture('VINE_SHAMBLER','GRASPING_VINES_MOVE',(8,),domain=domain,
                                 player_powers=() if domain else (('TANGLED_POWER',1),))
            c=dict(cardRef='attack',id='CARD.VOLIBEAR_B01',pile='Draw',type='Attack',affliction=None,afflictionAmount=None)
            w['before']['cards']=[c]; later=copy.deepcopy(c)
            if not domain: later.update(affliction='AFFLICTION.ENTANGLED',afflictionAmount=1)
            w['after']['cards']=[later]
            self.assertEqual(gate.validate_move_window(w,h),[])
            later['afflictionAmount']=99
            self.assertTrue(gate.validate_move_window(w,h))

    def test_source_attack_values_multi_hits_and_transitions(self):
        fixtures=[('CORPSE_SLUG','WHIP_SLAP_MOVE',(3,3),'GLOMP_MOVE'),('CORPSE_SLUG','GLOMP_MOVE',(8,),'GOOP_MOVE'),
                  ('AXEBOT','ONE_TWO_MOVE',(9,9),'HAMMER_UPPERCUT_MOVE'),('TUNNELER','BITE_MOVE',(13,),'BURROW_MOVE'),
                  ('TUNNELER','BELOW_MOVE',(23,),'BELOW_MOVE'),('ZAPBOT','ZAP',(14,),'ZAP'),
                  ('CHOMPER','CLAMP_MOVE',(8,8),'SCREECH_MOVE'),('SCROLL_OF_BITING','CHEW',(5,5),'CHEW'),
                  ('SCROLL_OF_BITING','CHOMP',(14,),'MORE_TEETH'),('TWIG_SLIME_M','POKEY_POUNCE_MOVE',(11,),'POKEY_POUNCE_MOVE'),
                  ('SNEAKY_GREMLIN','TACKLE_MOVE',(9,),'TACKLE_MOVE'),('SOUL_FYSH','DE_GAS_MOVE',(16,),'GAZE_MOVE'),
                  ('BOWLBUG_SILK','THRASH_MOVE',(4,4),'TOXIC_SPIT_MOVE'),('TRACKER_RUBY_RAIDER','HOUNDS_MOVE',(1,)*8,'HOUNDS_MOVE'),
                  ('AXE_RUBY_RAIDER','BIG_SWING',(12,),'SWING_1'),('CROSSBOW_RUBY_RAIDER','FIRE_MOVE',(14,),'RELOAD_MOVE'),
                  ('BRUTE_RUBY_RAIDER','BEAT_MOVE',(7,),'ROAR_MOVE'),('FLYCONID','SMASH_MOVE',(11,),'VULNERABLE_SPORES_MOVE'),
                  ('TOADPOLE','WHIRL_MOVE',(7,),'SPIKEN_MOVE'),('WRIGGLER','NASTY_BITE_MOVE',(6,),'WRIGGLE_MOVE'),
                  ('VINE_SHAMBLER','SWIPE_MOVE',(6,6),'GRASPING_VINES_MOVE'),('GLOBE_HEAD','THUNDER_STRIKE',(6,6,6),'GALVANIC_BURST'),
                  ('CALCIFIED_CULTIST','DARK_STRIKE_MOVE',(9,),'DARK_STRIKE_MOVE'),('DAMP_CULTIST','DARK_STRIKE_MOVE',(1,),'DARK_STRIKE_MOVE'),
                  ('CUBEX_CONSTRUCT','EXPEL_MOVE',(5,5),'REPEATER_BLAST_MOVE'),('EXOSKELETON','SKITTER_MOVE',(1,1,1),'MANDIBLES_MOVE'),
                  ('PUNCH_CONSTRUCT','STRONG_PUNCH_MOVE',(14,),'READY_MOVE'),('NIBBIT','BUTT_MOVE',(12,),'SLICE_MOVE'),
                  ('LEAF_SLIME_S','TACKLE_MOVE',(3,),'GOOP_MOVE'),('LEAF_SLIME_M','CLUMP_SHOT',(8,),'STICKY_SHOT'),
                  ('TWIG_SLIME_S','TACKLE_MOVE',(4,),'TACKLE_MOVE')]
        for model,move,hits,next_move in fixtures:
            for domain in (False,True):
                w,h=semantic_fixture(model,move,hits,domain=domain)
                next_actor=dict(nextMove=next_move)
                with self.subTest(model=model,domain=domain):
                    self.assertEqual(gate.validate_move_window(w,h,next_actor),[])
                    bad=copy.deepcopy(h); bad[0]['hpLost']+=1
                    self.assertTrue(gate.validate_move_window(w,bad,next_actor))
                    self.assertTrue(gate.validate_move_window(w,h,dict(nextMove='WRONG')))
                    if len(hits)>1: self.assertTrue(gate.validate_move_window(w,h[1:],next_actor))

    def test_mixed_attacks_preserve_damage_but_suppress_debuffs(self):
        for model,move,hit,powers in [('AXEBOT','HAMMER_UPPERCUT_MOVE',12,(('WEAK_POWER',2),('FRAIL_POWER',2))),
                                    ('STABBOT','STAB_MOVE',11,(('FRAIL_POWER',1),)),
                                    ('SOUL_FYSH','SCREAM_MOVE',13,(('VULNERABLE_POWER',3),))]:
            for domain in (False,True):
                w,h=semantic_fixture(model,move,(hit,),domain=domain,player_powers=() if domain else powers,
                                     after_guards={'isInvisible':False} if model=='SOUL_FYSH' else {})
                self.assertEqual(gate.validate_move_window(w,h),[])
                w['after']['player']['powers']=[dict(id='POWER.WEAK_POWER',amount=999)]
                self.assertTrue(gate.validate_move_window(w,h))

    def test_direct_block_not_coarsely_suppressed_with_burrow(self):
        for domain in (False,True):
            w,h=semantic_fixture('TUNNELER','BURROW_MOVE',domain=domain,block=32,
                                 actor_powers=() if domain else (('BURROWED_POWER',1),))
            self.assertEqual(gate.validate_move_window(w,h),[])
            w['after']['enemies'][0]['block']=0
            self.assertTrue(gate.validate_move_window(w,h))

    def test_stock_strength_is_source_branch_not_observed_answer(self):
        for stock in (0,1,2):
            for domain in (False,True):
                amount=3*(2-stock)
                w,h=semantic_fixture('AXEBOT','BOOT_UP_MOVE',domain=domain,block=10,before_guards={'stockAmount':stock},
                                     actor_powers=() if not amount else (('STRENGTH_POWER',amount),))
                self.assertEqual(gate.validate_move_window(w,h),[])
                w['after']['enemies'][0]['powers']=[dict(id='POWER.STRENGTH_POWER',amount=99)]
                self.assertTrue(gate.validate_move_window(w,h))

    def test_status_split_piles_identity_and_domain(self):
        for model,move,cards in [('NOISEBOT','NOISE_MOVE',(('DAZED','Draw'),('DAZED','Discard'))),
                                 ('CHOMPER','SCREECH_MOVE',(('DAZED','Discard'),)*3),
                                 ('SOUL_FYSH','BECKON_MOVE',(('BECKON','Draw'),('BECKON','Discard'))),
                                 ('TWIG_SLIME_M','STICKY_SHOT_MOVE',(('SLIMED','Discard'),))]:
            for domain in (False,True):
                w,h=semantic_fixture(model,move,domain=domain,cards=() if domain else cards)
                self.assertEqual(gate.validate_move_window(w,h),[])
                if domain: w['after']['cards']=[dict(cardRef='leak',id='CARD.DAZED',pile='Draw')]
                else: w['after']['cards'][0]['pile']='Hand'
                self.assertTrue(gate.validate_move_window(w,h))

    def test_state_flags_and_direct_strength_survive_domain(self):
        for domain in (False,True):
            w,h=semantic_fixture('FUZZY_WURM_CRAWLER','INHALE',domain=domain,after_guards={'isPuffed':True},
                                 actor_powers=(('STRENGTH_POWER',7),))
            self.assertEqual(gate.validate_move_window(w,h),[])
            w['after']['enemies'][0]['guards']['isPuffed']=False
            self.assertTrue(gate.validate_move_window(w,h))

    def test_guardbot_all_and_empty_recipient_sets(self):
        for domain in (False,True):
            for present in (False,True):
                w,h=semantic_fixture('GUARDBOT','GUARD_MOVE',domain=domain)
                if present:
                    actor=copy.deepcopy(w['before']['enemies'][0]); actor.update(creatureRef='fab',modelId='MONSTER.FABRICATOR',block=4)
                    w['before']['enemies'].append(actor)
                    after=copy.deepcopy(actor); after['block']=19; w['after']['enemies'].append(after)
                self.assertEqual(gate.validate_move_window(w,h),[])
                w['after']['enemies'][0]['block']=15
                self.assertTrue(gate.validate_move_window(w,h))

    def test_rat_countdown_and_shared_summon_counter(self):
        for domain in (False,True):
            w,h=semantic_fixture('TWO_TAILED_RAT','SCRATCH_MOVE',(8,),domain=domain,
                                 before_guards={'turnsUntilSummonable':1},after_guards={'turnsUntilSummonable':0})
            self.assertEqual(gate.validate_move_window(w,h),[])
            w['after']['enemies'][0]['guards']['turnsUntilSummonable']=1
            self.assertTrue(gate.validate_move_window(w,h))
            w,h=semantic_fixture('TWO_TAILED_RAT','CALL_FOR_BACKUP_MOVE',domain=domain,
                                 before_guards={'callForBackupCount':1},after_guards={'callForBackupCount':1 if domain else 2})
            if not domain:
                rat=copy.deepcopy(w['after']['enemies'][0]); rat.update(creatureRef='new-rat',slot='two',hp=18)
                w['after']['enemies'].append(rat)
            self.assertEqual(gate.validate_move_window(w,h),[])
            w['after']['enemies'][0]['guards']['callForBackupCount']=99
            self.assertTrue(gate.validate_move_window(w,h))

    def test_wriggler_mixed_status_buff_and_slot_guard(self):
        for domain in (False,True):
            w,h=semantic_fixture('WRIGGLER','WRIGGLE_MOVE',domain=domain,
                                 actor_powers=(('STRENGTH_POWER',2),),
                                 cards=() if domain else (('INFECTION','Discard'),))
            self.assertEqual(gate.validate_move_window(w,h),[])
            w['after']['cards']=[dict(cardRef='bad',id='CARD.SLIMED',pile='Discard')]
            self.assertTrue(gate.validate_move_window(w,h))
        for slot,expected in [('wriggler1','NASTY_BITE_MOVE'),('wriggler2','WRIGGLE_MOVE')]:
            w,h=semantic_fixture('WRIGGLER','SPAWNED_MOVE'); w['before']['enemies'][0]['slot']=slot
            self.assertEqual(gate.validate_move_window(w,h,dict(nextMove=expected)),[])
            self.assertTrue(gate.validate_move_window(w,h,dict(nextMove='WRIGGLE_MOVE' if expected=='NASTY_BITE_MOVE' else 'NASTY_BITE_MOVE')))

    def test_unknown_or_missing_window_never_becomes_semantic_pass(self):
        w,h=semantic_fixture('ARCHITECT','UNSPECIFIED')
        self.assertTrue(gate.validate_move_window(w,h)[0].startswith('UNSPECIFIED_NATIVE_MOVE:'))
        errors,rows=gate.validate_case_semantics(dict(nativeHistory=h,boundaries=[],moveWindows=[w]))
        self.assertEqual(errors,[]); self.assertEqual(rows[0]['status'],'UNSPECIFIED')
        errors,_=gate.validate_case_semantics(dict(nativeHistory=h,boundaries=[],moveWindows=[]))
        self.assertTrue(errors)


class PaidAcceptanceTests(unittest.TestCase):
    def test_exact_twelve_cases_and_all_four_combinations(self):
        cat=catalog(); selection=gate.prepare_selection(cat, mode='paid-acceptance')
        self.assertEqual(len(selection['cases']),12)
        self.assertEqual(gate.validate_selection(selection,cat),[])
        selection['cases'].pop()
        self.assertTrue(gate.validate_selection(selection,cat))

    def test_all_source_derived_four_cycle_oracles(self):
        for spec in gate.paid_cases():
            with self.subTest(case=spec['caseId']):
                self.assertEqual(gate.validate_paid_case(paid_fixture(spec),spec),[])

    def test_missing_payment_replay_wrong_side_and_missing_cycles_fail(self):
        spec=gate.paid_cases()[1]
        for mutation in ('payment','side','repeat','cycles','intent','damage','status','autoplay','destination'):
            c=paid_fixture(spec)
            if mutation=='payment': next(h for h in c['nativeHistory'] if h['kind']=='EnergySpentEntry')['amount']=0
            if mutation=='side': next(h for h in c['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry' and h['side']=='Player')['side']='Enemy'
            if mutation=='repeat': c['nativeHistory'].append(copy.deepcopy(next(h for h in c['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry')))
            if mutation=='cycles': c['boundaries'].pop()
            if mutation=='intent': c['boundaries'][1]['enemies'][1]['nextMove']='STICKY_SHOT'
            if mutation=='damage': next(h for h in c['nativeHistory'] if h['kind']=='DamageReceivedEntry')['blocked']=0
            if mutation=='status': c['boundaries'][1]['cards']=[]
            if mutation=='autoplay': c['inputs'][0]['type']='AutoPlay'
            if mutation=='destination': c['inputs'][0]['pileAfter']='Hand'
            with self.subTest(mutation=mutation): self.assertTrue(gate.validate_paid_case(c,spec))

    def test_domain_requires_paid_entry_and_blocks_only_status(self):
        spec=gate.paid_cases()[3]
        for mutation in ('no-domain','status-leak','attack-suppressed','missing-card','early-expiry'):
            c=paid_fixture(spec)
            if mutation=='no-domain': c['inputs'][0]['domainAfter']=0
            if mutation=='status-leak': c['boundaries'][1]['cards'].append(dict(cardRef='leak',id='CARD.SLIMED'))
            if mutation=='attack-suppressed': c['nativeHistory']=[h for h in c['nativeHistory'] if h['kind']!='DamageReceivedEntry']
            if mutation=='missing-card': c['inputs'].pop(0)
            if mutation=='early-expiry': c['inputs'][1]['domainBefore']=0
            with self.subTest(mutation=mutation): self.assertTrue(gate.validate_paid_case(c,spec))

    def test_all_formal_roots_get_finite_batches_without_dropping_denominator(self):
        cat=catalog(); required=gate.formal_cases(cat)
        self.assertGreater(len(required),80)
        selected=[]
        for batch in range((len(required)+79)//80):
            selection=gate.prepare_selection(cat,mode='formal-paid',batch_index=batch)
            self.assertEqual(gate.validate_selection(selection,cat),[])
            selected += selection['cases']
        self.assertEqual(selected,required)
        self.assertEqual({c['encounter'] for c in selected},set.union(*gate.registered(cat).values()))
        coverage=gate.formal_paid_coverage(cat)
        self.assertEqual(len(coverage['requiredCases']),len(required))
        self.assertTrue(all(c['schedulingStatus']=='NOT_RUN' and c['effectBranches']=='NOT_RUN' for c in coverage['requiredCases']))
        self.assertFalse(coverage['completeAiCoverage'])

    def test_formal_paid_scheduling_and_mutations(self):
        for policy in gate.PAID_POLICIES:
            spec=dict(caseId='formal-SLIMES_WEAK:LEAF_SLIME_M:'+policy,policy=policy,turnBudget=8)
            c=paid_fixture(spec,8)
            self.assertEqual(gate.validate_formal_paid_case(c,spec),[])
            for change in ('missing-target','missing-cycle','missing-domain','replay'):
                bad=copy.deepcopy(c)
                if change=='missing-target': bad['paidAttempts']=[dict(status='NOT_OBSERVED')]
                if change=='missing-cycle': bad['completedCycles']=2
                if change=='missing-domain': bad['inputs'].pop(0)
                if change=='replay':
                    if '-engage-' not in policy: continue
                    m=copy.deepcopy(next(h for h in bad['nativeHistory'] if h['kind']=='MonsterPerformedMoveEntry' and h['side']=='Player'))
                    m['side']='Enemy'; bad['nativeHistory'].append(m)
                with self.subTest(policy=policy,change=change): self.assertTrue(gate.validate_formal_paid_case(bad,spec))

    def test_existing_run_config_accepts_both_paid_modes_without_new_bootstrap(self):
        import json
        import tempfile
        from enemy_exploration_run_config import prepare_run_inputs
        cat=catalog()
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); cp=root/'catalog.json'; cp.write_text(json.dumps(cat),encoding='utf-8')
            for mode in ('paid-acceptance','formal-paid','paid-threshold'):
                if mode=='paid-threshold':
                    cat=json.loads(json.dumps(cat).replace('ENCOUNTER.BOWLBUGS_WEAK','ENCOUNTER.TUNNELER_WEAK').replace('MONSTER.TWIG_SLIME_S','MONSTER.TUNNELER'))
                    cp.write_text(json.dumps(cat),encoding='utf-8')
                sp=root/(mode+'.json'); sp.write_text(json.dumps(gate.prepare_selection(cat,mode=mode)),encoding='utf-8')
                env,frozen,_,prereq=prepare_run_inputs(root/mode,sp,cp)
                self.assertTrue(frozen.is_file())
                self.assertEqual(set(env),{'VOLIBEAR_TEST_MATRIX_SELECTION'})
                self.assertIsNone(prereq)

    def test_knowledge_input_receipt_cannot_fake_native_return(self):
        spec=dict(caseId='formal-SLIMES_WEAK:LEAF_SLIME_M:paid-engage-off',policy='paid-engage-off',turnBudget=8)
        c=paid_fixture(spec,8)
        c['choiceInputs']=[dict(api='Viewport.PushInput',kind='knowledge-disintegration-only',
                               selectedCardId='CARD.DISINTEGRATION',pressed=[True,False],focusMatched=True,
                               physicalInputValidated=False,candidates=['CARD.DISINTEGRATION','CARD.MIND_ROT'],
                               seq=10,pressSeq=10,releaseSeq=11,endSeq=12)]
        self.assertTrue(gate.validate_formal_paid_case(c,spec))
        c['choiceInputs'][0]['pressSeq']=True
        self.assertTrue(gate.validate_formal_paid_case(c,spec))

    def test_source_denominator_and_narrow_exclusions(self):
        import tempfile
        cat=catalog()
        cat['unreachedCandidates']=[dict(id='MONSTER.'+name.upper(),type='MegaCrit.Sts2.Core.Models.Monsters.'+name)
                                  for name in ('MockAttackMonster','MockArtifactMonster','Tunneler')]
        cat['unreachedCandidates'].append(dict(id='ENCOUNTER.TUNNELER_NORMAL',type='MegaCrit.Sts2.Core.Models.Encounters.TunnelerNormal'))
        classified=gate.source_classification(cat)
        self.assertEqual([c['status'] for c in classified],['SOURCE_UNREACHABLE','REACHABILITY_UNRESOLVED','REACHABILITY_UNRESOLVED','SOURCE_UNREACHABLE'])
        with tempfile.TemporaryDirectory() as root:
            monster=cat['monsters'][0]; ns,name=monster['type'].rsplit('.',1)
            path=Path(root)/ns/(name+'.cs'); path.parent.mkdir(parents=True)
            path.write_text('MoveState a = new MoveState("A", Attack);\na.FollowUpState = a;\nif (hp < 5)\nawait DamageCmd.Attack(3);\nnew AnimState("idle");',encoding='utf-8')
            result=gate.formal_source_requirements(cat,root)
        self.assertEqual(len(result['formalMonsters']),len(cat['monsters']))
        row=result['formalMonsters'][0]
        self.assertEqual(row['states'][0]['id'],'A')
        self.assertEqual(len(row['states']),1) # animator states are NOT enemy AI states
        self.assertEqual(len(row['transitions']),1)
        self.assertEqual(len(row['conditions']),1)
        self.assertEqual(len(row['effects']),1)
        self.assertFalse(row['branchInventoryComplete'])
        self.assertFalse(result['completeAiCoverage'])

    def test_baseline_and_unknown_denominator_never_pass_g4(self):
        cat=catalog(); coverage=gate.paid_coverage(cat)
        self.assertFalse(coverage['completeAiCoverage'])
        self.assertEqual(len(coverage['formalMonsters']),len(cat['monsters']))
        self.assertTrue(all(c['status']=='NOT_RUN' for c in coverage['requiredCases']))
        self.assertTrue(all(m['effectBranches']=='UNKNOWN_NOT_EXHAUSTIVELY_IDENTIFIED' for m in coverage['formalMonsters']))
        self.assertEqual(coverage['unreachedCandidates'],cat['unreachedCandidates'])
        self.assertTrue(coverage['remainingBranches'])

if __name__=='__main__': unittest.main()
