#!/usr/bin/env python3
"""Build the pinned mod and verified PCK, then package; optionally validate in one game process.

First use: python tools/local_delivery.py --game-dir GAME --godot GODOT_MONO --dotnet DOTNET
Paths are saved locally only after preflight succeeds. --resources-only never produces an installer.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv

try:
    from tools import audio_profiles, build_assets, dependencies, dev, overlay_cleanup, release_package, toolchain
except ModuleNotFoundError:
    import audio_profiles, build_assets, dependencies, dev, overlay_cleanup, release_package, toolchain

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.local/config.json'


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, help='Installed StS2 0.107.1 / 59260271 directory')
    parser.add_argument('--godot', help='Ordinary Godot 4.5.1 stable Mono executable')
    parser.add_argument('--dotnet', help='.NET 9 SDK executable; global.json selects the exact SDK')
    parser.add_argument('--doctor', action='store_true', help='Check versions and paths without modifying files')
    parser.add_argument('--resources-only', action='store_true', help='Build and verify PCK only; no game or DLL required')
    parser.add_argument('--verify-native', action='store_true', help='Deploy owned mod files and run one background game suite')
    parser.add_argument('--verify-release', action='store_true',
                        help='Run native gameplay/presentation, disk restart and real two-peer acceptance before packaging')
    parser.add_argument('--audio-profile', choices=('open', 'riot_en'), default='open')
    parser.add_argument('--display', choices=('background', 'xvfb', 'window'),
                        default='background' if os.name == 'nt' else 'xvfb')
    parser.add_argument('--presentation-mode', choices=('cards', 'actions', 'all'), default=None)
    parser.add_argument('--audio-driver', help='Real Godot audio driver; required for actions/all native presentation')
    parser.add_argument('--output', type=Path, help='Installer ZIP path; resource-only output must be a .pck beneath .local')
    args = parser.parse_args(argv)
    if args.verify_release:
        args.verify_native = True
        if args.presentation_mode is not None and args.presentation_mode != 'all':
            parser.error('--verify-release requires --presentation-mode all')
    args.presentation_mode = args.presentation_mode or ('all' if args.verify_release else 'cards')
    if args.resources_only and args.verify_native:
        parser.error('--resources-only cannot run --verify-native; a current mod DLL is required')
    if args.verify_native and args.presentation_mode != 'cards' and (
            not args.audio_driver or args.audio_driver.casefold() == 'dummy'):
        parser.error('actions/all native presentation requires --audio-driver with a real audio backend')
    return args


def preflight(args):
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10 or newer is required')
    dependencies.assert_unredirected(CONFIG)
    settings = json.loads(CONFIG.read_text(encoding='utf-8-sig')) if CONFIG.is_file() else {}
    if not isinstance(settings, dict):
        raise ValueError('.local/config.json must contain an object')
    settings = dict(settings)
    checked = toolchain.check(args.dotnet or os.environ.get('VOLIBEAR_DOTNET') or settings.get('dotnet')
                              or shutil.which('dotnet'),
                              args.godot or settings.get('godot') or shutil.which('godot'))
    settings.update({key: checked[key] for key in ('dotnet', 'godot')})
    if args.game_dir:
        settings['game_dir'] = str(args.game_dir.expanduser().resolve())
    if not args.resources_only:
        if not settings.get('game_dir'):
            raise ValueError('Supply --game-dir pointing at the installed game; --resources-only is PCK-only')
        settings['game_dir'] = str(Path(settings['game_dir']).expanduser().resolve())
        dev.validate_game(Path(settings['game_dir']))
    if args.verify_native:
        allowed_displays = ('background',) if os.name == 'nt' else ('xvfb', 'window')
        if args.display not in allowed_displays:
            raise ValueError('Native validation on this platform requires --display ' + '/'.join(allowed_displays))
        if os.name != 'nt' and args.display == 'window' and not os.environ.get('DISPLAY', '').strip():
            raise ValueError('POSIX window mode requires an existing DISPLAY')
        if args.display == 'xvfb' and not shutil.which('xvfb-run'):
            raise ValueError('Native background validation requires xvfb-run on Linux')
    overlay_cleanup.cleanup(ROOT, dry_run=True)
    if args.output:
        if args.resources_only:
            build_assets.output_path(args.output)
        elif args.output.suffix.lower() != '.zip':
            raise ValueError('Full delivery --output must be a .zip')
        elif args.audio_profile == 'riot_en' and not args.output.resolve().is_relative_to((ROOT / '.local').resolve()):
            raise ValueError('Private Riot output must remain beneath ignored .local/')
    print('Preflight: .NET SDK ' + checked['dotnet_version'] + '; Godot ' + checked['godot_version'], flush=True)
    if args.resources_only:
        print('Scope: resource PCK only; installed-game behavior and complete installation are outside this run.', flush=True)
    else:
        print('Game: 0.107.1 / 59260271; required installed assemblies and executable present.', flush=True)
    return settings


def save_settings(settings):
    dependencies.assert_unredirected(CONFIG)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=CONFIG.parent, prefix='config-', suffix='.tmp',
                                     mode='w', encoding='utf-8', delete=False) as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    try:
        dependencies.assert_unredirected(CONFIG)
        os.replace(temporary, CONFIG)
    finally:
        temporary.unlink(missing_ok=True)


def run(command, env):
    subprocess.run([str(value) for value in command], cwd=ROOT, env=env, check=True)


def python_for_checks(env, *, need_numpy=False):
    modules = ['PIL'] + (['numpy'] if need_numpy else [])
    if all(importlib.util.find_spec(name) is not None for name in modules):
        return Path(sys.executable)
    # Install missing check/processing dependencies into this repository's isolated venv,
    # never into the user's global Python. Ordinary resource-only builds need no packages.
    directory = ROOT / '.local/build-python'
    dependencies.assert_unredirected(directory)
    interpreter = directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not interpreter.is_file():
        if directory.exists() and any(directory.iterdir()):
            raise ValueError('Unrecognized nonempty build-Python directory: ' + str(directory))
        venv.EnvBuilder(with_pip=True).create(directory)
    requirements = ['Pillow>=10.0'] + (['numpy>=1.24'] if need_numpy else [])
    run([interpreter, '-m', 'pip', 'install', '--disable-pip-version-check', *requirements], env)
    return interpreter


def prepare_audio(profile, env, python=None):
    if profile != 'riot_en':
        return
    try:
        audio_profiles.verify_prepared(full_decode=False)
        return
    except (ValueError, OSError, KeyError):
        # A private source overlay may already include both pinned originals and prepared
        # clips. A public checkout invokes the pinned-source downloader/processor once.
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise ValueError('Riot audio is not prepared. Supply the private originals and prepared payload, or install '
                             'FFmpeg/ffprobe and rerun this command; open audio needs neither.')
    python = python_for_checks(env, need_numpy=True)
    run([python, ROOT / 'tools/audio_profiles.py', 'prepare', '--profile', 'riot_en'], env)


def native_command(args, python):
    command = [python, ROOT / 'tools/native_suite.py', '--execute-native', '--use-deployed',
               '--display', args.display, '--presentation-mode', args.presentation_mode,
               '--card-face-cases', 'all', '--card-lifecycle-cases', 'all']
    if args.audio_driver:
        command.extend(['--audio-driver', args.audio_driver])
    if args.verify_release:
        # Measured llvmpipe runs need ~3 hours for 410 faces plus ~1.5 hours
        # for 48 lifecycle cases, before presentation and normal product flow.
        # Keep a finite eight-hour whole-process cap, without dropping checks.
        command.extend(['--verify-restart', '--timeout', '28800', '--frames', '1728000'])
    return command


def multiplayer_command(args, python):
    return [python, ROOT / 'tools/multiplayer_suite.py', '--execute-native', '--use-deployed',
            '--display', args.display]


def acceptance_summary():
    scopes = {
        'A1': 'Current build, regression, packed resources and audio validation',
        'A2': 'All native card-face and lifecycle cases',
        'A3': 'Automated presentation/playback/cleanup only; no human hearing or aesthetic approval',
        'A4': 'Native normal gameplay flow',
        'A5': 'Cross-process save and restore',
        'A6': 'Two local clients; not Steam/public-network certification',
        'A7': 'BaseLib and tested contribution boundaries; not arbitrary third-party compatibility',
        'A8': 'Final ZIP filesystem install/same-ZIP update/uninstall; no installed-fixture game launch',
        'A9': 'Final ZIP inventory, hash and machine summary',
    }
    return {'schema': 1, 'status': 'not_completed', 'human_hearing': 'not_performed',
            'human_visual_review': 'not_performed',
            'items': {key: {'status': 'not_run', 'scope': value} for key, value in scopes.items()}}


def mark(args, *items):
    for item in items:
        args._acceptance['items'][item]['status'] = 'passed'


def deliver(args):
    if not args.verify_release or args.doctor:
        return _deliver(args)
    args._acceptance = acceptance_summary()
    args._active_items = ('A1',)
    directory = ROOT / '.local/release-acceptance'
    dependencies.assert_unredirected(directory)
    directory.mkdir(parents=True, exist_ok=True)
    args._acceptance_dir = Path(tempfile.mkdtemp(prefix='run-', dir=directory))
    try:
        result = _deliver(args)
        if any(item['status'] != 'passed' for item in args._acceptance['items'].values()):
            raise RuntimeError('Release acceptance contains incomplete stages')
        args._acceptance['status'] = 'automated_acceptance_passed'
        return result
    except Exception as error:
        args._acceptance['status'] = 'failed'
        for item in getattr(args, '_active_items', ()):
            if args._acceptance['items'][item]['status'] != 'passed':
                args._acceptance['items'][item]['status'] = (
                    'failed' if len(args._active_items) == 1 else 'group_gate_failed')
        args._acceptance['error'] = str(error)
        raise
    finally:
        summary = args._acceptance
        (args._acceptance_dir / 'summary.json').write_text(
            json.dumps(summary, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        lines = ['# Release automated acceptance', '', 'Status: ' + summary['status'], '',
                 'Human hearing: not performed. Human aesthetic review: not performed.', '',
                 '| Item | Status | Scope |', '|---|---|---|']
        lines += [f"| {key} | {value['status']} | {value['scope']} |"
                  for key, value in summary['items'].items()]
        if 'error' in summary:
            lines += ['', 'Failure: ' + summary['error']]
        (args._acceptance_dir / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('Acceptance summary: ' + str(args._acceptance_dir / 'summary.json'), flush=True)


def _deliver(args):
    settings = preflight(args)
    if args.doctor:
        print('DOCTOR PASS: version/path checks only; no builds or game validation performed.', flush=True)
        return None
    # A directly extracted source overlay can contain unchanged files removed in this
    # revision. Remove only its hash-pinned obsolete list before compiling or discovering tests.
    overlay_cleanup.cleanup(ROOT)
    # A resource-only machine has no valid game installation; do not create a partial
    # development config that native tools could mistake for a configured installation.
    if not args.resources_only:
        save_settings(settings)
    env = toolchain.dotnet_environment(settings['dotnet'])
    if not args.resources_only:
        env['VOLIBEAR_HARMONY'] = str(dev.data_directory(Path(settings['game_dir'])) / '0Harmony.dll')
    python = Path(sys.executable) if args.resources_only else python_for_checks(env)
    prepare_audio(args.audio_profile, env, python)
    if args.resources_only:
        pack = build_assets.build(Path(settings['godot']), args.output or build_assets.PACK,
                                  audio_profile=args.audio_profile, dotnet=settings['dotnet'])
        print('RESOURCE DELIVERY: ' + str(pack) + '; no installer produced.', flush=True)
        return pack

    selected = dependencies.acquire()
    dll = dev.build_mod(settings, fresh=True)
    # The native-metadata harness reads this newly rebuilt DLL. Run the full regression
    # only once, after compilation; a failing stage cannot continue to packaging.
    run([python, ROOT / 'tools/regression.py', '--require-native'], env)
    pack = build_assets.build(Path(settings['godot']), audio_profile=args.audio_profile,
                              dotnet=settings['dotnet'])
    if args.verify_release:
        mark(args, 'A1')
    if args.verify_native:
        game = Path(settings['game_dir'])
        dependencies.install(selected, game=game)
        dev.deploy(game, [dll, ROOT / 'src/Volibear/Volibear.json', pack])
        # The suite owns the single installed-game process and controlled in-process queue.
        if args.verify_release:
            args._active_items = ('A2', 'A3', 'A4', 'A5', 'A7')
        run(native_command(args, python), env)
        if args.verify_release:
            mark(args, 'A2', 'A3', 'A4', 'A5', 'A7')
            # These are actual independent clients. A shared-combat fixture cannot satisfy
            # the network gate, and neither a failed restart nor peer check may package.
            args._active_items = ('A6',)
            run(multiplayer_command(args, python), env)
            mark(args, 'A6')
    output = args.output or (ROOT / '.local/release' /
                            ('Volibear-0.1.0-StS2-0.107.1'
                             + ('-riot_en-private' if args.audio_profile == 'riot_en' else '') + '.zip'))
    if args.verify_release:
        args._active_items = ('A9',)
    result = release_package.package(dll, pack, ROOT / 'src/Volibear/Volibear.json',
                                     ROOT / '.local/dependencies/BaseLib.3.4.7.zip',
                                     ROOT / 'licenses/BaseLib-LICENSE.txt', ROOT / 'docs/INSTALL_ZH.md',
                                     output, audio_profile=args.audio_profile)
    if args.verify_release:
        try:
            from tools import package_lifecycle_acceptance
        except ModuleNotFoundError:
            import package_lifecycle_acceptance
        args._acceptance['package'] = str(result)
        args._active_items = ('A8',)
        lifecycle = package_lifecycle_acceptance.accept(
            result, Path(settings['game_dir']), args._acceptance_dir / 'lifecycle')
        args._acceptance['package_sha256'] = lifecycle['package_sha256']
        args._acceptance['lifecycle_report'] = str(args._acceptance_dir / 'lifecycle/report.json')
        mark(args, 'A8', 'A9')
    print('INSTALLER BUILT: ' + str(result), flush=True)
    print('Evidence: current DLL build + regression + ordinary-Godot packed-resource checks passed; '
          + ('native gameplay/presentation, process restart and two-peer suites passed (see each recorded scope).'
             if args.verify_release else 'single-process native suite passed (see its recorded scope).'
             if args.verify_native else 'native game suite was not requested and is not claimed.'), flush=True)
    return result


def main(argv=None):
    try:
        deliver(arguments(argv))
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('DELIVERY STOPPED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
