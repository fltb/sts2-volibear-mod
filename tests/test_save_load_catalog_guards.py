"""Independent S3 publication gates; no game process is launched."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_save_load_catalog_evidence import fixture, PROBE
import save_load_catalog_evidence as e
import save_load_catalog_pair as driver

class CatalogGuards(unittest.TestCase):
    def reject(self, mutate):
        r,x=fixture();mutate(r);errors=[]
        self.assertFalse(e.validate_phase(r,x,errors));self.assertTrue(errors)

    def test_non_s3_matching_bindings_are_still_unsupported(self):
        for case in ('S1','S2','S4','S5-finished','S5-reward-commit','',None):
            r,x=fixture();r['caseId']=x['caseId']=case
            self.assertFalse(e.validate_phase(r,x))

    def test_old_full_stage_envelope_cannot_be_accepted(self):
        self.reject(lambda r:r.update(scenario='save-load-persistence'))
        r,x=fixture();log='[Volibear] SAVE_PERSISTENCE_RESULT '+json.dumps(r)+'\n[Volibear] SHUTDOWN_BEGIN '+x['token']
        self.assertFalse(e.parse_log(log,x)[1])

    def test_non_s3_public_api_rejects_before_side_effects(self):
        for case in ('S4','S5-finished','S5-reward-commit','S1'):
            with patch.object(driver.h,'validate_game',side_effect=AssertionError('must not touch game')),patch.object(driver,'create_owned_profile',side_effect=AssertionError('must not create profile')):
                with self.assertRaisesRegex(ValueError,'NOT_SUPPORTED'):driver.run_pair(Path('unused'),case,'restart')

    def test_non_s3_phase_helper_cannot_bypass_public_gate(self):
        for case in ('S4','S5-finished','S5-reward-commit'):
            with self.assertRaisesRegex(ValueError,'NOT_SUPPORTED'):
                driver.launch_phase(None,None,None,case,'restart','prepare',None,None,None,None,None,None)

    def test_phase_helper_rejects_invalid_mode_before_filesystem(self):
        with self.assertRaisesRegex(ValueError,'Invalid phase/mode'):
            driver.launch_phase(None,None,None,'S3','restart','same',None,None,None,None,None,None)

    def test_cli_requires_opt_in_and_rejects_non_s3(self):
        for args in ([],['--execute-native','--case','S4'],['--execute-native','--case','S5-finished']):
            with patch.object(sys,'argv',['catalog_pair']+args),patch.object(driver,'run_pair',side_effect=AssertionError('no launch')):
                with self.assertRaises(SystemExit) as failure:driver.main()
                self.assertEqual(failure.exception.code,2)

    def test_old_hp30_and_butt_fixture_is_a_negative_control(self):
        def mutate(r):
            for key in ('initial','interrupted','resumed'):r[key]['enemies'][0].update(hp=30,maxHp=30,move='BUTT')
        self.reject(mutate)

    def test_original_master_value_drift_negative_controls(self):
        for field in ('baseValue','enchantedValue'):
            self.reject(lambda r,k=field:r['interrupted']['deck'][0]['vars']['Observed'].update({k:999999}))

    def test_synchronized_master_clone_value_drift_still_fails_continuity(self):
        for field in ('baseValue','enchantedValue'):
            def mutate(r,k=field):
                s=r['interrupted'];s['deck'][0]['vars']['Observed'][k]=999999
                for rows in s['piles'].values():
                    for card in rows:
                        if card['masterIndex']==0:card['vars']['Observed'][k]=999999
            self.reject(mutate)

    def test_whole_interrupted_graph_rebase_is_not_a_new_combat(self):
        def mutate(r):
            s=r['interrupted']
            for k in ('runEntity','combatEntity','playerEntity','creatureEntity'):s[k]+=20000
            for card in s['deck']+[c for rows in s['piles'].values() for c in rows]:
                for k in ('entity','owner','masterEntity'):
                    if card[k] is not None:card[k]+=20000
            for relic in s['relics']:
                for k in ('entity','owner'):relic[k]+=20000
            for enemy in s['enemies']:enemy['entity']+=20000
        self.reject(mutate)

    def test_original_clone_unknown_serialized_property_negative_control(self):
        self.reject(lambda r:r['interrupted']['piles']['Hand'][0]['serialized'].update(unrelated_leak=1))

    def test_synchronized_clone_variable_drift_is_not_conservation(self):
        def mutate(r):
            for c in r['interrupted']['piles']['Hand']:c['vars']['Observed']['baseValue']=999999
        self.reject(mutate)

    def test_preview_only_context_is_still_not_a_false_failure(self):
        r,x=fixture()
        for card in r['interrupted']['deck']+[c for rows in r['interrupted']['piles'].values() for c in rows]:card['vars']['Observed']['previewValue']=999999
        self.assertTrue(e.validate_phase(r,x))

    def test_native_serialization_unknown_field_cannot_be_dropped(self):
        self.reject(lambda r:r['afterLoad']['players'][0]['deck'][0].update(unrelated_leak=1))

    def test_whitelist_accepts_only_true_or_native_missing_default(self):
        r,x=fixture()
        for key in ('checkpoint','afterMenu','afterLoad'):r[key]['acts'][0]['saved_map']['points'][0]['can_modify']=True
        self.assertTrue(e.validate_phase(r,x))
        r['afterLoad']['acts'][0]['saved_map']['points'][0]['can_modify']=False
        self.assertFalse(e.validate_phase(r,x))
        for key in ('checkpoint','afterMenu'):r[key]['acts'][0]['saved_map']['points'][0]['can_modify']=False
        self.assertFalse(e.validate_phase(r,x))

    def test_failure_or_wrong_case_cannot_cross_pre_b_gate(self):
        r,x=fixture('restart','prepare');r['caseId']=x['caseId']='S4'
        checks={k:True for k in ('exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized','runtime_isolation','teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw')}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'save';path.write_text(json.dumps(r['afterMenu']),encoding='utf-8')
            self.assertIsNone(driver.gate_then_resume(dict(raw=r,expected=x,checks=checks),path,lambda:self.fail('B must not start')))

    def test_probe_does_not_contain_or_install_unreviewed_routes(self):
        source=PROBE.read_text(encoding='utf-8')
        for forbidden in ('partial class','InstallRoutes','ObserveDamageBranch','ObserveHistory','FinishedReady','WinNormally','RelicTwice','ClaimAndAdvance','EndingDamage','_observedAction','Task.Run('):self.assertNotIn(forbidden,source)
        install=source[source.index('public static void Install()'):source.index('private static bool Ready()')]
        self.assertLess(install.index('RequireCatalogCase();'),install.index('if (_installed)'))
        self.assertEqual(source.count('CreateClassProcessor('),1)
        self.assertIn('typeof(ObservePayment)',source)
        self.assertIn('NOT_SUPPORTED: save-load-catalog supports only S3',source)

    def test_candidate_imports_are_unambiguous_and_no_fullstage_oracle_dispatch(self):
        self.assertEqual(Path(e.__file__).resolve().parent,Path(driver.__file__).resolve().parent)
        self.assertEqual(driver.CASES,('S3',))
        source=Path(e.__file__).read_text(encoding='utf-8')
        self.assertNotIn('save_load_persistence_cases',source)
        self.assertNotIn('sys.path.insert(0',source)
        self.assertNotIn('save_load_persistence_evidence',Path(driver.__file__).read_text(encoding='utf-8'))

    def test_isolated_compile_manifest_has_only_catalog_source(self):
        project=PROBE.parent/'probe.csproj'
        if project.is_file():
            import xml.etree.ElementTree as ET
            root=ET.parse(project).getroot()
            self.assertEqual([node.attrib['Include'] for node in root.iter('Compile')],['SaveLoadCatalogProbe.cs'])
            self.assertEqual(root.find('.//EnableDefaultCompileItems').text,'false')
        else:
            self.assertTrue((PROBE.parent/'Volibear.csproj').is_file())
            self.assertNotIn('partial class',PROBE.read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
