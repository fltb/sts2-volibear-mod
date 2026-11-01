"""V1 cooperation managed fixtures and native-reference IL emission; no Godot."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(__file__).resolve().parent / 'domain_steam_v1/DomainSteamV1.Tests.csproj'


class DomainSteamV1Regression(unittest.TestCase):
    def test_audio_observer_prepares_leaf_before_its_native_caller(self):
        source = (ROOT / 'src/Volibear/DomainSteamNativeObservation.cs').read_text(encoding='utf-8')
        setup = source.split('private static void InstallAudioPatches', 1)[1].split('var method = AccessTools.Method', 1)[0]
        self.assertLess(setup.index('typeof(SfxCmd)'), setup.index('typeof(NCreature)'))
        entry = (ROOT / 'src/Volibear/ModEntry.cs').read_text(encoding='utf-8')
        self.assertLess(entry.index('DomainSteamNativeObservation.PrepareForTestScenario();'),
                        entry.index('Core.DomainSteamEruptionEffects.Install();'))

    def test_current_production_sources_cooperate(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native configuration unavailable; V1 emission NOT RUN')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        dotnet = Path(config['dotnet'])
        data_name = 'data_sts2_windows_x86_64' if os.name == 'nt' else 'data_sts2_linuxbsd_x86_64'
        data = Path(config['game_dir']) / data_name
        baselib = ROOT / '.local/dependencies/BaseLib-3.4.7/BaseLib.dll'
        required = [dotnet, baselib, *(data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll'))]
        if not all(path.is_file() for path in required):
            self.skipTest('Actual SDK/native/BaseLib references unavailable; V1 emission NOT RUN; no substitutes')
        # Missing project, broken source, compilation/fixture failures and timeout
        # must fail, never become skips. No prebuilt host DLL is necessary.
        project_text = PROJECT.read_text(encoding='utf-8')
        self.assertIn('$(RepositoryRoot)/src/Volibear/**/*.cs', project_text)
        self.assertNotIn('steam-stage', project_text)
        self.assertNotIn('Volibear.dll', project_text)
        result = subprocess.run([
            str(dotnet), 'run', '--project', str(PROJECT), '-c', 'Release',
            '-p:RepositoryRoot=' + str(ROOT), '-p:Sts2DataDir=' + str(data),
            '-p:BaseLibPath=' + str(baselib), '--nologo',
        ], cwd=ROOT, capture_output=True, text=True, timeout=180,
            env=dict(os.environ, DOTNET_NOLOGO='1'))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('BLOCK_CARD_NATIVE_MODIFIERS_PASS checks=25 actual-metadata-upgrade-native-modifiers=true native-gameplay=NOT_RUN', result.stdout)
        self.assertIn('SUMMON_GATE_ADAPTER_PASS cases=7 checks=34 typed-frames-only=true native-gameplay=NOT_RUN', result.stdout)
        self.assertIn('LIGHTNING_RESPONSE_ADAPTER_PASS checks=14 actual-subscription-reset=true native-world=NOT_RUN', result.stdout)
        cooperation = re.search(r'STEAM_ORDINARY_COOPERATION_PASS checks=(\d+) managed-dispatch-domain-combat-stubs=true native-gameplay=NOT_RUN', result.stdout)
        self.assertIsNotNone(cooperation, output)
        self.assertGreaterEqual(int(cooperation.group(1)), 26)
        chain = re.search(r'STEAM_FULL_INSTALL_CHAIN_EMISSION_PASS installers=21 pair-orders=2 checks=(\d+) registration-and-BaseLib-runtime=NOT_RUN gameplay=NOT_RUN', result.stdout)
        self.assertIsNotNone(chain, output)
        self.assertGreaterEqual(int(chain.group(1)), 55)
        self.assertEqual(len(re.findall(r'^STEAM_MAIN_INSTALL_EMIT ', result.stdout, re.MULTILINE)), 21, output)
        self.assertIn('STEAM_DOMAIN_PROBE_EMISSION_PASS shared-pipeline=true gameplay=NOT_RUN', result.stdout)
        audio = re.search(r'STEAM_EARLY_AUDIO_OBSERVER_EMISSION_PASS checks=(\d+) main-installers=21 expected-sequences=UNCHANGED core-calls=STATICALLY-PRESERVED pre-JIT-cause=NOT_PROVEN native-gameplay=NOT_RUN', result.stdout)
        self.assertIsNotNone(audio, output)
        self.assertGreaterEqual(int(audio.group(1)), 50)


if __name__ == '__main__':
    unittest.main()
