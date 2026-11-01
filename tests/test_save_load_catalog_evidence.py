import copy
import json
from pathlib import Path
import unittest
import sys
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/headless.py').is_file())
if str(ROOT/'tools') not in sys.path:sys.path.append(str(ROOT/'tools'))
import save_load_catalog_evidence as e
PROBE=Path(__file__).parent/'SaveLoadCatalogProbe.cs'
if not PROBE.is_file():PROBE=ROOT/'src/Volibear/SaveLoadCatalogProbe.cs'


def fixture(mode='same-process',phase='same',pid=11,token='s3-token'):
    seed='VOLIBEAR-CATALOG-S3';root='C:/isolated/pair/profile/appdata/SlayTheSpire2'
    deck=[]
    for i,(id,level) in enumerate(e.entries('S3')):
        definition=e.CATALOG[id];face=definition['faces'][level]
        serialized=dict(id='CARD.'+id,floor_added_to_deck=0)
        if level:serialized['current_upgrade_level']=level
        cost=0 if face['cost']=='X' else face['cost']
        deck.append(dict(entity=100+i,id=id,nativeType='Volibear_'+definition['card_id'],upgrade=level,type=definition['type'].title(),
            rarity=definition['rarity'].title(),target=e.TARGETS[definition['play_target']],shape={'T01':'Claw','T02':'Body'}.get(definition['card_id'],'None'),
            converted=False,canonicalCost=0 if definition['faces'][0]['cost']=='X' else definition['faces'][0]['cost'],cost=cost,allCost=cost,
            costsX=face['cost']=='X',vars={'Observed':dict(kind='DynamicVar',baseValue=1,enchantedValue=1,previewValue=1)},
            title=definition['name_zh']+('+' if level else ''),description=face['display_text_zh'],serialized=serialized,
            keywords=['Exhaust'] if face['self_exhaust'] else [],enchantment=None,pile='Deck',owner=1,masterIndex=i,masterEntity=None))
    clones=copy.deepcopy(deck)
    for i,c in enumerate(clones):c.update(entity=300+i,pile='Hand' if i<5 else 'Draw',masterEntity=deck[i]['entity'])
    relic=dict(entity=4,id='VOLIBEAR_HUNTERS_HEART',type='HuntersHeart',owner=1,slot=0,melted=False,serialized={'id':'RELIC.VOLIBEAR_HUNTERS_HEART'})
    initial=dict(runEntity=2,combatEntity=3,playerEntity=1,creatureEntity=999,character='VOLIBEAR_CHARACTER',shouldSave=True,seed=seed,room='CombatRoom',encounter='NIBBITS_WEAK',
        round=1,turn=1,energy=3,hp=80,maxHp=80,block=0,gold=99,deck=deck,relics=[relic],powers=[],
        piles=dict(Hand=clones[:5],Draw=clones[5:],Discard=[],Exhaust=[],Play=[]),enemies=[dict(entity=600,id='NIBBIT',hp=42,maxHp=42,block=0,move='BUTT_MOVE')])
    interrupted=copy.deepcopy(initial);interrupted.update(energy=2,block=5)
    card=next(c for c in interrupted['piles']['Hand'] if c['id']=='VOLIBEAR_B02' and c['upgrade']==0)
    interrupted['piles']['Hand'].remove(card);card['pile']='Discard';interrupted['piles']['Discard'].append(card)
    checkpoint=dict(rng={'seed':seed},start_time=1793484000,num_reloads=0,visited_map_coords=[{'col':0,'row':0}],pre_finished_room=None,
        acts=[{'id':'ACT.OVERGROWTH','saved_map':{'points':[{'coord':{'col':0,'row':0},'type':'monster'}]}}],
        players=[dict(character_id='CHARACTER.VOLIBEAR_CHARACTER',current_hp=80,max_hp=80,max_energy=3,gold=99,
            deck=[c['serialized'] for c in deck],relics=[relic['serialized']])])
    removed=[dict(entity=1000+i,id=id,upgrade=0) for i,id in enumerate(['VOLIBEAR_B01']*4+['VOLIBEAR_B02']*4+['VOLIBEAR_B03','VOLIBEAR_B04'])]
    acquired=[]
    for i,c in enumerate(deck):
        base=e.CATALOG[c['id']]['faces'][0]
        acquired.append(dict(entity=c['entity'],id=c['id'],upgrade=c['upgrade'],upgraderCalled=c['upgrade']==1,owner=1,deckIndex=i,
            beforeKeywords=['Exhaust'] if base['self_exhaust'] else [],afterKeywords=c['keywords'],serialized=c['serialized']))
    r=dict(schemaVersion=2,scenario='save-load-catalog',token=token,pair='pair',phase=phase,mode=mode,caseId='S3',roomKind='active-entry',pid=pid,
        userRoot=root,checkpointPath=root+'/default/1/modded/profile1/saves/current_run.save',gameVersion='v0.107.1',gameCommit='59260271',testMode=False,
        assemblyMvid='00000000-0000-0000-0000-000000000001',acceptance=e.SCOPE,seed=seed,
        fixture=dict(directRunApi=True,statsExistedBefore=False,statsPresent=True,ftuesDisabledInIsolatedProfile=True,shouldSave=True,startedWithNeow=False,
            masterPreparation=dict(kind='explicit-native-catalog-master-construction-not-natural-acquisition',removed=removed,registryIds=sorted(e.CATALOG),acquired=acquired)),
        events=[dict(op='native-ui-forceclick',button=b) for b in ('Pause','SaveAndQuit')],checkpoint=copy.deepcopy(checkpoint),afterMenu=copy.deepcopy(checkpoint),
        initial=initial,interruption=dict(kind='paid-base-defend-state-fixture',payment=dict(action='PlayCardAction',state='Finished',actionId=1,
            context='GameActionPlayerChoiceContext',history=[dict(id='VOLIBEAR_B02',autoPlay=False,spent=1,index=0,count=1)],
            afterEnergySpent=[dict(id='VOLIBEAR_B02',amount=1,energy=2)],energyHistory=[1])),interrupted=interrupted,resumed=None,afterLoad=None,resumedCase=None,route=None)
    if phase!='prepare':
        r['resumed']=copy.deepcopy(initial)
        for key in ('runEntity','combatEntity','playerEntity','creatureEntity'):r['resumed'][key]+=10000
        for c in r['resumed']['deck']+[c for rows in r['resumed']['piles'].values() for c in rows]:
            for key in ('entity','owner','masterEntity'):
                if c[key] is not None:c[key]+=10000
        for relic in r['resumed']['relics']:
            for key in ('entity','owner'):relic[key]+=10000
        for enemy in r['resumed']['enemies']:enemy['entity']+=10000
        r['afterLoad']=copy.deepcopy(checkpoint);r['afterLoad']['num_reloads']=1
        r['afterLoad']['acts'][0]['saved_map']['points'][0]['can_modify']=True
        r['events'].append(dict(op='native-ui-forceclick',button='Continue'))
    if phase=='resume':
        for key in ('initial','interrupted','interruption','fixture','afterMenu'):r[key]=None
        r['events']=[dict(op='native-ui-forceclick',button='Continue')]
    expected={k:r[k] for k in ('token','pair','phase','mode','caseId','seed','pid','userRoot','checkpointPath')}
    return r,expected

