"""Focused shared-MoveNext evidence for the debuff precommit gate.

Compiles the current production sources directly and emits the real
PowerAudioReceipts and DomainPlayerDebuffContributions transpilers over the
locked native IL. The fixture also proves four non-exact mutations still fail.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
PROJECT = Path(__file__).resolve().parent / 'domain_debuff_commit_il/DebuffCommitIl.Tests.csproj'


class DomainDebuffCommitIl(unittest.TestCase):
    def test_exact_audio_observer_and_result_local_binding(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        result = runtime.run(PROJECT, args=('-p:RepositoryRoot=' + str(ROOT), '--nologo'), timeout=180)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn(
            'DEBUFF_COMMIT_IL_PASS checks=17 shared-body=PowerCmd.ModifyAmount '
            'audio-close=exact result-local=int1 guard=preserved native-gameplay=NOT_RUN',
            result.stdout, output)
        for mutation in ('foreign-close', 'split-observer', 'non-local-frame', 'extra-after-close'):
            self.assertIn('DEBUFF_COMMIT_IL_REJECT ' + mutation, result.stdout, output)
        self.assertIn('SIGNAL ORIGINAL-MODIFY index=469', result.stdout, output)
