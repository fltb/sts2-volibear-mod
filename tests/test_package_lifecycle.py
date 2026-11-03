"""Real-file lifecycle tests for final-package validation and install/update/uninstall.

Every archive, game copy, ownership record and sentinel here is a real file on
disk. Fault-injection tests patch only filesystem commit boundaries; normal paths
exercise the same code used on a genuine final ZIP and an isolated game copy.
"""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import package_lifecycle as lifecycle
from tools import release_package
from tools.runtime_platform import create_directory_redirect


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_zip(path, payload, *, compression=zipfile.ZIP_DEFLATED):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=compression) as archive:
        for name in sorted(payload):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload[name])


def read_entries(path):
    with zipfile.ZipFile(path) as archive:
        return [(archive.getinfo(name), archive.read(name)) for name in archive.namelist()]


def write_entries(path, entries):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for info, data in entries:
            archive.writestr(info, data)


class PackageLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / 'lifecycle-state.json'
        self.game = self.root / 'game'
        self.sentinel = self.game / 'saves' / 'profile.json'
        self._make_game()

    def _make_game(self):
        self.game.mkdir(parents=True)
        (self.game / 'release_info.json').write_text(json.dumps({
            'commit': '59260271', 'version': 'v0.107.1',
            'date': '2026-06-18T15:43:56-07:00', 'branch': 'v0.107.1',
        }), encoding='utf-8')
        for directory in ('data_sts2_linuxbsd_x86_64', 'data_sts2_windows_x86_64'):
            data = self.game / directory
            data.mkdir()
            for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
                (data / name).write_bytes(b'game ' + name.encode())
        (self.game / 'SlayTheSpire2').write_bytes(b'game executable')
        (self.game / 'SlayTheSpire2.exe').write_bytes(b'game executable')
        mods = self.game / 'mods'
        mods.mkdir()
        other = mods / 'OtherMod'
        other.mkdir()
        (other / 'OtherMod.dll').write_bytes(b'foreign mod')
        (other / 'settings.json').write_text('{"keep": true}\n', encoding='utf-8')
        saves = self.game / 'saves'
        saves.mkdir()
        self.sentinel.write_text('{"save": "sentinel"}\n', encoding='utf-8')
        self.foreign_before = {
            path.relative_to(mods).as_posix(): path.read_bytes()
            for path in other.rglob('*') if path.is_file()
        }

    def build_package(self, name='v1.zip', *, version='0.1.0', dll=b'MZvolibear-v1',
                      pck=b'GDPCvolibear-v1', base_dll=b'MZbaselib',
                      base_pck=b'GDPCbaselib', json_version=None):
        version = json_version or version
        mod = {
            'id': 'Volibear', 'name': 'Volibear', 'author': 'fltb',
            'description': 'fixture', 'version': version,
            'min_game_version': '0.107.1', 'has_dll': True, 'has_pck': True,
            'dependencies': [{'id': 'BaseLib', 'min_version': '3.4.7'}],
            'affects_gameplay': True,
        }
        base = {'id': 'BaseLib', 'name': 'BaseLib', 'version': 'v3.4.7'}
        payload = {
            'mods/Volibear/Volibear.dll': dll,
            'mods/Volibear/Volibear.pck': pck,
            'mods/Volibear/Volibear.json': json.dumps(mod).encode('utf-8'),
            'mods/BaseLib/BaseLib.dll': base_dll,
            'mods/BaseLib/BaseLib.pck': base_pck,
            'mods/BaseLib/BaseLib.json': json.dumps(base).encode('utf-8'),
            'INSTALL_ZH.md': '# Install\n0.107.1 / 59260271; BaseLib 3.4.7\n'.encode('utf-8'),
            'LICENSE': b'fixture license\n',
            'LICENSE-ASSETS': b'fixture asset license\n',
            'LICENSING.md': b'fixture licensing\n',
            'licenses/BaseLib-LICENSE.txt': b'MIT License\nfixture\n',
            'licenses/audio/CREDITS.md': b'fixture credits\n',
            'licenses/audio/sources.json': b'{"recordings": []}\n',
            'licenses/audio/source/kenney/License.txt': b'CC0 fixture\n',
        }
        record = {
            'producer': lifecycle.PRODUCER,
            'status': 'packaged-build',
            'mod_version': version,
            'game_version': '0.107.1',
            'game_build': '59260271',
            'audio_profile': 'open',
            'private_audio': False,
            'dependency': {
                'id': 'BaseLib', 'version': '3.4.7',
                'archive_sha256': lifecycle.BASELIB_SHA256,
                'official_url': lifecycle.BASELIB_URL,
            },
            'files': {key: sha(value) for key, value in payload.items()},
        }
        payload['PACKAGE.json'] = (json.dumps(record, indent=2) + '\n').encode('utf-8')
        path = self.root / name
        write_zip(path, payload)
        return path, payload

    def base_payload(self, payload):
        return {name: payload[name] for name in
                ('mods/BaseLib/BaseLib.dll', 'mods/BaseLib/BaseLib.pck',
                 'mods/BaseLib/BaseLib.json')}

    def add_matching_baselib(self, payload):
        target = self.game / 'mods' / 'BaseLib'
        target.mkdir()
        for name, data in self.base_payload(payload).items():
            (target / Path(name).name).write_bytes(data)
        (target / 'notes.txt').write_text('reused dependency\n', encoding='utf-8')
        return target

    def run_lifecycle(self, package, **kwargs):
        kwargs.setdefault('state_path', self.state)
        kwargs.setdefault('save_sentinels', [self.sentinel])
        return lifecycle.run(package, self.game, **kwargs)

    def execute(self, package, **kwargs):
        kwargs['execute'] = True
        return self.run_lifecycle(package, **kwargs)

    def target(self):
        return self.game / 'mods' / 'Volibear'

    def assert_foreign_and_sentinel_unchanged(self):
        mods = self.game / 'mods'
        current = {
            path.relative_to(mods).as_posix(): path.read_bytes()
            for path in (mods / 'OtherMod').rglob('*') if path.is_file()
        }
        self.assertEqual(current, self.foreign_before)
        self.assertEqual(self.sentinel.read_text(encoding='utf-8'), '{"save": "sentinel"}\n')

    def snapshot_bytes(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_update_second_replace_failure_restores_exact_old_install(self):
        package, _ = self.build_package()
        self.execute(package)
        # Preserve noncanonical state formatting byte-for-byte on rollback.
        self.state.write_text(json.dumps(json.loads(self.state.read_text()), indent=4))
        newer, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZnew dll', pck=b'GDPCnew pck')
        before = self.snapshot_bytes()
        real = os.replace
        failed = False

        def replace(source, destination):
            nonlocal failed
            if Path(destination) == self.target() / 'Volibear.pck' and not failed:
                failed = True
                raise OSError('injected second replacement failure')
            return real(source, destination)

        with patch.object(lifecycle.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'second replacement'):
                self.execute(newer)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot_bytes(), before)
        self.assert_foreign_and_sentinel_unchanged()
        self.execute(newer)
        self.assertEqual((self.target() / 'Volibear.dll').read_bytes(), b'MZnew dll')
        self.assertEqual(json.loads(self.state.read_text())['package']['mod_version'], '0.2.0')

    def test_state_commit_failure_restores_old_files_and_state(self):
        package, _ = self.build_package()
        self.execute(package)
        newer, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZnew dll')
        before = self.snapshot_bytes()
        real = os.replace

        def replace(source, destination):
            if Path(destination) == self.state:
                raise OSError('injected state commit failure')
            return real(source, destination)

        with patch.object(lifecycle.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'state commit failure'):
                self.execute(newer)
        self.assertEqual(self.snapshot_bytes(), before)

    def test_exception_after_state_commit_restores_raw_state(self):
        package, _ = self.build_package()
        self.execute(package)
        self.state.write_text(json.dumps(json.loads(self.state.read_text()), indent=3))
        newer, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZnew dll')
        before = self.snapshot_bytes()
        real = lifecycle.write_state

        def write(path, state):
            real(path, state)
            raise OSError('after state commit')

        with patch.object(lifecycle, 'write_state', side_effect=write):
            with self.assertRaisesRegex(OSError, 'after state commit'):
                self.execute(newer)
        self.assertEqual(self.snapshot_bytes(), before)

    def test_actual_rollback_write_failure_retains_all_original_backups(self):
        package, _ = self.build_package()
        self.execute(package)
        old = {n: (self.target() / n).read_bytes() for n in lifecycle.MOD_FILES}
        newer, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZnew dll', pck=b'GDPCnew pck')
        real = lifecycle._copy_verified
        calls = 0

        def copy(source, destination, expected):
            nonlocal calls
            calls += 1
            if calls >= 2:
                raise OSError('persistent disk failure')
            real(source, destination, expected)

        with patch.object(lifecycle, '_copy_verified', side_effect=copy):
            with self.assertRaisesRegex(lifecycle.LifecycleError, 'rollback incomplete'):
                self.execute(newer)
        recovery, = self.root.glob('volibear-recovery-*')
        rows = json.loads((recovery / 'RECOVERY.json').read_text())['files']
        for row in rows:
            name = Path(row['path']).name
            if name in old:
                self.assertEqual((recovery / row['backup']).read_bytes(), old[name])
        self.assert_foreign_and_sentinel_unchanged()

    def test_new_install_rollback_preserves_external_baselib_edit(self):
        package, _ = self.build_package()

        def fail(path, state):
            (self.game / 'mods/BaseLib/BaseLib.dll').write_bytes(b'external dependency')
            (self.target() / 'foreign.txt').write_bytes(b'foreign data')
            raise OSError('state failure')

        with patch.object(lifecycle, 'write_state', side_effect=fail):
            with self.assertRaisesRegex(lifecycle.LifecycleError, 'rollback incomplete'):
                self.execute(package)
        self.assertEqual((self.game / 'mods/BaseLib/BaseLib.dll').read_bytes(), b'external dependency')
        self.assertEqual((self.target() / 'foreign.txt').read_bytes(), b'foreign data')
        self.assertFalse((self.target() / 'Volibear.dll').exists())
        self.assert_foreign_and_sentinel_unchanged()

    def test_new_install_and_baselib_removed_after_state_failure(self):
        package, _ = self.build_package()
        before = self.snapshot_bytes()
        with patch.object(lifecycle, 'write_state', side_effect=OSError('state failure')):
            with self.assertRaisesRegex(OSError, 'state failure'):
                self.execute(package)
        self.assertEqual(self.snapshot_bytes(), before)
        self.assertFalse(self.target().exists())
        self.assertFalse((self.game / 'mods/BaseLib').exists())

    def test_new_baselib_copy_failure_leaves_no_owned_install(self):
        package, _ = self.build_package()
        before = self.snapshot_bytes()
        real = lifecycle._copy_verified

        def copy(source, destination, expected):
            if Path(destination).name == 'BaseLib.pck':
                raise OSError('BaseLib copy failure')
            real(source, destination, expected)

        with patch.object(lifecycle, '_copy_verified', side_effect=copy):
            with self.assertRaisesRegex(OSError, 'BaseLib copy failure'):
                self.execute(package)
        self.assertEqual(self.snapshot_bytes(), before)
        self.assertFalse((self.game / 'mods/BaseLib').exists())

    def test_rollback_conflict_keeps_external_bytes_and_recovery_backup(self):
        package, _ = self.build_package()
        self.execute(package)
        old_state = self.state.read_bytes()
        old_dll = (self.target() / 'Volibear.dll').read_bytes()
        newer, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZnew dll')

        def fail(path, state):
            (self.target() / 'Volibear.dll').write_bytes(b'external edit')
            raise OSError('state failure')

        with patch.object(lifecycle, 'write_state', side_effect=fail):
            with self.assertRaisesRegex(lifecycle.LifecycleError, 'rollback incomplete.*Recovery backup retained'):
                self.execute(newer)
        self.assertEqual((self.target() / 'Volibear.dll').read_bytes(), b'external edit')
        recovery, = self.root.glob('volibear-recovery-*')
        record = json.loads((recovery / 'RECOVERY.json').read_text())
        row = next(r for r in record['files'] if Path(r['path']).name == 'Volibear.dll')
        self.assertEqual((recovery / row['backup']).read_bytes(), old_dll)
        self.assertEqual(self.state.read_bytes(), old_state)
        self.assert_foreign_and_sentinel_unchanged()

    def test_state_sentinel_overlap_rejected_before_uninstall(self):
        package, _ = self.build_package()
        self.execute(package)
        with tempfile.TemporaryDirectory() as aliases:
            for alias in ('equal', 'parent-redirect', 'hardlink'):
                with self.subTest(alias=alias):
                    sentinel = self.state
                    if alias == 'parent-redirect':
                        parent = create_directory_redirect(Path(aliases) / 'state-alias', self.root)
                        sentinel = parent / self.state.name
                    elif alias == 'hardlink':
                        sentinel = self.root / 'sentinel-hardlink'
                        os.link(self.state, sentinel)
                    self.assertTrue(sentinel.samefile(self.state))
                    before = self.snapshot_bytes()
                    with self.assertRaisesRegex(lifecycle.LifecycleError, 'overlaps protected input'):
                        self.execute(package, action='uninstall', save_sentinels=[sentinel])
                    self.assertEqual(self.snapshot_bytes(), before)

    def test_state_archive_overlap_rejected_before_changes(self):
        package, _ = self.build_package()
        previous, _ = self.build_package('previous.zip')
        with tempfile.TemporaryDirectory() as aliases:
            for archive in (package, previous):
                for alias in ('equal', 'hardlink', 'parent-redirect'):
                    with self.subTest(archive=archive.name, alias=alias):
                        state = archive
                        if alias == 'hardlink':
                            state = self.root / (archive.name + '-state')
                            os.link(archive, state)
                        elif alias == 'parent-redirect':
                            parent = create_directory_redirect(Path(aliases) / (archive.name + '-alias'), self.root)
                            state = parent / archive.name
                        self.assertTrue(state.samefile(archive))
                        before = self.snapshot_bytes()
                        with self.assertRaisesRegex(lifecycle.LifecycleError, 'overlaps protected input'):
                            self.execute(package, state_path=state, previous_package=previous)
                        self.assertEqual(self.snapshot_bytes(), before)

    def test_apply_rechecks_new_state_sentinel_alias(self):
        package, _ = self.build_package()
        self.execute(package)
        plan = lifecycle.plan_uninstall(lifecycle.load_package(package), self.game,
                                        self.state, sentinels=[self.sentinel])
        plan.sentinels_before[str(self.state)] = sha(self.state.read_bytes())
        before = self.snapshot_bytes()
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'overlaps protected input'):
            lifecycle.apply_plan(plan)
        self.assertEqual(self.snapshot_bytes(), before)

    def test_real_package_producer_output_round_trips(self):
        # Use the repository's actual pinned BaseLib archive and license so this
        # is the real release producer, not a second hand-written schema.
        base_archive = release_package.ROOT / '.local/dependencies/BaseLib.3.4.7.zip'
        base_license = release_package.ROOT / 'licenses/BaseLib-LICENSE.txt'
        if not base_archive.is_file() or not base_license.is_file():
            self.skipTest('pinned BaseLib archive/license not present in this checkout')
        artifacts = self.root / 'producer-artifacts'
        artifacts.mkdir()
        dll = artifacts / 'Volibear.dll'
        pck = artifacts / 'Volibear.pck'
        manifest = artifacts / 'Volibear.json'
        dll.write_bytes(b'MZproducer')
        pck.write_bytes(b'GDPCproducer')
        manifest.write_text(json.dumps({
            'id': 'Volibear', 'name': 'Volibear', 'author': 'fltb',
            'description': 'producer fixture', 'version': '0.1.0',
            'min_game_version': '0.107.1', 'has_dll': True, 'has_pck': True,
            'dependencies': [{'id': 'BaseLib', 'min_version': '3.4.7'}],
            'affects_gameplay': True,
        }), encoding='utf-8')
        final = self.root / 'producer.zip'
        release_package.package(dll, pck, manifest, base_archive, base_license,
                                release_package.ROOT / 'docs/INSTALL_ZH.md', final)
        package = lifecycle.load_package(final)
        self.assertEqual(package.record['producer'], release_package.PRODUCER)
        self.assertEqual(package.digest('mods/Volibear/Volibear.dll'), sha(b'MZproducer'))
        result = self.execute(final)
        self.assertTrue(result['applied'])
        self.assertEqual((self.target() / 'Volibear.pck').read_bytes(), b'GDPCproducer')
        self.run_lifecycle(final, action='uninstall', execute=True)
        self.assertFalse(self.target().exists())
        self.assert_foreign_and_sentinel_unchanged()

    def test_valid_package_extracts_with_exact_inventory(self):
        path, payload = self.build_package()
        package = lifecycle.load_package(path)
        self.assertEqual(package.mod_version, '0.1.0')
        self.assertEqual(set(package.files), set(payload) - {'PACKAGE.json'})
        for name, data in payload.items():
            if name != 'PACKAGE.json':
                self.assertEqual(package.files[name], sha(data))
        staging = self.root / 'staging'
        lifecycle.extract_package(package, staging)
        self.assertEqual({item.relative_to(staging).as_posix() for item in staging.rglob('*') if item.is_file()},
                         set(payload))
        for name, data in payload.items():
            self.assertEqual((staging / name).read_bytes(), data)
        self.assertEqual(json.loads((staging / 'PACKAGE.json').read_text())['producer'], lifecycle.PRODUCER)

    def test_package_validation_rejects_tamper_and_unsafe_paths(self):
        good, payload = self.build_package()
        entries = read_entries(good)

        changed = [list(item) for item in entries]
        for row in changed:
            if row[0].filename == 'mods/Volibear/Volibear.dll':
                row[1] = b'MZtampered'
        path = self.root / 'changed.zip'
        write_entries(path, [(info, data) for info, data in changed])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'hash mismatch'):
            lifecycle.load_package(path)

        for name, extra in (('extra.zip', 'mods/Other/Other.dll'),
                            ('traversal.zip', '../escape.dll'),
                            ('absolute.zip', '/tmp/escape.dll'),
                            ('backslash.zip', 'mods\\escape.dll'),
                            ('colon.zip', 'mods/Volibear/C:/escape.dll'),
                            ('reserved.zip', 'mods/Volibear/CON'),
                            ('trailing-dot.zip', 'mods/Volibear/name.')):
            path = self.root / name
            info = zipfile.ZipInfo(extra, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            write_entries(path, entries + [(info, b'escape')])
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.load_package(path)

        duplicate = self.root / 'duplicate.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            write_entries(duplicate, entries + [entries[0]])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'Duplicate'):
            lifecycle.load_package(duplicate)

        symlink = self.root / 'symlink.zip'
        link = zipfile.ZipInfo('mods/Volibear/link', (1980, 1, 1, 0, 0, 0))
        link.external_attr = (0o120777 << 16)
        write_entries(symlink, entries + [(link, b'ignored')])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'Symbolic link'):
            lifecycle.load_package(symlink)

    def test_package_validation_rejects_bad_record_and_manifests(self):
        good, payload = self.build_package()
        entries = read_entries(good)

        def record_variant(name, **changes):
            rows = [list(item) for item in entries]
            for row in rows:
                if row[0].filename == 'PACKAGE.json':
                    record = json.loads(row[1])
                    record.update(changes)
                    row[1] = json.dumps(record).encode()
            path = self.root / name
            write_entries(path, [(info, data) for info, data in rows])
            return path

        for name, field, value in (
                ('producer.zip', 'producer', 'someone-else'),
                ('status.zip', 'status', 'draft'),
                ('build.zip', 'game_build', '1'),
                ('version.zip', 'game_version', '0.108.0'),
                ('audio.zip', 'audio_profile', 'unknown')):
            with self.subTest(field=field):
                with self.assertRaises(lifecycle.LifecycleError):
                    lifecycle.load_package(record_variant(name, **{field: value}))

        missing_hash = record_variant('missing-hash.zip')
        rows = [list(item) for item in read_entries(missing_hash)]
        for row in rows:
            if row[0].filename == 'PACKAGE.json':
                record = json.loads(row[1])
                record['files']['mods/Volibear/Volibear.dll'] = '0' * 64
                row[1] = json.dumps(record).encode()
        write_entries(missing_hash, [(info, data) for info, data in rows])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'hash mismatch'):
            lifecycle.load_package(missing_hash)

        manifest = self.build_package('manifest.zip')[0]
        rows = [list(item) for item in read_entries(manifest)]
        changed_manifest = None
        for row in rows:
            if row[0].filename == 'mods/Volibear/Volibear.json':
                mod = json.loads(row[1])
                mod['version'] = '9.9.9'
                row[1] = json.dumps(mod).encode()
                changed_manifest = row[1]
            if row[0].filename == 'PACKAGE.json' and changed_manifest is not None:
                record = json.loads(row[1])
                record['files']['mods/Volibear/Volibear.json'] = sha(changed_manifest)
                row[1] = json.dumps(record).encode()
        # The manifest row may appear after PACKAGE.json in sorted order; repair
        # the inventory in a second pass so this case reaches manifest validation.
        for row in rows:
            if row[0].filename == 'PACKAGE.json':
                record = json.loads(row[1])
                record['files']['mods/Volibear/Volibear.json'] = sha(changed_manifest)
                row[1] = json.dumps(record).encode()
        write_entries(manifest, [(info, data) for info, data in rows])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'Volibear.json'):
            lifecycle.load_package(manifest)

        header = self.build_package('header.zip')[0]
        rows = [list(item) for item in read_entries(header)]
        for row in rows:
            if row[0].filename == 'mods/Volibear/Volibear.pck':
                row[1] = b'not a pack'
            if row[0].filename == 'PACKAGE.json':
                record = json.loads(row[1])
                record['files']['mods/Volibear/Volibear.pck'] = sha(b'not a pack')
                row[1] = json.dumps(record).encode()
        write_entries(header, [(info, data) for info, data in rows])
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'header mismatch'):
            lifecycle.load_package(header)

    def test_default_plan_and_cli_are_read_only(self):
        package, _ = self.build_package()
        state_before = self.state.exists()
        result = self.run_lifecycle(package)
        self.assertEqual(result['operation'], 'install')
        self.assertFalse(result['applied'])
        self.assertFalse(self.target().exists())
        self.assertFalse(self.state.exists())
        self.assertEqual(self.state.exists(), state_before)
        self.assert_foreign_and_sentinel_unchanged()

        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = lifecycle.main(['--package', str(package), '--game-dir', str(self.game),
                                   '--state', str(self.state), '--save-sentinel', str(self.sentinel)])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertIn('PLAN (no files changed', output.getvalue())
        self.assertIn('Plan only.', output.getvalue())
        self.assertFalse(self.target().exists())
        self.assertFalse(self.state.exists())
        self.assert_foreign_and_sentinel_unchanged()
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'outside the game'):
            self.run_lifecycle(package, state_path=self.game / 'state.json')

    def test_execute_install_and_repeat_install_is_idempotent(self):
        package, payload = self.build_package()
        result = self.execute(package)
        self.assertTrue(result['applied'])
        self.assertEqual(result['verification'], 'passed')
        self.assertEqual({path.name: path.read_bytes() for path in self.target().iterdir()},
                         {Path(name).name: data for name, data in payload.items()
                          if name.startswith('mods/Volibear/')})
        for name, data in self.base_payload(payload).items():
            self.assertEqual((self.game / 'mods' / 'BaseLib' / Path(name).name).read_bytes(), data)
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['target'], str(self.target()))
        self.assertEqual(state['baselib']['mode'], 'install')
        self.assertEqual(state['files'], {Path(name).name: sha(data) for name, data in payload.items()
                                          if name.startswith('mods/Volibear/')})
        mtimes = {path.name: path.stat().st_mtime_ns for path in self.target().iterdir()}
        base_mtimes = {path.name: path.stat().st_mtime_ns
                       for path in (self.game / 'mods' / 'BaseLib').iterdir()}
        again = self.execute(package)
        self.assertEqual(again['target_mode'], 'installed')
        self.assertEqual({path.name: path.stat().st_mtime_ns for path in self.target().iterdir()}, mtimes)
        self.assertEqual({path.name: path.stat().st_mtime_ns
                          for path in (self.game / 'mods' / 'BaseLib').iterdir()}, base_mtimes)
        self.assert_foreign_and_sentinel_unchanged()

    def test_repeat_update_uses_ownership_hashes_and_preserves_foreign(self):
        v1, payload1 = self.build_package('v1.zip')
        v2, payload2 = self.build_package('v2.zip', version='0.2.0', dll=b'MZvolibear-v2',
                                          pck=b'GDPCvolibear-v2')
        self.execute(v1)
        result = self.execute(v2)
        self.assertEqual(result['operation'], 'update')
        for name, data in payload2.items():
            if name.startswith('mods/Volibear/'):
                self.assertEqual((self.target() / Path(name).name).read_bytes(), data)
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['package']['mod_version'], '0.2.0')
        self.assertEqual(state['files'], {Path(name).name: sha(data) for name, data in payload2.items()
                                          if name.startswith('mods/Volibear/')})
        self.assert_foreign_and_sentinel_unchanged()
        again = self.execute(v2)
        self.assertEqual(again['target_mode'], 'installed')
        self.assertEqual((self.target() / 'Volibear.dll').read_bytes(), b'MZvolibear-v2')

    def test_previous_package_recovers_update_when_state_is_missing(self):
        v1, _ = self.build_package('v1.zip')
        v2, payload2 = self.build_package('v2.zip', version='0.2.0', dll=b'MZvolibear-v2',
                                          pck=b'GDPCvolibear-v2')
        self.execute(v1)
        self.state.unlink()
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'ownership'):
            self.execute(v2)
        self.assertEqual((self.target() / 'Volibear.dll').read_bytes(), b'MZvolibear-v1')
        result = lifecycle.run(v2, self.game, state_path=self.state, previous_package=v1,
                               save_sentinels=[self.sentinel], execute=True)
        self.assertTrue(result['applied'])
        self.assertEqual((self.target() / 'Volibear.dll').read_bytes(), b'MZvolibear-v2')
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['package']['mod_version'], '0.2.0')
        self.assert_foreign_and_sentinel_unchanged()

    def test_tamper_refusal_preserves_installation_and_blocks_uninstall(self):
        v1, _ = self.build_package('v1.zip')
        v2, _ = self.build_package('v2.zip', version='0.2.0', dll=b'MZvolibear-v2',
                                   pck=b'GDPCvolibear-v2')
        self.execute(v1)
        changed = self.target() / 'Volibear.dll'
        changed.write_bytes(b'MZlocal-change')
        before = {path.name: path.read_bytes() for path in self.target().iterdir()}
        state_before = self.state.read_bytes()
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'changed'):
            self.execute(v2)
        self.assertEqual({path.name: path.read_bytes() for path in self.target().iterdir()}, before)
        self.assertEqual(self.state.read_bytes(), state_before)
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'changed'):
            self.run_lifecycle(v1, action='uninstall', execute=True)
        self.assertEqual(changed.read_bytes(), b'MZlocal-change')
        self.assertTrue(self.state.exists())
        self.assert_foreign_and_sentinel_unchanged()

    def test_uninstall_preserves_foreign_target_entry_baselib_and_sentinel(self):
        package, payload = self.build_package()
        self.add_matching_baselib(payload)
        self.execute(package)
        note = self.target() / 'user-note.txt'
        note.write_text('keep me\n', encoding='utf-8')
        baselib_before = {path.relative_to(self.game / 'mods').as_posix(): path.read_bytes()
                          for path in (self.game / 'mods' / 'BaseLib').rglob('*') if path.is_file()}
        result = self.run_lifecycle(package, action='uninstall', execute=True)
        self.assertTrue(result['applied'])
        self.assertFalse((self.target() / 'Volibear.dll').exists())
        self.assertFalse((self.target() / 'Volibear.pck').exists())
        self.assertFalse((self.target() / 'Volibear.json').exists())
        self.assertEqual(note.read_text(encoding='utf-8'), 'keep me\n')
        self.assertTrue(self.target().is_dir())
        self.assertFalse(self.state.exists())
        self.assertEqual({path.relative_to(self.game / 'mods').as_posix(): path.read_bytes()
                          for path in (self.game / 'mods' / 'BaseLib').rglob('*') if path.is_file()},
                         baselib_before)
        self.assert_foreign_and_sentinel_unchanged()
        again = self.run_lifecycle(package, action='uninstall', execute=True)
        self.assertTrue(again['applied'])
        self.assertEqual(note.read_text(encoding='utf-8'), 'keep me\n')

    def test_matching_baselib_is_reused_and_never_removed(self):
        package, payload = self.build_package()
        baselib = self.add_matching_baselib(payload)
        before = {path.relative_to(baselib).as_posix(): path.read_bytes()
                  for path in baselib.rglob('*') if path.is_file()}
        result = self.execute(package)
        self.assertEqual(result['baselib']['mode'], 'reuse')
        self.assertEqual({path.relative_to(baselib).as_posix(): path.read_bytes()
                          for path in baselib.rglob('*') if path.is_file()}, before)
        self.run_lifecycle(package, action='uninstall', execute=True)
        self.assertEqual({path.relative_to(baselib).as_posix(): path.read_bytes()
                          for path in baselib.rglob('*') if path.is_file()}, before)

    def test_conflicting_baselib_is_refused_without_writing(self):
        package, payload = self.build_package()
        baselib = self.game / 'mods' / 'BaseLib'
        baselib.mkdir()
        (baselib / 'BaseLib.dll').write_bytes(b'MZother-version')
        before = {path.name: path.read_bytes() for path in baselib.iterdir()}
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'BaseLib differs'):
            self.execute(package)
        self.assertFalse(self.target().exists())
        self.assertFalse(self.state.exists())
        self.assertEqual({path.name: path.read_bytes() for path in baselib.iterdir()}, before)
        self.assert_foreign_and_sentinel_unchanged()

    def test_unowned_existing_volibear_is_refused(self):
        package, _ = self.build_package()
        target = self.target()
        target.mkdir()
        for name in lifecycle.MOD_FILES:
            (target / name).write_bytes(b'unowned ' + name.encode())
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'ownership'):
            self.execute(package)
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)
        self.assertFalse(self.state.exists())
        self.assert_foreign_and_sentinel_unchanged()

    def test_verify_action_checks_installed_state_and_sentinels(self):
        package, _ = self.build_package()
        self.execute(package)
        result = self.run_lifecycle(package, action='verify')
        self.assertTrue(result['verification']['verified'])
        self.assertEqual(result['verification']['target'], str(self.target()))
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = lifecycle.main(['--package', str(package), '--game-dir', str(self.game),
                                   '--state', str(self.state), '--action', 'verify'])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertIn('VERIFICATION PASSED.', output.getvalue())
        self.sentinel.write_text('{"save": "changed"}\n', encoding='utf-8')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'sentinel'):
            self.run_lifecycle(package, action='verify')
        self.sentinel.write_text('{"save": "sentinel"}\n', encoding='utf-8')
        (self.target() / 'Volibear.dll').write_bytes(b'MZchanged')
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'ownership'):
            self.run_lifecycle(package, action='verify')

    def test_cli_execute_and_uninstall_json(self):
        package, _ = self.build_package()
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = lifecycle.main(['--package', str(package), '--game-dir', str(self.game),
                                   '--state', str(self.state), '--save-sentinel', str(self.sentinel),
                                   '--execute', '--json'])
        self.assertEqual(code, 0, errors.getvalue())
        result = json.loads(output.getvalue())
        self.assertTrue(result['applied'])
        self.assertEqual(result['verification'], 'passed')
        self.assertTrue((self.target() / 'Volibear.dll').exists())
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = lifecycle.main(['--package', str(package), '--game-dir', str(self.game),
                                   '--state', str(self.state), '--save-sentinel', str(self.sentinel),
                                   '--action', 'uninstall', '--execute', '--json'])
        self.assertEqual(code, 0, errors.getvalue())
        result = json.loads(output.getvalue())
        self.assertTrue(result['applied'])
        self.assertFalse(self.target().exists())
        self.assertFalse(self.state.exists())
        self.assert_foreign_and_sentinel_unchanged()

    def test_redirected_target_is_refused_and_outside_is_untouched(self):
        package, _ = self.build_package()
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'keep.txt').write_text('outside\n', encoding='utf-8')
        target = self.target()
        create_directory_redirect(target, outside)
        self.assertEqual(target.resolve(), outside.resolve())
        with self.assertRaisesRegex(lifecycle.LifecycleError, 'Redirected|redirected'):
            self.execute(package)
        self.assertEqual((outside / 'keep.txt').read_text(encoding='utf-8'), 'outside\n')
        self.assertFalse(self.state.exists())


if __name__ == '__main__':
    unittest.main()
