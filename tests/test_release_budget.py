"""Short real Python process trees, never the game or the full release gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import release_budget as budget
from tools import local_delivery as delivery

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBudgetTests(unittest.TestCase):
    def run_worker(self, body, *, seconds=3, reserve=.5, started=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        worker = root / 'worker.py'
        worker.write_text('import sys, os, time, subprocess\nfrom pathlib import Path\n'
                          + 'sys.path.insert(0, ' + repr(str(ROOT)) + ')\n'
                          + 'from tools import release_budget as b\n'
                          + 'permit=b.worker_permit()\nassert permit is not None\n'
                          + 'assert b.WORKER_KEY not in os.environ\n' + body, encoding='utf-8')
        code = budget.supervise([sys.executable, '-B', worker], root, seconds=seconds,
                                cleanup_reserve=reserve, started=started)
        report = json.loads(next((root / '.local/release-deadlines').glob('*/deadline.json')).read_text())
        return code, report, root

    def test_success_and_failure_exit_codes_and_reports(self):
        for expected in (0, 7):
            with self.subTest(code=expected):
                code, report, _ = self.run_worker('raise SystemExit(' + str(expected) + ')\n')
                self.assertEqual(code, expected, report)
                self.assertEqual(report['status'], 'completed' if expected == 0 else 'failed')
                self.assertEqual(report['package_accepted'], expected == 0)
                self.assertTrue(report['cleanup_complete'])
                self.assertLess(report['elapsed_seconds'], 3)

    def test_timeout_kills_transitive_child_in_new_session_even_after_its_parent_exits(self):
        grandchild = "from pathlib import Path; import os,time; Path('grandchild.pid').write_text(str(os.getpid())); time.sleep(60)"
        child = ('import subprocess,sys,os; subprocess.Popen([sys.executable, "-c", '
                 + repr(grandchild) + '], start_new_session=os.name!="nt")')
        body = ('subprocess.Popen([sys.executable,"-c",' + repr(child)
                + '], start_new_session=os.name!="nt").wait()\ntime.sleep(60)\n')
        code, report, root = self.run_worker(body)
        self.assertEqual(code, 124)
        self.assertEqual(report['status'], 'deadline_exceeded')
        self.assertFalse(report['package_accepted'])
        self.assertTrue(report['cleanup_complete'], report)
        self.assertLess(report['elapsed_seconds'], 3)
        pid = int((root / 'grandchild.pid').read_text())
        if os.name == 'nt':
            from tools import headless
            self.assertFalse(headless.process_alive(pid))
        else:
            self.assertFalse(Path('/proc', str(pid)).exists())

    def test_success_also_cleans_leftover_worker_children(self):
        body = ('child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"], '
                'start_new_session=os.name!="nt")\nPath("child.pid").write_text(str(child.pid))\n')
        code, report, root = self.run_worker(body)
        self.assertEqual(code, 0, report)
        self.assertTrue(report['cleanup_complete'])
        pid = int((root / 'child.pid').read_text())
        if os.name == 'nt':
            from tools import headless
            self.assertFalse(headless.process_alive(pid))
        else:
            self.assertFalse(Path('/proc', str(pid)).exists())

    def test_ownership_failure_never_grants_permit_or_runs_worker_body(self):
        if os.name == 'nt':
            # The supervisor's import must resolve before the helper can be patched.
            tools = str(ROOT / 'tools')
            if tools not in sys.path:
                sys.path.insert(0, tools)
            from tools import headless
            context = patch.object(headless, '_assign_job', return_value=False)
        else:
            context = patch.object(budget, '_subreaper', side_effect=OSError('ownership unavailable'))
        with context:
            code, report, root = self.run_worker('Path("ran").write_text("unexpected")\n')
        self.assertEqual(code, 1)
        self.assertFalse((root / 'ran').exists())
        self.assertEqual(list((root / '.local/release-deadlines').glob('*/permit.json')), [])
        self.assertTrue(report['cleanup_complete'], report)

    def test_proc_ancestry_excludes_unrelated_processes(self):
        rows = {11: (10, 'one', 'S'), 12: (11, 'two', 'S'),
                13: (12, 'three', 'S'), 21: (20, 'other', 'S')}
        self.assertEqual(budget._descendants(rows, 10), {11, 12, 13})

    def test_prior_entry_time_is_not_reset_when_supervision_begins(self):
        code, report, _ = self.run_worker('time.sleep(60)\n', started=time.monotonic() - 1.5)
        self.assertEqual(code, 124)
        self.assertGreaterEqual(report['elapsed_seconds'], 2.5)
        self.assertLess(report['elapsed_seconds'], 3)

    def test_already_expired_budget_does_not_start_worker(self):
        with patch.object(budget.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
            code, report, _ = self.run_worker('raise AssertionError()\n', started=time.monotonic() - 10)
        self.assertEqual(code, 124)
        self.assertNotIn('worker_pid', report)
        self.assertFalse(report['package_accepted'])

    def test_hard_limit_cannot_be_extended(self):
        with self.assertRaises(ValueError):
            budget.supervise([], ROOT, seconds=601)

    def test_partial_or_stale_hidden_worker_environment_is_rejected(self):
        for env in ({budget.WORKER_KEY: 'stale'},
                    {budget.WORKER_KEY: 'stale', budget.PERMIT_KEY: 'absent', budget.PARENT_KEY: '-1'}):
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ValueError):
                    budget.worker_permit()

    def test_release_cli_supervises_before_deliver_and_includes_entry_time(self):
        args = ['--verify-release', '--audio-driver', 'WASAPI']
        with patch.object(budget, 'worker_permit', return_value=None), \
             patch.object(budget, 'supervise', return_value=124) as supervise, \
             patch.object(delivery, 'deliver') as deliver:
            self.assertEqual(delivery.main(args), 124)
            deliver.assert_not_called()
            self.assertEqual(supervise.call_args.kwargs['started'], delivery.ENTRY_STARTED)
            self.assertEqual(supervise.call_args.args[0][2:], args)

    def test_valid_permit_enters_worker_without_recursive_supervisor(self):
        with patch.object(budget, 'worker_permit', return_value={'deadline': time.monotonic() + 20}), \
             patch.object(budget, 'supervise') as supervise, patch.object(delivery, 'deliver') as deliver:
            self.assertEqual(delivery.main(['--verify-release', '--audio-driver', 'WASAPI']), 0)
            supervise.assert_not_called()
            deliver.assert_called_once()

    def test_native_and_peer_timeouts_never_exceed_total_limit(self):
        args = delivery.arguments(['--verify-release', '--audio-driver', 'WASAPI'])
        for command in (delivery.native_command(args, 'python'), delivery.multiplayer_command(args, 'python')):
            self.assertLessEqual(int(command[command.index('--timeout') + 1]), 600)
        self.assertIn('--verify-restart', delivery.native_command(args, 'python'))


if __name__ == '__main__':
    unittest.main()
