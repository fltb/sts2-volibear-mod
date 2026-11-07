#!/usr/bin/env python3
"""Diff the native game surface between two installed channels (stable vs PBE).

Runs a small reflection dumper against each game's managed assemblies, then classifies
the difference as: removed (must re-anchor), added (new target), signature-changed
(same name, new parameter list), or visibility-changed (public -> internal needs reflection).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMPER = ROOT / 'tools/apidiff'
DATA_NAMES = ('data_sts2_linuxbsd_x86_64', 'data_sts2_windows_x86_64')


def data_dir(game: Path) -> Path:
    for name in DATA_NAMES:
        candidate = game / name
        if (candidate / 'sts2.dll').is_file():
            return candidate
    raise SystemExit(f'No sts2.dll under {game}')


def dump(game: Path, dotnet: str) -> dict:
    env = dict(os.environ)
    env['VOLIBEAR_API_ASSEMBLY'] = str((data_dir(game) / 'sts2.dll').resolve())
    result = subprocess.run(
        [dotnet, 'run', '--project', str(DUMPER), '--no-launch-profile',
         '-p:Sts2DataDir=' + str(data_dir(game).resolve()),
         '-v', 'q', '--nologo'],
        capture_output=True, text=True, env=env, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit('surface dump failed:\n' + result.stderr[-2000:])
    line = result.stdout.strip().splitlines()[-1]
    return json.loads(line)


def classify(old: dict, new: dict) -> list[dict]:
    changes = []
    for type_name in sorted(set(old) | set(new)):
        a, b = old.get(type_name, {}), new.get(type_name, {})
        if not a:
            changes.append({'kind': 'type-added', 'type': type_name})
            continue
        if not b:
            changes.append({'kind': 'type-removed', 'type': type_name})
            continue
        for key in sorted(set(a) | set(b)):
            if key not in b:
                changes.append({'kind': 'removed', 'type': type_name, 'member': key, 'old': a[key]})
            elif key not in a:
                changes.append({'kind': 'added', 'type': type_name, 'member': key, 'new': b[key]})
            elif a[key].split(':', 1)[1] != b[key].split(':', 1)[1]:
                changes.append({'kind': 'return-changed', 'type': type_name, 'member': key, 'old': a[key], 'new': b[key]})
            elif a[key].split(':', 1)[0] != b[key].split(':', 1)[0]:
                changes.append({'kind': 'visibility-changed', 'type': type_name, 'member': key, 'old': a[key], 'new': b[key]})
        names_a = {}
        for key in a:
            if key.startswith('M:'):
                names_a.setdefault(key.split('(')[0], []).append(key)
        for name, keys in names_a.items():
            new_names = [k for k in b if k.split('(')[0] == name]
            if keys and new_names and set(keys) - set(b) and not (set(keys) & set(b)):
                changes.append({'kind': 'overloads-changed', 'type': type_name, 'name': name[2:],
                                'old': sorted(keys), 'new': sorted(new_names)})
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stable-dir', type=Path, required=True)
    parser.add_argument('--pbe-dir', type=Path, required=True)
    parser.add_argument('--dotnet', default=os.environ.get('DOTNET', 'dotnet'))
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    old = dump(args.stable_dir, args.dotnet)
    new = dump(args.pbe_dir, args.dotnet)
    changes = classify(old, new)
    counts = {}
    for c in changes:
        counts[c['kind']] = counts.get(c['kind'], 0) + 1
    print('surface diff: ' + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'no changes')
    for c in changes:
        if c['kind'] in ('removed', 'return-changed', 'visibility-changed', 'overloads-changed', 'type-removed'):
            print('  ' + json.dumps(c, ensure_ascii=False)[:300])
    if args.json:
        args.json.write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('wrote ' + str(args.json))
    return 0


if __name__ == '__main__':
    sys.exit(main())
