"""Separate catalog orchestration contracts; synthetic workers, never a game."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h
import native_suite as suite
import presentation_media_checks as media_checks
import test_acceptance_runner as routing_helpers


def main_report(pid=101):
    return {'run_id': 'main', 'scenario': 'native-suite', 'status': 'passed', 'mode': 'real-game-background',
            'checks': {'native_suite_assertions': True, 'stock_control_success': True},
            'exit_code': 0, 'timed_out': False, 'process_identity': {'pid': pid, 'token': 'main'},
            'combat_tests': {'stages': {'presentation': {'mode': 'actions', 'errors': []}}}}


def catalog_report(pid=102):
    return {'run_id': 'catalog', 'scenario': 'presentation-acceptance', 'status': 'passed', 'mode': 'real-game-background',
            'checks': {'presentation_acceptance_assertions': True, 'presentation_media_assertions': True, 'stock_control_success': True},
            'exit_code': 0, 'timed_out': False, 'process_identity': {'pid': pid, 'token': 'catalog'},
            'combat_tests': {'mode': 'cards', 'errors': [], 'verified_catalog_views': 356,
                             'media': {'status': 'PASS', 'errors': [], 'mode': 'cards', 'token': 'catalog', 'images': [{}] * 356}}}


class CatalogHeadlessRouting(unittest.TestCase):
    setUp = routing_helpers.AcceptanceRunnerTests.setUp
    run_scenario = routing_helpers.AcceptanceRunnerTests.run_scenario

    def test_catalog_retains_original_full_media_validator_not_only_receipt_validator(self):
        media = catalog_report()['combat_tests']['media']
        with patch.object(media_checks, 'check_log', return_value=media) as checked, \
             patch.object(h, 'presentation_acceptance_evidence', side_effect=AssertionError('Weak receipt-only route forbidden')):
            report, *_ = self.run_scenario('presentation-acceptance', presentation_mode='cards', record_process_identity=True)
        checked.assert_called_once()
        self.assertEqual(report['combat_tests']['verified_catalog_views'], 356)
        self.assertIs(report['combat_tests']['media'], media)
        self.assertTrue(report['checks']['presentation_media_assertions'])


class CatalogTests(unittest.TestCase):
    def test_three_real_short_workers_overlap_and_any_failure_cancels_other_two(self):
        for failing in (None, 'main', 'restart', 'catalog'):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                identities = {name: {} for name in ('main', 'restart', 'catalog')}
                for name in identities: (root / name).mkdir()
                def worker(name):
                    def run(cancel):
                        ending = 'raise SystemExit(7)' if name == failing else 'time.sleep(60)' if failing else 'print("complete")'
                        code = ('from pathlib import Path\nimport time\n'
                                + f'Path("ready-{name}").write_text("ready")\n'
                                + 'while not all(Path("ready-"+n).exists() for n in ("main","restart","catalog")): time.sleep(.01)\n'
                                + ending)
                        status, timed_out = h.launch(root, root / name, dict(os.environ, VOLIBEAR_TEST_TOKEN=name),
                            [sys.executable, '-B', '-c', code], 5, cancel_event=cancel, process_identity=identities[name])
                        self.assertFalse(timed_out)
                        if name == 'restart': return {'passed': status == 0, 'phases': [{}, {}]}
                        report = main_report() if name == 'main' else catalog_report()
                        report['process_identity'] = identities[name]
                        if status:
                            report['status'] = 'failed'
                            report['exit_code'] = status
                        return report
                    return run
                if failing:
                    with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                        suite._parallel_restart(worker('main'), worker('restart'), worker('catalog'))
                else:
                    reports = suite._parallel_restart(worker('main'), worker('restart'), worker('catalog'))
                    self.assertTrue(suite._split_presentation_ok(reports[0], reports[2]))
                    self.assertTrue(reports[1]['passed'])
                self.assertEqual(len({identity['pid'] for identity in identities.values()}), 3)
                self.assertTrue(all(not h.process_alive(identity['pid']) for identity in identities.values()))

    def test_current_stock_once_modes_paths_counts_and_full_catalog_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root / 'artifacts/headless/main').mkdir(parents=True)
            stock = {'successful': True, 'exit_code': 0, 'timed_out': False, 'runtime_errors': []}
            barrier = threading.Barrier(3)
            events = []
            def native(*args, **kwargs):
                self.assertIs(kwargs['stock_evidence'], stock)
                self.assertTrue(kwargs['record_process_identity'])
                events.append(kwargs['cancel_event'])
                if kwargs['scenario'] == 'native-suite':
                    self.assertEqual(kwargs['presentation_mode'], 'actions')
                    self.assertEqual(len(kwargs['card_face_batch']), 410)
                    self.assertEqual(len(kwargs['card_lifecycle_cases']), 48)
                    result = main_report()
                else:
                    self.assertEqual(kwargs['scenario'], 'presentation-acceptance')
                    self.assertEqual(kwargs['presentation_mode'], 'cards')
                    result = catalog_report()
                barrier.wait(timeout=2)
                return result
            def restart(*args, **kwargs):
                self.assertIs(kwargs['_stock_control'][1], stock)
                events.append(kwargs['cancel_event'])
                barrier.wait(timeout=2)
                return {'passed': True, 'phases': [{'phase': 'prepare'}, {'phase': 'resume'}]}
            stack.enter_context(patch.object(h, 'ROOT', root))
            stack.enter_context(patch.object(h, 'IS_WINDOWS', True))
            stack.enter_context(patch.object(h, 'display_command'))
            stack.enter_context(patch.object(h, 'validate_game'))
            baseline = stack.enter_context(patch.object(h, 'stock_teardown', return_value=(set(), stock)))
            launch = stack.enter_context(patch.object(h, 'run_once', side_effect=native))
            stack.enter_context(patch.object(suite.save_load_pair, 'run_pair', side_effect=restart))
            report = suite.run_suite(root, verify_restart=True, parallel_catalog=True,
                                     presentation_mode='all', audio_driver='WASAPI')
            baseline.assert_called_once()
            self.assertEqual(launch.call_count, 2)
            self.assertTrue(all(event is events[0] for event in events))
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(report['processes'], {'stock': 1, 'suite': 1, 'restart': 2, 'catalog': 1})
            self.assertTrue(report['checks']['separate_catalog_complete_356'])
            details = report['presentation']
            self.assertEqual((details['requested_mode'], details['main_mode'], details['catalog_mode']), ('all', 'actions', 'cards'))
            self.assertEqual(details['catalog_process'], {'pid': 102, 'token': 'catalog'})
            self.assertEqual(Path(details['catalog_report']), root / 'artifacts/headless/catalog/report.json')
            self.assertEqual(Path(details['catalog_artifacts']), root / 'artifacts/headless/catalog/presentation')
            self.assertEqual(json.loads(Path(report['report']).read_text())['presentation'], details)

    def test_catalog_missing_or_wrong_count_mode_identity_never_satisfies_full_gate(self):
        bad = []
        for key, value in (('verified_catalog_views', 355), ('mode', 'actions'), ('errors', ['missing image'])):
            row = catalog_report(); row['combat_tests'][key] = value; bad.append(row)
        for identity in ({'pid': 101, 'token': 'catalog'}, {'pid': 0, 'token': 'catalog'}, {'pid': 102, 'token': 'wrong'}):
            row = catalog_report(); row['process_identity'] = identity; bad.append(row)
        row = catalog_report(); row['status'] = 'failed'; bad.append(row)
        bad.append({})
        for row in bad:
            with self.subTest(row=row):
                self.assertFalse(suite._split_presentation_ok(main_report(), row))
        row = main_report(); row['combat_tests']['stages']['presentation']['mode'] = 'all'
        self.assertFalse(suite._split_presentation_ok(row, catalog_report()))

    def test_missing_catalog_is_and_failure_despite_main_and_restart_success(self):
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary)
            (root / 'artifacts/headless/main').mkdir(parents=True)
            stack.enter_context(patch.object(h, 'ROOT', root))
            stack.enter_context(patch.object(h, 'IS_WINDOWS', True))
            stack.enter_context(patch.object(h, 'display_command'))
            stack.enter_context(patch.object(h, 'validate_game'))
            stack.enter_context(patch.object(h, 'stock_teardown', return_value=(set(), {'successful': True, 'exit_code': 0, 'timed_out': False, 'runtime_errors': []})))
            stack.enter_context(patch.object(suite, '_parallel_restart', return_value=(main_report(), {'passed': True, 'phases': [{}, {}]}, None)))
            stack.enter_context(patch.object(h, 'run_once', side_effect=AssertionError('No game permitted')))
            report = suite.run_suite(root, verify_restart=True, parallel_catalog=True, presentation_mode='all', audio_driver='WASAPI')
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(report['checks']['native_suite_assertions'])
            self.assertTrue(report['checks']['checkpoint_process_restart'])
            self.assertFalse(report['checks']['separate_catalog_complete_356'])
            self.assertIsNone(report['presentation']['catalog'])
            with patch.object(suite, 'run_suite', return_value=report), redirect_stdout(io.StringIO()):
                self.assertEqual(suite.main(['--execute-native', '--use-deployed', '--game-dir', str(root),
                    '--parallel-catalog', '--verify-restart', '--presentation-mode', 'all', '--audio-driver', 'WASAPI']), 1)

    def test_invalid_modes_refused_before_stock_or_launch(self):
        for windows, display, mode, restart in ((False, 'xvfb', 'all', True), (True, 'window', 'all', True),
                                                (True, 'background', 'actions', True), (True, 'background', 'cards', True),
                                                (True, 'background', 'all', False)):
            with patch.object(h, 'IS_WINDOWS', windows), patch.object(h, 'stock_teardown') as stock:
                with self.assertRaises(ValueError):
                    suite.run_suite(Path('.'), display=display, presentation_mode=mode,
                                    verify_restart=restart, parallel_catalog=True)
                stock.assert_not_called()
