"""Compile the production Summon transport; real CLR boxes/TCS, not game acceptance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tests/summon_registration/SummonRegistration.Tests.csproj'

class SummonRegistrationTests(unittest.TestCase):
    def test_project_compiles_actual_production_transport_without_native_models(self):
        project = ET.parse(PROJECT).getroot()
        includes = [node.attrib['Include'] for node in project.findall('.//Compile')]
        self.assertEqual(includes, ['../../src/Volibear/Core/SummonRegistration.cs'])
        self.assertFalse(project.findall('.//Reference'))
        source = (PROJECT.parent / 'Program.cs').read_text(encoding='utf-8')
        self.assertIn('SummonRegistration.Await(ref Builder', source)
        self.assertNotIn('.BindBeforeSchedule(', source)
        self.assertIn('new TaskCompletionSource', source)

    def test_production_real_clr_registration_lifetime_matrix(self):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        dotnet = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not dotnet or not Path(dotnet).is_file():
            self.skipTest('SDK unavailable; NOT_RUN')
        result = subprocess.run([dotnet, 'run', '-c', 'Release', '--project', str(PROJECT)],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180,
                                env=dict(os.environ, DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS 186 production Summon registration/lifetime CLR checks; game NOT_RUN', result.stdout)

if __name__ == '__main__':
    unittest.main()
