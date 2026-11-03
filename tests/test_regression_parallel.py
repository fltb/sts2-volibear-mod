"""Exactly-once parallel scheduling checks; no native fixture/game/full regression run."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from tools import regression_parallel as parallel
from tools.regression import RunResult


def fixture(module, names=('test_a', 'test_b')):
    cls = type('Fixture', (unittest.TestCase,),
               {'__module__': module, **{name: lambda self: None for name in names}})
    return cls, unittest.defaultTestLoader.loadTestsFromTestCase(cls)


def receipt(task):
    ids = task['test_ids']
    return {'task': task['name'], 'nonce': task['nonce'], 'returncode': 0,
            'report': {'schema': 1, 'status': 'passed', 'task': task['name'], 'nonce': task['nonce'],
                       'required_scope': 'installed-game-references', 'native_gameplay_executed': False,
                       'tests_run': len(ids), 'passed': len(ids),
                       **{name: [] for name in parallel.LIST_FIELDS},
                       'requested_test_ids': list(ids), 'loaded_test_ids': list(ids),
                       'executed_test_ids': list(ids)}}


class ParallelRegressionTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['module.Fixture.test_a', 'module.Fixture.test_b']
        self.tasks = [{'name': 'module', 'nonce': 'new-run:module', 'slot': '0', 'test_ids': self.ids}]

    def summarize(self, records, tasks=None, ids=None):
        return parallel.aggregate(self.ids if ids is None else ids, self.tasks if tasks is None else tasks,
                                  records, require_native=True)

    def test_plan_keeps_modules_whole_and_preserves_manual_domain_and_remainder(self):
        _, native = fixture('test_gameplay_state_sequences')
        _, other = fixture('test_assets')
        _, manual = fixture('tests.domain_disabled_presentation.test_native')
        suite = unittest.TestSuite([native, unittest.TestSuite([other, manual])])
        ids, tasks = parallel.plan(suite)
        self.assertEqual(len(ids), 6)
        self.assertEqual([task['name'] for task in tasks],
                         ['test_gameplay_state_sequences', 'serial-remainder'])
        self.assertEqual(len(tasks[0]['test_ids']), 2)
        self.assertEqual(len(tasks[1]['test_ids']), 4)
        self.assertEqual(tasks[0]['test_ids'] + tasks[1]['test_ids'], ids)
        self.assertIn('No test or assertion is omitted', tasks[1]['reason'])

    def test_expanded_allowlist_keeps_all_modules_whole_and_unsafe_fixtures_serial(self):
        added = (
            'test_architect_ending', 'test_domain_debuff_commit_il', 'test_domain_interop',
            'test_domain_passive_contract', 'test_domain_revival_respawn_guard',
            'test_domain_self_debuff', 'test_domain_steam_v1', 'test_domain_summon_contract',
            'test_native_acceptance_host', 'test_native_art_residency',
            'test_native_starter_fixture', 'test_native_suite_phase_timing',
            'test_native_product_flow_pacing', 'test_native_product_flow_travel',
            'test_basic_card_lifecycle', 'test_beast_adapters', 'test_beast_power_lifecycle',
            'test_hand_capacity', 'test_history_contracts', 'test_hover_tips_canonical',
            'test_mechanic_hints', 'test_merchant_integration', 'test_native_flow_contract',
            'test_native_lobby_api', 'test_native_selector', 'test_summon_registration',
            'test_supported_game',
            'test_energy_states', 'test_domain_spirit',
        )
        serial = ('test_local_delivery', 'test_local_delivery_acceptance', 'test_release_budget',
                  'test_headless', 'test_dependencies', 'test_package_lifecycle', 'test_runtime_test')
        self.assertEqual(len(set(parallel.PARALLEL_MODULES)), len(parallel.PARALLEL_MODULES))
        self.assertTrue(set(added).issubset(parallel.PARALLEL_MODULES))
        self.assertTrue(set(serial).isdisjoint(parallel.PARALLEL_MODULES))
        suite = unittest.TestSuite([fixture(module)[1] for module in (*added, *serial)])
        ids, tasks = parallel.plan(suite)
        self.assertEqual(len(ids), 2 * (len(added) + len(serial)))
        self.assertEqual(len(tasks), len(added) + 1)
        self.assertCountEqual([value for task in tasks for value in task['test_ids']], ids)
        for task in tasks:
            if task['name'] == 'serial-remainder':
                self.assertEqual(len(task['test_ids']), 2 * len(serial))
            else:
                self.assertEqual(len(task['test_ids']), 2)
                self.assertTrue(all(value.startswith(task['name'] + '.') for value in task['test_ids']))

    def test_added_sdk_projects_own_distinct_default_output_trees(self):
        # Static isolation guard only: no project compilation or native fixture launch.
        root = Path(__file__).resolve().parents[1]
        projects = {
            'test_architect_ending': 'architect/Architect.Tests.csproj',
            'test_domain_debuff_commit_il': 'domain_debuff_commit_il/DebuffCommitIl.Tests.csproj',
            'test_domain_interop': 'domain_interop/DomainInterop.csproj',
            'test_domain_passive_contract': 'domain_passive_effects/DomainPassiveEffects.Tests.csproj',
            'test_domain_revival_respawn_guard': 'domain_revival_respawn_guard/DomainRevivalRespawnGuard.Tests.csproj',
            'test_domain_self_debuff': 'domain_self_debuff/DomainSelfDebuff.Tests.csproj',
            'test_domain_steam_v1': 'domain_steam_v1/DomainSteamV1.Tests.csproj',
            'test_domain_summon_contract': 'domain_summon_effects/DomainSummonEffects.Tests.csproj',
        }
        parents = []
        for module, relative in projects.items():
            with self.subTest(module=module):
                project = root / 'tests' / relative
                parents.append(project.parent)
                self.assertIn(relative, (root / 'tests' / (module + '.py')).read_text(encoding='utf-8'))
                tree = ET.parse(project)
                for tag in ('ProjectReference', 'OutputPath', 'BaseOutputPath', 'BaseIntermediateOutputPath',
                            'IntermediateOutputPath', 'ArtifactsPath', 'Exec', 'Copy', 'Import'):
                    self.assertEqual(tree.findall('.//' + tag), [], (relative, tag))
        self.assertEqual(len(set(parents)), len(parents))
        shared = ET.parse(root / 'tests/Directory.Build.props')
        for tag in ('OutputPath', 'BaseOutputPath', 'BaseIntermediateOutputPath', 'IntermediateOutputPath'):
            self.assertEqual(shared.findall('.//' + tag), [])

    def test_duplicate_discovery_is_an_error(self):
        cls, _ = fixture('module')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            parallel.plan(unittest.TestSuite([cls('test_a'), cls('test_a')]))

    def test_complete_fresh_outcomes_pass_and_preserve_counts(self):
        result = self.summarize([receipt(self.tasks[0])])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['passed'], 2)
        self.assertEqual(result['tests_run'], 2)
        self.assertEqual(result['executed_test_ids'], self.ids)
        self.assertFalse(result['native_gameplay_executed'])

    def test_missing_duplicate_unknown_and_crashed_workers_fail(self):
        good = receipt(self.tasks[0])
        for records in ([], [good, good], [{'task': 'module', 'returncode': -1}],
                        [{'task': 'unknown', 'returncode': 0, 'report': {}}]):
            with self.subTest(records=records):
                self.assertEqual(self.summarize(records)['status'], 'failed')

    def test_identity_exit_scope_and_malformed_fields_cannot_pass(self):
        mutations = [
            ('outer', 'returncode', 1), ('outer', 'nonce', 'old-run'),
            ('outer', 'infrastructure_error', 'crashed'), ('inner', 'nonce', 'old-run'),
            ('inner', 'task', 'other'), ('inner', 'schema', 0), ('inner', 'status', 'failed'),
            ('inner', 'required_scope', 'available-environment'),
            ('inner', 'native_gameplay_executed', True), ('inner', 'tests_run', 1),
            ('inner', 'passed', 1), ('inner', 'tests_run', None), ('inner', 'errors', None),
        ]
        for location, field, value in mutations:
            with self.subTest(location=location, field=field):
                record = receipt(self.tasks[0])
                (record if location == 'outer' else record['report'])[field] = value
                self.assertEqual(self.summarize([record])['status'], 'failed')

    def test_missing_duplicate_or_wrong_ids_at_each_boundary_fail(self):
        for field in ('requested_test_ids', 'loaded_test_ids', 'executed_test_ids'):
            for ids in (self.ids[:1], [self.ids[0], self.ids[0]], ['other'], None, [{}]):
                with self.subTest(field=field, ids=ids):
                    record = receipt(self.tasks[0])
                    record['report'][field] = ids
                    self.assertEqual(self.summarize([record])['status'], 'failed')

    def test_bad_plan_and_all_failure_kinds_are_fail_closed(self):
        record = receipt(self.tasks[0])
        self.assertEqual(self.summarize([record], ids=self.ids + ['omitted'])['status'], 'failed')
        for field in ('failures', 'errors', 'expected_failures', 'unexpected_successes', 'unavailable_required_checks'):
            bad = copy.deepcopy(record)
            bad['report'][field] = ['failed-test']
            self.assertEqual(self.summarize([bad])['status'], 'failed')

    def test_only_two_exact_linux_skip_id_reason_pairs_allowed_on_windows(self):
        pairs = [
            ('test_window_startup_hint.StartupHintRouting.test_missing_compiler_fails_instead_of_activating_fallback',
             'Linux x86_64 tool'),
            ('test_window_startup_hint.StartupHintRouting.test_real_dlopen_dlsym_pre_map_once_and_unrelated_executable_untouched',
             'Linux C compiler ABI fixture'),
        ]
        ids = [row[0] for row in pairs]
        task = {**self.tasks[0], 'test_ids': ids}
        with mock.patch.object(parallel.os, 'name', 'nt'):
            good = receipt(task)
            good['report']['passed'] = 0
            good['report']['skipped'] = [{'test': test, 'reason': reason} for test, reason in pairs]
            self.assertEqual(self.summarize([good], tasks=[task], ids=ids)['status'], 'passed')
            duplicate = copy.deepcopy(good)
            duplicate['report']['skipped'][1] = dict(duplicate['report']['skipped'][0])
            self.assertEqual(self.summarize([duplicate], tasks=[task], ids=ids)['status'], 'failed')
            for test, reason in [('other', pairs[0][1]), (pairs[0][0], 'sdk unavailable'),
                                 (pairs[0][0], pairs[1][1])]:
                bad = copy.deepcopy(good)
                bad['report']['skipped'][0] = {'test': test, 'reason': reason}
                self.assertEqual(self.summarize([bad], tasks=[task], ids=ids)['status'], 'failed')

    def test_worker_runs_whole_class_setup_once_and_emits_fresh_id_evidence(self):
        module = types.ModuleType('regression_test_fixture')
        cls, _ = fixture(module.__name__)
        setup = mock.Mock()
        cls.setUpClass = classmethod(lambda cls: setup())
        module.Fixture = cls
        ids = [f'{module.__name__}.Fixture.{name}' for name in ('test_a', 'test_b')]
        task = {**self.tasks[0], 'test_ids': ids}
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, {module.__name__: module}):
            plan, output = Path(directory) / 'plan.json', Path(directory) / 'result.json'
            plan.write_text(json.dumps(task))
            with mock.patch('sys.stderr', new=io.StringIO()):
                code = parallel.worker(plan, output, require_native=True)
            report = json.loads(output.read_text())
        self.assertEqual(code, 0)
        setup.assert_called_once()
        self.assertEqual(report['executed_test_ids'], ids)
        self.assertEqual(report['loaded_test_ids'], ids)
        self.assertEqual(report['nonce'], task['nonce'])

    def test_setup_error_cannot_forge_executed_ids_or_pass(self):
        module = types.ModuleType('regression_failed_fixture')
        cls, _ = fixture(module.__name__)
        def fail(cls):
            raise RuntimeError('setup failed')
        cls.setUpClass = classmethod(fail)
        module.Fixture = cls
        ids = [f'{module.__name__}.Fixture.test_a']
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, {module.__name__: module}):
            plan, output = Path(directory) / 'plan.json', Path(directory) / 'result.json'
            plan.write_text(json.dumps({**self.tasks[0], 'test_ids': ids}))
            with mock.patch('sys.stderr', new=io.StringIO()):
                self.assertEqual(parallel.worker(plan, output, require_native=True), 1)
            report = json.loads(output.read_text())
        self.assertEqual(report['executed_test_ids'], [])
        self.assertEqual(report['status'], 'failed')

    def test_process_scratch_is_unique_but_python_temp_preserved_and_no_pipe_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {'TEMP': 'short', 'TMP': 'short', 'TMPDIR': 'short'}
            with mock.patch.object(parallel.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                record = parallel.execute(self.tasks[0], root=root, directory=root,
                                          environment=environment, require_native=True, failfast=False)
                second = {**self.tasks[0], 'name': 'second', 'nonce': 'new-run:second', 'slot': '1'}
                parallel.execute(second, root=root, directory=root, environment=environment,
                                 require_native=True, failfast=False)
            first_env = run.call_args_list[0].kwargs['env']
            args = run.call_args.kwargs
            self.assertNotEqual(first_env['VOLIBEAR_RUNTIME_TEMP'], args['env']['VOLIBEAR_RUNTIME_TEMP'])
            self.assertNotEqual(first_env['NUGET_SCRATCH'], args['env']['NUGET_SCRATCH'])
            self.assertNotIn('NUGET_SCRATCH', environment)
            self.assertEqual(args['env']['TEMP'], 'short')
            self.assertEqual(args['env']['TMP'], 'short')
            self.assertIn('VOLIBEAR_RUNTIME_TEMP', args['env'])
            self.assertIn('NUGET_SCRATCH', args['env'])
            self.assertNotEqual(args['env']['VOLIBEAR_RUNTIME_TEMP'], args['env']['NUGET_SCRATCH'])
            self.assertNotIn('capture_output', args)
            self.assertIn('--require-native', run.call_args.args[0])
            self.assertIn('infrastructure_error', record)  # exit zero without a fresh result is still failure

    def test_run_bounds_jobs_and_combines_only_executed_records(self):
        _, suite = fixture('test_gameplay_state_sequences')
        with tempfile.TemporaryDirectory() as directory:
            for jobs in (1, 4, 5, 6):
                with mock.patch.object(parallel, 'execute', side_effect=lambda task, **kwargs: receipt(task)) as execute:
                    result = parallel.run(suite, jobs=jobs, root=Path(directory), directory=directory,
                                          environment={}, require_native=True)
                self.assertEqual(result['status'], 'passed')
                execute.assert_called_once()
                self.assertEqual(result['jobs'], jobs)
            for jobs in (0, 7):
                with self.assertRaises(ValueError):
                    parallel.run(suite, jobs=jobs, root=Path(directory), directory=directory,
                                 environment={}, require_native=True)

    def test_six_synthetic_modules_execute_once_at_bounded_concurrency(self):
        import threading
        modules = parallel.PARALLEL_MODULES[:6]
        suite = unittest.TestSuite([fixture(module)[1] for module in modules])
        barrier = threading.Barrier(6)
        lock = threading.Lock()
        active = peak = 0
        observed = []
        def execute(task, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                observed.append(task['name'])
            try:
                barrier.wait(timeout=10)
                return receipt(task)
            finally:
                with lock:
                    active -= 1
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(parallel, 'execute', execute):
            result = parallel.run(suite, jobs=6, root=Path(directory), directory=directory,
                                  environment={}, require_native=True)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['tests_run'], 12)
        self.assertEqual(peak, 6)
        self.assertCountEqual(observed, modules)
        self.assertEqual(len(set(result['executed_test_ids'])), 12)

    def test_runresult_counters_are_per_instance(self):
        result = RunResult(io.StringIO(), True, 0)
        other = RunResult(io.StringIO(), True, 0)
        cls, _ = fixture('module')
        test = cls('test_a')
        result.startTest(test)
        result.addSuccess(test)
        self.assertEqual(result.executed_test_ids, [test.id()])
        self.assertEqual(other.executed_test_ids, [])
        self.assertEqual(other.successful_tests, 0)


if __name__ == '__main__':
    unittest.main()
