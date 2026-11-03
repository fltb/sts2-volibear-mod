"""Merchant adapter scope/dispatch tests; stubs are not native gameplay proof."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class MerchantIntegrationTests(unittest.TestCase):
    def test_adapter_is_installed_on_normal_entry(self):
        source = (ROOT / 'src/Volibear/ModEntry.cs').read_text()
        self.assertIn('Presentation.VolibearMerchantIntegration.Install();', source)
        self.assertLess(source.index('Presentation.VolibearMerchantIntegration.Install();'),
                        source.index('VOLIBEAR_TEST_DATA_ROOT'))

    def test_scoped_animation_dispatch_stub(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        result = runtime.run('tests/merchant_integration/MerchantIntegration.Tests.csproj', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('stub logic test; not Godot execution', result.stdout)
