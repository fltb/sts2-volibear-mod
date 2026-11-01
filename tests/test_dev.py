import importlib.util
import json
import io
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
import unittest.mock as mock

SPEC = importlib.util.spec_from_file_location('dev', Path(__file__).resolve().parents[1] / 'tools/dev.py')
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


class EnvironmentContractTests(unittest.TestCase):
    def test_doctor_accepts_official_dependency_utf8_bom_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            dependency = game / 'mods/BaseLib'
            dependency.mkdir(parents=True)
            metadata = dependency / 'BaseLib.json'
            payload = b'\xef\xbb\xbf' + json.dumps({'id': 'BaseLib', 'version': 'v3.4.7', 'has_pck': True}).encode('utf-8')
            metadata.write_bytes(payload)
            output = io.StringIO()
            with redirect_stdout(output):
                dev.doctor_resources(game, {})
            self.assertIn('BaseLib installed manifest: v3.4.7', output.getvalue())
            self.assertEqual(metadata.read_bytes(), payload)

    def test_assets_symlink_is_not_a_known_junction(self):
        target = dev.ROOT / '.local/fixture-game/mods/Volibear'
        record = {'target': str(target.resolve()), 'files': {'Volibear.dll': 'hash'}}
        with mock.patch.object(dev.os.path, 'lexists', return_value=True), \
                mock.patch.object(dev, 'is_junction', return_value=False), \
                mock.patch.object(dev.os, 'rmdir') as remove:
            with self.assertRaisesRegex(RuntimeError, 'Unowned assets'):
                dev.unlink_assets(target, record)
            remove.assert_not_called()

    def test_assets_junction_revalidates_target_before_removal(self):
        target = dev.ROOT / '.local/fixture-game/mods/Volibear'
        with mock.patch.object(dev, 'validate_assets_junction',
                               side_effect=RuntimeError('target changed')) as validate, \
                mock.patch.object(dev.os, 'rmdir') as remove:
            with self.assertRaisesRegex(RuntimeError, 'target changed'):
                dev.unlink_assets(target, {'target': str(target)})
            validate.assert_called_once()
            remove.assert_not_called()

    def test_version_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'release_info.json').write_text(json.dumps({'version': 'v0.108.0', 'commit': '59260271'}))
            with self.assertRaisesRegex(RuntimeError, 'version mismatch'):
                dev.validate_game(root)

    def test_missing_game_reference_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'release_info.json').write_text(json.dumps({'version': 'v0.107.1', 'commit': '59260271'}))
            with self.assertRaisesRegex(RuntimeError, 'Missing game assembly'):
                dev.validate_game(root)

    def test_missing_executable_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'release_info.json').write_text(json.dumps({'version': 'v0.107.1', 'commit': '59260271'}))
            data = dev.data_directory(root)
            data.mkdir(parents=True)
            for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
                (data / name).write_bytes(b'')
            with self.assertRaisesRegex(RuntimeError, 'Missing game executable'):
                dev.validate_game(root)

    def test_unowned_mod_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            target = game / 'mods/Volibear'
            target.mkdir(parents=True)
            original = target / 'Volibear.dll'
            original.write_bytes(b'not ours')
            with self.assertRaisesRegex(RuntimeError, 'unowned'):
                dev.deploy(game)
            self.assertEqual(original.read_bytes(), b'not ours')

    def test_manifest_matches_probe(self):
        manifest = json.loads((dev.ROOT / 'src/Volibear/Volibear.json').read_text())
        self.assertEqual(manifest['id'], 'Volibear')
        self.assertEqual(manifest['min_game_version'], '0.107.1')
        self.assertTrue(manifest['has_dll'])
        self.assertTrue(manifest['has_pck'])


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        built = self.root / 'build'
        built.mkdir()
        (built / 'Volibear.dll').write_bytes(b'built dll')
        (built / 'Volibear.json').write_text('{"id": "Volibear"}')
        self.sources = [built / 'Volibear.dll', built / 'Volibear.json']
        self.game = self.root / 'game'
        (self.game / 'mods').mkdir(parents=True)
        markers = mock.patch.object(dev, 'DEPLOY_MARKERS', self.root / 'markers')
        markers.start()
        self.addCleanup(markers.stop)
        root_patch = mock.patch.object(dev, 'ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        (self.root / 'assets').mkdir()
        (self.root / 'assets/keep.txt').write_text('source assets must survive')

    def require_pack(self):
        self.sources[1].write_text(json.dumps({'id': 'Volibear', 'has_pck': True}))

    def test_declared_missing_pack_fails_before_writes(self):
        self.require_pack()
        with self.assertRaisesRegex(RuntimeError, 'has_pck.*missing'):
            dev.deploy(self.game, self.sources)
        self.assertFalse((self.game / 'mods/Volibear').exists())
        self.assertFalse(dev.ownership_marker().exists())

    def test_production_missing_pack_rejects_even_stale_staged_pack(self):
        self.require_pack()
        stale = self.root / '.local/deploy/Volibear.pck'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'stale pack')
        with mock.patch.object(dev, 'SOURCES', self.sources):
            with self.assertRaisesRegex(RuntimeError, 'has_pck.*missing'):
                dev.deploy(self.game)
        self.assertFalse((self.game / 'mods/Volibear').exists())
        self.assertEqual(stale.read_bytes(), b'stale pack')

    def test_production_pack_is_owned_without_junction(self):
        self.require_pack()
        pack = self.root / '.local/packs/Volibear.pck'
        pack.parent.mkdir(parents=True)
        pack.write_bytes(b'packed assets')
        with mock.patch.object(dev, 'SOURCES', self.sources):
            dev.deploy(self.game)
        target = self.game / 'mods/Volibear'
        self.assertEqual(sorted(p.name for p in target.iterdir()),
                         ['Volibear.dll', 'Volibear.json', 'Volibear.pck'])
        self.assertEqual((target / 'Volibear.pck').read_bytes(), b'packed assets')
        self.assertIn('Volibear.pck', json.loads(dev.ownership_marker().read_text())['files'])
        dev.undeploy(self.game)
        self.assertFalse(target.exists())
        self.assertEqual(pack.read_bytes(), b'packed assets')

    def test_unowned_assets_directory_preserved_on_deploy_and_undeploy(self):
        dev.deploy(self.game, self.sources)
        target = self.game / 'mods/Volibear'
        assets = target / 'assets'
        assets.mkdir()
        (assets / 'foreign.txt').write_text('keep')
        for operation in (lambda: dev.deploy(self.game, self.sources),
                          lambda: dev.undeploy(self.game)):
            with self.assertRaisesRegex(RuntimeError, 'Unowned assets'):
                operation()
            self.assertEqual((assets / 'foreign.txt').read_text(), 'keep')
            self.assertTrue((target / 'Volibear.dll').exists())
            self.assertTrue(dev.ownership_marker().exists())

    def make_junction(self, link, destination):
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(destination)], check=True)
        self.assertTrue(dev.is_junction(link))
        def cleanup():
            if dev.is_junction(link):
                self.assertEqual(link.resolve(), destination.resolve())
                os.rmdir(link)
        self.addCleanup(cleanup)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction migration')
    def test_known_owned_junction_removed_without_touching_assets(self):
        for operation in ('deploy', 'undeploy'):
            with self.subTest(operation=operation):
                dev.deploy(self.game, self.sources)
                target = self.game / 'mods/Volibear'
                self.make_junction(target / 'assets', self.root / 'assets')
                if operation == 'deploy':
                    dev.deploy(self.game, self.sources)
                else:
                    dev.undeploy(self.game)
                self.assertFalse(os.path.lexists(target / 'assets'))
                self.assertEqual((self.root / 'assets/keep.txt').read_text(),
                                 'source assets must survive')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction migration')
    def test_foreign_junction_refused_without_mutation(self):
        dev.deploy(self.game, self.sources)
        target = self.game / 'mods/Volibear'
        foreign = self.root / 'foreign'
        foreign.mkdir()
        (foreign / 'keep.txt').write_text('foreign assets')
        self.make_junction(target / 'assets', foreign)
        for operation in (lambda: dev.deploy(self.game, self.sources),
                          lambda: dev.undeploy(self.game)):
            with self.assertRaisesRegex(RuntimeError, 'Unowned assets'):
                operation()
            self.assertTrue(dev.is_junction(target / 'assets'))
            self.assertEqual((foreign / 'keep.txt').read_text(), 'foreign assets')
            self.assertTrue((target / 'Volibear.dll').is_file())

    @unittest.skipUnless(os.name == 'nt', 'Windows junction migration')
    def test_matching_junction_without_ownership_is_not_removed(self):
        target = self.game / 'mods/Volibear'
        target.mkdir()
        self.make_junction(target / 'assets', self.root / 'assets')
        with self.assertRaisesRegex(RuntimeError, 'unowned'):
            dev.deploy(self.game, self.sources)
        with self.assertRaisesRegex(RuntimeError, 'No owned deployment'):
            dev.undeploy(self.game)
        self.assertTrue(dev.is_junction(target / 'assets'))

    def test_undeploy_rejects_path_traversal_record(self):
        dev.deploy(self.game, self.sources)
        victim = self.game / 'mods/victim.txt'
        victim.write_text('not owned')
        record = json.loads(dev.ownership_marker().read_text())
        record['files']['../victim.txt'] = dev.digest(victim)
        dev.ownership_marker().write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError, 'Unexpected owned file name'):
            dev.undeploy(self.game)
        self.assertEqual(victim.read_text(), 'not owned')
        self.assertTrue((self.game / 'mods/Volibear/Volibear.dll').exists())

    def test_doctor_reports_observations_not_compatibility(self):
        manifest = self.root / 'src/Volibear/Volibear.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"has_pck": true}')
        output = io.StringIO()
        with redirect_stdout(output):
            dev.doctor_resources(self.game, {})
        report = output.getvalue()
        self.assertIn('PCK: MISSING (required)', report)
        self.assertIn('BaseLib installed manifest: MISSING', report)
        self.assertIn('required 4.5.1', report)
        self.assertIn('not verified by file presence', report)
        self.assertNotIn('RitsuLib', report)
        dependency = self.game / 'mods/BaseLib'
        dependency.mkdir()
        (dependency / 'BaseLib.json').write_text('{"id":"BaseLib","version":"3.4.7","has_pck":true}')
        (dependency / 'BaseLib.dll').write_bytes(b'dll')
        output = io.StringIO()
        with redirect_stdout(output):
            dev.doctor_resources(self.game, {'godot': str(self.root / 'missing.exe')})
        self.assertIn('BaseLib installed manifest: 3.4.7', output.getvalue())
        self.assertIn('BaseLib PCK: MISSING', output.getvalue())
        self.assertIn('configured executable MISSING', output.getvalue())

    def test_mod_directory_holds_only_deployable_files(self):
        dev.deploy(self.game, self.sources)
        target = self.game / 'mods' / 'Volibear'
        self.assertEqual(sorted(p.name for p in target.iterdir()),
                         ['Volibear.dll', 'Volibear.json'])
        dev.deploy(self.game, self.sources)
        self.assertEqual((target / 'Volibear.dll').read_bytes(), b'built dll')

    def test_tampered_deployment_is_refused(self):
        dev.deploy(self.game, self.sources)
        (self.game / 'mods/Volibear/Volibear.dll').write_bytes(b'edited by hand')
        with self.assertRaisesRegex(RuntimeError, 'Previously deployed file changed'):
            dev.deploy(self.game, self.sources)

    def test_marker_from_old_internal_layout_is_migrated(self):
        target = self.game / 'mods' / 'Volibear'
        target.mkdir(parents=True)
        for src in self.sources:
            (target / src.name).write_bytes(src.read_bytes())
        hashes = {p.name: dev.digest(p) for p in self.sources}
        (target / '.volibear-dev-owned.json').write_text(json.dumps(hashes))
        dev.deploy(self.game, self.sources)
        self.assertFalse((target / '.volibear-dev-owned.json').exists())
        self.assertTrue(dev.ownership_marker().is_file())

    def test_undeploy_removes_only_owned_files(self):
        dev.deploy(self.game, self.sources)
        target = self.game / 'mods' / 'Volibear'
        foreign = target / 'player-notes.txt'
        foreign.write_text('keep me')
        dev.undeploy(self.game)
        self.assertEqual([p.name for p in target.iterdir()], ['player-notes.txt'])
        self.assertFalse(dev.ownership_marker().is_file())
        with self.assertRaisesRegex(RuntimeError, 'No owned deployment'):
            dev.undeploy(self.game)
