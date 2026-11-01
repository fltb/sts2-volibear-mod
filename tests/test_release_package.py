"""Portable candidate packaging only: no SDK, game, network or deployment needed."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import release_package as release


class ReleasePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dll = self.root / 'Volibear.dll'
        self.pck = self.root / 'Volibear.pck'
        self.manifest = self.root / 'Volibear.json'
        self.archive = self.root / 'BaseLib.3.4.7.zip'
        self.license = self.root / 'LICENSE.txt'
        self.instructions = self.root / 'INSTALL_ZH.md'
        self.output = self.root / 'release/candidate.zip'
        self.dll.write_bytes(b'MZfrozen-mod')
        self.pck.write_bytes(b'GDPCfrozen-pack')
        self.mod = {'id': 'Volibear', 'version': '0.1.0', 'min_game_version': '0.107.1',
                    'has_dll': True, 'has_pck': True,
                    'dependencies': [{'id': 'BaseLib', 'min_version': '3.4.7'}]}
        self.manifest.write_text(json.dumps(self.mod), encoding='utf-8')
        base = dict(self.mod, id='BaseLib', version='v3.4.7', dependencies=[])
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, payload in {'BaseLib.dll': b'MZdependency', 'BaseLib.pck': b'GDPCdependency',
                                  'BaseLib.json': json.dumps(base).encode()}.items():
                z.writestr(name, payload)
        self.license.write_bytes(b'MIT License\nfixture notice\n')
        self.instructions.write_text('# Candidate\n0.107.1 / 59260271; BaseLib 3.4.7\n', encoding='utf-8')
        for target, value in (('tools.release_package.dependencies.SHA256', release.sha(self.archive.read_bytes())),
                              ('tools.release_package.LICENSE_SHA256', release.sha(self.license.read_bytes()))):
            mocked = patch(target, value); mocked.start(); self.addCleanup(mocked.stop)

    def package(self):
        return release.package(self.dll, self.pck, self.manifest, self.archive, self.license,
                               self.instructions, self.output)

    def test_exact_payload_inventory_and_reproducible_frozen_bytes(self):
        self.package(); first = self.output.read_bytes(); self.package()
        self.assertEqual(first, self.output.read_bytes())
        with zipfile.ZipFile(self.output) as z:
            expected = {'mods/Volibear/' + name for name in release.MOD_FILES}
            expected.update({'mods/BaseLib/' + name for name in release.dependencies.FILES})
            expected.update({'licenses/BaseLib-LICENSE.txt', 'INSTALL_ZH.md', 'PACKAGE.json',
                             'LICENSE', 'LICENSE-ASSETS', 'LICENSING.md',
                             'licenses/audio/CREDITS.md', 'licenses/audio/sources.json',
                             'licenses/audio/source/kenney/License.txt'})
            self.assertEqual(z.read('LICENSE'), (release.ROOT / 'LICENSE').read_bytes())
            self.assertEqual(z.read('LICENSE-ASSETS'), (release.ROOT / 'LICENSE-ASSETS').read_bytes())
            sources = json.loads(z.read('licenses/audio/sources.json'))
            self.assertEqual({row['license'] for row in sources['recordings']}, {'CC0-1.0'})
            self.assertEqual(set(z.namelist()), expected)
            self.assertEqual(z.read('mods/Volibear/Volibear.dll'), self.dll.read_bytes())
            self.assertEqual(z.read('mods/Volibear/Volibear.pck'), self.pck.read_bytes())
            self.assertEqual(z.read('mods/Volibear/Volibear.json'), self.manifest.read_bytes())
            record = json.loads(z.read('PACKAGE.json'))
            self.assertEqual(record['game_build'], '59260271')
            self.assertEqual(record['status'], 'packaged-build')
            self.assertNotIn('accepted', record)
            self.assertNotIn(str(self.root), z.read('PACKAGE.json').decode())
            for name, digest in record['files'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)

    def test_missing_artifact_fails_without_output(self):
        self.dll.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): self.package()
        self.assertFalse(self.output.parent.exists())

    def test_private_profile_keeps_rights_notices_and_metadata_in_ignored_output(self):
        original_root = release.ROOT
        for relative in ('assets/animation/audio/official/CREDITS.md',
                         'assets/animation/audio/profiles/riot_en.json'):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((original_root / relative).read_bytes())
        output = self.root / '.local/release/riot_en-private.zip'
        with patch.object(release, 'ROOT', self.root):
            release.package(self.dll, self.pck, self.manifest, self.archive, self.license,
                            self.instructions, output, audio_profile='riot_en')
        with zipfile.ZipFile(output) as z:
            record = json.loads(z.read('PACKAGE.json'))
            self.assertEqual(record['audio_profile'], 'riot_en')
            self.assertIs(record['private_audio'], True)
            self.assertIn('licenses/audio/RIOT_AUDIO_CREDITS.md', z.namelist())
            self.assertIn('licenses/audio/riot_en.json', z.namelist())
            self.assertIn(b'not GPL/CC licensed', z.read('AUDIO_PROFILE.txt'))

    def test_private_profile_refuses_output_outside_ignored_directory(self):
        with self.assertRaisesRegex(ValueError, 'ignored .local'):
            release.package(self.dll, self.pck, self.manifest, self.archive, self.license,
                            self.instructions, self.output, audio_profile='riot_en')
        self.assertFalse(self.output.exists())

    def test_manifest_identity_game_flags_and_dependency_pin_fail(self):
        for field, value in [('id', 'Other'), ('min_game_version', '0.108'), ('has_pck', False),
                             ('version', ''), ('dependencies', [{'id': 'BaseLib', 'min_version': '3.4.8'}])]:
            with self.subTest(field=field):
                self.manifest.write_text(json.dumps(dict(self.mod, **{field: value})), encoding='utf-8')
                with self.assertRaises(ValueError): self.package()
                self.assertFalse(self.output.exists())

    def test_game_dll_input_and_development_manifest_switches_fail(self):
        game = self.root / 'sts2.dll'; game.write_bytes(b'MZgame')
        with self.assertRaisesRegex(ValueError, 'filename mismatch'):
            release.package(game, self.pck, self.manifest, self.archive, self.license, self.instructions, self.output)
        self.manifest.write_text(json.dumps(dict(self.mod, probe_enabled=True)), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'development configuration'): self.package()
        self.assertFalse(self.output.exists())

    def test_dependency_digest_or_version_pin_fail(self):
        with patch.object(release.dependencies, 'SHA256', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'pin'): self.package()
        with patch.object(release.dependencies, 'VERSION', '3.4.8'):
            with self.assertRaisesRegex(ValueError, 'pin'): self.package()

    def test_extra_game_dll_or_traversal_in_dependency_rejected_even_with_matching_digest(self):
        for name in ('sts2.dll', '../BaseLib.dll'):
            with self.subTest(name=name):
                with zipfile.ZipFile(self.archive, 'a') as z: z.writestr(name, b'forbidden')
                with patch.object(release.dependencies, 'SHA256', release.sha(self.archive.read_bytes())):
                    with self.assertRaisesRegex(ValueError, 'Unexpected'): self.package()
        self.assertFalse(self.output.exists())

    def test_dependency_manifest_version_mismatch(self):
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr('BaseLib.dll', b'MZdependency'); z.writestr('BaseLib.pck', b'GDPCdependency')
            z.writestr('BaseLib.json', json.dumps(dict(self.mod, id='BaseLib', version='v3.4.8')))
        with patch.object(release.dependencies, 'SHA256', release.sha(self.archive.read_bytes())):
            with self.assertRaisesRegex(ValueError, 'pin'): self.package()

    def test_license_pin_failure(self):
        self.license.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'license pin'): self.package()

    def test_clean_checkout_contains_the_exact_dependency_license(self):
        license_bytes = (release.ROOT / 'licenses/BaseLib-LICENSE.txt').read_bytes()
        # Upstream v3.4.7 bytes, independent of this test's mocked fixture hash.
        self.assertEqual(hashlib.sha256(license_bytes).hexdigest(),
                         '1847e0e0698142ed4347c1441a9fa81c8fbddd44b1d8bbcd5e3647f991759d7f')

    def test_text_metadata_is_portable_but_binary_provenance_is_preserved(self):
        # A historical PDB/source-hash string is not evidence of a runtime file dependency.
        original = b'MZ\0' + 'C:\\Users\\operator\\mod.pdb'.encode('utf-16le')
        self.dll.write_bytes(original); self.package()
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('mods/Volibear/Volibear.dll'), original)
        for path in ('C:\\Users\\operator\\settings.json', '/home/operator/settings.json'):
            with self.subTest(path=path):
                self.manifest.write_text(json.dumps(dict(self.mod, description=path)), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Absolute local path'): self.package()
        release.reject_local_paths(b'https://github.com/Alchyr/BaseLib-StS2\nres://assets/card.png\nevent:/sfx/ui/test', 'urls')

    def test_wrong_binary_headers_fail(self):
        self.pck.write_bytes(b'not a pack')
        with self.assertRaisesRegex(ValueError, 'PCK header'): self.package()

    def test_unknown_existing_archive_is_not_overwritten(self):
        self.output.parent.mkdir(); self.output.write_bytes(b'user file')
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'): self.package()
        self.assertEqual(self.output.read_bytes(), b'user file')

    def test_modified_owned_archive_is_not_overwritten(self):
        self.package()
        with zipfile.ZipFile(self.output) as z: entries = {name: z.read(name) for name in z.namelist()}
        entries['mods/Volibear/Volibear.dll'] = b'MZuser change'
        with zipfile.ZipFile(self.output, 'w') as z:
            for name, data in entries.items(): z.writestr(name, data)
        changed = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'): self.package()
        self.assertEqual(changed, self.output.read_bytes())

    def test_owned_candidate_can_be_regenerated_from_new_frozen_input(self):
        self.package(); self.dll.write_bytes(b'MZnext-frozen-build'); self.package()
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('mods/Volibear/Volibear.dll'), b'MZnext-frozen-build')

    def test_shipping_instructions_require_safe_manual_install_and_uninstall(self):
        text = (release.ROOT / 'docs/INSTALL_ZH.md').read_text(encoding='utf-8')
        for required in ('59260271', '3.4.7', '停止', 'SHA-256', '不删除或修改 BaseLib', '存档',
                         'NOT_RUN', 'PCK 通过不代表这些结果已通过', '原生房间检查点'):
            self.assertIn(required, text)
        self.assertNotIn(str(Path.home()), text)


if __name__ == '__main__':
    unittest.main()
