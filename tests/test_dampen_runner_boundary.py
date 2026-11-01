"""Stock-matched exit noise is common-gate evidence, never a blanket waiver."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import headless
from domain_dampen_evidence import MARKER, check_log
from test_domain_dampen_evidence import fixture, TOKEN


class DampenRunnerBoundaryTests(unittest.TestCase):
    leak = 'ERROR: 5 shaders of type CanvasShaderRD were never freed'
    gates = {'stock_control_success': True, 'teardown_matches_stock': True}

    def log(self, tail='', before=''):
        return MARKER + json.dumps(fixture('off')) + '\n' + before + '\n[Volibear] SHUTDOWN_BEGIN ' + TOKEN + '\n' + tail

    def test_only_matched_post_shutdown_noise_is_delegated_to_common_gates(self):
        text = self.log(self.leak)
        self.assertTrue(check_log(text, TOKEN, 'off'))
        view = headless.dampen_protocol_log(text, TOKEN, self.gates)
        self.assertEqual(check_log(view, TOKEN, 'off'), [])
        self.assertIn(self.leak, text)  # Original report/diagnostic input is untouched.
        stock = headless.teardown_categories([self.leak])
        self.assertTrue(headless.evaluate(0, False, text, stock)['teardown_matches_stock'])

    def test_no_successful_matching_stock_control_never_filters(self):
        text = self.log(self.leak)
        for field in self.gates:
            for value in (False, None, 1, 'true'):
                gates = dict(self.gates, **{field: value})
                with self.subTest(field=field, value=value):
                    self.assertEqual(headless.dampen_protocol_log(text, TOKEN, gates), text)
                    self.assertTrue(check_log(text, TOKEN, 'off'))

    def test_missing_wrong_or_duplicate_token_boundary_never_filters(self):
        text = self.log(self.leak)
        for changed in (text.replace('SHUTDOWN_BEGIN', 'NOT_SHUTDOWN'),
                        text.replace('SHUTDOWN_BEGIN ' + TOKEN, 'SHUTDOWN_BEGIN other'),
                        text + '\n[Volibear] SHUTDOWN_BEGIN ' + TOKEN):
            self.assertEqual(headless.dampen_protocol_log(changed, TOKEN, self.gates), changed)
            self.assertTrue(check_log(changed, TOKEN, 'off'))

    def test_pre_shutdown_even_stock_shaped_error_still_fails_protocol(self):
        text = self.log(self.leak, before=self.leak)
        view = headless.dampen_protocol_log(text, TOKEN, self.gates)
        self.assertEqual(view.count(self.leak), 1)
        self.assertTrue(check_log(view, TOKEN, 'off'))

    def test_late_runtime_unsupported_and_fatal_are_not_hidden(self):
        stock = headless.teardown_categories([self.leak])
        for error in ('ERROR: gameplay broke', 'Unhandled exception: late callback',
                      '[Volibear] DOMAIN_DAMPEN_SOURCE_UNSUPPORTED stale',
                      '[Volibear] DOMAIN_DAMPEN_TRANSACTIONS_ERROR late', 'FATAL: late'):
            with self.subTest(error=error):
                text = self.log(self.leak + '\n' + error)
                view = headless.dampen_protocol_log(text, TOKEN, self.gates)
                self.assertIn(error, view)
                self.assertTrue(check_log(view, TOKEN, 'off'))
                if error.startswith('ERROR:'):
                    self.assertFalse(headless.evaluate(0, False, text, stock)['no_runtime_errors'])

    def test_novel_teardown_category_stays_rejected(self):
        stock = headless.teardown_categories([self.leak])
        text = self.log('ERROR: 1 shaders of type ParticlesShaderRD were never freed')
        checks = headless.evaluate(0, False, text, stock)
        self.assertFalse(checks['teardown_matches_stock'])
        checks['stock_control_success'] = True
        self.assertEqual(headless.dampen_protocol_log(text, TOKEN, checks), text)
        self.assertTrue(check_log(text, TOKEN, 'off'))


if __name__ == '__main__':
    unittest.main()
