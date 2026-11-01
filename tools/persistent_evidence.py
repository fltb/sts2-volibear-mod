"""Strict raw-observation comparator. U32 proves native action-queue payment, not mouse input.
The 19 hand-authored fixture cases remain the denominator; unsupported cases are NOT_RUN.
"""
import json
from pathlib import Path

PREFIX = '[Volibear] PERSISTENT_CONTRACT_RESULT '
PERSISTENT_CASES = ('PP-U21-deploy-at-three', 'PP-U21-two-independent', 'PP-U26-before-effects',
                    'PP-U25-replay', 'PP-U25-purification', 'PP-R02-unpowered', 'PP-R02-no-consumption')
ADDITIONAL_CASES = ('PP-U02-instances','PP-U02-domain-order','PP-U03-min-stack','PP-U03-other-retention',
                    'PP-R16-positive-own-block','PP-R16-passive-block-excluded','PP-U34-per-batch')
ENGAGEMENT_CASES = ('PP-U04-independent-first','PP-U19-draw-before-extend','PP-R18-independent-batches')
SPECIAL_CASES = ('PP-U25-live-finish-count','PP-U32-max-coupon')
PERSISTENT_CASES += ADDITIONAL_CASES + ENGAGEMENT_CASES + SPECIAL_CASES
FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/persistent_power_cases.json'


def _need(value):
    if not value:
        raise ValueError('Persistent native observation violates frozen fixture')


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


def case_statuses(results=None):
    """No probe availability or completed flag can turn an unexecuted case into PASS."""
    results = results or {}
    cases = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
    return {c['id']: results.get(c['id'], 'NOT_RUN') for c in cases}


