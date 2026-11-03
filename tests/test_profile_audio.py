"""Fresh offline audio preferences only; no game launch or ordinary profile edits."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless as h


class OwnedAudioPreferences(unittest.TestCase):
    def preferences(self, root):
        return [root / relative / 'prefs.save' for relative in
                ('default/1/profile1/saves', 'default/1/modded/profile1/saves')]

    def test_both_platforms_initialize_stock_and_modded_preferences_in_owned_root(self):
        for windows in (True, False):
            with self.subTest(windows=windows), tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary)
                ordinary = workspace / 'ordinary'
                ordinary.mkdir()
                original = ordinary / 'prefs.save'
                original.write_bytes(b'ordinary settings must remain unchanged')
                inherited = {key: str(ordinary) for key in
                             ('HOME', 'APPDATA', 'LOCALAPPDATA', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME')}
                with patch.object(h, 'ROOT', workspace), patch.object(h, 'IS_WINDOWS', windows), \
                     patch.dict(os.environ, inherited):
                    directory, env, _ = h.prepare_run(Path('not-a-game'), 'fresh', 10)
                    root = h.user_data_root(directory)
                    expected = directory / ('appdata' if windows else 'data') / 'SlayTheSpire2'
                    self.assertEqual(root, expected)
                    self.assertEqual(env['VOLIBEAR_TEST_DATA_ROOT'], str(root))
                    for prefs in self.preferences(root):
                        self.assertTrue(prefs.is_relative_to(directory))
                        self.assertEqual(json.loads(prefs.read_text(encoding='utf-8')),
                                         {'schema_version': 2, 'mute_in_background': False})
                    settings = json.loads((root / 'default/1/settings.save').read_text(encoding='utf-8'))
                    self.assertEqual(settings['schema_version'], 5)
                    self.assertNotIn('volume_master', settings)
                    self.assertNotIn('volume_sfx', settings)
                self.assertEqual(original.read_bytes(), b'ordinary settings must remain unchanged')

    def test_existing_profile_is_rejected_without_overwriting_preferences(self):
        for windows in (True, False):
            with self.subTest(windows=windows), tempfile.TemporaryDirectory() as temporary, \
                 patch.object(h, 'IS_WINDOWS', windows):
                directory = Path(temporary) / 'profile'
                env = h.isolated_env(directory)
                root = h.user_data_root(directory)
                prefs = self.preferences(root)[1]
                marker = b'{"schema_version":2,"mute_in_background":true,"custom":"preserve"}'
                prefs.write_bytes(marker)
                with self.assertRaises(FileExistsError):
                    h.isolated_env(directory)
                self.assertEqual(prefs.read_bytes(), marker)
                self.assertEqual(env['HOME'], str(directory / 'home'))

    def test_resume_environment_preserves_existing_preferences_and_settings_byte_for_byte(self):
        for windows in (True, False):
            with self.subTest(windows=windows), tempfile.TemporaryDirectory() as temporary, \
                 patch.object(h, 'ROOT', Path(temporary)), patch.object(h, 'IS_WINDOWS', windows):
                directory, env, _ = h.prepare_run(Path('not-a-game'), 'prepare', 10)
                root = h.user_data_root(directory)
                paths = self.preferences(root) + [root / 'default/1/settings.save']
                for i, path in enumerate(paths):
                    path.write_bytes(('preserved after prepare ' + str(i)).encode())
                before = {path: path.read_bytes() for path in paths}
                resumed, resumed_env, _ = h.prepare_run(Path('not-a-game'), 'resume', 10, _profile_env=env)
                self.assertEqual(resumed_env['VOLIBEAR_TEST_DATA_ROOT'], str(root))
                self.assertFalse(h.user_data_root(resumed).exists())
                self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_stock_control_uses_fresh_unmodded_preferences_without_changing_oracles(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(h, 'ROOT', Path(temporary)), \
             patch.object(h, 'new_run_id', return_value='stock'), \
             patch.object(h, 'launch', return_value=(0, False)) as launch, \
             patch.object(h, 'combined_log', return_value='Steam initialization skipped\nSTOCK_CONTROLLER_READY_NATIVE_QUIT\n'):
            _, report = h.stock_teardown(Path('not-a-game'), 60, 100)
            self.assertTrue(report['successful'])
            self.assertIn('--nomods', launch.call_args.args[3])
            root = Path(launch.call_args.args[2]['VOLIBEAR_TEST_DATA_ROOT'])
            self.assertFalse(json.loads(self.preferences(root)[0].read_text(encoding='utf-8'))['mute_in_background'])


if __name__ == '__main__':
    unittest.main()
