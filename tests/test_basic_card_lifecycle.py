"""Execute production B04/lifecycle sources with command-boundary doubles, not a game."""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BasicCardLifecycleTests(unittest.TestCase):
    def test_actual_b04_stops_at_terminal_block_and_attack_boundaries(self):
        dotnet = os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet and (ROOT / '.local/dotnet/dotnet').is_file():
            dotnet = str(ROOT / '.local/dotnet/dotnet')
        if not dotnet:
            self.skipTest('.NET SDK required for card lifecycle unit tests')
        result = subprocess.run(
            [dotnet, 'run', '--project', str(ROOT / 'tests/card_lifecycle/CardLifecycle.csproj'),
             '--configuration', 'Release'],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            env=dict(os.environ, DOTNET_NOLOGO='1',
                     DOTNET_CLI_HOME=str(ROOT / '.local/dotnet-home'),
                     NUGET_PACKAGES=str(ROOT / '.local/nuget/packages'),
                     DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',
                     DOTNET_CLI_TELEMETRY_OPTOUT='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('CARD_LIFECYCLE_UNIT_OK checks=20 engine=STUBBED native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
