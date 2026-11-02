"""G2 native receipt oracle. Numbers transcribed from CARDS.md, not C# metadata.

This finite suite is NOT the complete G2 gate. release_coverage always retains all
178 faces and separately reports the unimplemented section-7 branch obligations.
Synthetic records in the unit tests test this validator, not native gameplay.
"""
from collections import Counter
from copy import deepcopy
import json
from itertools import product
from math import isfinite

PREFIX = '[Volibear] CARD_FACE_RESULT '
ACCEPTANCE = 'controlled-native-queue-selector-no-input'
REFERENCE = 'reference/bear-forge/docs/volibear/CARDS.md'
ALL_IDS = tuple('B01 B02 B03 B04 C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 C13 C14 C15 C17 C18 C19 C20 C21 C22 C24 C25 C26 U02 U03 U04 U05 U06 U07 U08 U10 U11 U12 U13 U14 U15 U17 U19 U20 U21 U23 U24 U25 U26 U27 U28 U29 U31 U32 U34 U35 U36 U37 U38 U39 U40 U41 U42 U43 R01 R02 R05 R06 R07 R08 R09 R10 R12 R13 R14 R16 R17 R18 R21 R23 R24 R25 R27 R28 R29 R30 R31 T01 T02'.split())
IMPLEMENTED_IDS = tuple('B01 B02 B03 C01 C02 C03 C08 C09 C12 C13 C20 C22 C24 C26 U05 U06 U07 U13 U15 U20 U23 U24 U27 U31 U36 U38 U40 R05 R07 R12 R17 R21 R23 R24 T01 T02 C05 C14 C17 C18 C21 C25 U02 U03 U04 U10 U11 U12 U14 U19 U21 U25 U26 U29 U32 U34 U37 R01 R02 R06 R13 R14 R16 R18 B04 C04 C06 C10 C11 U08 U28 U35 R31 C07 C15 C19 U39 U41 U42 U43 R10 R25 R27 R28 R29 R30 U17 R08 R09'.split())
ALL_FACES = tuple(f'{c}-{f}' for c in ALL_IDS for f in ('base', 'upgrade'))


def branches(card):
    return ({
        'B01': ('plain','strength','weak','vulnerable','blocked','lethal','replay'),
        'B02': ('plain','dexterity','frail'),
        'B03': ('plain','lethal'), 'C02': ('plain','lethal','domain','conduction'), 'U06': ('plain','lethal','domain','conduction'),
        'C09': ('plain','domain','conduction'), 'C22': ('plain','domain','conduction'),
        'T01': ('plain','converted','master','domain'), 'T02': ('plain','converted','master'),
        'C12': ('plain','strength','negative-strength','dexterity','frail'),
        'C13': ('plain','material'), 'U15': ('plain','material'),
        **{c: ('plain','second-instance') for c in ('U02','U29','U34')},
        'U21': ('plain','prior1','prior2','prior5','second-instance'),
        'U05': ('plain','zero-block','strength'), 'R05': ('plain','zero-block','dexterity','frail'),
        'R07': ('plain','zero-block','charge'), 'U24': ('plain','blocked','injured','overkill'),
        'R31': ('plain','blocked'), 'U12': ('plain','strength','negative-strength'), 'U13': ('plain','strength','negative-strength'),
        'R13': ('plain','domain'), 'U37': ('plain','domain'), 'C24': ('plain','strength','weak','vulnerable'),
        'U31': ('x0','x1','x3','x0-replay','x1-replay','x3-replay'), 'R17': ('x0','x1','x3'),
        **{c: ('plain','prior1','prior2','prior5') for c in ('C26','U27','U36','U38','U40','R21','R24')},
        'R23': ('plain','blocked'),
        **{c: ('plain','empty','full-hand') for c in ('C07','C15')},
        **{c: ('plain','empty') for c in ('C19','U39','U41','U43','R29','R30')},
        'U42': ('plain','empty','status','curse'),
        **{c: ('plain','zero','empty','insufficient','full-hand') for c in ('R10','R25')},
        'R27': ('plain','zero','empty','insufficient'),
        'R28': ('plain','zero','empty'), 'U17': ('plain','zero','empty'), 'R12': ('plain','empty','full-hand'),
    }).get(card, ('plain',))


