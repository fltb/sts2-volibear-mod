"""Real Godot/Harmony scene conversion, with only the game trail type doubled.

Requires the Mono Godot 4.5.1 distribution (including its local SDK nupkgs), .NET
and Harmony. This fixture does not start StS2 or claim native gameplay acceptance.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class TrailCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', 'harmony', 'godot', root=ROOT)
        packages = Path(os.environ.get('VOLIBEAR_GODOT_NUPKGS') or
                        cls.runtime.godot.parent / 'GodotSharp/Tools/nupkgs')
        if not (packages / 'Godot.NET.Sdk.4.5.1.nupkg').is_file():
            raise unittest.SkipTest('Godot 4.5.1 Mono SDK nupkgs missing; set VOLIBEAR_GODOT_NUPKGS')
        output = ROOT / 'artifacts/trail-compatibility'
        output.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='isolated-', dir=output)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        shutil.copytree(ROOT / 'tests/trail_compatibility', cls.work, dirs_exist_ok=True)
        configuration = ET.Element('configuration')
        sources = ET.SubElement(configuration, 'packageSources')
        ET.SubElement(sources, 'clear')
        ET.SubElement(sources, 'add', key='godot-local', value=str(packages))
        ET.ElementTree(configuration).write(cls.work / 'NuGet.Config', encoding='utf-8')
        cls.env = cls.runtime.environment()
        cls.env.update(GODOT_SILENCE_ROOT_WARNING='1',
                       NUGET_PACKAGES=str(cls.work / 'packages'))
        build = cls.invoke(cls.runtime.dotnet, 'build', cls.work / 'TrailCompatibility.csproj',
                           '-c', 'Debug', '--nologo', '-p:HarmonyPath=' + str(cls.runtime.harmony),
                           '-p:TrailCompatibilitySource=' + str(ROOT / 'src/Volibear/Presentation/VolibearTrailFactory.cs'))
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        imported = cls.invoke(cls.runtime.godot, '--headless', '--path', cls.work,
                              '--editor', '--import', '--quit')
        if imported.returncode:
            raise AssertionError(imported.stdout + imported.stderr)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(arg) for arg in args], cwd=cls.work, env=cls.env,
                              text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=120)

    def test_real_scene_conversion_with_foreign_registration_orders(self):
        for order in ('foreign-first', 'volibear-first'):
            with self.subTest(order=order):
                result = self.invoke(self.runtime.godot, '--headless', '--path', self.work, '--', order)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                receipts = re.findall(
                    r'^TRAIL_COMPATIBILITY_PASS order=(\S+) assertions=(\d+) godot=REAL harmony=REAL '
                    r'game-type=DOUBLE native-gameplay=NOT_RUN$', result.stdout, re.MULTILINE)
                self.assertEqual(len(receipts), 1, result.stdout + result.stderr)
                self.assertEqual(receipts[0][0], order)
                self.assertGreaterEqual(int(receipts[0][1]), 35)
                self.assertNotIn('ERROR:', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
