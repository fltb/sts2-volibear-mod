"""Optional real Harmony on synthetic async types; requires an explicit/local upstream DLL."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
CASES = {'normal-reentry': 4, 'await-resume': 4, 'early-veto': 4,
         'late-veto': 4, 'public-veto': 4, 'natural-late-veto': 3}


class EngageHarmony(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', 'harmony', root=ROOT)
        cls.dotnet = str(cls.runtime.dotnet)
        harmony = cls.runtime.harmony
        result = cls.invoke('build', str(ROOT / 'tests/engage_adapter/harmony/RealHarmony.csproj'),
                            '-c', 'Release', '--nologo', '-p:HarmonyPath=' + str(harmony.resolve()))
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=cls.runtime.environment())

    def test_actual_patch_install_and_veto(self):
        for name, count in CASES.items():
            with self.subTest(case=name):
                result = self.invoke(str(ROOT / 'artifacts/engage-harmony/bin/net9.0/RealHarmony.dll'), name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                receipts = re.findall(r'^ENGAGE_HARMONY_PASS name=(\S+) assertions=(\d+) harmony=2\.4\.2\.0 native-gameplay=NOT_RUN multiplayer-network=NOT_RUN$',
                                      result.stdout, re.MULTILINE)
                self.assertEqual(receipts, [(name, str(count))], result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