CARD_FACE_CASES = tuple(f'{c}-{f}-{b}' for c in IMPLEMENTED_IDS for f in ('base','upgrade') for b in branches(c))
# Fixed per-face values: cost, block, draw, ordinary hit, hit count, lightning,
# lightning batches, lightning all-targets. These are reference examples, not a
# runtime card interpreter: unsupported cards/branches cannot enter this table.
ROWS = {
    'B01': [(1,0,0,6,1,0,0,False),(1,0,0,9,1,0,0,False)],
    'B02': [(1,5,0,0,0,0,0,False),(1,8,0,0,0,0,0,False)],
    'B03': [(1,0,0,8,1,3,1,True),(1,0,0,11,1,5,1,True)],
    'C01': [(0,0,0,6,1,0,0,False),(0,0,0,9,1,0,0,False)],
    'C02': [(1,0,0,5,2,0,0,False),(1,0,0,7,2,0,0,False)],
    'C03': [(2,0,0,20,1,5,1,True),(2,0,0,26,1,7,1,True)],
    'C08': [(1,0,0,8,1,0,0,False),(1,0,0,10,1,0,0,False)],
    'C09': [(1,0,0,6,1,3,1,True),(1,0,0,8,1,4,1,True)],
    'C12': [(1,10,0,0,0,0,0,False),(1,13,0,0,0,0,0,False)],
    'C13': [(1,0,3,0,0,0,0,False),(1,0,4,0,0,0,0,False)],
    'C20': [(1,0,0,10,1,0,0,False),(1,0,0,14,1,0,0,False)],
    'C22': [(2,0,0,5,2,2,2,True),(2,0,0,7,2,3,2,True)],
    'C24': [(1,0,1,0,0,6,1,True),(1,0,1,0,0,9,1,True)],
    'C26': [(0,0,0,0,0,0,0,False)]*2,
    'U05': [(1,0,0,10,1,0,0,False),(0,0,0,10,1,0,0,False)],
    'U06': [(2,0,0,8,3,0,0,False),(2,0,0,11,3,0,0,False)],
    'U07': [(3,0,0,28,1,0,0,False),(3,0,0,36,1,0,0,False)],
    'U13': [(1,0,0,0,0,0,0,False)]*2,
    'U15': [(0,0,2,0,0,0,0,False),(0,0,3,0,0,0,0,False)],
    'U20': [(1,0,0,10,1,0,0,False),(1,0,0,14,1,0,0,False)],
    'U23': [(1,9,0,0,0,0,0,False),(1,12,0,0,0,0,0,False)],
    'U24': [(2,0,0,21,1,3,1,False),(2,0,0,28,1,3,1,False)],
    'U27': [(1,0,0,8,1,0,0,False),(1,0,0,11,1,0,0,False)],
    'U31': [(0,0,0,5,0,3,0,True),(0,0,0,7,0,3,0,True)],
    'U36': [(0,0,0,0,0,0,0,False)]*2,
    'U38': [(3,0,0,18,1,0,0,False),(3,0,0,24,1,0,0,False)],
    'U40': [(1,0,0,0,0,8,1,False),(1,0,0,0,0,12,1,False)],
    'R05': [(2,20,0,0,0,0,0,False),(1,20,0,0,0,0,0,False)],
    'R07': [(2,0,0,0,0,10,1,True),(1,0,0,0,0,10,1,True)],
    'R12': [(1,0,7,0,0,0,0,False),(1,0,9,0,0,0,0,False)],
    'R17': [(0,0,0,0,0,6,0,False)]*2,
    'R21': [(1,0,2,0,0,0,0,False)]*2,
    'R23': [(2,0,0,0,0,8,3,False),(2,0,0,0,0,11,3,False)],
    'R24': [(1,0,2,0,0,0,0,False),(1,0,3,0,0,0,0,False)],
    'T01': [(1,0,0,7,2,0,0,False),(1,0,0,11,2,0,0,False)],
    'T02': [(1,9,0,0,0,2,1,True),(1,12,0,0,0,3,1,True)],
}
# Deployment/entry expectations are still not the required multi-instance lifecycle tests.
ROWS.update({
    'C05': [(1,0,0,6,1,4,1,True),(1,0,0,9,1,4,1,True)],
    'C14': [(2,8,0,0,0,0,0,False),(2,11,0,0,0,0,0,False)],
    'C17': [(0,0,0,0,0,0,0,False)]*2,
    'C18': [(1,0,0,0,0,0,0,False)]*2,
    'C21': [(1,5,2,0,0,0,0,False),(1,8,2,0,0,0,0,False)],
    'C25': [(1,0,0,0,0,0,0,False)]*2,
    'U02': [(1,0,0,0,0,6,1,True),(1,0,0,0,0,9,1,True)],
    'U03': [(1,8,0,0,0,0,0,False),(1,12,0,0,0,0,0,False)],
    'U04': [(1,6,0,0,0,0,0,False),(1,9,0,0,0,0,0,False)],
    'U10': [(1,0,1,0,0,0,0,False),(1,0,2,0,0,0,0,False)],
    'U11': [(1,0,0,0,0,0,0,False),(0,0,0,0,0,0,0,False)],
    'U12': [(1,0,1,0,0,0,0,False),(1,0,2,0,0,0,0,False)],
    'U14': [(0,5,0,0,0,0,0,False),(0,8,0,0,0,0,0,False)],
    'U19': [(2,0,1,0,0,0,0,False),(2,0,2,0,0,0,0,False)],
    'U21': [(1,0,0,0,0,0,0,False),(0,0,0,0,0,0,0,False)],
    'U25': [(1,0,1,0,0,0,0,False)]*2,
    'U26': [(1,0,0,0,0,0,0,False)]*2,
    'U29': [(1,0,0,0,0,0,0,False)]*2,
    'U32': [(2,0,0,0,0,0,0,False),(1,0,0,0,0,0,0,False)],
    'U34': [(1,4,0,0,0,0,0,False),(1,7,0,0,0,0,0,False)],
    'U37': [(2,0,0,0,0,12,1,True),(2,0,0,0,0,16,1,True)],
    'R01': [(3,10,0,0,0,0,0,False),(2,14,0,0,0,0,0,False)],
    'R02': [(2,10,0,0,0,0,0,False),(2,15,0,0,0,0,0,False)],
    'R06': [(2,10,0,0,0,0,0,False),(2,14,0,0,0,0,0,False)],
    'R13': [(2,0,0,0,0,0,0,False)]*2,
    'R14': [(1,0,0,0,0,0,0,False),(1,0,1,0,0,0,0,False)],
    'R16': [(1,0,0,0,0,0,0,False),(1,8,0,0,0,0,0,False)],
    'R18': [(2,0,0,0,0,6,1,True),(2,0,0,0,0,9,1,True)],
})
ROWS.update({
    'B04':[(1,8,1,6,1,0,0,False),(1,11,1,9,1,0,0,False)],
    'C04':[(1,0,1,9,1,0,0,False),(1,0,1,12,1,0,0,False)],
    'C06':[(1,6,0,8,1,0,0,False),(1,8,0,11,1,0,0,False)],
    'C10':[(2,8,1,9,1,0,0,False),(2,11,1,12,1,0,0,False)],
    'C11':[(1,8,1,0,0,0,0,False),(1,11,1,0,0,0,0,False)],
    'U08':[(1,6,0,10,1,0,0,False),(1,9,0,14,1,0,0,False)],
    'U28':[(2,12,1,0,0,7,1,True),(2,17,1,0,0,9,1,True)],
    'U35':[(1,8,1,0,0,3,1,True),(1,11,1,0,0,5,1,True)],
    'R31':[(2,8,0,20,1,4,1,True),(2,12,0,28,1,4,1,True)],
})
ROWS.update({
    'C07':[(1,0,0,8,1,0,0,False),(1,0,0,11,1,0,0,False)],
    'C15':[(1,0,0,0,0,0,0,False),(0,0,0,0,0,0,0,False)],
    'C19':[(0,0,0,0,0,0,0,False)]*2,
    'U39':[(1,4,0,0,0,0,0,False),(1,7,0,0,0,0,0,False)],
    'U41':[(1,0,0,3,1,0,0,False),(1,0,0,6,1,0,0,False)],
    'U42':[(1,3,0,0,0,0,0,False),(1,6,0,0,0,0,0,False)],
    'U43':[(1,0,0,0,0,0,0,False),(0,0,0,0,0,0,0,False)],
    'R10':[(1,0,0,0,0,0,0,False)]*2,
    'R25':[(2,0,0,0,0,0,0,False),(1,0,0,0,0,0,0,False)],
    'R27':[(1,4,0,0,0,0,0,False)]*2,
    'R28':[(1,0,1,0,0,0,0,False),(1,0,2,0,0,0,0,False)],
    'R29':[(3,0,0,0,0,0,0,False),(2,0,0,0,0,0,0,False)],
    'R30':[(2,0,0,0,0,0,0,False)]*2,
})
ROWS.update({
    'U17':[(0,0,1,0,0,0,0,False)]*2,
    'R08':[(3,0,0,10,4,5,4,False),(3,0,0,13,4,8,4,False)],
    'R09':[(2,15,1,0,0,7,1,True),(2,21,1,0,0,7,1,True)],
})
SELECTION_IDS = set('C07 C15 C19 U39 U41 U42 U43 R10 R25 R27 R28 R30'.split())
BEAST_CARDS = set('U41 U42 U43 R27 R28 R29 R30'.split())


