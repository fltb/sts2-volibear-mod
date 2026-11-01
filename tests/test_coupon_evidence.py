"""Hand-authored synthetic coupon receipts, not real gameplay evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools/coupon_evidence.py'
PROBE=ROOT/'src/Volibear/CouponContractProbe.cs'
spec=importlib.util.spec_from_file_location('coupon_gate',MODULE);evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)


def _role_order_receipt(case,medium='TwigSlimeM'):
    # Each descriptor is role, model, upgrade, label, paid, next(attack,engage,charge), next block.
    desc=[('attack-coupon','C25',False,'attack-coupon',1,(1,0,1),0)]
    if case=='CP-max-preserve':desc.append(('attack-coupon-upgrade','C25',True,'attack-coupon-upgrade',1,(1,0,3),0))
    charge=3 if case=='CP-max-preserve' else 1
    desc.append(('engage-coupon','U14',False,'engage-coupon',0,(1,1,charge),5))
    if case.startswith('CP-elig-'):
        code=case[8:];paid,attack,block={'B04':(0,0,10),'C04':(0,0,3),'C10':(0,0,10),'C11':(0,1,10),'U28':(1,1,14),'U35':(0,1,10),'R09':(1,1,13)}[code]
        desc.append(('target',code,False,'target',paid,(attack,0,1),block))
    elif case=='CP-max-preserve':
        desc += [('engage-coupon-upgrade','U14',True,'engage-coupon-upgrade',0,(1,1,3),13),('noneligible','B02',False,'noneligible',1,(1,1,3),18),
                 ('target','C10',False,'invalid-target',0,(1,1,3),18),('target','C10',False,'target',0,(0,0,3),23)]
    elif case=='CP-zero-consume':desc += [('zero-attack','C01',False,'zero-attack',0,(0,1,1),5),('target','B04',False,'target',0,(0,0,1),10)]
    elif case=='CP-expiry':desc += [('target','C10',False,'target',2,(0,0,1),8)]
    else:
        attack=case=='CP-beast-attack'
        desc += [('convert','R29',False,'convert',3,(1,1,1),5),('target','C10' if attack else 'U28',False,'target',0,(0 if attack else 1,1,1),5 if attack else 14)]
    cards=[]
    for i,code in enumerate(['B01']*4+['B02']*4+['B03','B04']):
        cards.append(dict(cardRef=f'starter-{i}',modelId='VOLIBEAR_'+code,upgraded=False,combatCardIndex=100+i,sameObject=True,ownerId=10,masterIndex=i,masterModelId='VOLIBEAR_'+code))
    for role,code,up,*_ in desc:
        if any(c['cardRef']==role for c in cards):continue
        cards.append(dict(cardRef=role,modelId='VOLIBEAR_'+code,upgraded=up,combatCardIndex=100+len(cards),sameObject=True,ownerId=10,masterIndex=-1,masterModelId=None))
    originals=[f'starter-{i}' for i in range(10)]
    state=dict(round=1,turn=1,side='Player',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},hand=[],draw=originals[:],discard=[],play=[],exhaust=[],forms=[])
    r=dict(token='run-token',variant=case,scenario='coupon-contract',completed=True,gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           acceptance=evidence.ACCEPTANCE,character='VolibearCharacter',playerId=10,enemyIds=[11,12,13],enemyTypes=['LeafSlimeS','TwigSlimeS',medium],
           fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-explicit',cards=cards,generated=[],initial=deepcopy(state),steps=[],transition=None)
    present=set(originals)
    def hist():return dict(plays=[],draws=[],moves=[],damage=[],generated=[])
    def hit(target,n,blocked=0,card=None,props=8):return dict(target=target,cardRef=card,hpLost=n,blocked=blocked,props=props)
    def gen(h,window):
        for j in range(2 if medium=='LeafSlimeM' else 1):
            role=f'generated-{j}';state['discard'].append(role);h['generated'].append(dict(cardRef=role,creatorId=None))
            r['generated'].append(dict(cardRef=role,modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=200+j,sameObject=True,ownerId=10,
                                       masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=13,sourceType=medium,sourceMove='STICKY_SHOT' if medium=='LeafSlimeM' else 'STICKY_SHOT_MOVE',
                                       round=1,turn=1,side='Enemy' if window=='end-turn' else 'Player',window=window))
        h['moves'].append(dict(enemy=13,move='STICKY_SHOT' if medium=='LeafSlimeM' else 'STICKY_SHOT_MOVE'))
    def draw(h,n,normal=False):
        take=state['draw'][:n];del state['draw'][:n];state['hand']+=take
        h['draws'] += [dict(cardRef=c,fromHandDraw=normal) for c in take]
    for i,(role,code,up,label,paid,(attack,engage,charge),block) in enumerate(desc):
        if case=='CP-expiry' and label=='target':
            before=deepcopy(state);h=hist();h['moves']=[dict(enemy=11,move='TACKLE_MOVE'),dict(enemy=12,move='TACKLE_MOVE')]
            h['damage']=[hit(10,0,3),hit(10,2,2)];gen(h,'end-turn');draw(h,5,True)
            state.update(round=2,turn=2,energy=3,hp=78,block=0,powers=dict(StormChargePower=1))
            r['transition']=dict(before=before,after=deepcopy(state),history=h)
        if label=='convert':state['hand'].append('target');present.add('target')
        if role not in present:state['hand'].append(role);present.add(role)
        before=deepcopy(state);a0=state['powers'].get('NextAttackDiscount',0);e0=state['powers'].get('NextEngageDiscount',0)
        shape=('Claw' if case.endswith('attack') else 'Body') if role=='target' and case.startswith('CP-beast-') else 'None'
        ctype='Attack' if shape=='Claw' or shape=='None' and code in ['B04','C04','C10','C01'] else 'Skill'
        invalid=label=='invalid-target';target=10 if invalid else 11 if code in ['B04','C04','C10','C11','U28','U35','C01'] and shape!='Body' else None
        aid=i;events=[dict(name='before-executed',state='Executing',id=aid,energy=before['energy'])];h=hist();payments=[];effects=[]
        if invalid:events.append(dict(name='cancelled',state='Canceled',id=aid,energy=state['energy']))
        else:
            state['energy']-=paid;state['hand'].remove(role)
            payments=[dict(cardRef=role,amount=paid,energy=state['energy'],coupons=dict(attack=a0,engage=e0))]
            if code in ['C25','U14','B02','R29']:post_coupons=dict(attack=a0,engage=e0)
            else:post_coupons=dict(attack=attack,engage=engage)
            effects=[dict(cardRef=role,index=0,count=1,autoPlay=False,playId=100+i,spent=paid,energy=state['energy'],cardType=ctype,shape=shape,coupons=post_coupons)]
            state['powers']=dict(StormChargePower=charge)
            if attack:state['powers']['NextAttackDiscount']=attack
            if engage:state['powers']['NextEngageDiscount']=engage
            state['block']=block;h['plays']=[dict(cardRef=role,index=0,count=1)]
            if label=='convert':state['forms']=[dict(cardRef='target',shape='Claw' if case.endswith('attack') else 'Body',type='Attack' if case.endswith('attack') else 'Skill')]
            if shape=='Claw':state['enemyHp'][0]-=14;h['damage']=[hit(11,7,card=role),hit(11,7,card=role)]
            elif shape=='Body':state['enemyHp']=[497]*3;h['damage']=[hit(e,3,card=role,props=4) for e in (11,12,13)]
            elif code=='C01':state['enemyHp'][0]-=6;h['damage']=[hit(11,6,card=role)]
            elif code in ['B04','C04','C10','C11','U28','U35','R09']:
                h['moves']=[dict(enemy=11,move='TACKLE_MOVE')];draw(h,1)
                blocked=2 if code=='C04' else 3
                if code in ['B04','C04']:
                    n=6 if code=='B04' else 9;state['enemyHp'][0]-=n;h['damage']=[hit(11,n,card=role),hit(10,0,blocked)]
                elif code=='C10' and case=='CP-expiry':
                    state['enemyHp'][0]=494;h['damage']=[hit(11,6,card=role)];h['moves']=[dict(enemy=11,move='GOOP_MOVE')]
                    j=len(r['generated']);goop=f'generated-{j}';state['discard'].append(goop);h['generated']=[dict(cardRef=goop,creatorId=None)]
                    r['generated'].append(dict(cardRef=goop,modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=200+j,sameObject=True,ownerId=10,
                        masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=11,sourceType='LeafSlimeS',sourceMove='GOOP_MOVE',round=2,turn=2,side='Player',window='expiry-engage'))
                elif code=='C10':state['enemyHp'][0]-=9;h['damage']=[hit(10,0,3),hit(11,9,card=role)]
                elif code=='C11':h['damage']=[hit(10,0,3)]
                elif code=='U35':state['enemyHp']=[496]*3;h['damage']=[hit(e,4,card=role,props=4) for e in (11,12,13)]+[hit(10,0,3)]
                else:
                    state['enemyHp']=[492]*3;h['damage']=[hit(10,0,3)]
                    if code=='R09':h['damage'].append(hit(10,0,4));h['moves'].append(dict(enemy=12,move='TACKLE_MOVE'));gen(h,'R09')
                    h['damage'] += [hit(e,8,card=role,props=4) for e in (11,12,13)]
            destination='exhaust' if code in ['C25','R29'] or code=='U14' and not up or shape!='None' else 'discard'
            state[destination].append(role)
        events.append(dict(name='after-finished',state='Finished',id=aid,energy=state['energy']))
        r['steps'].append(dict(label=label,cardRef=role,cardType=ctype,shape=shape,before=before,after=deepcopy(state),
                               action=dict(id=aid,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context=None if invalid else 'GameActionPlayerChoiceContext',target=target,sameCard=True,events=events),
                               payments=payments,effects=effects,history=h))
    return r


def specimen(case,medium='TwigSlimeM',reverse=False):
    # Convert semantic-role fixture slots to the four actual SlimesWeak layouts.
    order=[1,2,0] if reverse else [0,2,1]
    new_ids={11+old:11+new for new,old in enumerate(order)}
    native_types=(['TwigSlimeS',medium,'LeafSlimeS'] if reverse else ['LeafSlimeS',medium,'TwigSlimeS'])
    def visit(value):
        if isinstance(value,list):return [visit(v) for v in value]
        if not isinstance(value,dict):return value
        result={}
        for key,v in value.items():
            if key in ('target','sourceEnemy','enemy') and type(v) is int:result[key]=new_ids.get(v,v)
            elif key=='enemyHp':result[key]=[v[j] for j in order]
            elif key=='enemyTypes':result[key]=native_types[:]
            else:result[key]=visit(v)
        if 'plays' in result and 'damage' in result and 'moves' in result:
            result['moves'].sort(key=lambda row:row['enemy'])
            source_for_amount={2:11,3:11,4:12}
            damage=result['damage'];out=[];index=0
            while index<len(damage):
                end=index+1;row=damage[index]
                while end<len(damage) and (damage[end]['cardRef'],damage[end]['props'])==(row['cardRef'],row['props']):end+=1
                group=damage[index:end]
                if row['cardRef'] is None:group.sort(key=lambda d:new_ids[source_for_amount[d['hpLost']+d['blocked']]])
                elif row['props']==4:group.sort(key=lambda d:d['target'])
                out+=group;index=end
            result['damage']=out
            if case=='CP-expiry' and reverse and len(result['moves'])==3:
                # Initial five block: Twig's four first, then Leaf's three after the medium status move.
                result['damage'][0].update(hpLost=0,blocked=4)
                result['damage'][1].update(hpLost=2,blocked=1)
        return result
    return visit(_role_order_receipt(case,medium))


class CouponEvidenceTests(unittest.TestCase):
    def test_expiry_native_goop_requires_exact_source_count_identity_and_no_absorption(self):
        self.reject('CP-expiry',[
            lambda r:r['generated'].pop(),lambda r:r['generated'].append(deepcopy(r['generated'][-1])),
            lambda r:r['generated'][-1].update(sourceEnemy=12,sourceType='TwigSlimeM'),
            lambda r:r['generated'][-1].update(sourceMove='TACKLE_MOVE'),
            lambda r:r['generated'][-1].update(round=1,turn=1),lambda r:r['generated'][-1].update(turn=3),
            lambda r:r['generated'][-1].update(side='Enemy'),lambda r:r['generated'][-1].update(window='end-turn'),
            lambda r:r['generated'][-1].update(ownerId=11),lambda r:r['generated'][-1].update(creatorId=10),
            lambda r:r['generated'][-1].update(combatCardIndex=100),lambda r:r['generated'][-1].update(sameObject=False),
            lambda r:r['generated'][-1].update(masterModelId='SLIMED'),
            lambda r:r['steps'][-1]['history']['moves'][0].update(move='TACKLE_MOVE'),
            lambda r:r['steps'][-1]['history']['damage'][0].update(hpLost=9),
            lambda r:r['steps'][-1]['after'].update(block=5),lambda r:r['steps'][-1]['history']['draws'].clear(),
            lambda r:r['steps'][-1]['history']['generated'].clear(),
            lambda r:r['steps'][-1]['after']['discard'].remove(r['generated'][-1]['cardRef'])])
        source=PROBE.read_text(encoding='utf-8')
        for text in ['generationWindow == "expiry-engage"', 'state.RoundNumber == 2 && pcs.TurnNumber == 2',
                     'monster is LeafSlimeS && move == "GOOP_MOVE" && generated.Count == mediumStatusCount']:
            self.assertIn(text,source)

    def reject(self,case,mutations):
        for i,mutate in enumerate(mutations):
            r=specimen(case);mutate(r)
            with self.subTest(case=case,mutation=i):self.assertFalse(evidence.validate_coupon_result(r,'run-token',case))
    def test_twelve_synthetic_cases_all_four_native_layouts(self):
        self.assertEqual(len(evidence.COUPON_CASES),12)
        for case in evidence.COUPON_CASES:
            for medium in ['LeafSlimeM','TwigSlimeM']:
                for reverse in (False,True):
                    with self.subTest(case=case,medium=medium,reverse=reverse):self.assertTrue(evidence.validate_coupon_result(specimen(case,medium,reverse),'run-token',case))
    def test_native_layout_source_ids_move_order_and_block_allocation_are_strict(self):
        self.reject('CP-elig-R09',[
            lambda r:r.update(enemyTypes=['LeafSlimeS','TwigSlimeS','TwigSlimeM']),
            lambda r:r.update(enemyTypes=['TwigSlimeM','LeafSlimeS','TwigSlimeS']),
            lambda r:r.update(enemyTypes=['LeafSlimeS','TwigSlimeM','LeafSlimeS']),
            lambda r:r['generated'][0].update(sourceEnemy=13),
            lambda r:r['steps'][-1]['history']['moves'].reverse()])
        r=specimen('CP-elig-C10',reverse=True)
        self.assertEqual(r['steps'][-1]['action']['target'],13)
        r['steps'][-1]['action']['target']=11
        self.assertFalse(evidence.validate_coupon_result(r,'run-token','CP-elig-C10'))
        r=specimen('CP-expiry',reverse=True)
        self.assertEqual([(d['blocked'],d['hpLost']) for d in r['transition']['history']['damage']],[(4,0),(1,2)])
        r['transition']['history']['damage'][0].update(blocked=3)
        self.assertFalse(evidence.validate_coupon_result(r,'run-token','CP-expiry'))
    def test_max_not_stack_and_actual_two_coupon_payment(self):
        self.reject('CP-max-preserve',[lambda r:r['steps'][1]['after']['powers'].update(NextAttackDiscount=2),
            lambda r:r['steps'][3]['after']['powers'].update(NextEngageDiscount=2),lambda r:r['steps'][-1]['payments'][0].update(amount=1),
            lambda r:r['steps'][4]['after']['powers'].pop('NextAttackDiscount'),lambda r:r['steps'][4]['after']['powers'].pop('NextEngageDiscount'),
            lambda r:r['steps'][-1]['effects'][0]['coupons'].update(engage=1),lambda r:r['steps'][-1]['effects'][0]['coupons'].update(attack=1)])
    def test_distinct_coupon_kinds_combine_but_cross_kind_max_and_negative_cost_fail(self):
        def false_cross_kind_max(r):
            step=r['steps'][-1]
            step['payments'][0].update(amount=1,energy=step['payments'][0]['energy']-1)
            step['effects'][0].update(spent=1,energy=step['effects'][0]['energy']-1)
            step['after']['energy']-=1;step['action']['events'][-1]['energy']-=1
        for case in ('CP-elig-C10','CP-max-preserve'):
            row=specimen(case);step=row['steps'][-1]
            self.assertEqual(step['payments'][0]['amount'],0)
            self.assertEqual(step['payments'][0]['coupons'],dict(attack=1,engage=1))
            self.assertEqual(step['effects'][0]['coupons'],dict(attack=0,engage=0))
            self.reject(case,[false_cross_kind_max,lambda r:r['steps'][-1]['payments'][0].update(amount=-1)])

    def test_native_invalid_target_keeps_resources_cards_and_pending_coupons(self):
        self.reject('CP-max-preserve',[lambda r:r['steps'][-2]['action']['events'].pop(1),
            lambda r:r['steps'][-2]['payments'].append(dict(cardRef='target',amount=1)),lambda r:r['steps'][-2]['after'].update(energy=26),
            lambda r:r['steps'][-2]['after']['powers'].pop('NextEngageDiscount'),lambda r:r['steps'][-2]['after']['hand'].remove('target'),
            lambda r:r['steps'][-2]['history']['plays'].append(dict(cardRef='target',index=0,count=1))])
    def test_zero_cost_still_paid_native_wrapper_and_consumes_only_eligible_coupon(self):
        self.reject('CP-zero-consume',[lambda r:r['steps'][2]['effects'][0]['coupons'].update(attack=1),
            lambda r:r['steps'][2]['after']['powers'].pop('NextEngageDiscount'),lambda r:r['steps'][2]['payments'].clear(),
            lambda r:r['steps'][3]['payments'][0].update(amount=1),lambda r:r['steps'][3]['effects'][0]['coupons'].update(engage=1)])
    def test_all_seven_identities_and_skill_does_not_consume_attack_coupon(self):
        for code in ['C11','U28','U35','R09']:
            self.reject('CP-elig-'+code,[lambda r:r['steps'][-1]['after']['powers'].pop('NextAttackDiscount')])
        for code in ['B04','C04','C10']:
            self.reject('CP-elig-'+code,[lambda r:r['steps'][-1]['after']['powers'].update(NextAttackDiscount=1)])
        self.reject('CP-elig-R09',[lambda r:r['generated'].clear(),lambda r:r['generated'][0].update(sourceMove='TACKLE_MOVE'),
            lambda r:r['steps'][-1]['history']['generated'].clear(),lambda r:r['steps'][-1]['history']['moves'].pop()])
    def test_beast_same_identity_actual_type_and_no_underlying_engage(self):
        for case in ['CP-beast-attack','CP-beast-skill']:
            self.reject(case,[lambda r:r['steps'][-1]['after']['powers'].pop('NextEngageDiscount'),
                lambda r:r['steps'][-1]['action'].update(sameCard=False),lambda r:r['steps'][-1].update(shape='None'),
                lambda r:r['steps'][-1]['history']['moves'].append(dict(enemy=11,move='TACKLE_MOVE')),
                lambda r:r['steps'][-1]['payments'][0].update(amount=1)])
        self.reject('CP-beast-skill',[lambda r:r['steps'][-1]['after']['powers'].pop('NextAttackDiscount')])
        self.reject('CP-beast-attack',[lambda r:r['steps'][-1]['after']['powers'].update(NextAttackDiscount=1)])
    def test_turn_expiry_requires_native_enemy_phase_draw_and_next_payment(self):
        self.reject('CP-expiry',[lambda r:r['transition']['history']['moves'].clear(),lambda r:r['transition']['history']['draws'].pop(),
            lambda r:r['transition']['after']['powers'].update(NextAttackDiscount=1),lambda r:r['transition']['after']['powers'].update(NextEngageDiscount=1),
            lambda r:r['steps'][-1]['payments'][0].update(amount=1),lambda r:r['transition']['after'].update(hp=80),
            lambda r:r['generated'][0].update(side='Player'),lambda r:r['generated'][0].update(combatCardIndex=100)])
    def test_schema_provenance_and_log_uniqueness(self):
        self.reject('CP-elig-C10',[lambda r:r.update(testMode=True),lambda r:r.update(token='stale'),lambda r:r.update(passed=True),
            lambda r:r['cards'][0].update(masterModelId=None),lambda r:r['cards'][0].update(ownerId=99),
            lambda r:r['steps'][-1]['effects'][0].update(autoPlay=True),lambda r:r['steps'][-1]['payments'][0].update(amount=True)])
        line=evidence.PREFIX+json.dumps(specimen('CP-elig-C10'))
        self.assertTrue(evidence.coupon_contract_evidence(line,'run-token','CP-elig-C10')[1])
        for log in ['',line+'\n'+line,evidence.PREFIX+'{']:
            self.assertFalse(evidence.coupon_contract_evidence(log,'run-token','CP-elig-C10')[1])
    def test_source_uses_real_paid_actions_native_cancel_and_real_conversion_card(self):
        source=PROBE.read_text(encoding='utf-8')
        for text in ['new PlayCardAction(card,target)','ActionQueueSynchronizer.RequestEnqueue(action)','await action.CompletionTask',
                     'action.BeforeCancelled','Hook.AfterEnergySpent','Hook.BeforeCardPlayed','await original;','PlayerCmd.EndTurn(p,canBackOut:false)',
                     'state.CreateCard<Volibear_R29>(p)','CardGeneratedEntry','NetCombatCard.FromModel(card)']:
            self.assertIn(text,source)
        for text in ['NextAttackDiscount.Grant(', 'NextEngageDiscount.Grant(', 'BeastForms.Convert(', 'PowerCmd.Apply<',
                     'AddModifier(', 'CardCmd.AutoPlay(', 'SetMoveImmediate(', 'TryModifyEnergyCostInCombat(', '.SpendResources(']:
            self.assertNotIn(text,source)


if __name__=='__main__':unittest.main()
