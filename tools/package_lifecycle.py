#!/usr/bin/env python3
"""Verify a final Volibear package and exercise its documented manual lifecycle.

The verifier is deliberately bounded:

* it reads one final ZIP and one existing, isolated game copy;
* it validates PACKAGE.json, every inventory hash, every archive path and the
  mod manifests before doing anything;
* it plans by default and changes files only when --execute is supplied;
* install/update/uninstall use recorded ownership hashes, never a new package
  manifest to claim an older installation;
* BaseLib, foreign sibling mods and save sentinels are preserved;
* it never launches the game, downloads anything, builds anything or touches
  the user's normal game installation.

Typical parent workflow for a genuine final ZIP and an isolated copy of the
game (with any previous Volibear install removed):

    python -B tools/package_lifecycle.py --package FINAL.zip --game-dir GAME_COPY --execute
    # run the game copy with the normal native startup procedure
    python -B tools/package_lifecycle.py --package FINAL.zip --game-dir GAME_COPY --action uninstall --execute

Add --json for a machine-readable plan/result and --save-sentinel PATH for an
isolated save file that must remain byte-identical.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = 'volibear-release-package-v1'
GAME_VERSION = '0.107.1'
GAME_RELEASE = 'v0.107.1'
GAME_BUILD = '59260271'
BASELIB_VERSION = '3.4.7'
BASELIB_SHA256 = 'd28c649a3aea9ef4869050a06bfbadc4863016bcbd4c1740acc4cd07809e4bd8'
BASELIB_URL = f'https://github.com/Alchyr/BaseLib-StS2/releases/download/v{BASELIB_VERSION}/BaseLib.{BASELIB_VERSION}.zip'
MOD_FILES = ('Volibear.dll', 'Volibear.pck', 'Volibear.json')
BASELIB_FILES = ('BaseLib.dll', 'BaseLib.pck', 'BaseLib.json')
VOLIBEAR_PREFIX = 'mods/Volibear/'
BASELIB_PREFIX = 'mods/BaseLib/'
VOLIBEAR_ENTRIES = frozenset(VOLIBEAR_PREFIX + name for name in MOD_FILES)
BASELIB_ENTRIES = frozenset(BASELIB_PREFIX + name for name in BASELIB_FILES)
REQUIRED_ENTRIES = VOLIBEAR_ENTRIES | BASELIB_ENTRIES | {
    'INSTALL_ZH.md',
    'licenses/BaseLib-LICENSE.txt',
}
RECORD_KEYS = frozenset({
    'producer', 'status', 'mod_version', 'game_version', 'game_build',
    'audio_profile', 'private_audio', 'dependency', 'files',
})
DEPENDENCY_KEYS = frozenset({'id', 'version', 'archive_sha256', 'official_url'})
ROOT_DOCUMENTS = frozenset({
    'INSTALL_ZH.md', 'LICENSE', 'LICENSE-ASSETS', 'LICENSING.md', 'AUDIO_PROFILE.txt',
})
STATE_SCHEMA = 1
CHUNK = 1024 * 1024
MAX_ENTRY_SIZE = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_SIZE = 8 * 1024 * 1024 * 1024
MAX_ENTRIES = 10000


class LifecycleError(ValueError):
    """A package, game copy or ownership record is unsafe or inconsistent."""


def _is_junction(path: Path) -> bool:
    return hasattr(os.path, 'isjunction') and os.path.isjunction(path)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(CHUNK), b''):
        digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or _is_junction(path):
        raise LifecycleError(f'Refusing redirected {label}: {path}')
    if not path.is_file():
        raise LifecycleError(f'Missing {label}: {path}')


def _plain_directory(path: Path, label: str) -> None:
    if path.is_symlink() or _is_junction(path):
        raise LifecycleError(f'Refusing redirected {label}: {path}')
    if not path.is_dir():
        raise LifecycleError(f'Missing {label}: {path}')
    if path.resolve() != path.absolute():
        raise LifecycleError(f'Refusing redirected {label}: {path}')


def _safe_relative(name: str) -> None:
    """Reject archive names that can escape the extraction root."""
    if not isinstance(name, str) or not name:
        raise LifecycleError('Empty archive path')
    if len(name) > 1024:
        raise LifecycleError('Overlong archive path')
    if '\x00' in name:
        raise LifecycleError('NUL in archive path')
    if '\\' in name:
        raise LifecycleError(f'Backslash in archive path: {name}')
    if name.startswith('/') or re.match(r'^[A-Za-z]:', name):
        raise LifecycleError(f'Absolute archive path: {name}')
    if name.endswith('/'):
        raise LifecycleError(f'Directory entry is not allowed: {name}')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3',
                'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    parts = name.split('/')
    for part in parts:
        if part in ('', '.', '..'):
            raise LifecycleError(f'Unsafe archive path: {name}')
        if part != part.strip() or part.endswith('.'):
            raise LifecycleError(f'Unsafe archive path: {name}')
        if any(ord(character) < 32 for character in part):
            raise LifecycleError(f'Control character in archive path: {name}')
        if any(character in part for character in ':*?"<>|'):
            raise LifecycleError(f'Unsafe archive path: {name}')
        if part.split('.')[0].upper() in reserved:
            raise LifecycleError(f'Reserved archive path: {name}')
    if PurePosixPath(name).is_absolute():
        raise LifecycleError(f'Absolute archive path: {name}')


def _validate_record(record: object, archive_names: set[str]) -> dict:
    if not isinstance(record, dict) or set(record) != RECORD_KEYS:
        raise LifecycleError('PACKAGE.json must contain exactly the release record fields')
    if record['producer'] != PRODUCER or record['status'] != 'packaged-build':
        raise LifecycleError('PACKAGE.json producer/status mismatch')
    if record['game_version'] != GAME_VERSION or record['game_build'] != GAME_BUILD:
        raise LifecycleError('PACKAGE.json game version/build mismatch')
    if not isinstance(record['mod_version'], str) or not record['mod_version'].strip():
        raise LifecycleError('PACKAGE.json mod_version is empty')
    if record['audio_profile'] not in ('open', 'riot_en'):
        raise LifecycleError('PACKAGE.json audio_profile is invalid')
    if not isinstance(record['private_audio'], bool):
        raise LifecycleError('PACKAGE.json private_audio must be a boolean')
    if record['private_audio'] != (record['audio_profile'] == 'riot_en'):
        raise LifecycleError('PACKAGE.json audio profile/private flag mismatch')
    dependency = record['dependency']
    if not isinstance(dependency, dict) or set(dependency) != DEPENDENCY_KEYS:
        raise LifecycleError('PACKAGE.json dependency record is invalid')
    if (dependency['id'], dependency['version']) != ('BaseLib', BASELIB_VERSION):
        raise LifecycleError('PACKAGE.json dependency pin mismatch')
    if dependency['archive_sha256'] != BASELIB_SHA256:
        raise LifecycleError('PACKAGE.json dependency archive hash mismatch')
    if dependency['official_url'] != BASELIB_URL:
        raise LifecycleError('PACKAGE.json dependency URL mismatch')
    files = record['files']
    if not isinstance(files, dict) or not files:
        raise LifecycleError('PACKAGE.json files inventory is empty')
    payload_names = archive_names - {'PACKAGE.json'}
    if set(files) != payload_names:
        raise LifecycleError('PACKAGE.json inventory does not exactly match archive entries')
    for name, digest in files.items():
        _safe_relative(name)
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise LifecycleError(f'Invalid SHA-256 inventory value: {name}')
    missing = REQUIRED_ENTRIES - payload_names
    if missing:
        raise LifecycleError('Package is missing required entries: ' + ', '.join(sorted(missing)))
    for name in payload_names:
        if name.startswith('mods/'):
            if name not in REQUIRED_ENTRIES:
                raise LifecycleError(f'Unexpected file under mods/: {name}')
            continue
        if name.startswith('licenses/'):
            continue
        if name not in ROOT_DOCUMENTS:
            raise LifecycleError(f'Unexpected package root entry: {name}')
    if record['audio_profile'] == 'riot_en' and 'AUDIO_PROFILE.txt' not in payload_names:
        raise LifecycleError('Riot audio package is missing AUDIO_PROFILE.txt')
    return record


def _json_object(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as error:
        raise LifecycleError(f'Invalid JSON in {label}') from error
    if not isinstance(value, dict):
        raise LifecycleError(f'{label} must contain an object')
    return value


@dataclass(frozen=True)
class PackageArchive:
    path: Path
    sha256: str
    record: Mapping[str, object]
    files: Mapping[str, str]
    sizes: Mapping[str, int]

    @property
    def mod_version(self) -> str:
        return str(self.record['mod_version'])

    @property
    def audio_profile(self) -> str:
        return str(self.record['audio_profile'])

    def digest(self, name: str) -> str:
        try:
            return self.files[name]
        except KeyError as error:
            raise LifecycleError(f'Package has no inventory entry: {name}') from error


def load_package(package_path: Path | str) -> PackageArchive:
    """Validate one final ZIP strictly; never extract or write anything."""
    path = Path(package_path).expanduser()
    if not path.is_file():
        raise LifecycleError(f'Package archive not found: {path}')
    path = path.resolve()
    archive_digest = _sha_file(path)
    try:
        import zipfile
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos:
                raise LifecycleError('Package archive is empty')
            if len(infos) > MAX_ENTRIES:
                raise LifecycleError('Package archive has too many entries')
            names: set[str] = set()
            casefold_names: set[str] = set()
            total = 0
            for info in infos:
                name = info.filename
                _safe_relative(name)
                folded = name.casefold()
                if name in names:
                    raise LifecycleError(f'Duplicate archive entry: {name}')
                if folded in casefold_names:
                    raise LifecycleError(f'Case-colliding archive entry: {name}')
                names.add(name)
                casefold_names.add(folded)
                if info.is_dir():
                    raise LifecycleError(f'Directory entry is not allowed: {name}')
                if info.flag_bits & 0x1:
                    raise LifecycleError(f'Encrypted archive entry is not allowed: {name}')
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise LifecycleError(f'Symbolic link archive entry is not allowed: {name}')
                if stat.S_IFMT(mode) and not stat.S_ISREG(mode):
                    raise LifecycleError(f'Non-regular archive entry is not allowed: {name}')
                if info.file_size < 0 or info.file_size > MAX_ENTRY_SIZE:
                    raise LifecycleError(f'Archive entry is too large: {name}')
                total += info.file_size
                if total > MAX_ARCHIVE_SIZE:
                    raise LifecycleError('Package archive is too large')
            if 'PACKAGE.json' not in names:
                raise LifecycleError('Package archive is missing PACKAGE.json')
            package_info = archive.getinfo('PACKAGE.json')
            if package_info.file_size > 1024 * 1024:
                raise LifecycleError('PACKAGE.json is unexpectedly large')
            record = _json_object(archive.read('PACKAGE.json'), 'PACKAGE.json')
            record = _validate_record(record, names)
            hashes: dict[str, str] = {}
            sizes: dict[str, int] = {}
            for info in infos:
                name = info.filename
                with archive.open(info) as stream:
                    digest = _sha_stream(stream)
                if name == 'PACKAGE.json':
                    continue
                if digest != record['files'][name]:
                    raise LifecycleError(f'Package payload hash mismatch: {name}')
                hashes[name] = digest
                sizes[name] = info.file_size
            mod_manifest = _json_object(archive.read(VOLIBEAR_PREFIX + 'Volibear.json'),
                                        'Volibear.json')
            expected_dependencies = [{'id': 'BaseLib', 'min_version': BASELIB_VERSION}]
            if (mod_manifest.get('id') != 'Volibear'
                    or mod_manifest.get('version') != record['mod_version']
                    or mod_manifest.get('min_game_version') != GAME_VERSION
                    or mod_manifest.get('has_dll') is not True
                    or mod_manifest.get('has_pck') is not True
                    or mod_manifest.get('dependencies') != expected_dependencies):
                raise LifecycleError('Volibear.json identity/version/dependency mismatch')
            baselib_manifest = _json_object(archive.read(BASELIB_PREFIX + 'BaseLib.json'),
                                            'BaseLib.json')
            if (baselib_manifest.get('id') != 'BaseLib'
                    or baselib_manifest.get('version') != 'v' + BASELIB_VERSION):
                raise LifecycleError('BaseLib.json identity/version mismatch')
            for name, header in ((VOLIBEAR_PREFIX + 'Volibear.dll', b'MZ'),
                                 (BASELIB_PREFIX + 'BaseLib.dll', b'MZ'),
                                 (VOLIBEAR_PREFIX + 'Volibear.pck', b'GDPC'),
                                 (BASELIB_PREFIX + 'BaseLib.pck', b'GDPC')):
                with archive.open(name) as stream:
                    if stream.read(len(header)) != header:
                        raise LifecycleError(f'Binary header mismatch: {name}')
    except LifecycleError:
        raise
    except Exception as error:  # zipfile.BadZipFile, CRC errors, OS errors
        raise LifecycleError(f'Invalid package archive: {path.name}') from error
    return PackageArchive(path=path, sha256=archive_digest, record=record,
                          files=hashes, sizes=sizes)


def extract_package(package: PackageArchive, destination: Path | str) -> Path:
    """Extract a validated package into a fresh directory, rechecking every hash."""
    import zipfile
    destination = Path(destination)
    if destination.is_symlink() or _is_junction(destination):
        raise LifecycleError(f'Refusing redirected extraction destination: {destination}')
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise LifecycleError(f'Extraction destination must be empty: {destination}')
    else:
        destination.mkdir(parents=True)
    root = destination.resolve()
    expected = set(package.files) | {'PACKAGE.json'}
    try:
        with zipfile.ZipFile(package.path) as archive:
            for info in archive.infolist():
                name = info.filename
                _safe_relative(name)
                target = destination.joinpath(*PurePosixPath(name).parts)
                if not target.parent.exists():
                    target.parent.mkdir(parents=True)
                if target.parent.resolve() != root and not target.parent.resolve().is_relative_to(root):
                    raise LifecycleError(f'Extraction path escaped staging root: {name}')
                if target.exists() or target.is_symlink():
                    raise LifecycleError(f'Refusing to overwrite extraction target: {name}')
                digest = hashlib.sha256()
                with archive.open(info) as source, target.open('xb') as stream:
                    for chunk in iter(lambda: source.read(CHUNK), b''):
                        digest.update(chunk)
                        stream.write(chunk)
                if name != 'PACKAGE.json' and digest.hexdigest() != package.files[name]:
                    target.unlink()
                    raise LifecycleError(f'Extracted payload hash mismatch: {name}')
        actual = {path.relative_to(destination).as_posix()
                  for path in destination.rglob('*') if path.is_file()}
        if actual != expected:
            raise LifecycleError('Extracted package inventory does not match PACKAGE.json')
    except LifecycleError:
        raise
    except Exception as error:
        raise LifecycleError(f'Could not extract package: {error}') from error
    return destination


def validate_game(game_dir: Path | str) -> Path:
    """Require a complete, pinned, unredirected game copy without writing to it."""
    game = Path(game_dir).expanduser()
    if not game.exists():
        raise LifecycleError(f'Game copy not found: {game}')
    _plain_directory(game, 'game copy')
    game = game.resolve()
    release = game / 'release_info.json'
    _regular_file(release, 'release_info.json')
    info = _json_object(release.read_bytes(), 'release_info.json')
    if (info.get('version'), info.get('commit')) != (GAME_RELEASE, GAME_BUILD):
        raise LifecycleError('Game copy version/build is not 0.107.1 / 59260271')
    if os.name == 'nt':
        data = game / 'data_sts2_windows_x86_64'
        executable = game / 'SlayTheSpire2.exe'
    elif os.name == 'posix':
        data = game / 'data_sts2_linuxbsd_x86_64'
        executable = game / 'SlayTheSpire2'
    else:
        raise LifecycleError('Unsupported platform for the pinned game copy')
    _plain_directory(data, 'game data directory')
    for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'):
        _regular_file(data / name, 'game assembly ' + name)
    _regular_file(executable, 'game executable')
    mods = game / 'mods'
    if os.path.lexists(mods):
        _plain_directory(mods, 'mods directory')
    return game


def _snapshot_tree(path: Path, base: Path) -> dict[str, tuple]:
    rows: dict[str, tuple] = {}

    def visit(current: Path) -> None:
        relative = current.relative_to(base).as_posix()
        if current.is_symlink():
            rows[relative] = ('link', os.readlink(current))
            return
        if _is_junction(current):
            rows[relative] = ('junction', str(current.resolve()))
            return
        if current.is_dir():
            rows[relative] = ('dir', None)
            for child in sorted(current.iterdir(), key=lambda entry: entry.name):
                visit(child)
            return
        if current.is_file():
            rows[relative] = ('file', _sha_file(current))
            return
        rows[relative] = ('other', None)

    visit(path)
    return rows


def _snapshot_mods_foreign(game: Path) -> dict[str, tuple]:
    mods = game / 'mods'
    rows: dict[str, tuple] = {}
    if not os.path.lexists(mods):
        return rows
    if mods.is_symlink() or _is_junction(mods) or not mods.is_dir():
        raise LifecycleError(f'Refusing redirected mods directory: {mods}')
    for child in sorted(mods.iterdir(), key=lambda entry: entry.name):
        if child.name in ('Volibear', 'BaseLib'):
            continue
        rows.update(_snapshot_tree(child, mods))
    return rows


def _snapshot_sentinels(paths: Iterable[Path | str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for value in paths:
        path = Path(value).expanduser().resolve()
        _regular_file(path, 'save sentinel')
        rows[str(path)] = _sha_file(path)
    return rows


def _compare_snapshot(label: str, before: Mapping, after: Mapping) -> None:
    if dict(before) == dict(after):
        return
    changed = sorted(set(before) ^ set(after)
                     | {key for key in set(before) & set(after) if before[key] != after[key]})
    raise LifecycleError(f'{label} changed during lifecycle operation: ' + ', '.join(changed[:5]))


def _reject_state_overlap(state: Path, protected: Iterable[Path | str]) -> None:
    """State is mutable metadata, never a sentinel or an input archive alias."""
    for value in protected:
        path = Path(value).expanduser()
        if (state.resolve() == path.resolve()
                or (state.exists() and path.exists() and state.samefile(path))):
            raise LifecycleError('Lifecycle state overlaps protected input: ' + str(path))


def _reject_sentinel_overlap(sentinels: Mapping[str, str], target: Path, baselib: Path) -> None:
    for value in sentinels:
        path = Path(value)
        if path.is_relative_to(target) or path.is_relative_to(baselib):
            raise LifecycleError('Save sentinel must be outside the mod targets: ' + str(path))


def _compare_sentinels(before: Mapping[str, str], after: Mapping[str, str]) -> None:
    if dict(before) != dict(after):
        changed = sorted(set(before) ^ set(after)
                         | {key for key in set(before) & set(after) if before[key] != after[key]})
        raise LifecycleError('Save sentinel changed during lifecycle operation: ' + ', '.join(changed[:5]))


def default_state_path(game: Path) -> Path:
    key = hashlib.sha256(str(game).encode('utf-8')).hexdigest()[:16]
    return ROOT / '.local/package-lifecycle' / f'{key}.json'


def _state_path(value: Path | str | None, game: Path) -> Path:
    path = default_state_path(game) if value is None else Path(value).expanduser().absolute()
    if path.resolve().is_relative_to(game):
        raise LifecycleError('Lifecycle state must live outside the game copy: ' + str(path))
    if path.exists() and (path.is_symlink() or _is_junction(path) or not path.is_file()):
        raise LifecycleError(f'Refusing unsafe lifecycle state path: {path}')
    return path


def _validate_owned_files(files: object) -> dict[str, str]:
    if not isinstance(files, dict) or not files:
        raise LifecycleError('Lifecycle state has no owned files')
    if set(files) - set(MOD_FILES):
        raise LifecycleError('Lifecycle state names a file outside the Volibear mod')
    for name, digest in files.items():
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise LifecycleError(f'Invalid lifecycle state hash: {name}')
    return dict(files)


def read_state(path: Path) -> dict | None:
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or _is_junction(path) or not path.is_file():
        raise LifecycleError(f'Refusing unsafe lifecycle state path: {path}')
    state = _json_object(path.read_bytes(), 'lifecycle state')
    if state.get('schema') != STATE_SCHEMA:
        raise LifecycleError('Unsupported lifecycle state schema')
    if not isinstance(state.get('target'), str) or not state['target']:
        raise LifecycleError('Lifecycle state has no install target')
    state['files'] = _validate_owned_files(state.get('files'))
    package = state.get('package')
    if (not isinstance(package, dict)
            or not isinstance(package.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', package['sha256'])):
        raise LifecycleError('Lifecycle state has no package identity')
    baselib = state.get('baselib')
    if (not isinstance(baselib, dict)
            or baselib.get('mode') not in ('install', 'reuse', 'installed')
            or not isinstance(baselib.get('files'), dict)):
        raise LifecycleError('Lifecycle state BaseLib record is invalid')
    if not isinstance(state['target'], str) or not Path(state['target']).is_absolute():
        raise LifecycleError('Lifecycle state install target is not absolute')
    protected = state.get('protected')
    if protected is not None:
        if not isinstance(protected, dict):
            raise LifecycleError('Lifecycle state protected snapshot is invalid')
        if not isinstance(protected.get('foreign', {}), dict):
            raise LifecycleError('Lifecycle state foreign snapshot is invalid')
        if not isinstance(protected.get('sentinels', {}), dict):
            raise LifecycleError('Lifecycle state sentinel snapshot is invalid')
    return state


def _state_bytes(state: Mapping) -> bytes:
    return (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def write_state(path: Path, state: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or _is_junction(path):
        raise LifecycleError(f'Refusing redirected lifecycle state path: {path}')
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix='.lifecycle-', suffix='.tmp')
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(_state_bytes(state))
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or _is_junction(path):
            raise LifecycleError(f'Refusing redirected lifecycle state path: {path}')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def remove_state(path: Path) -> None:
    if os.path.lexists(path):
        if path.is_symlink() or _is_junction(path) or not path.is_file():
            raise LifecycleError(f'Refusing unsafe lifecycle state path: {path}')
        path.unlink()


def _current_file_hashes(target: Path, *, allow_missing: bool) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in MOD_FILES:
        path = target / name
        if not os.path.lexists(path):
            if allow_missing:
                continue
            raise LifecycleError(f'Missing owned file: {path}')
        _regular_file(path, 'owned mod file ' + name)
        if path.resolve() != target.resolve() / name:
            raise LifecycleError(f'Refusing redirected owned file: {path}')
        hashes[name] = _sha_file(path)
    return hashes


def _target_foreign_entries(target: Path) -> list[str]:
    return sorted(entry.name for entry in target.iterdir() if entry.name not in MOD_FILES)


def _protected_payload(foreign: Mapping[str, tuple], sentinels: Mapping[str, str]) -> dict:
    return {
        'foreign': {name: list(value) for name, value in sorted(foreign.items())},
        'sentinels': dict(sorted(sentinels.items())),
    }


def _protected_snapshot(state: Mapping) -> tuple[dict[str, tuple], dict[str, str]]:
    protected = state.get('protected')
    if not isinstance(protected, dict):
        return {}, {}
    foreign: dict[str, tuple] = {}
    for name, value in protected.get('foreign', {}).items():
        if not isinstance(name, str) or not isinstance(value, list) or len(value) != 2:
            raise LifecycleError('Lifecycle state foreign snapshot is invalid')
        foreign[name] = tuple(value)
    sentinels = protected.get('sentinels', {})
    if not isinstance(sentinels, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                  for k, v in sentinels.items()):
        raise LifecycleError('Lifecycle state sentinel snapshot is invalid')
    return foreign, dict(sentinels)


@dataclass
class LifecyclePlan:
    requested_action: str
    operation: str
    package: PackageArchive
    game_dir: Path
    target: Path
    baselib: Path
    state_path: Path
    state: dict | None
    old_files: dict[str, str]
    new_files: dict[str, str]
    target_mode: str
    baselib_mode: str
    write_state: bool
    remove_state: bool
    state_after: dict | None
    foreign_before: dict[str, tuple]
    baselib_before: dict[str, tuple] | None
    sentinels_before: dict[str, str]
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self, *, applied: bool = False) -> dict:
        return {
            'action': self.requested_action,
            'operation': self.operation,
            'applied': applied,
            'package': {
                'path': str(self.package.path),
                'sha256': self.package.sha256,
                'mod_version': self.package.mod_version,
                'audio_profile': self.package.audio_profile,
                'file_count': len(self.package.files),
            },
            'game_dir': str(self.game_dir),
            'target': str(self.target),
            'baselib': {'path': str(self.baselib), 'mode': self.baselib_mode},
            'state_path': str(self.state_path),
            'state_present': self.state is not None,
            'old_files': dict(sorted(self.old_files.items())),
            'new_files': dict(sorted(self.new_files.items())),
            'target_mode': self.target_mode,
            'write_state': self.write_state,
            'remove_state': self.remove_state,
            'steps': list(self.steps),
            'warnings': list(self.warnings),
            'protected': {
                'foreign_files': len(self.foreign_before),
                'sentinels': dict(sorted(self.sentinels_before.items())),
            },
        }


def _check_mods_layout(game: Path) -> Path:
    mods = game / 'mods'
    if os.path.lexists(mods):
        _plain_directory(mods, 'mods directory')
    return mods


def _check_target(target: Path) -> None:
    if target.is_symlink() or _is_junction(target):
        raise LifecycleError(f'Refusing redirected mod directory: {target}')
    if target.exists() and not target.is_dir():
        raise LifecycleError(f'Mod target is not a directory: {target}')
    if target.exists() and target.resolve() != target.absolute():
        raise LifecycleError(f'Refusing redirected mod directory: {target}')


def _check_baselib(base: Path, package: PackageArchive) -> None:
    _plain_directory(base, 'BaseLib directory')
    for name in BASELIB_FILES:
        path = base / name
        _regular_file(path, 'BaseLib file ' + name)
        if path.resolve() != base.resolve() / name:
            raise LifecycleError(f'Refusing redirected BaseLib file: {path}')
        if _sha_file(path) != package.digest(BASELIB_PREFIX + name):
            raise LifecycleError(f'Existing BaseLib differs from pinned 3.4.7: {name}; '
                                 'refusing to replace or remove a dependency owned by another installation')


def _state_package(state: Mapping | None) -> Mapping:
    package = state.get('package') if state else None
    return package if isinstance(package, dict) else {}


def plan_install(package: PackageArchive, game: Path, state_path: Path, *,
                 previous: PackageArchive | None, sentinels: Iterable[Path | str],
                 requested_action: str) -> LifecyclePlan:
    _reject_state_overlap(state_path, (package.path, *((previous.path,) if previous else ())))
    mods = _check_mods_layout(game)
    target = mods / 'Volibear'
    baselib = mods / 'BaseLib'
    _check_target(target)
    state = read_state(state_path)
    if state is not None and state['target'] != str(target):
        raise LifecycleError('Lifecycle state belongs to another installation target')
    foreign_before = _snapshot_mods_foreign(game)
    sentinels_before = _snapshot_sentinels(sentinels)
    _reject_sentinel_overlap(sentinels_before, target, baselib)
    _reject_state_overlap(state_path, (*sentinels_before, package.path))
    steps: list[str] = []
    warnings: list[str] = []
    if not mods.exists():
        steps.append(f'Create mods directory: {mods}')

    baselib_before: dict[str, tuple] | None = None
    if os.path.lexists(baselib):
        _check_baselib(baselib, package)
        baselib_before = _snapshot_tree(baselib, mods)
        baselib_mode = ('installed' if state and state.get('baselib', {}).get('mode') == 'installed'
                        else 'reuse')
        steps.append(f'Reuse existing pinned BaseLib {BASELIB_VERSION} at {baselib}; no BaseLib writes')
    else:
        baselib_mode = 'install'
        steps.append(f'Install BaseLib {BASELIB_VERSION} at {baselib} (uninstall never removes it)')

    new_files = {name: package.digest(VOLIBEAR_PREFIX + name) for name in MOD_FILES}
    old_files: dict[str, str] = {}
    if target.exists():
        foreign_entries = _target_foreign_entries(target)
        if foreign_entries:
            raise LifecycleError('mods/Volibear contains entries not owned by this package: '
                                 + ', '.join(foreign_entries))
        current = _current_file_hashes(target, allow_missing=True)
        if state is not None:
            old_files = dict(state['files'])
            steps.append('Use lifecycle ownership hashes for the existing installation')
        elif previous is not None:
            old_files = {name: previous.digest(VOLIBEAR_PREFIX + name) for name in MOD_FILES}
            steps.append('Use --previous-package ownership hashes for the existing installation')
        elif current:
            raise LifecycleError('Existing mods/Volibear has no ownership record; pass the package '
                                 'that installed it with --previous-package or remove it manually')
        for name, digest in old_files.items():
            if name in current and current[name] != digest:
                raise LifecycleError(f'Existing owned file changed; refusing update: {name}')
        for name in current:
            if name not in old_files:
                raise LifecycleError(f'Existing file is not owned by the recorded package: {name}')
        if old_files and current and all(current.get(name) == new_files[name] for name in MOD_FILES):
            state_package = _state_package(state)
            if (state is not None and state_package.get('sha256') == package.sha256
                    and state['files'] == new_files):
                target_mode = 'installed'
                steps.append('Existing installation already matches this exact package; no mod writes')
            else:
                target_mode = 'refresh'
                steps.append('File bytes already match; refresh lifecycle ownership to this package')
        elif old_files:
            target_mode = 'update'
            steps.append('Update only the owned Volibear files after checking every old hash')
        else:
            target_mode = 'create'
            steps.append(f'Install Volibear files into existing empty directory: {target}')
    else:
        target_mode = 'create'
        steps.append(f'Install Volibear files into new directory: {target}')

    if requested_action == 'update' and target_mode == 'create':
        raise LifecycleError('--action update requires an existing owned installation')

    write_state = not (target_mode == 'installed' and state is not None)
    state_after = None
    if target_mode != 'installed' or state is None:
        state_after = {
            'schema': STATE_SCHEMA,
            'target': str(target),
            'game': str(game),
            'package': {
                'path': str(package.path),
                'sha256': package.sha256,
                'mod_version': package.mod_version,
                'audio_profile': package.audio_profile,
            },
            'files': dict(sorted(new_files.items())),
            'baselib': {
                'mode': baselib_mode,
                'version': BASELIB_VERSION,
                'files': {name: package.digest(BASELIB_PREFIX + name) for name in BASELIB_FILES},
            },
            'protected': _protected_payload(foreign_before, sentinels_before),
        }
    operation = 'install' if target_mode == 'create' else 'update'
    return LifecyclePlan(requested_action=requested_action, operation=operation,
                         package=package, game_dir=game, target=target, baselib=baselib,
                         state_path=state_path, state=state, old_files=old_files,
                         new_files=new_files, target_mode=target_mode,
                         baselib_mode=baselib_mode, write_state=write_state,
                         remove_state=False, state_after=state_after,
                         foreign_before=foreign_before, baselib_before=baselib_before,
                         sentinels_before=sentinels_before, steps=steps, warnings=warnings)


def plan_uninstall(package: PackageArchive, game: Path, state_path: Path, *,
                   sentinels: Iterable[Path | str]) -> LifecyclePlan:
    mods = _check_mods_layout(game)
    target = mods / 'Volibear'
    baselib = mods / 'BaseLib'
    _check_target(target)
    state = read_state(state_path)
    if state is not None and state['target'] != str(target):
        raise LifecycleError('Lifecycle state belongs to another installation target')
    foreign_before = _snapshot_mods_foreign(game)
    sentinels_before = _snapshot_sentinels(sentinels)
    _reject_sentinel_overlap(sentinels_before, target, baselib)
    _reject_state_overlap(state_path, (*sentinels_before, package.path))
    baselib_before = (_snapshot_tree(baselib, mods) if os.path.lexists(baselib) else None)
    steps: list[str] = []
    warnings: list[str] = []
    owned: dict[str, str] = {}
    target_mode = 'absent'
    if target.exists():
        foreign_entries = _target_foreign_entries(target)
        if foreign_entries:
            warnings.append('Foreign entries in mods/Volibear will be preserved: '
                            + ', '.join(foreign_entries))
        current = _current_file_hashes(target, allow_missing=True)
        if state is not None:
            owned = dict(state['files'])
            steps.append('Use lifecycle ownership hashes from the recorded installation')
        for name in current:
            if state is not None:
                if name not in owned:
                    raise LifecycleError(f'Existing file is not owned by the recorded installation: {name}')
                if current[name] != owned[name]:
                    raise LifecycleError(f'Owned file changed; refusing uninstall: {name}')
            else:
                if current[name] != package.digest(VOLIBEAR_PREFIX + name):
                    raise LifecycleError(f'Existing file does not match the supplied package; '
                                         f'refusing uninstall: {name}')
                owned[name] = current[name]
        if not state and not owned and not current:
            target_mode = 'empty'
            steps.append('No owned Volibear files found; only an empty/foreign directory remains')
        elif owned:
            target_mode = 'remove'
            steps.append('Delete only hash-verified owned Volibear files: ' + ', '.join(sorted(owned)))
        else:
            target_mode = 'preserve'
            steps.append('No owned Volibear files found; preserving the directory')
    else:
        steps.append('mods/Volibear is already absent')
    if state is not None:
        steps.append('Remove the lifecycle ownership record after successful deletion')
    steps.append('Leave BaseLib, foreign sibling mods, save sentinels and all non-owned files untouched')
    return LifecyclePlan(requested_action='uninstall', operation='uninstall',
                         package=package, game_dir=game, target=target, baselib=baselib,
                         state_path=state_path, state=state, old_files=owned, new_files={},
                         target_mode=target_mode, baselib_mode='preserve', write_state=False,
                         remove_state=state is not None, state_after=None,
                         foreign_before=foreign_before, baselib_before=baselib_before,
                         sentinels_before=sentinels_before, steps=steps, warnings=warnings)


def verify_state(package: PackageArchive, game: Path, state_path: Path, *,
                 sentinels: Iterable[Path | str]) -> dict:
    """Read-only check of the recorded installation against the package."""
    mods = _check_mods_layout(game)
    target = mods / 'Volibear'
    baselib = mods / 'BaseLib'
    _check_target(target)
    state = read_state(state_path)
    if state is None:
        raise LifecycleError('No lifecycle ownership record to verify: ' + str(state_path))
    if state['target'] != str(target):
        raise LifecycleError('Lifecycle state belongs to another installation target')
    if not target.exists():
        raise LifecycleError('Recorded Volibear installation is missing: ' + str(target))
    current = _current_file_hashes(target, allow_missing=False)
    for name, digest in state['files'].items():
        if current.get(name) != digest:
            raise LifecycleError(f'Installed file no longer matches ownership record: {name}')
    for name in MOD_FILES:
        if name not in state['files']:
            raise LifecycleError(f'Ownership record does not cover expected file: {name}')
    if current != state['files']:
        raise LifecycleError('Installed Volibear files do not match the ownership record')
    expected = {name: package.digest(VOLIBEAR_PREFIX + name) for name in MOD_FILES}
    if current != expected:
        raise LifecycleError('Installed Volibear files do not match the supplied package')
    _check_baselib(baselib, package)
    foreign_state, sentinel_state = _protected_snapshot(state)
    current_foreign = _snapshot_mods_foreign(game)
    _compare_snapshot('Foreign sibling mod files', foreign_state, current_foreign)
    stored_sentinels = sentinel_state
    current_sentinels = _snapshot_sentinels(stored_sentinels)
    _compare_sentinels(stored_sentinels, current_sentinels)
    current_sentinels.update(_snapshot_sentinels(sentinels))
    extra = _target_foreign_entries(target)
    result = {
        'verified': True,
        'target': str(target),
        'files': dict(sorted(current.items())),
        'baselib': str(baselib),
        'foreign_files': len(current_foreign),
        'sentinels': dict(sorted(current_sentinels.items())),
    }
    if extra:
        result['foreign_entries'] = extra
    return result


def _preflight_apply(plan: LifecyclePlan) -> None:
    """Recheck every precondition immediately before writing or deleting."""
    _reject_state_overlap(plan.state_path, (*plan.sentinels_before, plan.package.path))
    game = validate_game(plan.game_dir)
    if game != plan.game_dir:
        raise LifecycleError('Game copy changed since planning')
    mods = game / 'mods'
    if plan.target.parent != mods:
        raise LifecycleError('Lifecycle target moved since planning')
    if plan.baselib.parent != mods:
        raise LifecycleError('BaseLib target moved since planning')
    if os.path.lexists(mods):
        _plain_directory(mods, 'mods directory')
    _check_target(plan.target)
    _compare_snapshot('Foreign sibling mod files', plan.foreign_before,
                      _snapshot_mods_foreign(game))
    _compare_sentinels(plan.sentinels_before, _snapshot_sentinels(plan.sentinels_before))
    state = read_state(plan.state_path)
    if (state is None) != (plan.state is None):
        raise LifecycleError('Lifecycle state changed since planning')
    if state is not None and _state_bytes(state) != _state_bytes(plan.state):
        raise LifecycleError('Lifecycle state changed since planning')
    if plan.operation != 'uninstall':
        if os.path.lexists(plan.baselib):
            if plan.baselib_mode == 'install':
                raise LifecycleError('BaseLib appeared since planning')
            _check_baselib(plan.baselib, plan.package)
            if plan.baselib_before is not None:
                _compare_snapshot('BaseLib', plan.baselib_before,
                                  _snapshot_tree(plan.baselib, mods))
        elif plan.baselib_mode != 'install':
            raise LifecycleError('BaseLib disappeared since planning')
        current = _current_file_hashes(plan.target, allow_missing=True) if plan.target.exists() else {}
        if plan.target.exists() and _target_foreign_entries(plan.target):
            raise LifecycleError('Foreign entries appeared in mods/Volibear since planning')
        for name, digest in plan.old_files.items():
            if name in current and current[name] != digest:
                raise LifecycleError(f'Owned file changed since planning: {name}')
        for name in current:
            if name not in plan.old_files:
                raise LifecycleError(f'Unowned file appeared since planning: {name}')
        if plan.target_mode == 'create' and current:
            raise LifecycleError('mods/Volibear is no longer empty')
        if plan.target_mode in ('update', 'refresh', 'installed') and not plan.target.exists():
            raise LifecycleError('Existing mods/Volibear disappeared since planning')
    else:
        if plan.baselib_before is None:
            if os.path.lexists(plan.baselib):
                raise LifecycleError('BaseLib appeared since planning')
        else:
            _compare_snapshot('BaseLib', plan.baselib_before,
                              _snapshot_tree(plan.baselib, mods))
        if plan.target.exists():
            current = _current_file_hashes(plan.target, allow_missing=True)
            for name, digest in plan.old_files.items():
                if name in current and current[name] != digest:
                    raise LifecycleError(f'Owned file changed since planning: {name}')
            for name in current:
                if name not in plan.old_files:
                    raise LifecycleError(f'Unowned file appeared since planning: {name}')


def _copy_verified(source: Path, target: Path, expected: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or _is_junction(target):
        raise LifecycleError(f'Refusing redirected write target: {target}')
    descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix='.lifecycle-', suffix='.tmp')
    temporary = Path(temporary_name)
    try:
        digest = hashlib.sha256()
        with source.open('rb') as src, os.fdopen(descriptor, 'wb') as dst:
            for chunk in iter(lambda: src.read(CHUNK), b''):
                digest.update(chunk)
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        if digest.hexdigest() != expected:
            raise LifecycleError(f'Staged payload changed: {source.name}')
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _install_baselib(plan: LifecyclePlan, staging: Path) -> None:
    mods = plan.game_dir / 'mods'
    mods.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(dir=mods, prefix='.volibear-baselib-'))
    try:
        for name in BASELIB_FILES:
            source = staging / BASELIB_PREFIX / name
            destination = temporary / name
            _copy_verified(source, destination, plan.package.digest(BASELIB_PREFIX + name))
        if os.path.lexists(plan.baselib):
            raise LifecycleError('BaseLib appeared before install')
        os.chmod(temporary, 0o755)
        os.replace(temporary, plan.baselib)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _install_target(plan: LifecyclePlan, staging: Path) -> None:
    target = plan.target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=True)
    for name in MOD_FILES:
        source = staging / VOLIBEAR_PREFIX / name
        _copy_verified(source, target / name, plan.package.digest(VOLIBEAR_PREFIX + name))


def _install_transaction(plan: LifecyclePlan, staging: Path) -> None:
    """Rollback ordinary install/update failures; preserve recovery files on conflict.

    This is not a crash-atomic multi-file filesystem commit. A recovery
    manifest and exact original bytes remain if rollback cannot safely complete.
    """
    plan.state_path.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='volibear-recovery-', dir=plan.state_path.parent)).resolve()
    directories = [plan.game_dir / 'mods', plan.baselib, plan.target]
    created = [p for p in directories if not os.path.lexists(p)]
    rows = []
    candidates = []
    if plan.baselib_mode == 'install':
        candidates.extend((plan.baselib / n, plan.package.digest(BASELIB_PREFIX + n)) for n in BASELIB_FILES)
    if plan.target_mode != 'installed':
        candidates.extend((plan.target / n, plan.package.digest(VOLIBEAR_PREFIX + n)) for n in MOD_FILES)
    if plan.write_state and plan.state_after is not None:
        candidates.append((plan.state_path, hashlib.sha256(_state_bytes(plan.state_after)).hexdigest()))
    # Snapshot all originals before the first destination write, including raw
    # state bytes (not a JSON reserialization). Extraction verified all new files.
    try:
        for index, (path, new_hash) in enumerate(candidates):
            old_hash = None
            saved = backup / str(index)
            if os.path.lexists(path):
                _regular_file(path, 'transaction original')
                old_hash = _sha_file(path)
                with path.open('rb') as src, saved.open('xb') as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
                    dst.flush()
                    os.fsync(dst.fileno())
                shutil.copystat(path, saved)
                if _sha_file(saved) != old_hash:
                    raise LifecycleError('Original changed during transaction backup')
            rows.append({'path': str(path), 'backup': saved.name,
                         'old_sha256': old_hash, 'new_sha256': new_hash})
        with (backup / 'RECOVERY.json').open('x', encoding='utf-8') as stream:
            json.dump({'schema': 1, 'files': rows, 'created_directories': [str(p) for p in created]}, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        _preflight_apply(plan)
    except BaseException:
        # No installation writes have occurred yet; this is our exact private dir.
        shutil.rmtree(backup)
        raise
    try:
        if plan.baselib_mode == 'install':
            _install_baselib(plan, staging)
        if plan.target_mode != 'installed':
            _install_target(plan, staging)
        if plan.write_state and plan.state_after is not None:
            write_state(plan.state_path, plan.state_after)
        _verify_install(plan)
    except BaseException as original:
        failures = []
        for row in reversed(rows):
            path = Path(row['path'])
            try:
                _plain_directory(path.parent, 'rollback destination parent')
                current = None
                if os.path.lexists(path):
                    _regular_file(path, 'rollback destination')
                    current = _sha_file(path)
                if current == row['old_sha256']:
                    continue
                if current != row['new_sha256']:
                    raise LifecycleError('Destination changed externally; refusing rollback overwrite')
                if row['old_sha256'] is None:
                    path.unlink()
                else:
                    saved = backup / row['backup']
                    _copy_verified(saved, path, row['old_sha256'])
                    shutil.copystat(saved, path)
            except BaseException as error:
                # Missing parent is harmless for files that never existed.
                if not os.path.lexists(path.parent) and row['old_sha256'] is None:
                    continue
                failures.append(f'{path}: {error}')
        for directory in reversed(created):
            try:
                if os.path.lexists(directory):
                    _plain_directory(directory, 'rollback created directory')
                    if not any(directory.iterdir()):
                        directory.rmdir()
            except BaseException as error:
                failures.append(f'{directory}: {error}')
        if failures:
            raise LifecycleError(f'Install failed ({original}); rollback incomplete. '
                                 f'Recovery backup retained at {backup}: ' + '; '.join(failures)) from original
        shutil.rmtree(backup)
        raise
    shutil.rmtree(backup)


def apply_plan(plan: LifecyclePlan) -> None:
    fresh = load_package(plan.package.path)
    if fresh.sha256 != plan.package.sha256 or dict(fresh.files) != dict(plan.package.files):
        raise LifecycleError('Package archive changed since planning')
    _preflight_apply(plan)
    if plan.operation == 'uninstall':
        for name in sorted(plan.old_files):
            path = plan.target / name
            if not os.path.lexists(path):
                continue
            _regular_file(path, 'owned mod file ' + name)
            if _sha_file(path) != plan.old_files[name]:
                raise LifecycleError(f'Owned file changed before deletion: {name}')
            path.unlink()
        if plan.target.exists() and not any(plan.target.iterdir()):
            plan.target.rmdir()
        if plan.remove_state:
            remove_state(plan.state_path)
        _verify_uninstall(plan)
        return

    if (plan.target_mode == 'installed' and plan.baselib_mode != 'install'
            and not plan.write_state):
        _verify_install(plan)
        return
    with tempfile.TemporaryDirectory(prefix='volibear-package-') as temporary:
        staging = extract_package(fresh, Path(temporary) / 'payload')
        _install_transaction(plan, staging)


def _verify_install(plan: LifecyclePlan) -> None:
    state = read_state(plan.state_path)
    if state is None:
        raise LifecycleError('Lifecycle state was not written')
    current = _current_file_hashes(plan.target, allow_missing=False)
    expected = {name: plan.package.digest(VOLIBEAR_PREFIX + name) for name in MOD_FILES}
    if current != expected:
        raise LifecycleError('Installed Volibear files do not match the package')
    if state['files'] != expected:
        raise LifecycleError('Lifecycle ownership hashes do not match the package')
    baselib_record = state.get('baselib', {})
    if (not isinstance(baselib_record, dict)
            or baselib_record.get('files') != {name: plan.package.digest(BASELIB_PREFIX + name)
                                               for name in BASELIB_FILES}):
        raise LifecycleError('Lifecycle BaseLib ownership hashes do not match the package')
    if _target_foreign_entries(plan.target):
        raise LifecycleError('Unexpected foreign entries appeared in mods/Volibear')
    _check_baselib(plan.baselib, plan.package)
    if plan.baselib_before is not None:
        _compare_snapshot('BaseLib', plan.baselib_before,
                          _snapshot_tree(plan.baselib, plan.game_dir / 'mods'))
    if state['target'] != str(plan.target):
        raise LifecycleError('Lifecycle state target does not match the installation')
    _compare_snapshot('Foreign sibling mod files', plan.foreign_before,
                      _snapshot_mods_foreign(plan.game_dir))
    _compare_sentinels(plan.sentinels_before, _snapshot_sentinels(plan.sentinels_before))


def _verify_uninstall(plan: LifecyclePlan) -> None:
    for name in plan.old_files:
        if os.path.lexists(plan.target / name):
            raise LifecycleError(f'Owned file remains after uninstall: {name}')
    if plan.remove_state and os.path.lexists(plan.state_path):
        raise LifecycleError('Lifecycle state remains after uninstall')
    if not plan.remove_state and os.path.lexists(plan.state_path):
        raise LifecycleError('Unexpected lifecycle state appeared during uninstall')
    if plan.baselib_before is None:
        if os.path.lexists(plan.baselib):
            raise LifecycleError('BaseLib appeared during uninstall')
    else:
        _compare_snapshot('BaseLib', plan.baselib_before,
                          _snapshot_tree(plan.baselib, plan.game_dir / 'mods'))
    _compare_snapshot('Foreign sibling mod files', plan.foreign_before,
                      _snapshot_mods_foreign(plan.game_dir))
    _compare_sentinels(plan.sentinels_before, _snapshot_sentinels(plan.sentinels_before))
    if plan.target.exists():
        remaining = _current_file_hashes(plan.target, allow_missing=True)
        if remaining:
            raise LifecycleError('Volibear files remain after uninstall: ' + ', '.join(remaining))


def run(package_path: Path | str, game_dir: Path | str, *, action: str = 'install',
        state_path: Path | str | None = None, previous_package: Path | str | None = None,
        save_sentinels: Iterable[Path | str] = (), execute: bool = False) -> dict:
    """Validate, plan and optionally apply one lifecycle operation."""
    if action not in ('install', 'update', 'uninstall', 'verify'):
        raise LifecycleError('Unknown lifecycle action: ' + str(action))
    package = load_package(package_path)
    game = validate_game(game_dir)
    state = _state_path(state_path, game)
    save_sentinels = tuple(save_sentinels)
    _reject_state_overlap(state, (*save_sentinels, package.path,
                                 *((previous_package,) if previous_package is not None else ())))
    if action == 'verify':
        if execute:
            raise LifecycleError('--action verify is read-only; remove --execute')
        result = verify_state(package, game, state, sentinels=save_sentinels)
        return {
            'action': action,
            'operation': 'verify',
            'applied': False,
            'package': {
                'path': str(package.path),
                'sha256': package.sha256,
                'mod_version': package.mod_version,
                'audio_profile': package.audio_profile,
                'file_count': len(package.files),
            },
            'game_dir': str(game),
            'state_path': str(state),
            'verification': result,
        }
    previous = load_package(previous_package) if previous_package is not None else None
    if action == 'uninstall':
        if previous is not None:
            raise LifecycleError('--previous-package is only used for install/update ownership')
        plan = plan_uninstall(package, game, state, sentinels=save_sentinels)
    else:
        plan = plan_install(package, game, state, previous=previous,
                            sentinels=save_sentinels, requested_action=action)
    result = plan.as_dict(applied=False)
    if execute:
        apply_plan(plan)
        result = plan.as_dict(applied=True)
        result['verification'] = 'passed'
    return result


def _print_plan(result: Mapping) -> None:
    heading = 'APPLIED' if result.get('applied') else 'PLAN (no files changed; use --execute to apply)'
    print(f'PACKAGE LIFECYCLE {heading}: {result["operation"]}')
    package = result['package']
    print(f'Package: {package["path"]}')
    print(f'  SHA-256: {package["sha256"]}')
    print(f'  Mod version: {package["mod_version"]}; audio: {package["audio_profile"]}; '
          f'files: {package["file_count"]}')
    print(f'Game copy: {result["game_dir"]}')
    if result.get('operation') == 'verify':
        verification = result['verification']
        print(f'Verified target: {verification["target"]}')
        print(f'BaseLib: {verification["baselib"]}')
        print(f'Foreign sibling files preserved: {verification["foreign_files"]}')
        for path, digest in verification['sentinels'].items():
            print(f'Save sentinel: {path} ({digest})')
        print('VERIFICATION PASSED.')
        return
    print(f'Target: {result["target"]}')
    print(f'BaseLib: {result["baselib"]["path"]} ({result["baselib"]["mode"]})')
    print(f'Lifecycle state: {result["state_path"]}')
    for step in result.get('steps', []):
        print('  - ' + step)
    for warning in result.get('warnings', []):
        print('  ! ' + warning)
    if result.get('applied'):
        print('VERIFICATION PASSED: installed/deleted files, ownership, BaseLib, foreign mods and sentinels match.')
    else:
        print('Plan only. No package, game, BaseLib, save sentinel or state file was changed.')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--package', type=Path, required=True,
                        help='Final Volibear installation ZIP to validate')
    parser.add_argument('--game-dir', type=Path, required=True,
                        help='Existing isolated copy of StS2 0.107.1 / 59260271')
    parser.add_argument('--action', choices=('install', 'update', 'uninstall', 'verify'),
                        default='install', help='Lifecycle action; install also performs a safe update')
    parser.add_argument('--state', type=Path,
                        help='Ownership record path; defaults to .local/package-lifecycle/<game>.json')
    parser.add_argument('--previous-package', type=Path,
                        help='Old package used to prove ownership when the state record is missing')
    parser.add_argument('--save-sentinel', type=Path, action='append', default=[],
                        help='Existing save file that must remain byte-identical; repeatable')
    parser.add_argument('--execute', action='store_true',
                        help='Apply the plan; without this flag only validation/planning occurs')
    parser.add_argument('--json', action='store_true', help='Print one machine-readable JSON object')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args.package, args.game_dir, action=args.action, state_path=args.state,
                     previous_package=args.previous_package,
                     save_sentinels=args.save_sentinel, execute=args.execute)
    except (LifecycleError, OSError, KeyError, ValueError) as error:
        print('PACKAGE LIFECYCLE STOPPED: ' + str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_plan(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
