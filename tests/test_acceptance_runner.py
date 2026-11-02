"""Acceptance runner routing with mocked launches; no native-game pass is claimed."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import headless

TOKEN = 'routing-only'
CLEAN_LOG = ('Steam initialization skipped\n[Volibear] LOAD_OK\n'
             '[Volibear] ISOLATION_OK steam=false\n')
STOCK = dict(successful=True, exit_code=0, timed_out=False)


class AcceptanceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='volibear-runner-test-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def run_scenario(self, scenario, *, initial_env=None, log=CLEAN_LOG,
                     evidence=None, evidence_value=None, inherited_adapter='0', **options):
        env = dict(initial_env or {})
        command = ['game', '--audio-driver', 'Dummy', '--force-steam=off']
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(headless, 'IS_WINDOWS', True))
            stack.enter_context(mock.patch.object(headless, 'new_run_id', return_value=TOKEN))
            prepared = stack.enter_context(mock.patch.object(headless, 'prepare_run',
                return_value=(self.directory, env, command)))
            launched = stack.enter_context(mock.patch.object(headless, 'launch', return_value=(0, False)))
            stack.enter_context(mock.patch.object(headless, 'combined_log', return_value=log))
            stack.enter_context(mock.patch.object(headless.subprocess, 'check_output', side_effect=['commit', '']))
            shell = stack.enter_context(mock.patch.object(headless.subprocess, 'run'))
            stack.enter_context(mock.patch.dict(os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': inherited_adapter}))
            checked = (stack.enter_context(mock.patch.object(headless, evidence, return_value=evidence_value))
                       if evidence else None)
            stack.enter_context(redirect_stdout(io.StringIO()))
            options.setdefault('display', 'background')
            report = headless.run_once(Path('game'), 900, 60000, scenario=scenario,
                stock=set(), stock_evidence=STOCK, **options)
        saved = json.loads((self.directory / 'report.json').read_text())
        self.assertEqual(saved['status'], report['status'])
        launched.assert_called_once()
        self.assertEqual(launched.call_args.args[1], self.directory)
        return report, env, launched.call_args.args[3], checked, prepared, shell

    def main_call(self, arguments, *, windows=True):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, 'argv', ['headless.py', *arguments]))
            stack.enter_context(mock.patch.object(headless, 'IS_WINDOWS', windows))
            configured = stack.enter_context(mock.patch.object(headless, 'config', return_value={'game_dir': str(self.directory)}))
            validated = stack.enter_context(mock.patch.object(headless, 'validate_game'))
            shell = stack.enter_context(mock.patch.object(headless.subprocess, 'run'))
            stock = stack.enter_context(mock.patch.object(headless, 'stock_teardown', return_value=(set(), STOCK)))
            run = stack.enter_context(mock.patch.object(headless, 'run_once', return_value={'status': 'passed'}))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            result = headless.main()
        return result, configured, validated, shell, stock, run

    def assert_cli_rejected_before_side_effects(self, arguments, *, windows=True):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, 'argv', ['headless.py', *arguments]))
            stack.enter_context(mock.patch.object(headless, 'IS_WINDOWS', windows))
            configured = stack.enter_context(mock.patch.object(headless, 'config', return_value={'game_dir': str(self.directory)}))
            validated = stack.enter_context(mock.patch.object(headless, 'validate_game'))
            shell = stack.enter_context(mock.patch.object(headless.subprocess, 'run'))
            stock = stack.enter_context(mock.patch.object(headless, 'stock_teardown'))
            run = stack.enter_context(mock.patch.object(headless, 'run_once'))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            with self.assertRaises((SystemExit, RuntimeError)) as caught:
                headless.main()
            if isinstance(caught.exception, SystemExit):
                self.assertEqual(caught.exception.code, 2)
        for operation in (configured, validated, shell, stock, run):
            operation.assert_not_called()

    def test_card_face_cli_all_and_explicit_cases_run_one_process(self):
        selected = tuple(headless.CARD_FACE_CASES[:2])
        for argument, expected in (('all', tuple(headless.CARD_FACE_CASES)), (','.join(selected), selected)):
            with self.subTest(argument=argument):
                result, _, _, shell, stock, run = self.main_call([
                    '--scenario', 'card-face-acceptance', '--card-face-batch', argument,
                    '--display', 'background', '--use-deployed'])
                self.assertEqual(result, 0)
                stock.assert_called_once()
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs['card_face_batch'], expected)
                self.assertGreaterEqual(run.call_args.args[1], 900)
                shell.assert_not_called()

    def test_card_face_batch_reaches_one_launch_and_its_exact_oracle(self):
        selected = tuple(headless.CARD_FACE_CASES[:2])
        result, env, command, oracle, _, _ = self.run_scenario('card-face-acceptance',
            card_face_batch=selected, evidence='extract_card_face_batch', evidence_value={'routing': 'only'})
        self.assertEqual(env['VOLIBEAR_TEST_CARD_FACE_BATCH'], ','.join(selected))
        self.assertEqual(env['VOLIBEAR_TEST_CHARACTER'], 'volibear')
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'card-face-acceptance')
        self.assertIn('--bootstrap', command)
        oracle.assert_called_once_with(CLEAN_LOG, TOKEN, selected)
        self.assertEqual(result['status'], 'passed')
        missing, *_ = self.run_scenario('card-face-acceptance', card_face_batch=selected)
        self.assertEqual(missing['status'], 'failed')
        self.assertFalse(missing['checks']['card_face_assertions'])

    def test_lifecycle_json_batch_and_independent_failure_are_preserved(self):
        selected = tuple(headless.CARD_LIFECYCLE_CASES[:2])
        result, env, command, oracle, _, _ = self.run_scenario('card-lifecycle',
            card_lifecycle_cases=selected,
            initial_env={'VOLIBEAR_TEST_CARD_LIFECYCLE_CASE': 'stale-single'},
            evidence='card_lifecycle_batch_evidence', evidence_value=({'error': 'independent failure'}, False))
        self.assertEqual(json.loads(env['VOLIBEAR_TEST_CARD_LIFECYCLE_CASES']), list(selected))
        self.assertNotIn('VOLIBEAR_TEST_CARD_LIFECYCLE_CASE', env)
        self.assertIn('--bootstrap', command)
        oracle.assert_called_once_with(CLEAN_LOG, TOKEN, selected)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['checks']['card_lifecycle_assertions'])
        self.assertEqual(result['combat_tests']['error'], 'independent failure')

    def test_native_run_uses_normal_entry_and_clears_inherited_test_modes(self):
        inherited = {'VOLIBEAR_TEST_CHARACTER': 'volibear', 'VOLIBEAR_TEST_SCENARIO': 'baseline',
            'VOLIBEAR_TEST_ENGAGE': '1', 'VOLIBEAR_TEST_PRESENTATION_ACCEPTANCE': '1',
            'VOLIBEAR_SAVE_CASE': 'S3', 'VOLIBEAR_NATIVE_RUN_MODE': 'resume',
            'VOLIBEAR_NATIVE_RUN_PAIR': 'stale', 'VOLIBEAR_TEST_TOKEN': TOKEN,
            'VOLIBEAR_TEST_DATA_ROOT': '/owned/profile', 'VOLIBEAR_TEST_PRIVATE_DESKTOP': '1',
            'VOLIBEAR_TEST_FAST_MODE': 'Fast', 'VOLIBEAR_TEST_ARTIFACT_DIR': str(self.directory),
            'UNCHANGED_ENVIRONMENT': 'keep'}
        result, env, command, oracle, _, _ = self.run_scenario('native-run', initial_env=inherited,
            native_run_mode='death-menu', native_run_pair='pair-new',
            evidence='native_run_evidence', evidence_value={'errors': []})
        self.assertNotIn('--bootstrap', command)
        for key in ('VOLIBEAR_TEST_CHARACTER', 'VOLIBEAR_TEST_ENGAGE',
                    'VOLIBEAR_TEST_PRESENTATION_ACCEPTANCE', 'VOLIBEAR_SAVE_CASE'):
            self.assertNotIn(key, env)
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'native-run')
        self.assertEqual(env['VOLIBEAR_NATIVE_RUN_MODE'], 'death-menu')
        self.assertEqual(env['VOLIBEAR_NATIVE_RUN_PAIR'], 'pair-new')
        self.assertEqual(env['VOLIBEAR_TEST_DATA_ROOT'], inherited['VOLIBEAR_TEST_DATA_ROOT'])
        self.assertEqual(env['UNCHANGED_ENVIRONMENT'], 'keep')
        oracle.assert_called_once_with(CLEAN_LOG, TOKEN, 'death-menu', 'pair-new')
        self.assertEqual(result['status'], 'passed')

    def test_native_run_cannot_inherit_fmod_test_adapter(self):
        result, _, _, _, _, shell = self.run_scenario('native-run', inherited_adapter='1',
            evidence='native_run_evidence', evidence_value={'errors': []})
        shell.assert_not_called()
        self.assertNotIn('audio_adapter_active', result['checks'])

    def test_presentation_cards_route_uses_real_capture_gate_without_audio_claim(self):
        result, env, command, oracle, _, _ = self.run_scenario('presentation-acceptance',
            presentation_mode='cards', evidence='presentation_acceptance_evidence', evidence_value=[])
        self.assertEqual(env['VOLIBEAR_TEST_PRESENTATION_ACCEPTANCE'], '1')
        self.assertEqual(env['VOLIBEAR_TEST_PRESENTATION_MODE'], 'cards')
        self.assertEqual(env['VOLIBEAR_TEST_PRESENTATION_OUTPUT'], str(self.directory / 'presentation'))
        self.assertIn('--bootstrap', command)
        oracle.assert_called_once_with(CLEAN_LOG, TOKEN, 'cards', self.directory / 'presentation')
        self.assertEqual(result['status'], 'passed')
        self.assertIn('not-human-visual-or-listening', result['combat_tests']['scope'])

    def test_presentation_audio_driver_and_runtime_error_are_independent(self):
        log = CLEAN_LOG + 'ERROR: native presentation failure\n'
        result, _, command, oracle, _, _ = self.run_scenario('presentation-acceptance',
            presentation_mode='actions', audio_driver='WASAPI', log=log,
            evidence='presentation_acceptance_evidence', evidence_value=[])
        self.assertEqual(command.count('--audio-driver'), 1)
        self.assertEqual(command[command.index('--audio-driver') + 1], 'WASAPI')
        self.assertNotIn('Dummy', command)
        self.assertIn('ERROR: native presentation failure', oracle.call_args.args[0])
        self.assertTrue(result['checks']['presentation_acceptance_assertions'])
        self.assertFalse(result['checks']['no_runtime_errors'])
        self.assertEqual(result['status'], 'failed')

    def test_presentation_unknown_teardown_cannot_be_filtered(self):
        log = CLEAN_LOG + '[Volibear] SHUTDOWN_BEGIN ' + TOKEN + '\nERROR: 2 shaders of type CanvasShaderRD were never freed\n'
        result, _, _, oracle, _, _ = self.run_scenario('presentation-acceptance', log=log,
            evidence='presentation_acceptance_evidence', evidence_value=[])
        self.assertIn('CanvasShaderRD', oracle.call_args.args[0])
        self.assertFalse(result['checks']['teardown_matches_stock'])
        self.assertEqual(result['status'], 'failed')

    def test_cli_passes_same_audio_driver_to_stock_and_acceptance(self):
        result, _, _, shell, stock, run = self.main_call([
            '--scenario', 'presentation-acceptance', '--presentation-mode', 'actions',
            '--display', 'background', '--audio-driver', 'WASAPI', '--use-deployed'])
        self.assertEqual(result, 0)
        shell.assert_not_called()
        self.assertEqual(stock.call_args.args[-1], 'WASAPI')
        self.assertEqual(run.call_args.kwargs['audio_driver'], 'WASAPI')
        run.assert_called_once()

    def test_short_development_fixtures_run_once_without_rebuilding(self):
        for scenario in ('domain-visual', 'architect-ending'):
            with self.subTest(scenario=scenario):
                result, _, _, shell, _, run = self.main_call([
                    '--scenario', scenario, '--display', 'background', '--use-deployed'])
                self.assertEqual(result, 0)
                shell.assert_not_called()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[1:3], (90, 5400))

    def test_stock_launch_replaces_default_driver_without_losing_nomods(self):
        command = ['game', '--audio-driver', 'Dummy', '--force-steam=off']
        with (mock.patch.object(headless, 'prepare_run', return_value=(self.directory, {}, command)),
              mock.patch.object(headless, 'launch', return_value=(0, False)) as launch,
              mock.patch.object(headless, 'combined_log', return_value='Steam initialization skipped\nSTOCK_CONTROLLER_READY_NATIVE_QUIT\n')):
            _, evidence = headless.stock_teardown(Path('game'), 900, 60000, 'background', 'WASAPI')
        launched = launch.call_args.args[3]
        self.assertEqual(launched.count('--audio-driver'), 1)
        self.assertEqual(launched[launched.index('--audio-driver') + 1], 'WASAPI')
        self.assertIn('--nomods', launched)
        self.assertNotIn('Dummy', launched)
        self.assertTrue(evidence['successful'])

    def test_cli_invalid_batches_repeats_and_foreground_fail_before_build(self):
        face = headless.CARD_FACE_CASES[0]
        lifecycle = headless.CARD_LIFECYCLE_CASES[0]
        cases = [
            ['--scenario', 'card-face-acceptance', '--card-face-batch', ''],
            ['--scenario', 'card-face-acceptance', '--card-face-batch', 'not-a-case'],
            ['--scenario', 'card-face-acceptance', '--card-face-batch', face + ',' + face],
            ['--scenario', 'card-face-acceptance', '--card-face-batch', face + ','],
            ['--scenario', 'discovery', '--card-face-batch', 'all'],
            ['--scenario', 'card-lifecycle', '--card-lifecycle-cases', lifecycle + ',' + lifecycle],
            ['--scenario', 'card-lifecycle', '--card-lifecycle-cases', '[]'],
            ['--scenario', 'card-lifecycle', '--repeat', '2'],
            ['--scenario', 'card-face-acceptance', '--card-face-batch', 'all', '--repeat', '2'],
            ['--scenario', 'native-run', '--repeat', '2'],
            ['--scenario', 'domain-visual', '--repeat', '2'],
            ['--scenario', 'architect-ending', '--repeat', '2'],
            ['--scenario', 'card-face-acceptance', '--card-face-batch', 'all', '--display', 'window'],
            ['--scenario', 'card-lifecycle', '--display', 'window'],
            ['--scenario', 'native-run', '--display', 'window'],
            ['--scenario', 'presentation-acceptance', '--display', 'window'],
            ['--scenario', 'presentation-acceptance', '--display', 'headless'],
            ['--scenario', 'presentation-acceptance', '--presentation-mode', 'actions', '--display', 'background'],
            ['--scenario', 'presentation-acceptance', '--presentation-mode', 'all', '--display', 'background', '--audio-driver', 'Dummy'],
        ]
        for args in cases:
            with self.subTest(arguments=args):
                self.assert_cli_rejected_before_side_effects(args)

    def test_run_once_invalid_requests_fail_before_profile_creation(self):
        cases = [
            {'scenario': 'card-lifecycle', 'card_lifecycle_cases': []},
            {'scenario': 'card-lifecycle', 'card_lifecycle_cases': [headless.CARD_LIFECYCLE_CASES[0]] * 2},
            {'scenario': 'card-face-acceptance', 'card_face_batch': []},
            {'scenario': 'discovery', 'card_face_batch': [headless.CARD_FACE_CASES[0]]},
            {'scenario': 'native-run', 'native_run_mode': 'resume'},
            {'scenario': 'native-run', 'native_run_mode': 'unknown'},
            {'scenario': 'presentation-acceptance', 'display': 'headless'},
            {'scenario': 'presentation-acceptance', 'display': 'background', 'presentation_mode': 'actions'},
            {'scenario': 'presentation-acceptance', 'display': 'background', 'presentation_mode': 'all', 'audio_driver': 'Dummy'},
            {'scenario': 'card-face-acceptance', 'display': 'window', 'card_face_batch': [headless.CARD_FACE_CASES[0]]},
        ]
        for options in cases:
            with self.subTest(options=options), mock.patch.object(headless, 'prepare_run') as prepare, \
                    mock.patch.object(headless, 'launch') as launch, mock.patch.object(headless, 'IS_WINDOWS', True):
                with self.assertRaises(RuntimeError):
                    headless.run_once(Path('game'), 900, 60000, **options)
                prepare.assert_not_called()
                launch.assert_not_called()

    def test_use_deployed_avoids_build_and_deploy_but_still_checks_game(self):
        _, configured, validated, shell, stock, run = self.main_call([
            '--scenario', 'card-lifecycle', '--display', 'background', '--use-deployed'])
        configured.assert_called_once()
        validated.assert_called_once()
        shell.assert_not_called()
        stock.assert_called_once()
        run.assert_called_once()
        self.assertEqual(tuple(run.call_args.kwargs['card_lifecycle_cases']), tuple(headless.CARD_LIFECYCLE_CASES))

    def test_reused_pair_profile_preserves_settings_and_original_environment(self):
        profile = self.directory / '.local/p/owned-profile'
        user = headless.user_data_root(profile)
        settings = user / 'default/1/settings.save'
        settings.parent.mkdir(parents=True)
        before = b'{"language":"zhs","nativeCheckpoint":"keep exact bytes"}\n'
        settings.write_bytes(before)
        env = {'VOLIBEAR_TEST_DATA_ROOT': str(user), 'VOLIBEAR_TEST_TOKEN': 'prepare-token',
               'VOLIBEAR_NATIVE_RUN_PAIR': 'pair-owned'}
        for key, child in headless.ISOLATION_BINDINGS:
            env[key] = str(profile / child)
        original = dict(env)
        with (mock.patch.object(headless, 'ROOT', self.directory),
              mock.patch.object(headless, 'game_executable', return_value=Path('game')),
              mock.patch.object(headless, 'isolated_env') as fresh):
            directory, actual, _ = headless.prepare_run(Path('game'), 'resume-token', 60000,
                _profile_env=env)
        fresh.assert_not_called()
        self.assertEqual(settings.read_bytes(), before)
        self.assertEqual(env, original)
        self.assertEqual(actual['VOLIBEAR_TEST_TOKEN'], 'resume-token')
        self.assertEqual(actual['VOLIBEAR_TEST_DATA_ROOT'], str(user))
        self.assertFalse((headless.user_data_root(directory) / 'default/1/settings.save').exists())


if __name__ == '__main__':
    unittest.main()
