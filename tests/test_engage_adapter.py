"""Execute the production adapter with explicit API fixtures, never claim native/network acceptance."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
CASES = {
    'skipped-actions': 8,
    'shared-opportunity-original-targets': 6,
    'normal-enemy-phase-only': 6,
    'stale-round': 6,
    'concurrent-reservation': 6,
    'suspended-run-reset': 14,
    'nested-failure-cleanup': 5,
    'death-boundaries': 4,
    'stable-group-snapshot': 5,
}


class EngageAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', root=ROOT)
        cls.dotnet = str(cls.runtime.dotnet)
        built = cls.invoke('build', str(ROOT / 'tests/engage_adapter/EngageAdapter.csproj'), '-c', 'Release', '--nologo')
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=cls.runtime.environment())

    def test_production_adapter_boundaries(self):
        for case, count in CASES.items():
            with self.subTest(case=case):
                result = self.invoke(str(ROOT / 'artifacts/engage-adapter/bin/net9.0/EngageAdapter.dll'), case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                receipts = re.findall(
                    r'^ENGAGE_ADAPTER_PASS name=(\S+) assertions=(\d+) native-gameplay=NOT_RUN multiplayer-network=NOT_RUN$',
                    result.stdout, re.MULTILINE)
                self.assertEqual(receipts, [(case, str(count))], result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
