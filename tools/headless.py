#!/usr/bin/env python3
"""Bounded real-game discovery runner; no combat pass without driver evidence."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import uuid

from dev import ROOT, config, game_executable, validate_game

IS_WINDOWS = os.name == 'nt'
USER_DATA_NAME = 'SlayTheSpire2'
# Every directory variable that can redirect user:// is repointed per run.
ISOLATION_BINDINGS = ([('HOME', 'home'), ('APPDATA', 'appdata'), ('LOCALAPPDATA', 'localappdata')]
                      if IS_WINDOWS else
                      [('HOME', 'home'), ('XDG_DATA_HOME', 'data'),
                       ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')])


def isolated_env(directory):
    env = os.environ.copy()
    for key, child in ISOLATION_BINDINGS:
        path = directory / child
        path.mkdir(parents=True)
        env[key] = str(path)
    return env


def user_data_root(directory):
    """Godot resolves user:// from APPDATA on Windows and XDG_DATA_HOME elsewhere."""
    return directory / ('appdata' if IS_WINDOWS else 'data') / USER_DATA_NAME


ERROR_TAGS = ('ERROR:', 'SCRIPT ERROR:', '[ERROR]')
# Godot's teardown report. It names a resource category and a count; counts vary per run,
# categories do not, so only the categories can be compared with the stock control.
TEARDOWN_TAGS = ('leaked at exit', 'were leaked', 'still in use at exit', 'instances leaked')


def error_lines(text):
    return [line for line in text.splitlines() if any(tag in line for tag in ERROR_TAGS)]


def is_teardown(line):
    return any(tag in line for tag in TEARDOWN_TAGS)


def teardown_categories(lines):
    return {re.sub(r'\d+', '#', line).strip() for line in lines if is_teardown(line)}


def evaluate(code, timed_out, log, stock_teardown=None):
    errors = error_lines(log)
    runtime = [line for line in errors if not is_teardown(line)]
    teardown = [line for line in errors if is_teardown(line)]
    checks = {
        'exited_zero': code == 0 and not timed_out,
        'steam_disabled': 'Steam initialization skipped' in log,
        'no_cloud_backend': 'write saves to steam storage' not in log,
        'no_runtime_errors': not runtime,
        'mod_initialized': '[Volibear] LOAD_OK' in log,
        'runtime_isolation': '[Volibear] ISOLATION_OK steam=false' in log,
    }
    if stock_teardown is not None:
        # The shipped game leaks renderer/text resources on every headless exit, with or
        # without mods. The gate accepts only the categories the stock run itself produces.
        checks['teardown_matches_stock'] = teardown_categories(teardown) <= stock_teardown
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


if IS_WINDOWS:
    # A job object is the Windows ownership boundary: the whole tree dies with the handle,
    # which a renamed or orphaned child cannot escape the way a PID-only taskkill can.
    _PROCESS_SET_QUOTA = 0x0100
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _WAIT_TIMEOUT = 0x102
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9

    class _JobBasicLimits(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', ctypes.c_uint32),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', ctypes.c_uint32),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', ctypes.c_uint32),
                    ('SchedulingClass', ctypes.c_uint32)]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class _JobExtendedLimits(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _JobBasicLimits),
                    ('IoInfo', _IoCounters),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    _kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                  ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _kernel32.WaitForSingleObject.restype = ctypes.c_uint32


def _create_job():
    if not IS_WINDOWS:
        return None
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), 'CreateJobObject failed')
    limits = _JobExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not _kernel32.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                             ctypes.byref(limits), ctypes.sizeof(limits)):
        _kernel32.CloseHandle(job)
        raise OSError(ctypes.get_last_error(), 'SetInformationJobObject failed')
    return job


def _assign_job(job, process):
    """Own an already running process. A process that exited first leaves nothing to own."""
    if job is None:
        return False
    handle = _kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, process.pid)
    if not handle:
        return False
    try:
        return bool(_kernel32.AssignProcessToJobObject(job, handle))
    finally:
        _kernel32.CloseHandle(handle)


def _terminate_job(job):
    if job is None or not IS_WINDOWS:
        return False
    return bool(_kernel32.TerminateJobObject(job, 1))


def close_owned(job):
    if job is not None and IS_WINDOWS:
        _kernel32.CloseHandle(job)


def process_alive(pid):
    if IS_WINDOWS:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            return _kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT
        finally:
            _kernel32.CloseHandle(handle)
    status = Path(f'/proc/{pid}/stat')
    if not status.exists():
        return False
    return status.read_text().split()[2] != 'Z'


def _terminate(process, job, force):
    if IS_WINDOWS:
        # Windows has no SIGTERM for GUI processes; the job tree is the owned boundary.
        if _terminate_job(job):
            return
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(process.pid)],
                       capture_output=True)
        return
    try:
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass


def spawn_owned(command, cwd, env, stdout):
    """Start a process in its own ownership boundary and return (process, job)."""
    if IS_WINDOWS:
        job = _create_job()
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                                   stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        if not _assign_job(job, process):
            close_owned(job)
            job = None
        return process, job
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                               stderr=subprocess.STDOUT, start_new_session=True)
    return process, None


def wait_owned_process(process, timeout, job=None):
    """Wait for our session leader and always remove surviving group children."""
    timed_out = False
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(process, job, force=False)
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _terminate(process, job, force=True)
            code = process.wait()
    finally:
        _terminate(process, job, force=True)
    return code, timed_out


