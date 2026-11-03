"""Delivery fail-closed ordering, pinned toolchain and source-overlay migration contracts."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import build_assets, local_delivery as delivery, overlay_cleanup, toolchain
from tools.runtime_platform import create_directory_redirect


class OverlayCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / overlay_cleanup.MANIFEST
        self.manifest.parent.mkdir(parents=True)

    def file(self, name, payload=b'old source'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {'path': name, 'sha256': hashlib.sha256(payload).hexdigest()}

    def record(self, rows):
        self.manifest.write_text(json.dumps({'schema': 1, 'files': rows}), encoding='utf-8')

    def test_hash_matched_obsolete_file_removed_but_unlisted_files_survive(self):
        row = self.file('src/obsolete.cs')
        self.file('src/current.cs', b'current')
        self.record([row, {'path': 'tests/already-removed.py', 'sha256': '0' * 64}])
        self.assertEqual(overlay_cleanup.cleanup(self.root, dry_run=True), [self.root / row['path']])
        self.assertTrue((self.root / row['path']).exists())
        overlay_cleanup.cleanup(self.root)
        self.assertFalse((self.root / row['path']).exists())
        self.assertEqual((self.root / 'src/current.cs').read_bytes(), b'current')
        self.assertEqual(overlay_cleanup.cleanup(self.root), [])

    def test_one_locally_edited_file_preserves_the_whole_batch(self):
        rows = [self.file('src/first.cs'), self.file('src/edited.cs')]
        (self.root / 'src/edited.cs').write_bytes(b'local changes')
        self.record(rows)
        with self.assertRaisesRegex(ValueError, 'conflict.*preserved'):
            overlay_cleanup.cleanup(self.root)
        self.assertTrue((self.root / 'src/first.cs').exists())
        self.assertEqual((self.root / 'src/edited.cs').read_bytes(), b'local changes')

    def test_unsafe_paths_and_duplicate_names_are_rejected_without_deletion(self):
        good = self.file('src/first.cs')
        for unsafe in ('../outside', '/tmp/file', 'C:/file', 'src\\file', '.git/config', 'src/../file',
                       'src//file', './file', 'src/.Git/config', 'src/.git./config', 'src/space '):
            with self.subTest(path=unsafe):
                self.record([good, {'path': unsafe, 'sha256': '0' * 64}])
                with self.assertRaises(ValueError):
                    overlay_cleanup.cleanup(self.root)
                self.assertTrue((self.root / good['path']).exists())
        self.record([good, good])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            overlay_cleanup.cleanup(self.root)

    def test_terminal_redirect_and_redirected_parent_are_never_followed(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'keep.cs').write_bytes(b'old source')
        # Windows has unprivileged directory junctions, not file symlinks.
        # Both exercise terminal reparse rejection before regular-file/deletion checks.
        if os.name == 'nt':
            create_directory_redirect(self.root / 'link.cs', target)
        else:
            (self.root / 'link.cs').symlink_to(target / 'keep.cs')
        create_directory_redirect(self.root / 'linked', target)
        for relative in ('link.cs', 'linked/keep.cs'):
            self.record([{'path': relative, 'sha256': hashlib.sha256(b'old source').hexdigest()}])
            with self.assertRaisesRegex(ValueError, 'Redirected'):
                overlay_cleanup.cleanup(self.root)
            self.assertEqual((target / 'keep.cs').read_bytes(), b'old source')

    def test_directories_and_bad_schema_are_refused(self):
        (self.root / 'directory').mkdir()
        self.record([{'path': 'directory', 'sha256': '0' * 64}])
        with self.assertRaisesRegex(ValueError, 'regular file'):
            overlay_cleanup.cleanup(self.root)
        self.manifest.write_text('{"schema":2,"files":[]}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'schema'):
            overlay_cleanup.cleanup(self.root)

    def test_redirect_inside_repository_rejected_even_without_junction_api(self):
        self.file('actual/keep.cs')
        create_directory_redirect(self.root / 'alias', self.root / 'actual')
        self.record([{'path': 'alias/keep.cs', 'sha256': hashlib.sha256(b'old source').hexdigest()}])
        with patch.object(Path, 'is_symlink', return_value=False), \
                patch.object(os.path, 'isjunction', return_value=False, create=True):
            with self.assertRaisesRegex(ValueError, 'Redirected'):
                overlay_cleanup.cleanup(self.root)
        self.assertTrue((self.root / 'actual/keep.cs').exists())


class ToolchainTests(unittest.TestCase):
    def test_pck_header_requires_pinned_engine_and_format(self):
        with tempfile.TemporaryDirectory() as temp:
            pack = Path(temp) / 'Volibear.pck'
            pack.write_bytes(struct.pack('<4s4I', b'GDPC', 3, 4, 5, 1))
            toolchain.validate_pack_header(pack)
            for values in ((b'GDPC', 3, 4, 6, 0), (b'GDPC', 2, 4, 5, 1), (b'nope', 3, 4, 5, 1)):
                pack.write_bytes(struct.pack('<4s4I', *values))
                with self.assertRaisesRegex(ValueError, '4.5.1 PCK'):
                    toolchain.validate_pack_header(pack)

    def test_godot_requires_mono_exact_version_and_dotnet_global_pin(self):
        with patch.object(toolchain, 'executable', side_effect=lambda value, label: Path('/tool') / label), \
                patch.object(toolchain, 'version') as version:
            pin = json.loads((toolchain.ROOT / 'global.json').read_text())['sdk']['version']
            version.side_effect = [pin, '4.5.1.stable.mono.official.hash']
            self.assertEqual(toolchain.check('dotnet', 'godot')['dotnet_version'], pin)
            for wrong in ('4.5.1.stable.official.hash', '4.5.2.stable.mono.hash', '4.6.stable.mono.hash'):
                version.side_effect = [pin, wrong]
                with self.assertRaisesRegex(ValueError, 'Godot 4.5.1 stable Mono'):
                    toolchain.check('dotnet', 'godot')
            version.side_effect = ['10.0.100']
            with self.assertRaisesRegex(ValueError, '.NET SDK'):
                toolchain.check('dotnet', 'godot')

    def test_source_export_is_explicit_for_every_supported_numeric_input(self):
        for mode in (0, 1, 2):
            preset = f'export_filter="all_resources"\nscript_export_mode={mode}\n'
            result = build_assets.source_export_preset(preset, ['res://scripts/a.gd'])
            self.assertIn('script_export_mode=0\n', result)
            self.assertIn('export_files=PackedStringArray("res://scripts/a.gd")', result)
        for preset in ('export_filter="all_resources"\n',
                       'export_filter="all_resources"\nscript_export_mode=1\nscript_export_mode=1\n'):
            with self.assertRaisesRegex(ValueError, 'exactly one GDScript'):
                build_assets.source_export_preset(preset, [])


class DeliveryTests(unittest.TestCase):
    def pipeline(self, options=(), fail=None):
        events = []
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(redirect_stdout(io.StringIO()))
        settings = {'game_dir': '/game path', 'godot': '/godot path', 'dotnet': '/dotnet path'}
        stack.enter_context(patch.object(delivery, 'preflight', return_value=settings))
        stack.enter_context(patch.object(delivery.native_python, 'native_runtime',
            side_effect=lambda python, env: (Path('/host python'), dict(env, PYTHONPATH='/verified libraries'))))
        for owner, name, event, result in (
            (delivery.overlay_cleanup, 'cleanup', 'cleanup', []),
            (delivery, 'save_settings', 'config', None),
            (delivery, 'python_for_checks', 'python', Path('/python path')),
            (delivery, 'prepare_audio', 'audio', None),
            (delivery.dependencies, 'acquire', 'dependency', {}),
            (delivery.dev, 'build_mod', 'build', Path('/built/Volibear.dll')),
            (delivery.build_assets, 'build', 'pck', Path('/built/Volibear.pck')),
            (delivery.dependencies, 'install', 'install', None),
            (delivery.dev, 'deploy', 'deploy', None),
            (delivery.release_package, 'package', 'zip', Path('/built/result.zip')),
        ):
            def invoke(*args, event=event, result=result, **kwargs):
                events.append((event, args, kwargs))
                if event == fail:
                    raise RuntimeError('fixture stage failed: ' + event)
                return result
            stack.enter_context(patch.object(owner, name, side_effect=invoke))
        def command(args, env):
            name = ('suite' if any(str(arg).endswith('native_suite.py') for arg in args) else
                    'multiplayer' if any(str(arg).endswith('multiplayer_suite.py') for arg in args) else 'regression')
            events.append((name, args, env))
            if name == fail:
                raise subprocess.CalledProcessError(1, args)
        stack.enter_context(patch.object(delivery, 'run', side_effect=command))
        return delivery.arguments(list(options)), events

    def test_one_full_regression_follows_fresh_build_and_precedes_packaging(self):
        args, events = self.pipeline()
        delivery.deliver(args)
        self.assertEqual([e[0] for e in events],
                         ['cleanup', 'config', 'python', 'audio', 'dependency', 'build', 'regression', 'pck', 'zip'])
        build = next(event for event in events if event[0] == 'build')
        self.assertEqual(build[2], {'fresh': True})
        regression = next(event for event in events if event[0] == 'regression')
        self.assertIn('--require-native', regression[1])

    def test_release_gate_includes_restart_real_peers_and_full_presentation(self):
        args, events = self.pipeline(['--verify-release', '--audio-driver', 'PulseAudio'])
        from tools import package_lifecycle_acceptance
        with patch.object(package_lifecycle_acceptance, 'accept', return_value={'package_sha256': 'fixture'}) as lifecycle:
            delivery.deliver(args)
        lifecycle.assert_called_once()
        self.assertEqual(lifecycle.call_args.args[:2], (Path('/built/result.zip'), Path('/game path')))
        self.assertEqual([event[0] for event in events][-6:],
                         ['pck', 'install', 'deploy', 'suite', 'multiplayer', 'zip'])
        native = next(event[1] for event in events if event[0] == 'suite')
        self.assertIn('--verify-restart', native)
        self.assertEqual(native[native.index('--timeout') + 1], '28800')
        self.assertEqual(native[native.index('--frames') + 1], '1728000')
        self.assertEqual(native[native.index('--presentation-mode') + 1], 'all')
        peer = next(event[1] for event in events if event[0] == 'multiplayer')
        self.assertIn('--execute-native', peer)
        self.assertIn('--use-deployed', peer)
        self.assertEqual(native[0], Path('/host python'))
        self.assertEqual(peer[0], Path('/host python'))
        for event in events:
            if event[0] in ('suite', 'multiplayer'):
                self.assertEqual(event[2]['PYTHONPATH'], '/verified libraries')
        regression = next(event for event in events if event[0] == 'regression')
        self.assertEqual(regression[1][0], Path('/python path'))

    def test_native_python_mismatch_stops_before_deployment_or_game(self):
        args, events = self.pipeline(['--verify-native'])
        with patch.object(delivery.native_python, 'native_runtime', side_effect=ValueError('ABI mismatch')):
            with self.assertRaisesRegex(ValueError, 'ABI mismatch'):
                delivery.deliver(args)
        for forbidden in ('build', 'regression', 'pck', 'install', 'deploy', 'suite', 'multiplayer', 'zip'):
            self.assertNotIn(forbidden, [event[0] for event in events])

    def test_release_gate_does_not_package_failed_restart_or_peers(self):
        for stage in ('suite', 'multiplayer'):
            with self.subTest(stage=stage):
                args, events = self.pipeline(['--verify-release', '--audio-driver', 'PulseAudio'], fail=stage)
                with self.assertRaises(subprocess.CalledProcessError):
                    delivery.deliver(args)
                self.assertNotIn('zip', [event[0] for event in events])

    def test_release_gate_cannot_silently_downgrade_audio_or_resource_scope(self):
        for options in (['--verify-release'], ['--verify-release', '--audio-driver', 'Dummy'],
                        ['--verify-release', '--presentation-mode', 'cards', '--audio-driver', 'PulseAudio'],
                        ['--verify-release', '--resources-only', '--audio-driver', 'PulseAudio']):
            with self.subTest(options=options), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    delivery.arguments(options)

    def test_requested_native_validation_runs_exactly_one_suite_with_no_os_input_runner(self):
        args, events = self.pipeline(['--verify-native', '--display', 'xvfb', '--presentation-mode', 'all',
                                     '--audio-driver', 'PulseAudio'])
        delivery.deliver(args)
        names = [event[0] for event in events]
        self.assertEqual(names[-5:], ['pck', 'install', 'deploy', 'suite', 'zip'])
        self.assertEqual(names.count('suite'), 1)
        command = next(event[1] for event in events if event[0] == 'suite')
        self.assertIn('--use-deployed', command)
        self.assertIn('all', command)
        self.assertIn('PulseAudio', command)
        self.assertNotIn('native_run_pair.py', ' '.join(map(str, command)))

    def test_failed_build_regression_pack_or_suite_never_packages(self):
        for stage in ('build', 'regression', 'pck', 'suite'):
            with self.subTest(stage=stage):
                args, events = self.pipeline(['--verify-native'], fail=stage)
                with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                    delivery.deliver(args)
                self.assertEqual(events[-1][0], stage)
                self.assertNotIn('zip', [e[0] for e in events])

    def test_resource_only_has_no_dll_dependency_regression_deployment_or_installer(self):
        args, events = self.pipeline(['--resources-only'])
        delivery.deliver(args)
        self.assertEqual([e[0] for e in events], ['cleanup', 'audio', 'pck'])

    def test_doctor_never_mutates_downloads_or_builds(self):
        args, events = self.pipeline(['--doctor'])
        self.assertIsNone(delivery.deliver(args))
        self.assertEqual(events, [])

    def test_preflight_failure_precedes_config_mutation_or_download(self):
        with patch.object(delivery, 'preflight', side_effect=ValueError('wrong version')), \
                patch.object(delivery, 'save_settings') as save, \
                patch.object(delivery.dependencies, 'acquire') as acquire:
            with self.assertRaisesRegex(ValueError, 'wrong version'):
                delivery.deliver(delivery.arguments([]))
            save.assert_not_called()
            acquire.assert_not_called()

    def test_existing_configuration_fields_survive_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'local config.json'
            path.write_text('\ufeff' + json.dumps({'native_option': {'keep': True}, 'game_dir': '/old'}), encoding='utf-8')
            checked = {'dotnet': '/SDK tools/dotnet', 'godot': '/Godot tools/mono',
                       'dotnet_version': '9.0.320', 'godot_version': '4.5.1.stable.mono.hash'}
            with patch.object(delivery, 'CONFIG', path), patch.object(delivery.toolchain, 'check', return_value=checked), \
                    patch.object(delivery.dev, 'validate_game'), patch.object(delivery.overlay_cleanup, 'cleanup'), \
                    redirect_stdout(io.StringIO()):
                settings = delivery.preflight(delivery.arguments(['--game-dir', '/game with spaces']))
                self.assertEqual(settings['native_option'], {'keep': True})
                self.assertEqual(json.loads(path.read_text(encoding='utf-8-sig'))['game_dir'], '/old')
                delivery.save_settings(settings)
                self.assertEqual(json.loads(path.read_text())['dotnet'], '/SDK tools/dotnet')


if __name__ == '__main__':
    unittest.main()
