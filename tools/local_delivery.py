#!/usr/bin/env python3
"""Build the pinned mod and verified PCK, then package; optionally validate in one game process.

First use: python tools/local_delivery.py --game-dir GAME --godot GODOT_MONO --dotnet DOTNET
Paths are saved locally only after preflight succeeds. --resources-only never produces an installer.
"""
import time
ENTRY_STARTED = time.monotonic()

import argparse
from contextlib import contextmanager
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
    from tools import audio_profiles, build_assets, dependencies, dev, native_python, overlay_cleanup, release_budget, release_package, toolchain
except ModuleNotFoundError:
    import audio_profiles, build_assets, dependencies, dev, native_python, overlay_cleanup, release_budget, release_package, toolchain

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
    parser.add_argument('--force-cold-assets', action='store_true',
                        help='Run the full asset build instead of reusing verified PCK evidence')
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
        # Frame insurance must not expire before the 240fps gameplay-only batch.
        # The CLI supervisor still owns the stricter remaining whole-release budget.
        command.extend(['--verify-restart', '--timeout', '600', '--frames', '216000'])
        if _parallel_native_enabled(args):
            command.append('--parallel-restart')
            if args.presentation_mode == 'all':
                command.append('--parallel-catalog')
    return command


def multiplayer_command(args, python):
    return [python, ROOT / 'tools/multiplayer_suite.py', '--execute-native', '--use-deployed',
            '--display', args.display, '--timeout', '600']


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


