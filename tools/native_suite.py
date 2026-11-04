#!/usr/bin/env python3
"""Native suite, with an explicit two-process face partition/full-catalog mode.

No OS input, viewport input, synthetic clicks, or per-case process restarts.
Runs only with --execute-native. Requires the user's pinned game installation.
Native receipts/artifacts are checked by the existing independent oracles; their
absence or any failed stage fails the command. Human sensory review is separate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import threading
import json
from pathlib import Path
import subprocess
import sys

import headless as h
import save_load_pair


def _suite_ok(report):
    return report.get('status') == 'passed' and bool(report.get('checks')) and all(
        value is True for value in report['checks'].values())


def split_face_cases(cases):
    """Fixed request-order partition; neither worker may receive an empty batch."""
    cases = h.finite_cases(cases, h.CARD_FACE_CASES, 'Card face partition')
    if len(cases) < 2:
        raise ValueError('Parallel catalog requires at least two distinct card-face cases')
    return cases[::2], cases[1::2]


def _face_union_ok(main, catalog, requested):
    try:
        main_cases, catalog_cases = split_face_cases(requested)
        main_batch = main['combat_tests']['stages']['card-faces']
        catalog_batch = catalog['combat_tests']['card_faces']
        completed = []
        for report, result, expected in ((main, main_batch, main_cases), (catalog, catalog_batch, catalog_cases)):
            batch = result['batch']
            if (batch['token'] != report['run_id'] or batch['cases'] != list(expected)
                    or batch['completed'] != list(expected)
                    or [row['variant'] for row in result['records']] != list(expected)
                    or any(row['token'] != report['run_id'] for row in result['records'])):
                return False
            completed.extend(batch['completed'])
        return (not set(main_cases).intersection(catalog_cases)
                and Counter(completed) == Counter(requested)
                and all(count == 1 for count in Counter(completed).values()))
    except (ValueError, RuntimeError, TypeError, KeyError, IndexError, AttributeError):
        return False


def _catalog_ok(report):
    identity = report.get('process_identity', {})
    details = report.get('combat_tests', {})
    return (_suite_ok(report) and report.get('scenario') == 'catalog-face-suite'
            and report.get('mode') == 'real-game-background'
            and report.get('exit_code') == 0 and report.get('timed_out') is False
            and report.get('checks', {}).get('presentation_acceptance_assertions') is True
            and report.get('checks', {}).get('presentation_media_assertions') is True
            and report.get('checks', {}).get('catalog_face_assertions') is True
            and details.get('media', {}).get('status') == 'PASS'
            and details.get('media', {}).get('errors') == []
            and details.get('media', {}).get('token') == report.get('run_id')
            and details.get('media', {}).get('mode') == 'cards'
            and len(details.get('media', {}).get('images', [])) == 356
            and details.get('mode') == 'cards' and details.get('errors') == []
            and type(details.get('verified_catalog_views')) is int and details['verified_catalog_views'] == 356
            and type(identity.get('pid')) is int and identity['pid'] > 0
            and bool(report.get('run_id')) and identity.get('token') == report['run_id'])


def _split_presentation_ok(main, catalog):
    identity = main.get('process_identity', {})
    presentation = main.get('combat_tests', {}).get('stages', {}).get('presentation', {})
    envelope = main.get('combat_tests', {}).get('stages', {}).get('suite', {})
    return (_suite_ok(main) and _catalog_ok(catalog) and main.get('scenario') == 'native-suite'
            and main.get('mode') == 'real-game-background'
            and main.get('checks', {}).get('native_suite_assertions') is True
            and presentation.get('mode') == 'actions' and presentation.get('errors') == []
            and type(identity.get('pid')) is int and identity['pid'] > 0
            and identity.get('token') == main.get('run_id')
            and type(envelope.get('pid')) is int and envelope['pid'] == identity['pid']
            and envelope.get('token') == main.get('run_id')
            and main.get('run_id') != catalog.get('run_id')
            and identity['pid'] != catalog['process_identity']['pid'])


def _parallel_restart(suite_call, restart_call, catalog_call=None):
    cancel = threading.Event()
    def guarded(call, valid):
        try:
            result = call(cancel)
            if not valid(result):
                cancel.set()
            return result
        except BaseException:
            cancel.set()
            raise
    # Cancellation only signals. The thread owning each native Job terminates and
    # closes it; even a normally returned failed report cancels the sibling.
    with ThreadPoolExecutor(max_workers=3 if catalog_call is not None else 2,
                            thread_name_prefix='native-restart') as pool:
        try:
            tasks = [pool.submit(guarded, suite_call, _suite_ok),
                     pool.submit(guarded, restart_call, lambda result: result.get('passed') is True)]
            if catalog_call is not None:
                tasks.append(pool.submit(guarded, catalog_call, _catalog_ok))
        except BaseException:
            cancel.set()
            raise
        results, errors = [], []
        for task in tasks:
            try:
                results.append(task.result())
            except BaseException as error:
                cancel.set()
                errors.append(error)
                results.append(None)
        if errors:
            raise RuntimeError('Native suite/restart failed or cancelled: ' + '; '.join(str(error) for error in errors)) from errors[0]
        return results


def run_suite(game, *, face_cases=None, lifecycle_cases=None, display=None,
              presentation_mode='cards', audio_driver=None, timeout=3600, frames=216000,
              verify_restart=False, restart_timeout=300, restart_frames=30000, parallel_restart=False,
              parallel_catalog=False):
    display = display or ('background' if h.IS_WINDOWS else 'xvfb')
    if type(parallel_catalog) is not bool or (parallel_catalog and not (
            verify_restart and h.IS_WINDOWS and display == 'background' and presentation_mode == 'all')):
        raise ValueError('Parallel catalog requires Windows/background, all presentation and verify_restart')
    if type(parallel_restart) is not bool or (parallel_restart and not (
            verify_restart and h.IS_WINDOWS and display == 'background')):
        raise ValueError('Parallel restart requires Windows background mode and verify_restart')
    if display not in (('background',) if h.IS_WINDOWS else ('xvfb', 'window')):
        raise ValueError('Suite requires a private background desktop on Windows or xvfb/window on POSIX')
    if type(timeout) is not int or not 60 <= timeout <= 28800:
        raise ValueError('timeout must be an integer in 60..28800 seconds for the whole process')
    if type(frames) is not int or not 3600 <= frames <= 1728000:
        raise ValueError('frames must be an integer in 3600..1728000 for the whole process')
    if type(verify_restart) is not bool or type(restart_timeout) is not int or not 30 <= restart_timeout <= 1800:
        raise ValueError('verify_restart must be bool; restart timeout must be an integer in 30..1800')
    if type(restart_frames) is not int or not 1000 <= restart_frames <= 108000:
        raise ValueError('restart frames must be an integer in 1000..108000')
    faces = h.finite_cases(h.CARD_FACE_CASES if face_cases is None else face_cases,
                          h.CARD_FACE_CASES, 'Card face batch')
    main_faces, catalog_faces = split_face_cases(faces) if parallel_catalog else (faces, ())
    lifecycle = h.finite_cases(h.CARD_LIFECYCLE_CASES if lifecycle_cases is None else lifecycle_cases,
                              h.CARD_LIFECYCLE_CASES, 'Card lifecycle batch')
    if presentation_mode not in ('cards', 'actions', 'all'):
        raise ValueError('Unknown presentation mode')
    if presentation_mode != 'cards' and (not audio_driver or audio_driver.lower() == 'dummy'):
        raise ValueError('Action/audio capture needs an explicit non-Dummy --audio-driver')
    h.with_audio_driver([], audio_driver)
    h.display_command([], display)
    game = Path(game).expanduser().resolve()
    h.validate_game(game)
    # One separate no-mod baseline, never one baseline or game process per case.
    # A cold isolated Mesa shader cache can take several minutes on software GL.
    # Keep the same frame bound and clean-exit/error gates; only allow startup time.
    stock, stock_evidence = h.stock_teardown(game, 300, 600, display, audio_driver=audio_driver)
    if (not isinstance(stock_evidence,dict) or stock_evidence.get('successful') is not True
            or type(stock_evidence.get('exit_code')) is not int or stock_evidence['exit_code'] != 0
            or stock_evidence.get('timed_out') is not False or stock_evidence.get('runtime_errors') != []):
        raise RuntimeError('Stock no-mod control did not complete cleanly; native suite not launched; '
                           + json.dumps(stock_evidence, ensure_ascii=False, default=str))
    def suite_call(cancel_event=None):
        options = {} if cancel_event is None else {'cancel_event': cancel_event}
        if parallel_catalog:
            options['record_process_identity'] = True
        return h.run_once(game, timeout, frames, scenario='native-suite', display=display,
                          stock=stock, stock_evidence=stock_evidence, card_face_batch=main_faces,
                          card_lifecycle_cases=lifecycle, presentation_mode='actions' if parallel_catalog else presentation_mode,
                          audio_driver=audio_driver, **options)
    def restart_call(cancel_event=None):
        options = {} if cancel_event is None else {'cancel_event': cancel_event}
        return save_load_pair.run_pair(game, 'S2', 'restart', restart_timeout,
            restart_frames, display, _stock_control=(stock, stock_evidence), audio_driver=audio_driver, **options)
    def catalog_call(cancel_event):
        return h.run_once(game, timeout, frames, scenario='catalog-face-suite', display=display,
                          stock=stock, stock_evidence=stock_evidence, presentation_mode='cards',
                          card_face_batch=catalog_faces,
                          audio_driver=audio_driver, cancel_event=cancel_event, record_process_identity=True)
    catalog = None
    if parallel_catalog:
        suite, restart, catalog = _parallel_restart(suite_call, restart_call, catalog_call)
    elif parallel_restart:
        suite, restart = _parallel_restart(suite_call, restart_call)
    else:
        suite = suite_call()
    if not verify_restart:
        return suite
    # Default: one process for all cases. Explicit parallel-catalog reuses the
    # existing catalog process for the second partition; persistence still owns
    # its two sequential processes. No additional baseline or per-case process.
    suite_ok = _suite_ok(suite)
    if not parallel_restart and not parallel_catalog:
        restart = {'passed': False, 'phases': [], 'reason': 'prior-native-suite-failed'}
        if suite_ok:
            try:
                restart = restart_call()
            except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
                restart = {'passed': False, 'phases': [], 'reason': 'restart-runner-failed', 'error': str(error)}
    # run_pair validates both raw native receipts, actual disk bytes and distinct
    # process identities before awarding this verdict. Cached report files are
    # never accepted as control inputs.
    checks = dict(suite.get('checks', {}), checkpoint_process_restart=restart.get('passed') is True)
    if parallel_catalog:
        checks['separate_catalog_complete_356'] = isinstance(catalog, dict) and _split_presentation_ok(suite, catalog)
        checks['card_face_partition_exact_once'] = checks['separate_catalog_complete_356'] and _face_union_ok(suite, catalog, faces)
    report_path = h.ROOT/'artifacts/headless'/suite['run_id']/'native-acceptance-report.json'
    combined = dict(schema=1, run_id=suite['run_id'], status='passed' if suite_ok and all(
        value is True for value in checks.values()) else 'failed', checks=checks,
        suite_report=str(report_path.with_name('report.json')), restart=restart,
        processes=dict(stock=1, suite=1, restart=len(restart.get('phases', []))),
        report=str(report_path), scope='native-single-process-batches-and-cold-checkpoint-restart')
    if parallel_catalog:
        combined['processes']['catalog'] = 1
        combined['scope'] = 'native-two-process-exact-face-partition-actions-full-catalog-and-cold-checkpoint-restart'
        combined['card_faces'] = {
            'partition_rule': 'request-order-even-odd-v1', 'requested': list(faces),
            'requested_count': len(faces), 'main_cases': list(main_faces), 'catalog_cases': list(catalog_faces),
            'main_count': len(main_faces), 'catalog_count': len(catalog_faces),
            'exact_once': checks['card_face_partition_exact_once'],
            'main_report': str(report_path.with_name('report.json')),
            'catalog_report': str(h.ROOT/'artifacts/headless'/catalog['run_id']/'report.json') if catalog else None,
        }
        combined['presentation'] = {
            'requested_mode': 'all', 'main_mode': 'actions', 'catalog_mode': 'cards', 'required_catalog_views': 356,
            'main_process': suite.get('process_identity'), 'catalog_process': catalog.get('process_identity') if catalog else None,
            'catalog_report': str(h.ROOT/'artifacts/headless'/catalog['run_id']/'report.json') if catalog else None,
            'catalog_artifacts': str(h.ROOT/'artifacts/headless'/catalog['run_id']/'presentation') if catalog else None,
            'catalog': catalog,
        }
    report_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return combined


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native', action='store_true', help='Run the user-owned game installation')
    parser.add_argument('--use-deployed', action='store_true', help='Use the DLL/PCK already built and deployed by local_delivery.py')
    parser.add_argument('--game-dir', type=Path, help='Pinned StS2 installation; otherwise use the local dev configuration')
    parser.add_argument('--display', choices=['background', 'xvfb', 'window'], default=None)
    parser.add_argument('--card-face-cases', default='all')
    parser.add_argument('--card-lifecycle-cases', default='all')
    parser.add_argument('--presentation-mode', choices=['cards', 'actions', 'all'], default='cards')
    parser.add_argument('--audio-driver', help='Required real Godot audio driver for actions/all capture')
    parser.add_argument('--timeout', type=int, default=3600, help='Whole suite process budget in seconds')
    parser.add_argument('--frames', type=int, default=216000, help='Whole suite --quit-after frame safety bound')
    parser.add_argument('--verify-restart', action='store_true',
                        help='After the single-process suite, verify S2 prepare/resume in distinct owned processes; share one stock baseline')
    parser.add_argument('--parallel-catalog', action='store_true',
                        help='Explicit Windows/all-mode full catalog plus second face partition alongside main suite and S2')
    parser.add_argument('--parallel-restart', action='store_true',
                        help='Explicit Windows/background overlap of suite and independent S2 chain')
    parser.add_argument('--restart-timeout', type=int, default=300, help='Each persistence process budget in seconds')
    parser.add_argument('--restart-frames', type=int, default=30000)
    args = parser.parse_args(argv)
    if not args.execute_native:
        parser.error('--execute-native is required; importing or listing this tool never launches the game')
    try:
        faces = h.cli_cases(args.card_face_cases, h.CARD_FACE_CASES, 'Card face batch')
        lifecycle = h.cli_cases(args.card_lifecycle_cases, h.CARD_LIFECYCLE_CASES, 'Card lifecycle batch')
        game = args.game_dir or Path(h.config()['game_dir'])
        # All finite input validation is repeated by run_suite before profile/launch side effects.
        if not args.use_deployed:
            raise ValueError('Build/deploy with local_delivery.py first, then pass --use-deployed')
        report = run_suite(game, face_cases=faces, lifecycle_cases=lifecycle, display=args.display,
                           presentation_mode=args.presentation_mode, audio_driver=args.audio_driver,
                           timeout=args.timeout, frames=args.frames, verify_restart=args.verify_restart,
                           restart_timeout=args.restart_timeout, restart_frames=args.restart_frames,
                           parallel_restart=args.parallel_restart, parallel_catalog=args.parallel_catalog)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, 'Native suite failed: ' + str(error) + '\n')
    print(json.dumps({'status':report.get('status'),'run_id':report.get('run_id'),
                      'checks':report.get('checks'),'stock_processes':1,'suite_processes':1,
                      'restart_processes':report.get('processes',{}).get('restart',0),
                      'catalog_processes':report.get('processes',{}).get('catalog',0),
                      'report':report.get('report') or str(h.ROOT/'artifacts/headless'/report['run_id']/'report.json'),
                      'human_visual_and_listening_review':'required'}, ensure_ascii=False, indent=2))
    return 0 if report.get('status') == 'passed' and report.get('checks') and all(
        value is True for value in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
