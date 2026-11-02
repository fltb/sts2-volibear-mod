"""Merchant adapter scope/dispatch tests; stubs are not native gameplay proof."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MerchantIntegrationTests(unittest.TestCase):
    def test_adapter_is_installed_on_normal_entry(self):
        source = (ROOT / 'src/Volibear/ModEntry.cs').read_text()
        self.assertIn('Presentation.VolibearMerchantIntegration.Install();', source)
        self.assertLess(source.index('Presentation.VolibearMerchantIntegration.Install();'),
                        source.index('VOLIBEAR_TEST_DATA_ROOT'))

    def test_scoped_animation_dispatch_stub(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Local SDK unavailable; merchant stub not run')
        dotnet = Path(json.loads(config_path.read_text())['dotnet'])
        env = dict(os.environ, DOTNET_ROOT=str(dotnet.parent))
        result = subprocess.run([str(dotnet), 'run', '--project',
            str(ROOT / 'tests/merchant_integration/MerchantIntegration.Tests.csproj'),
            '-c', 'Release'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('stub logic test; not Godot execution', result.stdout)
