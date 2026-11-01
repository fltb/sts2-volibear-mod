"""Published-source receipt routing and actual combined IL emission; not audio playback."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Volibear'


class AudioReceiptTests(unittest.TestCase):
    def test_receipts_follow_real_moves_without_changing_settlement(self):
        domain = (SRC / 'Core/DomainPower.cs').read_text(encoding='utf-8')
        after_applied = domain.split('public override async Task AfterApplied', 1)[1].split('public override async Task AfterPlayerTurnStartEarly', 1)[0]
        revival = 'await DomainRevivalEffects.AfterDomainOpened(Owner);'
        steam = 'await DomainSteamEruptionEffects.AfterDomainOpened(Owner);'
        self.assertEqual(after_applied.count(revival), 1)
        self.assertEqual(after_applied.count(steam), 1)
        self.assertLess(after_applied.index('_drawClock = new CardResolutionDrawClock'), after_applied.index(revival))
        self.assertLess(after_applied.index(revival), after_applied.index(steam))
        body = domain.split('public override async Task AfterCardDrawnEarly', 1)[1].split('internal static async Task', 1)[0]
        self.assertLess(body.index('TryBeginPurification'), body.index('await CardCmd.Exhaust'))
        self.assertLess(body.index('await CardCmd.Exhaust'), body.index('CardPresentationReceipts.Purified'))
        self.assertLess(body.index('CardPresentationReceipts.Purified'), body.index('await CardPileCmd.Draw'))
        for name in ('ControlledEffects', 'BeastEffects'):
            source = (SRC / f'Content/Cards/{name}.cs').read_text(encoding='utf-8')
            self.assertRegex(source, r'await CardPileCmd.Add\(card, PileType.Hand\);\s*CardPresentationReceipts.Retrieved\(card, source,')
        publisher = (SRC / 'Core/CardPresentationReceipts.cs').read_text(encoding='utf-8')
        self.assertIn('CardReceiptPolicy.Notify(Committed, receipt);', publisher)
        self.assertIn('internal static void Purified', publisher)
        code = re.sub(r'//[^\n]*|/\*.*?\*/', '', publisher, flags=re.S)
        self.assertNotIn('await ', code)

    def test_exact_native_scope_and_approved_audio_only(self):
        source = (SRC / 'Presentation/PowerAudioReceipts.cs').read_text(encoding='utf-8')
        self.assertIn('[HarmonyBefore("Volibear.DomainCardContributions")]', source)
        self.assertIn('[HarmonyAfter("Volibear.DomainPassiveEffects")]', source)
        self.assertIn('Closed: false, AtCommit: true', source)
        self.assertIn('ReferenceEquals(ticket.Combat, combat)', source)
        self.assertIn('owner.Powers.Contains(power), delta > 0, power.Amount > 0', source)
        self.assertNotIn('ref Task', source)
        self.assertNotIn('await ', source)
        self.assertNotIn('Task.CompletedTask', source)
        cues = set(re.findall(r'=> "([a-z_]+)"', source))
        self.assertEqual(cues, {'armor_retain', 'armor_iron', 'thunder_armor', 'cost_reduce', 'strength'})
        bridge = (SRC / 'Presentation/VolibearPresentationBridge.cs').read_text(encoding='utf-8')
        self.assertIn('PowerAudioReceipts.Install();', bridge)
        self.assertIn('CardPresentationReceipts.Committed += CardCommitted;', bridge)
        self.assertIn('var receipt = PowerAudioReceipts.Applied(power);', bridge)
        self.assertIn('var receipt = PowerAudioReceipts.Increased(power, amount, silent);', bridge)

    def test_published_sources_combined_native_emission(self):
        config_path = ROOT / '.local/config.json'
        if not config_path.is_file():
            self.skipTest('Pinned native assemblies unavailable; native emission NOT RUN')
        config = json.loads(config_path.read_text(encoding='utf-8'))
        dotnet = Path(config.get('dotnet', ''))
        data = Path(config.get('game_dir', '')) / 'data_sts2_windows_x86_64'
        host = SRC / 'bin/Release/net9.0/Volibear.dll'
        if not dotnet.is_file() or not (data / 'sts2.dll').is_file() or not host.is_file():
            self.skipTest('Actual native assemblies/built host missing; no fake substitution')
        project = ROOT / 'tests/audio_receipts/AudioReceipts.csproj'
        text = project.read_text(encoding='utf-8')
        self.assertNotIn('.local/audio-receipt-stage', text)
        for name in ('AudioCommitGate', 'PowerAudioReceipts', 'CardReceiptPolicy', 'CardPresentationReceipts',
                     'DomainPassiveEffects', 'DomainRevivalEffects', 'DomainSummonEffects', 'DomainCardContributions'):
            self.assertIn(name + '.cs', text)
        result = subprocess.run([str(dotnet), 'run', '--project', str(project), '-c', 'Release',
            '-p:Sts2DataDir=' + str(data)], cwd=ROOT, capture_output=True, text=True,
            timeout=180, env=dict(os.environ, DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        match = re.search(r'AUDIO_RECEIPT_RULES_AND_COMBINED_NATIVE_EMISSION_OK checks=(\d+)', result.stdout)
        self.assertIsNotNone(match, result.stdout + result.stderr)
        self.assertGreaterEqual(int(match.group(1)), 1745)
        self.assertIn('gameplay=NOT_RUN; playback=NOT_RUN; listening=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
