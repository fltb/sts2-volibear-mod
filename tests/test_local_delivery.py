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
import sys
import time
import unittest
from unittest.mock import Mock, patch

from tools import build_assets, local_delivery as delivery, overlay_cleanup, toolchain
from tools.runtime_platform import create_directory_redirect


class ParallelValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        context = patch.object(delivery, 'ROOT', self.root)
        context.start(); self.addCleanup(context.stop)
        self.args = delivery.arguments(['--verify-release', '--audio-driver', 'WASAPI'])
        self.args._release_deadline = time.monotonic() + 5
        self.args._phases = []
        self.args._acceptance = {'phases': self.args._phases}
        self.args._acceptance_dir = self.root / 'acceptance'
        self.args._acceptance_dir.mkdir()
        self.processes = []
        original = subprocess.Popen
        def spawn(*args, **kwargs):
            process = original(*args, **kwargs)
            self.processes.append(process)
            return process
        context = patch.object(delivery.subprocess, 'Popen', side_effect=spawn)
        context.start(); self.addCleanup(context.stop)
        # Emergency test cleanup only: production must already have collected both roots.
        def cleanup():
            for process in self.processes:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=2)
        self.addCleanup(cleanup)

    def command(self, name, ending):
        other = 'assets' if name == 'regression' else 'regression'
        code = ('import time\nfrom pathlib import Path\n'
                + f'Path({name!r}).write_text("ready")\n'
                + 'until=time.monotonic()+2\n'
                + f'while not Path({other!r}).exists():\n'
                + ' if time.monotonic()>until: raise SystemExit(19)\n time.sleep(.01)\n'
                + ending + '\n')
        return [sys.executable, '-B', '-c', code]

    def test_real_workers_overlap_and_summary_preserves_both_complete_phases(self):
        deadline = self.args._release_deadline
        delivery._parallel_validation(self.args, self.command('regression', 'print("regression done")'),
                                      self.command('assets', 'print("assets done")'), dict(os.environ))
        rows = json.loads((self.args._acceptance_dir / 'summary.json').read_text())['phases']
        self.assertEqual([row['name'] for row in rows], ['regression', 'assets'])
        self.assertTrue(all(row['status'] == 'completed' and row['exit_code'] == 0 for row in rows))
        self.assertLess(max(row['started_monotonic'] for row in rows),
                        min(row['started_monotonic'] + row['elapsed_seconds'] for row in rows))
        self.assertEqual(self.args._release_deadline, deadline)
        self.assertEqual(len(self.processes), 2)
        self.assertTrue(all(process.poll() == 0 for process in self.processes))
        for name in ('regression', 'assets'):
            self.assertIn(name + ' done', (self.args._acceptance_dir / (name + '.log')).read_text())

    def test_parallel_wait_uses_existing_deadline_and_collects_both_roots(self):
        self.args._release_deadline = time.monotonic() + .3
        deadline = self.args._release_deadline
        with self.assertRaises(TimeoutError):
            delivery._parallel_validation(self.args, self.command('regression', 'time.sleep(60)'),
                                          self.command('assets', 'time.sleep(60)'), dict(os.environ))
        self.assertEqual(self.args._release_deadline, deadline)
        self.assertTrue(all(process.poll() is not None for process in self.processes))
        self.assertEqual([row['status'] for row in self.args._phases], ['cancelled', 'cancelled'])
        self.assertTrue(all(row['remaining_seconds'] == 0 for row in self.args._phases))

    def test_native_pair_uses_both_native_environments_and_keeps_separate_gate_states(self):
        for failing in (None, 'native_suite', 'multiplayer'):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as directory:
                self.args._phases.clear()
                self.args._acceptance = delivery.acceptance_summary()
                self.args._acceptance['phases'] = self.args._phases
                self.args._acceptance_dir = Path(directory)
                env = dict(os.environ, VOLIBEAR_SYNTHETIC_NATIVE_ENV='present')
                commands = {}
                for name, ready in (('native_suite', 'regression'), ('multiplayer', 'assets')):
                    ending = ('raise SystemExit(7)' if name == failing else 'time.sleep(60)' if failing else 'print("done")')
                    commands[name] = self.command(ready, 'import os\nassert os.environ["VOLIBEAR_SYNTHETIC_NATIVE_ENV"] == "present"\n' + ending)
                with patch.object(delivery, 'native_command', return_value=commands['native_suite']) as native, \
                     patch.object(delivery, 'multiplayer_command', return_value=commands['multiplayer']) as peers:
                    if failing:
                        with self.assertRaises(subprocess.CalledProcessError):
                            delivery._parallel_native(self.args, Path(sys.executable), env)
                    else:
                        delivery._parallel_native(self.args, Path(sys.executable), env)
                    native.assert_called_once_with(self.args, Path(sys.executable))
                    peers.assert_called_once_with(self.args, Path(sys.executable))
                report = json.loads((self.args._acceptance_dir / 'summary.json').read_text())
                rows = {row['name']: row for row in report['phases']}
                for name, items in (('native_suite', ('A2', 'A3', 'A4', 'A5', 'A7')), ('multiplayer', ('A6',))):
                    expected = ('passed' if not failing else ('group_gate_failed' if len(items) > 1 else 'failed')
                                if name == failing else 'cancelled')
                    self.assertTrue(all(report['items'][item]['status'] == expected for item in items))
                    self.assertEqual(rows[name]['status'], 'completed' if not failing else 'failed' if name == failing else 'cancelled')
                self.assertTrue(all(process.poll() is not None for process in self.processes))
                if not failing:
                    self.assertLess(max(row['started_monotonic'] for row in rows.values()),
                                    min(row['started_monotonic'] + row['elapsed_seconds'] for row in rows.values()))

    def test_either_failure_collects_other_entrypoint_and_never_marks_it_completed(self):
        for failing in ('regression', 'assets'):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as directory:
                self.args._phases.clear()
                self.args._acceptance_dir = Path(directory)
                commands = {name: self.command(name, 'raise SystemExit(7)' if name == failing else 'time.sleep(60)')
                            for name in ('regression', 'assets')}
                with self.assertRaises(subprocess.CalledProcessError):
                    delivery._parallel_validation(self.args, commands['regression'], commands['assets'], dict(os.environ))
                rows = {row['name']: row for row in json.loads(
                    (self.args._acceptance_dir / 'summary.json').read_text())['phases']}
                self.assertEqual(rows[failing]['status'], 'failed')
                other = 'assets' if failing == 'regression' else 'regression'
                self.assertEqual(rows[other]['status'], 'cancelled')
                self.assertEqual(rows[other]['descendant_cleanup'], 'release-supervisor')
                self.assertTrue(all(process.poll() is not None for process in self.processes))


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

    def test_native_parallel_guard_requires_supervised_windows_background(self):
        args = delivery.arguments(['--verify-release', '--audio-driver', 'WASAPI'])
        args._release_deadline = time.monotonic() + 5
        for platform, display, expected in (('nt', 'background', True), ('nt', 'window', False),
                                            ('posix', 'window', False), ('posix', 'xvfb', False)):
            args.display = display
            with patch.object(delivery.os, 'name', platform):
                self.assertEqual(delivery._parallel_native_enabled(args), expected)
                self.assertEqual('--parallel-restart' in delivery.native_command(args, 'fixture-python'), expected)
                self.assertEqual('--parallel-catalog' in delivery.native_command(args, 'fixture-python'), expected)
        args.display = 'background'
        with patch.object(delivery.os, 'name', 'nt'):
            for mode in ('cards', 'actions'):
                args.presentation_mode = mode
                self.assertNotIn('--parallel-catalog', delivery.native_command(args, 'fixture-python'))
            args.presentation_mode = 'all'
            del args._release_deadline
            self.assertFalse(delivery._parallel_native_enabled(args))
            self.assertNotIn('--parallel-catalog', delivery.native_command(args, 'fixture-python'))
            args._release_deadline = time.monotonic() + 5
            args.verify_release = False
            self.assertFalse(delivery._parallel_native_enabled(args))

    def test_native_parallel_disabled_keeps_both_native_commands_serial(self):
        args, events = self.pipeline(['--verify-release', '--audio-driver', 'WASAPI'], fail='multiplayer')
        args._release_deadline = time.monotonic() + 5
        with patch.object(delivery, '_parallel_validation'), \
             patch.object(delivery, '_parallel_native_enabled', return_value=False), \
             patch.object(delivery, '_parallel_native', side_effect=AssertionError('Serial mode must not launch a pair')) as parallel:
            with self.assertRaises(subprocess.CalledProcessError):
                delivery.deliver(args)
        parallel.assert_not_called()
        names = [event[0] for event in events]
        self.assertLess(names.index('deploy'), names.index('suite'))
        self.assertLess(names.index('suite'), names.index('multiplayer'))
        self.assertNotIn('zip', names)

    def test_native_parallel_catalog_failure_preserves_independent_status_and_never_packages(self):
        args, events = self.pipeline(['--verify-release', '--audio-driver', 'WASAPI'])
        args._release_deadline = time.monotonic() + 5
        def fail(current, python, env):
            self.assertEqual([event[0] for event in events][-1], 'deploy')
            self.assertEqual(python, Path('/host python'))
            self.assertEqual(env['PYTHONPATH'], '/verified libraries')
            delivery.mark(current, 'A6')
            for item in ('A2', 'A3', 'A4', 'A5', 'A7'):
                current._acceptance['items'][item]['status'] = 'group_gate_failed'
            self.assertIn('--parallel-catalog', delivery.native_command(current, python))
            # Missing/failed catalog makes the native CLI nonzero even if main/S2 passed.
            raise subprocess.CalledProcessError(1, ['synthetic-native', '--parallel-catalog'])
        with patch.object(delivery, '_parallel_validation') as validation, \
             patch.object(delivery, '_parallel_native_enabled', return_value=True), \
             patch.object(delivery, '_parallel_native', side_effect=fail) as native:
            with self.assertRaises(subprocess.CalledProcessError):
                delivery.deliver(args)
        validation.assert_called_once()
        native.assert_called_once()
        self.assertNotIn('zip', [event[0] for event in events])
        self.assertFalse({'suite', 'multiplayer'} & {event[0] for event in events})
        summary = json.loads((args._acceptance_dir / 'summary.json').read_text())
        self.assertEqual(summary['items']['A6']['status'], 'passed')
        self.assertEqual(summary['items']['A2']['status'], 'group_gate_failed')
        self.assertEqual(summary['items']['A1']['status'], 'passed')

    def test_phase_timing_is_monotonic_flushed_and_running_snapshot_is_persisted(self):
        args = delivery.arguments([])
        args._phases = []
        args._acceptance = {'phases': args._phases}
        with tempfile.TemporaryDirectory() as directory:
            args._acceptance_dir = Path(directory)
            with patch.object(delivery.time, 'monotonic', side_effect=[10.0, 12.5]), \
                 patch('builtins.print') as output:
                with delivery.phase(args, 'build'):
                    running = json.loads((args._acceptance_dir / 'summary.json').read_text())
                    self.assertEqual(running['phases'][0]['status'], 'running')
                    self.assertIsNone(running['phases'][0]['elapsed_seconds'])
                self.assertTrue(all(call.kwargs.get('flush') is True for call in output.call_args_list))
            saved = json.loads((args._acceptance_dir / 'summary.json').read_text())
            self.assertEqual(saved['phases'][0]['elapsed_seconds'], 2.5)
            self.assertEqual(saved['phases'][0]['status'], 'completed')

    def test_failed_release_keeps_completed_and_failed_phase_timings(self):
        args, events = self.pipeline(['--verify-release', '--audio-driver', 'PulseAudio'], fail='regression')
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery, 'ROOT', Path(directory)):
            with self.assertRaises(subprocess.CalledProcessError):
                delivery.deliver(args)
            summary = json.loads((args._acceptance_dir / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual([row['name'] for row in summary['phases']],
                             ['preflight', 'tools_and_dependencies', 'build', 'regression'])
            self.assertEqual([row['status'] for row in summary['phases']],
                             ['completed', 'completed', 'completed', 'failed'])
            self.assertTrue(all(row['elapsed_seconds'] >= 0 for row in summary['phases']))
            self.assertIn('error', summary['phases'][-1])
            self.assertNotIn('zip', [event[0] for event in events])

    def test_force_cold_assets_is_explicit_and_reaches_serial_build(self):
        for options, reuse in (([], True), (['--force-cold-assets'], False),
                               (['--resources-only', '--force-cold-assets'], False)):
            with self.subTest(options=options):
                args, events = self.pipeline(options)
                delivery.deliver(args)
                assets = next(event for event in events if event[0] == 'pck')
                self.assertEqual(assets[2]['reuse'], reuse)

    def test_asset_cli_force_cold_forwards_reuse_false_without_building(self):
        for options, reuse in (([], True), (['--force-cold'], False)):
            with patch.object(sys, 'argv', ['build_assets.py', '--godot', 'fixture-godot', *options]), \
                 patch.object(build_assets, 'build') as build:
                build_assets.main()
                self.assertEqual(build.call_args.kwargs['reuse'], reuse)

    def test_supervised_parallel_failure_never_deploys_or_enters_native(self):
        for failing in ('regression', 'assets'):
            with self.subTest(failing=failing):
                args, events = self.pipeline(['--verify-release', '--audio-driver', 'WASAPI'])
                args._release_deadline = time.monotonic() + 5
                args.force_cold_assets = failing == 'assets'
                def fail(*commands):
                    self.assertIn('build', [event[0] for event in events])
                    self.assertNotIn('deploy', [event[0] for event in events])
                    raise subprocess.CalledProcessError(7, [failing])
                with patch.object(delivery, '_parallel_validation', side_effect=fail) as parallel:
                    with self.assertRaises(subprocess.CalledProcessError):
                        delivery.deliver(args)
                parallel.assert_called_once()
                regression, assets = parallel.call_args.args[1:3]
                self.assertIn('--require-native', regression)
                self.assertEqual(regression[regression.index('--jobs') + 1], '6')
                self.assertEqual(assets[0], sys.executable)
                self.assertEqual('--force-cold' in assets, args.force_cold_assets)
                self.assertNotIn('pck', [event[0] for event in events])
                self.assertFalse({'install', 'deploy', 'suite', 'multiplayer', 'zip'} & {event[0] for event in events})

    def test_one_full_regression_follows_fresh_build_and_precedes_packaging(self):
        args, events = self.pipeline()
        delivery.deliver(args)
        self.assertEqual([e[0] for e in events],
                         ['cleanup', 'config', 'python', 'audio', 'dependency', 'build', 'regression', 'pck', 'zip'])
        build = next(event for event in events if event[0] == 'build')
        self.assertEqual(build[2], {'fresh': True})
        regression = next(event for event in events if event[0] == 'regression')
        self.assertIn('--require-native', regression[1])
        self.assertEqual(regression[1][regression[1].index('--jobs') + 1], '6')

    def test_release_gate_includes_restart_real_peers_and_full_presentation(self):
        args, events = self.pipeline(['--verify-release', '--audio-driver', 'PulseAudio'])
        from tools import package_lifecycle_acceptance
        with patch.object(package_lifecycle_acceptance, 'accept', return_value={'package_sha256': 'fixture'}) as lifecycle:
            delivery.deliver(args)
        lifecycle.assert_called_once()
        self.assertEqual([row['name'] for row in args._acceptance['phases']],
                         ['preflight', 'tools_and_dependencies', 'build', 'regression', 'assets',
                          'deploy', 'native_suite', 'multiplayer', 'package', 'install_lifecycle'])
        self.assertTrue(all(row['status'] == 'completed' and row['elapsed_seconds'] >= 0
                            for row in args._acceptance['phases']))
        self.assertEqual(lifecycle.call_args.args[:2], (Path('/built/result.zip'), Path('/game path')))
        self.assertEqual([event[0] for event in events][-6:],
                         ['pck', 'install', 'deploy', 'suite', 'multiplayer', 'zip'])
        native = next(event[1] for event in events if event[0] == 'suite')
        self.assertIn('--verify-restart', native)
        self.assertEqual(native[native.index('--timeout') + 1], '600')
        self.assertEqual(native[native.index('--frames') + 1], '216000')
        self.assertGreater(int(native[native.index('--frames') + 1]), 600 * 240)
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
