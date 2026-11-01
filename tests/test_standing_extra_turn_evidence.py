"""Hand-authored native receipt expectations; synthetic tests are not runtime acceptance."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]/'tools'
spec=importlib.util.spec_from_file_location('standing_gate',HERE/'standing_extra_turn_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def specimen(variant,medium='TwigSlimeM',reverse=False):
    up=variant=='U03-upgraded-extra-turn';decay,entry,extra_block=(3,12,37) if up else (6,8,34)
    # Frozen expected native blocks, not values computed from the oracle.
    enemy_block,normal_block={('LeafSlimeM',False):(22,16),('TwigSlimeM',False):(19,13),('LeafSlimeM',True):(25,22),('TwigSlimeM',True):(22,19)}[medium,up]
    types=['TwigSlimeS',medium,'LeafSlimeS'] if reverse else ['LeafSlimeS',medium,'TwigSlimeS'];ids=[21,22,23];pid=20;leaf=23 if reverse else 21
    seed=[f'starter-{i}' for i in range(9,-1,-1)];medium_refs=[f'generated-{i}' for i in range(2 if medium=='LeafSlimeM' else 1)];goop='generated-'+str(len(medium_refs))
    pads=[[f'{label}-padding-{i}' for i in range(5)] for label in ('turn2','extra','turn4')]
    s=dict(round=1,turn=1,side='Player',phase='Play',energy=30,hp=80,block=0,enemyHp=[500]*3,powers={},relics=['HuntersHeart','PaelsEye'],eyeUsed=False,standingSame=None,
           hand=[],draw=seed[:],discard=[],play=[],exhaust=[],removed=[])
    r=dict(token='run-token',variant=variant,scenario='standing-extra-turn',schema='standing-extra-turn-v1',completed=True,gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           acceptance=gate.ACCEPTANCE,fixture='fresh-native-three-slimes-energy30-enemyHp500-created-cards-five-padding-native-block40-explicit',character='VolibearCharacter',
           playerId=pid,enemyIds=ids,enemyTypes=types,cards=[],generated=[],initial=deepcopy(s),actions=[],setups=[],blockFixture=None,transitions=[],final=None,payments=[],effects=[],boundaries=[],extraTurns=[],autoPhases=[],blockGains=[entry,40-entry],clearPreventers=[],blockTrace=[],powerLifecycle=[])
    for i,code in enumerate(['B01']*4+['B02']*4+['B03','B04']):r['cards'].append(dict(cardRef=f'starter-{i}',modelId='VOLIBEAR_'+code,upgraded=False,combatCardIndex=100+i,sameObject=True,ownerId=pid,masterIndex=i,masterModelId='VOLIBEAR_'+code))
    roles={'mayhem':'MAYHEM','standing':'VOLIBEAR_U03','extra-thunder':'VOLIBEAR_C24','normal-thunder':'VOLIBEAR_C24'}
    roles.update({c:'VOLIBEAR_B02' for group in pads for c in group})
    for i,(ref,model) in enumerate(roles.items()):r['cards'].append(dict(cardRef=ref,modelId=model,upgraded=ref=='standing' and up,combatCardIndex=110+i,sameObject=True,ownerId=pid,masterIndex=-1,masterModelId=None))
    for i,ref in enumerate(medium_refs+[goop]):
        last=ref==goop;r['generated'].append(dict(cardRef=ref,modelId='SLIMED',type='Slimed',cardType='Status',combatCardIndex=200+i,sameObject=True,ownerId=pid,masterModelId=None,creatorId=None,pile='Discard',
            sourceEnemy=leaf if last else 22,sourceType='LeafSlimeS' if last else medium,sourceMove='GOOP_MOVE' if last else 'STICKY_SHOT' if medium=='LeafSlimeM' else 'STICKY_SHOT_MOVE',round=2 if last else 1,turn=3 if last else 1,side='Enemy'))
    def window(state):return dict(round=state['round'],turn=state['turn'],side=state['side'],block=state['block'],standing=state['powers'].get('StandingPower',0),standingSame=state['standingSame'],eyeUsed=state['eyeUsed'])
    def h():return dict(plays=[],finished=[],exhausts=[],draws=[],moves=[],damage=[],generated=[],ordered=[])
    def fx(ref,spent,auto,state):
        row=dict(cardRef=ref,index=0,count=1,autoPlay=auto,playId=100+len(r['effects']),spent=spent,energy=state['energy'],window=window(state));r['effects'].append(deepcopy(row));return row
    def hit(target,amount,blocked=0,ref=None,props=8,dealer=None,round_no=1,turn=1,side='Enemy'):return dict(target=target,cardRef=ref,hpLost=amount,blocked=blocked,props=props,dealer=dealer,combatSame=True,round=round_no,turn=turn,side=side)
    def boundary(round_no,turn,side,block,standing,eye):
        w=dict(round=round_no,turn=turn,side=side,block=block,standing=standing,standingSame=True if standing else None,eyeUsed=eye)
        return dict(hook='Hook.AfterTurnEnd',side=side,participants=[pid] if side=='Player' else ids,before=w,after=deepcopy(w))
    s['hand']=['mayhem'];before=deepcopy(s);s['energy']=28;payment=dict(cardRef='mayhem',amount=2,energy=28,window=window(s));r['payments']=[payment];effect=fx('mayhem',2,False,s)
    s.update(hand=[],powers={'MayhemPower':1},removed=['mayhem']);history=h();history['plays']=[dict(cardRef='mayhem',index=0,count=1,autoPlay=False)];history['finished']=[dict(cardRef='mayhem',autoPlay=False)]
    r['actions']=[dict(label='mayhem',cardRef='mayhem',before=before,after=deepcopy(s),action=dict(id=7,state='Finished',type='PlayCardAction',actionType='CombatPlayPhaseOnly',context='GameActionPlayerChoiceContext',target=None,sameCard=True,
        events=[dict(name='before-executed',state='Executing',id=7,energy=30),dict(name='after-finished',state='Finished',id=7,energy=28)]),payments=[deepcopy(payment)],effects=[effect],history=history)]
    for i,(label,ref,transition) in enumerate([('turn2','standing','natural-enemy-before-standing'),('extra','extra-thunder','paels-eye-extra-player-turn'),('turn4','normal-thunder','natural-enemy-after-extra')]):
        if i==1:
            before=deepcopy(s);s['block']=40;r['blockFixture']=dict(operation='CreatureCmd.GainBlock-Unpowered-to40',amount=40-entry,before=before,after=deepcopy(s),blockGains=[40-entry],clearPreventers=[])
        before=deepcopy(s);s['draw']=pads[i]+[ref]+s['draw'];r['setups'].append(dict(label=label,operation='CardPileCmd.Add-Top-five-padding-before-native-auto-target',target=ref,before=before,after=deepcopy(s)))
        before=deepcopy(s);history=h();extras=[]
        if i==0:
            s.update(round=2,turn=2,phase='AutoPrePlay',energy=3,hp=73,block=0,hand=pads[0][:],draw=['standing']+seed,discard=medium_refs[:])
            ends=[boundary(1,1,'Player',0,0,False),boundary(1,1,'Enemy',0,0,False)]
            for actor,kind in zip(ids,types):
                move='STICKY_SHOT' if kind=='LeafSlimeM' else 'STICKY_SHOT_MOVE' if kind=='TwigSlimeM' else 'TACKLE_MOVE'
                history['moves'].append(dict(enemy=actor,move=move))
                if kind=='LeafSlimeS':history['damage'].append(hit(pid,3,dealer=actor))
                elif kind=='TwigSlimeS':history['damage'].append(hit(pid,4,dealer=actor))
            history['generated']=[dict(cardRef=c,creatorId=None) for c in medium_refs]
        elif i==1:
            s.update(round=2,turn=3,phase='AutoPrePlay',energy=3,block=extra_block,hand=pads[1][:],draw=['extra-thunder']+seed,exhaust=pads[0][:],eyeUsed=True)
            history['exhausts']=pads[0][:];ends=[boundary(2,2,'Player',40,decay,False)]
            w=dict(round=2,turn=3,side='Player',block=40,standing=decay,standingSame=True,eyeUsed=False);a=deepcopy(w);a['eyeUsed']=True
            extras=[dict(hook='Hook.AfterTakingExtraTurn',playerId=pid,before=w,after=a)]
        else:
            s.update(round=3,turn=4,phase='AutoPrePlay',energy=3,block=normal_block,hand=pads[2][:],draw=['normal-thunder']+seed[1:],discard=medium_refs+['extra-thunder']+pads[1]+[seed[0],goop])
            ends=[boundary(2,3,'Player',extra_block,decay,True),boundary(2,3,'Enemy',enemy_block,decay,True)]
            for actor,kind in zip(ids,types):
                move={'LeafSlimeS':'GOOP_MOVE','TwigSlimeS':'TACKLE_MOVE','LeafSlimeM':'CLUMP_SHOT','TwigSlimeM':'POKEY_POUNCE_MOVE'}[kind]
                history['moves'].append(dict(enemy=actor,move=move))
                if kind!='LeafSlimeS':history['damage'].append(hit(pid,0,{'TwigSlimeS':4,'LeafSlimeM':8,'TwigSlimeM':11}[kind],dealer=actor,round_no=2,turn=3))
            history['generated']=[dict(cardRef=goop,creatorId=None)]
        if i!=1:
            round_no,turn=(1,1) if i==0 else (2,3)
            for move_row in history['moves']:
                actor=move_row['enemy'];name=move_row['move']
                if name in ('STICKY_SHOT','STICKY_SHOT_MOVE','GOOP_MOVE'):
                    for card in medium_refs if i==0 else [goop]:
                        history['ordered'].append(dict(kind='generated',data=dict(cardRef=card,creatorId=None,ownerId=pid,combatSame=True,round=round_no,turn=turn,side='Enemy')))
                else:
                    history['ordered'] += [dict(kind='damage',data=deepcopy(d)) for d in history['damage'] if d['dealer']==actor]
                history['ordered'].append(dict(kind='move',data=dict(**move_row,combatSame=True,round=round_no,turn=turn,side='Enemy')))
        history['draws']=[dict(cardRef=c,fromHandDraw=True) for c in pads[i]];auto_before=deepcopy(s);effect=fx(ref,0,True,s);ah=h()
        ah['plays']=[dict(cardRef=ref,index=0,count=1,autoPlay=True)];ah['finished']=[dict(cardRef=ref,autoPlay=True)]
        if i==0:s.update(block=entry,draw=seed[:],powers={'MayhemPower':1,'StandingPower':decay},standingSame=True,removed=['mayhem','standing'])
        else:
            s['hand'].append(seed[i-1]);s['draw']=seed[i:];s['discard'].append(ref);s['enemyHp']=[494 if i==1 else 488]*3
            ah['draws']=[dict(cardRef=seed[i-1],fromHandDraw=False)];ah['damage']=[hit(enemy,6,ref=ref,props=4,dealer=pid,round_no=s['round'],turn=s['turn'],side='Player') for enemy in ids]
        ah['ordered']=[dict(kind='damage',data=deepcopy(d)) for d in ah['damage']]
        gains=[entry] if i==0 else []
        phase=dict(hook='MayhemPower.AfterAutoPrePlayPhaseEntered',context='HookPlayerChoiceContext',before=auto_before,after=deepcopy(s),history=ah,payments=[],effects=[effect],blockGains=gains,clearPreventers=[])
        for key in history:history[key]+=ah[key]
        s['phase']='Play';r['transitions'].append(dict(label=transition,before=before,after=deepcopy(s),history=history,payments=[],effects=[effect],boundaries=deepcopy(ends),extraTurns=deepcopy(extras),autoPhases=[deepcopy(phase)],blockGains=gains,clearPreventers=[]))
        r['boundaries']+=deepcopy(ends);r['extraTurns']+=deepcopy(extras);r['autoPhases'].append(deepcopy(phase))
    # Every actual setter call plus the native changed event, including unchanged zero writes.
    trace=[]
    def row(kind,before,after,clear_id,round_no,turn,side):
        trace.append(dict(sequence=len(trace)+1,kind=kind,clearId=clear_id,before=before,after=after,ownerId=pid,combatSame=True,round=round_no,turn=turn,side=side))
    row('block-write',0,0,None,1,1,'Enemy');row('block-write',0,0,None,1,1,'Enemy')
    row('clear-enter',0,0,1,2,2,'Player');row('block-write',0,0,1,2,2,'Player');row('clear-complete',0,0,1,2,2,'Player')
    row('block-write',0,entry,None,2,2,'Player');row('block-changed',0,entry,None,2,2,'Player')
    row('block-write',entry,40,None,2,2,'Player');row('block-changed',entry,40,None,2,2,'Player')
    row('clear-enter',40,40,2,2,3,'Player');row('block-write',40,extra_block,2,2,3,'Player');row('block-changed',40,extra_block,2,2,3,'Player');row('clear-complete',40,extra_block,2,2,3,'Player')
    intermediate=(33 if up else 30) if reverse else {('LeafSlimeM',False):26,('TwigSlimeM',False):23,('LeafSlimeM',True):29,('TwigSlimeM',True):26}[medium,up]
    row('block-write',extra_block,intermediate,None,2,3,'Enemy');row('block-changed',extra_block,intermediate,None,2,3,'Enemy')
    row('block-write',intermediate,enemy_block,None,2,3,'Enemy');row('block-changed',intermediate,enemy_block,None,2,3,'Enemy')
    row('clear-enter',enemy_block,enemy_block,3,3,4,'Player');row('block-write',enemy_block,normal_block,3,3,4,'Player');row('block-changed',enemy_block,normal_block,3,3,4,'Player');row('clear-complete',enemy_block,normal_block,3,3,4,'Player')
    r['blockTrace']=trace
    lifecycle=[]
    for kind,amount,before,requested,source in [('apply-enter',0,None,decay,False),('amount-write',decay,0,None,False),('collection-added',decay,None,None,False),('apply-complete',decay,None,None,False),('after-applied-enter',decay,None,None,True),('after-applied-complete',decay,None,None,True)]:
        lifecycle.append(dict(sequence=len(lifecycle)+1,kind=kind,powerRef='standing-power-1',epoch=1,type='StandingPower',ownerId=pid,ownerSame=True,combatSame=True,round=2,turn=2,side='Player',amount=amount,
            before=before,requested=requested,sourceCard='standing' if source else None,sourceOwnerId=pid if source else None,sourceSame=True if source else None,sourceUpgraded=up if source else None,sourceOwnerSame=True if source else None,applierId=pid if source else None,applierSame=True if source else None))
    r['powerLifecycle']=lifecycle
    r['final']=deepcopy(s);return r

class StandingExtraTurnTests(unittest.TestCase):
    def reject(self,mutations):
        for variant in gate.STANDING_CASES:
            for i,mutation in enumerate(mutations):
                raw=specimen(variant);mutation(raw)
                with self.subTest(variant=variant,mutation=i):self.assertFalse(gate.validate_result(raw,'run-token',variant))
    def test_base_upgraded_all_four_native_layouts(self):
        for variant in gate.STANDING_CASES:
            for medium in ('LeafSlimeM','TwigSlimeM'):
                for reverse in (False,True):
                    with self.subTest(variant=variant,medium=medium,reverse=reverse):self.assertTrue(gate.validate_result(specimen(variant,medium,reverse),'run-token',variant))
    def test_real_extra_turn_identity_and_single_start_decay(self):
        self.reject([lambda r:r['transitions'][1]['after'].update(round=3),lambda r:r['transitions'][1]['after'].update(turn=2),
            lambda r:r['transitions'][1]['after'].update(block=40),lambda r:r['transitions'][1]['after'].update(block=28),
            lambda r:r['transitions'][1]['after'].update(block=40-2*r['transitions'][1]['after']['powers']['StandingPower']),
            lambda r:r['transitions'][1]['after'].update(standingSame=False),lambda r:r['extraTurns'].clear(),
            lambda r:r['extraTurns'][0].update(playerId=21),lambda r:r['extraTurns'][0]['after'].update(eyeUsed=False),
            lambda r:r['transitions'][1]['boundaries'].append(deepcopy(r['boundaries'][1])),
            lambda r:r['transitions'][1]['history']['moves'].append(dict(enemy=21,move='TACKLE_MOVE'))])
    def test_no_fake_gained_block_or_retention_preventer(self):
        self.reject([lambda r:r['transitions'][1]['blockGains'].append(6),lambda r:r['transitions'][2]['blockGains'].append(3),
            lambda r:r['autoPhases'][1]['clearPreventers'].append('BarricadePower'),lambda r:r['blockGains'].append(1),
            lambda r:r['blockFixture'].update(amount=40),lambda r:r['blockFixture']['after'].update(block=50),
            lambda r:r['blockFixture']['before'].update(block=0),lambda r:r['transitions'][0]['after']['powers'].update(StandingPower=9)])
    def test_normal_enemy_turn_and_second_start_preserve_real_goop(self):
        self.reject([lambda r:r['transitions'][2]['after'].update(block=0),lambda r:r['transitions'][2]['after'].update(block=r['transitions'][1]['after']['block']),
            lambda r:r['transitions'][2]['after'].update(block=r['transitions'][2]['after']['block']+r['transitions'][2]['after']['powers']['StandingPower']),
            lambda r:r['transitions'][2]['after'].update(block=r['transitions'][2]['after']['block']-r['transitions'][2]['after']['powers']['StandingPower']),
            lambda r:r['transitions'][2]['history']['moves'][0].update(move='TACKLE_MOVE'),
            lambda r:r['transitions'][2]['history']['generated'].clear(),lambda r:r['generated'][-1].update(round=1,turn=1),
            lambda r:r['generated'][-1].update(sourceEnemy=22,sourceType='TwigSlimeM'),lambda r:r['generated'][-1].update(creatorId=20),
            lambda r:r['generated'][-1].update(combatCardIndex=100),lambda r:r['final'].update(hp=80),
            lambda r:r['transitions'][2]['history']['damage'].pop(0)])
    def test_normal_draw_before_native_mayhem_and_power_retirement(self):
        self.reject([lambda r:r['autoPhases'][0]['before']['hand'].pop(),lambda r:r['setups'][0]['after']['draw'].__setitem__(0,'standing'),
            lambda r:r['transitions'][0]['effects'][0].update(autoPlay=False),lambda r:r['transitions'][0]['payments'].append(dict(amount=1)),
            lambda r:r['effects'][1].update(spent=1),lambda r:r['transitions'][0]['after']['removed'].remove('standing'),
            lambda r:r['transitions'][1]['history']['exhausts'].reverse(),lambda r:r['transitions'][1]['history']['exhausts'].append('standing'),
            lambda r:r['transitions'][1]['history']['draws'].pop(),lambda r:r['autoPhases'][0]['history']['draws'].append(dict(cardRef='starter-9',fromHandDraw=False))])
    def test_schema_native_identity_and_log_uniqueness(self):
        self.reject([lambda r:r.update(completed=False),lambda r:r.update(token='stale'),lambda r:r.update(passed=True),lambda r:r.update(testMode=True),
            lambda r:r['cards'][0].update(sameObject=False),lambda r:r['cards'][1].update(combatCardIndex=100),lambda r:r['cards'][0].update(masterModelId=None),
            lambda r:r['payments'].clear(),lambda r:r['effects'][2].update(playId=r['effects'][1]['playId']),lambda r:r['autoPhases'].pop(),
            lambda r:r.update(enemyTypes=['LeafSlimeS','TwigSlimeS','TwigSlimeM'])])
        v=gate.STANDING_CASES[0];line=gate.PREFIX+json.dumps(specimen(v))
        self.assertTrue(gate.standing_extra_turn_evidence(line,'run-token',v)[1]);self.assertFalse(gate.standing_extra_turn_evidence(line+'\n'+line,'run-token',v)[1])
    def test_block_net_value_cannot_hide_double_decay_refund_or_clear_restore(self):
        def hidden_excursion(raw,value):
            rows=raw['blockTrace'];index=next(i for i,row in enumerate(rows) if row['kind']=='block-write' and row['clearId']==2)
            write,changed=deepcopy(rows[index:index+2]);final=write['after']
            first=deepcopy(write);first['after']=value
            first_changed=deepcopy(changed);first_changed['after']=value
            second=deepcopy(write);second.update(before=value,after=final)
            second_changed=deepcopy(changed);second_changed.update(before=value,after=final)
            rows[index:index+2]=[first,first_changed,second,second_changed]
            for i,row in enumerate(rows):row['sequence']=i+1
        self.reject([lambda r:hidden_excursion(r,28),lambda r:hidden_excursion(r,0),
            lambda r:r['blockTrace'].pop(11),lambda r:r['blockTrace'][10].update(clearId=None),
            lambda r:r['blockTrace'][12].update(after=40)])
    def test_power_original_apply_source_and_whole_epoch_lifecycle(self):
        def remove_readd(raw):
            rows=raw['powerLifecycle'];remove=deepcopy(rows[2]);remove['kind']='remove-enter'
            done=deepcopy(remove);done['kind']='remove-complete';again=deepcopy(rows)
            for row in again:row['epoch']=2
            rows.extend([remove,done]+again)
            for i,row in enumerate(rows):row['sequence']=i+1
        def direct_collection_readd(raw):
            removed=deepcopy(raw['powerLifecycle'][2]);removed['kind']='collection-removed'
            added=deepcopy(raw['powerLifecycle'][2]);added['epoch']=2
            raw['powerLifecycle'] += [removed,added]
            for i,row in enumerate(raw['powerLifecycle']):row['sequence']=i+1
        self.reject([remove_readd,direct_collection_readd,lambda r:r['powerLifecycle'].clear(),lambda r:r['powerLifecycle'].pop(0),
            lambda r:r['powerLifecycle'][4].update(sourceCard='mayhem'),lambda r:r['powerLifecycle'][4].update(sourceSame=False),
            lambda r:r['powerLifecycle'][4].update(sourceOwnerId=21),lambda r:r['powerLifecycle'][4].update(applierId=21),
            lambda r:r['powerLifecycle'][4].update(ownerSame=False),lambda r:r['powerLifecycle'][4].update(sourceOwnerSame=False),
            lambda r:r['powerLifecycle'][4].update(applierSame=False),lambda r:r['powerLifecycle'][4].update(type='MayhemPower'),lambda r:r['powerLifecycle'][4].update(epoch=2),
            lambda r:r['powerLifecycle'][4].update(powerRef='standing-power-2'),lambda r:r['powerLifecycle'][1].update(before=6)])
    def test_damage_dealer_native_context_and_cross_type_completion_order(self):
        def move_before_damage(raw):
            ordered=raw['transitions'][2]['history']['ordered'];index=next(i for i,row in enumerate(ordered) if row['kind']=='damage')
            ordered[index],ordered[index+1]=ordered[index+1],ordered[index]
        self.reject([move_before_damage,lambda r:r['transitions'][2]['history']['damage'][0].update(dealer=23),
            lambda r:r['transitions'][2]['history']['damage'][0].update(combatSame=False),
            lambda r:r['transitions'][2]['history']['damage'][0].update(round=3),
            lambda r:r['transitions'][2]['history']['damage'][0].update(turn=2),
            lambda r:r['transitions'][2]['history']['damage'][0].update(side='Player'),
            lambda r:r['transitions'][2]['history']['ordered'][0]['data'].update(turn=2),
            lambda r:r['autoPhases'][1]['history']['damage'][0].update(dealer=None)])
    def test_reviewer_master_link_and_reversed_play_ids_false_accepts(self):
        def swapped_masters(raw):
            attack=next(c for c in raw['cards'] if c['masterIndex']==0);skill=next(c for c in raw['cards'] if c['masterIndex']==4)
            attack['masterIndex'],skill['masterIndex']=4,0
        def inverted_ids(raw):
            def walk(value):
                if isinstance(value,list):return [walk(v) for v in value]
                if isinstance(value,dict):return {k:1000-v if k=='playId' else walk(v) for k,v in value.items()}
                return value
            new=walk(raw);raw.clear();raw.update(new)
        self.reject([swapped_masters,inverted_ids])
    def test_identity_turn_fields_are_int_while_decimal_quantities_remain_valid(self):
        self.reject([lambda r:r['cards'][0].update(ownerId=20.0),lambda r:r['initial'].update(round=1.0),
            lambda r:r['generated'][0].update(sourceEnemy=22.0),lambda r:r['transitions'][1]['after'].update(turn=3.0),
            lambda r:r['powerLifecycle'][0].update(epoch=1.0),lambda r:r['blockTrace'][0].update(ownerId=20.0)])
        def decimals(value,key=None):
            if isinstance(value,list):return [decimals(v,key) for v in value]
            if isinstance(value,dict):return {k:decimals(v,k) for k,v in value.items()}
            return float(value) if type(value) is int and key in ('amount','hpLost','blocked','blockGains','requested') else value
        for variant in gate.STANDING_CASES:self.assertTrue(gate.validate_result(decimals(specimen(variant)),'run-token',variant))

    def test_source_has_only_native_turn_and_autoplay_routes(self):
        source=(HERE.parent/'src'/'Volibear'/'StandingExtraTurnProbe.cs').read_text(encoding='utf-8')
        for text in ['new PlayCardAction(card,target)','await action.CompletionTask','RelicCmd.Obtain<PaelsEye>(p)','PlayerCmd.EndTurn(p,canBackOut:false)',
                     'state.CreateCard<Volibear_U03>(p)','CardCmd.Upgrade(card)','CreatureCmd.GainBlock(creature,fixtureGain',
                     'typeof(MayhemPower),nameof(MayhemPower.AfterAutoPrePlayPhaseEntered)','typeof(Hook),nameof(Hook.AfterTakingExtraTurn)',
                     'typeof(Hook),nameof(Hook.AfterBlockGained)','typeof(Hook),nameof(Hook.AfterPreventingBlockClear)','ReferenceEquals(standingInstance,current)',
                     'HasBeenRemovedFromState','monster is LeafSlimeS && move == "GOOP_MOVE"',
                     'eyeUsed = EyeUsed(),standingSame = StandingSame(),','VOLIBEAR_TEST_STANDING_EXTRA_TURN_CASE','STANDING_EXTRA_TURN_RESULT',
                     'creature.BlockChanged += ObserveBlockChanged','owner.Creature.BlockChanged -= ObserveBlockChanged',
                     'creature.PowerApplied += ObservePowerAdded','creature.PowerRemoved += ObservePowerRemoved',
                     'typeof(Creature),"Block",MethodType.Setter','typeof(Creature),"ClearBlock"',
                     'typeof(PowerModel),nameof(PowerModel.ApplyInternal)','typeof(PowerModel),nameof(PowerModel.RemoveInternal)',
                     'typeof(PowerModel),nameof(PowerModel.SetAmount)','typeof(StandingPower),nameof(StandingPower.AfterApplied)',
                     'dealer = e.Dealer?.CombatId','_playerTurnNumbers','entries.Select(OrderedRow)']:
            self.assertIn(text,source)
        for text in ['PowerCmd.Apply<','StandingPower.Deploy(','CardCmd.AutoPlay(','.AfterTakingExtraTurn(','.AfterAutoPrePlayPhaseEntered(',
                     'MockExtraTurnPower','SwitchFromPlayerToEnemySide(','SetMoveImmediate(','SetValue(','CreatureCmd.LoseBlock(','CreatureCmd.SetBlock(',
                     'standingInstance ??= current','.ApplyInternal(','.RemoveInternal(','.SetAmount(','.ClearBlock(']:self.assertNotIn(text,source)
        self.assertEqual(source.count('CreatureCmd.GainBlock('),1)

if __name__=='__main__':unittest.main()
