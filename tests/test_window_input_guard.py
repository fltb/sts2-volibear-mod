"""Filesystem ownership and real launch routing; no game process is started."""
from contextlib import ExitStack
from pathlib import Path
import os
import json
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h
import multiplayer_suite as multiplayer
from tools.runtime_platform import create_directory_redirect


class WindowInputGuard(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.game = self.root / '.local/game'
        self.game.mkdir(parents=True)
        self.path = self.game / 'override.cfg'
        self.stack.enter_context(patch.object(h, 'ROOT', self.root))
        self.stack.enter_context(patch.object(h, 'IS_WINDOWS', False))

    def linux_unwind_file(self, available=True):
        """Mock only the Linux library on tests deliberately routing as POSIX."""
        original = Path.is_file
        unwind = Path('/lib/x86_64-linux-gnu/libgcc_s.so.1')
        return patch.object(Path, 'is_file', autospec=True,
                            side_effect=lambda path: available if path == unwind else original(path))

    def test_create_cleanup_and_exception(self):
        for fail in (False, True):
            try:
                with h.window_input_guard(self.game, 'window'):
                    self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)
                    for setting in (b'window/size/no_focus=false', b'window/size/mode=0',
                                    b'window/size/always_on_top=false', b'window/size/borderless=false',
                                    b'window/size/window_width_override=1280', b'window/size/window_height_override=720'):
                        self.assertIn(setting + b'\n', self.path.read_bytes())
                    if fail:
                        raise LookupError('test exception')
            except LookupError:
                self.assertTrue(fail)
            self.assertFalse(self.path.exists())

    def test_real_launch_arguments_and_fresh_profile_force_small_window(self):
        with patch.dict(os.environ, {'DISPLAY': ':77'}), patch.object(h, 'game_executable', return_value=self.game/'sts2'):
            directory, env, command = h.prepare_run(self.game, 'window-contract', 600, 'window')
        self.assertIn('--windowed', command)
        self.assertEqual(command[command.index('--resolution') + 1], '1280x720')
        settings = json.loads((h.user_data_root(directory)/'default/1/settings.save').read_text())
        self.assertIs(settings['fullscreen'], False)
        self.assertEqual(settings['window_size'], {'X': 1280, 'Y': 720})
        self.assertEqual(settings['window_position'], {'X': 64, 'Y': 64})

    def test_refuse_existing_even_identical(self):
        self.path.write_bytes(h.WINDOW_OVERRIDE)
        with self.assertRaises(FileExistsError), h.window_input_guard(self.game, 'window'):
            self.fail('must not enter')
        self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)

    def test_preserve_mutation(self):
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            with h.window_input_guard(self.game, 'window'):
                self.path.write_bytes(b'operator update')
        self.assertEqual(self.path.read_bytes(), b'operator update')

    def test_preserve_replacement_even_identical_bytes(self):
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            with h.window_input_guard(self.game, 'window'):
                replacement = self.game / 'replacement.cfg'
                replacement.write_bytes(h.WINDOW_OVERRIDE)
                self.assertEqual(self.path.resolve(), self.game / 'override.cfg')
                replacement.replace(self.path)
        self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)

    def test_launch_failure_cleans_override(self):
        with patch.object(h, 'spawn_owned', side_effect=OSError('launch failed')):
            with self.assertRaisesRegex(OSError, 'launch failed'):
                h.launch(self.game, self.root, {}, [], 1, display='window')
        self.assertFalse(self.path.exists())

    def test_scripts_guard_before_original_scene_without_synthetic_input(self):
        tools = Path(__file__).resolve().parents[1] / 'tools'
        for name in ('window_guard.gd', 'stock_ready.gd'):
            source = (tools / name).read_text()
            for flag in ('WINDOW_FLAG_NO_FOCUS', 'WINDOW_FLAG_MOUSE_PASSTHROUGH'):
                setter = 'window_set_flag(DisplayServer.' + flag + ', false)'
                self.assertLess(source.index(setter), source.index('call_deferred("launch_original")'))
                self.assertNotIn(flag + ', true)', source)
            self.assertIn('window_set_size(Vector2i(1280, 720))', source)
            self.assertIn('verify_window_manager("startup")', source)
            self.assertIn('_NET_WM_USER_TIME(CARDINAL) = 0 |', source)
            self.assertIn('WINDOW_GUARD_ERROR missing pre-map non-activation hint', source)
            self.assertIn('"_NET_WM_WINDOW_TYPE_NORMAL" in observed', source)
            for forbidden in ('_NET_WM_WINDOW_TYPE_UTILITY', '_NET_WM_STATE_ABOVE', '_NET_WM_STATE_FULLSCREEN'):
                self.assertIn('"' + forbidden + '" in observed', source)
            self.assertIn('OS.execute("xprop", ["-root", "_NET_ACTIVE_WINDOW"]', source)
            self.assertNotIn('window_move_to_foreground(', source)
            self.assertNotIn('grab_focus(', source)
            self.assertNotIn('wmctrl', source)
            self.assertLess(source.index('WINDOW_MODE_WINDOWED'), source.index('call_deferred("launch_original")'))
            self.assertIn('window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)', source)
            self.assertIn('window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)', source)
            self.assertIn('WINDOW_MODE_READY mode=', source)
            self.assertIn('WINDOW_GUARD_ERROR windowed/non-topmost contract lost', source)
            self.assertNotIn('!= DisplayServer.WINDOW_MODE_WINDOWED', source)
            self.assertIn('mode != DisplayServer.WINDOW_MODE_FULLSCREEN', source)
            self.assertIn('mode != DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN', source)
            self.assertIn('WINDOW_MODE_VIOLATION mode=', source)
            self.assertIn('verify_window_manager("mode_violation")', source)
            self.assertIn('change_scene_to_file(scene)', source)
            self.assertNotIn('Input.parse_input_event', source)
            self.assertNotIn('set_process_input', source)
            self.assertNotIn('transparent', source)

    def test_window_performance_guard_is_bounded_without_time_scaling(self):
        source = (Path(__file__).resolve().parents[1] / 'tools/window_guard.gd').read_text()
        self.assertIn('now >= 30000', source)
        self.assertIn('Engine.get_frames_per_second() < 10', source)
        self.assertIn('low_fps_samples >= 3', source)
        self.assertIn('WINDOW_PERFORMANCE_FAILED', source)
        self.assertIn('quit(3)', source)
        self.assertNotIn('time_scale', source)

    def test_all_isolated_profile_writers_disable_vsync_and_keep_60fps(self):
        tools = Path(__file__).resolve().parents[1] / 'tools'
        for name in ('headless.py', 'native_run_pair.py', 'save_load_pair.py', 'save_load_catalog_pair.py'):
            source = (tools / name).read_text()
            self.assertRegex(source, r"(?:'vsync': 'off'|vsync='off')")
            self.assertRegex(source, r"(?:'fps_limit': 60|fps_limit=60)")
            compact = ''.join(source.split())
            for field, value in [('fullscreen', 'False'), ('window_size', "{'X':1280,'Y':720}"),
                                 ('window_position', "{'X':64,'Y':64}")]:
                self.assertTrue("'" + field + "':" + value in compact or field + '=' + value in compact, (name, field))

    def test_refuse_production_and_terminal_redirect(self):
        with self.assertRaises(ValueError), h.window_input_guard(self.root, 'window'):
            pass
        outside = self.root / 'outside'
        outside.mkdir()
        target = outside / 'existing.cfg'
        target.write_bytes(b'keep')
        if os.name == 'nt':
            # A junction is a terminal directory reparse point, not a file symlink.
            create_directory_redirect(self.path, outside)
        else:
            self.path.symlink_to(target)
        with self.assertRaises(ValueError), h.window_input_guard(self.game, 'window'):
            pass
        self.assertEqual(target.read_bytes(), b'keep')

    def test_other_modes_do_not_touch_existing_file(self):
        self.path.write_bytes(b'keep')
        for display in ('headless', 'xvfb', 'background'):
            with h.window_input_guard(self.game, display):
                self.assertEqual(self.path.read_bytes(), b'keep')
        with patch.object(h, 'IS_WINDOWS', True), h.window_input_guard(self.game, 'window'):
            self.assertEqual(self.path.read_bytes(), b'keep')

    def test_launch_owns_override_until_wait_completes(self):
        def spawn(*args, **kwargs):
            self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)
            return Mock(), None
        def wait(*args):
            self.assertTrue(self.path.exists())
            return 0, False
        with patch.object(h, 'spawn_owned', side_effect=spawn), patch.object(h, 'wait_owned_process', side_effect=wait):
            self.assertEqual(h.launch(self.game, self.root, {}, [], 1, display='window'), (0, False))
        self.assertFalse(self.path.exists())

    def test_cold_restart_route_guards_spawn_and_cleans_failure(self):
        import save_load_pair
        def spawn(command, *args, **kwargs):
            self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)
            self.assertEqual(command.count('--script'), 1)
            raise OSError('test spawn failure')
        with self.linux_unwind_file(), patch.dict(os.environ, {'DISPLAY': ':77'}), patch.object(h, 'spawn_owned', side_effect=spawn):
            with self.assertRaisesRegex(OSError, 'test spawn failure'):
                save_load_pair.launch_phase(self.game, self.root,
                    {'VOLIBEAR_TEST_DATA_ROOT': str(self.root / 'profile')},
                    'S2', 'restart', 'prepare', 'seed', set(), {}, 1, 1, 'window')
        self.assertFalse(self.path.exists())

    def test_linux_harmony_missing_unwind_still_refuses_before_spawn(self):
        import save_load_pair
        with self.linux_unwind_file(False), patch.dict(os.environ, {'DISPLAY': ':77'}), \
                patch.object(h, 'spawn_owned') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'libgcc_s.so.1'):
                save_load_pair.launch_phase(self.game, self.root,
                    {'VOLIBEAR_TEST_DATA_ROOT': str(self.root / 'profile')},
                    'S2', 'restart', 'prepare', 'seed', set(), {}, 1, 1, 'window')
            spawn.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_stock_uses_one_script_and_same_guard(self):
        directory = self.root / 'stock'
        directory.mkdir()
        command = ['game', '--script', str(self.root / 'tools/window_guard.gd')]
        def launch(game, directory, env, command, timeout, display):
            self.assertEqual(display, 'window')
            self.assertEqual(command.count('--script'), 1)
            self.assertEqual(command[command.index('--script') + 1], str(self.root / 'tools/stock_ready.gd'))
            self.assertEqual(env['VOLIBEAR_TEST_WINDOW_GUARD'], '1')
            return 0, False
        with patch.object(h, 'prepare_run', return_value=(directory, {}, command)), patch.object(h, 'launch', side_effect=launch), patch.object(h, 'combined_log', return_value='STOCK_CONTROLLER_READY_NATIVE_QUIT\nSteam initialization skipped'):
            self.assertTrue(h.stock_teardown(self.game, 1, 1, 'window')[1]['successful'])

    def test_multiplayer_shared_override_covers_both_peers(self):
        import threading
        barrier = threading.Barrier(2)
        stock = {'successful': True, 'exit_code': 0, 'timed_out': False, 'runtime_errors': []}
        seen = []
        def peer(game, directory, env, command, *args):
            self.assertEqual(self.path.read_bytes(), h.WINDOW_OVERRIDE)
            self.assertEqual(command.count('--script'), 1)
            self.assertEqual(Path(command[command.index('--script') + 1]).name, 'window_guard.gd')
            barrier.wait(timeout=5)
            seen.append(directory.name)
            return {'pid': 10 if directory.name.endswith('host') else 11, 'checks': {'ok': True}}, ''
        with self.linux_unwind_file(), patch.dict(os.environ, {'DISPLAY': ':77'}), patch.object(h, 'validate_game'), patch.object(multiplayer, 'deployed_hashes', return_value={}), patch.object(h, 'stock_teardown', return_value=(set(), stock)), patch.object(multiplayer, 'launch_peer', side_effect=peer), patch.object(multiplayer, 'check_pair', return_value={'errors': [], 'scope': 'test'}):
            result = multiplayer.run_suite(self.game, display='window')
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(seen), 2)
        self.assertFalse(self.path.exists())
