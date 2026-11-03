"""Synthetic parser checks, not game acceptance or payment proof."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from card_lifecycle_evidence import (CASES,CODES,POWER_CARDS,POWER_TYPES,EXISTING,PREFIX,BATCH_PREFIX,
    ACCEPTANCE,plan,validate,card_lifecycle_evidence,card_lifecycle_batch_evidence,same)


def u07_fixture():
    def snap(combat='old',turn=1,energy=30,block=0,lightning=0,hand=None):
        return dict(combatRef=combat,round=turn,turn=turn,side='Player',phase='Play',energy=energy,hp=1000,block=block,
                    strength=0,dexterity=0,storm=0,domain=0,permanent=False,lightning=lightning,temporary=0,
                    hand=hand or [],handCards=[],powers=[],
                    enemies=[dict(enemyRef=combat+str(i),id=i+1,type=('LeafSlimeS','TwigSlimeM','TwigSlimeS')[i],hp=1000,block=0) for i in range(3)])
    def history(): return dict(plays=[],finished=[],draws=[],exhausts=[],damage=[],moves=[])
    original=snap(energy=3);original['hp']=80
    fixtures=[dict(label='native-created-card-and-HP-energy-isolation',before=deepcopy(original),after=snap(),history=history(),batches=[])]
    actions=[]
    # Independently specified exact U07 sequence: replay is one historical attack, targets don't share counts.
    rows=[('history-replayed-attack-counts-once','B01',0,1,1,6,None,'old',1),
          ('history-same-target','U07',0,0,2,28,[2,3,3],'old',1),
          ('history-other-target','U07',1,0,3,28,[1,3,3],'old',1),
          ('history-return-target','U07',0,0,1,28,[1,2,3],'old',1),
          ('history-next-turn-reset','U07',0,0,3,28,[3,3,3],'old',2),
          ('new-combat-first','B01',0,0,1,6,None,'new',1),
          ('new-combat-second','B01',0,0,1,6,None,'new',1),
          ('new-combat-lightning','C24',-1,0,1,None,None,'new',1),
          ('new-combat-engage','B04',1,0,1,6,None,'new',1),
          ('new-combat-no-coupon','U07',2,0,3,28,[1,2,3],'new',1)]
    current=snap();transitions=[]; before_exit=None; fresh=None
    for n,(label,card,target,replay,cost,damage,previews,combat,turn) in enumerate(rows):
        if n==4:
            normal=snap(turn=2,energy=3)
            h=history();h['moves']=[dict(enemyRef='old2',move='native-unconsumed-move')]
            transitions.append(dict(label='native-normal-next-player-turn',before=deepcopy(current),after=deepcopy(normal),history=h,batches=[],extraTurns=[]))
            current=snap(turn=2)
            fixtures.append(dict(label='native-next-turn-energy-and-negative-modifier-isolation',before=normal,after=deepcopy(current),history=history(),batches=[]))
        if n==5:
            before_exit=deepcopy(current);fresh=snap('new',energy=3)
            current=snap('new')
            fixtures.append(dict(label='native-second-combat-isolation-no-power-reset',before=deepcopy(fresh),after=deepcopy(current),history=history(),batches=[]))
        ref='card'+str(n);before=deepcopy(current);before['hand']=current['hand']+[ref]
        after=deepcopy(current);after['energy']-=cost
        h=history();repeat=replay+1
        h['plays']=[dict(cardRef=ref,index=i,count=repeat,autoPlay=False,spent=cost) for i in range(repeat)]
        h['finished']=[dict(cardRef=ref,index=i,autoPlay=False) for i in range(repeat)]
        target_ref=combat+str(target) if target>=0 else 'null'
        if damage is not None:
            h['damage']=[dict(targetRef=target_ref,sourceRef='owner',cardRef=ref,hpLost=damage,blocked=0,props=8) for _ in range(repeat)]
        batches=[]
        if card=='C24':
            after['lightning']=1
            targets=['new0','new1','new2']
            batches=[dict(id=1,combatRef='new',round=1,turn=1,count=1,baseDamage=6,storm=0,amount=6,cardRef=ref,targets=targets,
                          hits=[dict(targetRef=t,hpLost=6,blocked=0) for t in targets])]
            h['damage']=[dict(targetRef=t,sourceRef='owner',cardRef=ref,hpLost=6,blocked=0,props=4) for t in targets]
        if card in ('C24','B04'):
            drawn='draw-'+str(n);h['draws']=[dict(cardRef=drawn,type='Volibear_B02',normal=False)];after['hand'].append(drawn)
        if card=='B04': after['block']+=8;h['moves']=[dict(enemyRef=target_ref,move='native-nonattack-engage')]
        effects=[dict(cardRef=ref,index=i,count=repeat,autoPlay=False,spent=cost,state=deepcopy(before)) for i in range(repeat)]
        actions.append(dict(label=label,code=card,upgraded=False,replay=replay,cardRef=ref,targetRef=target_ref,before=before,after=deepcopy(after),
                            previews=[dict(targetRef=combat+str(i),cost=c) for i,c in enumerate(previews or [1,1,1])],pile='Discard',
                            action=dict(type='PlayCardAction',state='Finished',actionType='PlayCard',sameCard=True,events=['before-executed','after-finished']),
                            payments=[dict(cardRef=ref,amount=cost,energy=before['energy']-cost)],effects=effects,batches=batches,history=h))
        current=after
    destination=[dict(cardRef=f'starter-{i}',type='Volibear_'+model) for i,model in enumerate(['B01']*4+['B02']*4+['B03','B04'])]
    moved=deepcopy(destination[5:])
    for fixture in fixtures: fixture['starterSetup']=None
    fixtures[0]['starterSetup']=dict(moved=moved,destination=destination,movedCount=5,target='Draw',position='Bottom',skipVisuals=False)
    for snapshot in (original,fixtures[0]['before']):
        snapshot['hand']=[row['cardRef'] for row in moved]
        snapshot['handCards']=[dict(row,cost=1) for row in moved]
    return dict(schema=1,token='test',runRef='run-1',scenario='card-lifecycle',variant='U07-base',code='U07',upgraded=False,completed=True,
                version='v0.107.1',commit='59260271',testMode=False,acceptance=ACCEPTANCE,playerRef='player',ownerRef='owner',original=original,
                fixtures=fixtures,actions=actions,transitions=transitions,confirmations=[],choiceSync=[],
                reentry=dict(beforeExit=before_exit,afterReentry=fresh,samePlayer=True,combatChanged=True),final=deepcopy(current))


def batch_log(raw=None):
    raw=raw or u07_fixture()
    final=dict(schema=1,token='test',scenario='card-lifecycle',requested=['U07-base'],completed=['U07-base'],runRefs=['run-1'],finished=True,
               exits=[dict(variant='U07-base',runRef='run-1',receipt=dict(RunNull=True,CombatNull=True,InProgress=False,QueueEmpty=True,ActionNull=True,HistoryVisible=0))])
    return PREFIX+json.dumps(raw)+'\n'+BATCH_PREFIX+json.dumps(final),final


class CardLifecycleEvidenceTests(unittest.TestCase):
    def test_starter_setup_is_required_only_at_original_setup_boundary(self):
        mutations = [
            lambda r: r['fixtures'][0].pop('starterSetup'),
            lambda r: r['fixtures'][0]['starterSetup'].update(extra=True),
            lambda r: r['fixtures'][0]['starterSetup'].update(skipVisuals=True),
            lambda r: r['fixtures'][0]['starterSetup'].update(position='Top'),
            lambda r: r['fixtures'][0]['starterSetup'].update(movedCount=5.0),
            lambda r: r['fixtures'][0]['starterSetup']['destination'].pop(),
            lambda r: r['fixtures'][0]['starterSetup']['moved'].reverse(),
            lambda r: r['original']['hand'].reverse(),
            lambda r: r['fixtures'][0]['before']['handCards'][0].update(type='Volibear_B01'),
            lambda r: r['fixtures'][0]['starterSetup']['destination'][0].update(cardRef='null'),
            lambda r: r['fixtures'][1].update(starterSetup=deepcopy(r['fixtures'][0]['starterSetup'])),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                row=u07_fixture();mutate(row)
                with self.assertRaises((ValueError,KeyError)):
                    validate(row,'test','U07-base')

    def reject(self, raw):
        result,valid=card_lifecycle_evidence(PREFIX+json.dumps(raw),'test','U07-base')
        self.assertFalse(valid,result)

    def test_manual_history_fixture_and_one_native_batch(self):
        self.assertTrue(validate(u07_fixture(),'test','U07-base'))
        self.assertTrue(card_lifecycle_batch_evidence(batch_log()[0],'test',['U07-base'])[1])

    def test_manual_upgraded_history_fixture_keeps_target_cost_contract(self):
        value=u07_fixture();value.update(variant='U07-upgraded',upgraded=True)
        for action in value['actions']:
            if action['code']=='U07' and not action['label'].startswith('new-combat-'):
                action['upgraded']=True
                for hit in action['history']['damage']:hit['hpLost']=36
        self.assertTrue(validate(value,'test','U07-upgraded'))
        value['actions'][1]['history']['damage'][0]['hpLost']=28
        self.assertFalse(card_lifecycle_evidence(PREFIX+json.dumps(value),'test','U07-upgraded')[1])

    def test_full_finite_inventory_not_silent_unknown_exemption(self):
        self.assertEqual(len(CASES),48);self.assertEqual(len(set(CASES)),48)
        self.assertEqual(set(POWER_CARDS),{'U02','U03','U04','U19','U21','U25','U26','U29','U32','U34','R01','R02','R14','R16','R18','R28','R30'})
        declared=set()
        for file in (ROOT/'src/Volibear/Content/Cards').glob('*.cs'):
            declared.update(re.findall(r'public Volibear_([A-Z]\d+)\(\)\s*:\s*base\([^\n]*CardType\.Power',file.read_text(encoding='utf-8')))
        self.assertEqual(declared,set(POWER_CARDS))
        for code in POWER_CARDS:self.assertIn(code,POWER_TYPES)
        self.assertIn('R06',CODES);self.assertNotIn('R06',POWER_CARDS)
        for case in CASES:
            rows=plan(case)
            self.assertEqual(len({r['label'] for r in rows}),len(rows))
            self.assertTrue(any(r['phase']=='next' for r in rows))
            self.assertTrue(any(r['label']=='new-combat-engage' for r in rows))
            if case.rsplit('-',1)[0] in POWER_TYPES:
                paid=[r for r in rows if r['label']=='paid-second-deployment'];self.assertEqual(len(paid),1)
        for mapping in EXISTING.values():self.assertTrue((ROOT/mapping[-1]).is_file())

    def test_native_queue_not_autoplay_or_fabricated_payment(self):
        for mutate in ('auto','double','free','wrongcard','cancel','nohand','nopaid'):
            value=u07_fixture();a=value['actions'][1]
            if mutate=='auto':a['history']['plays'][0]['autoPlay']=True
            elif mutate=='double':a['payments']*=2
            elif mutate=='free':a['payments'][0]['amount']=0
            elif mutate=='wrongcard':a['action']['sameCard']=False
            elif mutate=='cancel':a['action']['events'].insert(1,'cancelled')
            elif mutate=='nohand':a['before']['hand']=[]
            else:a['payments']=[]
            with self.subTest(mutate=mutate):self.reject(value)

    def test_target_history_replay_and_turn_boundaries(self):
        for index,field,wrong in ((1,'targetRef','old1'),(1,'replay',1),(2,'targetRef','old0'),(4,'targetRef','new0')):
            value=u07_fixture();value['actions'][index][field]=wrong
            with self.subTest(index=index,field=field):self.reject(value)
        for index in (1,2,3,4,9):
            value=u07_fixture();value['actions'][index]['previews'][0]['cost']+=1;self.reject(value)

    def test_native_damage_and_distinct_lightning_not_self_certified(self):
        for mutate in ('damage','source','batch','receipt','bool'):
            value=u07_fixture()
            if mutate=='damage':value['actions'][1]['history']['damage'][0]['hpLost']=0
            elif mutate=='source':value['actions'][0]['history']['damage'][0]['sourceRef']='other'
            elif mutate=='batch':value['actions'][7]['batches']=[]
            elif mutate=='receipt':value['actions'][7]['history']['damage'][0]['hpLost']=0
            else:value['actions'][0]['payments'][0]['amount']=True
            with self.subTest(mutate=mutate):self.reject(value)

    def test_native_lifecycle_and_fresh_combat_required(self):
        for mutate in ('nomoves','turn','round','samecombat','oldstrength','oldclock','sameenemy','badfinal'):
            value=u07_fixture()
            if mutate=='nomoves':value['transitions'][0]['history']['moves']=[]
            elif mutate=='turn':value['transitions'][0]['after']['turn']=1
            elif mutate=='round':value['transitions'][0]['after']['round']=1
            elif mutate=='samecombat':value['reentry']['combatChanged']=False
            elif mutate=='oldstrength':value['reentry']['afterReentry']['strength']=1
            elif mutate=='oldclock':value['reentry']['afterReentry']['lightning']=2
            elif mutate=='sameenemy':value['reentry']['afterReentry']['enemies'][0]['enemyRef']='old0'
            else:value['final']['energy']=999
            with self.subTest(mutate=mutate):self.reject(value)

    def test_missing_fields_actions_and_replay_fragments_fail_closed(self):
        for key in ('runRef','actions','fixtures','transitions','reentry','final','version','ownerRef','confirmations','choiceSync'):
            value=u07_fixture();del value[key]
            with self.subTest(field=key):self.reject(value)
        value=u07_fixture();value['actions'].pop();self.reject(value)
        value=u07_fixture();value['actions'][0]['history']['plays'].pop();self.reject(value)
        value=u07_fixture();value['actions'][0]['effects'].pop();self.reject(value)

    def test_batch_final_and_every_native_clean_exit_are_mandatory(self):
        good,final=batch_log();prefix=good.split('\n')[0]+'\n'
        self.assertFalse(card_lifecycle_batch_evidence(prefix,'test',['U07-base'])[1])
        for key,wrong in (('RunNull',False),('CombatNull',False),('InProgress',True),('QueueEmpty',False),('ActionNull',False),('HistoryVisible',1)):
            altered=deepcopy(final);altered['exits'][0]['receipt'][key]=wrong
            with self.subTest(field=key):self.assertFalse(card_lifecycle_batch_evidence(prefix+BATCH_PREFIX+json.dumps(altered),'test',['U07-base'])[1])
        self.assertFalse(card_lifecycle_batch_evidence(good+'\n'+good,'test',['U07-base'])[1])
        self.assertFalse(card_lifecycle_batch_evidence(good,'test',CASES)[1])
        self.assertFalse(card_lifecycle_batch_evidence(good,'other-run',['U07-base'])[1])

    def test_batch_run_identity_cannot_be_relabelled(self):
        log,final=batch_log();final['runRefs']=['run-other']
        self.assertFalse(card_lifecycle_batch_evidence(log.split('\n')[0]+'\n'+BATCH_PREFIX+json.dumps(final),'test',['U07-base'])[1])

    def test_real_newrun_host_not_per_case_shutdown_or_manual_reset(self):
        source=(ROOT/'src/Volibear/CardLifecycleAcceptanceProbe.cs').read_text(encoding='utf-8')
        body=source.split('internal static async Task<JsonElement> RunCase',1)[1]
        self.assertNotIn('.Quit(',body);self.assertNotIn('CombatManager.Instance.Reset',source)
        self.assertNotIn('CardCmd.AutoPlay',source);self.assertNotIn('CardSelectCmd.Selector =',source)
        for edge in ('NativeAcceptanceRunHost.StartFresh','NativeAcceptanceRunHost.ExitToMainMenu','RequestEnqueue(action)','PlayerCmd.EndTurn','EnterRoom(new MapRoom())'):
            self.assertIn(edge,source)


if __name__=='__main__':unittest.main()
