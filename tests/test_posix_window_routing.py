"""Authorized foreground routing only; never launches a game or builds assets."""
from contextlib import ExitStack
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import headless as h
import native_suite
import multiplayer_suite
import save_load_pair
import local_delivery


class PosixWindowRouting(unittest.TestCase):
    def test_native_and_multiplayer_keep_stock_gate(self):
        for suite in (native_suite, multiplayer_suite):
            with self.subTest(suite=suite.__name__), ExitStack() as stack:
                stack.enter_context(patch.object(h, 'IS_WINDOWS', False))
                stack.enter_context(patch.dict(os.environ, {'DISPLAY': ':77'}))
                stack.enter_context(patch.object(h, 'validate_game'))
                if suite is multiplayer_suite:
                    stack.enter_context(patch.object(suite, 'deployed_hashes', return_value={}))
                stock = stack.enter_context(patch.object(h, 'stock_teardown', return_value=(set(), {'successful': False})))
                launch = stack.enter_context(patch.object(h, 'run_once'))
                with self.assertRaisesRegex(RuntimeError, 'Stock'):
                    suite.run_suite(Path('/unused'), display='window')
                self.assertEqual(stock.call_args.args[3], 'window')
                launch.assert_not_called()

    def test_missing_display_fails_before_validation_or_launch(self):
        for run in (lambda: native_suite.run_suite(Path('/unused'), display='window'),
                    lambda: multiplayer_suite.run_suite(Path('/unused'), display='window'),
                    lambda: save_load_pair.run_pair(Path('/unused'), 'S2', 'restart', display='window')):
            with patch.object(h, 'IS_WINDOWS', False), patch.dict(os.environ, {'DISPLAY': ''}), \
                    patch.object(h, 'validate_game') as validate, patch.object(h, 'stock_teardown') as stock:
                with self.assertRaisesRegex(RuntimeError, 'DISPLAY'):
                    run()
                validate.assert_not_called()
                stock.assert_not_called()

    def test_restart_direct_command_and_real_pid(self):
        with patch.object(h, 'IS_WINDOWS', False), patch.dict(os.environ, {'DISPLAY': ':77'}):
            command = save_load_pair.phase_command(Path('/game'), Path('/receipt'), 'window', 5000,
                                                   token='phase-token', audio_driver='PulseAudio')
        self.assertNotIn('xvfb-run', command)
        self.assertNotIn('--headless', command)
        self.assertNotIn('--bootstrap', command)
        self.assertEqual(command.count('--script'), 1)
        self.assertEqual(command[command.index('--script') + 1], str(h.ROOT / 'tools/window_guard.gd'))
        self.assertIn('--force-steam=off', command)
        self.assertEqual(command[-2:], ['--audio-driver', 'PulseAudio'])
        self.assertEqual(save_load_pair.native_pid(Path('/receipt'), 'window', 123, 'phase-token', Path('/game')), 123)

    def test_delivery_routes_window_through_all_release_checks(self):
        args = local_delivery.arguments(['--verify-release', '--display', 'window', '--audio-driver', 'PulseAudio'])
        native = local_delivery.native_command(args, Path(sys.executable))
        peers = local_delivery.multiplayer_command(args, Path(sys.executable))
        for command in (native, peers):
            self.assertEqual(command[command.index('--display') + 1], 'window')
        self.assertIn('--verify-restart', native)
        self.assertEqual(native[native.index('--card-face-cases') + 1], 'all')
        self.assertEqual(native[native.index('--card-lifecycle-cases') + 1], 'all')

    def test_window_profile_keeps_offline_isolation_and_fast_mode(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp, patch.object(h, 'ROOT', Path(temp)), \
                patch.object(h, 'IS_WINDOWS', False), patch.dict(os.environ, {'DISPLAY': ':77'}):
            directory, env, command = h.prepare_run(Path('/game'), 'window-test', 5000, 'window')
            self.assertEqual(env['DISPLAY'], ':77')
            self.assertEqual(env['VOLIBEAR_TEST_FAST_MODE'], 'Fast')
            self.assertEqual(env['VOLIBEAR_TEST_TOKEN'], 'window-test')
            self.assertNotIn('VOLIBEAR_TEST_PRIVATE_DESKTOP', env)
            self.assertTrue(Path(env['VOLIBEAR_TEST_DATA_ROOT']).is_relative_to(directory))
            self.assertIn('--force-steam=off', command)
