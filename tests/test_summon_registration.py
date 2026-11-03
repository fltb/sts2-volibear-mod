"""Compile the production Summon transport; real CLR boxes/TCS, not game acceptance."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
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
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        result = runtime.run(PROJECT, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS 186 production Summon registration/lifetime CLR checks; game NOT_RUN', result.stdout)

if __name__ == '__main__':
    unittest.main()
