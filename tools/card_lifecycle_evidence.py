"""Finite paid/lifecycle oracle, from CARDS.md and TEST_SPEC §7/P, not C# values.
48 cases complement (do not replace) selection, normal UI, full G2/G3 and enemy matrices.
"""
import json
import math
from collections import Counter
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')
try:
    from .card_face_evidence import validate_starter_setup
except ImportError:
    from card_face_evidence import validate_starter_setup

CODES = ('U02','U04','U19','U21','U25','U26','U32','U34','R16','R18',
         'U07','U08','U20','C17','U13','U26-extra','U29','R01','R14','R06','U03','R02','R28','R30')
CASES = tuple(code + '-' + grade for code in CODES for grade in ('base','upgraded'))
PREFIX = '[Volibear] CARD_LIFECYCLE_RESULT '
BATCH_PREFIX = '[Volibear] CARD_LIFECYCLE_BATCH_RESULT '
ACCEPTANCE = 'paid-native-queue-controlled-first-instance-and-room-lifecycle-not-OS-input'
# Actual existing entrypoints, not claims that every listed branch already ran.
EXISTING = {
    'U03-extra-turn': ('standing-extra-turn', 'U03-base-extra-turn', 'U03-upgraded-extra-turn', 'tools/standing_extra_turn_evidence.py'),
    'U12-snapshot-extra-turn': ('primal-contract', 'U12-paid-snapshot', 'U12-native-extra-turn', 'tools/primal_evidence.py'),
    'U08-same-play-replay': ('prepared-contract', 'PR-replay-paid', 'tools/prepared_evidence.py'),
    'R02-native-absorption': ('persistent-contract', 'PP-R02-no-consumption', 'PP-R02-unpowered', 'tools/persistent_evidence.py'),
    'R06-training-replay': ('prepared-contract', 'PR-training-dynamic-spells', 'PR-training-native-domain', 'tools/prepared_evidence.py'),
}
# Explicit 17 native Power cards; R06 is deliberately included separately as a persistent Skill.
POWER_CARDS = ('U02','U03','U04','U19','U21','U25','U26','U29','U32','U34','R01','R02','R14','R16','R18','R28','R30')
POWER_TYPES = {
    'U02':'StormConductionPower','U03':'StandingPower','U04':'BattleScarsPower','U19':'LingeringStormPower',
    'U21':'ThunderAftershockPower','U25':'PreyStillStandsPower','U26':'GrowingFuryPower','U26-extra':'GrowingFuryPower',
    'U29':'StormChargePower','U32':'WelcomeThunderPower','U34':'ThunderArmorPower','R01':'DomainPower',
    'R02':'ImmovableBodyPower','R14':'EndlessHuntPower','R16':'BattleBodyPower','R18':'ThunderPoolPower',
    'R28':'BearSpiritPower','R30':'WildernessPower','R06':'UnifyPower',
}
INSTANCED = {'U02','U04','U19','U21','U25','U26','U26-extra','U32','U34','R18','R28','R30'}


def need(value, label):
    if not value: raise ValueError('Lifecycle evidence: ' + label)


def same(actual, expected, label):
    if type(expected) is dict:
        need(type(actual) is dict and actual.keys() == expected.keys(), label)
        for k, v in expected.items(): same(actual[k], v, label + '.' + k)
    elif type(expected) is list:
        need(type(actual) is list and len(actual) == len(expected), label)
        for i, v in enumerate(expected): same(actual[i], v, label + '[' + str(i) + ']')
    elif type(expected) in (int, float):
        need(type(actual) in (int, float) and math.isfinite(actual) and actual == expected, label)
    else:
        need(type(actual) is type(expected) and actual == expected, label)


