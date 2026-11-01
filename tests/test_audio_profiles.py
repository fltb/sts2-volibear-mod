"""Bounded checks for offline defaults, private-source integrity and package staging."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audio_profiles', ROOT / 'tools/audio_profiles.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class AudioProfileTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.local').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='audio-profile-test-', dir=ROOT / '.local')
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def test_open_is_complete_offline_and_needs_no_private_media(self):
        with patch.object(audio, 'WORK', self.directory), patch.object(audio.urllib.request, 'build_opener') as network:
            result = audio.verify_open(full_decode=False)
            audio.stage_profile('open', self.directory / 'VolibearArt/audio')
            network.assert_not_called()
        self.assertEqual((result['assets'], result['cues'], result['cc0_recordings']), (47, 54, 7))
        runtime = json.loads((self.directory / 'VolibearArt/audio/profiles/runtime.json').read_text())
        self.assertEqual(runtime, {'schema_version': 1, 'profile': 'open', 'overrides': []})
        self.assertFalse((self.directory / 'originals').exists())

    def test_resource_archive_has_exact_switch_uninstall_hashes_and_notices(self):
        pack = self.directory / 'Volibear.pck'
        pack.write_bytes(b'GDPC frozen test pack')
        with patch.object(audio, 'WORK', self.directory):
            result = audio.archive_profile('open', pack)
            first = result.read_bytes()
            audio.archive_profile('open', pack)
            self.assertEqual(first, result.read_bytes())
        with zipfile.ZipFile(result) as archive:
            record = json.loads(archive.read('AUDIO_PACKAGE.json'))
            self.assertEqual(record['profile'], 'open')
            self.assertEqual(record['game_build'], '59260271')
            self.assertEqual(set(record['files']), set(archive.namelist()) - {'AUDIO_PACKAGE.json'})
            self.assertEqual(archive.read('mods/Volibear/Volibear.pck'), pack.read_bytes())
            for name, digest in record['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
            self.assertIn('CC0', archive.read('KENNEY-CC0.txt').decode())
            self.assertEqual(len(json.loads(archive.read('OPEN_AUDIO_SOURCES.json'))['recordings']), 7)
            self.assertNotIn('RIOT_AUDIO_CREDITS.md', archive.namelist())

    def test_pinned_private_sources_keep_english_voice_separate_from_sfx(self):
        data = audio.profile_data('riot_en')
        self.assertEqual(len(data['overrides']), 11)
        by_id = {row['id']: row for row in data['sources']}
        for row in data['overrides']:
            expected = 'voice' if row['cue'].startswith('voice.') else 'sfx'
            self.assertEqual(by_id[row['source']]['kind'], expected)
        self.assertEqual({row['ability'] for row in data['sfx_research']}, {'Q', 'W', 'E', 'R'})
        self.assertEqual({row['ability'] for row in data['sfx_research'] if row['status'] == 'unresolved_exact_media_url'}, {'W', 'E', 'R'})
        self.assertIn('voice.low_health', {row['cue'] for row in data['fallbacks']})

    def test_fetch_reuses_exact_local_bytes_and_protects_changed_original(self):
        raw = b'OggS test fixture'
        row = {'id': 'test', 'filename': 'test.ogg', 'bytes': len(raw),
               'sha256': hashlib.sha256(raw).hexdigest(),
               'download_url': 'https://static.wikia.nocookie.net/test.ogg'}
        source = self.directory / 'originals/test.ogg'
        source.parent.mkdir()
        source.write_bytes(raw)
        with patch.object(audio, 'WORK', self.directory), patch.object(audio, 'profile_data', return_value={'sources': [row]}), patch.object(audio.urllib.request, 'build_opener') as network:
            self.assertEqual(audio.fetch_sources()['downloaded_now'], 0)
            network.return_value.open.assert_not_called()
            source.write_bytes(b'changed local original')
            with self.assertRaisesRegex(ValueError, 'Missing/changed original'):
                audio.fetch_sources()
            network.return_value.open.assert_not_called()
        self.assertEqual(source.read_bytes(), b'changed local original')

    def test_public_fetch_cannot_follow_arbitrary_hosts_or_private_paths(self):
        for url in ('http://static.wikia.nocookie.net/test.ogg', 'https://example.org/test.ogg',
                    'https://user:secret@static.wikia.nocookie.net/test.ogg',
                    'https://cmsassets.rgpub.io:9443/test.mp3'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                audio.source_url(url)
        with self.assertRaisesRegex(ValueError, 'ignored .local'):
            audio.local_path(ROOT / 'assets/animation/audio/new-private.ogg')

    def test_missing_private_media_is_explicit_and_open_rejects_a_dirty_private_stage(self):
        with patch.object(audio, 'WORK', self.directory):
            with self.assertRaisesRegex(ValueError, 'not prepared'):
                audio.stage_profile('riot_en', self.directory / 'VolibearArt/audio')
        (self.directory / 'VolibearArt/audio/profiles/riot_en').mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh stage'):
            audio.stage_profile('open', self.directory / 'VolibearArt/audio')


if __name__ == '__main__':
    unittest.main()
