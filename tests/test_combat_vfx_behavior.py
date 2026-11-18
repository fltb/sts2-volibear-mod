"""Run production Godot geometry/lifecycle behavior, without a game fixture."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class CombatVfxBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'godot', root=ROOT)

    def test_production_geometry_and_owner_lifetime(self):
        artifacts = ROOT / 'artifacts/combat-vfx-tests'
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifacts, prefix='geometry-') as output:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'tools/preview_combat_vfx.py'),
                 '--godot', str(self.runtime.godot), '--headless', '--output', output],
                cwd=ROOT, env=self.runtime.environment(), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout[-8000:])
            self.assertIn('VOLIBEAR_COMBAT_VFX_PASS styles=29', result.stdout)


if __name__ == '__main__':
    unittest.main()
