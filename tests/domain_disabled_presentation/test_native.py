"""Native-reference presentation regression registered by tools/regression.py."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime


class DomainDisabledPresentationTests(unittest.TestCase):
    def _references(self):
        return fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)

    def test_real_native_hover_entries_and_projection(self):
        runtime = self._references()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('run.py'))], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=130,
                                env=runtime.environment())
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'DOMAIN_DISABLED_PRESENTATION_PASS checks=\d+ native-entry-patches=5 gameplay-predicates=TEST-DOUBLES Godot-render=NOT_RUN')

    def test_linked_visual_unbound_late_bind_rebind_exit_and_reentry(self):
        runtime = fixture_runtime(self, 'sdk', 'harmony', root=ROOT)
        project = ROOT / 'tests/disabled_visual_lifecycle/DisabledVisualLifecycle.csproj'
        result = runtime.run(project, timeout=120)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('PASS disabled visual lifecycle 16 checks', output)


if __name__ == '__main__':
    unittest.main()
