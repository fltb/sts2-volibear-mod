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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

# These modules assert the exact 0.107.1 native signatures/IL the stable channel was built
# against. On a PBE assembly set they are obsolete by construction; the PBE content gate is
# the native scenario matrix (tools/pbe_verify.py). They are skipped, with a recorded reason,
# instead of being reported as regressions.
STABLE_CONTRACT_MODULES = (
    'test_persistent_cards', 'tests.domain_disabled_presentation', 'test_audio_receipts',
    'test_audio_receipt_evidence', 'test_domain_hopper', 'test_power_stack_visual',
    'test_power_stack_presentation', 'test_architect_ending', 'test_domain_debuff_commit_il',
    'test_domain_passive_contract', 'test_domain_revival_respawn_guard', 'test_domain_self_debuff',
    'test_domain_steam_v1', 'test_domain_summon_contract', 'test_native_acceptance_host',
    'test_native_starter_fixture', 'test_native_product_flow_pacing',
    'test_catalog_face_suite_native', 'test_card_lifecycle_native_preloading',
    'test_beast_power_lifecycle', 'test_history_contracts', 'test_domain_team_protection',
    'test_hover_tips_canonical', 'test_mechanic_hints', 'test_merchant_integration',
    'test_native_flow_contract',
)


def stable_contract_channel() -> bool:
    return os.environ.get('VOLIBEAR_CHANNEL', 'stable') == 'stable'


def partition_stable_contract(suite):
    """Remove stable-pinned native contract tests and return their ids for the skip report."""
    skipped, kept = [], []

    def walk(item):
        if isinstance(item, unittest.TestSuite):
            for child in item:
                walk(child)
        elif item.id().startswith(STABLE_CONTRACT_MODULES):
            skipped.append(item.id())
        else:
            kept.append(item)

    walk(suite)
    return unittest.TestSuite(kept), skipped
OTHER_PLATFORM_REASONS = frozenset({
    'Windows junction migration', 'Windows native window fixtures',
    'Windows private-desktop native renderer', 'Windows private-desktop launch failure',
    'Windows owned process flags', 'native Windows chdir regression',
    'Windows Job descendant ownership contract',
})

LINUX_PLATFORM_REASONS = frozenset({'Linux x86_64 tool', 'Linux C compiler ABI fixture'})


class RunResult(unittest.TextTestResult):
    """Count real successes, including when class skips/subtests change testsRun semantics."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successful_tests = 0
        self.executed_test_ids = []

    def startTest(self, test):
        self.executed_test_ids.append(test.id())
        super().startTest(test)

    def addSuccess(self, test):
        self.successful_tests += 1
        super().addSuccess(test)


def summarize(result, *, require_native, platform=None):
    platform = os.name if platform is None else platform
    skipped = [{'test': test.id(), 'reason': reason} for test, reason in result.skipped]
    unavailable = [row for row in skipped if not (
        (platform != 'nt' and row['reason'] in OTHER_PLATFORM_REASONS) or
        (platform == 'nt' and row['reason'] in LINUX_PLATFORM_REASONS))]
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
    parser.add_argument('--failfast', action='store_true', help='Stop at the first failure for targeted diagnosis')
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/validation/regression.json')
    parser.add_argument('--jobs', type=int, choices=range(1, 7), default=1,
                        help='Independent module worker processes (1 retains serial execution; maximum 6)')
    parser.add_argument('--worker-plan', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--worker-result', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if bool(args.worker_plan) != bool(args.worker_result):
        parser.error('--worker-plan and --worker-result must be supplied together')
    # unittest discovery imports the modules from tests; repository modules must also
    # resolve when this entrypoint is executed as a script instead of python -m.
    sys.path.insert(0, str(ROOT))
    from tools.runtime_test import get_runtime
    runtime = get_runtime(ROOT)
    environment = runtime.environment()
    # The suite's Python filesystem fixtures retain the host's short temporary
    # root. Only launched SDK/Godot children receive the isolated compiler temp;
    # nesting every Python fixture there can exceed Windows shader path limits.
    for name in ('TEMP', 'TMP', 'TMPDIR'):
        if name in os.environ:
            environment[name] = os.environ[name]
        else:
            environment.pop(name, None)
    if args.require_native:
        environment['VOLIBEAR_REQUIRE_NATIVE'] = '1'
    began = time.monotonic()
    with patch.dict(os.environ, environment):
        if args.worker_plan:
            # Match discover's import path without discovering/running unrelated modules.
            sys.path.insert(0, str(ROOT / 'tests'))
            from tools.regression_parallel import worker
            return worker(args.worker_plan, args.worker_result,
                          require_native=args.require_native, failfast=args.failfast)
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        # This scoped native fixture directory is intentionally not a discovery package.
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
            'tests.domain_disabled_presentation.test_native.DomainDisabledPresentationTests'))
        stable_skips = []
        if not stable_contract_channel():
            suite, stable_skips = partition_stable_contract(suite)
        if args.jobs == 1:
            result = unittest.TextTestRunner(verbosity=2, resultclass=RunResult, failfast=args.failfast).run(suite)
            report = summarize(result, require_native=args.require_native)
            report.setdefault('skipped', []).extend(
                {'test': test_id, 'reason': 'stable-channel native contract (PBE channel)'} for test_id in stable_skips)
        else:
            from tools.regression_parallel import run
            report = run(suite, jobs=args.jobs, root=ROOT, directory=args.report.parent,
                         environment=dict(os.environ), require_native=args.require_native,
                         failfast=args.failfast)
            report.setdefault('skipped', []).extend(
                {'test': test_id, 'reason': 'stable-channel native contract (PBE channel)'} for test_id in stable_skips)
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
