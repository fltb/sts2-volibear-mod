"""Launch-config tests; no game, deployment, shared runner edits or native execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import enemy_exploration_run_config as config
from enemy_exploration_evidence import prepare_selection
from test_enemy_exploration_evidence import fixture


class ExplorationRunConfigTests(unittest.TestCase):
    def setUp(self):
        self.base = (Path(__file__).resolve().parents[1] / '.local').resolve()
        self.base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='exploration-config-test-', dir=self.base)
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, self.base)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.prior = self.source / 'prior'
        self.prior.mkdir()
        self.smoke, self.smoke_selection, self.catalog = fixture()
        self.selection = prepare_selection(self.catalog, mode='explore', prerequisite=self.smoke)
        self.selection_path = self.source / 'selection-source.json'
        self.catalog_path = self.source / 'catalog-source.json'
        self.report_path = self.prior / 'report.json'
        self.artifact_path = self.prior / config.MANIFEST_NAME
        self.write_json(self.selection_path, self.selection)
        self.write_json(self.catalog_path, self.catalog)
        raw = self.write_json(self.artifact_path, self.smoke)
        self.report = dict(schema=1, run_id='current', mode='real-game-window', scenario='enemy-exploration',
            game_version='0.107.1', game_commit='59260271', status='passed', exit_code=0, timed_out=False,
            checks={key: True for key in config.REQUIRED_GATES},
            diagnostics=dict(shutdown_marker_seen=True, runtime_errors=[]),
            combat_tests=dict(token='current',scenario='enemy-exploration',acceptance='bounded-native-exploration-only',
                manifest=config.MANIFEST_NAME,completed=True,failure=None,validationErrors=[],completeAiCoverage=False,
                caseCount=6,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        self.write_json(self.report_path, self.report)
        self.counter = 0

    def tearDown(self):
        # Verify the exact managed temporary target before its recursive cleanup.
        self.assertEqual(self.root.resolve().parent, self.base)
        self.assertTrue(self.root.name.startswith('exploration-config-test-'))
        self.temp.cleanup()

    @staticmethod
    def write_json(path, value):
        raw = b'  '+json.dumps(value, ensure_ascii=False, indent=1).encode('utf-8')+b'\r\n  '
        path.write_bytes(raw)
        return raw

    def launch_inputs(self, report=True, directory=None):
        self.counter += 1
        directory = directory or self.root / ('run-'+str(self.counter))
        return config.prepare_run_inputs(directory, self.selection_path, self.catalog_path,
                                         self.report_path if report else None)

    def rebind_artifact(self, artifact):
        raw = self.write_json(self.artifact_path, artifact)
        report = copy.deepcopy(self.report)
        report['combat_tests'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        self.write_json(self.report_path,report)

    def test_successful_complete_report_approves_and_freezes_exact_bytes(self):
        originals={config.SELECTION_NAME:self.selection_path.read_bytes(),config.CATALOG_NAME:self.catalog_path.read_bytes(),
                   config.REPORT_NAME:self.report_path.read_bytes(),config.MANIFEST_NAME:self.artifact_path.read_bytes()}
        env, frozen, catalog, prerequisite=self.launch_inputs()
        self.assertTrue(frozen.is_absolute())
        self.assertEqual(Path(env['VOLIBEAR_TEST_MATRIX_SELECTION']),frozen)
        self.assertEqual(env['VOLIBEAR_TEST_EXPLORATION_APPROVED'],'current')
        self.assertEqual(catalog,self.catalog)
        self.assertEqual(prerequisite,self.smoke)
        for name,raw in originals.items():
            self.assertEqual((frozen.parent/name).read_bytes(),raw)
        for path in (self.selection_path,self.catalog_path,self.report_path,self.artifact_path):
            path.write_bytes(b'changed after freezing')
        for name,raw in originals.items():
            self.assertEqual((frozen.parent/name).read_bytes(),raw)
        self.assertEqual(prerequisite['token'],'current')
        self.assertEqual(catalog['gameVersion'],'v0.107.1')

    def test_smoke_has_no_approval_and_rejects_supplied_prerequisite(self):
        self.write_json(self.selection_path,self.smoke_selection)
        env,frozen,cat,prereq=self.launch_inputs(report=False)
        self.assertNotIn('VOLIBEAR_TEST_EXPLORATION_APPROVED',env)
        self.assertIsNone(prereq)
        self.assertEqual({p.name for p in frozen.parent.iterdir()},{config.SELECTION_NAME,config.CATALOG_NAME})
        with self.assertRaises(ValueError): self.launch_inputs(report=True)
        bad=copy.deepcopy(self.smoke_selection);bad['prerequisiteToken']='current'
        self.write_json(self.selection_path,bad)
        with self.assertRaises(ValueError): self.launch_inputs(report=False)

    def test_explore_missing_report_or_artifact_rejects_before_freezing(self):
        with self.assertRaises(ValueError): self.launch_inputs(report=False)
        with self.assertRaises(ValueError):
            config.prepare_run_inputs(self.root/'missing',self.selection_path,self.catalog_path,self.prior/'missing-report.json')
        self.artifact_path.write_bytes(b'not json')
        with self.assertRaises(ValueError): self.launch_inputs()
        self.assertFalse(any(self.root.glob('run-*/'+config.SNAPSHOT_DIRECTORY)))

    def test_failed_or_nonwindow_report_never_approves_completed_native_artifact(self):
        mutations=dict(status='failed',exit_code=1,timed_out=True,mode='real-game-headless',
                       scenario='enemy-matrix-mvp',game_version='0.107.2',game_commit='other',schema=True)
        for key,value in mutations.items():
            with self.subTest(key=key):
                report=copy.deepcopy(self.report);report[key]=value
                self.write_json(self.report_path,report)
                with self.assertRaises(ValueError): self.launch_inputs()
        report=copy.deepcopy(self.report);report['exit_code']=False
        self.write_json(self.report_path,report)
        with self.assertRaises(ValueError): self.launch_inputs()

    def test_every_exact_public_and_scenario_gate_must_exist_and_be_true(self):
        self.assertEqual(len(config.PUBLIC_GATES),8)
        self.assertEqual(len(config.REQUIRED_GATES),9)
        for key in config.REQUIRED_GATES:
            for mode in ('missing','false','integer'):
                with self.subTest(key=key,mode=mode):
                    report=copy.deepcopy(self.report)
                    if mode=='missing': del report['checks'][key]
                    else: report['checks'][key]=False if mode=='false' else 1
                    self.write_json(self.report_path,report)
                    with self.assertRaises(ValueError): self.launch_inputs()
        report=copy.deepcopy(self.report);report['checks']['invented_gate']=True
        self.write_json(self.report_path,report)
        with self.assertRaises(ValueError): self.launch_inputs()

    def test_diagnostics_must_independently_confirm_no_runtime_failure_and_shutdown(self):
        for diagnostics in ({},dict(shutdown_marker_seen=False,runtime_errors=[]),
                            dict(shutdown_marker_seen=True,runtime_errors=['late native error']),
                            dict(shutdown_marker_seen=True,runtime_errors=None)):
            report=copy.deepcopy(self.report);report['diagnostics']=diagnostics
            self.write_json(self.report_path,report)
            with self.assertRaises(ValueError): self.launch_inputs()

    def test_summary_hash_size_token_manifest_and_completion_are_bound(self):
        for key,value in dict(sha256='0'*64,bytes=1,token='stale',manifest='../enemy-exploration.json',
                              scenario='enemy-matrix-mvp',completed=False,failure='error',validationErrors=['bad'],
                              completeAiCoverage=True,caseCount=5).items():
            with self.subTest(key=key):
                report=copy.deepcopy(self.report);report['combat_tests'][key]=value
                self.write_json(self.report_path,report)
                with self.assertRaises(ValueError): self.launch_inputs()
        report=copy.deepcopy(self.report);report['run_id']='wrong'
        self.write_json(self.report_path,report)
        with self.assertRaises(ValueError): self.launch_inputs()

    def test_rebound_artifact_must_still_be_valid_native_smoke(self):
        for mutate in (lambda d:d.__setitem__('token','stale'),
                       lambda d:d.__setitem__('gameVersion','v0.107.2'),
                       lambda d:d.__setitem__('gameCommit','other'),
                       lambda d:d['selection'].__setitem__('mode','explore'),
                       lambda d:d['cases'][2]['terminal']['player'].__setitem__('alive',True),
                       lambda d:d['cases'][1]['afterExit'].__setitem__('runIsNull',False)):
            artifact=copy.deepcopy(self.smoke);mutate(artifact)
            self.rebind_artifact(artifact)
            with self.assertRaises(ValueError): self.launch_inputs()

    def test_bad_catalog_and_selection_are_rejected(self):
        bad=copy.deepcopy(self.catalog);bad['counts']['actEncounters']=0
        self.write_json(self.catalog_path,bad)
        with self.assertRaises(ValueError): self.launch_inputs()
        self.write_json(self.catalog_path,self.catalog)
        bad=copy.deepcopy(self.selection);bad['cases'][0]['act']='ACT.UNKNOWN'
        self.write_json(self.selection_path,bad)
        with self.assertRaises(ValueError): self.launch_inputs()

    def test_existing_snapshot_never_overwritten_and_duplicate_json_is_rejected(self):
        directory=self.root/'same-run'
        env,frozen,cat,prereq=self.launch_inputs(directory=directory)
        original=frozen.read_bytes()
        with self.assertRaises(ValueError): self.launch_inputs(directory=directory)
        self.assertEqual(frozen.read_bytes(),original)
        self.selection_path.write_bytes(b'{"mode":"smoke","mode":"explore"}')
        with self.assertRaises(ValueError): self.launch_inputs()


if __name__=='__main__': unittest.main()
