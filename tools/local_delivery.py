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
    parser.add_argument('--audio-profile', choices=('open', 'riot_en'), default='open')
    parser.add_argument('--display', choices=('background', 'xvfb'),
                        default='background' if os.name == 'nt' else 'xvfb')
    parser.add_argument('--presentation-mode', choices=('cards', 'actions', 'all'), default='cards')
    parser.add_argument('--audio-driver', help='Real Godot audio driver; required for actions/all native presentation')
    parser.add_argument('--output', type=Path, help='Installer ZIP path; resource-only output must be a .pck beneath .local')
    args = parser.parse_args(argv)
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
        expected_display = 'background' if os.name == 'nt' else 'xvfb'
        if args.display != expected_display:
            raise ValueError('Native validation on this platform requires --display ' + expected_display)
        if os.name != 'nt' and not shutil.which('xvfb-run'):
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
        # A private overlay ZIP may already include the verified prepared clips. A public
        # checkout instead invokes the existing pinned-source downloader/processor once.
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            raise ValueError('Riot audio is not prepared. Supply the private prepared payload, or install '
                             'FFmpeg/ffprobe and rerun this command; open audio needs neither.')
    python = python_for_checks(env, need_numpy=True)
    run([python, ROOT / 'tools/audio_profiles.py', 'prepare', '--profile', 'riot_en'], env)


def native_command(args, python):
    command = [python, ROOT / 'tools/native_suite.py', '--execute-native', '--use-deployed',
               '--display', args.display, '--presentation-mode', args.presentation_mode,
               '--card-face-cases', 'all', '--card-lifecycle-cases', 'all']
    if args.audio_driver:
        command.extend(['--audio-driver', args.audio_driver])
    return command


def deliver(args):
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
    run([python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], env)
    pack = build_assets.build(Path(settings['godot']), audio_profile=args.audio_profile,
                              dotnet=settings['dotnet'])
    if args.verify_native:
        game = Path(settings['game_dir'])
        dependencies.install(selected, game=game)
        dev.deploy(game, [dll, ROOT / 'src/Volibear/Volibear.json', pack])
        # The suite owns the single installed-game process and controlled in-process queue.
        run(native_command(args, python), env)
    output = args.output or (ROOT / '.local/release' /
                            ('Volibear-0.1.0-StS2-0.107.1'
                             + ('-riot_en-private' if args.audio_profile == 'riot_en' else '') + '.zip'))
    result = release_package.package(dll, pack, ROOT / 'src/Volibear/Volibear.json',
                                     ROOT / '.local/dependencies/BaseLib.3.4.7.zip',
                                     ROOT / 'licenses/BaseLib-LICENSE.txt', ROOT / 'docs/INSTALL_ZH.md',
                                     output, audio_profile=args.audio_profile)
    print('INSTALLER BUILT: ' + str(result), flush=True)
    print('Evidence: current DLL build + regression + ordinary-Godot packed-resource checks passed; '
          + ('single-process native suite passed (see its recorded scope).'
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