class PersistenceTests(unittest.TestCase):
    def reject(self,mutate):
        r,x=fixture();mutate(r);errors=[]
        self.assertFalse(e.validate_phase(r,x,errors));self.assertTrue(errors)
    def test_positive_same(self):
        r,x=fixture();errors=[];self.assertTrue(e.validate_phase(r,x,errors),errors)
    def test_positive_restart(self):
        a,xa=fixture('restart','prepare');b,xb=fixture('restart','resume',22,'second')
        self.assertTrue(e.validate_pair(a,b,xa,xb,True,True))
    def test_missing89th(self):self.reject(lambda r:r['fixture']['masterPreparation']['registryIds'].pop())
    def test_177_cards(self):self.reject(lambda r:r['initial']['deck'].pop())
    def test_duplicate_master(self):self.reject(lambda r:r['initial']['deck'][1].update(entity=100))
    def test_upgrade_member_missing(self):self.reject(lambda r:r['initial']['deck'][1].update(upgrade=0))
    def test_token_intrinsic_shape_required(self):
        self.reject(lambda r:next(c for c in r['initial']['deck'] if c['id']=='VOLIBEAR_T01').update(shape='None'))
    def test_token_not_conversion(self):
        self.reject(lambda r:next(c for c in r['initial']['deck'] if c['id']=='VOLIBEAR_T02').update(converted=True))
    def test_other_card_cannot_be_claw(self):self.reject(lambda r:r['initial']['deck'][0].update(shape='Claw'))
    def test_deprecated_card(self):self.reject(lambda r:r['resumed']['deck'][0].update(nativeType='DeprecatedCard'))
    def test_wrong_owner(self):self.reject(lambda r:r['resumed']['deck'][0].update(owner=10002))
    def test_wrong_deck_version(self):self.reject(lambda r:r['resumed']['piles']['Hand'][0].update(masterEntity=10101))
    def test_x_cost_preserved(self):
        self.reject(lambda r:next(c for c in r['resumed']['deck'] if c['costsX']).update(costsX=False))
    def test_upgraded_cost_preserved(self):
        self.reject(lambda r:next(c for c in r['resumed']['deck'] if c['upgrade']==1 and c['cost']!=c['canonicalCost']).update(cost=99))
    def test_c14_keyword_upgrade_cache(self):
        self.reject(lambda r:next(c for c in r['fixture']['masterPreparation']['acquired'] if c['id']=='VOLIBEAR_C14' and c['upgrade']==1).update(afterKeywords=['Exhaust']))
    def test_persisted_native_variable_drift(self):self.reject(lambda r:r['resumed']['deck'][0]['vars']['Observed'].update(baseValue=2))
    def test_not_independent_numeric_oracle(self):
        # Arbitrary observed values consistent across entry/load are persistence,
        # not a fabricated authority for native DynamicVar numeric correctness.
        r,x=fixture()
        for key in ('initial','interrupted','resumed'):
            s=r[key];s['deck'][0]['vars']['Observed'].update(baseValue=777,enchantedValue=777)
            for rows in s['piles'].values():
                for card in rows:
                    if card['masterIndex']==0:card['vars']['Observed'].update(baseValue=777,enchantedValue=777)
        self.assertTrue(e.validate_phase(r,x))
    def test_face_text_independent(self):self.reject(lambda r:r['resumed']['deck'][0].update(description='造成999伤害。'))
    def test_saved_card_property_drift(self):self.reject(lambda r:r['resumed']['deck'][0]['serialized'].update(floor_added_to_deck=99))
    def test_relic_slot(self):self.reject(lambda r:r['resumed']['relics'][0].update(slot=1))
    def test_relic_owner(self):self.reject(lambda r:r['resumed']['relics'][0].update(owner=12))
    def test_old_relic_instance(self):self.reject(lambda r:r['resumed']['relics'][0].update(entity=4))
    def test_fake_finished(self):self.reject(lambda r:r['interruption']['payment'].update(context=None,history=[]))
    def test_missing_hook_payment(self):self.reject(lambda r:r['interruption']['payment'].update(afterEnergySpent=[]))
    def test_wrong_paid_variant(self):self.reject(lambda r:r['interrupted']['piles']['Discard'][0].update(upgrade=1))
    def test_num_reloads_exact(self):self.reject(lambda r:r['afterLoad'].update(num_reloads=2))
    def test_map_native_default_mandatory(self):self.reject(lambda r:r['afterLoad']['acts'][0]['saved_map']['points'][0].pop('can_modify'))
    def test_no_time_exclusion(self):self.reject(lambda r:r['afterLoad'].update(start_time=1))
    def test_pid_binding(self):self.reject(lambda r:r.update(pid=999))
    def test_stale_token(self):self.reject(lambda r:r.update(token='stale'))
    def test_no_unsupported_case_acceptance(self):self.reject(lambda r:r.update(caseId='S4'))
    def test_no_cross_schema_acceptance(self):self.reject(lambda r:r.update(schemaVersion=1))
    def test_mvid_pair_binding(self):
        a,xa=fixture('restart','prepare');b,xb=fixture('restart','resume',22,'second');b['assemblyMvid']='00000000-0000-0000-0000-000000000002'
        self.assertFalse(e.validate_pair(a,b,xa,xb,True,True))
    def test_shared_gate_cannot_be_bypassed(self):
        a,xa=fixture('restart','prepare');b,xb=fixture('restart','resume',22,'second')
        self.assertFalse(e.validate_pair(a,b,xa,xb,False,True))
    def test_log_envelope(self):
        r,x=fixture();log=e.PREFIX+json.dumps(r)+'\n[Volibear] SHUTDOWN_BEGIN '+x['token']
        self.assertTrue(e.parse_log(log,x)[1]);self.assertFalse(e.parse_log(log+'\n'+log,x)[1])
    def test_boolean_owner_rejected(self):self.reject(lambda r:r['initial']['deck'][0].update(owner=True))
    def test_boolean_index_rejected(self):self.reject(lambda r:r['initial']['deck'][1].update(masterIndex=True))
    def test_identity_alias_across_native_types(self):self.reject(lambda r:r['initial'].update(runEntity=3))
    def test_driver_gates_disk_before_restart(self):
        import tempfile
        import save_load_catalog_pair as driver
        a,xa=fixture('restart','prepare')
        checks={k:True for k in ('exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized','runtime_isolation','teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw')}
        report=dict(raw=a,expected=xa,checks=checks,passed=True)
        called=[]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'checkpoint.json';path.write_text(json.dumps(a['afterMenu']),encoding='utf-8')
            self.assertEqual(driver.gate_then_resume(report,path,lambda:called.append(1) or 'B'),'B')
            checks['runtime_isolation']=False
            self.assertIsNone(driver.gate_then_resume(report,path,lambda:called.append(2)))
            checks['runtime_isolation']=True;path.write_text('{}',encoding='utf-8')
            self.assertIsNone(driver.gate_then_resume(report,path,lambda:called.append(3)))
        self.assertEqual(called,[1])
    def test_driver_no_bootstrap_or_profile_override(self):
        import save_load_catalog_pair as driver
        self.assertNotIn('--bootstrap',driver.phase_command(Path('game'),Path('out'),'headless',1000))
        source=Path(driver.__file__).read_text(encoding='utf-8')
        self.assertIn("'--execute-native'",source);self.assertIn("'--seed'",source)
        self.assertNotIn("'--profile'",source)
        self.assertIn('exist_ok=False',source)
    def test_source_native_lifecycle_no_surrogate(self):
        source=PROBE.read_text(encoding='utf-8')
        for wanted in ('RemoveFromDeck','run.CreateCard(model, player)','CardCmd.Upgrade(card)','EnterMapCoord','ForceClick','new PlayCardAction(defend, null)','card.CurrentUpgradeLevel == level'):
            self.assertIn(wanted,source)
        for forbidden in ('.LoadRun(','.FromSerializable(','.SaveRun(','.Kill(','.CheckWinCondition('):self.assertNotIn(forbidden,source)

if __name__=='__main__':unittest.main()