def plan(case):
    """Literal finite input sequence, independently authored; never reads game output."""
    need(case in CASES, 'unsupported case')
    code, grade = case.rsplit('-', 1); up = grade == 'upgraded'; rows = []
    def add(label, card, target=-1, upgraded=False, replay=0, phase='same'):
        rows.append(dict(label=label, code=card, target=target, upgraded=upgraded, replay=replay, phase=phase))
    def events(prefix, phase):
        def a(suffix, card, target=-1): add(prefix+'-'+suffix,card,target,phase=phase)
        if code in ('R28','R30'):
            a('first','T01',0); a('second','T01',0)
            if code == 'R30': a('body-one','T02'); a('body-two','T02')
        elif code == 'R14':
            for suffix,card,target in (('first','B01',0),('second','B01',0),('other','B01',1),('accumulated','U07',0),('untouched','U07',2)): a(suffix,card,target)
        elif code == 'R06': a('first','B01',0); a('second','C24')
        elif code == 'U32':
            if phase == 'same': a('initial-coupon','U07',2)
            for suffix,card,target in (('first','B04',0),('coupon','U07',1),('second','B04',1),('spent','U07',2)): a(suffix,card,target)
        else:
            trigger = 'B04' if code in ('U04','U19','R18','U03','R02') else 'C24' if code in ('U21','U34','U29') else 'B01'
            a('first',trigger,-1 if trigger=='C24' else 0)
            a('second','B04' if code=='R16' else trigger,-1 if trigger=='C24' else 1 if trigger=='B04' else 0)
            if code in ('U25','U26','U26-extra'): a('third','B01',1); a('fourth','B01',1)
    if code in POWER_TYPES:
        if code == 'U21': add('prior-lightning-one','C24'); add('prior-lightning-two','C24')
        add('paid-second-deployment', 'U26' if code=='U26-extra' else code, upgraded=up)
        events('same-turn','same'); events('next-turn','next')
    elif code == 'U07':
        add('history-replayed-attack-counts-once','B01',0,replay=1)
        add('history-same-target','U07',0,up); add('history-other-target','U07',1,up); add('history-return-target','U07',0,up)
        add('history-next-turn-reset','U07',0,up,phase='next')
    elif code == 'U08':
        for label,target in (('bite-blocked-first',0),('bite-other-target',1),('bite-marked-target',0)): add(label,'U08',target,up)
        add('bite-next-turn-marked','U08',0,up,phase='next'); add('bite-new-instance-unmarked','U08',3,up,phase='next')
    elif code == 'U20':
        add('previous-skill','B02'); add('previous-skill-replay','U20',0,up,1); add('previous-attack-replay','U20',1,up,1)
        add('previous-attack-across-turn','U20',0,up,phase='next'); add('previous-skill-again','B02',phase='next'); add('previous-skill-no-refund','U20',1,up,phase='next')
    else:
        add('temporary-first','C17',upgraded=up)
        if code=='U13': add('convert-temporary','U13',upgraded=up); add('temporary-second','C17',upgraded=up)
        add('temporary-attack','B01',0); add('temporary-next-turn','B01',0,phase='next')
    for label,card,target in (('first','B01',0),('second','B01',0),('lightning','C24',-1),('engage','B04',1),('no-coupon','U07',2)):
        add('new-combat-'+label,card,target,phase='fresh')
    if code in ('R28','R30'): add('new-combat-claw','T01',0,phase='fresh'); add('new-combat-body','T02',phase='fresh')
    return rows


def _power_rows(snapshot, power):
    rows = snapshot['powers']; need(type(rows) is list, 'power rows')
    need(len({p['powerRef'] for p in rows}) == len(rows), 'duplicate native power identity')
    return [p for p in rows if p['type'] == power]


