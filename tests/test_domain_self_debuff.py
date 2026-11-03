"""Production-domain contribution semantics and locked native binding checks; no game launch."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class DomainSelfDebuffTests(unittest.TestCase):
    def test_native_bindings_and_temporary_suppression(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/domain_self_debuff/DomainSelfDebuff.Tests.csproj', args=('--nologo',), timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('SELF_DEBUFF_SEMANTICS_PASS checks=37', output)
        self.assertIn('SELF_DEBUFF_NATIVE_BINDINGS_PASS count=28', output)
        self.assertIn('SANDPIT_SEMANTICS_PASS checks=5', output)
        self.assertIn('WEAK_NATIVE_DURATION_PASS checks=5 actual-side-and-skip-callbacks=true decrement-command-seam=true gameplay=NOT_RUN', output)
        self.assertIn('BASELIB_WEAK_DURATION_PASS checks=13 actual-postfix-and-await=true apply-decrement-scene-seams=true gameplay=NOT_RUN', output)
