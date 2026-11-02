#!/usr/bin/env python3
"""Bounded native ENet acceptance: one stock control and two concurrent game peers.

Build/deploy first with local_delivery.py. Requires --execute-native --use-deployed.
Each peer has its own isolated profile and one background game process for all
stages, including disconnect and native checkpoint rejoin. No OS/input simulation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import headless as h
from multiplayer_evidence import check_pair
from save_load_pair import native_pid, phase_command, successful_stock


def deployed_hashes(game):
    folder = game / 'mods' / 'Volibear'
    if folder.is_symlink() or folder.resolve() != folder.absolute():
        raise ValueError('Deployed mod directory is redirected')
    hashes = {}
    for name in ('Volibear.dll', 'Volibear.pck', 'Volibear.json'):
        path = folder / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Build/deploy the complete candidate first: ' + str(path))
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def free_loopback_port():
    # The native host binds immediately afterwards. An intervening bind fails the
    # native listen and the entire suite; it never silently selects a remote host.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def peer_environment(env, *, pair, role, control, port):
    env = dict(env)
    retained = {'VOLIBEAR_TEST_DATA_ROOT', 'VOLIBEAR_TEST_TOKEN', 'VOLIBEAR_TEST_ARTIFACT_DIR',
                'VOLIBEAR_TEST_PRIVATE_DESKTOP', 'VOLIBEAR_TEST_FAST_MODE'}
    for name in list(env):
        if name.startswith(('VOLIBEAR_TEST_', 'VOLIBEAR_SAVE_', 'VOLIBEAR_NATIVE_RUN_', 'VOLIBEAR_MULTIPLAYER_')) and name not in retained:
            del env[name]
    env.update(VOLIBEAR_TEST_SCENARIO='multiplayer-suite', VOLIBEAR_MULTIPLAYER_PAIR=pair,
               VOLIBEAR_MULTIPLAYER_ROLE=role, VOLIBEAR_MULTIPLAYER_CONTROL=str(control),
               VOLIBEAR_MULTIPLAYER_PORT=str(port))
    if not h.IS_WINDOWS:
        unwind = Path('/lib/x86_64-linux-gnu/libgcc_s.so.1')
        if not unwind.is_file():
            raise RuntimeError('Native Harmony acceptance requires the host libgcc_s.so.1')
        env['LD_PRELOAD'] = str(unwind) + (' ' + env['LD_PRELOAD'] if env.get('LD_PRELOAD') else '')
    return env


def launch_peer(game, directory, env, command, timeout, display, stock, stock_evidence):
    with (directory / 'stdout.log').open('w', encoding='utf-8') as output:
        process, job = h.spawn_owned(command, game, env, output,
                                     window=h.IS_WINDOWS and display == 'background')
        pid = process.pid
        try:
            code, timed_out = h.wait_owned_process(process, timeout, job)
        finally:
            h.close_owned(job)
    errors = []
    try:
        pid = native_pid(directory, display, pid, env['VOLIBEAR_TEST_TOKEN'], game)
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append('native-process-binding: ' + str(error))
        pid = -1
    log = h.combined_log(directory)
    checks = h.evaluate(code, timed_out, log, stock)
    checks['stock_control_success'] = successful_stock(stock_evidence)
    checks['native_process_binding'] = pid > 0 and not errors
    report = dict(directory=str(directory), pid=pid, token=env['VOLIBEAR_TEST_TOKEN'], command=command,
                  user_root=env['VOLIBEAR_TEST_DATA_ROOT'], exit_code=code, timed_out=timed_out,
                  checks=checks, errors=errors)
    (directory / 'multiplayer-process.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report, log


def run_suite(game, *, display=None, timeout=900, frames=108000):
    display = display or ('background' if h.IS_WINDOWS else 'xvfb')
    if display not in (('background',) if h.IS_WINDOWS else ('xvfb', 'window')):
        raise ValueError('Multiplayer suite requires a private background desktop on Windows or xvfb/window on POSIX')
    if type(timeout) is not int or not 120 <= timeout <= 14400:
        raise ValueError('timeout must be an integer in 120..14400 seconds per peer')
    if type(frames) is not int or not 7200 <= frames <= 864000:
        raise ValueError('frames must be an integer in 7200..864000 per peer')
    h.display_command([], display)
    game = Path(game).expanduser().resolve()
    h.validate_game(game)
    hashes = deployed_hashes(game)
    # Match the single-player cold-cache startup budget without relaxing exit gates.
    stock, stock_evidence = h.stock_teardown(game, 300, 600, display)
    if not successful_stock(stock_evidence):
        raise RuntimeError('Stock no-mod control failed; neither native multiplayer peer was launched')
    pair = h.new_run_id() + '-multiplayer'
    folder = h.ROOT / 'artifacts' / 'multiplayer' / pair
    control = folder / 'readiness'
    control.mkdir(parents=True, exist_ok=False)
    port = free_loopback_port()
    prepared = {}
    for role in ('host', 'client'):
        directory, env, _ = h.prepare_run(game, pair + '-' + role, frames, display)
        env = peer_environment(env, pair=pair, role=role, control=control, port=port)
        command = phase_command(game, directory, display, frames, env['VOLIBEAR_TEST_TOKEN'])
        prepared[role] = directory, env, command
    peers, logs, errors = {}, {}, []
    # Both native executables exist at the same time. Tests assert this scheduling
    # boundary; sequential host/client runs cannot satisfy the readiness protocol.
    with h.window_input_guard(game, display), ThreadPoolExecutor(max_workers=2, thread_name_prefix='native-enet-peer') as pool:
        tasks = {role: pool.submit(launch_peer, game, directory, env, command, timeout,
                                  display, stock, stock_evidence)
                 for role, (directory, env, command) in prepared.items()}
        for role, task in tasks.items():
            try:
                peers[role], logs[role] = task.result()
            except Exception as error:
                errors.append(role + ' launch/collection: ' + str(error))
                logs[role] = ''
    tokens = {role: env['VOLIBEAR_TEST_TOKEN'] for role, (_, env, _) in prepared.items()}
    roots = {role: env['VOLIBEAR_TEST_DATA_ROOT'] for role, (_, env, _) in prepared.items()}
    pids = {role: peers.get(role, {}).get('pid', -1) for role in prepared}
    evidence = check_pair(logs, pair, tokens, roots, pids)
    errors.extend(evidence['errors'])
    checks = {'stock_control_success': successful_stock(stock_evidence),
              'two_native_processes': len(peers) == 2 and all(type(pid) is int and pid > 0 for pid in pids.values())
                                      and len(set(pids.values())) == 2,
              'peer_runtime_gates': len(peers) == 2 and all(p['checks'] and all(v is True for v in p['checks'].values()) for p in peers.values()),
              'native_multiplayer_assertions': not errors,
              'deployed_candidate_unchanged': deployed_hashes(game) == hashes}
    report = dict(schema=1, run_id=pair, status='passed' if all(v is True for v in checks.values()) else 'failed',
                  checks=checks, errors=errors, stock_processes=1, multiplayer_processes=len(peers),
                  stock=stock_evidence, peers=peers, evidence=evidence, candidate_sha256=hashes,
                  transport='native-ENet-loopback', port=port, scope=evidence['scope'],
                  repository=h.repository_metadata(), report=str(folder / 'report.json'))
    (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native', action='store_true')
    parser.add_argument('--use-deployed', action='store_true')
    parser.add_argument('--game-dir', type=Path)
    parser.add_argument('--display', choices=['background', 'xvfb', 'window'])
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--frames', type=int, default=108000)
    args = parser.parse_args(argv)
    if not args.execute_native or not args.use_deployed:
        parser.error('Build/deploy first, then explicitly pass --execute-native --use-deployed')
    try:
        report = run_suite(args.game_dir or Path(h.config()['game_dir']), display=args.display,
                           timeout=args.timeout, frames=args.frames)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, 'Native multiplayer suite failed: ' + str(error) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'run_id', 'checks', 'errors', 'report',
                                                 'stock_processes', 'multiplayer_processes', 'scope')}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' and all(value is True for value in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