def validate(raw, token, case):
    code, grade = case.rsplit('-',1); up = grade=='upgraded'; specs = plan(case)
    for key, expected in dict(schema=1,token=token,scenario='card-lifecycle',variant=case,code=code,upgraded=up,completed=True,
                              version=EXPECTED_GAME_VERSION,commit=EXPECTED_GAME_COMMIT,testMode=False,acceptance=ACCEPTANCE).items(): same(raw[key],expected,key)
    need(type(raw['runRef']) is str and raw['runRef'].startswith('run-'), 'actual batch run identity')
    original = raw['original']; same(original['round'],1,'fresh round'); same(original['turn'],1,'fresh turn')
    same(original['hp'],80,'fresh native player'); same(original['block'],0,'fresh native block'); same(original['powers'],[],'fresh native powers')
    same(len(original['enemies']),3,'native three slimes'); same(original['lightning'],0,'fresh lightning clock')
    need(raw['playerRef'] != raw['ownerRef'] and raw['ownerRef'] != 'null', 'player/creature identity')
    fixture_rows = raw['fixtures']; labels = [f['label'] for f in fixture_rows]
    need(labels.count('native-created-card-and-HP-energy-isolation')==1 and labels.count('native-second-combat-isolation-no-power-reset')==1 and labels.count('native-next-turn-energy-and-negative-modifier-isolation')==1, 'explicit native setup boundaries')
    for fixture in fixture_rows:
        need(type(fixture) is dict and set(fixture)==set('label before after history batches starterSetup'.split()), 'fixture fields')
        if fixture['label']=='native-created-card-and-HP-energy-isolation':
            setup=fixture['starterSetup'];validate_starter_setup(setup)
            moved=[row['cardRef'] for row in setup['moved']]
            same(moved,original['hand'],'starter setup original hand order')
            same(moved,fixture['before']['hand'],'starter setup before hand order')
            for snapshot in (original,fixture['before']):
                same([{'cardRef':row['cardRef'],'type':row['type']} for row in snapshot['handCards']],setup['moved'],'starter setup hand types')
            same(fixture['after']['hand'],[],'starter setup empty hand')
        else:
            same(fixture['starterSetup'],None,'nonstarter setup not bulk')
    ability = code in POWER_TYPES
    same(labels.count('first-instance-native-PowerCmd-not-paid-card'), int(ability), 'first instance disclosure')
    expected_amount = {'U02':4 if up else 3,'U03':3 if up else 6,'U04':2 if up else 1,'U19':1,'U21':1,'U25':2 if up else 1,
                       'U26':2 if up else 1,'U26-extra':2 if up else 1,'U29':3 if up else 2,'U32':2 if up else 1,'U34':4 if up else 3,
                       'R02':1,'R14':1,'R16':1,'R18':6 if up else 4,'R28':2 if up else 1,'R30':9 if up else 6,'R06':3}.get(code)
    first_power_ids = []
    if ability:
        setup = next(f for f in fixture_rows if f['label']=='first-instance-native-PowerCmd-not-paid-card')
        same(setup['history']['plays'],[],'native fixture is NOT a paid card')
        powers = _power_rows(setup['after'],POWER_TYPES[code]); same(len(powers),1,'one native earlier deployment')
        first_power_ids = [powers[0]['powerRef']]
        if code != 'R01': same(powers[0]['amount'],expected_amount,'first configured amount')
        else: same(setup['after']['permanent'],True,'native permanent domain fixture')
    same([a['label'] for a in raw['actions']],[s['label'] for s in specs],'complete ordered paid actions')
    need(len({a['cardRef'] for a in raw['actions']})==len(specs), 'distinct actual created card identities')
    strength=dex=storm=temporary=0; domain=0; permanent=False; lightning=0
    if code=='U29': storm=2*(3 if up else 2)
    # First fixture modifies no ordinary strength; these aggregates are set at the paid deployment below.
    target_counts=Counter(); phase=None; attack_number=0; engaged=0; beast_plays=0; previous_attack=False; coupon=0
    player_ref=raw['ownerRef']; power_ids=[]
    for actual,spec in zip(raw['actions'],specs):
        label=spec['label']; card=spec['code']; phase_now=spec['phase']; repeat=spec['replay']+1; before=actual['before']; after=actual['after']
        if phase_now != phase:
            target_counts=Counter(); attack_number=engaged=beast_plays=0; lightning=0
            if phase_now=='next':
                if code=='U26-extra': strength+=2*(2 if up else 1); storm+=2*(2 if up else 1)
                if code=='U19': domain=4
                elif code=='U32': domain=0
                if code=='C17': strength=temporary=0
                if code=='U13': strength=(6 if up else 4)+(3 if up else 2); temporary=0
                coupon=0
            elif phase_now=='fresh': strength=dex=storm=temporary=domain=0; permanent=False; coupon=0; previous_attack=False
            phase=phase_now
        fresh=phase_now=='fresh'; deployment=label=='paid-second-deployment'
        for key in ('label','code','upgraded','replay'): same(actual[key],spec[key],label+'.'+key)
        same(actual['action']['type'],'PlayCardAction',label+'.native action')
        same(actual['action']['state'],'Finished',label+'.finished')
        same(actual['action']['sameCard'],True,label+'.native card identity')
        same(actual['action']['events'],['before-executed','after-finished'],label+'.not cancelled')
        need(actual['cardRef'] in before['hand'] and actual['cardRef'] not in after['hand'], label+'.actual hand-to-native-destination')
        target_ids=[e['enemyRef'] for e in before['enemies']]
        target=target_ids[spec['target']] if spec['target']>=0 else 'null'
        same(actual['targetRef'],target,label+'.actual target')
        is_attack=card in ('B01','B04','U07','U08','U20','T01')
        cost=0 if card=='C17' else 3 if card=='U07' else 2 if card in ('U19','R18','R06','R02','R30') else (1 if up else 2) if card=='U32' else (2 if up else 3) if card=='R01' else (0 if up else 1) if card=='U21' else 1
        if card=='U07': cost=max(0,3-target_counts[target])
        if not fresh and code=='R14' and is_attack: cost=max(0,cost-2*target_counts[target])
        if is_attack and coupon: cost=max(0,cost-coupon); coupon=0
        if card=='U07':
            wanted=[max(0,3-target_counts[t]-(2*target_counts[t] if not fresh and code=='R14' else 0)) for t in target_ids]
            # Preview is taken before payment consumes the ordinary next-attack coupon.
            old_coupon=(2 if up else 1) if not fresh and code=='U32' and label.endswith(('initial-coupon','-coupon')) else 0
            wanted=[max(0,n-old_coupon) for n in wanted]
            same(actual['previews'],[dict(targetRef=t,cost=n) for t,n in zip(target_ids,wanted)],label+'.same-card target preview')
        same(actual['payments'],[dict(cardRef=actual['cardRef'],amount=cost,energy=before['energy']-cost)],label+'.one real payment')
        same(actual['history']['plays'],[dict(cardRef=actual['cardRef'],index=i,count=repeat,autoPlay=False,spent=cost) for i in range(repeat)],label+'.real actual play/replay')
        same(actual['history']['finished'],[dict(cardRef=actual['cardRef'],index=i,autoPlay=False) for i in range(repeat)],label+'.native complete')
        same(len(actual['effects']),repeat,label+'.before-effect observations')
        for i,effect in enumerate(actual['effects']):
            for k,v in dict(cardRef=actual['cardRef'],index=i,count=repeat,autoPlay=False,spent=cost).items(): same(effect[k],v,label+'.effect.'+k)
        bases=[]; refund=0; draw=0; block_gain=0; ordinary=[]
        if deployment:
            if code in ('U02','R18'): bases=[9 if up else 6]
            if code=='U03': block_gain=12 if up else 8
            if code=='U04': block_gain=9 if up else 6
            if code=='U19': domain=1; draw=2 if up else 1
            if code=='U21': lightning=2; refund=1
            if code=='U25': draw=1
            if code in ('U26','U26-extra'): strength=1
            if code=='U29': storm=2*(3 if up else 2)
            if code=='U32': domain=1; coupon=2 if up else 1
            if code=='U34': block_gain=7 if up else 4
            if code=='R01': permanent=True; domain=before['domain']; block_gain=14 if up else 10
            if code=='R02': block_gain=15 if up else 10
            if code=='R14': draw=int(up)
            if code=='R16': block_gain=8 if up else 0
            if code=='R06': strength=4 if up else 3; block_gain=14 if up else 10
            powers=_power_rows(after,POWER_TYPES[code]); same(len(powers),2 if code in INSTANCED else 1,label+'.native stack/instance policy')
            power_ids=[p['powerRef'] for p in powers]; need(set(first_power_ids)<=set(power_ids),'first native instance retained')
            if code!='R01':
                values=[expected_amount]*2 if code in INSTANCED else [expected_amount if code in ('U03','R02') else expected_amount*2]
                same([p['amount'] for p in powers],values,label+'.configured amounts')
        else:
            if is_attack:
                attack_number+=1
                if not fresh and code in ('U26','U26-extra') and attack_number==2:
                    strength+=2*(2 if up else 1); storm+=2*(2 if up else 1)
                if not fresh and code=='R28' and card in ('T01','T02') and beast_plays==0: storm+=2
                if card in ('T01','T02'): beast_plays+=1
                damage={'B01':6,'B04':6,'U07':36 if spec['upgraded'] else 28,'U08':14 if spec['upgraded'] else 10,'U20':14 if spec['upgraded'] else 10,'T01':7}[card]
                if card=='U08' and label in ('bite-marked-target','bite-next-turn-marked'): damage+=9 if up else 6
                if not fresh and code=='R06': damage+=6
                ordinary=[damage+strength]*(repeat*(2 if card=='T01' else 1))
                for effect in actual['effects']: same(effect['state']['strength'],strength,label+'.strength before original effect')
                if not fresh and code=='R28':
                    for effect in actual['effects']: same(effect['state']['storm'],storm,label+'.beast storm before original effect')
                if card=='B04': block_gain=8+dex
                if card=='U08': block_gain=(9 if spec['upgraded'] else 6)+dex
                if card=='U20' and previous_attack: refund=(3 if spec['upgraded'] else 2)*repeat
                if not fresh and code=='R30' and card=='T01' and beast_plays==1: block_gain+=2*(9 if up else 6)
                if not fresh and code=='U02': bases += [4 if up else 3]*2*len(ordinary)
                if domain>0: bases += [4]
                target_counts[target]+=1
                if not fresh and code=='U25' and target_counts[target]==2 and target==target_ids[0]: draw=2*(2 if up else 1)
                if card=='B04':
                    if engaged==0: draw+=1  # Native HuntersHeart first completion, not an ability deployment.
                    if not fresh and code=='U04' and engaged==0: strength+=2*(2 if up else 1); storm+=2
                    if not fresh and code=='U19': domain+=2; draw+=2
                    if not fresh and code=='U32' and engaged==0: coupon=2 if up else 1
                    if not fresh and code=='R18' and engaged==0: bases += [6 if up else 4]*2
                    engaged+=1
                if not fresh and code=='R16': strength+=2; dex+=2 if card=='B04' else 0
            elif card=='C24': bases=[6]; draw=1
            elif card=='T02':
                bases=[2]; block_gain=9+dex
                if not fresh and code=='R30': refund=2
            elif card=='B02': block_gain=5+dex
            elif card=='C17': strength+=6 if spec['upgraded'] else 4; temporary+=6 if spec['upgraded'] else 4
            elif card=='U13': strength+=3 if spec['upgraded'] else 2; temporary=0
            if not fresh and code=='U21' and card=='C24' and not label.startswith('prior-') and (lightning+1)%2==0: refund+=2
            if not fresh and code=='U34' and card=='C24': block_gain+=2*(4 if up else 3)
        if not deployment: previous_attack=is_attack
        else: previous_attack=False
        # Native callbacks receive an exact per-batch amount, not an aggregate per target.
        thunder_bonus = 6 if not fresh and code=='R06' and card=='C24' else 0
        same(len(actual['batches']),len(bases),label+'.lightning batch multiplicity')
        for batch,base in zip(actual['batches'],bases):
            lightning+=1
            for k,v in dict(baseDamage=base,storm=storm,amount=base+storm+thunder_bonus,count=lightning,targets=target_ids,combatRef=before['combatRef'],round=before['round'],turn=before['turn']).items(): same(batch[k],v,label+'.batch.'+k)
            same([h['targetRef'] for h in batch['hits']],target_ids,label+'.batch native hits')
            for hit in batch['hits']: same(hit['hpLost']+hit['blocked'],base+storm+thunder_bonus,label+'.native lightning applied')
        own=[h for h in actual['history']['damage'] if h['sourceRef']==player_ref]
        powered=[h for h in own if h['props'] & 8 and not h['props'] & 4]
        same([h['hpLost']+h['blocked'] for h in powered],ordinary,label+'.ordinary native damage')
        same([h['targetRef'] for h in powered],[target]*len(ordinary),label+'.ordinary native target')
        for hit in powered: same(hit['cardRef'],actual['cardRef'],label+'.actual damage card')
        if label=='bite-blocked-first': same([h['hpLost'] for h in powered],[0],label+'.truly fully blocked')
        raw_lightning=[(h['targetRef'],h['hpLost']+h['blocked']) for h in own if h['props'] & 4]
        same(Counter(raw_lightning),Counter((t,base+storm+thunder_bonus) for base in bases for t in target_ids),label+'.independent native lightning receipts')
        moves=actual['history']['moves']; same(len(moves),int(card=='B04'),label+'.actual engage move')
        if card=='B04': same(moves[0]['enemyRef'],target,label+'.actual engaged identity')
        same(len(actual['history']['draws']),draw,label+'.actual draws')
        need(all(not row['normal'] for row in actual['history']['draws']),label+'.response draws not normal start')
        if code=='U25':
            discounted = not fresh and label in ('same-turn-second','next-turn-second')
            for drawn in actual['history']['draws']:
                same(drawn['type'],'Volibear_B01',label+'.actual drawn attack')
                card_rows=[h for h in after['handCards'] if h['cardRef']==drawn['cardRef']]
                same(len(card_rows),1,label+'.drawn identity still in hand')
                same(card_rows[0]['cost'],0 if discounted else 1,label+'.actual response discount not ordinary draw')
        same(after['energy'],before['energy']-cost+refund,label+'.actual paid/refunded energy')
        absorbed=sum(h['blocked'] for h in actual['history']['damage'] if h['targetRef']==player_ref)
        same(after['block'],before['block']+block_gain-(0 if not fresh and code=='R02' else absorbed),label+'.block contribution/absorption')
        for k,v in dict(strength=strength,dexterity=dex,storm=storm,temporary=temporary,domain=domain,permanent=permanent,lightning=lightning).items(): same(after[k],v,label+'.after.'+k)
        if ability and not fresh and not label.startswith('prior-'):
            same([p['powerRef'] for p in _power_rows(after,POWER_TYPES[code])],power_ids,label+'.same deployed instances')
        if fresh: need(not any(p['type'] in POWER_TYPES.values() for p in after['powers']),'no prior ability in new combat')
        expected_pile='Exhaust' if card in ('U20','R06','T01','T02') else 'None' if deployment else 'Discard'
        same(actual['pile'],expected_pile,label+'.native destination')
        same(actual['history']['exhausts'],[actual['cardRef']] if expected_pile=='Exhaust' else [],label+'.native single removal')
    transitions=raw['transitions']; wanted=['native-normal-next-player-turn']
    if code=='U26-extra': wanted+=['native-PaelsEye-extra-player-turn']
    if code=='U13': wanted+=['native-second-recovery-must-not-repeat']
    same([t['label'] for t in transitions],wanted,'complete native lifecycle boundaries')
    for t in transitions:
        b,a=t['before'],t['after']; extra=t['label']=='native-PaelsEye-extra-player-turn'
        same(a['turn'],b['turn']+1,'native player turn progression'); same(a['round'],b['round']+(0 if extra else 1),'native round/extra distinction')
        same(a['side'],'Player','next native side'); same(a['phase'],'Play','next native phase'); same(a['lightning'],0,'native lightning reset')
        same(len(t['extraTurns']),int(extra),'real native extra callback')
        if extra: same(t['history']['moves'],[],'extra turn cannot fabricate enemy phase')
        else: need(len(t['history']['moves'])>=1,'unconsumed native enemies continue acting')
        if code=='U26-extra':
            s=2 if up else 1
            if not extra:
                auto=t['history']['plays']; same(len(auto),2,'actual native Mayhem two-card phase')
                need(len({row['cardRef'] for row in auto})==2,'two distinct original Mayhem cards')
                for row in auto:
                    same(row['autoPlay'],True,'Mayhem explicitly not paid inputs'); same(row['spent'],0,'native Mayhem no payment'); same(row['count'],1,'Mayhem no invented replay')
                damage=[d for d in t['history']['damage'] if d['sourceRef']==player_ref]
                same([d['hpLost']+d['blocked'] for d in damage],[7+2*s,7+4*s],'native turn2 Mayhem consumes second-attack response')
                same(a['strength'],1+4*s,'actual response consumed in earlier turn of same round'); same(a['storm'],4*s,'earlier same-round storm')
            else:
                same(t['history']['plays'],[],'removed Mayhem cannot consume extra-turn paid opportunity')
                same(a['strength'],1+4*s,'extra turn itself adds no phantom strength'); same(a['storm'],4*s,'extra turn itself adds no phantom storm')
        for move in t['history']['moves']: need(move['enemyRef'] in {e['enemyRef'] for e in b['enemies']},'native enemy source')
        if code in ('C17','U13'):
            wanted_strength=0 if code=='C17' else (6 if up else 4)+(3 if up else 2)
            same(a['strength'],wanted_strength,'native temporary strength recovery/conversion'); same(a['temporary'],0,'no temporary debt survives')
        if code=='U03':
            absorbed=sum(h['blocked'] for h in t['history']['damage'] if h['targetRef']==player_ref)
            same(a['block'],max(0,b['block']-absorbed-(3 if up else 6)),'native standing next-turn decay')
            need(a['block']>0,'positive retention branch actually tested')
        else: same(a['block'],0,'native next-turn clear retained')
        if code=='R18':
            base=6 if up else 4; targets=[e['enemyRef'] for e in b['enemies']]
            same([batch['baseDamage'] for batch in t['batches']],[base]*2,'both native end-turn responders')
            same([batch['count'] for batch in t['batches']],[b['lightning']+1,b['lightning']+2],'actual end-turn batch counter')
            for batch in t['batches']:
                same(batch['targets'],targets,'end-turn native targets'); same(batch['amount'],base,'end-turn actual amount')
                same([h['hpLost']+h['blocked'] for h in batch['hits']],[base]*3,'end-turn actual hits')
            own=[d for d in t['history']['damage'] if d['sourceRef']==player_ref]
            same(Counter((d['targetRef'],d['hpLost']+d['blocked']) for d in own),Counter((target,base) for _ in range(2) for target in targets),'native independent end-turn damage history')
        else: same(t['batches'],[],'no phantom turn-end lightning')
    reentry=raw['reentry']; same(reentry['samePlayer'],True,'same-run room lifecycle'); same(reentry['combatChanged'],True,'new native combat instance')
    fresh=reentry['afterReentry']; need(fresh['combatRef']!=reentry['beforeExit']['combatRef'],'native different combat identity')
    for k,v in dict(round=1,turn=1,strength=0,dexterity=0,storm=0,domain=0,permanent=False,temporary=0,lightning=0,block=0,powers=[]).items(): same(fresh[k],v,'raw pre-fixture new combat.'+k)
    if code=='R28':
        same(len(raw['confirmations']),2,'two native optional start-turn decisions')
        same(raw['choiceSync'],[],'selector route does not claim network transport')
        for item in raw['confirmations']:
            same(item['api'],'CardSelectCmd.UseSelector','native automated selection interface')
            same(item['selection'],'optional-zero','explicit optional decision')
            same(item['min'],0,'optional minimum'); same(item['selected'],[],'zero choice')
            need(type(item['max']) is int and item['max']>0,'native maximum')
            need(type(item['options']) is list and len(item['options'])==len(set(item['options'])) and bool(item['options']),'distinct native options')
    else: same(raw['confirmations'],[],'no invented selection'); same(raw['choiceSync'],[],'no invented choice sync')
    same(raw['final'],raw['actions'][-1]['after'],'final is actual last paid boundary')
    need({e['enemyRef'] for e in original['enemies']}.isdisjoint(e['enemyRef'] for e in fresh['enemies']), 'new combat cannot reuse old enemy identities')
    return True


