"""Structural build gate against the real installed game/BaseLib assemblies."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class NativeCompatibilityTests(unittest.TestCase):
    def test_curated_native_surface_resolves_and_unknown_builds_are_gated(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run('tests/native_compatibility/NativeCompatibility.Tests.csproj', timeout=120)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('NATIVE_COMPATIBILITY_PASS checks=4', output)


if __name__ == '__main__':
    unittest.main()
