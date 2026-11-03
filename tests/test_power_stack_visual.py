"""UI grouping regressions; no game, no production build, no input simulation."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PowerStackVisualTests(unittest.TestCase):
    def run_fixture(self, project):
        path = ROOT / '.local/config.json'
        if not path.is_file():
            self.skipTest('Pinned UI references unavailable')
        config = json.loads(path.read_text())
        dotnet = Path(config['dotnet'])
        data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        if not all(p.is_file() for p in (dotnet, data/'sts2.dll', data/'GodotSharp.dll', data/'0Harmony.dll')):
            self.skipTest('Pinned UI references unavailable')
        env = dict(os.environ, DOTNET_ROOT=str(dotnet.parent), DOTNET_NOLOGO='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
        env['PATH'] = str(dotnet.parent) + os.pathsep + env.get('PATH', '')
        # SDK artifacts layout separates both bin AND obj by project name. These
        # projects share a directory; an OutputPath-only override leaves stale run metadata.
        artifacts = ROOT / 'artifacts/power-stack-visual-tests'
        result = subprocess.run([str(dotnet), 'run', '--project', str(ROOT/'tests/power_stack_visual'/project),
                                 '--artifacts-path', str(artifacts),
                                 '-c', 'Release', '-p:Sts2DataDir=' + str(data)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
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