def validate_persistent_result(r, token, variant):
    try:
        _need(variant in PERSISTENT_CASES)
        if variant in ADDITIONAL_CASES:
            return _additional(r, token, variant)
        if variant in ENGAGEMENT_CASES:
            return _engagement(r, token, variant)
        if variant in SPECIAL_CASES:
            return _special(r, token, variant)
        oracle = next(c['expected'] for c in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases'] if c['id'] == variant)
        fixed = dict(token=token, scenario='persistent-contract', variant=variant, completed=True,
                     gameVersion='v0.107.1', gameCommit='59260271', testMode=False,
                     acceptance='mechanism-autoplay-not-payment-not-formal-enemy', character='VolibearCharacter')
        _need(set(r) == set(fixed) | set('enemyIds enemyTypes inputs snapshots beforeEffects batches draw engage playHistory drawHistory damageHistory'.split()))
        _need(all(_eq(r[k], v) for k, v in fixed.items()))
        ids = r['enemyIds']
        clamp = variant == 'PP-R02-no-consumption'
        size = 2 if clamp else 3
        _need(type(ids) is list and len(ids) == size and len(set(ids)) == size and all(type(i) is int and i >= 0 for i in ids))
        monsters = r['enemyTypes']
        if clamp:
            _need(_eq(monsters,['Chomper','Chomper']))
        else:
            _need(r['engage'] is None)
            _need(len(monsters) == 3 and monsters.count('LeafSlimeS') == 1 and monsters.count('TwigSlimeS') == 1
                  and sum(x in ('LeafSlimeM', 'TwigSlimeM') for x in monsters) == 1)
        powers_seen = {}
        def snap(actual, label, energy=3, hp=80, block=0, enemies=None, count=0, powers=(), round=1, turn=1):
            expected = dict(label=label, round=round, turn=turn, energy=energy, hp=hp, block=block,
                            enemyHp=list(enemies) if enemies is not None else [100]*size, lightningCount=count, powers=actual['powers'])
            _need(_eq(actual, expected))
            rows = actual['powers']
            _need(len(rows) == len(powers))
            _need(len({p['powerRef'] for p in rows}) == len(rows))
            for row, (kind, amount) in zip(rows, powers):
                ref = row['powerRef']
                _need(type(ref) is int and ref > 0 and _eq(row, dict(powerRef=ref, type=kind, amount=amount)))
                if ref in powers_seen:
                    _need(powers_seen[ref] == kind)
                powers_seen[ref] = kind
        def hit(target, amount, card, props=8, blocked=0, player=False):
            return dict(target=target, playerTarget=player, hpLost=amount, blocked=blocked, props=props, cardRef=card)
        def plays(replay):
            return [dict(cardRef='first',index=0,count=1),dict(cardRef='second',index=0,count=1+replay)] + (
                [dict(cardRef='second',index=1,count=2)] if replay else [])
        def pre(replay, strengths, storms):
            rows = r['beforeEffects']; sequence = plays(replay)
            _need(len(rows) == len(sequence))
            seen = []
            for i, (row, card) in enumerate(zip(rows, sequence)):
                identity = row['playId']
                _need(type(identity) is int and identity > 0)
                _need(_eq(row, dict(card,playId=identity,ordinal=1 if i == 0 else 2,
                                   strength=strengths[i],storm=storms[i])))
                seen.append(identity)
            _need(seen[0] != seen[1] and (not replay or seen[1] == seen[2]))
        expected_damage = []
        expected_batches = []
        snapshots = r['snapshots']
        _need(type(r['inputs']) is list)
        if variant.startswith('PP-U21'):
            two = variant == 'PP-U21-two-independent'
            start, end = (5, 8) if two else (3, 4)
            power = [('ThunderAftershockPower',1)] * (2 if two else 1)
            energies = [oracle['energy_after_deployments'],oracle['energy_after_sixth'],oracle['energy_after_seventh'],oracle['energy_after_eighth']] if two else [oracle['energy_after_deploy'],oracle['energy_after_fourth']]
            _need(len(snapshots) == (6 if two else 4))
            snap(snapshots[0],'initial',energy=0)
            snap(snapshots[1],'before-deploy',energy=0,count=start)
            snap(snapshots[2],'after-deploy',energy=energies[0],count=start,powers=power)
            for j, n in enumerate(range(start+1,end+1),3):
                snap(snapshots[j],'batch-'+str(n),energy=energies[j-2],count=n,powers=power)
                _need([p['powerRef'] for p in snapshots[j]['powers']] == [p['powerRef'] for p in snapshots[2]['powers']])
            _need(_eq(r['beforeEffects'],[]) and _eq(r['playHistory'],[]) and _eq(r['drawHistory'],[]) and r['draw'] is None)
            expected_batches = [(0,None)] * end
            expected_damage = [hit(e,0,None,4) for _ in range(end) for e in ids]
            _need(sum(x.get('op')=='PowerCmd.Apply' for x in r['inputs']) == len(power))
        elif variant == 'PP-U26-before-effects':
            _need(len(snapshots) == 3)
            snap(snapshots[0],'initial')
            base = [('GrowingFuryPower',1),('GrowingFuryPower',2)]
            snap(snapshots[1],'after-first',enemies=(94,100,100),powers=base)
            snap(snapshots[2],'after-second',enemies=(76,100,100),powers=base+[('StrengthPower',oracle['strength_after_replay']),('StormChargePower',oracle['storm_after_replay'])])
            pre(1,[0,oracle['strength_before_first_effect'],oracle['strength_before_first_effect']],[0,3,3])
            _need(_eq(r['playHistory'],plays(1)) and _eq(r['drawHistory'],[]) and r['draw'] is None)
            expected_damage = [hit(ids[0],6,'first')] + [hit(ids[0],v,'second') for v in oracle['ordinary_hit_amounts']]
        elif variant.startswith('PP-U25'):
            purification = variant == 'PP-U25-purification'
            replay = 0 if purification else 1
            _need(len(snapshots) == 3)
            snap(snapshots[0],'initial')
            powers = [('PreyStillStandsPower',1)] + ([('DomainPower',1)] if purification else [])
            snap(snapshots[1],'after-first',enemies=(90,96,96) if purification else (94,100,100),count=int(purification),powers=powers)
            snap(snapshots[2],'after-second',enemies=(80,92,92) if purification else (82,100,100),count=2 if purification else 0,powers=powers)
            pre(replay,[0]*(2+replay),[0]*(2+replay))
            _need(_eq(r['playHistory'],plays(replay)))
            # Native Draw records the direct status before its purification hook draws the replacement.
            expected_draws = ([dict(cardRef='direct-status',fromHandDraw=False)] if purification else []) + [dict(cardRef='drawn-attack',fromHandDraw=False)]
            _need(_eq(r['drawHistory'],expected_draws))
            _need(_eq(r['draw'], dict(attackRef='drawn-attack',type='Volibear_B01',cost=oracle['replacement_attack_next_cost'] if purification else oracle['drawn_attack_next_cost'],pile='Hand',identityInHand=True,
                                     statusRef='direct-status' if purification else None,statusPile='Exhaust' if purification else None,
                                     statusIdentityInExhaust=purification,targetCount=2)))
            expected_damage=[hit(ids[0],6,'first')]
            if purification:
                expected_damage += [hit(e,4,'first',4) for e in ids] + [hit(ids[0],6,'second')] + [hit(e,4,'second',4) for e in ids]
                expected_batches=[(4,'first'),(4,'second')]
            else:
                expected_damage += [hit(ids[0],6,'second')]*2
        elif clamp:
            _need(len(snapshots)==5)
            power=[('ImmovableBodyPower',oracle['immovable_amount'])]
            snap(snapshots[0],'initial')
            snap(snapshots[1],'before-engage',block=5,powers=power)
            snap(snapshots[2],'after-engage',hp=oracle['hp'],block=oracle['block'],powers=power)
            snap(snapshots[3],'after-duplicate',hp=74,block=5,powers=power)
            snap(snapshots[4],'after-native-phase',hp=74,block=0,powers=power,round=2,turn=2)
            _need(_eq(r['playHistory'],[]) and _eq(r['beforeEffects'],[]) and r['draw'] is None)
            draws=r['drawHistory'];_need(len(draws)==6)
            _need(_eq(draws[0],dict(cardRef='engage-draw',fromHandDraw=False)))
            _need(len({d['cardRef'] for d in draws[1:]})==5)
            for d in draws[1:]:
                _need(type(d['cardRef']) is str and d['cardRef'].startswith('starting-') and _eq(d,dict(cardRef=d['cardRef'],fromHandDraw=True)))
            _need(_eq(r['engage'],dict(target=ids[0],consumedBefore=False,consumedAfter=True,consumedNextTurn=False,
                movesBefore=['CLAMP_MOVE','SCREECH_MOVE'],movesAfterEngage=['CLAMP_MOVE','SCREECH_MOVE'],
                movesNextTurn=['SCREECH_MOVE','CLAMP_MOVE'],moveCountsBefore=[0,0],moveCountsAfter=[1,0],
                duplicateCounts=[1,0],moveCountsNextTurn=[1,1],
                receipt=dict(performed=True,completed=True,absorbed=oracle['absorbed']),
                duplicate=dict(performed=False,completed=False,absorbed=0),
                absorption=[dict(requested=8,props=8,absorbed=5,blockAfter=5,hpBeforeLoss=80),dict(requested=8,props=8,absorbed=5,blockAfter=5,hpBeforeLoss=77)],
                stateLogs=[['CLAMP_MOVE','SCREECH_MOVE'],['SCREECH_MOVE','CLAMP_MOVE']])))
            _need(len(r['damageHistory'])==2)
            pid=r['damageHistory'][0]['target'];_need(type(pid) is int and pid not in ids)
            expected_damage=[hit(pid,3,None,8,5,True)]*2
        else:
            _need(len(snapshots) == 3)
            snap(snapshots[0],'initial')
            snap(snapshots[1],'before-damage',block=5,powers=[('ImmovableBodyPower',1)])
            snap(snapshots[2],'after-damage',hp=oracle['hp'],block=oracle['block'],powers=[('ImmovableBodyPower',1)])
            _need(_eq(r['beforeEffects'],[]) and _eq(r['playHistory'],[]) and _eq(r['drawHistory'],[]) and r['draw'] is None)
            _need(len(r['damageHistory']) == 1)
            player_id=r['damageHistory'][0]['target']
            _need(type(player_id) is int and player_id not in ids)
            expected_damage=[hit(player_id,3,None,4,5,True)]
        apply = lambda name, n: dict(op='PowerCmd.Apply',type=name,amount=n)
        play_input = lambda name, n: dict(op='CardCmd.AutoPlay',cardRef=name,type='Volibear_B01',replay=n,target=ids[0])
        if variant.startswith('PP-U21'):
            expected_inputs = [apply('ThunderAftershockPower',1)]*(2 if two else 1) + [dict(op='LightningCmd.DealAllEnemies',baseDamage=0)]*(3 if two else 1)
        elif variant == 'PP-U26-before-effects':
            expected_inputs = [apply('GrowingFuryPower',1),apply('GrowingFuryPower',2),play_input('first',0),play_input('second',1)]
        elif variant.startswith('PP-U25'):
            expected_inputs = [apply('PreyStillStandsPower',1),play_input('first',0),play_input('second',replay)]
        elif clamp:
            expected_inputs = [dict(op='ImmovableBodyPower.Deploy',cardRef='engage-source')]*2 + [dict(op='EngageCmd.Perform',cardRef='engage-source',target=ids[0]),dict(op='PlayerCmd.EndTurn')]
        else:
            expected_inputs = [apply('ImmovableBodyPower',1),dict(op='CreatureCmd.Damage',amount=8,props=4)]
        _need(_eq(r['inputs'],expected_inputs))
        _need(_eq(r['damageHistory'],expected_damage))
        _need(len(r['batches']) == len(expected_batches))
        seen_batch=[]
        for i,(row,(amount,card)) in enumerate(zip(r['batches'],expected_batches),1):
            identity=row['id'];_need(type(identity) is int and identity>0);seen_batch.append(identity)
            _need(_eq(row,dict(id=identity,round=1,turn=1,count=i,baseDamage=amount,storm=0,amount=amount,
                              cardRef=card,targets=ids,hits=[dict(target=e,hpLost=amount,blocked=0) for e in ids])))
        _need(seen_batch==sorted(set(seen_batch)))
        # Preserve instance identity across all post-deployment snapshots, not merely counts/types.
        for earlier,later in zip(snapshots[1:],snapshots[2:]):
            old=earlier['powers'];new=later['powers']
            _need([p['powerRef'] for p in new[:len(old)]] == [p['powerRef'] for p in old])
        return True
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,StopIteration):
        return False


