"""Focused shared-MoveNext evidence for the debuff precommit gate.

Compiles the current production sources directly and emits the real
PowerAudioReceipts and DomainPlayerDebuffContributions transpilers over the
locked native IL. The fixture also proves four non-exact mutations still fail.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(__file__).resolve().parent / 'domain_debuff_commit_il/DebuffCommitIl.Tests.csproj'


class DomainDebuffCommitIl(unittest.TestCase):
    def test_exact_audio_observer_and_result_local_binding(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native configuration unavailable; debuff commit IL NOT RUN')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        dotnet = Path(config['dotnet'])
        data_name = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
        data = Path(config['game_dir']) / data_name
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        required = [dotnet, baselib, *(data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        if not all(path.is_file() for path in required):
            self.skipTest('Actual SDK/native/BaseLib references unavailable; debuff commit IL NOT RUN; no substitutes')
        result = subprocess.run([
            str(dotnet), 'run', '--project', str(PROJECT), '-c', 'Release',
            '-p:RepositoryRoot=' + str(ROOT), '-p:Sts2DataDir=' + str(data),
            '-p:BaseLibPath=' + str(baselib), '--nologo',
        ], cwd=ROOT, capture_output=True, text=True, timeout=180,
            env=dict(os.environ, DOTNET_NOLOGO='1'))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn(
            'DEBUFF_COMMIT_IL_PASS checks=17 shared-body=PowerCmd.ModifyAmount '
            'audio-close=exact result-local=int1 guard=preserved native-gameplay=NOT_RUN',
            result.stdout, output)
        for mutation in ('foreign-close', 'split-observer', 'non-local-frame', 'extra-after-close'):
            self.assertIn('DEBUFF_COMMIT_IL_REJECT ' + mutation, result.stdout, output)
        self.assertIn('SIGNAL ORIGINAL-MODIFY index=469', result.stdout, output)
