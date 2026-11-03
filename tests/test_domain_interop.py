"""Execute production provenance/cost adapters. Native game binding remains a separate gate."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class DomainInterop(unittest.TestCase):
    def test_real_harmony_reentry_and_mixed_contributions(self):
        runtime = fixture_runtime(self, 'sdk', 'harmony', root=ROOT)
        result = runtime.run('tests/domain_interop/DomainInterop.csproj', args=('--nologo',), timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        entry = re.search(r'^DOMAIN_NATIVE_ENTRY_PASS checks=(\d+) real-harmony=true native-gameplay=NOT_RUN$', result.stdout, re.MULTILINE)
        contribution = re.search(r'^DOMAIN_CARD_INTEROP_PASS checks=(\d+) production-adapters=true native-gameplay=NOT_RUN$', result.stdout, re.MULTILINE)
        self.assertIsNotNone(entry, result.stdout)
        self.assertIsNotNone(contribution, result.stdout)
        self.assertGreaterEqual(int(entry.group(1)), 98)
        self.assertGreaterEqual(int(contribution.group(1)), 49)


if __name__ == '__main__':
    unittest.main()
