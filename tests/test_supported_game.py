"""Execute the production version guard; no game assemblies or simulated game objects."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SupportedGameTests(unittest.TestCase):
    def test_wrong_or_missing_release_is_rejected_before_any_mod_initialization(self):
        entry = (ROOT / 'src/Volibear/ModEntry.cs').read_text(encoding='utf-8')
        body = entry.split('public static void Initialize()', 1)[1]
        self.assertLess(body.index('SupportedGameBuild.EnsureInstalled'), body.index('ContentRegistry.Register'))
        self.assertLess(body.index('SupportedGameBuild.EnsureInstalled'), body.index('Core.EngageCmd.Install'))
        sdk = os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not sdk:
            self.skipTest('SDK unavailable; production version guard NOT_RUN')
        result = subprocess.run(
            [sdk, 'run', '--project', str(ROOT / 'tests/supported_game/SupportedGame.csproj'), '-c', 'Release'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('SUPPORTED_GAME_PASS cases=12 native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