def selection_fixture(c,branch='plain'):
    """Fixed physical fixture entities: label/model/pile, not generated expectations."""
    if branch=='empty':return []
    if c=='U42' and branch in ('status','curse'):
        return [('selected','SLIMED' if branch=='status' else 'INJURY','Hand'),('alternate','INJURY' if branch=='status' else 'SLIMED','Hand')]
    if branch=='insufficient':return [('selected','B02' if c=='R25' else 'B01','Discard' if c=='R10' else 'Draw' if c=='R25' else 'Hand')]
    if c=='C07': return [('selected','B01','Draw'),('alternate','B01','Draw')]
    if c=='C15': return [('selected','B01','Discard'),('alternate','R07','Discard')]
    if c=='U39': return [('selected','R07','Draw'),('alternate','R23','Draw')]
    if c=='U43': return [('selected','B01','Draw'),('alternate','B02','Hand'),('third','B02','Draw')]
    if c=='R10': return [(x,'B01','Discard') for x in ('selected','alternate','third','fourth','fifth')]
    if c=='R25': return [('selected','B02','Draw'),('alternate','B02','Draw')]
    if c=='R27': return [('selected','B01','Hand'),('alternate','B02','Hand'),('third','B01','Hand'),('fourth','B02','Hand')]
    if c in SELECTION_IDS or c=='R29':
        return [('selected','B02' if c=='U42' else 'B01','Hand'),('alternate','B01' if c in ('C19','U41') else 'B02','Hand')]
    return []


def beast_materials(c,up,branch):
    """Independent fixed fixture selections, before exhaust/generation responses."""
    if c not in BEAST_CARDS or branch in ('empty','zero'): return []
    candidates=selection_fixture(c,branch)
    count=(3 if up else 2) if c=='R27' else len(candidates) if c=='R29' else 1
    return candidates[:count]


ENGAGE_CARDS = set('B04 C04 C10 C11 U28 U35'.split())
POWER_CARDS = set('R28 R30 U02 U03 U04 U19 U21 U25 U26 U29 U32 U34 R01 R02 R14 R16 R18'.split())
ENTRY_POWERS = {
    'U39':({'DomainPower':1},{'DomainPower':1}), 'R25':({'DomainPower':2},{'DomainPower':2}),
    'R28':({'BearSpiritPower':1},{'BearSpiritPower':2}), 'R30':({'WildernessPower':6},{'WildernessPower':9}),
    'C05':({'DomainPower':1},{'DomainPower':1}),
    'C14':({'DomainPower':1,'ThunderGuardPower':3},{'DomainPower':1,'ThunderGuardPower':5}),
    'C17':({'StrengthPower':4,'VolibearChargeStrengthPower':4},{'StrengthPower':6,'VolibearChargeStrengthPower':6}),
    'C18':({'DomainPower':1},{'DomainPower':1}), 'C21':({'DomainPower':1},{'DomainPower':1}),
    'C25':({'StormChargePower':1,'NextAttackDiscount':1},{'StormChargePower':2,'NextAttackDiscount':1}),
    'U02':({'StormConductionPower':3},{'StormConductionPower':4}),
    'U03':({'StandingPower':6},{'StandingPower':3}), 'U04':({'BattleScarsPower':1},{'BattleScarsPower':2}),
    'U10':({'NextAttackTrainingPower':3},{'NextAttackTrainingPower':5}), 'U11':({'NextAttackReplayPower':1},{'NextAttackReplayPower':1}),
    'U14':({'NextEngageDiscount':1},{'NextEngageDiscount':1}),
    'U19':({'DomainPower':1,'LingeringStormPower':1},{'DomainPower':1,'LingeringStormPower':1}),
    'U21':({'ThunderAftershockPower':1},{'ThunderAftershockPower':1}),
    'U25':({'PreyStillStandsPower':1},{'PreyStillStandsPower':2}),
    'U26':({'GrowingFuryPower':1,'StrengthPower':1},{'GrowingFuryPower':2,'StrengthPower':1}),
    'U29':({'StormChargePower':2},{'StormChargePower':3}),
    'U32':({'DomainPower':1,'NextAttackDiscount':1,'WelcomeThunderPower':1},{'DomainPower':1,'NextAttackDiscount':2,'WelcomeThunderPower':2}),
    'U34':({'ThunderArmorPower':3},{'ThunderArmorPower':4}), 'U37':({'DomainPower':1},{'DomainPower':1}),
    'R01':({'DomainPower':999999999},{'DomainPower':999999999}), 'R02':({'ImmovableBodyPower':1},{'ImmovableBodyPower':1}),
    'R06':({'StrengthPower':3,'UnifyPower':3},{'StrengthPower':4,'UnifyPower':3}),
    'R13':({'DomainPower':1,'StrengthPower':2},{'DomainPower':1,'StrengthPower':3}),
    'R14':({'EndlessHuntPower':1},{'EndlessHuntPower':1}), 'R16':({'BattleBodyPower':1},{'BattleBodyPower':1}),
    'R18':({'ThunderPoolPower':4},{'ThunderPoolPower':6}),
}
TARGETED = set('C07 U41 B04 C04 C06 C10 C11 U08 U28 U35 R31 C05 B01 B03 C01 C02 C03 C08 C20 U05 U06 U07 U20 U24 U27 U31 U38 U40 R17 R23 T01'.split())
EXHAUST = set('U43 R25 R27 R29 R31 C25 C26 U12 U20 U24 U36 R06 R13 R17 R21 R24 T01 T02'.split())


def _need(value, label):
    if not value:
        raise ValueError(label)


def _same(a, b, label):
    # No bool-as-int, NaN, extra fields or omitted fields acceptance.
    if isinstance(b, dict):
        _need(type(a) is dict and a.keys() == b.keys(), label)
        for k in b: _same(a[k], b[k], label+'.'+k)
    elif isinstance(b, list):
        _need(type(a) is list and len(a) == len(b), label)
        for i, (x,y) in enumerate(zip(a,b)): _same(x,y,f'{label}[{i}]')
    elif type(b) in (int,float):
        _need(type(a) in (int,float) and a == b, label)
    else:
        _need(type(a) is type(b) and a == b, label)


