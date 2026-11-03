"""Locked native ending IL plus scoped command-boundary semantics; no game launch."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class ArchitectEndingTests(unittest.TestCase):
    def test_native_victory_chain_and_living_domain_exit(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/architect/Architect.Tests.csproj', args=('--nologo',), timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        receipt = re.search(r'ARCHITECT_ENDING_PASS checks=(\d+) native-sites=2 gameplay=NOT_RUN', output)
        self.assertIsNotNone(receipt, output)
        self.assertGreaterEqual(int(receipt.group(1)), 20)
