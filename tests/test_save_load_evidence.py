import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import sys
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/headless.py').is_file())
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import save_load_evidence as e
import save_load_pair as driver


def fixture(case='S2',mode='restart',phase='prepare',pid=100,token='phase-a'):
    seed='VOLIBEAR-SAVE-'+case
    s=dict(runEntity=1,combatEntity=2,playerEntity=3,character='VOLIBEAR_CHARACTER',shouldSave=True,seed=seed,
           room='CombatRoom',encounter='SLIMES_WEAK',round=1,turn=1,energy=3,hp=80,maxHp=80,block=0,gold=99,
           deck=[],relics=[dict(id='VOLIBEAR_HUNTERS_HEART',type='HuntersHeart')],powers=[],
           piles={k:[] for k in ('Draw','Hand','Discard','Exhaust','Play')},
           enemies=[dict(id='ACID_SLIME',hp=20,maxHp=20,block=0,move='ATTACK')])
    for i,id in enumerate(e.expected_deck(case)):
        kind,target,vars=e.FACES[id]
        c=dict(entity=10+i,id=id,nativeType='Volibear_'+id.removeprefix('VOLIBEAR_'),upgrade=1 if id=='VOLIBEAR_U03' else 0,
               type=kind,target=target,shape='None',converted=False,canonicalCost=1,cost=1,costsX=False,vars=copy.deepcopy(vars),
               keywords=[],enchantment=None,pile='Deck',owner=3,masterIndex=i,masterEntity=None)
        s['deck'].append(c)
        clone=copy.deepcopy(c);clone.update(entity=30+i,masterEntity=10+i,pile='Hand' if i in (0,1,2,4,5) else 'Draw')
        s['piles'][clone['pile']].append(clone)
    interrupted=copy.deepcopy(s);interrupted.update(energy=2,block=5)
    defend=next(c for c in interrupted['piles']['Hand'] if c['masterIndex']==4)
    interrupted['piles']['Hand'].remove(defend);defend['pile']='Discard';interrupted['piles']['Discard'].append(defend)
    conversions=[];events=[]
    if case=='S2':
        for index in (0,10):
            c=next(c for pile in interrupted['piles'].values() for c in pile if c['masterIndex']==index)
            if c['pile']!='Hand':
                interrupted['piles'][c['pile']].remove(c);interrupted['piles']['Hand'].append(c);c['pile']='Hand'
                events.append(dict(op='state-fixture-native-move-to-hand',id=c['id'],entity=c['entity']))
            original=copy.deepcopy(c)
            c.update(shape='Claw' if index==0 else 'Body',converted=True,cost=0,type='Attack' if index==0 else 'Skill',
                     target='AnyEnemy' if index==0 else 'AllEnemies',
                     vars={'Damage':7,'Hits':2} if index==0 else {'Block':12,'Lightning':3},keywords=['Exhaust'])
            conversions.append(dict(original=original,form=copy.deepcopy(c),masterBefore=copy.deepcopy(s['deck'][index]),masterAfter=copy.deepcopy(s['deck'][index])))
            events.append(dict(op='state-fixture-convert-and-temporary-zero',id=c['id']))
    checkpoint=dict(rng={'seed':seed},start_time=1793484000,num_reloads=0,visited_map_coords=[{'x':0,'y':0}],pre_finished_room=None,
        acts=[{'id':'ACT.OVERGROWTH','saved_map':{'points':[
            {'coord':{'col':0,'row':0},'type':'monster','can_modify':True},
            {'coord':{'col':1,'row':1},'type':'elite'}]}}],
        players=[dict(character_id='CHARACTER.VOLIBEAR_CHARACTER',current_hp=80,max_hp=80,max_energy=3,gold=99,
                      deck=[dict(id='CARD.'+c['id'],current_upgrade_level=c['upgrade']) for c in s['deck']],
                      relics=[dict(id='RELIC.VOLIBEAR_HUNTERS_HEART')])])
    path='C:/isolated/pair/profile/appdata/SlayTheSpire2'
    r=dict(schema=1,token=token,pair='pair',phase=phase,mode=mode,caseId=case,pid=pid,userRoot=path,
           checkpointPath=path+'/default/1/modded/profile1/saves/current_run.save',gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
           assemblyMvid='00000000-0000-0000-0000-000000000001',acceptance=e.SCOPE,seed=seed,
           fixture=dict(directRunApi=True,statsExistedBefore=False,statsPresent=True,ftuesDisabledInIsolatedProfile=True,shouldSave=True,
                        startedWithNeow=False,masterPreparation='native-CreateCard-AddToDeck-Upgrade-U03' if case=='S2' else 'native-starter-deck'),
           events=events+[dict(op='native-ui-forceclick',button=b) for b in ['Pause','SaveAndQuit']],
           checkpoint=checkpoint,afterMenu=copy.deepcopy(checkpoint),initial=s,interruption=dict(converted=conversions,payment=dict(
               action='PlayCardAction',state='Finished',actionId=1,context='GameActionPlayerChoiceContext',
               history=[dict(id='VOLIBEAR_B02',autoPlay=False,spent=1,index=0,count=1)],
               afterEnergySpent=[dict(id='VOLIBEAR_B02',amount=1,energy=2)],energyHistory=[1])),
           interrupted=interrupted,resumed=None,afterLoad=None)
    if phase!='prepare':
        r['resumed']=copy.deepcopy(s)
        def new_refs(v):
            if isinstance(v,dict):
                return {k:(value+100 if k in ('entity','owner','masterEntity','runEntity','combatEntity','playerEntity') and value is not None else new_refs(value)) for k,value in v.items()}
            if isinstance(v,list):return [new_refs(x) for x in v]
            return v
        r['resumed']=new_refs(r['resumed'])
        r['afterLoad']=copy.deepcopy(checkpoint);r['afterLoad']['num_reloads']=1
        # Independently model the pinned native constructor/default-omission roundtrip.
        r['afterLoad']['acts'][0]['saved_map']['points'][1]['can_modify']=True
        r['events'].append(dict(op='native-ui-forceclick',button='Continue'))
        if phase=='resume':
            for k in ('fixture','initial','interruption','interrupted','afterMenu'):r[k]=None
            r['events']=[dict(op='native-ui-forceclick',button='Continue')]
    expected={k:r[k] for k in ('token','pair','phase','mode','caseId','seed','pid','userRoot','checkpointPath')}
    return r,expected