def expected_observations(variant, draw_order, *, random_targets=(0,0,0,0), medium='LeafSlimeM', enemy_order=(0,1,2)):
    """Expand only the explicit finite reference fixtures, never inspected C# values."""
    _need(variant in CARD_FACE_CASES, 'unknown case')
    c,face,b = variant.split('-',2); up = face == 'upgrade'; u = int(up)
    cost,block,draw,hit,hits,light,batches,all_light = ROWS[c][u]
    prior = int(b[5:]) if b.startswith('prior') else 0
    energy = 0 if c == 'C01' else int(b.split('-')[0][1:]) if b.startswith('x') else 10
    initial_block = 10 if c in ('U05','R05','R07') and b != 'zero-block' else 0
    powers = {}; enemy_powers = [{},{},{}]
    if b in ('strength','negative-strength'): powers['StrengthPower'] = 3 if b == 'strength' else -3
    if b == 'weak': powers['WeakPower'] = 1
    if b == 'vulnerable': enemy_powers[0]['VulnerablePower'] = 1
    if b == 'dexterity': powers['DexterityPower'] = 3
    if b == 'frail': powers['FrailPower'] = 1
    if b=='second-instance':powers.update(ENTRY_POWERS[c][u])
    if b=='conduction':powers['StormConductionPower']=3
    if b.endswith('replay'):powers['NextAttackReplayPower']=1
    if b=='charge':powers['StormChargePower']=2
    if b=='domain':powers['DomainPower']=2
    hp = [500-prior]*3
    if b == 'lethal': hp[0] = hit
    if b == 'overkill':hp[0]=29 if up else 22
    before = dict(round=1,turn=1,energy=energy,hp=70 if b in ('injured','overkill') else 80,block=initial_block,enemyHp=hp,
                  enemyBlock=[100 if b == 'blocked' else 0,0,0],powers=powers,powerInstances={key:1 for key in powers},enemyPowers=enemy_powers,
                  lightningCount=prior,sourceShape='Claw' if c=='T01' else 'Body' if c=='T02' else 'None',hand=['source']+(['material','alternate'] if b=='material' else []),
                  draw=list(draw_order),discard=[],play=[],exhaust=[],selectedCards=[])
    if b=='empty' and c in ('C07','U43','R25','U17','R12') or b=='insufficient' and c=='R25':
        before['exhaust']=before['draw'];before['draw']=[]
    if b=='full-hand':before['hand']+=before['draw'][:9];before['draw']=before['draw'][9:]
    if b=='master':before['draw'].remove('source-material')
    if b in ('converted','master'):before['exhaust'].append('source-material')
    for ref,model,pile in selection_fixture(c,b):
        before[pile.lower()].append(ref)
        before['selectedCards'].append(dict(cardRef=ref,shape='None',type='Attack' if model=='B01' else 'Status' if model=='SLIMED' else 'Curse' if model=='INJURY' else 'Skill',upgraded=False,
                                            cost=-1 if model=='INJURY' else 2 if model in ('R07','R23') else 1,prepared=0,retain=False,discount=0,pile=pile))
    after = deepcopy(before); after['hand'].remove('source')
    if b == 'strength':
        if c in ('B01','U05'): hit += 3
        if c == 'C12': block += 3
    if b == 'weak': hit = hit*3//4
    if b == 'vulnerable': hit = hit*3//2
    if b == 'dexterity' and c!='R05': block += 3
    if b == 'frail' and c!='R05': block = block*3//4
    if b == 'zero-block':
        if c == 'U05': hit = 0
        if c == 'R05': block = 0
        if c == 'R07': light = 0
    if c=='R27' and b!='plain':block=0
    if c=='R28' and b in ('zero','empty'):draw=0
    if c=='U17' and b=='empty' or c=='R12' and b in ('empty','full-hand'):draw=0
    if c == 'U31': cost = hits = batches = energy
    if c == 'R17':
        cost = energy; batches = energy+u; light = 6+batches
        if batches: after['powers']['StormChargePower'] = batches
    play_count=2 if b.endswith('replay') else 1
    if play_count==2:
        hits*=2;batches*=2;after['powers'].pop('NextAttackReplayPower')
    if b in ('converted','master'):cost=0
    if c == 'U38': cost = max(0,3-prior)
    if c == 'U27': block = prior*2
    if c == 'R21': block = prior*(5 if up else 4)
    if c == 'U36': draw = int(prior > 0)
    gain = (2+u if prior else 0) if c == 'C26' else 1+u if c == 'U36' else 2 if c == 'U40' and prior >= 2 else prior if c == 'R24' else 0
    if c=='U21' and prior>=2:gain=1
    after['energy'] -= cost; paid_energy = after['energy']; after['energy'] += gain
    after['block'] += block
    if c == 'C08': after['enemyPowers'][0]['VulnerablePower'] = 1+u
    if c == 'U13':
        strength=before['powers'].get('StrengthPower',0)+2+u
        if strength:after['powers']['StrengthPower']=strength
        else:after['powers'].pop('StrengthPower',None)
    if c=='U12' and b=='strength':after['powers']['PrimalThunderPower']=3
    if c == 'U23': after['enemyPowers'] = [{'WeakPower':1+u} for _ in range(3)]
    if c == 'C18': after['enemyPowers'] = [{'WeakPower':2+u} for _ in range(3)]
    if c in ENTRY_POWERS: after['powers'].update(ENTRY_POWERS[c][u])
    if b=='domain':after['powers']['DomainPower']=3 if c=='U37' else 2
    if c=='R31':after['enemyBlock'][0]=0
    light_base=light
    if b=='charge':light+=2
    if c == 'C04': after['enemyPowers'][0]['WeakPower'] = 1
    if c == 'U08': after['enemyPowers'][0]['BiteMarkPower'] = 1
    if c == 'R31': after['powers']['DomainPower'] = 1+u
    if b=='second-instance':
        for name,value in ENTRY_POWERS[c][u].items():after['powers'][name]=2*value
    after['powerInstances']={key:2 if b=='second-instance' and c!='U29' else 1 for key in after['powers']}
    damage = []; batch_records = []; damage_groups=[]; deferred_enemy=None
    def enemy_receipt(record):
        damage.append(record);damage_groups.append([record])
    if c in ENGAGE_CARDS:
        enemy_hit = 2 if c == 'C04' else 3
        absorbed = min(after['block'],enemy_hit)
        after['block'] -= absorbed; after['hp'] -= enemy_hit-absorbed
        record=dict(target=-1,cardRef=None,hpLost=enemy_hit-absorbed,blocked=absorbed,props=8)
        if c in ('B04','C04','U35'):deferred_enemy=record
        else:enemy_receipt(record)
    if c == 'R09':
        for actor in enemy_order:
            if actor < 2:
                amount=3+actor;after['block']-=amount
                enemy_receipt(dict(target=-1,cardRef=None,hpLost=0,blocked=amount,props=8))
        after['discard'] += [f'generated-{i}' for i in range(2 if medium=='LeafSlimeM' else 1)]
    def receipt(target, amount, props, card_ref='source'):
        absorbed = min(after['enemyBlock'][target],amount)
        lost = min(after['enemyHp'][target], amount-absorbed)
        after['enemyBlock'][target] -= absorbed; after['enemyHp'][target] -= lost
        damage.append(dict(target=target,cardRef=card_ref,hpLost=lost,blocked=absorbed,props=props))
        return dict(target=target,hpLost=lost,blocked=absorbed,overkill=max(0,amount-absorbed-lost))
    # Explicit attack/lightning ordering for these finite non-replay examples.
    for i in range(max(hits,batches)):
        if i < hits:
            segment_start=len(damage)
            for target in range(3) if c in ('C09','C22') else (random_targets[i] if c=='R08' else 0,):
                if after['enemyHp'][target] > 0: receipt(target,hit,8)
            if len(damage)>segment_start:damage_groups.append(damage[segment_start:])
            if b=='conduction' or b=='domain' and i==0:
                extra=3 if b=='conduction' else 4;extra_ref=None if b=='conduction' else 'source'
                segment_start=len(damage);after['lightningCount']+=1
                batch_records.append(dict(cardRef=extra_ref,baseDamage=extra,amount=extra,count=after['lightningCount'],targets=[0,1,2],
                                          hits=[receipt(t,extra,4,extra_ref) for t in range(3)]))
                damage_groups.append(damage[segment_start:])
        if i < batches:
            targets = [t for t in (range(3) if all_light else (random_targets[i] if c=='R08' else 0,)) if after['enemyHp'][t] > 0]
            if targets:
                segment_start=len(damage)
                after['lightningCount'] += 1
                batch_records.append(dict(cardRef='source',baseDamage=6 if c=='R17' else light_base,amount=light,
                                          count=after['lightningCount'],targets=targets,hits=[receipt(t,light,4) for t in targets]))
                damage_groups.append(damage[segment_start:])
    if deferred_enemy is not None:enemy_receipt(deferred_enemy)
    if c=='U24' and b in ('injured','overkill'):after['hp']+=1 if b=='overkill' else 3
    if c == 'R31':
        native_light = 9 if up else 6
        segment_start=len(damage)
        after['lightningCount'] += 1
        batch_records.append(dict(cardRef='source',baseDamage=native_light,amount=native_light,count=after['lightningCount'],targets=[0,1,2],
                                  hits=[receipt(t,native_light,4) for t in range(3)]))
        damage_groups.append(damage[segment_start:])
    selection_pending=[]
    if (c in SELECTION_IDS or c=='U17') and b!='empty':
        pending=deepcopy(after);pending['play']=['source']
        if c=='R27' and b=='plain':pending['block']-=4
        if c=='R30':pending['powers'].pop('WildernessPower');pending['powerInstances'].pop('WildernessPower')
        selection_pending.append(pending)
    tracked=after['selectedCards']
    chosen=tracked[:4 if up else 3] if c=='R10' else tracked[:3 if up else 2] if c=='R27' else tracked[:2] if c in ('R25','R29') else tracked[:1]
    if b=='zero':chosen=[]
    if b=='full-hand':chosen=chosen[:1]
    if c in ('C07','C15','U39','U43','R10','R25'):
        for card in chosen:
            ref=card['cardRef'];after[card['pile'].lower()].remove(ref);after['hand'].append(ref);card['pile']='Hand'
        if c=='U43' and b!='empty':
            pending=deepcopy(after);pending['play']=['source'];selection_pending.append(pending)
    conversion_sequence=[]
    for card in chosen:
        if c=='C19':card.update(prepared=5 if up else 3,retain=True)
        if c in BEAST_CARDS:
            material=card['cardRef'];after[card['pile'].lower()].remove(material)
            after['exhaust'].append(material);card['pile']='Exhaust'
            conversion_sequence.append([dict(kind='exhaust',cardRef=material)])
            shape='Claw' if card['type']=='Attack' else 'Body'
            card=dict(cardRef=material+'-beast',shape=shape,type='Attack' if shape=='Claw' else 'Skill',
                      upgraded=False,cost=1,prepared=0,retain=False,discount=0,pile='Hand')
            tracked.append(card);after['hand'].append(card['cardRef'])
            if c=='R27' and shape=='Body':
                conversion_sequence.append([dict(kind='block',target=-1,cardRef='source',amount=4,props=8)])
        if c in ('C15','R10','U41','U42','U43','R29','R30') or c=='R27' and card['shape']=='Claw':
            card['cost']=max(0,card['cost']-1);card['discount']=1
    if b == 'material': after['hand'].remove('material'); after['exhaust'].append('material')
    if c=='U17' and b=='plain':
        after['discard']+=after['draw'][:2];after['draw']=after['draw'][2:]
    drawn = after['draw'][:draw]; after['draw'] = after['draw'][draw:]; after['hand'] += drawn
    if c not in POWER_CARDS:
        after['exhaust' if c in EXHAUST or c in ('C14','U14') and not up else 'discard'].append('source')
    # Fixed native-history projection: damage, block, draws, exhausts and the
    # explicitly ordered domain/enemy debuff events. No production state is executed here.
    sequence=[[dict(kind='damage',**d) for d in group] for group in damage_groups]
    draw_groups=[[dict(kind='draw',cardRef=ref)] for ref in drawn]
    def power(kind,amount,targets=(-1,)):
        return [dict(kind='power',target=t,type=kind,amount=amount) for t in targets]
    if c in ('C10','U28'):sequence[1:1]=draw_groups
    elif c=='R09':
        sequence=[];enemy_records=iter(d for d in damage if d['target']==-1)
        for index,actor in enumerate(enemy_order):
            if actor<2:sequence.append([dict(kind='damage',**next(enemy_records))])
            if index==0:sequence+=draw_groups
        sequence.append([dict(kind='damage',**d) for d in damage if d['target']!=-1])
    elif c!='U19':sequence+=draw_groups
    if c=='C04':sequence.insert(1,power('WeakPower',1,(0,)))
    if c=='C08':sequence.append(power('VulnerablePower',1+u,(0,)))
    if c=='U08':sequence.append(power('BiteMarkPower',1,(0,)))
    if c=='C18':sequence.append(power('WeakPower',2+u,range(3)))
    if c=='U23':sequence.append(power('WeakPower',1+u,range(3)))
    domain_amount={'C05':1,'C14':1,'C18':1,'C21':1,'U19':1,'U32':1,'U37':1,'U39':1,'R01':999999999,'R25':2,'R31':1+u}.get(c)
    if c=='R13' and b!='domain':domain_amount=1
    if domain_amount is not None:
        domain_group=power('DomainPower',domain_amount)
        if c=='U37':sequence.append(domain_group)
        elif c=='U19':sequence=draw_groups+[domain_group]
        else:sequence.insert(0,domain_group)
    block_gain=before['block']*2 if c=='R05' else block
    if block_gain and c!='R27':
        block_group=[dict(kind='block',target=-1,cardRef='source',amount=block_gain,props=12 if c=='R05' else 8)]
        if c in ('C06','U27','U23'):sequence.append(block_group)
        else:sequence.insert(0,block_group)
    if b=='material':sequence.insert(0,[dict(kind='exhaust',cardRef='material')])
    if c in BEAST_CARDS:
        # Exhaust is an actual native event. R28 draws after the first generated
        # token; R27's body block follows that body's conversion, not the batch.
        sequence=[group for group in sequence if not any(event['kind']=='draw' for event in group)]
        sequence+=conversion_sequence+draw_groups
    if 'source' in after['exhaust']:sequence.append([dict(kind='exhaust',cardRef='source')])
    return dict(before=before,after=after,cost=cost,playCount=play_count,paidEnergy=paid_energy,damage=damage,damageGroups=damage_groups,sequenceGroups=sequence,batches=batch_records,draws=drawn,selectionPending=selection_pending)


