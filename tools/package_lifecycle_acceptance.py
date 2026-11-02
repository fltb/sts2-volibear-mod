#!/usr/bin/env python3
"""No-launch final ZIP acceptance on a fresh minimal copy of pinned game files.

This exercises filesystem installation, same-ZIP update and removal, not gameplay
or compatibility with arbitrary third-party mods. No game PCK is copied.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

try:
    from tools import package_lifecycle as lifecycle
except ModuleNotFoundError:
    import package_lifecycle as lifecycle


def write_report(path, report):
    path = Path(path)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def accept(package_path, source_game, output):
    """Output must be a new directory; failures retain fixture and evidence."""
    output = Path(output).absolute()
    # Check parents too: never allow a redirected acceptance target.
    for parent in (output, *output.parents):
        if parent.is_symlink() or lifecycle._is_junction(parent):
            raise lifecycle.LifecycleError('Redirected acceptance output: ' + str(parent))
    source = lifecycle.validate_game(source_game)
    if output == source or source in output.parents:
        raise lifecycle.LifecycleError('Acceptance output must be outside source game')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'status': 'failed', 'scope': 'filesystem-only; same-ZIP update; no game launch',
              'steps': [], 'source_files': {}, 'checks': {}, 'package_sha256': None}
    try:
        package = lifecycle.load_package(package_path)
        report['package_sha256'] = package.sha256
        game = output / 'game'
        game.mkdir()
        data = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
        executable = 'SlayTheSpire2.exe' if os.name == 'nt' else 'SlayTheSpire2'
        names = ['release_info.json', executable, *(data + '/' + n for n in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        for name in names:
            target = game / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
            digest = lifecycle._sha_file(source / name)
            if lifecycle._sha_file(target) != digest:
                raise lifecycle.LifecycleError('Source copy hash mismatch: ' + name)
            report['source_files'][name] = digest
        # Explicit synthetic sentinels, not evidence of third-party gameplay.
        other = game / 'mods/AcceptanceSentinel/keep.bin'
        other.parent.mkdir(parents=True)
        other.write_bytes(b'volibear acceptance foreign-mod sentinel v1\n')
        save = game / 'saves/acceptance-sentinel.save'
        save.parent.mkdir()
        save.write_bytes(b'volibear acceptance save sentinel v1\n')
        protected = {p.relative_to(game).as_posix(): lifecycle._sha_file(p) for p in (other, save)}
        state = output / 'ownership.json'
        base_hashes = None
        for action in ('install', 'update', 'uninstall'):
            result = lifecycle.run(package.path, game, action=action, state_path=state,
                                   save_sentinels=[save], execute=True)
            if result.get('verification') != 'passed' or result.get('applied') is not True:
                raise lifecycle.LifecycleError('Operation did not apply and verify: ' + action)
            for name, digest in protected.items():
                if lifecycle._sha_file(game / name) != digest:
                    raise lifecycle.LifecycleError('Protected sentinel changed: ' + name)
            current_base = {name: lifecycle._sha_file(game / name) for name in sorted(lifecycle.BASELIB_ENTRIES)}
            if base_hashes is None:
                base_hashes = current_base
            if current_base != base_hashes or any(current_base[n] != package.digest(n) for n in current_base):
                raise lifecycle.LifecycleError('BaseLib changed or differs from package')
            if action != 'uninstall':
                lifecycle.run(package.path, game, action='verify', state_path=state, save_sentinels=[save])
            report['steps'].append({'action': action, 'status': 'passed', 'protected_sha256': protected,
                                    'baselib_sha256': current_base})
        if (game / 'mods/Volibear').exists() or state.exists():
            raise lifecycle.LifecycleError('Uninstall left owned mod or ownership state')
        for name, digest in report['source_files'].items():
            if lifecycle._sha_file(game / name) != digest or lifecycle._sha_file(source / name) != digest:
                raise lifecycle.LifecycleError('Pinned game file changed: ' + name)
        if lifecycle._sha_file(package.path) != package.sha256:
            raise lifecycle.LifecycleError('Package changed during acceptance')
        report['checks'] = dict(install=True, same_zip_update=True, uninstall=True,
                                other_mod_preserved=True, save_preserved=True, baselib_preserved=True,
                                pinned_game_files_preserved=True, package_unchanged=True)
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        write_report(output / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--source-game', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = accept(args.package, args.source_game, args.output)
    except (ValueError, OSError) as error:
        print('LIFECYCLE FAILED: ' + str(error))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
