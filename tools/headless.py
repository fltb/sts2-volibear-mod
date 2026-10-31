#!/usr/bin/env python3
"""Bounded real-game discovery runner; no combat pass without driver evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import uuid

from dev import ROOT, config, validate_game


def isolated_env(directory):
    env = os.environ.copy()
    for key, child in [('HOME', 'home'), ('XDG_DATA_HOME', 'data'),
                       ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')]:
        path = directory / child
        path.mkdir(parents=True)
        env[key] = str(path)
    return env


def evaluate(code, timed_out, log):
    checks = {
        'exited_zero': code == 0 and not timed_out,
        'steam_disabled': 'Steam initialization skipped' in log,
        'no_cloud_backend': 'write saves to steam storage' not in log,
        'no_engine_errors': not any(s in log for s in ('ERROR:', 'SCRIPT ERROR:', '[ERROR]')),
        'mod_initialized': '[Volibear] LOAD_OK' in log,
        'runtime_isolation': '[Volibear] ISOLATION_OK steam=false' in log,
    }
    return checks


def scenario_evidence(log, run_id, scenario):
    prefix = '[Volibear] BASELINE_RESULT '
    records = []
    for line in log.splitlines():
        if line.startswith(prefix):
            try:
                record = json.loads(line[len(prefix):])
            except json.JSONDecodeError:
                return None, False
            if not isinstance(record, dict):
                return None, False
            records.append(record)
    if len(records) != 1:
        return None, False
    result = records[0]
    valid = (result.get('token') == run_id and result.get('scenario') == scenario
             and result.get('passed') is True and result.get('testMode') is False
             and result.get('api') == 'DamageCmd.Attack'
             and result.get('resultCount') == 1
             and type(result.get('before')) is int and type(result.get('after')) is int
             and result['before'] - result['after'] == 6
             and type(result.get('roundBefore')) is int
             and type(result.get('roundAfter')) is int
             and result['roundAfter'] == result['roundBefore'] + 1
             and result.get('cardApi') == 'CardCmd.AutoPlay:StrikeIronclad'
             and type(result.get('cardTargetBefore')) is int
             and type(result.get('cardTargetAfter')) is int
             and result['cardTargetBefore'] - result['cardTargetAfter'] == (7 if result.get('engageEnabled') is True else 6))
    return result, valid


def engage_evidence(result, expected):
    """Validate measured prototype evidence independently of the driver's pass bit."""
    if not isinstance(result, dict) or result.get('engageEnabled') is not expected:
        return False
    if not expected:
        return result.get('engage') is None and result.get('duplicate') is None and result.get('skippedActions') == 0
    return (result.get('engage') == {'Performed': True, 'Absorbed': 3, 'Completed': True}
            and result.get('duplicate') == {'Performed': False, 'Absorbed': 0, 'Completed': False}
            and type(result.get('skippedActions')) is int and result['skippedActions'] == 1
            and result.get('responseCount') == 1 and result.get('responseBlockBefore') == 27
            and result.get('responseBlockAfter') == 30 and result.get('followupDamage') == 1
            and result.get('engageOrder') == ['pre-effect-finished', 'enemy-action-finished',
                'completion-response', 'duplicate-rejected', 'remaining-card-effect'])


def wait_owned_process(process, timeout):
    """Wait for our session leader and always remove surviving group children."""
    timed_out = False
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = process.wait()
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return code, timed_out


