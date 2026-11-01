"""Pinned release and ownership contracts; no network or real game installation."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import dev

SPEC = importlib.util.spec_from_file_location('dependencies_under_test', TOOLS / 'dependencies.py')
dependencies = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dependencies)


class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / '.local/dependencies/BaseLib-3.4.7'
        self.archive = self.root / '.local/dependencies/BaseLib.3.4.7.zip'
        self.game = self.root / 'game'
        self.game.mkdir()
        (self.game / 'release_info.json').write_text(json.dumps({
            'version': 'v0.107.1', 'commit': '59260271'}), encoding='utf-8')
        data = dev.data_directory(self.game)
        data.mkdir()
        for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
            (data / name).write_bytes(b'fixture reference, not a real assembly')
        dev.game_executable(self.game).write_bytes(b'fixture executable, never launched')
        self.target = self.game / 'mods/BaseLib'
        self.marker = self.root / '.local/deploy/BaseLib.json'
        self.selected = {
            'BaseLib.dll': b'fixture dll', 'BaseLib.pck': b'fixture pack',
            'BaseLib.json': json.dumps({'id': 'BaseLib', 'version': 'v3.4.7',
                                       'has_dll': True, 'has_pck': True}).encode('utf-8'),
        }
        for patcher in (mock.patch.object(dependencies, 'ROOT', self.root),
                        mock.patch.object(dependencies, 'CACHE', self.cache),
                        mock.patch.object(dev, 'config', return_value={'game_dir': str(self.game)})):
            patcher.start()
            self.addCleanup(patcher.stop)
        network = mock.patch.object(dependencies.urllib.request, 'urlopen',
                                    side_effect=AssertionError('Real network forbidden in dependency tests'))
        self.network = network.start()
        self.addCleanup(network.stop)

    def archive_bytes(self, entries=None):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name, content in (entries if entries is not None else self.selected.items()):
                archive.writestr(name, content)
        return output.getvalue()

    def cached_archive(self, entries=None):
        payload = self.archive_bytes(entries)
        self.archive.parent.mkdir(parents=True, exist_ok=True)
        self.archive.write_bytes(payload)
        patcher = mock.patch.object(dependencies, 'SHA256', dependencies.digest(payload))
        patcher.start()
        self.addCleanup(patcher.stop)
        return payload

    def make_redirect(self, link, destination):
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(destination)], check=True)
        else:
            link.symlink_to(destination, target_is_directory=True)
        self.assertEqual(link.resolve(), destination.resolve())
        def cleanup():
            if os.path.lexists(link):
                self.assertEqual(link.resolve(), destination.resolve())
                if os.name == 'nt':
                    self.assertTrue(os.path.isjunction(link))
                    os.rmdir(link)
                else:
                    self.assertTrue(link.is_symlink())
                    link.unlink()
        self.addCleanup(cleanup)

    def test_cached_archive_hash_mismatch_refused_without_network(self):
        self.archive.parent.mkdir(parents=True)
        self.archive.write_bytes(b'not the pinned release')
        with self.assertRaisesRegex(RuntimeError, 'pinned release'):
            dependencies.acquire()
        self.network.assert_not_called()
        self.assertFalse(self.cache.exists())

    def test_download_hash_mismatch_not_cached(self):
        with mock.patch.object(dependencies.urllib.request, 'urlopen',
                               return_value=io.BytesIO(b'wrong release')) as download:
            with self.assertRaisesRegex(RuntimeError, 'pinned release'):
                dependencies.acquire()
        download.assert_called_once_with(dependencies.URL, timeout=60)
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.cache.exists())

    def test_valid_nested_archive_extracts_only_required_payloads(self):
        entries = [('release/' + name, content) for name, content in self.selected.items()]
        entries += [('../../unrelated.txt', b'must never be extracted')]
        self.cached_archive(entries)
        self.assertEqual(dependencies.acquire(), self.selected)
        self.assertEqual(sorted(p.name for p in self.cache.iterdir()), sorted(self.selected))
        self.assertFalse((self.root / 'unrelated.txt').exists())
        for name, payload in self.selected.items():
            self.assertEqual((self.cache / name).read_bytes(), payload)
        self.assertEqual(dependencies.acquire(), self.selected)
        self.network.assert_not_called()

    def test_missing_archive_payload_rejected(self):
        for missing in self.selected:
            with self.subTest(missing=missing):
                self.cached_archive([(name, payload) for name, payload in self.selected.items()
                                     if name != missing])
                with self.assertRaisesRegex(RuntimeError, 'Expected exactly one'):
                    dependencies.acquire()
                self.assertFalse(self.cache.exists())

    def test_ambiguous_archive_payload_rejected(self):
        self.cached_archive([*self.selected.items(), ('nested/BaseLib.dll', b'ambiguous')])
        with self.assertRaisesRegex(RuntimeError, 'Expected exactly one BaseLib.dll'):
            dependencies.acquire()
        self.assertFalse(self.cache.exists())

    def test_invalid_manifest_identity_and_version_rejected(self):
        for field, value in [('id', 'OtherMod'), ('version', 'v3.4.8'), ('version', '3.4.7')]:
            with self.subTest(field=field, value=value):
                selected = dict(self.selected)
                manifest = json.loads(selected['BaseLib.json'])
                manifest[field] = value
                selected['BaseLib.json'] = json.dumps(manifest).encode('utf-8')
                self.cached_archive(selected.items())
                with self.assertRaisesRegex(RuntimeError, 'Unexpected dependency manifest'):
                    dependencies.acquire()
                self.assertFalse(self.cache.exists())

    def test_cache_collision_preflight_preserves_all_entries(self):
        self.cached_archive()
        self.cache.mkdir()
        # The last payload differs: no earlier missing payload may be created before refusal.
        changed = self.cache / 'BaseLib.json'
        changed.write_bytes(b'locally edited cache')
        with self.assertRaises(RuntimeError):
            dependencies.acquire()
        self.assertEqual([p.name for p in self.cache.iterdir()], ['BaseLib.json'])
        self.assertEqual(changed.read_bytes(), b'locally edited cache')

    def test_redirected_cache_directory_refused_without_target_writes(self):
        self.cached_archive()
        foreign = self.root / 'foreign-cache'
        foreign.mkdir()
        self.make_redirect(self.cache, foreign)
        with self.assertRaises(RuntimeError):
            dependencies.acquire()
        self.assertEqual(list(foreign.iterdir()), [])

    def test_cache_file_redirect_refused_even_when_bytes_match(self):
        self.cached_archive()
        self.cache.mkdir()
        redirected = self.cache / 'BaseLib.dll'
        redirected.write_bytes(self.selected['BaseLib.dll'])
        original = Path.is_symlink
        # Emulate the file-symlink bit without requiring Windows symlink privileges.
        with mock.patch.object(Path, 'is_symlink', autospec=True,
                               side_effect=lambda path: path == redirected or original(path)):
            with self.assertRaises(RuntimeError):
                dependencies.acquire()
        self.assertEqual(redirected.read_bytes(), self.selected['BaseLib.dll'])
        self.assertFalse((self.cache / 'BaseLib.pck').exists())

    def test_new_install_records_exact_owned_hashes_and_preserves_foreign_files(self):
        self.target.mkdir(parents=True)
        notes = self.target / 'notes.txt'
        notes.write_text('not ours')
        dependencies.install(self.selected)
        record = json.loads(self.marker.read_text(encoding='utf-8'))
        self.assertEqual(record['target'], str(self.target))
        self.assertEqual(record['version'], '3.4.7')
        self.assertEqual(record['files'], {name: dependencies.digest(data)
                                           for name, data in self.selected.items()})
        self.assertEqual(notes.read_text(), 'not ours')
        dependencies.install(self.selected)
        self.assertEqual(json.loads(self.marker.read_text(encoding='utf-8')), record)

    def test_identical_unowned_install_reused_without_claim(self):
        self.target.mkdir(parents=True)
        for name, payload in self.selected.items():
            (self.target / name).write_bytes(payload)
        dependencies.install(self.selected)
        self.assertEqual(json.loads(self.marker.read_text(encoding='utf-8'))['files'], {})

    def test_mixed_install_claims_only_new_files(self):
        self.target.mkdir(parents=True)
        (self.target / 'BaseLib.dll').write_bytes(self.selected['BaseLib.dll'])
        dependencies.install(self.selected)
        owned = json.loads(self.marker.read_text(encoding='utf-8'))['files']
        self.assertEqual(set(owned), {'BaseLib.json', 'BaseLib.pck'})

    def test_changed_unowned_payload_refused_before_any_write(self):
        self.target.mkdir(parents=True)
        (self.target / 'BaseLib.json').write_bytes(b'foreign manifest')
        with self.assertRaisesRegex(RuntimeError, 'unowned or changed'):
            dependencies.install(self.selected)
        self.assertFalse(self.marker.exists())
        self.assertEqual([p.name for p in self.target.iterdir()], ['BaseLib.json'])
        self.assertEqual((self.target / 'BaseLib.json').read_bytes(), b'foreign manifest')

    def test_changed_owned_payload_refused_and_marker_preserved(self):
        dependencies.install(self.selected)
        marker_before = self.marker.read_bytes()
        (self.target / 'BaseLib.pck').write_bytes(b'hand edited')
        with self.assertRaisesRegex(RuntimeError, 'unowned or changed'):
            dependencies.install(self.selected)
        self.assertEqual(self.marker.read_bytes(), marker_before)
        self.assertEqual((self.target / 'BaseLib.pck').read_bytes(), b'hand edited')

    def test_ownership_marker_for_another_game_refused(self):
        self.marker.parent.mkdir(parents=True)
        original = json.dumps({'target': str(self.root / 'other-game'), 'files': {}}).encode()
        self.marker.write_bytes(original)
        with self.assertRaisesRegex(RuntimeError, 'another installation'):
            dependencies.install(self.selected)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.marker.read_bytes(), original)

    def test_redirected_install_directory_refused(self):
        foreign = self.root / 'foreign-mod'
        foreign.mkdir()
        self.make_redirect(self.target, foreign)
        with self.assertRaisesRegex(RuntimeError, 'redirected'):
            dependencies.install(self.selected)
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertFalse(self.marker.exists())

    def test_redirected_install_file_refused_even_when_bytes_match(self):
        self.target.mkdir(parents=True)
        redirected = self.target / 'BaseLib.dll'
        redirected.write_bytes(self.selected['BaseLib.dll'])
        original = Path.is_symlink
        with mock.patch.object(Path, 'is_symlink', autospec=True,
                               side_effect=lambda path: path == redirected or original(path)):
            with self.assertRaisesRegex(RuntimeError, 'redirected file'):
                dependencies.install(self.selected)
        self.assertFalse(self.marker.exists())
        self.assertEqual([p.name for p in self.target.iterdir()], ['BaseLib.dll'])

    def test_game_version_guard_runs_before_install(self):
        (self.game / 'release_info.json').write_text(json.dumps({
            'version': 'v0.108.0', 'commit': '59260271'}), encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'version mismatch'):
            dependencies.install(self.selected)
        self.assertFalse(self.target.exists())
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
