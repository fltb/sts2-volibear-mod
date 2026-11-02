"""Pinned native respawn counter guard; IL checks, not gameplay evidence."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RespawnGuardTests(unittest.TestCase):
    def test_actual_native_counter_guard_and_rejections(self):
        config = ROOT / '.local/config.json'
        if not config.is_file():
            self.skipTest('Pinned native configuration unavailable; respawn IL NOT RUN')
        settings = json.loads(config.read_text(encoding='utf-8'))
        data = Path(settings['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        required = [Path(settings['dotnet']), baselib, *(data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        if not all(path.is_file() for path in required):
            self.skipTest('Actual SDK/native/BaseLib references unavailable; respawn IL NOT RUN')
        result = subprocess.run([
            settings['dotnet'], 'run', '--project', str(ROOT / 'tests/domain_revival_respawn_guard/DomainRevivalRespawnGuard.Tests.csproj'),
            '-c', 'Release', '-p:Sts2DataDir=' + str(data), '--nologo',
        ], cwd=ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RESPAWN_GUARD_IL_PASS checks=9 negatives=4 native-gameplay=NOT_RUN', result.stdout)
        self.assertIn('REVIVE_AWAIT_GUARD_PASS generic-discard=true negatives=3 native-gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
