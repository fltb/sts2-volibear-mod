"""Optional real Harmony on synthetic async types; requires an explicit/local upstream DLL."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = {'normal-reentry': 4, 'await-resume': 4, 'early-veto': 4,
         'late-veto': 4, 'public-veto': 4, 'natural-late-veto': 3}


class EngageHarmony(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = ROOT / '.local/config.json'
        settings = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
        cls.dotnet = settings.get('dotnet') or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        harmony = Path(os.environ.get('VOLIBEAR_HARMONY', str(ROOT / '.local/dependencies/Harmony-2.4.2/0Harmony.dll')))
        if not harmony.is_file() and 'VOLIBEAR_HARMONY' not in os.environ and settings.get('game_dir'):
            data = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
            harmony = Path(settings['game_dir']) / data / '0Harmony.dll'
        if not cls.dotnet or not Path(cls.dotnet).is_file() or not harmony.is_file():
            raise unittest.SkipTest('SDK or upstream Harmony unavailable; real patch fixture NOT_RUN')
        result = cls.invoke('build', str(ROOT / 'tests/engage_adapter/harmony/RealHarmony.csproj'),
                            '-c', 'Release', '--nologo', '-p:HarmonyPath=' + str(harmony.resolve()))
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.dotnet), *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=dict(os.environ, DOTNET_NOLOGO='1'))

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
