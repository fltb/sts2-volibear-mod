"""Synthetic runner/oracle regressions only; these tests never launch the game."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_run_pair as pair
import save_load_profile
from test_native_run_evidence import fixture, find, log


class NativeRunPairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.stock = {'successful': True, 'exit_code': 0, 'timed_out': False,
                      'runtime_errors': [], 'categories': []}
        for target, name, value in ((pair, 'ROOT', self.root), (pair.h, 'ROOT', self.root),
                                    (save_load_profile, 'ROOT', self.root), (pair.h, 'IS_WINDOWS', False)):
            context = patch.object(target, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.validate = patch.object(pair.h, 'validate_game').start()
        self.addCleanup(patch.stopall)
        self.stock_runner = patch.object(pair.h, 'stock_teardown', return_value=(set(), self.stock)).start()
        self.rows, self.environments = [], []
        self.native_save = {'schema_version': 1, 'native': 'synthetic-unit-only', 'flag': False}
        self.data = json.dumps(self.native_save, separators=(',', ':')).encode('utf-8')
        self.before_return = None
        self.run_once = patch.object(pair.h, 'run_once', side_effect=self.fake_phase).start()

    def fake_phase(self, game, timeout, frames, **options):
        # A native process is represented only at this external call boundary.
        # No test claims that this synthetic event stream ran the real game.
        self.assertEqual(options['scenario'], 'native-run')
        self.assertEqual(options['display'], 'headless')
        self.assertIs(options['stock_evidence'], self.stock)
        self.environments.append(dict(options['_profile_env']))
        root = Path(options['_profile_env']['VOLIBEAR_TEST_DATA_ROOT'])
        checkpoint = root / 'default/1/modded/profile1/saves/current_run.save'
        mode = options['native_run_mode']
        token = 'prepare-token' if mode == 'three-battle-save' else 'resume-token'
        row = fixture(mode, token, 100 if mode == 'three-battle-save' else 101)
        row['pair'] = options['native_run_pair']
        if mode == 'three-battle-save':
            self.assertFalse(checkpoint.exists(), 'The runner must start with no existing checkpoint')
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(self.data)
        recorded = find(row, 'checkpoint' if mode == 'three-battle-save' else 'checkpoint-before-continue')
        data = checkpoint.read_bytes()
        recorded.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), nativeSave=json.loads(data))
        report = {'run_id': token, 'status': 'passed', 'scenario': 'native-run',
                  'exit_code': 0, 'timed_out': False,
                  'checks': {name: True for name in pair.REQUIRED_CHECKS}}
        text = log(row) + '\nSteam initialization skipped\n[Volibear] LOAD_OK\n[Volibear] ISOLATION_OK steam=false\n'
        if self.before_return:
            text = self.before_return(mode, row, report, checkpoint, text)
        self.rows.append(copy.deepcopy(row))
        directory = self.root / 'artifacts/headless' / token
        directory.mkdir(parents=True)
        (directory / 'game.log').write_text(text, encoding='utf-8')
        if mode == 'resume':
            # The real game may advance its save after Continue. The runner must
            # compare the pre-Continue observation, not overwrite or freeze this.
            checkpoint.write_text('{"advanced_by_native_resume":true}', encoding='utf-8')
        return report

    def run_pair(self):
        return pair.run_pair(self.root / 'game', timeout=300, frames=60000, display='headless')

    def test_success_uses_one_fresh_profile_and_exactly_one_required_restart(self):
        result = self.run_pair()
        self.assertTrue(result['passed'], result)
        self.assertEqual(self.run_once.call_count, 2)
        self.assertEqual([call.kwargs['native_run_mode'] for call in self.run_once.call_args_list],
                         ['three-battle-save', 'resume'])
        self.assertEqual(self.environments[0], self.environments[1])
        self.assertEqual(result['pair_evidence']['errors'], [])
        self.assertEqual(json.loads(Path(result['checkpointPath']).read_text()), {'advanced_by_native_resume': True})
        saved = json.loads(Path(result['report']).read_text())
        self.assertTrue(saved['passed'])
        self.assertEqual(len(saved['phases']), 2)
        settings = Path(result['userRoot']) / 'default/1/settings.save'
        self.assertEqual(json.loads(settings.read_text())['mod_settings'], {'mods_enabled': True})

    def test_stale_development_environment_is_not_forwarded_to_either_phase(self):
        with patch.dict('os.environ', {'VOLIBEAR_TEST_CHARACTER': 'ironclad',
                                       'VOLIBEAR_TEST_CARD_FACE_BATCH': 'bad',
                                       'VOLIBEAR_SAVE_CASE': 'S1', 'VOLIBEAR_NATIVE_RUN_PAIR': 'stale'}):
            result = self.run_pair()
        self.assertTrue(result['passed'], result)
        for env in self.environments:
            for name in ('VOLIBEAR_TEST_CHARACTER', 'VOLIBEAR_TEST_CARD_FACE_BATCH', 'VOLIBEAR_SAVE_CASE', 'VOLIBEAR_NATIVE_RUN_PAIR'):
                self.assertNotIn(name, env)

    def test_every_prepare_gate_is_required_even_with_passed_status(self):
        for name in pair.REQUIRED_CHECKS:
            for value in (False, 1, None):
                with self.subTest(name=name, value=value):
                    report = {'run_id': 'unused', 'status': 'passed', 'scenario': 'native-run',
                              'checks': {gate: True for gate in pair.REQUIRED_CHECKS}}
                    report['checks'][name] = value
                    _, _, errors = pair.phase_evidence(report, 'three-battle-save', 'pair', set(), self.stock)
                    self.assertIn('Every common and native-run gate must be present and literally true', errors)
            report['checks'].pop(name)
            _, _, errors = pair.phase_evidence(report, 'three-battle-save', 'pair', set(), self.stock)
            self.assertIn('Every common and native-run gate must be present and literally true', errors)

    def test_failed_prepare_never_launches_resume(self):
        def fail(mode, row, report, checkpoint, text):
            report['checks']['no_runtime_errors'] = False
            return text
        self.before_return = fail
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)
        self.assertTrue(Path(result['checkpointPath']).is_file())

    def test_common_gates_are_recomputed_from_full_native_log(self):
        self.before_return = lambda mode, row, report, checkpoint, text: text + '\nERROR: actual runtime fault\n'
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)
        self.assertTrue(any('Independent common' in error for error in result['errors']))

    def test_raw_oracle_is_rerun_before_resume(self):
        def corrupt(mode, row, report, checkpoint, text):
            changed = copy.deepcopy(row)
            find(changed, 'paid-action')['plays'][0]['autoPlay'] = True
            return text.replace(log(row), log(changed))
        self.before_return = corrupt
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)
        self.assertTrue(any('AutoPlay' in error for error in result['errors']))

    def test_equivalent_json_with_changed_checkpoint_bytes_stops_resume(self):
        def rewrite(mode, row, report, checkpoint, text):
            checkpoint.write_text(json.dumps(self.native_save, indent=2), encoding='utf-8')
            return text
        self.before_return = rewrite
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)
        self.assertTrue(any('bytes/hash/JSON' in error for error in result['errors']))

    def test_checkpoint_gate_checks_hash_length_and_json_independently(self):
        root = self.root / 'owned'
        root.mkdir()
        checkpoint = root / 'current_run.save'
        checkpoint.write_bytes(self.data)
        original = pair.read_checkpoint(checkpoint, root)
        self.assertEqual(original['nativeSave'], self.native_save)
        for key, bad in (('sha256', '0' * 64), ('bytes', len(self.data) + 1),
                         ('nativeSave', dict(self.native_save, flag=0))):
            evidence = {'observation': {'events': [{'kind': 'checkpoint', 'data': dict(original, **{key: bad})}]}}
            with self.subTest(key=key):
                self.assertTrue(pair.checkpoint_gate(evidence, checkpoint, root))

    def test_checkpoint_symlink_cannot_read_a_different_profile(self):
        root = self.root / 'owned'
        root.mkdir()
        elsewhere = self.root / 'different-profile.save'
        elsewhere.write_bytes(self.data)
        checkpoint = root / 'current_run.save'
        try:
            checkpoint.symlink_to(elsewhere)
        except OSError as error:
            self.skipTest('Symlinks unavailable in unit-test host: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'escaped or redirected'):
            pair.read_checkpoint(checkpoint, root)

    def test_prepare_checkpoint_must_still_exist(self):
        def remove(mode, row, report, checkpoint, text):
            checkpoint.unlink()
            return text
        self.before_return = remove
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)

    def test_pair_requires_actual_distinct_process_ids(self):
        def same_pid(mode, row, report, checkpoint, text):
            if mode == 'resume':
                changed = copy.deepcopy(row)
                changed['processId'] = 100
                return text.replace(log(row), log(changed))
            return text
        self.before_return = same_pid
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 2)
        self.assertTrue(any('actual process restart' in error for error in result['errors']))

    def test_continue_must_restore_saved_state_before_next_battle(self):
        def wrong_gold(mode, row, report, checkpoint, text):
            if mode == 'resume':
                changed = copy.deepcopy(row)
                find(changed, 'continued')['gold'] += 1
                return text.replace(log(row), log(changed))
            return text
        self.before_return = wrong_gold
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertTrue(any('differs: gold' in error for error in result['errors']))

    def test_failed_stock_never_launches_the_native_run(self):
        self.stock['successful'] = False
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(result['phases'], [])
        self.run_once.assert_not_called()
        self.assertTrue(Path(result['report']).is_file())

    def test_runner_exception_is_failure_and_does_not_resume(self):
        self.run_once.side_effect = RuntimeError('launch failed')
        result = self.run_pair()
        self.assertFalse(result['passed'])
        self.assertEqual(self.run_once.call_count, 1)
        self.assertTrue(any('launch failed' in error for error in result['errors']))

    def test_interactive_or_wrong_platform_display_rejected_before_side_effects(self):
        for windows, display in ((True, 'window'), (True, 'headless'), (True, 'xvfb'),
                                 (False, 'window'), (False, 'background')):
            with self.subTest(windows=windows, display=display), patch.object(pair.h, 'IS_WINDOWS', windows):
                with self.assertRaises(ValueError):
                    pair.run_pair(self.root / 'game', display=display)
        self.validate.assert_not_called()
        self.assertFalse((self.root / '.local').exists())

    def test_invalid_bounds_rejected_before_profile_creation(self):
        for timeout, frames in ((29, 1000), (301, 1000), (300, 999), (300, 60001), (True, 1000)):
            with self.subTest(timeout=timeout, frames=frames), self.assertRaises(ValueError):
                pair.run_pair(self.root / 'game', timeout=timeout, frames=frames)
        self.validate.assert_not_called()

    def test_explicit_execute_native_required_before_config_or_launch(self):
        with patch.object(pair.h, 'config') as config, patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as exit_status:
                pair.main([])
            self.assertEqual(exit_status.exception.code, 2)
            config.assert_not_called()
        self.run_once.assert_not_called()


if __name__ == '__main__':
    unittest.main()
