#!/usr/bin/env python3
"""Acquire the pinned BaseLib release and install only explicitly owned mod files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.4.7'
URL = f'https://github.com/Alchyr/BaseLib-StS2/releases/download/v{VERSION}/BaseLib.{VERSION}.zip'
SHA256 = 'd28c649a3aea9ef4869050a06bfbadc4863016bcbd4c1740acc4cd07809e4bd8'
CACHE = ROOT / '.local/dependencies' / f'BaseLib-{VERSION}'
FILES = ('BaseLib.dll', 'BaseLib.pck', 'BaseLib.json')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assert_unredirected(path):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise RuntimeError(f'Refusing redirected dependency path: {path}')


def acquire():
    archive = ROOT / '.local/dependencies' / f'BaseLib.{VERSION}.zip'
    assert_unredirected(archive)
    assert_unredirected(CACHE)
    if archive.is_file():
        data = archive.read_bytes()
        if digest(data) != SHA256:
            raise RuntimeError('Cached BaseLib archive does not match pinned release; refusing it')
    else:
        data = urllib.request.urlopen(URL, timeout=60).read()
        if digest(data) != SHA256:
            raise RuntimeError('Downloaded BaseLib archive does not match pinned release')
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        selected = {}
        for name in FILES:
            matches = [entry for entry in z.namelist() if entry.rstrip('/').split('/')[-1] == name]
            if len(matches) != 1:
                raise RuntimeError(f'Expected exactly one {name} in release archive')
            selected[name] = z.read(matches[0])
    manifest = json.loads(selected['BaseLib.json'])
    if manifest.get('id') != 'BaseLib' or manifest.get('version') != f'v{VERSION}':
        raise RuntimeError('Unexpected dependency manifest')
    # Validate every cache destination before changing any of them.
    for name, payload in selected.items():
        target = CACHE / name
        assert_unredirected(target)
        if target.exists() and target.read_bytes() != payload:
            raise RuntimeError(f'Existing dependency cache differs: {target}')
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, payload in selected.items():
        target = CACHE / name
        if not target.exists():
            target.write_bytes(payload)
    print(f'BaseLib {VERSION}: release integrity verified; game compatibility still requires execution')
    return selected


def install(selected, game=None):
    if game is None:
        from dev import config, validate_game
        game = Path(config()['game_dir']).expanduser().resolve()
    else:
        try:
            from .dev import validate_game
        except ImportError:
            from dev import validate_game
        game = Path(game).expanduser().resolve()
    validate_game(game)
    target = game / 'mods' / 'BaseLib'
    if target.is_symlink() or target.resolve() != target:
        raise RuntimeError('Refusing redirected dependency install target')
    marker = ROOT / '.local/deploy/BaseLib.json'
    old = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
    if old is not None and old.get('target') != str(target):
        raise RuntimeError('Dependency ownership marker belongs to another installation')
    for name, payload in selected.items():
        dst = target / name
        if dst.is_symlink() or dst.resolve() != target / name:
            raise RuntimeError(f'Refusing redirected file: {dst}')
        if dst.exists():
            current = dst.read_bytes()
            recorded = old.get('files', {}).get(name) if old else None
            if recorded is not None and recorded != digest(current):
                raise RuntimeError(f'Refusing unowned or changed dependency: {dst}')
            if current == payload:
                continue
            if old is None or old.get('files', {}).get(name) != digest(current):
                raise RuntimeError(f'Refusing to replace unowned or changed dependency: {dst}')
    # Preflight all destinations before writing. Do not touch other mods or save directories.
    target.mkdir(parents=True, exist_ok=True)
    owned = dict(old.get('files', {})) if old else {}
    for name, payload in selected.items():
        dst = target / name
        if not dst.exists() or dst.read_bytes() != payload:
            dst.write_bytes(payload)
            owned[name] = digest(payload)
        # A matching pre-existing unowned installation is reused, not claimed for removal.
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({'target': str(target), 'version': VERSION, 'files': owned}, indent=2) + '\n', encoding='utf-8')
    print(f'BaseLib {VERSION}: dependency files available at {target}; load not yet verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('fetch', 'install'))
    args = parser.parse_args()
    selected = acquire()
    if args.command == 'install':
        install(selected)


if __name__ == '__main__':
    main()
