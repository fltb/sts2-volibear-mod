"""Production-domain contribution semantics and locked native binding checks; no game launch."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DomainSelfDebuffTests(unittest.TestCase):
    def test_native_bindings_and_temporary_suppression(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native SDK configuration unavailable')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        if not all(p.is_file() for p in [Path(config['dotnet']), baselib, data / 'sts2.dll', data / 'GodotSharp.dll', data / '0Harmony.dll']):
            self.skipTest('Pinned native references unavailable')
        result = subprocess.run([config['dotnet'], 'run', '--project', str(ROOT / 'tests/domain_self_debuff/DomainSelfDebuff.Tests.csproj'),
                                 '-c', 'Release', '-p:Sts2DataDir=' + str(data), '-p:BaseLibPath=' + str(baselib), '--nologo'],
                                cwd=ROOT, capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('SELF_DEBUFF_SEMANTICS_PASS checks=37', output)
        self.assertIn('SELF_DEBUFF_NATIVE_BINDINGS_PASS count=28', output)
        self.assertIn('SANDPIT_SEMANTICS_PASS checks=5', output)
        self.assertIn('WEAK_NATIVE_DURATION_PASS checks=5 actual-side-and-skip-callbacks=true decrement-command-seam=true gameplay=NOT_RUN', output)
        self.assertIn('BASELIB_WEAK_DURATION_PASS checks=13 actual-postfix-and-await=true apply-decrement-scene-seams=true gameplay=NOT_RUN', output)