class EvidenceTests(unittest.TestCase):
    def test_positive_all_four_modes(self):
        for case in ('S1','S2'):
            for mode,phase in [('restart','prepare'),('restart','resume'),('same-process','same')]:
                r,x=fixture(case,mode,phase);self.assertTrue(e.validate_phase(r,x),(case,phase))
    def test_body_target_anchored_to_independent_frozen_t02(self):
        frozen=json.loads((ROOT/'tests/fixtures/card_expectations.json').read_text(encoding='utf-8'))
        token=next(card for card in frozen['cards'] if card['card_id']=='T02')
        self.assertEqual(token['play_target'],'all_enemies')
        r,x=fixture();body=next(c for c in r['interrupted']['piles']['Hand'] if c['shape']=='Body')
        self.assertEqual(body['target'],{'all_enemies':'AllEnemies'}[token['play_target']])
        self.assertEqual(body['type'],token['type'].title());self.assertEqual(body['canonicalCost'],token['faces'][1]['cost'])
        self.assertTrue(e.validate_phase(r,x))
    def reject_body_target(self,target):
        r,x=fixture();body=next(c for c in r['interrupted']['piles']['Hand'] if c['shape']=='Body')
        body['target']=target;r['interruption']['converted'][1]['form']['target']=target
        errors=[];self.assertFalse(e.validate_phase(r,x,errors));self.assertIn('form metadata',errors[0])
    def test_body_self_target_rejected(self):self.reject_body_target('Self')
    def test_body_single_enemy_target_rejected(self):self.reject_body_target('AnyEnemy')
    def test_pair_positive(self):
        a,x=fixture();b,y=fixture(phase='resume',pid=200,token='phase-b')
        self.assertTrue(e.validate_pair(a,b,x,y,True,True))
    def reject(self,mutation,phase='same'):
        r,x=fixture(mode='same-process' if phase=='same' else 'restart',phase=phase)
        mutation(r);self.assertFalse(e.validate_phase(r,x))
    def test_root_missing_fields(self):
        r,x=fixture()
        for key in r:
            bad=copy.deepcopy(r);del bad[key]
            self.assertFalse(e.validate_phase(bad,x),key)
    def test_binding_mutations(self):
        for key in ('token','pair','phase','mode','caseId','seed','userRoot','checkpointPath','gameVersion','gameCommit','acceptance','assemblyMvid'):
            with self.subTest(key=key):self.reject(lambda r:r.update({key:'wrong'}))
    def test_fake_pass_flag(self):self.reject(lambda r:r.update(passed=True))
    def test_pid_boolean(self):self.reject(lambda r:r.update(pid=True))
    def test_test_mode(self):self.reject(lambda r:r.update(testMode=True))
    def test_save_disabled(self):self.reject(lambda r:r['fixture'].update(shouldSave=False))
    def test_neow_bypass(self):self.reject(lambda r:r['fixture'].update(startedWithNeow=True))
    def test_missing_stats(self):self.reject(lambda r:r['fixture'].update(statsPresent=False))
    def test_fake_ui(self):self.reject(lambda r:r['events'].__setitem__(-1,{'op':'direct-loadrun','button':'Continue'}))
    def test_wrong_ui_order(self):self.reject(lambda r:r['events'].reverse())
    def test_same_reference_resume(self):self.reject(lambda r:r['resumed'].update(combatEntity=r['initial']['combatEntity']))
    def test_room_is_ancient(self):self.reject(lambda r:r['initial'].update(room='EventRoom'))
    def test_energy_not_spent(self):self.reject(lambda r:r['interrupted'].update(energy=3))
    def test_block_missing(self):self.reject(lambda r:r['interrupted'].update(block=0))
    def test_autoplay(self):self.reject(lambda r:r['interruption']['payment']['history'][0].update(autoPlay=True))
    def test_wrong_payment(self):self.reject(lambda r:r['interruption']['payment']['history'][0].update(spent=0))
    def test_duplicate_history(self):self.reject(lambda r:r['interruption']['payment']['history'].append(copy.deepcopy(r['interruption']['payment']['history'][0])))
    def test_no_conversion_receipts(self):self.reject(lambda r:r['interruption'].update(converted=[]))
    def test_master_pollution(self):self.reject(lambda r:r['interrupted']['deck'][10].update(type='Skill'))
    def test_retained_zero(self):self.reject(lambda r:r['resumed']['piles']['Hand'][0].update(cost=0))
    def test_lost_upgrade(self):self.reject(lambda r:r['resumed']['deck'][10].update(upgrade=0))
    def test_deprecated_card(self):self.reject(lambda r:r['resumed']['deck'][0].update(nativeType='DeprecatedCard'))
    def test_wrong_deckversion(self):self.reject(lambda r:r['resumed']['piles']['Hand'][0].update(masterEntity=999))
    def test_wrong_owner(self):self.reject(lambda r:r['resumed']['piles']['Hand'][0].update(owner=999))
    def test_missing_clone(self):self.reject(lambda r:r['resumed']['piles']['Draw'].pop())
    def test_duplicate_clone(self):self.reject(lambda r:r['resumed']['piles']['Draw'].append(copy.deepcopy(r['resumed']['piles']['Draw'][0])))
    def test_midcombat_save(self):self.reject(lambda r:r['afterMenu']['players'][0].update(current_hp=70))
    def test_reload_not_incremented(self):self.reject(lambda r:r['afterLoad'].update(num_reloads=0))
    def test_reload_skipped_twice(self):self.reject(lambda r:r['afterLoad'].update(num_reloads=2))
    def test_afterload_rewrite(self):self.reject(lambda r:r['afterLoad']['players'][0].update(gold=100))
    def test_prefinished(self):self.reject(lambda r:r['checkpoint'].update(pre_finished_room={'type':'Combat'}))
    def test_prepare_must_not_continue(self):self.reject(lambda r:r.update(resumed=copy.deepcopy(r['initial'])),phase='prepare')
    def test_resume_must_not_new_run(self):self.reject(lambda r:r.update(fixture={'directRunApi':True}),phase='resume')
    def test_pair_wrong_pid_or_token_or_mvid(self):
        for key,value in [('pid',100),('token','phase-a'),('assemblyMvid','00000000-0000-0000-0000-000000000002')]:
            a,x=fixture();b,y=fixture(phase='resume',pid=200,token='phase-b');b[key]=value
            if key in y:y[key]=value
            self.assertFalse(e.validate_pair(a,b,x,y,True,True))
    def test_pair_requires_shared_runtime_gates(self):
        a,x=fixture();b,y=fixture(phase='resume',pid=200,token='phase-b')
        for gates in ((False,True),(True,False),(False,False)):
            self.assertFalse(e.validate_pair(a,b,x,y,*gates))
    def test_raw_log_requires_unique_token_and_shutdown(self):
        r,x=fixture();line=e.PREFIX+json.dumps(r);end='[Volibear] SHUTDOWN_BEGIN '+x['token']
        self.assertTrue(e.parse_log(line+'\n'+end,x)[1])
        for log in (line,line+'\n'+line+'\n'+end,line+'\n'+end+'\nSAVE_LOAD_PROBE_ERROR'):
            self.assertFalse(e.parse_log(log,x)[1])
    def test_resume_launch_blocks_every_shared_gate(self):
        raw,expected=fixture();keys=['exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized',
            'runtime_isolation','teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic-checkpoint.json';path.write_text(json.dumps(raw['afterMenu']))
            report=dict(raw=raw,expected=expected,checks=dict.fromkeys(keys,True),passed=True)
            resume=Mock(return_value='B');self.assertEqual(driver.gate_then_resume(report,path,resume),'B');resume.assert_called_once()
            for key in keys:
                bad=copy.deepcopy(report);bad['checks'][key]=False;resume=Mock()
                self.assertIsNone(driver.gate_then_resume(bad,path,resume));resume.assert_not_called()
            path.write_text('{}');resume=Mock();self.assertIsNone(driver.gate_then_resume(report,path,resume));resume.assert_not_called()
    def test_card_cost_bool_rejected(self):self.reject(lambda r:r['initial']['deck'][0].update(cost=True))
    def test_card_upgrade_bool_rejected(self):self.reject(lambda r:r['initial']['deck'][10].update(upgrade=True))
    def test_saved_upgrade_bool_rejected(self):self.reject(lambda r:r['checkpoint']['players'][0]['deck'][10].update(current_upgrade_level=True))
    def test_missing_state_fixture_label(self):
        self.reject(lambda r:r.update(events=[v for v in r['events'] if v['op']!='state-fixture-convert-and-temporary-zero']))
    def test_reused_combat_clone_after_same_process_continue(self):
        self.reject(lambda r:r['resumed']['piles']['Hand'][0].update(entity=r['initial']['piles']['Hand'][0]['entity']))
    def test_extra_keyword_not_in_material(self):
        self.reject(lambda r:r['interrupted']['piles']['Hand'][0]['keywords'].append('Retain'))
    def test_malformed_roots(self):
        _,x=fixture()
        for raw in (None,False,1,[],{},'passed'):
            self.assertFalse(e.validate_phase(raw,x))
    def test_stale_A_blocks_B_despite_passed_flag(self):
        raw,expected=fixture();raw['token']='stale'
        keys=['exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized',
              'runtime_isolation','teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw']
        resume=Mock();a=dict(raw=raw,expected=expected,checks=dict.fromkeys(keys,True),passed=True)
        self.assertIsNone(driver.gate_then_resume(a,Path('not-read'),resume));resume.assert_not_called()
    def test_probe_uses_native_string_seed(self):
        source=(ROOT/'src/Volibear/SaveLoadContractProbe.cs').read_text(encoding='utf-8')
        self.assertIn('seed = run.Rng.StringSeed',source)
        self.assertNotIn('seed = run.Rng.Seed,',source)
    def test_probe_uses_real_pause_continue_and_no_save_writer(self):
        source=(ROOT/'src/Volibear/SaveLoadContractProbe.cs').read_text(encoding='utf-8')
        for required in ('button.ForceClick()', 'EnterMapCoord(', 'MainMenuTextButtons/ContinueButton',
                         '%ButtonContainer/SaveAndQuit', 'StartNewSingleplayerRun(character, true'):
            self.assertIn(required,source)
        for forbidden in ('EnterRoomDebug(', '.LoadRun(', '.FromSerializable(', 'File.Write', '.SaveRun('):
            self.assertNotIn(forbidden,source)
    def test_missing_after_energy_spent_witness(self):self.reject(lambda r:r['interruption']['payment'].update(afterEnergySpent=[]))
    def test_missing_energy_history(self):self.reject(lambda r:r['interruption']['payment'].update(energyHistory=[]))
    def test_duplicate_energy_spent_witness(self):
        self.reject(lambda r:r['interruption']['payment']['afterEnergySpent'].append(dict(id='VOLIBEAR_B02',amount=1,energy=2)))
    def test_finished_cancelled_play_has_diagnostic(self):
        r,x=fixture(case='S1',mode='same-process',phase='same')
        r['interrupted']=copy.deepcopy(r['initial'])
        r['interruption']['payment'].update(context=None,history=[],afterEnergySpent=[],energyHistory=[])
        errors=e.diagnose_phase(r,x)
        self.assertEqual(errors,['interrupted: ValueError: snapshot.energy: expected 2, observed 3'])
        self.assertFalse(e.validate_phase(r,x))
    def test_diagnostic_preserves_strict_success(self):
        r,x=fixture();self.assertEqual(e.diagnose_phase(r,x),[]);self.assertTrue(e.validate_phase(r,x))
    def test_payment_receipt_error_is_detailed(self):
        r,x=fixture();r['interruption']['payment']['context']=None
        self.assertIn('native paid disturbance',e.diagnose_phase(r,x)[0])
        self.assertIn("'context': None",e.diagnose_phase(r,x)[0])
    def test_source_self_action_uses_null_target(self):
        source=(ROOT/'src/Volibear/SaveLoadContractProbe.cs').read_text(encoding='utf-8')
        self.assertIn('new PlayCardAction(defend, null)',source)
        self.assertNotIn('new PlayCardAction(defend, player.Creature)',source)
        self.assertIn('defend.IsValidTarget(null)',source)
        self.assertIn('nameof(Hook.AfterEnergySpent)',source)
    def test_native_map_missing_becomes_literal_true(self):
        r,x=fixture(mode='same-process',phase='same');before=copy.deepcopy(r['checkpoint'])
        expected,paths=e.native_reload_expected(r['checkpoint'])
        self.assertEqual(paths,['acts[0].saved_map.points[1].can_modify'])
        self.assertEqual(expected,r['afterLoad']);self.assertEqual(before,r['checkpoint'])
        self.assertTrue(e.validate_phase(r,x))
    def test_map_missing_not_filled_rejected(self):
        self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][1].pop('can_modify'))
    def test_map_existing_true_cannot_disappear(self):
        self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][0].pop('can_modify'))
    def test_map_false_or_numeric_not_permitted_before(self):
        for value in (False,1,0,'true',None):
            with self.subTest(value=value):self.reject(lambda r:r['checkpoint']['acts'][0]['saved_map']['points'][0].update(can_modify=value))
    def test_map_false_or_numeric_not_permitted_after(self):
        for value in (False,1,0,'true',None):
            with self.subTest(value=value):self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][1].update(can_modify=value))
    def test_map_normalization_cannot_change_coords(self):
        self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][1]['coord'].update(col=2))
    def test_map_normalization_cannot_change_type(self):
        self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][1].update(type='shop'))
    def test_map_normalization_cannot_add_other_path(self):self.reject(lambda r:r['afterLoad'].update(can_modify=True))
    def test_no_generic_recursive_missing_flag_default(self):
        r,_=fixture();c=r['checkpoint'];c['other']={'points':[{}]}
        expected,paths=e.native_reload_expected(c)
        self.assertEqual(expected['other'],{'points':[{}]})
        self.assertEqual(paths,['acts[0].saved_map.points[1].can_modify'])
    def test_map_rule_cannot_hide_other_native_changes(self):
        for key in ('start_time','save_time','run_time'):
            def mutate(r,key=key):
                for stage in ('checkpoint','afterMenu','afterLoad'):r[stage][key]=100
                r['afterLoad'][key]=101
            with self.subTest(key=key):self.reject(mutate)
        self.reject(lambda r:r['afterLoad']['rng'].update(seed='changed'))
        self.reject(lambda r:r['afterLoad']['visited_map_coords'][0].update(x=99))
        self.reject(lambda r:r['afterLoad']['players'][0]['deck'][0].update(id='CARD.STRIKE_IRONCLAD'))
        self.reject(lambda r:r['afterLoad']['players'][0]['relics'][0].update(id='RELIC.BURNING_BLOOD'))
    def test_no_bootstrap_in_native_command(self):
        command=driver.phase_command(Path('C:/game'),Path('C:/phase'),'headless',30000)
        self.assertNotIn('--bootstrap',command);self.assertIn('--force-steam=off',command)

if __name__=='__main__':unittest.main()
