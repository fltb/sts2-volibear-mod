import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import unittest.mock as mock

SPEC = importlib.util.spec_from_file_location('dev', Path(__file__).resolve().parents[1] / 'tools/dev.py')
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


class EnvironmentContractTests(unittest.TestCase):
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
        self.assertFalse(manifest['has_pck'])


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