def _rows(log,prefix):
    return [json.loads(line.split(prefix,1)[1]) for line in log.splitlines() if prefix in line]


def card_lifecycle_evidence(log,token,case):
    try:
        rows=_rows(log,PREFIX); selected=[r for r in rows if r.get('variant')==case]
        need(len(selected)==1,'missing/duplicate requested case'); validate(selected[0],token,case)
        return selected[0],True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as error: return {'error':str(error)},False


def card_lifecycle_batch_evidence(log,token,cases=CASES):
    try:
        requested=list(cases); need(requested and len(set(requested))==len(requested) and all(c in CASES for c in requested),'finite requested cases')
        finals=_rows(log,BATCH_PREFIX); need(len(finals)==1,'missing/duplicate final batch ledger'); final=finals[0]
        for k,v in dict(schema=1,token=token,scenario='card-lifecycle',requested=requested,completed=requested,finished=True).items(): same(final[k],v,'batch.'+k)
        rows=_rows(log,PREFIX); same([r['variant'] for r in rows],requested,'no missing/extra/duplicate per-case evidence')
        runs=final['runRefs']; need(len(runs)==len(requested) and len(set(runs))==len(runs),'one actual fresh run per case')
        same([r['runRef'] for r in rows],runs,'case/native run correspondence')
        same(len(final['exits']),len(requested),'native cleanup after every case')
        for row,variant,run,exit in zip(rows,requested,runs,final['exits']):
            validate(row,token,variant)
            same(exit,dict(variant=variant,runRef=run,receipt=dict(RunNull=True,CombatNull=True,InProgress=False,QueueEmpty=True,ActionNull=True,HistoryVisible=0)),'native clean exit receipt')
        return final,True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as error: return {'error':str(error)},False
