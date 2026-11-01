#!/usr/bin/env python3
"""One background game process for existing native card/lifecycle/presentation batches.

No OS input, viewport input, synthetic clicks, or per-case process restarts.
Runs only with --execute-native. Requires the user's pinned game installation.
Native receipts/artifacts are checked by the existing independent oracles; their
absence or any failed stage fails the command. Human sensory review is separate.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import headless as h


def run_suite(game, *, face_cases=None, lifecycle_cases=None, display=None,
              presentation_mode='cards', audio_driver=None, timeout=3600, frames=216000):
    display = display or ('background' if h.IS_WINDOWS else 'xvfb')
    if display not in (('background',) if h.IS_WINDOWS else ('xvfb',)):
        raise ValueError('Suite requires a private background desktop on Windows or xvfb on Linux')
    if type(timeout) is not int or not 60 <= timeout <= 14400:
        raise ValueError('timeout must be an integer in 60..14400 seconds for the whole process')
    if type(frames) is not int or not 3600 <= frames <= 864000:
        raise ValueError('frames must be an integer in 3600..864000 for the whole process')
    faces = h.finite_cases(h.CARD_FACE_CASES if face_cases is None else face_cases,
                          h.CARD_FACE_CASES, 'Card face batch')
    lifecycle = h.finite_cases(h.CARD_LIFECYCLE_CASES if lifecycle_cases is None else lifecycle_cases,
                              h.CARD_LIFECYCLE_CASES, 'Card lifecycle batch')
    if presentation_mode not in ('cards', 'actions', 'all'):
        raise ValueError('Unknown presentation mode')
    if presentation_mode != 'cards' and (not audio_driver or audio_driver.lower() == 'dummy'):
        raise ValueError('Action/audio capture needs an explicit non-Dummy --audio-driver')
    h.display_command([], display)
    game = Path(game).expanduser().resolve()
    h.validate_game(game)
    # One separate no-mod baseline, never one baseline or game process per case.
    stock, stock_evidence = h.stock_teardown(game, 60, 600, display, audio_driver=audio_driver)
    if (not isinstance(stock_evidence,dict) or stock_evidence.get('successful') is not True
            or type(stock_evidence.get('exit_code')) is not int or stock_evidence['exit_code'] != 0
            or stock_evidence.get('timed_out') is not False or stock_evidence.get('runtime_errors') != []):
        raise RuntimeError('Stock no-mod control did not complete cleanly; native suite not launched')
    return h.run_once(game, timeout, frames, scenario='native-suite', display=display,
                      stock=stock, stock_evidence=stock_evidence, card_face_batch=faces,
                      card_lifecycle_cases=lifecycle, presentation_mode=presentation_mode,
                      audio_driver=audio_driver)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native', action='store_true', help='Run the user-owned game installation')
    parser.add_argument('--use-deployed', action='store_true', help='Use the DLL/PCK already built and deployed by local_delivery.py')
    parser.add_argument('--game-dir', type=Path, help='Pinned StS2 installation; otherwise use the local dev configuration')
    parser.add_argument('--display', choices=['background', 'xvfb'], default=None)
    parser.add_argument('--card-face-cases', default='all')
    parser.add_argument('--card-lifecycle-cases', default='all')
    parser.add_argument('--presentation-mode', choices=['cards', 'actions', 'all'], default='cards')
    parser.add_argument('--audio-driver', help='Required real Godot audio driver for actions/all capture')
    parser.add_argument('--timeout', type=int, default=3600, help='Whole suite process budget in seconds')
    parser.add_argument('--frames', type=int, default=216000, help='Whole suite --quit-after frame safety bound')
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
                           timeout=args.timeout, frames=args.frames)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, 'Native suite failed: ' + str(error) + '\n')
    print(json.dumps({'status':report.get('status'),'run_id':report.get('run_id'),
                      'checks':report.get('checks'),'stock_processes':1,'suite_processes':1,
                      'report':str(h.ROOT/'artifacts/headless'/report['run_id']/'report.json'),
                      'human_visual_and_listening_review':'required'}, ensure_ascii=False, indent=2))
    return 0 if report.get('status') == 'passed' and report.get('checks') and all(
        value is True for value in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
