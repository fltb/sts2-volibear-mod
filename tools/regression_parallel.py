"""Bounded process sharding of whole regression modules; no cached test outcomes."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import unittest

# Audited SDK modules own separate projects/output trees. Keep each module intact:
# setUpClass builds once and mutations remain sequential inside their original test.
PARALLEL_MODULES = (
    'test_gameplay_state_sequences', 'test_domain_team_protection',
    'test_presentation_bridge_behavior', 'test_audio_receipts',
    'test_audio_receipt_evidence', 'test_domain_lifecycle_states',
    'test_engage_adapter', 'test_engage_harmony', 'test_engage_opportunities',
    'test_lightning_responses', 'test_domain_hopper', 'test_power_stack_visual',
    'test_power_stack_presentation',
    # Separate SDK project directories with default project-local bin/obj. Native
    # assemblies and production sources are read-only inputs, not ProjectReferences.
    'test_architect_ending', 'test_domain_debuff_commit_il', 'test_domain_interop',
    'test_domain_passive_contract', 'test_domain_revival_respawn_guard',
    'test_domain_self_debuff', 'test_domain_steam_v1', 'test_domain_summon_contract',
    # Generated projects have unique .local/acceptance-host-* / art-lease-* roots.
    'test_native_acceptance_host', 'test_native_art_residency',
    # Unique starter-fixture-*, suite-phase-*, and acceptance-host-* temp projects;
    # production/native inputs are read-only, including the full-source API compile.
    'test_native_starter_fixture', 'test_native_suite_phase_timing',
    'test_native_product_flow_pacing', 'test_native_product_flow_travel',
    'test_catalog_face_suite_native', 'test_card_lifecycle_native_preloading',
    # Each remaining SDK module owns its project bin/obj or named artifact tree.
    # Beast/hand generated sources are owned by that same whole-module task only.
    'test_basic_card_lifecycle', 'test_beast_adapters', 'test_beast_power_lifecycle',
    'test_hand_capacity', 'test_history_contracts', 'test_hover_tips_canonical',
    'test_mechanic_hints', 'test_merchant_integration', 'test_native_flow_contract',
    'test_native_lobby_api', 'test_native_selector', 'test_summon_registration',
    'test_supported_game',
    # Standalone Godot projects/imports/profiles/CA and UI reproduction are all in
    # per-test TemporaryDirectories; approved shaders/images are only read/copied.
    'test_energy_states', 'test_domain_spirit',
)
REMAINDER_REASON = (
    'Conservative serial bucket: modules outside the audited independent SDK/Godot '
    'allowlist retain discovery order, including platform/installer/CLI/process fixtures and '
    'unaudited fixed generated-file builders. No test or assertion is omitted.'
)
LIST_FIELDS = ('failures', 'errors', 'expected_failures', 'unexpected_successes',
               'skipped', 'unavailable_required_checks')
COUNT_FIELDS = ('tests_run', 'passed')


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def plan(suite):
    tests = list(flatten(suite))
    ids = [test.id() for test in tests]
    if len(set(ids)) != len(ids):
        raise ValueError('Discovery contains duplicate test IDs')
    grouped = {module: [] for module in PARALLEL_MODULES}
    remainder = []
    for test in tests:
        grouped.get(type(test).__module__, remainder).append(test.id())
    tasks = [{'name': module, 'test_ids': grouped[module]} for module in PARALLEL_MODULES if grouped[module]]
    # Schedule the remainder with the three expensive mutation modules, not last.
    if remainder:
        tasks.insert(min(3, len(tasks)), {'name': 'serial-remainder', 'test_ids': remainder,
                                       'reason': REMAINDER_REASON})
    return ids, tasks


def worker(plan_path, result_path, *, require_native, failfast=False):
    from tools.regression import RunResult, summarize
    data = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    expected = data['test_ids']
    suite = unittest.defaultTestLoader.loadTestsFromNames(expected)
    loaded = [test.id() for test in flatten(suite)]
    began = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RunResult, failfast=failfast).run(suite)
    report = summarize(result, require_native=require_native)
    report.update(nonce=data['nonce'], task=data['name'], requested_test_ids=expected,
                  loaded_test_ids=loaded, executed_test_ids=result.executed_test_ids,
                  elapsed_seconds=round(time.monotonic() - began, 3))
    if Counter(loaded) != Counter(expected) or Counter(result.executed_test_ids) != Counter(expected):
        report['status'] = 'failed'
        report['errors'].append('worker test ID coverage mismatch')
    Path(result_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1


def execute(task, *, root, directory, environment, require_native, failfast):
    work = directory / task['name']
    work.mkdir()
    plan_path, result_path = work / 'plan.json', work / 'result.json'
    plan_path.write_text(json.dumps(task), encoding='utf-8')
    env = dict(environment)
    # Do not lengthen Python's TEMP/TMP: Windows path-boundary fixtures need short paths.
    # runtime.environment applies these only to SDK/Godot children.
    scratch = root / 'artifacts/runtime' / ('rp-' + task['nonce'].split(':')[0][:12]) / task['slot']
    env['VOLIBEAR_RUNTIME_TEMP'] = str(scratch / 'tmp')
    env['NUGET_SCRATCH'] = str(scratch / 'nuget')
    command = [sys.executable, '-B', str(root / 'tools/regression.py'),
               '--worker-plan', str(plan_path), '--worker-result', str(result_path)]
    if require_native:
        command.append('--require-native')
    if failfast:
        command.append('--failfast')
    began = time.monotonic()
    record = {'task': task['name'], 'nonce': task['nonce'], 'result_path': str(result_path),
              'log': str(work / 'output.log')}
    try:
        with (work / 'output.log').open('w', encoding='utf-8') as stream:
            completed = subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record['returncode'] = completed.returncode
        record['report'] = json.loads(result_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        record.update(returncode=record.get('returncode', -1), infrastructure_error=str(error))
    record['wall_seconds'] = round(time.monotonic() - began, 3)
    return record


def aggregate(expected, tasks, records, *, require_native):
    """Only a complete, current, exactly-once set of real worker outcomes can pass."""
    result = {'schema': 1, 'status': 'passed',
              'required_scope': 'installed-game-references' if require_native else 'available-environment',
              'native_gameplay_executed': False, 'tests_run': 0, 'passed': 0,
              **{field: [] for field in LIST_FIELDS}}
    problems, executed = [], []
    expected_tasks = {task['name']: task for task in tasks}
    seen = Counter()
    if Counter(test for task in tasks for test in task['test_ids']) != Counter(expected):
        problems.append('task plan does not exactly cover discovery')
    if len(set(expected)) != len(expected) or len(expected_tasks) != len(tasks):
        problems.append('duplicate discovery IDs or task names')
    for record in records:
        name = record.get('task')
        seen[name] += 1
        task = expected_tasks.get(name)
        report = record.get('report')
        if task is None or not isinstance(report, dict):
            problems.append(f'{name}: unknown task or missing/malformed worker report')
            continue
        if (record.get('returncode') != 0 or record.get('infrastructure_error')
                or record.get('nonce') != task['nonce'] or report.get('nonce') != task['nonce']
                or report.get('task') != name or report.get('schema') != 1
                or report.get('required_scope') != result['required_scope']
                or report.get('native_gameplay_executed') is not False):
            problems.append(f'{name}: worker exit, identity or scope invalid')
        if report.get('status') != 'passed':
            problems.append(f'{name}: worker failed')
        for field in ('requested_test_ids', 'loaded_test_ids', 'executed_test_ids'):
            values = report.get(field)
            if (not isinstance(values, list) or not all(isinstance(value, str) for value in values)
                    or Counter(values) != Counter(task['test_ids'])):
                problems.append(f'{name}: {field} coverage mismatch')
        actual = report.get('executed_test_ids', [])
        if isinstance(actual, list) and all(isinstance(value, str) for value in actual):
            executed.extend(actual)
        for field in COUNT_FIELDS:
            value = report.get(field)
            if type(value) is not int or value < 0:
                problems.append(f'{name}: invalid {field}')
            else:
                result[field] += value
        for field in LIST_FIELDS:
            value = report.get(field)
            if not isinstance(value, list):
                problems.append(f'{name}: invalid {field}')
            else:
                result[field].extend(value)
        if report.get('tests_run') != len(task['test_ids']):
            problems.append(f'{name}: tests_run coverage mismatch')
    if seen != Counter({name: 1 for name in expected_tasks}):
        problems.append('missing or duplicate worker results')
    if Counter(executed) != Counter(expected):
        problems.append('executed test IDs do not exactly cover discovery')
    if any(result[field] for field in ('failures', 'errors', 'expected_failures',
                                       'unexpected_successes', 'unavailable_required_checks')):
        problems.append('regression outcomes contain failures or unavailable required checks')
    if result['passed'] + len(result['skipped']) != len(expected):
        problems.append('success/skip totals do not cover discovered tests')
    # Reapply the original skip policy centrally; never trust a worker's status alone.
    from tools.regression import LINUX_PLATFORM_REASONS, OTHER_PLATFORM_REASONS
    linux_skips = {
        'test_window_startup_hint.StartupHintRouting.test_missing_compiler_fails_instead_of_activating_fallback':
            'Linux x86_64 tool',
        'test_window_startup_hint.StartupHintRouting.test_real_dlopen_dlsym_pre_map_once_and_unrelated_executable_untouched':
            'Linux C compiler ABI fixture',
    }
    skip_ids = set()
    for row in result['skipped']:
        if not isinstance(row, dict) or not isinstance(row.get('test'), str) or not isinstance(row.get('reason'), str):
            problems.append('malformed skip receipt')
            continue
        if row['test'] not in expected or row['test'] in skip_ids:
            problems.append('unknown or duplicate skipped test ID: ' + row['test'])
        skip_ids.add(row['test'])
        if require_native:
            allowed = row['reason'] in (LINUX_PLATFORM_REASONS if os.name == 'nt' else OTHER_PLATFORM_REASONS)
            if os.name == 'nt':
                allowed = allowed and linux_skips.get(row['test']) == row['reason']
            if not allowed:
                problems.append('unavailable required check: ' + row['test'])
    result['errors'].extend(problems)
    if problems:
        result['status'] = 'failed'
    result.update(discovered_test_ids=expected, executed_test_ids=executed, workers=records,
                  serial_bucket_reason=REMAINDER_REASON)
    return result


def run(suite, *, jobs, root, directory, environment, require_native, failfast=False):
    if not 1 <= jobs <= 6:
        raise ValueError('Regression jobs must be between 1 and 6')
    expected, tasks = plan(suite)
    nonce = uuid.uuid4().hex
    directory = Path(directory) / ('rp-' + nonce[:12])
    directory.mkdir(parents=True)
    for index, task in enumerate(tasks):
        task['nonce'] = nonce + ':' + task['name']
        task['slot'] = str(index)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(execute, task, root=root, directory=directory,
                               environment=environment, require_native=require_native,
                               failfast=failfast) for task in tasks]
        records = []
        for task, future in zip(tasks, futures):
            try:
                records.append(future.result())
            except Exception as error:
                records.append({'task': task['name'], 'nonce': task['nonce'], 'returncode': -1,
                                'infrastructure_error': repr(error)})
    report = aggregate(expected, tasks, records, require_native=require_native)
    report.update(jobs=jobs, worker_artifacts=str(directory))
    return report
