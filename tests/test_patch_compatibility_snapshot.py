"""Production metadata scanner with real Harmony and a separate foreign assembly.

No game API doubles or StS2 assemblies are needed. This checks patch metadata and
native CLR detours, not game behavior or universal mod compatibility.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime

CASES = ('own-first', 'foreign-first', 'uncommitted-failure', 'empty')
PROJECT = ROOT / 'tests/patch_compatibility_snapshot/PatchCompatibilitySnapshot.Tests.csproj'
DLL = ROOT / 'artifacts/patch-compatibility-snapshot/bin/net9.0/PatchCompatibilitySnapshot.Tests.dll'


class PatchCompatibilitySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', 'harmony', root=ROOT)
        built = cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo',
                           '-p:HarmonyPath=' + str(cls.runtime.harmony.resolve()))
        if built.returncode:
            raise AssertionError(built.stdout + built.stderr)
        listed = cls.invoke(str(DLL), '--list')
        if listed.returncode or tuple(listed.stdout.splitlines()) != CASES:
            raise AssertionError(listed.stdout + listed.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.runtime.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180, env=cls.runtime.environment())

    def test_only_registered_metadata_is_observed_without_reexecution(self):
        for case in CASES:
            with self.subTest(case=case):
                result = self.invoke(str(DLL), case)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, output)
                receipt = re.findall(
                    r'^PATCH_COMPATIBILITY_SNAPSHOT_PASS name=(\S+) assertions=(\d+) harmony=2\.4\.2\.0 native-gameplay=NOT_RUN$',
                    result.stdout, re.MULTILINE)
                self.assertEqual(len(receipt), 1, output)
                self.assertEqual(receipt[0][0], case, output)
                self.assertGreaterEqual(int(receipt[0][1]), 6, output)
                self.assertIn('"status":"metadata_only"', result.stdout)
                self.assertNotIn('"status":"compatible"', result.stdout)


if __name__ == '__main__':
    unittest.main()
