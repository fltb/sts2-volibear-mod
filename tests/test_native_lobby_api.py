"""Execute the actual acceptance binder; this does not replace the two native peers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeLobbyBinding(unittest.TestCase):
    def test_public_signature_binding_and_native_callback_failures(self):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        dotnet = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet or not Path(dotnet).is_file():
            self.skipTest('SDK unavailable; native lobby binder NOT_RUN')
        for arguments in (['build', str(ROOT / 'tests/native_lobby/NativeLobby.csproj'), '-c', 'Release', '--nologo'],
                          [str(ROOT / 'artifacts/native-lobby/bin/net9.0/NativeLobby.dll')]):
            result = subprocess.run([dotnet, *arguments], cwd=ROOT, capture_output=True, text=True,
                                    encoding='utf-8', timeout=180, env=dict(os.environ, DOTNET_NOLOGO='1'))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NATIVE_LOBBY_BINDING_PASS assertions=20 native-network=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
