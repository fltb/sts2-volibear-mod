import importlib.util
from pathlib import Path
import sys
import tempfile
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
        self.assertFalse(checks['no_engine_errors'])

    def test_timeout_always_fails(self):
        self.assertFalse(headless.evaluate(0, True,
            'Steam initialization skipped\n[Volibear] LOAD_OK')['exited_zero'])

    def test_cloud_backend_rejected(self):
        self.assertFalse(headless.evaluate(0, False,
            'Steam initialization skipped\nwrite saves to steam storage')['no_cloud_backend'])

    def test_scenario_evidence_rejects_stale_missing_and_malformed(self):
        import json
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

    def test_owned_process_timeout(self):
        import subprocess
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                   start_new_session=True)
        code, timed_out = headless.wait_owned_process(process, 0.05)
        self.assertTrue(timed_out)
        self.assertNotEqual(code, 0)
        self.assertIsNotNone(process.poll())

    def test_wrapper_exit_still_cleans_group(self):
        import os
        import subprocess
        import time
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / 'child.pid'
            script = ('import subprocess,sys; from pathlib import Path; '
                      'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                      'Path(sys.argv[1]).write_text(str(p.pid))')
            process = subprocess.Popen([sys.executable, '-c', script, str(pidfile)],
                                       start_new_session=True)
            code, timed_out = headless.wait_owned_process(process, 5)
            self.assertEqual(code, 0)
            self.assertFalse(timed_out)
            pid = int(pidfile.read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                status = Path(f'/proc/{pid}/stat')
                if not status.exists() or status.read_text().split()[2] == 'Z':
                    break
                time.sleep(0.01)
            else:
                self.fail('Owned child survived wrapper cleanup')

    def test_environment_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env = headless.isolated_env(directory)
            for key in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
                self.assertTrue(Path(env[key]).is_relative_to(directory))
                self.assertTrue(Path(env[key]).is_dir())
