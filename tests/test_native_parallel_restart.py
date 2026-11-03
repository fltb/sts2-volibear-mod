"""Synthetic ownership/cancellation only; never launch the installed game."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h
import native_suite as suite
import save_load_pair as pair


class ParallelRestartTests(unittest.TestCase):
    def test_success_overlaps_reuses_current_stock_and_combines_all_reports(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root / 'artifacts/headless/suite').mkdir(parents=True)
            stock = {'successful': True, 'exit_code': 0, 'timed_out': False, 'runtime_errors': []}
            barrier = threading.Barrier(2)
            events = []
            def native(*args, **kwargs):
                self.assertIs(kwargs['stock_evidence'], stock)
                events.append(kwargs['cancel_event'])
                barrier.wait(timeout=2)
                return {'status': 'passed', 'checks': {'all_native': True}, 'run_id': 'suite'}
            def restart(*args, **kwargs):
                self.assertIs(kwargs['_stock_control'][1], stock)
                self.assertEqual(args[1:3], ('S2', 'restart'))
                events.append(kwargs['cancel_event'])
                barrier.wait(timeout=2)
                return {'passed': True, 'phases': [{'phase': 'prepare'}, {'phase': 'resume'}]}
            for name, value in (('ROOT', root), ('IS_WINDOWS', True)):
                stack.enter_context(patch.object(h, name, value))
            stack.enter_context(patch.object(h, 'validate_game'))
            stack.enter_context(patch.object(h, 'display_command'))
            baseline = stack.enter_context(patch.object(h, 'stock_teardown', return_value=(set(), stock)))
            stack.enter_context(patch.object(h, 'run_once', side_effect=native))
            stack.enter_context(patch.object(pair, 'run_pair', side_effect=restart))
            report = suite.run_suite(root, verify_restart=True, parallel_restart=True)
            baseline.assert_called_once()
            self.assertIs(events[0], events[1])
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['processes'], {'stock': 1, 'suite': 1, 'restart': 2})
            self.assertEqual(report['checks'], {'all_native': True, 'checkpoint_process_restart': True})

    def test_failed_normal_return_cancels_other_thread_and_collects_it(self):
        for failing in ('suite', 'restart'):
            with self.subTest(failing=failing):
                barrier = threading.Barrier(2)
                finished = threading.Event()
                def failed(cancel):
                    barrier.wait(timeout=2)
                    return {'status': 'failed', 'checks': {'ok': False}, 'passed': False}
                def waiting(cancel):
                    barrier.wait(timeout=2)
                    try:
                        self.assertTrue(cancel.wait(2))
                        h.check_cancelled(cancel)
                    finally:
                        finished.set()
                with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                    suite._parallel_restart(failed if failing == 'suite' else waiting,
                                            failed if failing == 'restart' else waiting)
                self.assertTrue(finished.is_set())

    def test_success_requires_both_reports_even_when_both_already_finished(self):
        for suite_good, restart_good in ((False, True), (True, False)):
            rows = suite._parallel_restart(
                lambda _: {'status': 'passed' if suite_good else 'failed', 'checks': {'ok': suite_good}},
                lambda _: {'passed': restart_good})
            self.assertFalse(suite._suite_ok(rows[0]) and rows[1]['passed'])

    def test_explicit_parallel_flag_rejects_unsupported_mode_before_stock(self):
        with patch.object(h, 'stock_teardown') as stock, patch.object(h, 'IS_WINDOWS', False):
            with self.assertRaises(ValueError):
                suite.run_suite(Path('.'), verify_restart=True, parallel_restart=True, display='xvfb')
            stock.assert_not_called()

    @unittest.skipUnless(h.IS_WINDOWS, 'Windows Job descendant ownership contract')
    def test_each_launch_cancel_kills_child_and_grandchild_with_single_owner_close(self):
        for stage in ('suite', 'prepare', 'resume', 'spawn-race'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                root = Path(temporary)
                cancel = threading.Event()
                command = [sys.executable, '-B', '-c',
                    'import subprocess,sys,time\nfrom pathlib import Path\n'
                    'while not Path("permit").exists(): time.sleep(.01)\n'
                    'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\n'
                    'Path("grandchild").write_text(str(p.pid))\ntime.sleep(60)']
                processes, owners = [], []
                original_spawn, original_close, original_terminate = h.spawn_owned, h.close_owned, h._terminate
                def spawn(*args, **kwargs):
                    process, job = original_spawn(*args, **kwargs)
                    processes.append(process)
                    self.assertIsNotNone(job)
                    (root / 'permit').write_text('owned')
                    if stage == 'spawn-race':
                        cancel.set()
                    return process, job
                def close(job):
                    owners.append(('close', threading.get_ident()))
                    return original_close(job)
                def terminate(*args, **kwargs):
                    owners.append(('terminate', threading.get_ident()))
                    return original_terminate(*args, **kwargs)
                stack.enter_context(patch.object(h, 'spawn_owned', side_effect=spawn))
                stack.enter_context(patch.object(h, 'close_owned', side_effect=close))
                stack.enter_context(patch.object(h, '_terminate', side_effect=terminate))
                stack.enter_context(patch.object(pair, 'phase_command', return_value=command))
                def run():
                    if stage in ('suite', 'spawn-race'):
                        return h.launch(root, root, dict(os.environ), command, 10, cancel_event=cancel)
                    return pair.launch_phase(root, root, dict(os.environ, VOLIBEAR_TEST_DATA_ROOT=str(root / 'profile')),
                        'S2', 'restart', stage, 'seed', set(), {}, 10, 1000, 'headless', cancel_event=cancel)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(run)
                    try:
                        if stage != 'spawn-race':
                            until = time.monotonic() + 3
                            while not (root / 'grandchild').exists() and time.monotonic() < until:
                                time.sleep(.01)
                            self.assertTrue((root / 'grandchild').is_file())
                        cancel.set()
                        with self.assertRaises(h.OwnedProcessCancelled):
                            future.result(timeout=6)
                    finally:
                        cancel.set()
                self.assertTrue(all(process.poll() is not None for process in processes))
                if (root / 'grandchild').is_file():
                    self.assertFalse(h.process_alive(int((root / 'grandchild').read_text())))
                self.assertEqual([name for name, _ in owners], ['terminate', 'close'])
                self.assertEqual(owners[0][1], owners[1][1])
                self.assertNotEqual(owners[0][1], threading.get_ident())

    def test_prepare_failure_or_cancel_never_launches_resume(self):
        for mode in ('failed-prepare', 'after-prepare', 'before-resume'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                root = Path(temporary); profile = root / 'profile'; profile.mkdir()
                cancel = threading.Event()
                stack.enter_context(patch.object(pair, 'ROOT', root))
                stack.enter_context(patch.object(pair, 'create_owned_profile', return_value=profile))
                stack.enter_context(patch.object(h, 'validate_game'))
                stock = {'successful': True, 'exit_code': 0, 'timed_out': False, 'runtime_errors': []}
                def prepare(*args, **kwargs):
                    self.assertEqual(args[5], 'prepare')
                    self.assertIs(kwargs['cancel_event'], cancel)
                    if mode == 'after-prepare': cancel.set()
                    return {'passed': False, 'checks': {}, 'expected': {'checkpointPath': str(root / 'checkpoint')}}
                launch = stack.enter_context(patch.object(pair, 'launch_phase', side_effect=prepare))
                if mode == 'before-resume':
                    def resume_race(a, checkpoint, resume):
                        cancel.set()
                        return resume()
                    stack.enter_context(patch.object(pair, 'gate_then_resume', side_effect=resume_race))
                if mode == 'failed-prepare':
                    result = pair.run_pair(root, 'S2', 'restart', display='headless', _stock_control=(set(), stock), cancel_event=cancel)
                    self.assertFalse(result['passed'])
                    self.assertEqual(len(result['phases']), 1)
                else:
                    with self.assertRaises(h.OwnedProcessCancelled):
                        pair.run_pair(root, 'S2', 'restart', display='headless', _stock_control=(set(), stock), cancel_event=cancel)
                launch.assert_called_once()

    def test_prelaunch_cancel_never_spawns(self):
        cancel = threading.Event(); cancel.set()
        with patch.object(h, 'spawn_owned') as spawn:
            with self.assertRaises(h.OwnedProcessCancelled):
                h.launch(Path('.'), Path('.'), {}, [], 10, cancel_event=cancel)
            with self.assertRaises(h.OwnedProcessCancelled):
                pair.launch_phase(None, None, {}, 'S2', 'restart', 'resume', '', None, None, 10, 1000, 'headless', cancel_event=cancel)
            spawn.assert_not_called()
