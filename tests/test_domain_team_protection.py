"""Run unchanged production status/domain callbacks against command-boundary doubles.

This checks shared encounter policy, provenance and cancellation decisions, not
Harmony installation, the game engine, network transport or real multiplayer.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'src/Volibear/Core'


def declaration(text, signature):
    start = text.index(signature)
    cursor, depth = start, 0
    opened = False
    first_brace = text.find('{', start)
    first_semicolon = text.find(';', start)
    expression = '=>' in text[start:min(first_brace, first_semicolon)]
    while cursor < len(text):
        char = text[cursor]
        if char == '{':
            depth += 1
            opened = True
        elif char == '}':
            depth -= 1
            if opened and not depth and not expression:
                # Expression-bodied switches and records end with a semicolon.
                end = cursor + 1
                if end < len(text) and text[end] == ';':
                    end += 1
                return text[start:end]
        elif char == ';' and not depth:
            return text[start:cursor + 1]
        cursor += 1
    raise AssertionError('Unterminated production declaration: ' + signature)


class DomainTeamProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = os.environ.get('VOLIBEAR_DOTNET') or shutil.which('dotnet')
        if not cls.dotnet and (ROOT / '.local/dotnet/dotnet').is_file():
            cls.dotnet = str(ROOT / '.local/dotnet/dotnet')
        if not cls.dotnet:
            raise unittest.SkipTest('.NET SDK absent; team domain callbacks NOT_RUN')
        base = ROOT / 'artifacts/domain-team-protection'
        base.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='isolated-', dir=base)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        cls.sources = {name: (CORE / name).read_text(encoding='utf-8') for name in (
            'DomainEnemyEffects.cs', 'DomainEnemyStatusContributions.cs',
            'DomainEnemyStatusContributions.PowerEffects.cs', 'DomainEnemyStatusContributions.Wither.cs',
            'DomainPlayerStatContributions.cs')}
        cls.dll = cls.build('production', cls.sources)

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([cls.dotnet, *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=120, env=dict(os.environ, DOTNET_NOLOGO='1',
                              DOTNET_CLI_HOME=str(ROOT / '.local/dotnet-home'),
                              NUGET_PACKAGES=str(ROOT / '.local/nuget/packages'),
                              DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_TELEMETRY_OPTOUT='1'))

    @classmethod
    def build(cls, name, sources):
        directory = cls.work / name
        directory.mkdir()
        signatures = {
            'DomainEnemyEffects.cs': (
                'public static bool ActiveFor(ICombatState?', 'public static bool ActiveFor(Creature?',
                'internal static bool ProtectsPlayer(', 'private static bool ProtectsTarget(',
                'private sealed record ShellWindow(', 'private static void NeutralMultiplier(',
                'private static void NeutralHpLoss(', 'private static void NeutralShell('),
            'DomainPlayerStatContributions.cs': ('private static bool Contributes(',),
            'DomainEnemyStatusContributions.cs': (
                'private sealed record Origin(', 'private static Creature SourceCreature(',
                'private static bool EnemySource(', 'private static Task AddEnemyStatusOne<T>(',
                'private static async Task AddEnemyStatuses<T>(', 'private static Task<CardPileAddResult> AddEnemyGenerated(',
                'private static bool Suppress(', 'private static Task<IEnumerable<DamageResult>> StatusDamageVar(',
                'private static Task<IEnumerable<DamageResult>> StatusDamageAmount(', 'public static void Reset()'),
            'DomainEnemyStatusContributions.PowerEffects.cs': (
                'private sealed record SparkTicket(', 'private sealed class TaintedReceipt(',
                'private static bool SuppressPowerContribution(', 'private static Task<T?> EnemyAfflict<T>(',
                'private static Task<IEnumerable<DamageResult>> GalvanicDamage(', 'private static Task PaperCutMaxHp(',
                'private static async Task<TaintedPower?> SparkApply(', 'private static bool EnemyTainted(',
                'internal static bool ShouldCancelTainted(', 'internal static void AppliedTainted(',
                'internal static void TaintedAmountChanged(', 'private static void RememberTaintedSource(',
                'private static void ReconcileTainted(', 'private static int EffectiveTaintedAmount(',
                'private static void ResetStatusPowerEffects()'),
            'DomainEnemyStatusContributions.Wither.cs': (
                'private sealed record WitherContribution(', 'private static void SetWitherUpgradeCount(',
                'private static void EnemyWitherUpgrade(', 'private static decimal WitherDamageWithoutEnemyContribution(',
                'private static void CopyStatusReceipts('),
        }
        extracted = {key: '\n'.join(declaration(sources[key], signature) for signature in values)
                     for key, values in signatures.items()}
        template = (ROOT / 'tests/domain_team_protection/Program.cs').read_text(encoding='utf-8')
        for key, body in extracted.items():
            template = template.replace('// PRODUCTION_' + key, body)
        presentation = (ROOT / 'src/Volibear/Presentation/PowerPresentationDomain.cs').read_text(encoding='utf-8')
        template = template.replace('// PRODUCTION_PRESENTATION', declaration(presentation, 'internal static void Suppressed('))
        (directory / 'Program.cs').write_text(template, encoding='utf-8')
        project = directory / 'DomainTeamProtection.csproj'
        project.write_text('''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>
<OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings>
<Nullable>enable</Nullable><NuGetAudit>false</NuGetAudit><RestoreIgnoreFailedSources>true</RestoreIgnoreFailedSources>
</PropertyGroup></Project>''', encoding='utf-8')
        result = cls.invoke('build', str(project), '-c', 'Release', '--nologo')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return directory / 'bin/Release/net9.0/DomainTeamProtection.dll'

    def run_case(self, name):
        result = self.invoke(str(self.dll), name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DOMAIN_TEAM_PROTECTION_PASS ' + name, result.stdout)
        self.assertIn('native-network=NOT_RUN', result.stdout)

    def test_live_team_domain_has_one_encounter_scope(self):
        self.run_case('scope')

    def test_enemy_status_generation_and_existing_damage_protect_teammates(self):
        self.run_case('statuses')

    def test_enemy_power_contributions_keep_player_and_foreign_sources(self):
        self.run_case('powers')

    def test_wither_cancellation_is_consumed_and_player_damage_is_preserved(self):
        self.run_case('wither')

    def test_other_mods_enemy_penalties_are_not_neutralized(self):
        self.run_case('scalars')

    def test_stat_compensation_uses_exactly_one_attached_live_holder(self):
        self.run_case('holder')

    def test_old_recipient_only_policy_is_rejected(self):
        broken = dict(self.sources)
        for name in broken:
            if name.startswith('DomainEnemyStatusContributions'):
                broken[name] = broken[name].replace('DomainEnemyEffects.ProtectsPlayer(', 'DomainPower.IsActive(')
        dll = self.build('recipient-only-regression', broken)
        for case, expected in (
            ('statuses', 'Teammate domain must stop enemy status generation'),
            ('powers', 'Teammate domain must stop enemy Galvanic damage'),
            ('wither', 'Teammate domain must stop hostile Wither upgrades')):
            result = self.invoke(str(dll), case)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout + result.stderr)

    def test_old_scalar_and_stale_holder_regressions_are_rejected(self):
        broken = dict(self.sources)
        source = broken['DomainEnemyEffects.cs']
        source = source.replace('if (__result < 1m && ProtectsTarget(__instance, __0))',
                                'if (ProtectsTarget(__instance, __0))')
        source = source.replace('if (__result < __1 && ProtectsTarget(__instance, __0))',
                                'if (ProtectsTarget(__instance, __0))')
        source = source.replace('if (__result < __1)\n', 'if (true)\n')
        broken['DomainEnemyEffects.cs'] = source
        broken['DomainPlayerStatContributions.cs'] = broken['DomainPlayerStatContributions.cs'].replace(
            ' || !DomainEnemyEffects.ProtectsPlayer(domain.Owner)', '').replace(
            ' && DomainEnemyEffects.ProtectsPlayer(player.Creature)', '')
        dll = self.build('scalar-holder-regressions', broken)
        for case, expected in (
            ('scalars', 'Independent damage increase must survive domain'),
            ('holder', 'Detached first holder must not block live holder compensation')):
            result = self.invoke(str(dll), case)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