def expected_response(c,up,source_after):
    """Fixed responder cards and generated beast tokens from status/curse material."""
    if c=='U42':
        before=deepcopy(source_after);after=deepcopy(before)
        after['hand'].remove('selected-beast');after['exhaust'].append('selected-beast');after['block']+=9
        after['enemyHp']=[hp-2 for hp in after['enemyHp']];after['lightningCount']+=1
        selected=next(card for card in after['selectedCards'] if card['cardRef']=='selected-beast');selected.update(cost=1,discount=0,pile='Exhaust')
        damage=[dict(target=t,cardRef='selected-beast',hpLost=2,blocked=0,props=4) for t in range(3)]
        sequence=[[dict(kind='block',target=-1,cardRef='selected-beast',amount=9,props=8)],[dict(kind='damage',**d) for d in damage],[dict(kind='exhaust',cardRef='selected-beast')]]
        batch=dict(cardRef='selected-beast',baseDamage=2,amount=2,count=after['lightningCount'],targets=[0,1,2],hits=[dict(target=t,hpLost=2,blocked=0,overkill=0) for t in range(3)])
        history=dict(plays=[dict(cardRef='selected-beast',index=0,count=1)],draws=[],moves=[],generated=[],damage=damage,sequence=sum(sequence,[]))
        return dict(before=before,after=after,cost=0,paidEnergy=before['energy'],batches=[batch],history=history,damageGroups=[damage],sequenceGroups=sequence)
    before=deepcopy(source_after);before['hand'].append('response-card');after=deepcopy(before)
    after['hand'].remove('response-card');after['discard'].append('response-card')
    cost=2 if c=='U21' else 1;after['energy']-=cost;paid=after['energy']
    groups=[];sequence=[];batches=[];draws=[]
    def ordinary():
        after['enemyHp'][0]-=5
        group=[dict(target=0,cardRef='response-card',hpLost=5,blocked=0,props=8)]
        groups.append(group);sequence.append([dict(kind='damage',**d) for d in group])
    def thunder(base,amount,targets,ref):
        after['lightningCount']+=1
        group=[dict(target=t,cardRef=ref,hpLost=amount,blocked=0,props=4) for t in targets]
        for t in targets:after['enemyHp'][t]-=amount
        groups.append(group);sequence.append([dict(kind='damage',**d) for d in group])
        batches.append(dict(cardRef=ref,baseDamage=base,amount=amount,count=after['lightningCount'],targets=list(targets),
                            hits=[dict(target=t,hpLost=amount,blocked=0,overkill=0) for t in targets]))
    if c=='U02':
        for _ in range(2):
            ordinary()
            for _ in range(2):thunder(4 if up else 3,4 if up else 3,range(3),None)
    elif c=='U21':
        for _ in range(3):thunder(8,8,(0,),'response-card')
        after['energy']+=2
    else:
        thunder(6,(12 if up else 10) if c=='U29' else 6,range(3),'response-card')
        if c=='U34':
            value=4 if up else 3;after['block']+=2*value
            sequence += [[dict(kind='block',target=-1,cardRef=None,amount=value,props=8)] for _ in range(2)]
        draws=after['draw'][:1];after['draw']=after['draw'][1:];after['hand']+=draws
        sequence += [[dict(kind='draw',cardRef=ref)] for ref in draws]
    history=dict(plays=[dict(cardRef='response-card',index=0,count=1)],draws=draws,moves=[],generated=[],damage=sum(groups,[]),sequence=sum(sequence,[]))
    return dict(before=before,after=after,cost=cost,paidEnergy=paid,batches=batches,history=history,damageGroups=groups,sequenceGroups=sequence)


