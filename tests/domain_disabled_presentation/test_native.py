"""Native-reference presentation regression registered by tools/regression.py."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DomainDisabledPresentationTests(unittest.TestCase):
    def _references(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native hover configuration unavailable')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        required = [Path(config['dotnet']), ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll',
                    *(data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        if not all(path.is_file() for path in required):
            self.skipTest('Pinned native hover references unavailable')
        return config, data

    def test_real_native_hover_entries_and_projection(self):
        self._references()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('run.py'))], cwd=ROOT,
                                capture_output=True, text=True, timeout=130)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'DOMAIN_DISABLED_PRESENTATION_PASS checks=\d+ native-entry-patches=5 gameplay-predicates=TEST-DOUBLES Godot-render=NOT_RUN')

    def test_linked_visual_unbound_late_bind_rebind_exit_and_reentry(self):
        config, data = self._references()
        dotnet = Path(config['dotnet'])
        env = dict(os.environ, DOTNET_ROOT=str(dotnet.parent), DOTNET_NOLOGO='1', DOTNET_CLI_TELEMETRY_OPTOUT='1')
        env['PATH'] = str(dotnet.parent) + os.pathsep + env.get('PATH', '')
        project = ROOT / 'tests/disabled_visual_lifecycle/DisabledVisualLifecycle.csproj'
        result = subprocess.run([str(dotnet), 'run', '--project', str(project), '-c', 'Release',
                                 '-p:Sts2DataDir=' + str(data)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('PASS disabled visual lifecycle 16 checks', output)


if __name__ == '__main__':
    unittest.main()
