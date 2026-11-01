"""Execute the production adapter with explicit API fixtures, never claim native/network acceptance."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    'skipped-actions': 8,
    'shared-opportunity-original-targets': 6,
    'normal-enemy-phase-only': 6,
    'stale-round': 6,
    'nested-failure-cleanup': 5,
    'death-boundaries': 4,
    'stable-group-snapshot': 5,
}


class EngageAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        cls.dotnet = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not cls.dotnet or not Path(cls.dotnet).is_file():
            raise unittest.SkipTest('SDK unavailable; engage adapter NOT_RUN')
        built = cls.invoke('build', str(ROOT / 'tests/engage_adapter/EngageAdapter.csproj'), '-c', 'Release', '--nologo')
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=dict(os.environ, DOTNET_NOLOGO='1'))

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