def run_once(game, timeout, frames, scenario='discovery', display='headless'):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    directory = ROOT / 'artifacts/headless' / run_id
    directory.mkdir(parents=True)
    env = isolated_env(directory)
    env['VOLIBEAR_TEST_DATA_ROOT'] = str(directory / 'data/SlayTheSpire2')
    # Only this fresh, offline test profile opts into loading mods.
    # Never read, copy, or edit the operator's normal settings or saves.
    settings = directory / 'data/SlayTheSpire2/default/1/settings.save'
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        'schema_version': 5, 'mod_settings': {'mods_enabled': True},
        'seen_ea_disclaimer': True, 'skip_intro_logo': True,
        'fullscreen': False, 'language': 'eng',
    }) + '\n')
    command = [str(game / 'SlayTheSpire2'), '--headless', '--audio-driver', 'Dummy',
               '--force-steam=off', '--quit-after', str(frames),
               '--log-file', str(directory / 'game.log')]
    env['VOLIBEAR_TEST_TOKEN'] = run_id
    # Optional diagnostic adapter; the shipped extension may bind its own symbols.
    # Never enable this unverified workaround implicitly.
    adapter_enabled = os.environ.get('VOLIBEAR_TEST_AUDIO_ADAPTER') == '1'
    if adapter_enabled:
        adapter = ROOT / '.local/libvolibear-test-audio.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(ROOT / 'tools/fmod_nosound.c'), '-ldl', '-o', str(adapter)], check=True)
        # ld.so splits LD_PRELOAD on spaces even inside a colon-delimited path.
        # Use a no-space alias to the existing game directory; copy no binaries.
        alias = ROOT / '.local/game-audio-link'
        if not alias.exists():
            alias.symlink_to(game, target_is_directory=True)
        if alias.resolve() != game:
            raise RuntimeError('Audio diagnostic game alias points elsewhere')
        env['LD_PRELOAD'] = ':'.join([str(adapter), str(alias / 'libGodotFmod.linux.template_release.x86_64.so')]) + (':' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
    if scenario == 'baseline':
        # MonoMod's native exception helper needs globally visible libgcc unwind symbols.
        # This is scoped to the child; it changes no system loader configuration.
        unwind = Path('/lib/x86_64-linux-gnu/libgcc_s.so.1')
        if not unwind.is_file():
            raise RuntimeError('Baseline Harmony probe requires the host libgcc_s.so.1')
        env['LD_PRELOAD'] = str(unwind) + (' ' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
        env['VOLIBEAR_TEST_SCENARIO'] = scenario
        command.append('--bootstrap')
    if display == 'xvfb':
        command.remove('--headless')
        command.remove('--audio-driver')
        command.remove('Dummy')
        command.extend(['--display-driver', 'x11', '--rendering-method', 'gl_compatibility'])
        command = ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24', *command]
    timed_out = False
    with (directory / 'stdout.log').open('w') as output:
        process = subprocess.Popen(command, cwd=game, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        code, timed_out = wait_owned_process(process, timeout)
    log = (directory / 'stdout.log').read_text(errors='replace')
    checks = evaluate(code, timed_out, log)
    if adapter_enabled:
        checks['audio_adapter_active'] = '[Volibear] AUDIO_OUTPUT nosound' in log
    scenario_result = None
    if scenario != 'discovery':
        scenario_result, checks['scenario_assertions'] = scenario_evidence(log, run_id, scenario)
        checks['engage_variant_assertions'] = engage_evidence(
            scenario_result, env.get('VOLIBEAR_TEST_ENGAGE') == '1')
    shutdown_marker = '[Volibear] SHUTDOWN_BEGIN ' + run_id
    before_shutdown, marker, after_shutdown = log.partition(shutdown_marker)
    def error_lines(text):
        return [line for line in text.splitlines()
                if any(tag in line for tag in ('ERROR:', 'SCRIPT ERROR:', '[ERROR]'))]
    diagnostics = {
        'shutdown_marker_seen': bool(marker),
        'runtime_errors': error_lines(before_shutdown),
        'shutdown_errors': error_lines(after_shutdown) if marker else [],
    }
    # Phase classification is diagnostic only: every engine error still fails.
    report = {
        'schema': 1, 'run_id': run_id, 'mode': 'real-game-' + display, 'scenario': scenario,
        'game_version': '0.107.1', 'game_commit': '59260271',
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'exit_code': code, 'timed_out': timed_out, 'checks': checks,
        'diagnostics': diagnostics,
        'status': 'passed' if all(checks.values()) else 'failed',
        'combat_tests': scenario_result or 'not_run', 'command': command,
    }
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': str(directory / 'report.json'), 'status': report['status'], 'checks': checks}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--display', choices=['headless', 'xvfb'], default='headless')
    parser.add_argument('--scenario', choices=['discovery', 'baseline'], default='discovery')
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--frames', type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10 or not 5 <= args.timeout <= 300 or not 1 <= args.frames <= 10000:
        parser.error('repeat 1..10, timeout 5..300, frames 1..10000 required')
    game = Path(config()['game_dir']).expanduser().resolve()
    validate_game(game)
    subprocess.run([os.sys.executable, 'tools/dev.py', 'test'], cwd=ROOT, check=True)
    subprocess.run([os.sys.executable, 'tools/dev.py', 'build'], cwd=ROOT, check=True)
    subprocess.run([os.sys.executable, 'tools/dev.py', 'deploy'], cwd=ROOT, check=True)
    reports = [run_once(game, args.timeout, args.frames, args.scenario, args.display) for _ in range(args.repeat)]
    return 0 if all(r['status'] == 'passed' for r in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
