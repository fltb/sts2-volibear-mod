#!/usr/bin/env python3
"""Run the PBE verification matrix in one command and print an aggregate table.

Each scenario keeps its own native receipt validation; this wrapper only sequences the
runs and collects pass/fail so a channel update is one command, not a manual loop.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = (
    # Every native scenario that exists for the stable channel, with one representative
    # case each; batch scenarios cover their whole case set in one game process.
    ('baseline', []),
    ('api', []),
    ('content', []),
    ('engage-contract', ['--engage-case', 'e01']),
    ('domain-contract', ['--domain-case', 'd01']),
    ('beast-contract', ['--beast-case', 'f01']),
    ('domain-enemy-contract', ['--domain-enemy-case', 'flutter']),
    ('persistent-contract', ['--persistent-case', 'PP-U03-clamp-priority']),
    ('persistent-contract', ['--persistent-case', 'PP-U03-min-stack']),
    ('persistent-contract', ['--persistent-case', 'PP-U03-other-retention']),
    ('catalog', []),
    ('enemy-catalog', []),
    ('domain-summon-contract', ['--domain-summon-case', 'fabricator-off']),
    ('relic-contract', ['--relic-case', 'RH-starter-turns']),
    ('domain-passive-contract', ['--domain-passive-case', 'ritual-off']),
    ('prepared-contract', ['--prepared-case', 'PR-training-dynamic-spells']),
    ('enemy-matrix-mvp', []),
    ('domain-revival', ['--revival-case', 'reattach-off']),
    ('prepared-choice', ['--prepared-choice-case', 'PC-C19-fixed-replay']),
    ('power-presentation', []),
    ('enemy-exploration', []),
    ('coupon-contract', ['--coupon-case', 'CP-max-preserve']),
    ('domain-card-contributions', ['--domain-card-case', 'hex']),
    ('primal-contract', ['--primal-case', 'U12-paid-snapshot']),
    ('audio-receipts', []),
    ('domain-dampen-transactions', []),
    ('standing-extra-turn', ['--standing-case', 'U03-base-extra-turn']),
    ('domain-steam', ['--steam-case', 'off']),
    ('card-face-acceptance', ['--card-face-batch', 'all']),
    ('domain-hopper', ['--hopper-case', 'off']),
    ('domain-suppression', ['--domain-suppression-family', 'all']),
    ('domain-visual', []),
    ('architect-ending', []),
    ('card-lifecycle', ['--card-lifecycle-cases', 'all']),
    ('native-run', ['--native-run-mode', 'three-battle-save']),
    ('presentation-acceptance', ['--presentation-mode', 'cards']),
)


def run(scenario, extra, args) -> dict:
    command = [str(ROOT / '.local/build-python/bin/python'), '-B', str(ROOT / 'tools/headless.py'),
               '--use-deployed', '--scenario', scenario,
               '--display', args.display, '--audio-driver', args.audio]
    # Batch scenarios choose their own frame budget inside headless; only override on request.
    if args.timeout is not None:
        command += ['--timeout', str(args.timeout)]
    if args.frames is not None:
        command += ['--frames', str(args.frames)]
    command += extra
    env = dict(os.environ)
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, env=env)
    tail = [line for line in completed.stdout.splitlines() if line.strip().startswith('{"report"')]
    report = json.loads(tail[-1]) if tail else None
    directory = Path(report['report']).parent if report else None
    checks = json.loads((directory / 'report.json').read_text(encoding='utf-8'))['checks'] if directory and (directory / 'report.json').is_file() else {}
    failed = [name for name, value in checks.items() if value is False]
    return {'scenario': scenario, 'case': ' '.join(extra), 'exit': completed.returncode,
            'passed': completed.returncode == 0 and bool(checks) and not failed,
            'failed_checks': failed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', action='append', default=[], help='Limit to scenario names')
    parser.add_argument('--timeout', type=int, default=None)
    parser.add_argument('--frames', type=int, default=None)
    parser.add_argument('--display', default='window')
    parser.add_argument('--audio', default='PulseAudio')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    if not (os.environ.get('VOLIBEAR_GAME_VERSION') and os.environ.get('VOLIBEAR_GAME_COMMIT')):
        print('Set VOLIBEAR_GAME_VERSION and VOLIBEAR_GAME_COMMIT to the installed channel first.', file=sys.stderr)
        return 2
    rows = []
    for scenario, extra in MATRIX:
        if args.only and scenario not in args.only:
            continue
        result = run(scenario, extra, args)
        result['case'] = ' '.join(extra)
        rows.append(result)
        label = scenario + (':' + result['case'] if result['case'] else '')
        print(('PASS ' if result['passed'] else 'FAIL ') + label +
              ('' if result['passed'] else '  failed=' + ','.join(result['failed_checks'])), flush=True)
    passed = sum(1 for row in rows if row['passed'])
    print(f'\n{passed}/{len(rows)} scenarios passed')
    if args.json:
        args.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if passed == len(rows) and rows else 1


if __name__ == '__main__':
    sys.exit(main())
