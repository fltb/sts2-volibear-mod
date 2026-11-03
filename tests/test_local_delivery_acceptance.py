import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools import local_delivery as delivery


class SummaryTests(unittest.TestCase):
    def setUp(self):
        # These tests exercise worker-local summaries, never the CLI process launcher.
        permit = patch.object(delivery.release_budget, 'worker_permit',
                              side_effect=lambda: {'deadline': time.monotonic() + 30})
        permit.start()
        self.addCleanup(permit.stop)
        supervisor = patch.object(delivery.release_budget, 'supervise',
                                  side_effect=AssertionError('Summary fixture must never launch a release worker'))
        self.supervisor = supervisor.start()
        self.addCleanup(supervisor.stop)

    def tearDown(self):
        self.supervisor.assert_not_called()

    def test_summary_order_and_honest_scope(self):
        result = delivery.acceptance_summary()
        self.assertEqual(list(result['items']), ['A' + str(n) for n in range(1, 10)])
        self.assertEqual(result['human_hearing'], 'not_performed')
        self.assertTrue(all(v['status'] == 'not_run' for v in result['items'].values()))

    def test_failure_writes_summary_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(delivery, 'ROOT', Path(directory)), patch.object(
                    delivery, '_deliver', side_effect=ValueError('gate failed')):
                self.assertEqual(delivery.main(['--verify-release', '--audio-driver', 'PulseAudio']), 1)
            reports = list(Path(directory).glob('.local/release-acceptance/*/summary.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(reports[0].with_suffix('.md').is_file())

    def test_success_is_automated_not_human_acceptance(self):
        def complete(args):
            delivery.mark(args, *args._acceptance['items'])
            return Path('package.zip')
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(delivery, 'ROOT', Path(directory)), patch.object(delivery, '_deliver', side_effect=complete):
                self.assertEqual(delivery.main(['--verify-release', '--audio-driver', 'PulseAudio']), 0)
            report = json.loads(next(Path(directory).glob('.local/release-acceptance/*/summary.json')).read_text())
            self.assertEqual(report['status'], 'automated_acceptance_passed')
            self.assertEqual(report['human_hearing'], 'not_performed')

    def test_lifecycle_is_after_package_and_before_success_output(self):
        import inspect
        source = inspect.getsource(delivery._deliver)
        self.assertLess(source.index('release_package.package('), source.index('package_lifecycle_acceptance.accept('))
        self.assertLess(source.index('package_lifecycle_acceptance.accept('), source.index("print('INSTALLER BUILT:"))
