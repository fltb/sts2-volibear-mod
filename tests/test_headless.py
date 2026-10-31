import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import headless


class HeadlessRunnerTests(unittest.TestCase):
    def test_exit_zero_alone_not_success(self):
        self.assertFalse(all(headless.evaluate(0, False, '').values()))

    def test_engine_error_rejects_load_marker(self):
        checks = headless.evaluate(0, False,
            'Steam initialization skipped\n[Volibear] LOAD_OK\nSCRIPT ERROR: failed')
        self.assertFalse(checks['no_runtime_errors'])

    def test_engine_teardown_leaks_are_not_runtime_errors(self):
        leak = ("ERROR: 27 RID allocations of type 'PN13RendererDummy14TextureStorage"
                "12DummyTextureE' were leaked at exit.")
        log = 'Steam initialization skipped\n[Volibear] LOAD_OK\n' + leak
        checks = headless.evaluate(0, False, log)
        self.assertTrue(checks['no_runtime_errors'])
        stock = headless.teardown_categories([leak])
        self.assertTrue(headless.evaluate(0, False, log, stock)['teardown_matches_stock'])

    def test_teardown_category_not_in_stock_control_fails(self):
        stock = headless.teardown_categories(
            ["ERROR: 27 RID allocations of type 'A' were leaked at exit."])
        novel = "ERROR: 3 RID allocations of type 'SomethingNew' were leaked at exit."
        self.assertFalse(headless.evaluate(0, False, novel, stock)['teardown_matches_stock'])
        # Counts differ per run; only the category may be compared.
        same = headless.teardown_categories(
            ["ERROR: 99 RID allocations of type 'A' were leaked at exit."])
        self.assertTrue(headless.evaluate(0, False, novel.replace('SomethingNew', 'A'), stock)['teardown_matches_stock'])
        self.assertEqual(same, stock)

    def test_timeout_always_fails(self):
        self.assertFalse(headless.evaluate(0, True,
            'Steam initialization skipped\n[Volibear] LOAD_OK')['exited_zero'])

    def test_cloud_backend_rejected(self):
        self.assertFalse(headless.evaluate(0, False,
            'Steam initialization skipped\nwrite saves to steam storage')['no_cloud_backend'])

    def test_scenario_evidence_rejects_stale_missing_and_malformed(self):
        record = dict(scenario='baseline', token='current', passed=True,
                      before=80, after=74, resultCount=1, roundBefore=1, roundAfter=2,
                      api='DamageCmd.Attack', testMode=False,
                      cardApi='CardCmd.AutoPlay:StrikeIronclad',
                      cardTargetBefore=15, cardTargetAfter=9)
        line = '[Volibear] BASELINE_RESULT ' + json.dumps(record)
        self.assertTrue(headless.scenario_evidence(line, 'current', 'baseline')[1])
        for log in ('', line + '\n' + line, '[Volibear] BASELINE_RESULT []',
                    '[Volibear] BASELINE_RESULT broken'):
            self.assertFalse(headless.scenario_evidence(log, 'current', 'baseline')[1])
        self.assertFalse(headless.scenario_evidence(line, 'stale', 'baseline')[1])
        record['after'] = 15
        self.assertFalse(headless.scenario_evidence('[Volibear] BASELINE_RESULT ' +
            json.dumps(record), 'current', 'baseline')[1])

    def test_engage_evidence_requires_exact_variant_and_absorption(self):
        import copy
        record = dict(engageEnabled=True, skippedActions=1,
                      responseCount=1, responseBlockBefore=27, responseBlockAfter=30, followupDamage=1,
                      engageOrder=['pre-effect-finished', 'enemy-action-finished',
                                   'completion-response', 'duplicate-rejected', 'remaining-card-effect'],
                      engage=dict(Performed=True, Absorbed=3, Completed=True),
                      duplicate=dict(Performed=False, Absorbed=0, Completed=False))
        self.assertTrue(headless.engage_evidence(record, True))
        self.assertFalse(headless.engage_evidence(record, False))
        self.assertFalse(headless.engage_evidence(None, True))
        for key, value in [('engageEnabled', False), ('skippedActions', 0),
                           ('engage', None), ('duplicate', {}), ('responseCount', 2),
                           ('responseBlockAfter', 27), ('followupDamage', 0), ('engageOrder', [])]:
            bad = copy.deepcopy(record)
            bad[key] = value
            self.assertFalse(headless.engage_evidence(bad, True))
        for field, value in [('Absorbed', 0), ('Completed', False), ('Performed', False)]:
            bad = copy.deepcopy(record)
            bad['engage'][field] = value
            self.assertFalse(headless.engage_evidence(bad, True))
        self.assertTrue(headless.engage_evidence(dict(engageEnabled=False,
            engage=None, duplicate=None, skippedActions=0), False))

    def _spawn(self, directory, command):
        output = (directory / 'stdout.log').open('w')
        try:
            process, job = headless.spawn_owned(command, str(directory), os.environ.copy(), output)
        finally:
            # The child owns its duplicated handle; Windows cannot delete an open file.
            output.close()
        self.addCleanup(headless.close_owned, job)
        return process, job

    def test_owned_process_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            process, job = self._spawn(directory, [sys.executable, '-c', 'import time; time.sleep(60)'])
            code, timed_out = headless.wait_owned_process(process, 0.05, job)
            self.assertTrue(timed_out)
            self.assertNotEqual(code, 0)
            self.assertIsNotNone(process.poll())

    def test_wrapper_exit_still_cleans_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            pidfile = directory / 'child.pid'
            script = ('import subprocess,sys; from pathlib import Path; '
                      'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                      'Path(sys.argv[1]).write_text(str(p.pid))')
            process, job = self._spawn(directory, [sys.executable, '-c', script, str(pidfile)])
            code, timed_out = headless.wait_owned_process(process, 5, job)
            self.assertEqual(code, 0)
            self.assertFalse(timed_out)
            pid = int(pidfile.read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if not headless.process_alive(pid):
                    break
                time.sleep(0.01)
            else:
                self.fail('Owned child survived wrapper cleanup')

    def test_environment_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env = headless.isolated_env(directory)
            for key, _ in headless.ISOLATION_BINDINGS:
                self.assertTrue(Path(env[key]).is_relative_to(directory))
                self.assertTrue(Path(env[key]).is_dir())
            self.assertTrue(headless.user_data_root(directory).is_relative_to(directory))

    def test_engine_log_preferred_over_redirected_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'stdout.log').write_text('')
            (directory / 'game.log').write_text('[Volibear] LOAD_OK\n')
            self.assertIn('LOAD_OK', headless.combined_log(directory))


if __name__ == '__main__':
    unittest.main()