def _write_phase_summary(args):
    if not hasattr(args, '_acceptance_dir'):
        return
    # Publish in the same owned directory so forced termination leaves the last
    # complete snapshot, including the currently running phase.
    temporary = args._acceptance_dir / 'summary.pending'
    temporary.write_text(json.dumps(args._acceptance, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args._acceptance_dir / 'summary.json')


@contextmanager
def phase(args, name):
    started = time.monotonic()
    row = {'name': name, 'status': 'running', 'started_monotonic': started,
           'elapsed_seconds': None}
    args._phases.append(row)
    print('RELEASE_PHASE ' + name + ' started', flush=True)
    _write_phase_summary(args)
    try:
        yield
    except BaseException as error:
        row.update(status='failed', error=str(error))
        raise
    else:
        row['status'] = 'completed'
    finally:
        row['elapsed_seconds'] = time.monotonic() - started
        remaining = (max(0, args._release_deadline - time.monotonic())
                     if hasattr(args, '_release_deadline') else None)
        if remaining is not None:
            row['remaining_seconds'] = remaining
        print('RELEASE_PHASE ' + json.dumps(row, sort_keys=True), flush=True)
        _write_phase_summary(args)


def deliver(args):
    args._phases = []
    if not args.verify_release or args.doctor:
        return _deliver(args)
    args._acceptance = acceptance_summary()
    args._acceptance['phases'] = args._phases
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
            if args._acceptance['items'][item]['status'] in ('not_run', 'running'):
                args._acceptance['items'][item]['status'] = (
                    'failed' if len(args._active_items) == 1 else 'group_gate_failed')
        args._acceptance['error'] = str(error)
        raise
    finally:
        summary = args._acceptance
        _write_phase_summary(args)
        lines = ['# Release automated acceptance', '', 'Status: ' + summary['status'], '',
                 'Human hearing: not performed. Human aesthetic review: not performed.', '',
                 '| Item | Status | Scope |', '|---|---|---|']
        lines += [f"| {key} | {value['status']} | {value['scope']} |"
                  for key, value in summary['items'].items()]
        if 'error' in summary:
            lines += ['', 'Failure: ' + summary['error']]
        (args._acceptance_dir / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('Acceptance summary: ' + str(args._acceptance_dir / 'summary.json'), flush=True)


def _parallel_validation(args, regression, assets, env):
    return _parallel_pair(args, (('regression', regression, env, ()),
                                 ('assets', assets, dict(os.environ), ())))


def _parallel_native_enabled(args):
    return (args.verify_release and hasattr(args, '_release_deadline')
            and os.name == 'nt' and args.display == 'background')


def _parallel_native(args, python, env):
    return _parallel_pair(args, (
        ('native_suite', native_command(args, python), env, ('A2', 'A3', 'A4', 'A5', 'A7')),
        ('multiplayer', multiplayer_command(args, python), env, ('A6',))))


def _parallel_pair(args, branches):
    """Exactly two supervisor-owned entrypoints; this thread alone writes phases."""
    if len(branches) != 2:
        raise ValueError('Parallel release gate requires exactly two branches')
    tasks = []

    def finish(task, status, **details):
        row = task['row']
        row.update(status=status, elapsed_seconds=time.monotonic() - row['started_monotonic'],
                   remaining_seconds=max(0, args._release_deadline - time.monotonic()), **details)
        for item in task['items']:
            args._acceptance['items'][item]['status'] = (
                'passed' if status == 'completed' else
                'group_gate_failed' if status == 'failed' and len(task['items']) > 1 else status)
        print('RELEASE_PHASE ' + json.dumps(row, sort_keys=True), flush=True)
        _write_phase_summary(args)

    try:
        for name, command, environment, items in branches:
            if time.monotonic() >= args._release_deadline:
                raise TimeoutError('Release budget exhausted before parallel validation launch')
            row = {'name': name, 'status': 'running', 'started_monotonic': time.monotonic(),
                   'elapsed_seconds': None, 'log': str(args._acceptance_dir / (name + '.log'))}
            args._phases.append(row)
            task = {'row': row, 'command': command, 'process': None, 'stream': None, 'items': items}
            tasks.append(task)
            for item in items:
                args._acceptance['items'][item]['status'] = 'running'
            print('RELEASE_PHASE ' + name + ' started; log=' + row['log'], flush=True)
            _write_phase_summary(args)
            try:
                task['stream'] = Path(row['log']).open('x', encoding='utf-8')
                task['process'] = subprocess.Popen([str(value) for value in command], cwd=ROOT,
                    env=environment, stdout=task['stream'], stderr=subprocess.STDOUT)
                row.update(pid=task['process'].pid, command=[str(value) for value in command])
                _write_phase_summary(args)
            except Exception as error:
                finish(task, 'failed', error=str(error))
                raise
        while True:
            failures = []
            for task in tasks:
                if task['row']['status'] != 'running':
                    continue
                code = task['process'].poll()
                if code is not None:
                    finish(task, 'completed' if code == 0 else 'failed', exit_code=code)
                    if code:
                        failures.append(subprocess.CalledProcessError(code, task['command']))
            if failures:
                raise failures[0]
            if all(task['row']['status'] == 'completed' for task in tasks):
                return
            if time.monotonic() >= args._release_deadline:
                raise TimeoutError('Release budget exhausted during parallel validation')
            time.sleep(min(.05, max(0, args._release_deadline - time.monotonic())))
    finally:
        for task in tasks:
            process = task['process']
            try:
                if process is not None and task['row']['status'] == 'running':
                    code = process.poll()
                    if code is None:
                        finish(task, 'cancel_requested', descendant_cleanup='release-supervisor')
                        process.terminate()
                        try:
                            code = process.wait(timeout=.5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            code = process.wait(timeout=.5)
                        finish(task, 'cancelled', entrypoint_exit_code=code,
                               descendant_cleanup='release-supervisor')
                    else:
                        finish(task, 'completed' if code == 0 else 'failed', exit_code=code)
            except (OSError, subprocess.SubprocessError) as error:
                finish(task, 'cancel_requested', cleanup_error=str(error),
                       descendant_cleanup='release-supervisor')
            finally:
                if task['stream'] is not None:
                    task['stream'].close()


def _deliver(args):
    with phase(args, 'preflight'):
        settings = preflight(args)
    if args.doctor:
        print('DOCTOR PASS: version/path checks only; no builds or game validation performed.', flush=True)
        return None
    with phase(args, 'tools_and_dependencies'):
        # Remove only hash-pinned obsolete overlay files before compiling/discovery.
        overlay_cleanup.cleanup(ROOT)
        # Resource-only delivery must not create a partial game configuration.
        if not args.resources_only:
            save_settings(settings)
        env = toolchain.dotnet_environment(settings['dotnet'])
        if not args.resources_only:
            env['VOLIBEAR_HARMONY'] = str(dev.data_directory(Path(settings['game_dir'])) / '0Harmony.dll')
        python = Path(sys.executable) if args.resources_only else python_for_checks(env)
        host_python, native_env = python, env
        if args.verify_native:
            host_python, native_env = native_python.native_runtime(python, env)
        prepare_audio(args.audio_profile, env, python)
        if not args.resources_only:
            selected = dependencies.acquire()
    if args.resources_only:
        with phase(args, 'assets'):
            pack = build_assets.build(Path(settings['godot']), args.output or build_assets.PACK,
                                      audio_profile=args.audio_profile, dotnet=settings['dotnet'],
                                      reuse=not args.force_cold_assets)
        print('RESOURCE DELIVERY: ' + str(pack) + '; no installer produced.', flush=True)
        return pack

    with phase(args, 'build'):
        dll = dev.build_mod(settings, fresh=True)
    # The native-metadata harness reads this newly rebuilt DLL. Run the full regression
    # only once, after compilation; a failing stage cannot continue to packaging.
    regression = [python, ROOT / 'tools/regression.py', '--require-native', '--jobs', '6']
    if args.verify_release and hasattr(args, '_release_deadline'):
        pack = build_assets.PACK
        assets = [sys.executable, ROOT / 'tools/build_assets.py', '--godot', settings['godot'],
                  '--dotnet', settings['dotnet'], '--audio-profile', args.audio_profile, '--output', pack]
        if args.force_cold_assets:
            assets.append('--force-cold')
        _parallel_validation(args, regression, assets, env)
    else:
        # Direct API callers/non-release work retain the existing serial contract.
        with phase(args, 'regression'):
            run(regression, env)
        with phase(args, 'assets'):
            pack = build_assets.build(Path(settings['godot']), audio_profile=args.audio_profile,
                                      dotnet=settings['dotnet'], reuse=not args.force_cold_assets)
    if args.verify_release:
        mark(args, 'A1')
    if args.verify_native:
        game = Path(settings['game_dir'])
        with phase(args, 'deploy'):
            dependencies.install(selected, game=game)
            dev.deploy(game, [dll, ROOT / 'src/Volibear/Volibear.json', pack])
        # Only Windows private desktops have no shared override.cfg writer.
        if _parallel_native_enabled(args):
            args._active_items = ('A2', 'A3', 'A4', 'A5', 'A6', 'A7')
            _parallel_native(args, host_python, native_env)
        else:
            # Preserve serial native scheduling for direct callers and every POSIX display.
            if args.verify_release:
                args._active_items = ('A2', 'A3', 'A4', 'A5', 'A7')
            with phase(args, 'native_suite'):
                run(native_command(args, host_python), native_env)
            if args.verify_release:
                mark(args, 'A2', 'A3', 'A4', 'A5', 'A7')
                args._active_items = ('A6',)
                with phase(args, 'multiplayer'):
                    run(multiplayer_command(args, host_python), native_env)
                mark(args, 'A6')
    output = args.output or (ROOT / '.local/release' /
                            ('Volibear-0.1.0-StS2-0.107.1'
                             + ('-riot_en-private' if args.audio_profile == 'riot_en' else '') + '.zip'))
    if args.verify_release:
        args._active_items = ('A9',)
    with phase(args, 'package'):
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
        with phase(args, 'install_lifecycle'):
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
        args = arguments(argv)
        permit = release_budget.worker_permit()
        if permit is not None and not args.verify_release:
            raise ValueError('A release worker permit requires --verify-release')
        if args.verify_release and not args.doctor and permit is None:
            return release_budget.supervise(
                [sys.executable, Path(__file__).resolve(), *(sys.argv[1:] if argv is None else argv)],
                ROOT, started=ENTRY_STARTED)
        if permit is not None:
            args._release_deadline = permit['deadline']
        deliver(args)
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('DELIVERY STOPPED: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
