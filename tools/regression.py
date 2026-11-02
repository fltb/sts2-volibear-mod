#!/usr/bin/env python3
"""Run the repository regression once and distinguish skips from executed checks.

--require-native is the installed-game delivery gate: an unavailable SDK, game
reference, selector binding or native metadata test is a failure there. Platform
checks for the other OS may remain skipped. The report is an ignored run artifact.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
OTHER_PLATFORM_REASONS = frozenset({
    'Windows junction migration', 'Windows native window fixtures',
    'Windows private-desktop native renderer', 'Windows private-desktop launch failure',
    'Windows owned process flags', 'native Windows chdir regression',
})


class RunResult(unittest.TextTestResult):
    """Count real successes, including when class skips/subtests change testsRun semantics."""
    successful_tests = 0

    def addSuccess(self, test):
        self.successful_tests += 1
        super().addSuccess(test)


def summarize(result, *, require_native, platform=None):
    platform = os.name if platform is None else platform
    skipped = [{'test': test.id(), 'reason': reason} for test, reason in result.skipped]
    unavailable = [row for row in skipped if not (
        platform != 'nt' and row['reason'] in OTHER_PLATFORM_REASONS)]
    passed = result.wasSuccessful() and not result.expectedFailures and (not require_native or not unavailable)
    return {
        'schema': 1, 'status': 'passed' if passed else 'failed',
        'required_scope': 'installed-game-references' if require_native else 'available-environment',
        'tests_run': result.testsRun,
        'passed': getattr(result, 'successful_tests', max(0, result.testsRun - len(result.errors)
                          - len(result.failures) - len(skipped) - len(result.expectedFailures)
                          - len(result.unexpectedSuccesses))),
        'failures': [test.id() for test, _ in result.failures],
        'errors': [test.id() for test, _ in result.errors],
        'expected_failures': [test.id() for test, _ in result.expectedFailures],
        'unexpected_successes': [test.id() for test in result.unexpectedSuccesses],
        'skipped': skipped, 'unavailable_required_checks': unavailable if require_native else [],
        # These tests inspect real references where available, but never stand in for
        # the actual gameplay, presentation, disk-restart or two-peer process runners.
        'native_gameplay_executed': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-native', action='store_true')
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/validation/regression.json')
    args = parser.parse_args(argv)
    # unittest discovery imports the modules from tests; repository modules must also
    # resolve when this entrypoint is executed as a script instead of python -m.
    sys.path.insert(0, str(ROOT))
    began = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    # This scoped native fixture directory is intentionally not a discovery package.
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
        'tests.domain_disabled_presentation.test_native.DomainDisabledPresentationTests'))
    result = unittest.TextTestRunner(verbosity=2, resultclass=RunResult).run(suite)
    report = summarize(result, require_native=args.require_native)
    report.update(elapsed_seconds=round(time.monotonic() - began, 3),
                  finished_utc=datetime.now(timezone.utc).isoformat())
    try:
        report['git_commit'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        report['dirty'] = bool(subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        report.update(git_commit=None, dirty=None)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('REGRESSION ' + report['status'].upper() + ': ' + str(args.report), flush=True)
    if report['unavailable_required_checks']:
        print('Required installed-game checks did not execute:', file=sys.stderr)
        for row in report['unavailable_required_checks']:
            print('  ' + row['test'] + ': ' + row['reason'], file=sys.stderr)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
