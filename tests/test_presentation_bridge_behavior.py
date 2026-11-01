"""Execute the production presentation orchestration in a minimal C# scene boundary.

The native game/Godot scene graph is not simulated or claimed as verified. Exact
production method bodies drive observable calls, so setup/replay regressions can
be exercised without redistributing the game assemblies.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/Presentation/VolibearPresentationBridge.cs'
MOTION = SOURCE.with_name('VolibearPresentationBridge.Motion.cs')


def method(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    cursor = opening + 1
    while depth:
        if source[cursor] == '{':
            depth += 1
        elif source[cursor] == '}':
            depth -= 1
        cursor += 1
    return source[start:cursor]


class PresentationBridgeBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not cls.dotnet and (ROOT / '.local/dotnet/dotnet').is_file():
            cls.dotnet = str(ROOT / '.local/dotnet/dotnet')
        if not cls.dotnet:
            raise unittest.SkipTest('SDK absent; production presentation behavior NOT_RUN')
        root = ROOT / 'artifacts/presentation-behavior'
        root.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='isolated-', dir=root)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.dll = cls.build('production', cls.source)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([cls.dotnet, *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=120,
                              env=dict(os.environ, DOTNET_NOLOGO='1',
                                       DOTNET_CLI_HOME=str(ROOT / '.local/dotnet-home'),
                                       NUGET_PACKAGES=str(ROOT / '.local/nuget/packages'),
                                       DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',
                                       DOTNET_CLI_TELEMETRY_OPTOUT='1'))

    @classmethod
    def build(cls, name, source):
        directory = cls.work / name
        directory.mkdir()
        bodies = '\n'.join(method(source, signature) for signature in (
            'internal void Tick()',
            'private void UpdateLowHealth(bool announce = true)',
            'internal void CardStarted(CardPlay play, string id)',
            'internal void AtCard(string id, string effect, CardModel card)',
            'internal void EngageTelegraph(string id)',
        ))
        metadata = '\n'.join(method(source, signature) for signature in (
            'private static void ReadMetadata()',
            'private static string? ReadContactEffect(JsonElement row)',
            'private static string ContactEffectFor(CardModel? card)',
        ))
        motion = MOTION.read_text(encoding='utf-8')
        engage = '\n'.join([
            re.search(r'private sealed record EngageGroup\([^;]+;', motion).group(),
            method(source, 'private sealed class EngageObservation('),
            method(motion, 'private static void BeforeEngageGroup('),
            method(motion, 'private static Exception? FinishEngageGroupInvocation('),
            method(source, 'private static void BeforeEngage('),
            method(source, 'private static void BeforeIntent('),
            method(source, 'private static Exception? FinishEngageInvocation('),
        ])
        template = (ROOT / 'tests/presentation_bridge_behavior/Program.cs').read_text(encoding='utf-8')
        (directory / 'Program.cs').write_text(template.replace('// PRODUCTION_METHODS', bodies)
                                            .replace('// PRODUCTION_METADATA', metadata)
                                            .replace('// PRODUCTION_ENGAGE', engage), encoding='utf-8')
        project = directory / 'PresentationBehavior.csproj'
        project.write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable>
    <NuGetAudit>false</NuGetAudit><RestoreIgnoreFailedSources>true</RestoreIgnoreFailedSources>
  </PropertyGroup>
</Project>''', encoding='utf-8')
        result = cls.invoke('build', str(project), '-c', 'Release', '--nologo')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return directory / 'bin/Release/net9.0/PresentationBehavior.dll'

    def run_case(self, case):
        result = self.invoke(str(self.dll), case, str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PRESENTATION_BEHAVIOR_PASS ' + case, result.stdout)
        self.assertIn('native-gameplay=NOT_RUN', result.stdout)

    def test_low_health_start_snapshot_and_hysteresis(self):
        self.run_case('low-health')

    def test_replay_has_marker_without_restarting_primary_motion(self):
        self.run_case('replay')

    def test_removed_card_view_uses_its_captured_anchor(self):
        self.run_case('card-anchor')

    def test_physical_contacts_follow_all_approved_card_cues(self):
        self.run_case('contact-bindings')

    def test_accepted_engage_announces_once_per_single_or_grouped_action(self):
        self.run_case('engage-voice')

    def test_all_lightning_overloads_share_the_observed_entry(self):
        install = method(self.source, 'public static void Install()')
        self.assertRegex(install, r'var lightning = Required\(typeof\(LightningCmd\), "DealCore",\s*'
                         r'typeof\(PlayerChoiceContext\), typeof\(Creature\), typeof\(IEnumerable<Creature>\), '
                         r'typeof\(decimal\), typeof\(CardModel\),\s*'
                         r'typeof\(bool\), typeof\(Action<IReadOnlyList<LightningHit>>\)\);')
        self.assertIn('harmony.Patch(lightning, prefix: Handler(nameof(BeforeLightning)));', install)
        lightning = (ROOT / 'src/Volibear/Content/LightningCmd.cs').read_text(encoding='utf-8')
        self.assertEqual(lightning.count('private static async Task<int> DealCore('), 1)
        self.assertNotIn('CreatureCmd.Damage', lightning[:lightning.index('private static async Task<int> DealCore(')])

    def test_previous_setup_and_replay_bugs_are_rejected(self):
        tick = method(self.source, 'internal void Tick()')
        card_started = method(self.source, 'internal void CardStarted(CardPlay play, string id)')
        at_card = method(self.source, 'internal void AtCard(string id, string effect, CardModel card)')
        mutants = [
            ('low-health', self.source.replace(tick, tick.replace('UpdateLowHealth(announce: false);', '', 1)),
             'Starting low HP must select weak pose once playable'),
            ('replay', self.source.replace(card_started, card_started.replace(
                'return; // Repeated effects retain the original paid play\'s primary motion.', '', 1)),
             'Replay must not restart primary motion'),
            ('card-anchor', self.source.replace(at_card, at_card.replace(
                'var node = CardAnchor(card);', 'var node = NCard.FindOnTable(card);', 1)),
             'Exhaust after view removal must retain the measured card effect'),
        ]
        for case, changed, expected in mutants:
            with self.subTest(case=case):
                self.assertNotEqual(changed, self.source)
                dll = self.build('old-' + case, changed)
                result = self.invoke(str(dll), case, str(ROOT))
                self.assertNotEqual(result.returncode, 0, 'Old behavior passed: ' + case)
                self.assertIn(expected, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