def persistent_contract_evidence(log, run_id, variant):
    lines=[line[len(PREFIX):] for line in log.splitlines() if line.startswith(PREFIX)]
    if len(lines)!=1 or variant not in PERSISTENT_CASES:
        return None,False
    try:
        result=json.loads(lines[0])
    except (ValueError,TypeError):
        return None,False
    return result,validate_persistent_result(result,run_id,variant)


def _additional(r,token,case):
    oracle=next(c['expected'] for c in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases'] if c['id']==case)
    fixed=dict(token=token,scenario='persistent-contract',variant=case,completed=True,schema='additional-v1',gameVersion='v0.107.1',
               gameCommit='59260271',testMode=False,acceptance='mechanism-autoplay-not-payment-not-formal-enemy',character='VolibearCharacter')
    fields='enemyIds enemyTypes fixturePreparation setup before after batches beforeEffects finishedEffects played phaseBlockGains clearPreventers movesAfterBoundary consumedAfterBoundary drawHistory playHistory damageHistory'.split()
    _need(set(r)==set(fixed)|set(fields) and all(_eq(r[k],v) for k,v in fixed.items()))
    ids=r['enemyIds'];two=case.startswith('PP-U02');standing=case.startswith('PP-U03')
    _need(type(ids) is list and len(ids)==(2 if two else 3) and len(set(ids))==len(ids) and all(type(i) is int and i>=0 for i in ids))
    types=r['enemyTypes']
    if two:_need(_eq(types,['Chomper','Chomper']))
    else:_need(len(types)==3 and types.count('LeafSlimeS')==1 and types.count('TwigSlimeS')==1 and sum(t in ('LeafSlimeM','TwigSlimeM') for t in types)==1)
    prep=r['fixturePreparation']
    _need(set(prep)==set('removedRelics restoredHpAfterPreparation preparations moves damage measurementHistoryBoundary preparationHistoryStart'.split()))
    _need(_eq(prep['removedRelics'],['HuntersHeart']) and _eq(prep['restoredHpAfterPreparation'],standing))
    _need(type(prep['measurementHistoryBoundary']) is int and type(prep['preparationHistoryStart']) is int and
          prep['measurementHistoryBoundary']>=prep['preparationHistoryStart']>=0)
    if standing:
        _need(_eq(prep['moves'],ids) and len(prep['preparations'])==3)
        amounts={'LeafSlimeS':{'TACKLE_MOVE':3,'GOOP_MOVE':0},'TwigSlimeS':{'TACKLE_MOVE':4},
                 'LeafSlimeM':{'CLUMP_SHOT':8,'STICKY_SHOT':0},'TwigSlimeM':{'POKEY_POUNCE_MOVE':11,'STICKY_SHOT_MOVE':0}}
        attacks=[]
        for row,e,t in zip(prep['preparations'],ids,types):
            move=row['move'];_need(move in amounts[t])
            _need(_eq(row,dict(enemy=e,move=move,performed=True,completed=True,absorbed=0,consumed=True)))
            if amounts[t][move]:attacks.append(amounts[t][move])
        _need(len(prep['damage'])==len(attacks))
        pid=None
        for row,damage in zip(prep['damage'],attacks):
            pid=row['target'] if pid is None else pid
            _need(type(pid) is int and pid not in ids and _eq(row,dict(target=pid,playerTarget=True,hpLost=damage,blocked=0,props=8,cardRef=None)))
        _need(prep['measurementHistoryBoundary']>prep['preparationHistoryStart'])
    else:_need(_eq(prep['preparations'],[]) and _eq(prep['moves'],[]) and _eq(prep['damage'],[]))
    powers=[];final=[];setup=[];block0=0;block1=0;enemyBlock0=[0]*len(ids);enemyBlock1=[0]*len(ids)
    enemyHp=[100]*len(ids);count=0;batch_specs=[];damage=[];replay=0;strength=0;dexterity=0
    def hit(e,n,props=8,card='played',blocked=0):return dict(target=e,playerTarget=False,hpLost=n,blocked=blocked,props=props,cardRef=card)
    def app(t,n):return dict(type=t,amount=n)
    if case=='PP-U02-instances':
        powers=[('StormConductionPower',3),('StormConductionPower',4)];setup=[app(t,n) for t,n in powers]
        enemyHp=oracle['enemy_hp'];count=oracle['lightning_batches'];batch_specs=[(3,0,None,0),(4,0,None,0)]
    elif case=='PP-U02-domain-order':
        powers=[('DomainPower',1),('StormConductionPower',3),('StormChargePower',2)];setup=[app('StormConductionPower',3)]
        enemyHp=oracle['enemy_hp'];count=oracle['batches'];batch_specs=[(4,2,'played',0),(3,2,None,0)]
    elif standing:
        powers=[('StandingPower',3)];block0=20;block1=oracle['block']
        setup=[app('StandingPower.Deploy',n) for n in ([6,3,6] if case=='PP-U03-min-stack' else [3])]
        if case=='PP-U03-other-retention':powers.append(('BarricadePower',1));setup.append(app('BarricadePower',1))
    elif case=='PP-U34-per-batch':
        powers=[('ThunderArmorPower',3),('ThunderArmorPower',4)];setup=[app(t,n) for t,n in powers]
        block1=oracle['block'];count=oracle['lightning_count'];enemyBlock0=[10]*3;enemyBlock1=[9]*3;batch_specs=[(1,0,None,1)]
    elif case=='PP-R16-positive-own-block':
        powers=[('BattleBodyPower',2)];setup=[app('BattleBodyPower',2)];replay=1;block1=10;enemyHp=[90,100,100]
        strength=oracle['strength_gained'];dexterity=oracle['dexterity_gained'];damage=[hit(ids[0],5)]*2
        final=[('StrengthPower',strength),('DexterityPower',dexterity)]
    else:
        powers=[('BattleBodyPower',1),('ThunderArmorPower',3),('DomainPower',1)];setup=[app('BattleBodyPower',1),app('ThunderArmorPower',3)]
        strength=oracle['strength_gained'];dexterity=oracle['dexterity_gained'];block1=oracle['block'];count=1;enemyHp=[90,96,96]
        batch_specs=[(4,0,'played',0)];final=[('StrengthPower',1)]
    _need(_eq(r['setup'],setup))
    def snapshot(row,after):
        wanted=powers+(final if after else [])
        _need(len(row['powers'])==len(wanted))
        refs=[]
        for power,(kind,n) in zip(row['powers'],wanted):
            ref=power['powerRef'];_need(type(ref) is int and ref>0);refs.append(ref)
            _need(_eq(power,dict(powerRef=ref,type=kind,amount=n)))
        _need(len(set(refs))==len(refs))
        _need(_eq(row,dict(round=2 if standing and after else 1,turn=2 if standing and after else 1,hp=80,
                           block=block1 if after else block0,energy=3,enemyHp=enemyHp if after else [100]*len(ids),
                           enemyBlock=enemyBlock1 if after else enemyBlock0,count=count if after else 0,powers=row['powers'])))
        return refs
    before_refs=snapshot(r['before'],False);after_refs=snapshot(r['after'],True)
    _need(after_refs[:len(before_refs)]==before_refs)
    no_play=standing or case=='PP-U34-per-batch'
    if no_play:
        for key in ('beforeEffects','finishedEffects','playHistory'):_need(_eq(r[key],[]))
        _need(r['played'] is None)
    else:
        _need(_eq(r['played'],dict(cardRef='played',type='IronWave' if replay else 'Volibear_B01',replay=replay)))
        plays=[dict(cardRef='played',index=i,count=1+replay) for i in range(1+replay)]
        _need(_eq(r['playHistory'],plays) and len(r['beforeEffects'])==len(plays) and len(r['finishedEffects'])==len(plays))
        play_id=r['beforeEffects'][0]['playId'];_need(type(play_id) is int and play_id>0)
        for i,p in enumerate(plays):
            _need(_eq(r['beforeEffects'][i],dict(p,playId=play_id,ordinal=1,strength=0,storm=2 if case=='PP-U02-domain-order' else 0)))
            _need(_eq(r['finishedEffects'][i],dict(p,playId=play_id,actualCompleted=i==replay,strength=strength if i==replay else 0,dexterity=dexterity if i==replay else 0)))
        if not replay:damage=[hit(ids[0],6)]
    _need(len(r['batches'])==len(batch_specs))
    batch_ids=[]
    for index,(row,(base,storm,card,blocked)) in enumerate(zip(r['batches'],batch_specs),1):
        identity=row['id'];_need(type(identity) is int and identity>0);batch_ids.append(identity)
        amount=base+storm;lost=0 if blocked else amount
        _need(_eq(row,dict(id=identity,round=1,turn=1,count=index,baseDamage=base,storm=storm,amount=amount,cardRef=card,targets=ids,
                           hits=[dict(target=e,hpLost=lost,blocked=blocked) for e in ids])))
        damage += [hit(e,lost,4,card,blocked) for e in ids]
    _need(batch_ids==sorted(set(batch_ids)) and _eq(r['damageHistory'],damage))
    _need(_eq(r['phaseBlockGains'],[]) and _eq(r['movesAfterBoundary'],[]) and _eq(r['consumedAfterBoundary'],[False]*len(ids)))
    _need(_eq(r['clearPreventers'],['BarricadePower'] if case=='PP-U03-other-retention' else []))
    if standing:
        draws=r['drawHistory'];_need(len(draws)==5 and len({d['cardRef'] for d in draws})==5)
        for row in draws:_need(type(row['cardRef']) is str and row['cardRef'].startswith('starting-') and _eq(row,dict(cardRef=row['cardRef'],fromHandDraw=True)))
    else:_need(_eq(r['drawHistory'],[]))
    return True


def _engagement(r,token,case):
    oracle=next(c['expected'] for c in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases'] if c['id']==case)
    fixed=dict(token=token,scenario='persistent-contract',variant=case,completed=True,schema='engagement-v1',gameVersion='v0.107.1',gameCommit='59260271',
               testMode=False,acceptance='mechanism-autoplay-not-payment-not-formal-enemy',character='VolibearCharacter')
    fields='enemyIds enemyTypes removedRelics initialMoves stages receipts batches drawResponses consumed status playHistory drawHistory moveHistory damageHistory'.split()
    _need(set(r)==set(fixed)|set(fields) and all(_eq(r[k],v) for k,v in fixed.items()))
    ids=r['enemyIds'];types=r['enemyTypes']
    _need(type(ids) is list and len(ids)==3 and len(set(ids))==3 and all(type(i) is int and i>=0 for i in ids))
    _need(len(types)==3 and types.count('LeafSlimeS')==1 and types.count('TwigSlimeS')==1 and sum(t in ('LeafSlimeM','TwigSlimeM') for t in types)==1)
    _need(_eq(r['removedRelics'],['HuntersHeart']) and _eq(r['playHistory'],[]))
    amounts={'LeafSlimeS':{'TACKLE_MOVE':3,'GOOP_MOVE':0},'TwigSlimeS':{'TACKLE_MOVE':4},
             'LeafSlimeM':{'CLUMP_SHOT':8,'STICKY_SHOT':0},'TwigSlimeM':{'POKEY_POUNCE_MOVE':11,'STICKY_SHOT_MOVE':0}}
    _need(type(r['initialMoves']) is list and len(r['initialMoves'])==3)
    losses=[amounts[t][m] for t,m in zip(types,r['initialMoves'])]
    lingering=case=='PP-U19-draw-before-extend';pool=case=='PP-R18-independent-batches'
    count=1 if lingering else 2
    _need(_eq(r['receipts'],[dict(target=e,performed=True,completed=True,absorbed=0,consumed=True) for e in ids[:count]]))
    _need(_eq(r['moveHistory'],ids if pool else ids[:count]))
    _need(_eq(r['consumed'],[False]*3 if pool else [True]*count+[False]*(3-count)))
    powers=[];stage_specs=[]
    if lingering:
        powers=[('LingeringStormPower',1)]
        stage_specs=[('before',80,3,100,0,1,powers),('after-first',80-losses[0],2,100,0,1,powers+[('DomainPower',oracle['domain_rounds'])])]
    elif pool:
        powers=[('ThunderPoolPower',4),('ThunderPoolPower',6)]
        stage_specs=[('before',80,3,100,0,1,powers),('after-first',80-losses[0],3,90,2,1,powers),
                     ('after-second',80-losses[0]-losses[1],3,90,2,1,powers),('after-native-phase',80-sum(losses),3,80,0,2,powers)]
    else:
        powers=[('BattleScarsPower',1)]
        first=powers+[('StrengthPower',1),('StormChargePower',1)]
        second=first+[('BattleScarsPower',2)]
        final=[('BattleScarsPower',1),('StrengthPower',oracle['strength_gained']),('StormChargePower',oracle['storm_gained']),('BattleScarsPower',2)]
        stage_specs=[('before',80,3,100,0,1,powers),('after-first',80-losses[0],3,100,0,1,first),
                     ('after-second-deploy',80-losses[0],3,100,0,1,second),('after-second',80-losses[0]-losses[1],3,100,0,1,final)]
    _need(len(r['stages'])==len(stage_specs))
    previous=[]
    for row,(label,hp,energy,enemyhp,batches,turn,expected_powers) in zip(r['stages'],stage_specs):
        rows=row['powers'];_need(len(rows)==len(expected_powers));refs=[]
        for power,(kind,amount) in zip(rows,expected_powers):
            ref=power['powerRef'];_need(type(ref) is int and ref>0);refs.append(ref)
            _need(_eq(power,dict(powerRef=ref,type=kind,amount=amount)))
        _need(len(set(refs))==len(refs) and refs[:len(previous)]==previous);previous=refs
        _need(_eq(row,dict(label=label,round=turn,turn=turn,hp=hp,block=0,energy=energy,enemyHp=[enemyhp]*3,count=batches,powers=rows)))
    damage=[]
    player_hits=[h for h in r['damageHistory'] if h['playerTarget'] is True]
    pid=player_hits[0]['target'] if player_hits else None
    if pid is not None:_need(type(pid) is int and pid not in ids)
    def native_hit(index):
        if losses[index]:
            _need(pid is not None)
            damage.append(dict(target=pid,playerTarget=True,hpLost=losses[index],blocked=0,props=8,cardRef=None))
    def lightning(n):
        damage.extend(dict(target=e,playerTarget=False,hpLost=n,blocked=0,props=4,cardRef=None) for e in ids)
    native_hit(0)
    bases=oracle['first_engage_bases']+oracle['end_turn_bases'] if pool else []
    if pool:
        lightning(4);lightning(6)
    if not lingering:native_hit(1)
    if pool:
        lightning(4);lightning(6);native_hit(2)
    _need(_eq(r['damageHistory'],damage) and len(r['batches'])==len(bases))
    batch_ids=[]
    for i,(row,n) in enumerate(zip(r['batches'],bases),1):
        identity=row['id'];_need(type(identity) is int and identity>0);batch_ids.append(identity)
        _need(_eq(row,dict(id=identity,round=1,turn=1,count=i,baseDamage=n,storm=0,amount=n,cardRef=None,targets=ids,
                           hits=[dict(target=e,hpLost=n,blocked=0) for e in ids])))
    _need(batch_ids==sorted(set(batch_ids)))
    if lingering:
        _need(_eq(r['status'],dict(cardRef='direct-status',pile='Hand',inHand=oracle['status_remains_in_hand'],inExhaust=oracle['status_purified'])))
        _need(_eq(r['drawHistory'],[dict(cardRef='direct-status',fromHandDraw=False)]))
        _need(_eq(r['drawResponses'],[dict(cardRef='direct-status',fromHandDraw=False,domain=0,energy=2,pile='Hand')]))
    elif pool:
        _need(r['status'] is None and len(r['drawHistory'])==5 and len({d['cardRef'] for d in r['drawHistory']})==5)
        for d in r['drawHistory']:_need(type(d['cardRef']) is str and d['cardRef'].startswith('starting-') and _eq(d,dict(cardRef=d['cardRef'],fromHandDraw=True)))
        _need(_eq(r['drawResponses'],[dict(d,domain=0,energy=3,pile='Hand') for d in r['drawHistory']]))
    else:_need(r['status'] is None and _eq(r['drawHistory'],[]) and _eq(r['drawResponses'],[]))
    return True


def _special(r,token,case):
    nested=case=='PP-U25-live-finish-count'
    oracle=next(c['expected'] for c in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases'] if c['id']==case)
    fixed=dict(token=token,scenario='persistent-contract',variant=case,completed=True,schema='special-v1',gameVersion='v0.107.1',gameCommit='59260271',
               testMode=False,character='VolibearCharacter',acceptance='native-nested-autoplay-not-payment' if nested else 'native-action-queue-not-mouse')
    fields='enemyIds enemyTypes removedRelics eliminated special beforeEffects playHistory drawHistory energyHistory damageHistory'.split()
    _need(set(r)==set(fixed)|set(fields) and all(_eq(r[k],v) for k,v in fixed.items()))
    ids=r['enemyIds'];types=r['enemyTypes'];d=r['special']
    _need(type(ids) is list and len(ids)==3 and len(set(ids))==3 and all(type(i) is int and i>=0 for i in ids))
    _need(len(types)==3 and types.count('LeafSlimeS')==1 and types.count('TwigSlimeS')==1 and sum(t in ('LeafSlimeM','TwigSlimeM') for t in types)==1)
    _need(_eq(r['removedRelics'],['HuntersHeart']))
    def hit(e,n,card,player=False):return dict(target=e,playerTarget=player,hpLost=n,blocked=0,props=8,cardRef=card)
    def snapshot(row,hp,energy,enemyhp,count,powers):
        refs=[];_need(len(row['powers'])==len(powers))
        for p,(kind,n) in zip(row['powers'],powers):
            ref=p['powerRef'];_need(type(ref) is int and ref>0);refs.append(ref)
            _need(_eq(p,dict(powerRef=ref,type=kind,amount=n)))
        _need(len(refs)==len(set(refs)))
        _need(_eq(row,dict(round=1,turn=1,hp=hp,block=0,energy=energy,enemyHp=enemyhp,powers=row['powers'],targetCount=count,lightning=0)))
        return refs
    def pre(names):
        _need(len(r['beforeEffects'])==len(names));playids=[]
        for i,(row,name) in enumerate(zip(r['beforeEffects'],names),1):
            identity=row['playId'];_need(type(identity) is int and identity>0);playids.append(identity)
            _need(_eq(row,dict(cardRef=name,index=0,count=1,playId=identity,ordinal=i,strength=0,storm=0)))
        _need(len(playids)==len(set(playids)))
        return playids
    if nested:
        _need(set(d)==set('before after allowanceBefore allowanceAfter finishes cards'.split()))
        _need(_eq(r['eliminated'],[dict(enemy=e,hp=0,dead=True,stillHittable=False) for e in ids[1:]]))
        powers=[('PreyStillStandsPower',1),('HellraiserPower',1)]
        refs=snapshot(d['before'],80,3,[100,0,0],0,powers)
        _need(snapshot(d['after'],80,3,[79,0,0],3,powers)==refs)
        state=dict(powerRef=refs[0],usedRound=-1,usedTurn=-1)
        _need(_eq(d['allowanceBefore'],state) and _eq(d['allowanceAfter'],state))
        playids=pre(['first','outer','inner'])
        _need(_eq(d['finishes'],[
            dict(cardRef='first',playId=playids[0],capturedTargetOrdinal=1,liveTargetCount=1,actualCompleted=True),
            dict(cardRef='inner',playId=playids[2],capturedTargetOrdinal=3,liveTargetCount=oracle['target_count_at_both_finishes'],actualCompleted=True),
            dict(cardRef='outer',playId=playids[1],capturedTargetOrdinal=2,liveTargetCount=oracle['target_count_at_both_finishes'],actualCompleted=True)]))
        _need(_eq(d['cards'],[dict(cardRef=name,type=kind,cost=1,pile='Discard',isStrike=strike) for name,kind,strike in
                              [('first','Volibear_B01',False),('outer','PommelStrike',True),('inner','StrikeIronclad',True)]]))
        _need(_eq(r['playHistory'],[dict(cardRef=name,index=0,count=1,autoPlay=True,spent=0) for name in ['first','outer','inner']]))
        _need(_eq(r['drawHistory'],[dict(cardRef='inner',fromHandDraw=False)]) and _eq(r['energyHistory'],[]))
        _need(_eq(r['damageHistory'],[hit(ids[0],n,name) for n,name in [(6,'first'),(9,'outer'),(6,'inner')]]))
    else:
        _need(set(d)==set('initialMove receipt before after beforeInvalid afterInvalid afterValid actions paymentEvents paymentBeforeEffects'.split()))
        _need(_eq(r['eliminated'],[]) and _eq(r['drawHistory'],[]))
        amounts={'LeafSlimeS':{'TACKLE_MOVE':3,'GOOP_MOVE':0},'TwigSlimeS':{'TACKLE_MOVE':4},
                 'LeafSlimeM':{'CLUMP_SHOT':8,'STICKY_SHOT':0},'TwigSlimeM':{'POKEY_POUNCE_MOVE':11,'STICKY_SHOT_MOVE':0}}
        loss=amounts[types[0]][d['initialMove']]
        _need(_eq(d['receipt'],dict(performed=True,completed=True,absorbed=0)))
        beforepowers=[('WelcomeThunderPower',1),('WelcomeThunderPower',2),('NextAttackDiscount',oracle['pending_discount'])]
        refs=snapshot(d['before'],80-loss,3,[100,100,100],0,beforepowers)
        _need(snapshot(d['after'],80-loss,2,[68,100,100],1,beforepowers[:2])==refs[:2])
        unpaid=dict(energy=3,coupon=2,canonicalCost=3,cost=1,pile='Hand',hp=100,paymentEvents=0)
        _need(_eq(d['beforeInvalid'],unpaid) and _eq(d['afterInvalid'],unpaid))
        _need(_eq(d['afterValid'],dict(energy=2,coupon=0,canonicalCost=3,cost=3,pile='Discard',hp=68,paymentEvents=1)))
        _need(_eq(d['paymentEvents'],[dict(cardRef='paid',amount=oracle['paid_energy'],energy=2,coupon=2)]))
        _need(_eq(d['paymentBeforeEffects'],[dict(cardRef='paid',energy=2,coupon=0,spent=1,autoPlay=False)]))
        pre(['paid'])
        _need(_eq(r['playHistory'],[dict(cardRef='paid',index=0,count=1,autoPlay=False,spent=1)]) and _eq(r['energyHistory'],[1]))
        _need(len(d['actions'])==2)
        actionids=[];pid=d['actions'][0]['target'];_need(type(pid) is int and pid not in ids)
        for i,a in enumerate(d['actions']):
            identity=a['id'];_need(type(identity) is int and identity>=0);actionids.append(identity)
            events=[dict(label='before-executed',state='Executing',id=identity,energy=3,coupon=2,pile='Hand')]
            if i==0:events.append(dict(label='cancelled',state='Canceled',id=identity,energy=3,coupon=2,pile='Hand'))
            events.append(dict(label='after-finished',state='Finished',id=identity,energy=3 if i==0 else 2,coupon=2 if i==0 else 0,pile='Hand' if i==0 else 'Discard'))
            _need(_eq(a,dict(role='invalid-self-target' if i==0 else 'valid-enemy-target',id=identity,target=pid if i==0 else ids[0],
                             state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',sameCard=True,
                             context=None if i==0 else 'GameActionPlayerChoiceContext',events=events)))
        _need(actionids[1]>actionids[0])
        damage=([hit(pid,loss,None,True)] if loss else [])+[hit(ids[0],32,'paid')]
        _need(_eq(r['damageHistory'],damage))
    return True
