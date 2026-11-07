"""Execute the production version guard; no game assemblies or simulated game objects."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class SupportedGameTests(unittest.TestCase):
    def test_wrong_or_missing_release_is_rejected_before_any_mod_initialization(self):
        entry = (ROOT / 'src/Volibear/ModEntry.cs').read_text(encoding='utf-8')
        body = entry.split('public static void Initialize()', 1)[1]
        self.assertLess(body.index('SupportedGameBuild.StructuralCheck'), body.index('SupportedGameBuild.EnsureInstalled'))
        self.assertLess(body.index('SupportedGameBuild.EnsureInstalled'), body.index('ContentRegistry.Register'))
        self.assertLess(body.index('SupportedGameBuild.EnsureInstalled'), body.index('Core.EngageCmd.Install'))
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        result = runtime.run('tests/supported_game/SupportedGame.csproj', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'SUPPORTED_GAME_PASS cases=\d+ native-gameplay=NOT_RUN')


if __name__ == '__main__':
    unittest.main()
