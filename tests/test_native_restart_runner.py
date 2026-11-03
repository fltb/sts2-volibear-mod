"""Owned-process routing/PID evidence controls; only Python children run here."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import native_suite
import save_load_pair as pair

STOCK = dict(successful=True, exit_code=0, timed_out=False, runtime_errors=[])


class NativeRestartRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-restart-routing-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root/'artifacts/headless/current').mkdir(parents=True)

    def run_suite(self, *, suite_report=None, restart_report=None, restart_error=None, **options):
        if suite_report is None:
            suite_report = dict(status='passed', run_id='current', checks={'runtime': True, 'native': True})
        if restart_report is None:
            restart_report = dict(passed=True, phases=[{'phase': 'prepare'}, {'phase': 'resume'}])
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(native_suite.h, 'ROOT', self.root))
            stack.enter_context(mock.patch.object(native_suite.h, 'IS_WINDOWS', True))
            stack.enter_context(mock.patch.object(native_suite.h, 'display_command'))
            stack.enter_context(mock.patch.object(native_suite.h, 'validate_game'))
            baseline = stack.enter_context(mock.patch.object(native_suite.h, 'stock_teardown', return_value=(set(), STOCK)))
            native = stack.enter_context(mock.patch.object(native_suite.h, 'run_once', return_value=deepcopy(suite_report)))
            restart = stack.enter_context(mock.patch.object(pair, 'run_pair', return_value=restart_report, side_effect=restart_error))
            result = native_suite.run_suite(self.root, verify_restart=True, **options)
        return result, baseline, native, restart

    def test_stock_failure_reports_run_and_errors_without_launching_suite(self):
        failed = dict(STOCK, successful=False, run_id='current-stock',
                      runtime_errors=['ERROR: Failed to read the root certificate store.'])
        with mock.patch.object(native_suite.h, 'display_command'), \
             mock.patch.object(native_suite.h, 'validate_game'), \
             mock.patch.object(native_suite.h, 'stock_teardown', return_value=(set(), failed)), \
             mock.patch.object(native_suite.h, 'run_once') as native:
            with self.assertRaises(RuntimeError) as error:
                native_suite.run_suite(self.root)
        self.assertIn('current-stock', str(error.exception))
        self.assertIn(failed['runtime_errors'][0], str(error.exception))
        native.assert_not_called()

    def test_one_stock_one_continuous_suite_then_two_persistence_processes(self):
        result, baseline, native, restart = self.run_suite()
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['processes'], dict(stock=1, suite=1, restart=2))
        baseline.assert_called_once(); native.assert_called_once(); restart.assert_called_once()
        self.assertEqual(restart.call_args.args[1:3], ('S2', 'restart'))
        self.assertEqual(restart.call_args.kwargs['_stock_control'], (set(), STOCK))
        persisted = json.loads(Path(result['report']).read_text(encoding='utf-8'))
        self.assertEqual(persisted, result)

    def test_failed_incomplete_and_truthy_nonboolean_suite_cannot_launch_restart(self):
        for report in (dict(status='failed', checks={'native': True}),
                       dict(status='passed', checks={}), dict(status='passed', checks={'native': 1}),
                       dict(status='passed', checks={'native': False})):
            result, _, _, restart = self.run_suite(suite_report=dict(report, run_id='current'))
            self.assertEqual(result['status'], 'failed'); restart.assert_not_called()
            self.assertEqual(result['processes']['restart'], 0)

    def test_failed_restart_cannot_be_awarded_suite_pass(self):
        for report in (dict(passed=False, phases=[{'phase': 'prepare'}]),
                       dict(passed=1, phases=[{}, {}])):
            result, _, _, _ = self.run_suite(restart_report=report)
            self.assertEqual(result['status'], 'failed')
            self.assertIs(result['checks']['checkpoint_process_restart'], False)

    def test_restart_runner_error_persists_reviewable_failure(self):
        result, _, _, _ = self.run_suite(restart_error=RuntimeError('binding failed'))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['restart']['error'], 'binding failed')
        self.assertTrue(Path(result['report']).is_file())

    def test_one_control_is_shared_only_with_matching_audio_driver(self):
        result, baseline, native, restart = self.run_suite(presentation_mode='all', audio_driver='WASAPI')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(baseline.call_args.kwargs['audio_driver'], 'WASAPI')
        self.assertEqual(native.call_args.kwargs['audio_driver'], 'WASAPI')
        self.assertEqual(restart.call_args.kwargs['audio_driver'], 'WASAPI')

    def test_invalid_restart_limits_fail_before_any_launch(self):
        for invalid in (dict(restart_timeout=True), dict(restart_timeout=1801),
                        dict(restart_frames=1), dict(restart_frames=True)):
            with mock.patch.object(native_suite.h, 'stock_teardown') as baseline:
                with self.assertRaises(ValueError): self.run_suite(**invalid)
                baseline.assert_not_called()

    def test_standalone_stock_missing_or_nonboolean_evidence_is_rejected(self):
        self.assertTrue(pair.successful_stock(STOCK))
        for change in (dict(successful=1), dict(exit_code=False), dict(timed_out=0), dict(runtime_errors=['error'])):
            self.assertFalse(pair.successful_stock(dict(STOCK, **change)))
        for field in STOCK:
            broken = dict(STOCK); del broken[field]
            self.assertFalse(pair.successful_stock(broken))

    def test_foreground_restart_is_rejected_before_profile_or_launch(self):
        with mock.patch.object(pair.h, 'IS_WINDOWS', True), mock.patch.object(pair, 'create_owned_profile') as profile, mock.patch.object(pair.h, 'stock_teardown') as stock:
            with self.assertRaisesRegex(ValueError, 'foreground'):
                pair.run_pair(self.root, 'S2', 'restart', display='window')
        profile.assert_not_called(); stock.assert_not_called()

    def test_background_phase_launches_on_private_windows_desktop(self):
        base = {'VOLIBEAR_TEST_DATA_ROOT': str(self.root/'isolated')}
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(pair.h, 'IS_WINDOWS', True))
            stack.enter_context(mock.patch.object(pair, 'phase_command', return_value=['game']))
            spawn = stack.enter_context(mock.patch.object(pair.h, 'spawn_owned', return_value=(SimpleNamespace(pid=777), object())))
            stack.enter_context(mock.patch.object(pair.h, 'wait_owned_process', return_value=(0, False)))
            close = stack.enter_context(mock.patch.object(pair.h, 'close_owned'))
            stack.enter_context(mock.patch.object(pair.h, 'combined_log', return_value=''))
            stack.enter_context(mock.patch.object(pair.h, 'evaluate', return_value={}))
            stack.enter_context(mock.patch.object(pair, 'parse_log', return_value=(None, False)))
            result = pair.launch_phase(self.root, self.root, base, 'S2', 'restart', 'prepare',
                                       'seed', set(), STOCK, 30, 1000, 'background')
        self.assertIs(spawn.call_args.kwargs['window'], True)
        self.assertEqual(spawn.call_args.args[2]['VOLIBEAR_TEST_PRIVATE_DESKTOP'], '1')
        self.assertEqual(result['pid'], 777); close.assert_called_once()


class NativeProcessReceipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='native-pid-receipt-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.path = self.root/'native-process.json'
        self.native = Path(sys.executable).resolve()
        self.receipt = dict(schema=1, token='current-token', pid=123, process_group=100, executable=str(self.native))

    def check(self, receipt=None):
        self.path.write_text(json.dumps(self.receipt if receipt is None else receipt), encoding='utf-8')
        with mock.patch.object(pair.h, 'game_executable', return_value=self.native):
            return pair.native_pid(self.root, 'xvfb', 100, 'current-token', self.root)

    def test_wrapper_pid_binds_only_to_current_token_group_and_executable(self):
        self.assertEqual(self.check(), 123)
        for field, value in [('schema', True), ('pid', True), ('pid', -1), ('token', 'stale'),
                             ('process_group', 101), ('executable', 'another-game')]:
            altered = dict(self.receipt); altered[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(altered)

    def test_missing_or_redirected_pid_receipt_never_uses_log_pid(self):
        with self.assertRaises(OSError): pair.native_pid(self.root, 'xvfb', 100, 'current-token', self.root)
        if os.name == 'nt':
            with mock.patch.object(Path, 'is_symlink', return_value=True):
                with self.assertRaises(ValueError): pair.native_pid(self.root, 'xvfb', 100, 'current-token', self.root)
        else:
            target = self.root/'actual.json'; target.write_text(json.dumps(self.receipt))
            self.path.symlink_to(target)
            with self.assertRaises(ValueError): pair.native_pid(self.root, 'xvfb', 100, 'current-token', self.root)

    def test_xvfb_command_contains_same_exec_receipt_identity_and_no_bootstrap(self):
        with mock.patch.object(pair.h, 'game_executable', return_value=self.native), \
             mock.patch.object(pair.h, 'display_command', side_effect=lambda command, display: command):
            command = pair.phase_command(self.root, self.root, 'xvfb', 1000, 'current-token')
        self.assertEqual(command[:2], [sys.executable, str(ROOT/'tools/native_child_exec.py')])
        self.assertIn(str(self.path), command); self.assertIn('current-token', command)
        self.assertNotIn('--bootstrap', command)

    def test_persistence_command_preserves_explicit_control_audio_driver(self):
        with mock.patch.object(pair.h, 'IS_WINDOWS', True), \
             mock.patch.object(pair.h, 'game_executable', return_value=self.native):
            command = pair.phase_command(self.root, self.root, 'background', 1000, 'current-token', 'WASAPI')
        self.assertEqual(command[-2:], ['--audio-driver', 'WASAPI'])
        self.assertNotIn('Dummy', command)

    def test_exec_helper_preserves_actual_python_child_pid_and_exclusive_receipt(self):
        # On Windows the helper must fail instead of pretending xvfb is supported.
        command = [sys.executable, str(ROOT/'tools/native_child_exec.py'), '--pid-file', str(self.path),
            '--token', 'current-token', '--', str(self.native), '-c',
            'import json,os;print(json.dumps({"pid":os.getpid(),"group":os.getpgrp()}))']
        with subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=os.name != 'nt') as process:
            output, error = process.communicate(timeout=10)
            if os.name == 'nt':
                self.assertNotEqual(process.returncode, 0); self.assertFalse(self.path.exists()); return
            self.assertEqual(process.returncode, 0, error)
            native = json.loads(output)
            receipt = json.loads(self.path.read_text(encoding='utf-8'))
            self.assertEqual(receipt['pid'], process.pid)
            self.assertEqual(native, dict(pid=process.pid, group=process.pid))
            self.assertEqual(receipt['process_group'], process.pid)
        original = self.path.read_bytes()
        retry = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(retry.returncode, 0); self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__': unittest.main()
