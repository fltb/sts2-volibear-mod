"""Production summon/revival decisions, not native Add/HP/fullCombatReset acceptance."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tests/domain_lifecycle_states/DomainLifecycleStates.csproj'
DLL = ROOT / 'artifacts/domain-lifecycle-states/bin/net9.0/DomainLifecycleStates.dll'
CASES = (
    'summon-partial-boundary-close', 'summon-prevented-close-independent',
    'summon-known-stale-versus-unknown', 'revival-pending-confirmed-cancelled',
    'revival-commit-versus-domain', 'revival-reference-authority', 'revival-unstarted-callback',
)


def require_success(result):
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise AssertionError('Missing or undecodable subprocess output')
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


class DomainLifecycleStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = ROOT / '.local/config.json'
        configured = json.loads(config.read_text(encoding='utf-8')).get('dotnet') if config.is_file() else None
        value = configured or os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not value or not Path(value).is_file():
            raise unittest.SkipTest('SDK unavailable; domain lifecycle states NOT_RUN')
        cls.dotnet = value
        require_success(cls.invoke('build', str(PROJECT), '-c', 'Release', '--nologo'))
        result = cls.invoke(str(DLL), '--list')
        require_success(result)
        if result.stdout.splitlines() != list(CASES):
            raise AssertionError('Required lifecycle sequences missing/changed:\n' + result.stdout)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([cls.dotnet, *args], cwd=ROOT, capture_output=True,
                              text=True, encoding='utf-8', timeout=180,
                              env=dict(os.environ, DOTNET_NOLOGO='1'))

    def run_case(self, case):
        result = self.invoke(str(DLL), case)
        require_success(result)
        matches = re.findall(r'^DOMAIN_LIFECYCLE_PASS name=(\S+) assertions=(\d+) native-gameplay=NOT_RUN$',
                             result.stdout, re.MULTILINE)
        self.assertEqual(len(matches), 1, result.stdout)
        self.assertEqual(matches[0][0], case)
        self.assertGreaterEqual(int(matches[0][1]), 7)

    def test_summon_partial_boundary_close(self):
        self.run_case('summon-partial-boundary-close')

    def test_summon_prevented_close_independent(self):
        self.run_case('summon-prevented-close-independent')

    def test_summon_known_stale_versus_unknown(self):
        self.run_case('summon-known-stale-versus-unknown')

    def test_revival_pending_confirmed_cancelled(self):
        self.run_case('revival-pending-confirmed-cancelled')

    def test_revival_commit_versus_domain(self):
        self.run_case('revival-commit-versus-domain')

    def test_revival_reference_authority(self):
        self.run_case('revival-reference-authority')

    def test_revival_unstarted_callback(self):
        self.run_case('revival-unstarted-callback')


class DomainDecisionSourceContracts(unittest.TestCase):
    def test_actual_adapter_calls_extracted_decisions(self):
        summon = (ROOT / 'src/Volibear/Core/DomainSummonEffects.cs').read_text(encoding='utf-8')
        revival = (ROOT / 'src/Volibear/Core/DomainRevivalEffects.cs').read_text(encoding='utf-8')
        self.assertIn('public static partial class DomainSummonEffects', summon)
        self.assertNotIn('class DeathDecision', summon)
        self.assertIn('internal readonly DeathDecision Decision = new(entryDomain);', summon)
        self.assertIn('Tasks.Close(frame.Binding, static batch => { batch.Closed = true; batch.Decision.Close(); })', summon)
        self.assertIn('batch!.Decision.AtBoundary(false,', summon)
        self.assertIn('ClassifyGate(batch is not null, frame.Generation, batch?.Generation ?? 0, _generation)', summon)
        self.assertIn('if (ownership == GateOwnership.Unknown) return false;', summon)
        self.assertIn('if (ownership == GateOwnership.StaleKnown) return true;', summon)
        self.assertNotIn('class RevivalDecision', revival)
        self.assertIn('internal readonly RevivalDecision Decision = new();', revival)
        for method in ('CancelIfRequired(', 'OwnsCancelledPreservation(', 'SkipUnstartedCallback(', '.Commit()'):
            self.assertIn(method, revival)

    def test_all_explicit_native_project_links_include_extracted_sources(self):
        # Static wiring only: these native-reference projects are deliberately NOT built here.
        projects = {
            'domain_revival/DomainRevival.Tests.csproj': ('RevivalDecision.cs',),
        }
        for project, names in projects.items():
            with self.subTest(project=project):
                root = ET.parse(ROOT / 'tests' / project).getroot()
                includes = [part for node in root.findall('.//Compile') for part in node.attrib['Include'].split(';')]
                for name in names:
                    self.assertEqual(includes.count('../../src/Volibear/Core/' + name), 1)
        # Audio now shares internal commit adapters and partial implementations
        # with the production core. A partial source list plus a host DLL creates
        # duplicate identities or omits internal dependencies; compile one source tree.
        for project in ('audio_receipts/AudioReceipts.csproj', 'audio_receipt_probe/AudioReceiptProbe.csproj'):
            with self.subTest(project=project):
                root = ET.parse(ROOT / 'tests' / project).getroot()
                sources = [node for node in root.findall('.//Compile')
                           if node.attrib['Include'] == '$(RepositoryRoot)/src/Volibear/**/*.cs']
                self.assertEqual(len(sources), 1)
                self.assertEqual(set(sources[0].attrib.get('Exclude', '').split(';')), {
                    '$(RepositoryRoot)/src/Volibear/bin/**', '$(RepositoryRoot)/src/Volibear/obj/**'})
                self.assertNotIn('Volibear', [node.attrib['Include'] for node in root.findall('.//Reference')])
                self.assertFalse(root.findall('.//HostAssembly'))

    def test_stage_override_remains_self_contained_unless_kernel_explicit(self):
        root = ET.parse(ROOT / 'tests/domain_summon_effects/DomainSummonEffects.Tests.csproj').getroot()
        props = list(root.find('PropertyGroup'))
        tags = [node.tag for node in props]
        for source, decision, file in (('SummonSource', 'SummonDecisionSource', 'DomainSummonDecision.cs'),
                                       ('RevivalSource', 'RevivalDecisionSource', 'RevivalDecision.cs'),
                                       ('SummonSource', 'SummonRegistrationSource', 'SummonRegistration.cs')):
            self.assertLess(tags.index(decision), tags.index(source))
            prop = props[tags.index(decision)]
            self.assertEqual(prop.attrib['Condition'], f"'$({source})' == '' and '$({decision})' == ''")
            self.assertEqual(prop.text, '../../src/Volibear/Core/' + file)
            nodes = [node for node in root.findall('.//Compile') if node.attrib['Include'] == f'$({decision})']
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0].attrib['Condition'], f"'$({decision})' != ''")

    def test_compile_failure_and_missing_output_fail_closed(self):
        for result in (subprocess.CompletedProcess([], 1, 'build failed', ''),
                       subprocess.CompletedProcess([], 0, None, '')):
            with self.subTest(result=result), self.assertRaises(AssertionError):
                require_success(result)


if __name__ == '__main__':
    unittest.main()
