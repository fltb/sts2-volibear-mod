import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import domain_suppression_evidence as evidence
import headless


def receipt(family):
    steps = []
    if family == 'sandpit':
        steps = [dict(phase='baseline', count=6, x=300), dict(phase='domain-on', count=6, x=300),
                 dict(phase='domain-off', count=5, x=350)]
    return dict(schema=1, token='current', scenario='domain-suppression', family=family,
                version='v0.107.1', commit='59260271', testMode=False, passed=True,
                checks={key: True for key in evidence.REQUIRED_CHECKS[family]}, steps=steps)


def log_for(rows):
    return '\n'.join(evidence.PREFIX + json.dumps(row) for row in rows)


class DomainSuppressionEvidenceTests(unittest.TestCase):
    def test_all_families_and_single_family(self):
        for family in evidence.CASES:
            names = evidence.FAMILIES if family == 'all' else (family,)
            result, passed = evidence.check_log(log_for([receipt(name) for name in names]), 'current', family)
            self.assertTrue(passed, result)
            self.assertEqual([row['family'] for row in result['results']], list(names))

    def test_required_check_set_and_strict_boolean(self):
        for family in evidence.FAMILIES:
            for name in evidence.REQUIRED_CHECKS[family]:
                for change in ('missing', False, 1, 'true', None):
                    row = receipt(family)
                    if change == 'missing':
                        del row['checks'][name]
                    else:
                        row['checks'][name] = change
                    self.assertFalse(evidence.check_log(log_for([row]), 'current', family)[1], (family, name, change))
            row = receipt(family)
            row['checks']['invented-pass'] = True
            self.assertFalse(evidence.check_log(log_for([row]), 'current', family)[1])

    def test_identity_version_and_completion_are_strict(self):
        mutations = dict(schema=True, token='stale', scenario='domain-contract', family='self', version='v0.107.2',
                         commit='other', testMode=True, passed=1)
        for field, value in mutations.items():
            row = receipt('sandpit'); row[field] = value
            self.assertFalse(evidence.check_log(log_for([row]), 'current', 'sandpit')[1], field)
        for field in receipt('sandpit'):
            row = receipt('sandpit'); del row[field]
            self.assertFalse(evidence.check_log(log_for([row]), 'current', 'sandpit')[1], field)

    def test_incomplete_duplicate_wrong_order_and_native_error_rejected(self):
        rows = [receipt(name) for name in evidence.FAMILIES]
        for bad in (rows[:2], rows + [rows[0]], [rows[0], rows[0], rows[2]], rows[::-1]):
            self.assertFalse(evidence.check_log(log_for(bad), 'current')[1])
        self.assertFalse(evidence.check_log(log_for(rows) + '\n' + evidence.ERROR_PREFIX + '{}', 'current')[1])
        self.assertFalse(evidence.check_log(log_for(rows), '', 'all')[1])
        self.assertFalse(evidence.check_log(log_for(rows), 'current', 'unknown')[1])

    def test_malformed_protocol_and_duplicate_json_keys_rejected(self):
        for payload in ('[]', 'null', 'false', '{broken', '{"family":"self","family":"sandpit"}'):
            self.assertFalse(evidence.check_log(evidence.PREFIX + payload, 'current', 'self')[1])

    def test_sandpit_values_independently_checked_despite_all_checks_true(self):
        mutations = ((0, 'count', 7), (1, 'count', 5), (2, 'count', 4), (1, 'x', 302),
                     (2, 'x', 300), (0, 'x', float('nan')), (2, 'x', float('inf')),
                     (1, 'count', True), (2, 'count', '5'), (1, 'phase', 'domain-off'))
        for index, key, value in mutations:
            row = receipt('sandpit'); row['steps'][index][key] = value
            self.assertFalse(evidence.check_log(log_for([row]), 'current', 'sandpit')[1], (index, key, value))

    def test_probe_check_names_and_family_order_match_frozen_oracle(self):
        # A source-contract guard supplements, not substitutes for the native fixture.
        import re
        source = (ROOT / 'src/Volibear/DomainSuppressionAcceptanceProbe.cs').read_text(encoding='utf-8')
        actual = set(re.findall(r'Check\("([^"]+)"', source))
        self.assertEqual(actual, set().union(*evidence.REQUIRED_CHECKS.values()))
        self.assertIn('RequestedFamily == "all" ? "sandpit" : RequestedFamily', source)
        self.assertIn('Family == "sandpit" ? "knights" : "self"', source)
        self.assertIn('Family != "self"', source)
        self.assertIn('phase = "baseline"', source)

    def test_native_dispatch_and_encounter_bootstrap_are_connected(self):
        import re
        entry = (ROOT / 'src/Volibear/ModEntry.cs').read_text()
        branch = re.search(r'else if \(scenario == "domain-suppression"\)\s*\{([^}]+)\}', entry)
        self.assertIsNotNone(branch)
        self.assertIn('DevelopmentBootstrap.Install(installDriver: false)', branch[1])
        self.assertIn('DomainSuppressionAcceptanceProbe.Install()', branch[1])
        bootstrap = (ROOT / 'src/Volibear/VolibearBootstrap.cs').read_text()
        self.assertIn('Scenario == "domain-suppression" ? DomainSuppressionAcceptanceProbe.Encounter.RoomType', bootstrap)
        self.assertIn('if (Scenario == "domain-suppression") return DomainSuppressionAcceptanceProbe.Encounter;', bootstrap)

    def run_fixture(self, log, family='all', stock_ok=True, code=0):
        env, command = {}, ['game']
        with mock.patch.object(headless, 'new_run_id', return_value='current'), \
             mock.patch.object(headless, 'prepare_run', return_value=(Path('synthetic'), env, command)), \
             mock.patch.object(headless, 'launch', return_value=(code, False)) as launch, \
             mock.patch.object(headless, 'combined_log', return_value=log), \
             mock.patch.object(headless, 'IS_WINDOWS', True), \
             mock.patch.dict(os.environ, {'VOLIBEAR_TEST_AUDIO_ADAPTER': '0'}), \
             mock.patch.object(headless.subprocess, 'check_output', side_effect=['commit', '']), \
             mock.patch.object(Path, 'write_text'), mock.patch('builtins.print'):
            report = headless.run_once(Path('game'), 900, 60000, scenario='domain-suppression',
                stock=set(), stock_evidence=dict(successful=stock_ok, exit_code=0, timed_out=False),
                domain_suppression_family=family)
            launch.assert_called_once()
        return report, env, command

    def test_runner_routes_all_in_one_process_and_independently_verifies(self):
        prefix = 'Steam initialization skipped\n[Volibear] LOAD_OK\n[Volibear] ISOLATION_OK steam=false\n'
        report, env, command = self.run_fixture(prefix + log_for([receipt(name) for name in evidence.FAMILIES]))
        self.assertEqual(env['VOLIBEAR_TEST_DOMAIN_SUPPRESSION_CASE'], 'all')
        self.assertEqual(env['VOLIBEAR_TEST_CHARACTER'], 'volibear')
        self.assertEqual(env['VOLIBEAR_TEST_SCENARIO'], 'domain-suppression')
        self.assertIn('--bootstrap', command)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['checks']['domain_suppression_assertions'])

    def test_runner_preserves_stock_exit_and_missing_receipt_failures(self):
        prefix = 'Steam initialization skipped\n[Volibear] LOAD_OK\n[Volibear] ISOLATION_OK steam=false\n'
        complete = prefix + log_for([receipt(name) for name in evidence.FAMILIES])
        for log, stock, code in ((prefix, True, 0), (complete, False, 0), (complete, True, 2)):
            self.assertEqual(self.run_fixture(log, stock_ok=stock, code=code)[0]['status'], 'failed')

    def test_invalid_family_rejected_before_profile_or_launch(self):
        with mock.patch.object(headless, 'prepare_run') as prepare, mock.patch.object(headless, 'launch') as launch:
            with self.assertRaises(RuntimeError):
                headless.run_once(Path('game'), 900, 60000, scenario='domain-suppression', domain_suppression_family='bad')
        prepare.assert_not_called(); launch.assert_not_called()

    def test_cli_defaults_to_single_bounded_all_process(self):
        with mock.patch.object(sys, 'argv', ['headless.py', '--scenario', 'domain-suppression', '--use-deployed']), \
             mock.patch.object(headless, 'display_command'), mock.patch.object(headless, 'config', return_value={'game_dir': '.'}), \
             mock.patch.object(headless, 'validate_game'), mock.patch.object(headless, 'stock_teardown', return_value=(set(), {})), \
             mock.patch.object(headless, 'run_once', return_value={'status': 'passed'}) as run, mock.patch('builtins.print'):
            self.assertEqual(headless.main(), 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs['domain_suppression_family'], 'all')
        self.assertEqual(run.call_args.args[1:3], (900, 60000))

    def test_cli_rejects_repeat_before_any_game_start(self):
        with mock.patch.object(sys, 'argv', ['headless.py', '--scenario', 'domain-suppression', '--repeat', '2']), \
             mock.patch.object(headless, 'stock_teardown') as stock, mock.patch.object(headless, 'run_once') as run, \
             mock.patch('sys.stderr'):
            with self.assertRaises(SystemExit) as error:
                headless.main()
        self.assertEqual(error.exception.code, 2)
        stock.assert_not_called(); run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
