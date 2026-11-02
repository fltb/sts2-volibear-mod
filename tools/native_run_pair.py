#!/usr/bin/env python3
"""Run normal three-battle Save-and-Quit, then restart the same new private profile.

Explicit --execute-native only. Reuses headless.run_once, its native-input probe and
independent oracle. Never builds/deploys, imports an existing profile, edits a native
checkpoint, or sends OS input. Reports remain in ignored artifacts/native-run/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
import headless as h
from native_run_evidence import native_run_evidence, native_run_pair_evidence
from save_load_evidence import eq
from save_load_profile import create_owned_profile, shader_directory_budget

COMMON_CHECKS = frozenset({
    'exited_zero', 'steam_disabled', 'no_cloud_backend', 'no_runtime_errors',
    'mod_initialized', 'runtime_isolation', 'teardown_matches_stock',
    'stock_control_success',
})
REQUIRED_CHECKS = COMMON_CHECKS | {'native_run_assertions'}
SCOPE = 'normal-native-run-three-battles-save-restart-continue-one-battle'


def validate_options(timeout, frames, display):
    if type(timeout) is not int or not 30 <= timeout <= 300:
        raise ValueError('timeout must be an integer in 30..300 seconds per phase')
    if type(frames) is not int or not 1000 <= frames <= 60000:
        raise ValueError('frames must be an integer in 1000..60000 per phase')
    allowed = ('background',) if h.IS_WINDOWS else ('headless', 'xvfb')
    if display not in allowed:
        raise ValueError('Native run pairs require ' + '/'.join(allowed) + ' on this platform')
    h.display_command([], display)


def successful_stock(evidence):
    return (isinstance(evidence, dict) and evidence.get('successful') is True
            and type(evidence.get('exit_code')) is int and evidence['exit_code'] == 0
            and evidence.get('timed_out') is False and evidence.get('runtime_errors') == [])


def read_checkpoint(checkpoint, user_root):
    """Read the engine's file; never repair, rewrite or normalize its bytes."""
    checkpoint, user_root = Path(checkpoint), Path(user_root)
    if checkpoint.resolve() != checkpoint or not checkpoint.is_relative_to(user_root):
        raise ValueError('Native checkpoint escaped or redirected the newly owned profile')
    if not checkpoint.is_file():
        raise ValueError('Native checkpoint is missing')
    data = checkpoint.read_bytes()
    native_save = json.loads(data)
    if not data or not isinstance(native_save, dict):
        raise ValueError('Native checkpoint must be a nonempty JSON object')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'nativeSave': native_save}


def phase_evidence(report, mode, pair, stock, stock_evidence):
    """Re-read this invocation's log; neither report.status nor its verdict is authority."""
    errors = []
    if not isinstance(report, dict):
        return '', {}, ['Native runner did not return a structured report']
    checks = report.get('checks')
    if (not isinstance(checks, dict) or not REQUIRED_CHECKS <= checks.keys()
            or any(value is not True for value in checks.values())):
        errors.append('Every common and native-run gate must be present and literally true')
    if report.get('status') != 'passed' or report.get('scenario') != 'native-run':
        errors.append('Native runner phase failed or belongs to another scenario')
    if not successful_stock(stock_evidence):
        errors.append('Fresh stock control did not pass')
    token = report.get('run_id')
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,96}', token):
        return '', {}, errors + ['Invalid invocation token']
    directory = h.ROOT / 'artifacts/headless' / token
    if directory.resolve() != directory:
        return '', {}, errors + ['Invocation artifacts were redirected']
    try:
        text = h.combined_log(directory)
    except (OSError, ValueError) as error:
        return '', {}, errors + ['Cannot re-read native phase log: ' + str(error)]
    common = h.evaluate(report.get('exit_code'), report.get('timed_out'), text, stock)
    if (type(report.get('exit_code')) is not int or report.get('timed_out') is not False
            or not COMMON_CHECKS - {'stock_control_success'} <= common.keys()
            or any(value is not True for value in common.values())):
        errors.append('Independent common/runtime/isolation/teardown checks failed')
    evidence = native_run_evidence(text, token, mode, pair)
    errors.extend(evidence.get('errors', ['Missing native oracle result']))
    return text, evidence, errors


def checkpoint_gate(evidence, checkpoint, user_root):
    try:
        events = evidence['observation']['events']
        recorded = [event['data'] for event in events if event['kind'] == 'checkpoint']
        if len(recorded) != 1 or not eq(read_checkpoint(checkpoint, user_root), recorded[0]):
            return ['Native disk checkpoint bytes/hash/JSON differ from the completed prepare phase']
    except (OSError, ValueError, TypeError, KeyError) as error:
        return ['Cannot verify native checkpoint before Continue: ' + str(error)]
    return []


