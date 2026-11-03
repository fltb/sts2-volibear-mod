"""Delivery must not treat missing native-reference checks as successful execution."""
import unittest

from tools.regression import summarize


class RegressionResultTests(unittest.TestCase):
    def outcome(self, skip_reason=None, error=False):
        test = unittest.FunctionTestCase(lambda: None, description='independent fixture')
        result = unittest.TestResult()
        result.startTest(test)
        if skip_reason:
            result.addSkip(test, skip_reason)
        elif error:
            try:
                raise RuntimeError('binding failed')
            except RuntimeError:
                import sys
                result.addError(test, sys.exc_info())
        else:
            result.addSuccess(test)
        result.stopTest(test)
        return result

    def test_native_skip_blocks_delivery_but_is_visible_in_cloud_report(self):
        result = self.outcome('Pinned native assemblies unavailable; native IL checks NOT RUN')
        local = summarize(result, require_native=True, platform='posix')
        self.assertEqual(local['status'], 'failed')
        self.assertEqual(local['passed'], 0)
        self.assertEqual(len(local['unavailable_required_checks']), 1)
        cloud = summarize(result, require_native=False, platform='posix')
        self.assertEqual(cloud['status'], 'passed')
        self.assertEqual(len(cloud['skipped']), 1)
        self.assertFalse(cloud['native_gameplay_executed'])

    def test_only_actual_other_platform_checks_may_skip(self):
        result = self.outcome('Windows junction migration')
        self.assertEqual(summarize(result, require_native=True, platform='posix')['status'], 'passed')
        self.assertEqual(summarize(result, require_native=True, platform='nt')['status'], 'failed')
        self.assertEqual(summarize(self.outcome('unknown skip'), require_native=True)['status'], 'failed')

    def test_linux_only_checks_skip_only_on_windows(self):
        for reason in ('Linux x86_64 tool', 'Linux C compiler ABI fixture'):
            result = self.outcome(reason)
            self.assertEqual(summarize(result, require_native=True, platform='nt')['status'], 'passed')
            self.assertEqual(summarize(result, require_native=True, platform='posix')['status'], 'failed')
        self.assertEqual(summarize(self.outcome('sdk runtime unavailable'),
                                  require_native=True, platform='nt')['status'], 'failed')

    def test_executed_failure_or_success_remains_decisive(self):
        failed = summarize(self.outcome(error=True), require_native=True)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['passed'], 0)
        passed = summarize(self.outcome(), require_native=True)
        self.assertEqual(passed['status'], 'passed')
        self.assertEqual(passed['passed'], 1)


if __name__ == '__main__':
    unittest.main()
