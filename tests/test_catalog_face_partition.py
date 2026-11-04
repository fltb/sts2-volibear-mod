"""Synthetic partition/envelope contracts; no native evidence or game execution."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h
import native_suite as suite
import presentation_media_checks as media_checks
import test_acceptance_runner as routing
from test_card_face_evidence import synthetic
from test_native_parallel_catalog import main_report, catalog_report


class PartitionTests(unittest.TestCase):
    def test_fixed_nonempty_exact_once_for_full_even_and_odd_requests(self):
        for requested in (h.CARD_FACE_CASES, h.CARD_FACE_CASES[:136], h.CARD_FACE_CASES[:3], h.CARD_FACE_CASES[:2]):
            left, right = suite.split_face_cases(requested)
            self.assertEqual(tuple(left), requested[::2])
            self.assertEqual(tuple(right), requested[1::2])
            self.assertTrue(suite._face_union_ok(main_report(cases=left), catalog_report(cases=right), requested))
            self.assertFalse(set(left) & set(right))
            self.assertEqual(len(left) + len(right), len(requested))

    def test_empty_singleton_duplicates_and_unknown_rejected_before_stock(self):
        for requested in ([], h.CARD_FACE_CASES[:1], [h.CARD_FACE_CASES[0]] * 2, ['bogus', h.CARD_FACE_CASES[0]]):
            with patch.object(h, 'IS_WINDOWS', True), patch.object(h, 'stock_teardown') as stock:
                with self.assertRaises((ValueError, RuntimeError)):
                    suite.run_suite(Path('.'), face_cases=requested, parallel_catalog=True,
                                    verify_restart=True, presentation_mode='all', audio_driver='WASAPI')
                stock.assert_not_called()

    def test_union_rejects_missing_duplicate_swapped_order_and_cross_token_records(self):
        requested = h.CARD_FACE_CASES[:6]
        left, right = suite.split_face_cases(requested)
        good_main, good_catalog = main_report(cases=left), catalog_report(cases=right)
        bad = []
        for key in ('cases', 'completed'):
            row = deepcopy(good_catalog); row['combat_tests']['card_faces']['batch'][key] = list(right[:-1]); bad.append(row)
            row = deepcopy(good_catalog); row['combat_tests']['card_faces']['batch'][key] = list(right) + [right[0]]; bad.append(row)
        row = deepcopy(good_catalog); row['combat_tests']['card_faces']['records'].reverse(); bad.append(row)
        row = deepcopy(good_catalog); row['combat_tests']['card_faces']['records'][0]['token'] = 'main'; bad.append(row)
        row = deepcopy(good_catalog); row['combat_tests']['card_faces']['records'][0]['variant'] = left[0]; bad.append(row)
        row = deepcopy(good_catalog); row['combat_tests']['card_faces']['batch']['token'] = 'main'; bad.append(row)
        bad.append(catalog_report(cases=left))
        for row in bad:
            with self.subTest(row=row):
                self.assertFalse(suite._face_union_ok(good_main, row, requested))
        self.assertFalse(suite._face_union_ok(good_main, good_catalog, requested + (requested[0],)))
        self.assertFalse(suite._face_union_ok(good_main, good_catalog, h.CARD_FACE_CASES))

    def test_media_success_then_face_failure_cancels_both_other_branches(self):
        barrier = threading.Barrier(3)
        cancelled = []
        def waiter(label):
            def run(event):
                barrier.wait(timeout=2)
                self.assertTrue(event.wait(2))
                cancelled.append(label)
                raise h.OwnedProcessCancelled('synthetic owned cancellation')
            return run
        def catalog(event):
            barrier.wait(timeout=2)
            report = catalog_report()
            report['checks']['catalog_face_assertions'] = False
            self.assertEqual(report['combat_tests']['media']['status'], 'PASS')
            return report  # Normal return, even incorrectly optimistic status, must cancel.
        with self.assertRaisesRegex(RuntimeError, 'cancel'):
            suite._parallel_restart(waiter('main'), waiter('restart'), catalog)
        self.assertCountEqual(cancelled, ['main', 'restart'])


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.token = 'unit-fixture-not-native'
        self.cases = ['B01-base-plain', 'B02-upgrade-dexterity']
        self.identity = {'pid': 123, 'token': self.token}
        self.records = [synthetic(case) for case in self.cases]
        self.batch = dict(schema=1, token=self.token, cases=self.cases, completed=self.cases,
            lifecycle='EnterRoom(MapRoom)->ReturnToMainMenu->StartNewSingleplayerRun', shouldSave=False,
            transitions=[dict(variant=case, runIdentity=4+4*i, playerIdentity=5+4*i, creatureIdentity=6+4*i,
                deckIdentity=7+4*i, runNull=True, combatNull=True, inProgress=False, queueEmpty=True,
                actionNull=True, historyVisible=0) for i,case in enumerate(self.cases)])
        self.begin = dict(schema=1, token=self.token, pid=123, cases=self.cases, presentationMode='cards')
        self.final = dict(schema=1, token=self.token, pid=123, cases=self.cases,
            completed=['presentation', 'card-faces'], finished=True, processRestarts=0,
            cleanup=dict(RunNull=True, CombatNull=True, InProgress=False, QueueEmpty=True, ActionNull=True, HistoryVisible=0))

    def lines(self):
        return ['[Volibear] CATALOG_FACE_BEGIN ' + json.dumps(self.begin),
                '[Volibear] PRESENTATION_ACCEPTANCE_RESULT {}',
                *['[Volibear] CARD_FACE_RESULT ' + json.dumps(row) for row in self.records],
                '[Volibear] CARD_FACE_BATCH_RESULT ' + json.dumps(self.batch),
                '[Volibear] CATALOG_FACE_RESULT ' + json.dumps(self.final)]

    def validate(self, lines=None, identity=None):
        return h.catalog_face_evidence('\n'.join(self.lines() if lines is None else lines),
                                       self.token, self.cases, self.identity if identity is None else identity)

    def test_original_full_per_case_oracle_and_exact_owned_envelope_pass(self):
        result = self.validate()
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['card_faces']['batch']['completed'], self.cases)
        self.assertEqual(result['envelope'], self.final)

    def test_duplicate_missing_or_reordered_envelopes_and_media_rejected(self):
        good = self.lines()
        for lines in (good + good[:1], good + good[-1:], good[1:], good[:-1], good + [good[1]],
                      [good[1], good[0], *good[2:]], [good[0], *good[2:4], good[1], *good[4:]],
                      good + ['[Volibear] CATALOG_FACE_ERROR injected']):
            with self.subTest(lines=lines): self.assertTrue(self.validate(lines)['errors'])
        malformed = good.copy()
        malformed[0] = malformed[0].replace('{', '{"schema":1,', 1)
        self.assertTrue(self.validate(malformed)['errors'])

    def test_typed_schema_pid_token_cleanup_and_exact_case_selection(self):
        for field, value in [('schema', True), ('schema', 1.0), ('pid', 123.0), ('pid', 124), ('token', 'other'), ('cases', self.cases[:1]),
                             ('finished', False), ('processRestarts', 1), ('processRestarts', 0.0), ('completed', ['card-faces', 'presentation'])]:
            old = deepcopy(self.final)
            self.final[field] = value
            self.assertTrue(self.validate()['errors'], field)
            self.final = old
        self.final['cleanup']['HistoryVisible'] = 1
        self.assertTrue(self.validate()['errors'])
        self.final['cleanup']['HistoryVisible'] = 0
        for identity in ({}, {'pid': True, 'token': self.token}, {'pid': 123, 'token': 'other'}):
            self.assertTrue(self.validate(identity=identity)['errors'])

    def test_paid_card_mutation_and_native_batch_cleanup_are_not_weakened(self):
        self.records[1]['after']['block'] -= 1
        self.assertTrue(self.validate()['errors'])
        self.records[1] = synthetic(self.cases[1])
        self.batch['transitions'][1]['queueEmpty'] = False
        self.assertTrue(self.validate()['errors'])


class CompositeRoutingTests(unittest.TestCase):
    setUp = routing.AcceptanceRunnerTests.setUp
    run_scenario = routing.AcceptanceRunnerTests.run_scenario

    def test_clean_environment_routes_both_original_oracles_and_no_audio_adapter(self):
        cases = h.CARD_FACE_CASES[1:4:2]
        composite = {'errors': [], 'card_faces': {'fixture': True}, 'envelope': {'fixture': True}}
        media = catalog_report()['combat_tests']['media']
        with patch.object(media_checks, 'check_log', return_value=media) as media_check, \
             patch.object(h, 'catalog_face_evidence', return_value=composite) as face_check:
            report, env, command, _, _, shell = self.run_scenario('catalog-face-suite',
                presentation_mode='cards', card_face_batch=cases, record_process_identity=True,
                inherited_adapter='1', initial_env={'VOLIBEAR_TEST_PRIMAL_CASE': 'bad',
                    'VOLIBEAR_SAVE_PHASE': 'bad', 'VOLIBEAR_TEST_ARTIFACT_DIR': 'keep'})
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'catalog-face-suite')
        self.assertIn('--bootstrap', command)
        self.assertEqual(env['VOLIBEAR_TEST_CARD_FACE_BATCH'], ','.join(cases))
        self.assertEqual(env['VOLIBEAR_TEST_PRESENTATION_MODE'], 'cards')
        self.assertNotIn('VOLIBEAR_TEST_PRIMAL_CASE', env)
        self.assertNotIn('VOLIBEAR_SAVE_PHASE', env)
        self.assertEqual(env['VOLIBEAR_TEST_ARTIFACT_DIR'], 'keep')
        shell.assert_not_called()
        media_check.assert_called_once()
        face_check.assert_called_once()
        self.assertEqual(face_check.call_args.args[2], cases)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['checks']['catalog_face_assertions'])

    def test_failed_faces_or_runtime_tail_cannot_hide_behind_successful_media(self):
        for face_errors, tail in ((['failed paid face'], ''), ([], '\nERROR: synthetic runtime tail failure')):
            with patch.object(media_checks, 'check_log', return_value=catalog_report()['combat_tests']['media']), \
                 patch.object(h, 'catalog_face_evidence', return_value={'errors': face_errors, 'card_faces': {}, 'envelope': {}}):
                report, *_ = self.run_scenario('catalog-face-suite', presentation_mode='cards',
                    card_face_batch=h.CARD_FACE_CASES[:2], record_process_identity=True, log=routing.CLEAN_LOG+tail)
            self.assertTrue(report['checks']['presentation_media_assertions'])
            self.assertEqual(report['status'], 'failed')
            if face_errors: self.assertFalse(report['checks']['catalog_face_assertions'])
            if tail: self.assertFalse(report['checks']['no_runtime_errors'])
