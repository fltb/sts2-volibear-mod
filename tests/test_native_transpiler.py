"""Real Harmony detours exercise production ordering; no game assemblies are simulated."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime

CASES = (
    'metadata-copy', 'legacy-order-conflict', 'foreign-first', 'volibear-first', 'legal-registration-orders',
    'explicit-foreign-order', 'indirect-foreign-order', 'mixed-owner-priorities',
    'explicit-tail-order', 'uninstall-reinstall', 'nop-padding', 'marked-nops', 'real-conflict',
    'observe-call-composition', 'observe-call-async', 'observe-call-zero-arguments',
    'observe-call-metadata', 'observe-call-validation',
)
PROJECT = ROOT / 'tests/native_transpiler/NativeTranspiler.Tests.csproj'
DLL = ROOT / 'artifacts/native-transpiler/bin/net9.0/NativeTranspiler.Tests.dll'


class NativeTranspilerTests(unittest.TestCase):
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

    def test_native_detours_preserve_foreign_and_internal_effects(self):
        for case in CASES:
            with self.subTest(case=case):
                result = self.invoke(str(DLL), case)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0, output)
                receipts = re.findall(
                    r'^NATIVE_TRANSPILER_PASS name=(\S+) assertions=(\d+) harmony=2\.4\.2\.0 native-gameplay=NOT_RUN$',
                    result.stdout, re.MULTILINE)
                self.assertEqual(len(receipts), 1, output)
                self.assertEqual(receipts[0][0], case, output)
                self.assertGreaterEqual(int(receipts[0][1]), 4, output)


if __name__ == '__main__':
    unittest.main()
