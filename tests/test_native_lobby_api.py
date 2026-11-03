"""Execute the actual acceptance binder; this does not replace the two native peers."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class NativeLobbyBinding(unittest.TestCase):
    def test_public_signature_binding_and_native_callback_failures(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        dotnet = str(runtime.dotnet)
        for arguments in (['build', str(ROOT / 'tests/native_lobby/NativeLobby.csproj'), '-c', 'Release', '--nologo'],
                          [str(ROOT / 'artifacts/native-lobby/bin/net9.0/NativeLobby.dll')]):
            result = subprocess.run([dotnet, *arguments], cwd=ROOT, capture_output=True, text=True,
                                    encoding='utf-8', timeout=180, env=runtime.environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NATIVE_LOBBY_BINDING_PASS assertions=20 native-network=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
