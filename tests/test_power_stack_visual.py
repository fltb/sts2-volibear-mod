"""UI grouping regressions; no game, no production build, no input simulation."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class PowerStackVisualTests(unittest.TestCase):
    def run_fixture(self, project):
        requirements = ('harmony',) if project == 'PowerStackVisual.csproj' else ('native',)
        runtime = fixture_runtime(self, 'sdk', *requirements, root=ROOT)
        # SDK artifacts layout separates both bin AND obj by project name. These
        # projects share a directory; an OutputPath-only override leaves stale run metadata.
        artifacts = ROOT / 'artifacts/power-stack-visual-tests'
        result = runtime.run(ROOT / 'tests/power_stack_visual' / project, artifacts=artifacts, timeout=120)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        return output

    def test_grouping_labels_hover_and_lifecycle(self):
        output = self.run_fixture('PowerStackVisual.csproj')
        self.assertIn('POWER_STACK_VISUAL_PASS checks=48 production-ui=LINKED tree-and-projection=TEST-DOUBLES', output)

    def test_pinned_native_fields_layout_and_actual_ui_patch_installation(self):
        output = self.run_fixture('NativeAbi.csproj')
        self.assertIn('POWER_STACK_VISUAL_ABI_PASS checks=15 native-layout-loads=6 Godot-render=NOT_RUN', output)


if __name__ == '__main__':
    unittest.main()
