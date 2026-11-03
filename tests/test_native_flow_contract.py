"""Independent actual-game metadata checks; no stub APIs and no game launch."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class NativeFlowContract(unittest.TestCase):
    def test_selector_rewards_and_room_entries_bind_actual_installed_game(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        sdk = runtime.dotnet
        data = runtime.data
        project = ROOT/'tests/native/native-flow-contract/NativeFlowContract.csproj'
        built = subprocess.run([str(sdk), 'build', str(project), '-c', 'Release',
                                '-p:Sts2DataDir='+str(data), '--nologo'], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, env=runtime.environment())
        self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
        result = subprocess.run([str(sdk), str(ROOT/'artifacts/native-flow-contract/bin/net9.0/NativeFlowContract.dll')],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, env=runtime.environment())
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('NATIVE_FLOW_CONTRACT_PASS checks=18 references=actual-game gameplay=NOT_RUN', result.stdout)


if __name__ == '__main__': unittest.main()