def _validate_response(response,c,up,source_after,root_action,enemy_id):
    _need(type(response) is dict and set(response)=={'before','after','action','payments','effects','batches','history'},'response fields')
    e=expected_response(c,up,source_after)
    _same(response['before'],e['before'],'response before');_same(response['after'],e['after'],'response after')
    aid=response['action']['id'];_need(type(aid) is int and aid>root_action,'distinct later native action')
    _same(response['action'],dict(id=aid,state='Finished',type='PlayCardAction',context='GameActionPlayerChoiceContext',actionType='CombatPlayPhaseOnly',
        target=enemy_id if c in ('U02','U21') else None,sameCard=True,events=[dict(name='before-executed',state='Executing',id=aid,energy=e['before']['energy']),
        dict(name='after-finished',state='Finished',id=aid,energy=e['after']['energy'])]),'response action')
    ref='selected-beast' if c=='U42' else 'response-card'
    _same(response['payments'],[dict(cardRef=ref,amount=e['cost'],energy=e['paidEnergy'])],'response payment')
    _same(response['effects'],[dict(cardRef=ref,index=0,count=1,autoPlay=False,energy=e['paidEnergy'],spent=e['cost'])],'response effect')
    actual=deepcopy(response['batches'])
    for batch in actual:batch['targets'].sort();batch['hits'].sort(key=lambda h:h['target'])
    _same(actual,e['batches'],'response lightning')
    actual=deepcopy(response['history'])
    _same([{k:v for k,v in event.items() if k!='kind'} for event in actual['sequence'] if event.get('kind')=='damage'],actual['damage'],'response projections agree')
    for key,groups in (('damage',e['damageGroups']),('sequence',e['sequenceGroups'])):
        offset=0
        for group in groups:
            actual[key][offset:offset+len(group)]=sorted(actual[key][offset:offset+len(group)],key=lambda d:d.get('target',-2))
            offset+=len(group)
    _same(actual,e['history'],'response history')


