import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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
