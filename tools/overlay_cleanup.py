"""Remove only unchanged obsolete files declared by a local source overlay archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path('.local/delivery/obsolete-files.json')


def _plain_path(root, relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
            or relative.startswith('/') or any(part in ('', '.', '..') or part != part.rstrip(' .')
                                               for part in relative.split('/'))
            or any(part.casefold() == '.git' for part in PurePosixPath(relative).parts)):
        raise ValueError('Unsafe obsolete file path: ' + str(relative))
    target = root / relative
    for candidate in [*target.parents, target]:
        if candidate == root or root not in candidate.parents:
            continue
        if candidate.is_symlink() or (hasattr(os.path, 'isjunction') and os.path.isjunction(candidate)):
            raise ValueError('Redirected obsolete file path: ' + relative)
    if not target.resolve().is_relative_to(root):
        raise ValueError('Obsolete file escapes repository: ' + relative)
    # Python before 3.12 has no os.path.isjunction; canonical-path equality still
    # rejects a Windows junction, including one redirected elsewhere inside the repo.
    if target.resolve() != target:
        raise ValueError('Redirected obsolete file path: ' + relative)
    return target


def plan(root=ROOT):
    root = Path(root).resolve()
    manifest = _plain_path(root, MANIFEST.as_posix())
    if not manifest.exists():
        return []
    if not stat.S_ISREG(manifest.stat().st_mode):
        raise ValueError('Obsolete-file manifest is not a regular file')
    data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if (not isinstance(data, dict) or data.get('schema') != 1
            or not isinstance(data.get('files'), list)):
        raise ValueError('Unsupported obsolete-file manifest schema')
    selected, names = [], set()
    for row in data['files']:
        if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
            raise ValueError('Invalid obsolete-file record')
        relative, digest = row['path'], row['sha256']
        target = _plain_path(root, relative)
        if relative.casefold() in names or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Duplicate obsolete file or invalid SHA-256: ' + relative)
        names.add(relative.casefold())
        if target == manifest:
            raise ValueError('Obsolete-file manifest cannot delete itself')
        if not target.exists():
            continue
        if not stat.S_ISREG(target.stat().st_mode):
            raise ValueError('Obsolete path is not a regular file: ' + relative)
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Obsolete-file conflict; local changes preserved: ' + relative)
        selected.append((target, digest))
    return selected


def cleanup(root=ROOT, *, dry_run=False):
    # Preflight the whole manifest before deleting any files; a conflict leaves the batch intact.
    selected = plan(root)
    if dry_run:
        return [path for path, _ in selected]
    for path, digest in selected:
        relative = path.relative_to(Path(root).resolve()).as_posix()
        current = _plain_path(Path(root).resolve(), relative)
        if not current.exists():
            continue
        if not stat.S_ISREG(current.stat().st_mode) or hashlib.sha256(current.read_bytes()).hexdigest() != digest:
            raise ValueError('Obsolete-file changed during cleanup; preserved: ' + relative)
        current.unlink()
        print('Removed unchanged obsolete file:', relative, flush=True)
    return [path for path, _ in selected]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    print('Obsolete files:', len(cleanup(dry_run=arguments.check)))
