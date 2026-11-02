"""Execute production provenance/cost adapters. Native game binding remains a separate gate."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DomainInterop(unittest.TestCase):
    def test_real_harmony_reentry_and_mixed_contributions(self):
        config_path = ROOT / '.local/config.json'
        config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.is_file() else {}
        dotnet = config.get('dotnet') or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        harmony = Path(os.environ.get('VOLIBEAR_HARMONY', ROOT / '.local/dependencies/Harmony-2.4.2/0Harmony.dll'))
        if not harmony.is_file() and 'VOLIBEAR_HARMONY' not in os.environ and config.get('game_dir'):
            data = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
            harmony = Path(config['game_dir']) / data / '0Harmony.dll'
        if not dotnet or not Path(dotnet).is_file() or not harmony.is_file():
            self.skipTest('SDK or upstream Harmony unavailable; production interop fixtures NOT_RUN')
        result = subprocess.run([str(dotnet), 'run', '--project', 'tests/domain_interop/DomainInterop.csproj',
                                 '-c', 'Release', '--nologo', '-p:HarmonyPath=' + str(harmony.resolve())],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180,
                                env=dict(os.environ, DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        entry = re.search(r'^DOMAIN_NATIVE_ENTRY_PASS checks=(\d+) real-harmony=true native-gameplay=NOT_RUN$', result.stdout, re.MULTILINE)
        contribution = re.search(r'^DOMAIN_CARD_INTEROP_PASS checks=(\d+) production-adapters=true native-gameplay=NOT_RUN$', result.stdout, re.MULTILINE)
        self.assertIsNotNone(entry, result.stdout)
        self.assertIsNotNone(contribution, result.stdout)
        self.assertGreaterEqual(int(entry.group(1)), 98)
        self.assertGreaterEqual(int(contribution.group(1)), 49)


if __name__ == '__main__':
    unittest.main()
