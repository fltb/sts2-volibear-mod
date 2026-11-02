"""Launch routing and envelope negative controls; these tests never run the game."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import native_suite as suite
import native_suite_evidence as gate
import test_acceptance_runner as routing_helpers
STOCK = dict(routing_helpers.STOCK,runtime_errors=[])
from test_save_load_evidence import fixture as save_fixture
from test_native_product_flow import fixture as flow_fixture
from test_character_integration_evidence import fixture as character_fixture
from test_domain_suppression_evidence import receipt as suppression_receipt, log_for as suppression_log
from test_architect_ending_evidence import fixture as ending_fixture


class SuiteRouting(unittest.TestCase):
    setUp = routing_helpers.AcceptanceRunnerTests.setUp
    run_scenario = routing_helpers.AcceptanceRunnerTests.run_scenario
    def test_same_process_all_seven_stages_route_once_and_clear_old_inputs(self):
        faces = tuple(suite.h.CARD_FACE_CASES[:2]); lifecycle = ('U07-base',)
        report, env, command, oracle, _, shell = self.run_scenario('native-suite',
            initial_env={'VOLIBEAR_TEST_DATA_ROOT':str(self.directory/'data'),
                         'VOLIBEAR_TEST_ENGAGE':'1','VOLIBEAR_TEST_MANUAL_PLAY':'1',
                         'VOLIBEAR_SAVE_PHASE':'resume'}, inherited_adapter='1',
            card_face_batch=faces, card_lifecycle_cases=lifecycle,
            evidence='native_suite_evidence', evidence_value={'errors':[]})
        self.assertEqual(report['status'],'passed')
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'],'native-suite')
        self.assertEqual(env['VOLIBEAR_TEST_CARD_FACE_BATCH'],','.join(faces))
        self.assertEqual(json.loads(env['VOLIBEAR_TEST_CARD_LIFECYCLE_CASES']),list(lifecycle))
        self.assertIn('--bootstrap',command)
        for name in ('VOLIBEAR_TEST_ENGAGE','VOLIBEAR_TEST_MANUAL_PLAY','VOLIBEAR_SAVE_PHASE'):
            self.assertNotIn(name,env)
        oracle.assert_called_once();shell.assert_not_called()

    def test_failed_substage_or_runtime_never_becomes_suite_success(self):
        for errors, log in ((['missing native card receipt'],None),([], 'ERROR: real native error\n')):
            args = dict(card_face_batch=('B01-base-plain',),card_lifecycle_cases=('U07-base',),
                        initial_env={'VOLIBEAR_TEST_DATA_ROOT':str(self.directory/'data')},
                        evidence='native_suite_evidence',evidence_value={'errors':errors})
            if log: args['log'] = log
            report,*_ = self.run_scenario('native-suite',**args)
            self.assertEqual(report['status'],'failed')

    def test_entry_calls_one_stock_and_one_mod_process(self):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(suite.h,'IS_WINDOWS',True))
            stack.enter_context(mock.patch.object(suite.h,'display_command'))
            stack.enter_context(mock.patch.object(suite.h,'validate_game'))
            baseline=stack.enter_context(mock.patch.object(suite.h,'stock_teardown',return_value=(set(),STOCK)))
            launch=stack.enter_context(mock.patch.object(suite.h,'run_once',return_value={'status':'passed'}))
            suite.run_suite(self.directory,face_cases=('B01-base-plain',),lifecycle_cases=('U07-base',))
        baseline.assert_called_once();launch.assert_called_once()
        self.assertEqual(launch.call_args.kwargs['scenario'],'native-suite')
        self.assertEqual(launch.call_args.kwargs['display'],'background')

    def test_bad_options_and_failed_stock_never_launch_mod(self):
        for invalid in (dict(display='window'),dict(timeout=True),dict(timeout=28801),dict(frames=1728001),dict(frames=2),dict(face_cases=[]),
                        dict(lifecycle_cases=['U07-base','U07-base']),dict(presentation_mode='all')):
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(suite.h,'IS_WINDOWS',True))
                baseline=stack.enter_context(mock.patch.object(suite.h,'stock_teardown'))
                launch=stack.enter_context(mock.patch.object(suite.h,'run_once'))
                with self.assertRaises((ValueError,RuntimeError)):suite.run_suite(self.directory,**invalid)
                baseline.assert_not_called();launch.assert_not_called()
        for stock in ({'successful':False},dict(STOCK,exit_code=1),dict(STOCK,exit_code=False),
                      dict(STOCK,timed_out=True),dict(STOCK,runtime_errors=['native-error'])):
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(suite.h,'IS_WINDOWS',True))
                stack.enter_context(mock.patch.object(suite.h,'display_command'))
                stack.enter_context(mock.patch.object(suite.h,'validate_game'))
                stack.enter_context(mock.patch.object(suite.h,'stock_teardown',return_value=(set(),stock)))
                launch=stack.enter_context(mock.patch.object(suite.h,'run_once'))
                with self.assertRaises(RuntimeError):suite.run_suite(self.directory)
                launch.assert_not_called()

    def test_native_case_timings_are_observations_not_speed_overrides(self):
        host=(ROOT/'src/Volibear/NativeAcceptanceRunHost.cs').read_text()
        cards=(ROOT/'src/Volibear/CardFaceAcceptanceProbe.cs').read_text()
        for stage in ('start-run','start-room-quiet','exit-map','exit-menu'):
            self.assertIn('Timing("'+stage+'",timing)',host)
        self.assertIn('System.Diagnostics.Stopwatch.StartNew()',host)
        self.assertIn('CARD_FACE_TIMING case=',cards)
        self.assertIn('actionClock.ElapsedMilliseconds',cards)
        for source in (host,cards):
            self.assertIn('Engine.GetFramesPerSecond()',source)
            self.assertNotIn('Engine.TimeScale =',source)

    def test_suite_reachable_drivers_have_no_input_simulation(self):
        names=('NativeVerificationSuite','NativeAcceptanceRunHost','NativeAutomationSelector','NativeProductFlowProbe','CharacterIntegrationProbe',
               'CardFaceAcceptanceProbe','CardLifecycleAcceptanceProbe','PresentationAcceptanceProbe','SaveLoadContractProbe',
               'DomainSuppressionAcceptanceProbe', 'ArchitectEndingAcceptanceProbe')
        for name in names:
            source=(ROOT/'src/Volibear'/f'{name}.cs').read_text(encoding='utf-8')
            for forbidden in ('ForceClick(', 'PushInput(', 'InputEvent', 'EmitSignal(', 'SendInput(', 'UiHelper.Click('):
                self.assertNotIn(forbidden,source,name)
        driver=(ROOT/'src/Volibear/NativeVerificationSuite.cs').read_text()
        self.assertEqual(driver.count('NGame.Instance!.Quit()'),1)
        for name in ('DomainSuppressionAcceptanceProbe.RunManaged','ArchitectEndingAcceptanceProbe.RunManaged','CardFaceAcceptanceProbe.RunBatch','CardLifecycleAcceptanceProbe.RunBatch',
                     'PresentationAcceptanceProbe.Run','NativeProductFlowProbe.Run','SaveLoadContractProbe.Run'):
            self.assertIn(name,driver)
        flow=(ROOT/'src/Volibear/NativeProductFlowProbe.cs').read_text()
        for forbidden in ('EnterRoomDebug(', 'DebugWin(', 'CreateCard(', 'CardPileCmd.Add(',
                          'SetDebugTravelEnabled(', 'OnRelease(', 'OptionButtonClicked('):
            self.assertNotIn(forbidden,flow)

    def test_source_zip_without_git_keeps_native_verdict_and_report(self):
        unavailable=dict(git_commit=None,dirty=None,git_metadata='unavailable:FileNotFoundError')
        with mock.patch.object(suite.h,'repository_metadata',return_value=unavailable):
            report,*_ = self.run_scenario('native-suite',
                initial_env={'VOLIBEAR_TEST_DATA_ROOT':str(self.directory/'data')},
                card_face_batch=('B01-base-plain',),card_lifecycle_cases=('U07-base',),
                evidence='native_suite_evidence',evidence_value={'errors':[]})
        self.assertEqual(report['status'],'passed');self.assertIsNone(report['git_commit'])
        self.assertIsNone(report['dirty']);self.assertEqual(report['git_metadata'],unavailable['git_metadata'])

    def test_optional_git_metadata_distinguishes_missing_repo_from_clean_repo(self):
        for error in (FileNotFoundError('git'),suite.h.subprocess.CalledProcessError(128,['git'])):
            with mock.patch.object(suite.h.subprocess,'check_output',side_effect=error):
                actual=suite.h.repository_metadata()
            self.assertIsNone(actual['git_commit']);self.assertIsNone(actual['dirty'])
            self.assertTrue(actual['git_metadata'].startswith('unavailable:'))


class SuiteEnvelope(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='volibear-suite-oracle-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.checkpoint=self.root/'default/1/modded/profile1/saves/current_run.save'
        self.checkpoint.parent.mkdir(parents=True)
        saved,_=save_fixture(mode='same-process',phase='same',token='suite-test')
        old_seed=saved['seed']
        saved=json.loads(json.dumps(saved).replace(old_seed,'VOLIBEARTEST'))
        saved.update(pair='suite-test',userRoot=str(self.root),checkpointPath=str(self.checkpoint))
        self.checkpoint.write_text(json.dumps(saved['afterLoad']))
        self.saved=saved
        self.final=dict(schema=2,token='suite-test',pid=100,completed=gate.STAGES,finished=True,
                        osInput=False,simulatedClicks=False,processRestarts=0,selector='CardSelectCmd.UseSelector',
                        rewardDecisionBoundary='NCardRewardSelectionScreen.OptionSelected',
                        cleanup=dict(RunNull=True,CombatNull=True,InProgress=False,QueueEmpty=True,ActionNull=True,HistoryVisible=0),
                        scope='native-paid-card-faces-lifecycle-presentation-product-flow-and-checkpoint',
                        exclusions=['live-multiplayer-peers','physical-input','human-visual-listening-review','disk-process-restart'])

    def log(self):
        character = character_fixture()
        character.update(token='suite-test', pid=100)
        from test_character_integration_evidence import BaseLibRuntimeOracle
        framework = BaseLibRuntimeOracle()
        framework.setUp()
        return '\n'.join(framework.lines + [gate.BEGIN+json.dumps(dict(token='suite-test',pid=100)),
            '[Volibear] CHARACTER_INTEGRATION_RESULT '+json.dumps(character),
            suppression_log([dict(suppression_receipt(name), token='suite-test')
                             for name in ('sandpit', 'knights', 'self')]),
            '[Volibear] ARCHITECT_ENDING_RESULT ' + json.dumps(dict(ending_fixture(), token='suite-test')),
            '[Volibear] CARD_FACE_BATCH_RESULT {}','[Volibear] CARD_LIFECYCLE_BATCH_RESULT {}',
            '[Volibear] PRESENTATION_ACCEPTANCE_RESULT {}','[Volibear] NATIVE_PRODUCT_FLOW_RESULT '+json.dumps(flow_fixture()),
            '[Volibear] SAVE_LOAD_RESULT '+json.dumps(self.saved),
            gate.RESULT+json.dumps(self.final),'[Volibear] SHUTDOWN_BEGIN suite-test'])

    def test_missing_failed_or_misordered_suppression_receipt_fails_suite(self):
        lines = self.log().splitlines()
        index = next(i for i, line in enumerate(lines) if 'DOMAIN_SUPPRESSION_RESULT ' in line)
        missing = lines[:index] + lines[index + 1:]
        self.assertTrue(self.evaluate('\n'.join(missing))['errors'])
        # Mutate an independently required boolean, not just the top-level passed flag.
        row = json.loads(lines[index].split('DOMAIN_SUPPRESSION_RESULT ', 1)[1])
        row['checks'][next(iter(row['checks']))] = False
        corrupted = list(lines)
        corrupted[index] = '[Volibear] DOMAIN_SUPPRESSION_RESULT ' + json.dumps(row)
        self.assertTrue(self.evaluate('\n'.join(corrupted))['errors'])
        moved = missing + [lines[index]]
        self.assertTrue(self.evaluate('\n'.join(moved))['errors'])

    def evaluate(self,log=None,*,face_error=False,lifecycle_ok=True,presentation_errors=()):
        # Existing face/lifecycle/presentation oracles have their own receipt tests.
        # Keep the save oracle and actual disk JSON validation live here.
        with mock.patch.object(gate,'extract_card_face_batch',side_effect=ValueError('missing case') if face_error else None), \
             mock.patch.object(gate,'card_lifecycle_batch_evidence',return_value=({},lifecycle_ok)), \
             mock.patch.object(gate,'presentation_media_report',return_value={'errors': list(presentation_errors)}):
            return gate.check_log(self.log() if log is None else log,'suite-test',('B01-base-plain',),
                                  ('U07-base',),'cards',self.root/'presentation',self.root)

    def test_complete_single_process_with_actual_checkpoint_passes_envelope(self):
        self.assertEqual(self.evaluate()['errors'],[])

    def test_failed_existing_oracle_and_missing_case_never_pass(self):
        for kwargs in (dict(face_error=True),dict(lifecycle_ok=False),dict(presentation_errors=['missing screenshot'])):
            self.assertTrue(self.evaluate(**kwargs)['errors'])

    def test_no_self_awarded_completion_input_or_restarts(self):
        for key,value in (('pid',101),('finished',False),('processRestarts',1),('osInput',True),
                          ('simulatedClicks',True),('completed',gate.STAGES[:-1]),('schema',True)):
            prior=self.final[key];self.final[key]=value
            with self.subTest(key=key):self.assertTrue(self.evaluate()['errors'])
            self.final[key]=prior
        self.final['cleanup']['ActionNull']=False
        self.assertTrue(self.evaluate()['errors'])

    def test_missing_duplicate_out_of_order_stage_and_native_error_fail(self):
        original=self.log()
        for bad in (original.replace('[Volibear] CARD_LIFECYCLE_BATCH_RESULT {}\n',''),
                    original+'\n'+gate.RESULT+json.dumps(self.final),
                    original.replace('[Volibear] CARD_FACE_BATCH_RESULT {}','[Volibear] NATIVE_SUITE_ERROR failed'),
                    original.replace('[Volibear] SHUTDOWN_BEGIN suite-test',''),
                    original+'\n[Volibear] SHUTDOWN_BEGIN suite-test'):
            self.assertTrue(self.evaluate(bad)['errors'])

    def test_checkpoint_missing_changed_and_symlinked_fail(self):
        self.checkpoint.write_text('{}');self.assertTrue(self.evaluate()['errors'])
        self.checkpoint.unlink();self.assertTrue(self.evaluate()['errors'])
        target=self.root/'actual.json';target.write_text(json.dumps(self.saved['afterLoad']))
        self.checkpoint.symlink_to(target)
        self.assertTrue(self.evaluate()['errors'])


if __name__=='__main__':unittest.main()
