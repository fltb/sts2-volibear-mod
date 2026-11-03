"""Focused cache evidence tests: no Godot/game launch or approved asset writes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import asset_pack_cache as cache, build_assets


class PackCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'build'
        self.work.mkdir()
        self.output = self.root / 'Volibear.pck'
        self.output.write_bytes(b'pack')
        self.source = self.root / 'source'
        self.source.write_bytes(b'input')
        self.markers = build_assets.validation_markers('open')
        for label, markers in self.markers.items():
            (self.work / (label + '.log')).write_text('\n'.join(markers), encoding='utf-8')
        self.key = cache.fingerprint([self.source], {'tool_version': '1', 'audio_profile': 'open'})

    def publish(self):
        return cache.publish(self.output, self.key, self.markers, self.work, 111.25)

    def lookup(self, key=None):
        return cache.lookup(self.output, key or self.key, self.markers, self.root)

    def test_old_pack_and_logs_are_not_retroactively_accepted(self):
        self.assertIsNone(self.lookup())
        self.assertFalse(cache.receipt_path(self.output).exists())

    def test_complete_evidence_reused_with_original_cold_cost(self):
        self.publish()
        self.assertEqual(self.lookup()['cold_seconds'], 111.25)

    def test_actual_pack_digest_not_size_or_timestamp(self):
        self.publish()
        stamp = self.output.stat()
        self.output.write_bytes(b'fake')
        os.utime(self.output, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertIsNone(self.lookup())

    def test_each_validation_receipt_required_and_content_checked(self):
        for label in self.markers:
            with self.subTest(label=label):
                self.publish()
                path = self.work / (label + '.log')
                original = path.read_bytes()
                path.write_bytes(original + b'altered')
                self.assertIsNone(self.lookup())
                path.unlink()
                self.assertIsNone(self.lookup())
                path.write_bytes(original)

    def test_missing_sentinel_and_errors_rejected_even_with_updated_log_digest(self):
        for text in ('not a pass', '\n'.join(self.markers['verify']) + '\nERROR: fail'):
            self.publish()
            path = self.work / 'verify.log'
            original = path.read_text()
            path.write_text(text)
            record = json.loads(cache.receipt_path(self.output).read_text())
            record['receipts']['verify']['sha256'] = cache.digest(path)
            cache.receipt_path(self.output).write_text(json.dumps(record))
            self.assertIsNone(self.lookup())
            with self.assertRaises(ValueError):
                self.publish()
            path.write_text(original)

    def test_malformed_stale_and_incomplete_record_fail_closed(self):
        for value in ('{', 'null', '[]', '{}', '{"schema": 0}'):
            cache.receipt_path(self.output).write_text(value)
            self.assertIsNone(self.lookup())
        for field in ('schema', 'input_digest', 'pack_sha256', 'receipts', 'cold_seconds'):
            record = self.publish()
            del record[field]
            cache.receipt_path(self.output).write_text(json.dumps(record))
            self.assertIsNone(self.lookup())

    def test_input_tool_and_profile_changes_invalidate(self):
        self.publish()
        for identity in ({'tool_version': '2', 'audio_profile': 'open'},
                         {'tool_version': '1', 'audio_profile': 'riot_en'}):
            self.assertIsNone(self.lookup(cache.fingerprint([self.source], identity)))
        stamp = self.source.stat()
        self.source.write_bytes(b'other')
        os.utime(self.source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertIsNone(self.lookup(cache.fingerprint([self.source],
                          {'tool_version': '1', 'audio_profile': 'open'})))

    def test_added_removed_input_changes_fingerprint(self):
        extra = self.root / 'optional'
        extra.write_bytes(b'new')
        self.assertNotEqual(cache.fingerprint([self.source], {}),
                            cache.fingerprint([self.source, extra], {}))

    def test_outside_receipt_or_nonzero_exit_rejected(self):
        for change in ('outside', 'exit'):
            record = self.publish()
            if change == 'outside':
                record['receipts']['verify']['path'] = str(self.source)
            else:
                record['receipts']['verify']['returncode'] = 1
            cache.receipt_path(self.output).write_text(json.dumps(record))
            self.assertIsNone(cache.lookup(self.output, self.key, self.markers, self.work))

    def test_all_actual_staged_source_categories_are_fingerprinted(self):
        _, clips, portraits = build_assets.read_inputs()
        ui = build_assets.read_ui_inputs()
        effects, audio = build_assets.read_effect_inputs()
        paths = set(build_assets.pack_input_paths(clips, portraits, ui, effects, audio, 'open'))
        for path in (build_assets.VFX / 'card_vfx_bindings.json',
                     build_assets.AUDIO / 'action_cues.json',
                     build_assets.VFX / 'icons/manifest.json',
                     build_assets.PRESENTATION / 'verify_pack.gd',
                     build_assets.PRESENTATION / 'verify_effects.gd',
                     build_assets.PRESENTATION / 'verify_audio_profile.gd',
                     Path(cache.__file__)):
            self.assertIn(path, paths)
        self.assertTrue(all(path.is_file() for path in paths))
        self.assertGreater(len(paths), 300)
        with mock.patch.object(build_assets.audio_profiles, 'profile_data',
                               return_value={'sources': [{'id': 'voice', 'filename': 'original.ogg'}]}):
            private = set(build_assets.pack_input_paths(clips, portraits, ui, effects, audio, 'riot_en'))
        private_root = build_assets.audio_profiles.WORK
        for path in (private_root / 'originals/original.ogg', private_root / 'prepared/riot_en/voice.ogg',
                     private_root / 'prepared/riot_en/build.json', private_root / 'prepared/riot_en/runtime.json',
                     build_assets.audio_profiles.PROFILES / 'riot_en.json'):
            self.assertIn(path, private)
        self.assertNotEqual(paths, private)


class BuilderReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / '.local/pack.pck'
        self.godot = self.root / 'godot'
        self.godot.write_bytes(b'godot')
        self.dotnet = self.root / 'dotnet'
        self.dotnet.write_bytes(b'dotnet')
        # Tests isolate orchestration; content validation itself is exercised above.
        for name, value in [('ROOT', self.root), ('ANIMATIONS', self.root), ('CARDS', self.root),
                            ('UI', self.root), ('VFX', self.root), ('AUDIO', self.root),
                            ('PRESENTATION', self.root)]:
            patcher = mock.patch.object(build_assets, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, value in [('read_inputs', ({}, [], [])), ('read_ui_inputs', []),
                              ('read_effect_inputs', ([], {'assets': []})), ('sha', 'digest'),
                              ('pack_input_paths', [self.godot])]:
            patcher = mock.patch.object(build_assets, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(build_assets.audio_profiles, 'profile_data', return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hit_returns_same_path_without_staging_export_or_fresh_pass_claim(self):
        with mock.patch.object(build_assets, 'run', side_effect=['4.5.1.stable.mono.test', '9.0.320']) as run, \
                mock.patch.object(cache, 'lookup', return_value={'cold_seconds': 123}) as lookup, \
                mock.patch.object(cache, 'publish') as publish, \
                mock.patch.object(build_assets.toolchain, 'validate_pack_header') as header, \
                mock.patch('builtins.print') as report:
            result = build_assets.build(self.godot, self.output, dotnet=self.dotnet)
        self.assertEqual(result, self.output.resolve())
        self.assertEqual(run.call_count, 2)
        lookup.assert_called_once()
        header.assert_called_once_with(self.output)
        publish.assert_not_called()
        text = ' '.join(str(call) for call in report.call_args_list)
        self.assertIn('RESOURCE BUILD cached', text)
        self.assertIn('original_cold_seconds=123.000', text)

    def test_bad_pack_header_falls_back_to_full_build(self):
        with mock.patch.object(build_assets, 'run', side_effect=[
                '4.5.1.stable.mono.test', '9.0.320', RuntimeError('stage failed')]) as run, \
                mock.patch.object(cache, 'lookup', return_value={'cold_seconds': 123}), \
                mock.patch.object(build_assets.toolchain, 'validate_pack_header', side_effect=ValueError('bad header')), \
                mock.patch.object(cache, 'publish') as publish:
            with self.assertRaisesRegex(RuntimeError, 'stage failed'):
                build_assets.build(self.godot, self.output, dotnet=self.dotnet)
            self.assertEqual(run.call_args.args[2], 'stage')
            publish.assert_not_called()

    def test_cache_miss_or_explicit_cold_reaches_existing_build_and_failure_cannot_publish(self):
        for reuse in (True, False):
            with self.subTest(reuse=reuse), \
                    mock.patch.object(build_assets, 'run', side_effect=[
                        '4.5.1.stable.mono.test', '9.0.320', RuntimeError('stage failed')]) as run, \
                    mock.patch.object(cache, 'lookup', return_value=None) as lookup, \
                    mock.patch.object(cache, 'publish') as publish:
                with self.assertRaisesRegex(RuntimeError, 'stage failed'):
                    build_assets.build(self.godot, self.output, dotnet=self.dotnet, reuse=reuse)
                self.assertEqual(run.call_args.args[2], 'stage')
                self.assertEqual(lookup.call_count, int(reuse))
                publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
