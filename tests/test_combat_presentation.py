"""SDK behavior checks for the production combat-presentation adapter.

The complete catalog and combat bridge are compiled directly. Native/Godot/Harmony
objects are explicit call-recording doubles; this does not verify game ABI,
Harmony detours, animation pixels, network transport, or native gameplay.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime

FIXTURE = ROOT / 'tests/combat_presentation'
PRESENTATION = ROOT / 'src/Volibear/Presentation'
CORE = ROOT / 'src/Volibear/Core'


def method(source, signature):
    """Project an exact production method body, without changing its statements."""
    start = source.index(signature)
    opening = source.index('{', start)
    depth, cursor = 1, opening + 1
    while depth:
        depth += (source[cursor] == '{') - (source[cursor] == '}')
        cursor += 1
    return source[start:cursor]


CASES = (
    'catalog', 'segments', 'bite-replay', 'target-snapshots', 'lightning-origins', 'lightning-delivery', 'direct-lightning-motion',
    'native-arbitration', 'trigger-indices', 'nested-ownership', 'stale-source', 'lifecycle',
    'ending-contact', 'pipeline-order', 'pipeline-fault-cancel', 'pipeline-scope',
)


class CombatPresentationBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = fixture_runtime(cls, 'sdk', root=ROOT)
        artifacts = ROOT / 'artifacts/combat-presentation'
        artifacts.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='isolated-', dir=artifacts)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        hooks = (CORE / 'CardResolutionHooks.cs').read_text(encoding='utf-8')
        pipeline = '\n'.join(method(hooks, signature) for signature in (
            'internal sealed class OrdinaryAttackObservation(',
            'private readonly struct ExistingDamageAwaitable(',
            'internal static async Task<IEnumerable<DamageResult>> CompleteOrdinaryAttack(',
            'private static void PresentOrdinarySegment(',
            'internal static async Task<IEnumerable<DamageResult>> OrdinaryAttackPipelineV1(',
        ))
        event = next(line.strip() for line in hooks.splitlines()
                     if 'public static event' in line and 'OrdinarySegmentCommitted' in line)
        pipeline += '\n' + event
        program = (FIXTURE / 'Program.cs').read_text(encoding='utf-8')
        motion = (PRESENTATION / 'VolibearPresentationBridge.Motion.cs').read_text(encoding='utf-8')
        program = program.replace('// PRODUCTION_PIPELINE', pipeline)
        program = program.replace('// PRODUCTION_CLEAR_MOTIONS', method(motion, 'private void ClearMotions()'))
        bridge = (PRESENTATION / 'VolibearPresentationBridge.cs').read_text(encoding='utf-8')
        live_start = bridge.index('private bool Live =>')
        program = program.replace('// PRODUCTION_LIVE', bridge[live_start:bridge.index(';', live_start) + 1])
        program = program.replace('// PRODUCTION_LIGHTNING\n', method(bridge, 'internal void Lightning(LightningBatch batch)') + '\n')
        program = program.replace('// PRODUCTION_SUSPEND', method(bridge, 'internal void SuspendEnding()'))
        lightning = (CORE / 'LightningBatches.cs').read_text(encoding='utf-8')
        program = program.replace('// PRODUCTION_LIGHTNING_PRESENT', method(lightning, 'internal static void Present(LightningBatch batch)'))
        (cls.work / 'Program.cs').write_text(program, encoding='utf-8')
        (cls.work / 'LightningTypes.cs').write_text(
            lightning[:lightning.index('public static class LightningBatches')], encoding='utf-8')
        (cls.work / 'CombatPresentation.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable>
    <NuGetAudit>false</NuGetAudit><RestoreIgnoreFailedSources>true</RestoreIgnoreFailedSources>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="''' + str(PRESENTATION / 'CombatPresentationCatalog.cs') + '''" Link="Production/CombatPresentationCatalog.cs" />
    <Compile Include="''' + str(PRESENTATION / 'VolibearPresentationBridge.Combat.cs') + '''" Link="Production/VolibearPresentationBridge.Combat.cs" />
  </ItemGroup>
</Project>''', encoding='utf-8')
        result = cls.invoke('build', str(cls.work / 'CombatPresentation.csproj'), '-c', 'Release', '--nologo')
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.dll = cls.work / 'bin/Release/net9.0/CombatPresentation.dll'

    @classmethod
    def invoke(cls, *args):
        return subprocess.run([str(cls.runtime.dotnet), *args], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8',
                              timeout=120, env=cls.runtime.environment())

    def run_case(self, case):
        result = self.invoke(str(self.dll), case, str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, rf'COMBAT_PRESENTATION_PASS {case} assertions=\d+ native-gameplay=NOT_RUN')


for _case in CASES:
    setattr(CombatPresentationBehaviorTests, 'test_' + _case.replace('-', '_'),
            lambda self, case=_case: self.run_case(case))


if __name__ == '__main__':
    unittest.main()
