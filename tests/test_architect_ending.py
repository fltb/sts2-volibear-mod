"""Locked native ending IL plus scoped command-boundary semantics; no game launch."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ArchitectEndingTests(unittest.TestCase):
    def test_native_victory_chain_and_living_domain_exit(self):
        path = ROOT / '.local/config.json'
        if not path.is_file():
            self.skipTest('Pinned native configuration unavailable')
        config = json.loads(path.read_text(encoding='utf-8'))
        data = Path(config['game_dir']) / ('data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64')
        result = subprocess.run([config['dotnet'], 'run', '--project', str(ROOT / 'tests/architect/Architect.Tests.csproj'),
                                 '-c', 'Release', '-p:Sts2DataDir=' + str(data), '--nologo'],
                                cwd=ROOT, capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        receipt = re.search(r'ARCHITECT_ENDING_PASS checks=(\d+) native-sites=2 gameplay=NOT_RUN', output)
        self.assertIsNotNone(receipt, output)
        self.assertGreaterEqual(int(receipt.group(1)), 20)
