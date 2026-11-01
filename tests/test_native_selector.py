"""Run the production selection adapter with API fixtures, without game/UI/network claims."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeSelector(unittest.TestCase):
    def test_production_selector_identity_count_ownership_and_cleanup(self):
        local=ROOT/'.local/config.json'
        configured=json.loads(local.read_text()).get('dotnet') if local.is_file() else None
        dotnet=configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet or not Path(dotnet).is_file():self.skipTest('SDK unavailable; native selector adapter NOT_RUN')
        built=subprocess.run([dotnet,'build',str(ROOT/'tests/native_selector/NativeSelector.csproj'),'-c','Release','--nologo'],
                             cwd=ROOT,capture_output=True,text=True,timeout=180)
        self.assertEqual(built.returncode,0,built.stdout+built.stderr)
        result=subprocess.run([dotnet,str(ROOT/'artifacts/native-selector/bin/net9.0/NativeSelector.dll')],
                              cwd=ROOT,capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertRegex(result.stdout,r'NATIVE_SELECTOR_PASS assertions=29 native-gameplay=NOT_RUN network-transport=NOT_RUN')


if __name__=='__main__':unittest.main()
