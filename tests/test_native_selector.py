"""Run the production selection adapter with API fixtures, without game/UI/network claims."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class NativeSelector(unittest.TestCase):
    def test_production_selector_identity_count_ownership_and_cleanup(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        dotnet = str(runtime.dotnet)
        built=subprocess.run([dotnet,'build',str(ROOT/'tests/native_selector/NativeSelector.csproj'),'-c','Release','--nologo'],
                             cwd=ROOT,capture_output=True,text=True,timeout=180, encoding='utf-8', env=runtime.environment())
        self.assertEqual(built.returncode,0,built.stdout+built.stderr)
        result=subprocess.run([dotnet,str(ROOT/'artifacts/native-selector/bin/net9.0/NativeSelector.dll')],
                              cwd=ROOT,capture_output=True,text=True,timeout=60, encoding='utf-8', env=runtime.environment())
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertRegex(result.stdout,r'NATIVE_SELECTOR_PASS assertions=29 native-gameplay=NOT_RUN network-transport=NOT_RUN')


if __name__=='__main__':unittest.main()