def combined_log(directory):
    """Prefer the engine's own log; GUI-subsystem processes may not write redirected stdout."""
    engine = directory / 'game.log'
    if engine.is_file() and engine.stat().st_size:
        return engine.read_text(errors='replace')
    return (directory / 'stdout.log').read_text(errors='replace')


def new_run_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]


def prepare_run(game, run_id, frames):
    directory = ROOT / 'artifacts/headless' / run_id
    directory.mkdir(parents=True)
    env = isolated_env(directory)
    env['VOLIBEAR_TEST_DATA_ROOT'] = str(user_data_root(directory))
    # Only this fresh, offline test profile opts into loading mods.
    # Never read, copy, or edit the operator's normal settings or saves.
    settings = user_data_root(directory) / 'default/1/settings.save'
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        'schema_version': 5, 'mod_settings': {'mods_enabled': True},
        'seen_ea_disclaimer': True, 'skip_intro_logo': True,
        'fullscreen': False, 'language': 'eng',
    }) + '\n')
    env['VOLIBEAR_TEST_TOKEN'] = run_id
    command = [str(game_executable(game)), '--headless', '--audio-driver', 'Dummy',
               '--force-steam=off', '--quit-after', str(frames),
               '--log-file', str(directory / 'game.log')]
    return directory, env, command


def launch(game, directory, env, command, timeout):
    with (directory / 'stdout.log').open('w') as output:
        process, job = spawn_owned(command, game, env, output)
        try:
            return wait_owned_process(process, timeout, job)
        finally:
            close_owned(job)


def stock_teardown(game, timeout, frames):
    """Measure the shipped game's own exit signature with mod initialization disabled."""
    run_id = new_run_id()
    directory, env, command = prepare_run(game, run_id, frames)
    command.append('--nomods')
    code, timed_out = launch(game, directory, env, command, timeout)
    categories = teardown_categories(error_lines(combined_log(directory)))
    return categories, {'run_id': run_id, 'exit_code': code, 'timed_out': timed_out,
                        'categories': sorted(categories)}


def run_once(game, timeout, frames, scenario='discovery', display='headless',
             stock=None, stock_evidence=None):
    run_id = new_run_id()
    directory, env, command = prepare_run(game, run_id, frames)
    # Optional diagnostic adapter; the shipped extension may bind its own symbols.
    # Never enable this unverified workaround implicitly.
    adapter_enabled = os.environ.get('VOLIBEAR_TEST_AUDIO_ADAPTER') == '1'
    if adapter_enabled:
        if IS_WINDOWS:
            raise RuntimeError('The FMOD NOSOUND adapter is a POSIX LD_PRELOAD test; '
                               'Windows headless initializes FMOD with --audio-driver Dummy')
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
        if not IS_WINDOWS:
            unwind = Path('/lib/x86_64-linux-gnu/libgcc_s.so.1')
            if not unwind.is_file():
                raise RuntimeError('Baseline Harmony probe requires the host libgcc_s.so.1')
            env['LD_PRELOAD'] = str(unwind) + (' ' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
        env['VOLIBEAR_TEST_SCENARIO'] = scenario
        command.append('--bootstrap')
    if display == 'xvfb':
        if IS_WINDOWS:
            raise RuntimeError('xvfb is a POSIX virtual display; Windows runs --headless only')
        command.remove('--headless')
        command.remove('--audio-driver')
        command.remove('Dummy')
        command.extend(['--display-driver', 'x11', '--rendering-method', 'gl_compatibility'])
        command = ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24', *command]
    code, timed_out = launch(game, directory, env, command, timeout)
    log = combined_log(directory)
    checks = evaluate(code, timed_out, log, stock)
    if adapter_enabled:
        checks['audio_adapter_active'] = '[Volibear] AUDIO_OUTPUT nosound' in log
    scenario_result = None
    if scenario != 'discovery':
        scenario_result, checks['scenario_assertions'] = scenario_evidence(log, run_id, scenario)
        checks['engage_variant_assertions'] = engage_evidence(
            scenario_result, env.get('VOLIBEAR_TEST_ENGAGE') == '1')
    shutdown_marker = '[Volibear] SHUTDOWN_BEGIN ' + run_id
    before_shutdown, marker, after_shutdown = log.partition(shutdown_marker)
    teardown_errors = [line for line in error_lines(log) if is_teardown(line)]
    def runtime_lines(text):
        return [line for line in error_lines(text) if not is_teardown(line)]
    diagnostics = {
        'shutdown_marker_seen': bool(marker),
        'runtime_errors': runtime_lines(before_shutdown),
        'shutdown_errors': runtime_lines(after_shutdown) if marker else [],
        'engine_teardown_errors': teardown_errors,
        'teardown_categories': sorted(teardown_categories(teardown_errors)),
        'stock_teardown_control': stock_evidence,
    }
    # Phase classification is diagnostic only: every engine error still fails.
    report = {
        'schema': 1, 'run_id': run_id, 'mode': 'real-game-' + display, 'scenario': scenario,
        'platform': os.name,
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
    subprocess.run([sys.executable, 'tools/dev.py', 'test'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/dev.py', 'build'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/dev.py', 'deploy'], cwd=ROOT, check=True)
    # One control launch per invocation defines the exit signature the shipped game produces
    # on its own, so teardown noise is attributed instead of waived.
    stock, stock_evidence = stock_teardown(game, args.timeout, args.frames)
    print(json.dumps({'stock_teardown_control': stock_evidence}))
    reports = [run_once(game, args.timeout, args.frames, args.scenario, args.display,
                        stock, stock_evidence) for _ in range(args.repeat)]
    return 0 if all(r['status'] == 'passed' for r in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