def _validate(r, token, variant):
    _need(type(token) is str and bool(token), 'token required')
    _need(variant in CARD_FACE_CASES, 'unknown case')
    c,face,b = variant.split('-',2)
    fields = 'schema token variant scenario acceptance version commit testMode character enemyTypes playerId enemyIds enemyOrder cards sourceIdentity starterDrawOrder before after choice selections conversions action payments effects batches history response'.split()
    _need(type(r) is dict and set(r)==set(fields), 'result fields')
    for k,v in dict(schema=2,token=token,variant=variant,scenario='card-face-acceptance',acceptance=ACCEPTANCE,
                    version='v0.107.1',commit='59260271',testMode=False,character='VolibearCharacter').items(): _same(r[k],v,k)
    _need(r['enemyTypes'] in [['LeafSlimeS','TwigSlimeS',m] for m in ('LeafSlimeM','TwigSlimeM')], 'native roster')
    _need(type(r['enemyOrder']) is list and sorted(r['enemyOrder'])==[0,1,2] and all(type(x) is int for x in r['enemyOrder']),'initial native enemy order')
    ids = r['enemyIds']; pid = r['playerId']
    _need(type(ids) is list and len(ids)==3 and all(type(x) is int and x>=0 for x in ids+[pid]) and len(set(ids+[pid]))==4,'creature identity')
    originals = [f'starter-{i}' for i in range(10)]
    if b=='master':
        present={card['cardRef'] for card in r['cards']}
        originals=[ref for ref in originals if ref in present]
        _need(len(originals)==9,'exactly one physical starter is the source')
    extra = {'source':'VOLIBEAR_'+c}
    if b in ('converted','master'):extra['source-material']='VOLIBEAR_'+('B01' if c=='T01' else 'B02')
    if b=='second-instance':extra['response-card']='VOLIBEAR_'+('C02' if c=='U02' else 'R23' if c=='U21' else 'C24')
    if b == 'material': extra.update(material='VOLIBEAR_B01',alternate='VOLIBEAR_B02')
    extra.update({ref:model if model in ('SLIMED','INJURY') else 'VOLIBEAR_'+model for ref,model,pile in selection_fixture(c,b)})
    extra.update({ref+'-beast':'VOLIBEAR_T01' if model=='B01' else 'VOLIBEAR_T02' for ref,model,pile in beast_materials(c,face=='upgrade',b)})
    if c=='R09':extra.update({f'generated-{i}':'SLIMED' for i in range(2 if r['enemyTypes'][2]=='LeafSlimeM' else 1)})
    lookup = {}; indices=set(); masters=set(); models=[]
    for card in r['cards']:
        _need(type(card) is dict and set(card)==set('cardRef modelId upgraded combatCardIndex sameObject ownerId masterIndex masterModelId'.split()),'card fields')
        ref=card['cardRef']; index=card['combatCardIndex']; master=card['masterIndex']
        _need(type(index) is int and index>=0 and index not in indices and ref not in lookup,'unique identity')
        _same(card['sameObject'],True,'native reference'); _same(card['ownerId'],pid,'owner')
        _same(card['upgraded'],ref in ('source','source-material') and face=='upgrade','upgrade')
        if ref in originals or b=='master' and ref=='source-material':
            if ref=='source-material':_same(card['modelId'],extra[ref],'material source model')
            _need(type(master) is int and 0<=master<10 and master not in masters,'deck identity')
            masters.add(master); models.append(card['modelId']); _same(card['masterModelId'],card['modelId'],'master model')
        else:
            _need(ref in extra,'unknown fixture entity'); _same(card['modelId'],extra[ref],'model'); _same(master,-1,'generated master'); _same(card['masterModelId'],None,'generated deck')
        lookup[ref]=card; indices.add(index)
    _need(set(lookup)==set(originals)|set(extra),'fixture cards')
    _need(Counter(models)==Counter(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04']),'starter models')
    source=lookup['source']
    _same(r['sourceIdentity'],dict(indexBefore=source['combatCardIndex'],masterIndexBefore=source['masterIndex'],sameMaster=True,
                                   masterUpgradedBefore=None,masterUpgradedAfter=None),'played source identity')
    order=r['starterDrawOrder']
    _need(type(order) is list and len(order)==10 and set(order)==set(originals)|({'source-material'} if b=='master' else set()),'original native draw fixture')
    conversion_pairs=([('source-material','source')] if b in ('converted','master') else []) + [
        (ref,ref+'-beast') for ref,model,pile in beast_materials(c,face=='upgrade',b)]
    expected_conversions=[]
    for material_ref,beast_ref in conversion_pairs:
        material=lookup[material_ref];beast=lookup[beast_ref]
        master_upgraded=False if b=='master' and material_ref=='source-material' else None
        expected_conversions.append(dict(materialRef=material_ref,cardRef=beast_ref,
            materialIndex=material['combatCardIndex'],cardIndex=beast['combatCardIndex'],sameObject=False,masterUnchanged=True,
            materialMasterUpgradedBefore=master_upgraded,materialMasterUpgradedAfter=master_upgraded,
            pileBefore='Hand',pileAfter='Hand',originalExhausted=True))
    _same(r['conversions'],expected_conversions,'native exhaust and new-token identities')
    e=expected_observations(variant,order,medium=r['enemyTypes'][2],enemy_order=r['enemyOrder'])
    if c=='R08':
        # Exactly 81 legal four-target outcomes in this nonlethal three-enemy fixture.
        # This checks paired hits and actual HP, NOT seeded RNG consumption acceptance.
        candidates=[expected_observations(variant,order,random_targets=targets) for targets in product(range(3),repeat=4)]
        matches=[x for x in candidates if x['batches']==r['batches'] and x['damage']==r['history']['damage']]
        _need(len(matches)==1,'one legal four-hit random outcome');e=matches[0]
    _same(r['before'],e['before'],'before'); _same(r['after'],e['after'],'after')
    a=r['action']; aid=a['id']; _need(type(aid) is int and aid>=0,'action id')
    _same(a,dict(id=aid,state='Finished',type='PlayCardAction',context='GameActionPlayerChoiceContext',actionType='CombatPlayPhaseOnly',
                 target=ids[0] if c in TARGETED else None,sameCard=True,events=[
                     dict(name='before-executed',state='Executing',id=aid,energy=e['before']['energy']),
                     dict(name='after-finished',state='Finished',id=aid,energy=e['after']['energy'])]),'action')
    _same(r['payments'],[dict(cardRef='source',amount=e['cost'],energy=e['paidEnergy'])],'payments')
    _same(r['effects'],[dict(cardRef='source',index=i,count=e['playCount'],autoPlay=False,energy=e['paidEnergy'],spent=e['cost']) for i in range(e['playCount'])],'effects')
    _same(r['history']['plays'],[dict(cardRef='source',index=i,count=e['playCount']) for i in range(e['playCount'])],'play receipt')
    _same(r['history']['draws'],e['draws'],'draw receipt')
    moves=['TACKLE_MOVE'] if c in ENGAGE_CARDS else []
    generated=[dict(cardRef=ref+'-beast',creatorId=pid) for ref,model,pile in beast_materials(c,face=='upgrade',b)]
    if c=='R09':
        moves=['TACKLE_MOVE' if t<2 else 'STICKY_SHOT' if r['enemyTypes'][2]=='LeafSlimeM' else 'STICKY_SHOT_MOVE' for t in r['enemyOrder']]
        generated=[dict(cardRef=f'generated-{i}',creatorId=None) for i in range(2 if r['enemyTypes'][2]=='LeafSlimeM' else 1)]
    _same(r['history']['moves'],moves,'native enemy moves');_same(r['history']['generated'],generated,'native generated identities')
    _need(set(r['history'])=={'plays','draws','moves','damage','generated','sequence'},'history fields')
    # Preserve segment order across targets (especially Engage vs lightning).
    # Only target permutation INSIDE one all-target segment is native-order agnostic.
    actual_damage=r['history']['damage'];_need(type(actual_damage) is list and len(actual_damage)==len(e['damage']),'damage count')
    offset=0
    for segment in e['damageGroups']:
        chunk=actual_damage[offset:offset+len(segment)]
        _same(sorted(chunk,key=lambda d:d['target']),sorted(segment,key=lambda d:d['target']),'ordered damage segment')
        offset+=len(segment)
    _need(offset==len(actual_damage),'complete segment coverage')
    sequence=r['history']['sequence'];_need(type(sequence) is list,'native ordered history projection')
    _same([{k:v for k,v in event.items() if k!='kind'} for event in sequence if event.get('kind')=='damage'],actual_damage,'history projections agree')
    _same([event['cardRef'] for event in sequence if event.get('kind')=='draw'],r['history']['draws'],'draw projections agree')
    offset=0
    for group in e['sequenceGroups']:
        chunk=sequence[offset:offset+len(group)]
        _same(sorted(chunk,key=lambda d:d.get('target',-2)),sorted(group,key=lambda d:d.get('target',-2)),'ordered native effect event')
        offset+=len(group)
    _need(offset==len(sequence),'no extra native effect events')
    actual=deepcopy(r['batches'])
    for batch in actual:
        batch['targets'].sort(); batch['hits'].sort(key=lambda h:h['target'])
    _same(actual,e['batches'],'lightning receipts')
    if b != 'material': _same(r['choice'],None,'no native choice')
    else: _validate_choice(r['choice'],lookup,aid,e)
    _validate_selections(r['selections'],lookup,aid,e,c,face=='upgrade',b)
    if b=='second-instance' or c=='U42' and b in ('status','curse'):_validate_response(r['response'],c,face=='upgrade',e['after'],aid,ids[0])
    else:_same(r['response'],None,'no response fixture')


def selection_plan(c,up,index,branch='plain'):
    if c=='U17':return 'Draw',0,5 if up else 3,[]
    pile='Discard' if c in ('C15','R10') else 'Draw' if c in ('C07','U39','R25') or c=='U43' and index==0 else 'Hand'
    maximum=(4 if up else 3) if c=='R10' else (3 if up else 2) if c=='R27' else 2 if c=='R25' else 1
    minimum=0 if c in ('R10','R25','R27','R28') else maximum
    selected=['selected','alternate','third','fourth'][:maximum] if c in ('R10','R27') else ['selected','alternate'] if c=='R25' else ['selected']
    if branch in ('insufficient','full-hand'):maximum=1;selected=['selected']
    if branch=='zero':selected=[]
    return pile,minimum,maximum,selected


def _validate_selector(receipt,pending,aid,minimum,maximum,allowed,selected):
    # Native ICardSelector resolves the original candidate objects. This makes no
    # claim about visible controls, UI input, or remote-peer synchronization.
    _need(type(receipt) is dict and set(receipt)=={'api','pending','actionId','min','max','options','selected','sameObjects'},'selector fields')
    _same(receipt,dict(api='CardSelectCmd.UseSelector',pending=pending,actionId=aid,min=minimum,max=maximum,
                       options=allowed,selected=selected,sameObjects=[True]*len(selected)),'controlled native selector')


def _validate_selections(selections,cards,aid,e,c,up,branch):
    _need(type(selections) is list and len(selections)==len(e['selectionPending']),'selection count')
    for i,receipt in enumerate(selections):
        pending=e['selectionPending'][i]
        pile,minimum,maximum,selected=selection_plan(c,up,i,branch)
        available=pending[pile.lower()]
        if c=='U17':available=available[:maximum];selected=[] if branch=='zero' else available[:2]
        def eligible(ref):
            model=cards[ref]['modelId']
            if c in ('C07','C19','U41'):return model in ('VOLIBEAR_B01','VOLIBEAR_B03','VOLIBEAR_B04')
            if c=='U39':return ref in ('selected','alternate')
            if c=='R25':return model=='VOLIBEAR_B02'
            return True
        allowed=[ref for ref in available if eligible(ref)]
        # Locked native FromCombatPile selector IL sorts Draw by Rarity then Id
        # (stable LINQ OrderBy/ThenBy), not physical draw order. These fixtures
        # contain equal-rarity candidates (Basic, or U39's two Rares). Reject
        # expansion without a rarity oracle.
        # U17's top-N inspection is not a pile search.
        if pile=='Draw' and c!='U17':
            equal_rarity = ('VOLIBEAR_R07','VOLIBEAR_R23') if c=='U39' else ('VOLIBEAR_B01','VOLIBEAR_B02','VOLIBEAR_B03','VOLIBEAR_B04')
            _need(all(cards[ref]['modelId'] in equal_rarity for ref in allowed), 'draw-search fixture candidates must have equal rarity')
            allowed.sort(key=lambda ref:cards[ref]['modelId'])
        _validate_selector(receipt,pending,aid,minimum,maximum,allowed,selected)


def _validate_choice(choice,cards,aid,e):
    # The source is already in Play. Both material entities must remain available
    # before resolution, and the selected object must be the original candidate.
    pending=deepcopy(e['before']);pending['energy']=e['paidEnergy'];pending['hand'].remove('source');pending['play']=['source']
    _validate_selector(choice,pending,aid,1,1,['material','alternate'],['material'])


def validate_card_face_result(result, token, variant):
    try:
        _validate(result,token,variant)
        return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        return False


def extract_card_face_result(text, token, variant):
    records=[json.loads(line.split(PREFIX,1)[1]) for line in text.splitlines() if PREFIX in line]
    if len(records)!=1 or not validate_card_face_result(records[0],token,variant):
        raise ValueError('Expected exactly one complete, matching native face receipt')
    return records[0]


BATCH_PREFIX='[Volibear] CARD_FACE_BATCH_RESULT '


def extract_card_face_batch(text,token,cases):
    """One process, one token, exact requested order, full per-case validation."""
    _need(type(token) is str and bool(token),'batch token')
    _need(type(cases) in (list,tuple) and bool(cases) and all(type(c) is str and c in CARD_FACE_CASES for c in cases),'batch selection')
    cases=list(cases);_need(len(set(cases))==len(cases),'duplicate selected case')
    _need('[Volibear] CARD_FACE_ERROR ' not in text and '[Volibear] CARD_FACE_BATCH_ERROR ' not in text,'native batch error')
    records=[json.loads(line.split(PREFIX,1)[1]) for line in text.splitlines() if PREFIX in line]
    summaries=[json.loads(line.split(BATCH_PREFIX,1)[1]) for line in text.splitlines() if BATCH_PREFIX in line]
    _need(len(records)==len(cases) and len(summaries)==1,'complete unique batch receipts')
    for record,case in zip(records,cases):
        try:
            _validate(record,token,case)
        except (ValueError,TypeError,KeyError,IndexError,AttributeError) as error:
            raise ValueError(f'full native case {case}: {error}') from error
    summary=summaries[0]
    _need(type(summary) is dict and set(summary)=={'schema','token','cases','completed','transitions','lifecycle','shouldSave'},'batch summary fields')
    _same({k:v for k,v in summary.items() if k!='transitions'},dict(schema=1,token=token,cases=cases,completed=cases,
          lifecycle='EnterRoom(MapRoom)->ReturnToMainMenu->StartNewSingleplayerRun',shouldSave=False),'native batch completeness')
    transitions=summary['transitions'];_need(type(transitions) is list and len(transitions)==len(cases),'all native exits')
    seen=set()
    for transition,case in zip(transitions,cases):
        ids={key:transition[key] for key in ('runIdentity','playerIdentity','creatureIdentity','deckIdentity')}
        _need(all(type(value) is int and value>=4 and value not in seen for value in ids.values()) and len(set(ids.values()))==4,'fresh native object identities')
        seen.update(ids.values())
        _same(transition,dict(variant=case,**ids,runNull=True,combatNull=True,inProgress=False,queueEmpty=True,actionNull=True,historyVisible=0),'native exit cleanup')
    return dict(records=records,batch=summary,coverage=release_coverage(records))


def validate_card_face_batch(text,token,cases):
    try:extract_card_face_batch(text,token,cases);return True
    except (AssertionError,ValueError,KeyError,TypeError,IndexError,AttributeError):return False


def release_coverage(records):
    """No passed metadata, cross-case substitution, or denominator reduction."""
    valid=[]; invalid=[]; seen=set()
    for r in records:
        key=(r.get('token'),r.get('variant'))
        if key in seen or not validate_card_face_result(r,*key): invalid.append(key)
        else: valid.append(r['variant'])
        seen.add(key)
    faces={v.rsplit('-',1)[0] for v in valid}
    # negative-strength is a branch containing a dash; use the first two fields.
    faces={'-'.join(v.split('-')[:2]) for v in valid}
    return dict(face_denominator=178,executed_faces=len(faces),missing_faces=sorted(set(ALL_FACES)-faces),
                implemented_cases=len(CARD_FACE_CASES),missing_implemented_cases=sorted(set(CARD_FACE_CASES)-set(valid)),invalid=invalid,
                section7_complete=False,section7_unclosed=list(ALL_IDS),release_pass=False)
