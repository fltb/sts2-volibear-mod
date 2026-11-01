"""Independent actual-game metadata checks; no stub APIs and no game launch."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeFlowContract(unittest.TestCase):
    def test_selector_rewards_and_room_entries_bind_actual_installed_game(self):
        config = ROOT/'.local/config.json'
        if not config.is_file():
            self.skipTest('Actual game configuration unavailable; native flow API binding NOT_RUN')
        values = json.loads(config.read_text(encoding='utf-8-sig'))
        sdk = Path(values['dotnet'])
        data = Path(values['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        if not sdk.is_file() or not all((data/name).is_file() for name in ('sts2.dll', 'GodotSharp.dll')):
            self.skipTest('Actual SDK/game references unavailable; native flow API binding NOT_RUN; no substitutes')
        project = ROOT/'tests/native/native-flow-contract/NativeFlowContract.csproj'
        built = subprocess.run([str(sdk), 'build', str(project), '-c', 'Release',
                                '-p:Sts2DataDir='+str(data), '--nologo'], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
        result = subprocess.run([str(sdk), str(ROOT/'artifacts/native-flow-contract/bin/net9.0/NativeFlowContract.dll')],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('NATIVE_FLOW_CONTRACT_PASS checks=18 references=actual-game gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__': unittest.main()
