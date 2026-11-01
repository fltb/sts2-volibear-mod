"""Named state sequences over compiled production kernels, not a battle simulator."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tests/gameplay_state_sequences/GameplayStateSequences.csproj'
DLL = ROOT / 'artifacts/gameplay-state-sequences/bin/net9.0/GameplayStateSequences.dll'
CASES = {
    'card-domain-replay-close', 'domain-two-clocks',
    'lightning-pending-epoch-close', 'beast-reference-clone-lifetime',
    'steam-death-evidence', 'steam-commit-and-identity',
    'steam-terminal-guards', 'steam-veto-and-retirement',
}


class GameplayStateSequences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        value = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not value or not Path(value).is_file():
            raise unittest.SkipTest('SDK unavailable; production state sequences NOT_RUN')
        cls.dotnet = Path(value)
        # Missing source/project, compile failure and timeout fail rather than skip.
        result = cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        listed = cls.invoke(str(DLL), '--list')
        if listed.returncode or set(listed.stdout.splitlines()) != CASES:
            raise AssertionError('Required state cases missing/changed:\n' + listed.stdout + listed.stderr)

    @classmethod
    def invoke(cls, *arguments):
        return subprocess.run([str(cls.dotnet), *arguments], cwd=ROOT,
                              capture_output=True, text=True, timeout=180,
                              env=dict(os.environ, DOTNET_NOLOGO='1'))

    def run_case(self, case):
        result = self.invoke(str(DLL), case)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        matches = re.findall(r'^STATE_SEQUENCE_PASS name=(\S+) assertions=(\d+) native-gameplay=NOT_RUN$',
                             result.stdout, re.MULTILINE)
        self.assertEqual(len(matches), 1, output)
        self.assertEqual(matches[0][0], case, output)
        self.assertGreaterEqual(int(matches[0][1]), 6, output)

    def test_card_domain_replay_close(self):
        self.run_case('card-domain-replay-close')

    def test_domain_two_clocks(self):
        self.run_case('domain-two-clocks')

    def test_lightning_pending_epoch_close(self):
        self.run_case('lightning-pending-epoch-close')

    def test_beast_reference_clone_lifetime(self):
        self.run_case('beast-reference-clone-lifetime')

    def test_steam_death_evidence(self):
        self.run_case('steam-death-evidence')

    def test_steam_commit_and_identity(self):
        self.run_case('steam-commit-and-identity')

    def test_steam_terminal_guards(self):
        self.run_case('steam-terminal-guards')

    def test_steam_veto_and_retirement(self):
        self.run_case('steam-veto-and-retirement')

    def test_behavioral_mutations_are_rejected(self):
        # G7: intentionally mutate isolated production copies, never live sources.
        # Compile errors do NOT count as detecting a behavioral mutation.
        mutations = [
            ('CardResolutionState.cs', 'if (Closed || Attached || !domainActive)',
             'if (Closed || !domainActive)', 'card-domain-replay-close',
             'Reentry while first batch pending cannot attach again.'),
            ('CardResolutionState.cs', 'if (round <= _lastDrawRound)',
             'if (round < _lastDrawRound)', 'domain-two-clocks',
             'Same-round extra turn must not consume Domain duration.'),
            ('LightningCounter.cs',
             'ticket.PlayerTurn != _turn || !_pending.Remove(ticket.Id)) return false;',
             'ticket.PlayerTurn != _turn) return false;', 'lightning-pending-epoch-close',
             'Abort only consumes its own pending ticket.'),
            ('BeastFormsCost.cs', 'new HashSet<T>(existing, ReferenceEqualityComparer.Instance)',
             'new HashSet<T>(existing)', 'beast-reference-clone-lifetime',
             'Only original reference is inherited.'),
            ('SteamEruptionDecision.cs', 'proposed > 0 && !CanApplyBenefit ? 0 : proposed;',
             'proposed > 0 ? 0 : proposed;', 'steam-death-evidence',
             'Confirmed native benefit remains allowed without Domain; do not permanently suppress matched damage.'),
        ]
        production = ROOT / 'src/Volibear/Core'
        source_names = ('CardResolutionState.cs', 'LightningCounter.cs',
                        'BeastFormsCost.cs', 'SteamEruptionDecision.cs')
        temporary_root = ROOT / 'artifacts/gameplay-state-mutations'
        temporary_root.mkdir(parents=True, exist_ok=True)
        for filename, before, after, case, assertion in mutations:
            with self.subTest(case=case):
                source = (production / filename).read_text(encoding='utf-8')
                self.assertEqual(source.count(before), 1, 'Mutation anchor drift: ' + case)
                with tempfile.TemporaryDirectory(prefix='isolated-', dir=temporary_root) as directory:
                    work = Path(directory).resolve()
                    # Validate the exact cleanup scope before TemporaryDirectory removes it.
                    self.assertEqual(work.parent, temporary_root.resolve())
                    mutated = work / filename
                    mutated.write_text(source.replace(before, after, 1), encoding='utf-8')
                    project = ET.Element('Project', Sdk='Microsoft.NET.Sdk')
                    properties = ET.SubElement(project, 'PropertyGroup')
                    for name, value in {
                        'OutputType': 'Exe', 'TargetFramework': 'net9.0',
                        'ImplicitUsings': 'enable', 'Nullable': 'enable',
                        'EnableDefaultCompileItems': 'false', 'NuGetAudit': 'false',
                        'RestoreIgnoreFailedSources': 'true',
                    }.items():
                        ET.SubElement(properties, name).text = value
                    items = ET.SubElement(project, 'ItemGroup')
                    for name in source_names:
                        path = mutated if name == filename else production / name
                        ET.SubElement(items, 'Compile', Include=str(path))
                    ET.SubElement(items, 'Compile', Include=str(PROJECT.parent / 'Program.cs'))
                    mutant_project = work / 'Mutant.csproj'
                    ET.ElementTree(project).write(mutant_project, encoding='utf-8', xml_declaration=True)
                    built = self.invoke('build', str(mutant_project), '-c', 'Release', '--nologo')
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    result = self.invoke(str(work / 'bin/Release/net9.0/Mutant.dll'), case)
                    output = result.stdout + result.stderr
                    self.assertNotEqual(result.returncode, 0, 'Behavioral mutant survived: ' + case)
                    self.assertIn(assertion, output)
                    self.assertNotIn('STATE_SEQUENCE_PASS', output)


if __name__ == '__main__':
    unittest.main()