def run_pair(game, timeout=300, frames=60000, display=None):
    display = display or ('background' if h.IS_WINDOWS else 'headless')
    validate_options(timeout, frames, display)  # Before profile creation or launch.
    game = Path(game).expanduser().resolve()
    h.validate_game(game)
    pair_dir = ROOT / 'artifacts/native-run' / h.new_run_id()
    pair_dir.mkdir(parents=True, exist_ok=False)
    profile = create_owned_profile()
    env = h.isolated_env(profile)
    for key in list(env):
        if key.startswith(('VOLIBEAR_TEST_', 'VOLIBEAR_SAVE_', 'VOLIBEAR_NATIVE_RUN_')):
            del env[key]
    user_root = h.user_data_root(profile)
    env['VOLIBEAR_TEST_DATA_ROOT'] = str(user_root)
    checkpoint = user_root / 'default/1/modded/profile1/saves/current_run.save'
    if checkpoint.exists():
        raise ValueError('Freshly owned profile unexpectedly contains an existing run')
    settings = user_root / 'default/1/settings.save'
    settings.parent.mkdir(parents=True, exist_ok=True)
    with settings.open('x', encoding='utf-8') as stream:
        json.dump({'schema_version': 5, 'mod_settings': {'mods_enabled': True},
                   'seen_ea_disclaimer': True, 'skip_intro_logo': True,
                   'fullscreen': False, 'window_size': {'X': 1280, 'Y': 720},
                   'window_position': {'X': 64, 'Y': 64},
                   'language': 'zhs', 'limit_fps_in_background': False,
                   'vsync': 'off', 'fps_limit': 60}, stream)
        stream.write('\n')
    profile_record = {'pair': pair_dir.name, 'profile': str(profile), 'userRoot': str(user_root),
                      'checkpointPath': str(checkpoint),
                      'shaderDirectoryBudget': shader_directory_budget(user_root) if h.IS_WINDOWS else None}
    (pair_dir / 'profile.json').write_text(json.dumps(profile_record, indent=2) + '\n', encoding='utf-8')
    result = {'schema': 1, 'pair': pair_dir.name, 'scope': SCOPE, **profile_record,
              'display': display, 'passed': False, 'phases': [], 'errors': [],
              'pair_evidence': None}

    def finish():
        (pair_dir / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result['report'] = str(pair_dir / 'report.json')
        return result

    stock, stock_evidence = h.stock_teardown(game, timeout, frames, display)
    result['stock'] = stock_evidence
    if not successful_stock(stock_evidence):
        result['errors'].append('stock-control-failed; no native-run phase launched')
        return finish()

    texts, tokens = [], []
    for mode in ('three-battle-save', 'resume'):
        try:
            report = h.run_once(game, timeout, frames, scenario='native-run', display=display,
                                stock=stock, stock_evidence=stock_evidence,
                                native_run_mode=mode, native_run_pair=pair_dir.name,
                                _profile_env=env)
            text, evidence, errors = phase_evidence(report, mode, pair_dir.name, stock, stock_evidence)
            if mode == 'three-battle-save' and not errors:
                errors.extend(checkpoint_gate(evidence, checkpoint, user_root))
            result['phases'].append({'mode': mode, 'run_id': report.get('run_id'),
                                     'checks': report.get('checks'), 'errors': errors,
                                     'observed_coverage': evidence.get('observed_coverage', [])})
        except Exception as error:
            result['errors'].append(mode + ': native runner failed: ' + type(error).__name__ + ': ' + str(error))
            return finish()
        if errors:
            result['errors'].extend(mode + ': ' + error for error in errors)
            return finish()  # Never launch Continue after any failed prepare gate.
        texts.append(text)
        tokens.append(report['run_id'])

    pair_evidence = native_run_pair_evidence(texts[0], tokens[0], texts[1], tokens[1], pair_dir.name)
    result['pair_evidence'] = pair_evidence
    result['errors'].extend(pair_evidence['errors'])
    result['passed'] = not result['errors']
    return finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native', action='store_true', help='Authorize the bounded native pair; never builds or deploys')
    parser.add_argument('--display', choices=['background', 'headless', 'xvfb'],
                        default='background' if h.IS_WINDOWS else 'headless')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--frames', type=int, default=60000)
    args = parser.parse_args(argv)
    if not args.execute_native:
        parser.error('--execute-native is required; no game was launched')
    try:
        validate_options(args.timeout, args.frames, args.display)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    game = Path(h.config()['game_dir']).expanduser().resolve()
    result = run_pair(game, args.timeout, args.frames, args.display)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
