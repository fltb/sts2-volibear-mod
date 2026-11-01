"""Independent synthetic receipts; no claim of real U12 acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tools/primal_evidence.py'
PROBE=ROOT/'src/Volibear/PrimalContractProbe.cs'
spec=importlib.util.spec_from_file_location('primal_gate',MODULE);evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)


def _role_order_receipt(case,medium='TwigSlimeM'):
    extra=case=='U12-native-extra-turn';seed=[f'starter-{i}' for i in range(10)]
    s=dict(round=1,turn=1,side='Player',phase='Play',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},
           relics=['HuntersHeart','PaelsEye'] if extra else ['HuntersHeart'],eyeUsed=False if extra else None,
           hand=[],draw=seed[:],discard=[],play=[],exhaust=[],removed=[])
    r=dict(token='run-token',variant=case,scenario='primal-contract',completed=True,gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           acceptance=evidence.ACCEPTANCE,fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-and-deck-order-explicit',character='VolibearCharacter',
           playerId=10,enemyIds=[11,12,13],enemyTypes=['LeafSlimeS','TwigSlimeS',medium],cards=[],generated=[],initial=deepcopy(s),actions=[],setups=[],transitions=[],
           final=None,payments=[],effects=[],boundaries=[],extraTurns=[],autoPhases=[])
    roles={'strength-a':'R06','primal':'U12'}
    if extra:
        roles.update(mayhem='MAYHEM',**{'extra-thunder':'C24','expired-thunder':'C24'})
        for label in ['turn2','extra','turn4']:
            for i in range(5):roles[f'{label}-padding-{i}']='B02'
    else:roles.update({'strength-b':'R06','native-thunder':'C24','ordinary-attack':'B01'})
    for i,code in enumerate(['B01']*4+['B02']*4+['B03','B04']):
        r['cards'].append(dict(cardRef=seed[i],modelId='VOLIBEAR_'+code,upgraded=False,combatCardIndex=100+i,sameObject=True,ownerId=10,masterIndex=i,masterModelId='VOLIBEAR_'+code))
    for i,(ref,code) in enumerate(roles.items()):
        r['cards'].append(dict(cardRef=ref,modelId=code if code=='MAYHEM' else 'VOLIBEAR_'+code,upgraded=False,combatCardIndex=110+i,sameObject=True,ownerId=10,masterIndex=-1,masterModelId=None))
    def hist():return dict(plays=[],finished=[],exhausts=[],draws=[],moves=[],damage=[],generated=[])
    def win(state):return dict(round=state['round'],turn=state['turn'],side=state['side'],strength=state['powers'].get('StrengthPower',0),
                              primal=state['powers'].get('PrimalThunderPower',0),unify=state['powers'].get('UnifyPower',0),eyeUsed=state['eyeUsed'])
    def hit(target,n,blocked=0,card=None,props=8):return dict(target=target,cardRef=card,hpLost=n,blocked=blocked,props=props)
    def fx(ref,cost,auto,state):
        row=dict(cardRef=ref,index=0,count=1,autoPlay=auto,playId=100+len(r['effects']),spent=cost,energy=state['energy'],window=win(state))
        r['effects'].append(deepcopy(row));return row
    # Hand-authored paid outcomes, independent from the oracle's arithmetic.
    spec_rows=[('strength-a',2,dict(StrengthPower=3,UnifyPower=3),10)]
    if extra:spec_rows.append(('mayhem',2,dict(StrengthPower=3,UnifyPower=3,MayhemPower=1),10))
    else:spec_rows += [('primal',1,dict(StrengthPower=3,UnifyPower=3,PrimalThunderPower=3),10),
                       ('strength-b',2,dict(StrengthPower=6,UnifyPower=6,PrimalThunderPower=3),20),
                       ('native-thunder',1,dict(StrengthPower=6,UnifyPower=6,PrimalThunderPower=3),20),
                       ('ordinary-attack',1,dict(StrengthPower=6,UnifyPower=6,PrimalThunderPower=3),20)]
    for i,(ref,cost,powers,block) in enumerate(spec_rows):
        s['hand'].append(ref);before=deepcopy(s);s['energy']-=cost
        pay=dict(cardRef=ref,amount=cost,energy=s['energy'],window=win(s));r['payments'].append(deepcopy(pay));effect=fx(ref,cost,False,s)
        s['hand'].remove(ref);s['powers']=powers;s['block']=block;h=hist();h['plays']=[dict(cardRef=ref,index=0,count=1,autoPlay=False)];h['finished']=[dict(cardRef=ref,autoPlay=False)]
        if ref in ['primal','native-thunder']:
            card=s['draw'].pop(0);s['hand'].append(card);h['draws']=[dict(cardRef=card,fromHandDraw=False)]
        if ref=='native-thunder':s['enemyHp']=[485]*3;h['damage']=[hit(e,15,card=ref,props=4) for e in [11,12,13]]
        elif ref=='ordinary-attack':s['enemyHp']=[467,485,485];h['damage']=[hit(11,18,card=ref)]
        if ref=='mayhem':s['removed'].append(ref)
        elif ref in ['strength-a','primal','strength-b']:s['exhaust'].append(ref);h['exhausts']=[ref]
        else:s['discard'].append(ref)
        r['actions'].append(dict(label=ref,cardRef=ref,before=before,after=deepcopy(s),
                                 action=dict(id=i,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context='GameActionPlayerChoiceContext',target=11 if ref=='ordinary-attack' else None,sameCard=True,
                                             events=[dict(name='before-executed',state='Executing',id=i,energy=before['energy']),dict(name='after-finished',state='Finished',id=i,energy=s['energy'])]),payments=[pay],effects=[effect],history=h))
    if not extra:r['final']=deepcopy(s);return r
    gen=[f'generated-{i}' for i in range(2 if medium=='LeafSlimeM' else 1)]
    for i,ref in enumerate(gen):
        r['generated'].append(dict(cardRef=ref,modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=200+i,sameObject=True,ownerId=10,
                                   masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=13,sourceType=medium,sourceMove='STICKY_SHOT' if medium=='LeafSlimeM' else 'STICKY_SHOT_MOVE',round=1,turn=1,side='Enemy'))
    goop='generated-'+str(len(gen))
    r['generated'].append(dict(cardRef=goop,modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=200+len(gen),sameObject=True,ownerId=10,
                               masterModelId=None,creatorId=None,pile='Discard',sourceEnemy=11,sourceType='LeafSlimeS',sourceMove='GOOP_MOVE',round=2,turn=3,side='Enemy'))
    pad2=[f'turn2-padding-{i}' for i in range(5)];pad3=[f'extra-padding-{i}' for i in range(5)];pad4=[f'turn4-padding-{i}' for i in range(5)]
    def boundary(round_no,turn,side,primal,after_primal,eye):
        b=dict(round=round_no,turn=turn,side=side,strength=3,primal=primal,unify=3,eyeUsed=eye)
        a=deepcopy(b);a['primal']=after_primal
        return dict(hook='Hook.AfterTurnEnd',side=side,participants=[10] if side=='Player' else [11,12,13],before=b,after=a)
    descriptors=[('turn2','primal',pad2,'natural-enemy-before-primal'),('extra','extra-thunder',pad3,'paels-eye-extra-player-turn'),('turn4','expired-thunder',pad4,'natural-enemy-expiry')]
    for i,(label,ref,padding,transition_label) in enumerate(descriptors):
        before=deepcopy(s);s['draw']=padding+[ref]+s['draw']
        r['setups'].append(dict(label=label,operation='CardPileCmd.Add-Top-five-padding-before-native-auto-target',target=ref,before=before,after=deepcopy(s)))
        before=deepcopy(s);h=hist();extras=[]
        if i==0:
            s.update(round=2,turn=2,phase='AutoPrePlay',energy=3,block=0,hand=pad2[:],draw=['primal']+seed,discard=gen[:])
            ends=[boundary(1,1,'Player',0,0,False),boundary(1,1,'Enemy',0,0,False)]
            h['moves']=[dict(enemy=11,move='TACKLE_MOVE'),dict(enemy=12,move='TACKLE_MOVE'),dict(enemy=13,move='STICKY_SHOT' if medium=='LeafSlimeM' else 'STICKY_SHOT_MOVE')]
            h['damage']=[hit(10,0,3),hit(10,0,4)];h['generated']=[dict(cardRef=g,creatorId=None) for g in gen]
        elif i==1:
            s.update(round=2,turn=3,phase='AutoPrePlay',energy=3,block=0,hand=pad3[:],draw=['extra-thunder']+seed[1:],eyeUsed=True,
                     exhaust=['strength-a','primal']+pad2+[seed[0]])
            h['exhausts']=pad2+[seed[0]];ends=[boundary(2,2,'Player',3,3,False)]
            b=dict(round=2,turn=3,side='Player',strength=3,primal=3,unify=3,eyeUsed=False);a=deepcopy(b);a['eyeUsed']=True
            extras=[dict(hook='Hook.AfterTakingExtraTurn',playerId=10,before=b,after=a)]
        else:
            s.update(round=3,turn=4,phase='AutoPrePlay',energy=3,block=0,hp=68 if medium=='LeafSlimeM' else 65,hand=pad4[:],draw=['expired-thunder']+seed[2:],
                     discard=gen+['extra-thunder']+pad3+[seed[1],goop],powers=dict(StrengthPower=3,UnifyPower=3,MayhemPower=1))
            ends=[boundary(2,3,'Player',3,3,True),boundary(2,3,'Enemy',3,0,True)]
            h['moves']=[dict(enemy=11,move='GOOP_MOVE'),dict(enemy=12,move='TACKLE_MOVE'),dict(enemy=13,move='CLUMP_SHOT' if medium=='LeafSlimeM' else 'POKEY_POUNCE_MOVE')]
            h['damage']=[hit(10,4),hit(10,8 if medium=='LeafSlimeM' else 11)]
            h['generated']=[dict(cardRef=goop,creatorId=None)]
        h['draws']=[dict(cardRef=p,fromHandDraw=True) for p in padding];auto_before=deepcopy(s);effect=fx(ref,0,True,s)
        s['draw']=seed[i+1:];s['hand'].append(seed[i]);ah=hist()
        ah['plays']=[dict(cardRef=ref,index=0,count=1,autoPlay=True)];ah['finished']=[dict(cardRef=ref,autoPlay=True)];ah['draws']=[dict(cardRef=seed[i],fromHandDraw=False)]
        if i==0:s['powers']['PrimalThunderPower']=3;s['exhaust'].append('primal');ah['exhausts']=['primal']
        else:
            s['enemyHp']=[488 if i==1 else 479]*3;s['discard'].append(ref)
            ah['damage']=[hit(e,12 if i==1 else 9,card=ref,props=4) for e in [11,12,13]]
        auto=dict(hook='MayhemPower.AfterAutoPrePlayPhaseEntered',context='HookPlayerChoiceContext',before=auto_before,after=deepcopy(s),history=ah,payments=[],effects=[effect])
        s['phase']='Play'
        for key in h:h[key]+=ah[key]
        r['transitions'].append(dict(label=transition_label,before=before,after=deepcopy(s),history=h,payments=[],effects=[effect],boundaries=deepcopy(ends),extraTurns=deepcopy(extras),autoPhases=[deepcopy(auto)]))
        r['boundaries']+=deepcopy(ends);r['extraTurns']+=deepcopy(extras);r['autoPhases'].append(deepcopy(auto))
    r['final']=deepcopy(s);return r


def specimen(case,medium='TwigSlimeM',reverse=False):
    # Receipt builder above uses semantic role slots, not native encounter ordering.
    # SlimesWeak places the medium in the center and randomizes the two distinct smalls.
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
            source_for_amount={3:11,4:12,8:13,11:13}
            damage=result['damage'];out=[];index=0
            while index<len(damage):
                end=index+1;row=damage[index]
                while end<len(damage) and (damage[end]['cardRef'],damage[end]['props'])==(row['cardRef'],row['props']):end+=1
                group=damage[index:end]
                if row['cardRef'] is None:group.sort(key=lambda d:new_ids[source_for_amount[d['hpLost']+d['blocked']]])
                elif row['props']==4:group.sort(key=lambda d:d['target'])
                out+=group;index=end
            result['damage']=out
        return result
    return visit(_role_order_receipt(case,medium))


class PrimalEvidenceTests(unittest.TestCase):
    def reject(self,case,mutations):
        for i,mutate in enumerate(mutations):
            r=specimen(case);mutate(r)
            with self.subTest(case=case,mutation=i):self.assertFalse(evidence.validate_primal_result(r,'run-token',case))
    def test_two_frozen_cases_all_four_native_slimesweak_layouts(self):
        for case in evidence.PRIMAL_CASES:
            for medium in ['LeafSlimeM','TwigSlimeM']:
                for reverse in (False,True):
                    with self.subTest(case=case,medium=medium,reverse=reverse):self.assertTrue(evidence.validate_primal_result(specimen(case,medium,reverse),'run-token',case))
    def test_impossible_layouts_wrong_role_ids_and_reordered_moves_are_rejected(self):
        self.reject('U12-native-extra-turn',[
            lambda r:r.update(enemyTypes=['LeafSlimeS','TwigSlimeS','TwigSlimeM']),
            lambda r:r.update(enemyTypes=['TwigSlimeM','LeafSlimeS','TwigSlimeS']),
            lambda r:r.update(enemyTypes=['LeafSlimeS','TwigSlimeM','LeafSlimeS']),
            lambda r:r['generated'][0].update(sourceEnemy=13),
            lambda r:r['transitions'][0]['history']['moves'].reverse(),
            lambda r:r['transitions'][2]['history']['damage'].__setitem__(0,deepcopy(r['transitions'][2]['history']['damage'][1]))])
        r=specimen('U12-paid-snapshot',reverse=True)
        self.assertEqual(r['actions'][-1]['action']['target'],13)
        r['actions'][-1]['action']['target']=11
        self.assertFalse(evidence.validate_primal_result(r,'run-token','U12-paid-snapshot'))
    def test_paid_snapshot_does_not_follow_later_strength_or_boost_ordinary_attack(self):
        self.reject('U12-paid-snapshot',[lambda r:r['actions'][2]['after']['powers'].update(PrimalThunderPower=6),
            lambda r:r['actions'][3]['history']['damage'][0].update(hpLost=18),lambda r:r['actions'][4]['history']['damage'][0].update(hpLost=21),
            lambda r:r['actions'][2]['after']['powers'].update(StrengthPower=3),lambda r:r['actions'][1]['history']['draws'].clear(),
            lambda r:r['actions'][1]['payments'][0].update(amount=0),lambda r:r['effects'][1].update(autoPlay=True),
            lambda r:r['actions'][1]['effects'][0]['window'].update(primal=3)])
    def test_mayhem_must_follow_actual_normal_five_draw_and_not_fake_paid_u12(self):
        self.reject('U12-native-extra-turn',[lambda r:r['transitions'][0]['history']['draws'].pop(0),
            lambda r:r['autoPhases'][0]['before']['hand'].pop(),lambda r:r['autoPhases'][0]['before'].update(phase='Play'),
            lambda r:r['autoPhases'][0].update(context='GameActionPlayerChoiceContext'),
            lambda r:r['transitions'][0]['effects'][0].update(autoPlay=False),lambda r:r['transitions'][0]['effects'][0].update(spent=1),
            lambda r:r['transitions'][0]['payments'].append(dict(cardRef='primal',amount=1)),
            lambda r:r['setups'][0]['after']['draw'].__setitem__(0,'primal'),lambda r:r['autoPhases'][0].update(hook='injected-callback')])
    def test_extra_turn_preserves_round_primal_and_has_no_enemy_side_end(self):
        self.reject('U12-native-extra-turn',[lambda r:r['transitions'][1]['after'].update(round=3),lambda r:r['transitions'][1]['after'].update(turn=2),
            lambda r:r['transitions'][1]['after']['powers'].pop('PrimalThunderPower'),lambda r:r['transitions'][1]['boundaries'].append(deepcopy(r['boundaries'][1])),
            lambda r:r['transitions'][1]['history']['moves'].append(dict(enemy=11,move='TACKLE_MOVE')),
            lambda r:r['extraTurns'][0]['after'].update(eyeUsed=False),lambda r:r['transitions'][1]['history']['exhausts'].clear(),
            lambda r:r['transitions'][1]['history']['damage'][0].update(hpLost=9)])
    def test_real_enemy_end_clears_primal_and_native_clump_is_not_suppressed(self):
        self.reject('U12-native-extra-turn',[lambda r:r['transitions'][2]['boundaries'][-1]['after'].update(primal=3),
            lambda r:r['transitions'][2]['history']['moves'].pop(),lambda r:r['transitions'][2]['after'].update(hp=80),
            lambda r:r['transitions'][2]['history']['damage'][-1].update(hpLost=12),lambda r:r['final']['powers'].update(PrimalThunderPower=3),
            lambda r:r['autoPhases'][2]['before']['powers'].update(PrimalThunderPower=3),lambda r:r['transitions'][2]['after'].update(round=2)])
    def test_second_enemy_leaf_goop_is_exact_not_repeated_tackle_or_generic_generation(self):
        self.reject('U12-native-extra-turn',[
            lambda r:r['generated'].pop(),
            lambda r:r['generated'][-1].update(sourceMove='TACKLE_MOVE'),
            lambda r:r['generated'][-1].update(sourceType='TwigSlimeM',sourceEnemy=12),
            lambda r:r['generated'][-1].update(round=1,turn=1),
            lambda r:r['generated'][-1].update(side='Player'),
            lambda r:r['generated'][-1].update(creatorId=10),
            lambda r:r['transitions'][2]['history']['generated'].clear(),
            lambda r:r['transitions'][2]['history']['moves'][0].update(move='TACKLE_MOVE'),
            lambda r:r['transitions'][2]['history']['damage'].insert(0,dict(target=10,cardRef=None,hpLost=3,blocked=0,props=8)),
            lambda r:r['transitions'][2]['after']['discard'].remove(r['generated'][-1]['cardRef'])])
        source=PROBE.read_text(encoding='utf-8')
        for text in ['activeTransition == "natural-enemy-expiry"', 'pcs.TurnNumber == 3', 'monster is LeafSlimeS && move == "GOOP_MOVE"',
                     'generated.Count == mediumStatusCount', 'generated.Count < mediumStatusCount', 'PRIMAL_GENERATION_DIAGNOSTIC']:
            self.assertIn(text,source)

    def test_identity_generated_status_and_native_power_card_retirement(self):
        self.reject('U12-native-extra-turn',[lambda r:r['generated'].clear(),lambda r:r['generated'][0].update(creatorId=10),
            lambda r:r['generated'][0].update(side='Player'),lambda r:r['generated'][0].update(combatCardIndex=100),
            lambda r:r['actions'][1]['after']['removed'].clear(),lambda r:r['actions'][1]['after']['discard'].append('mayhem'),
            lambda r:r['cards'][10].update(sameObject=False),lambda r:r['cards'][0].update(masterModelId=None),
            lambda r:r['cards'][1].update(combatCardIndex=100)])
    def test_all_global_receipts_and_schema_are_required(self):
        self.reject('U12-native-extra-turn',[lambda r:r.update(token='stale'),lambda r:r.update(testMode=True),lambda r:r.update(passed=True),
            lambda r:r['payments'].clear(),lambda r:r['effects'][3].update(playId=r['effects'][2]['playId']),lambda r:r['boundaries'].pop(),
            lambda r:r['autoPhases'].pop(),lambda r:r['extraTurns'].clear(),lambda r:r['actions'][0]['action'].update(sameCard=False)])
        row=evidence.PREFIX+json.dumps(specimen('U12-paid-snapshot'))
        self.assertTrue(evidence.primal_contract_evidence(row,'run-token','U12-paid-snapshot')[1])
        self.assertFalse(evidence.primal_contract_evidence(row+'\n'+row,'run-token','U12-paid-snapshot')[1])
        self.assertFalse(evidence.primal_contract_evidence(evidence.PREFIX+'{','run-token','U12-paid-snapshot')[1])
    def test_probe_observes_real_native_callbacks_without_invoking_them(self):
        source=PROBE.read_text(encoding='utf-8')
        for text in ['new PlayCardAction(card,target)', 'ActionQueueSynchronizer.RequestEnqueue(action)', 'await action.CompletionTask',
                     'RelicCmd.Obtain<PaelsEye>(p)', 'state.CreateCard<Mayhem>(p)', 'PlayerCmd.EndTurn(p,canBackOut:false)',
                     'typeof(MayhemPower),nameof(MayhemPower.AfterAutoPrePlayPhaseEntered)', 'typeof(Hook),nameof(Hook.AfterTakingExtraTurn)',
                     'typeof(Hook),nameof(Hook.AfterTurnEnd)', 'await original;', 'CardPilePosition.Top', 'CardExhaustedEntry', 'HasBeenRemovedFromState']:
            self.assertIn(text,source)
        for text in ['PowerCmd.Apply<', 'CardCmd.AutoPlay(', 'CardPileCmd.AutoPlayFromDrawPile(', '.ShouldTakeExtraTurn(',
                     '.AfterTakingExtraTurn(', '.AfterAutoPrePlayPhaseEntered(', 'SwitchFromPlayerToEnemySide(', 'MockExtraTurnPower',
                     'CardCmd.Exhaust(', 'SetValue(', 'SetMoveImmediate(', 'RemoveFromState(', 'HasBeenRemovedFromState =']:
            self.assertNotIn(text,source)


if __name__=='__main__':unittest.main()
