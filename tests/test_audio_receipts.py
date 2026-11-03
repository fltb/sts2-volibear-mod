"""Published-source receipt routing and actual combined IL emission; not audio playback."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.runtime_test import fixture_runtime
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
        self.assertEqual(cues, {'armor_retain', 'armor_iron', 'cost_reduce', 'strength'})
        bridge = (SRC / 'Presentation/VolibearPresentationBridge.cs').read_text(encoding='utf-8')
        self.assertIn('PowerAudioReceipts.Install();', bridge)
        self.assertIn('CardPresentationReceipts.Committed += CardCommitted;', bridge)
        self.assertIn('var receipt = PowerAudioReceipts.Applied(power);', bridge)
        self.assertIn('var receipt = PowerAudioReceipts.Increased(power, amount, silent);', bridge)

    def test_thunder_armor_cue_follows_actual_lightning_batch_block(self):
        # V18 belongs to the positive block commit, not the earlier power deployment.
        powers = (SRC / 'Core/PersistentPowers.cs').read_text(encoding='utf-8')
        thunder_armor = powers.split('public sealed class ThunderArmorPower ', 1)[1].split('public sealed class ', 1)[0]
        self.assertIn('LightningBatches.Subscribe(Owner, AfterBatch)', thunder_armor)
        self.assertIn('!ReferenceEquals(receipt.Owner, Owner)', thunder_armor)
        self.assertIn('var added = Math.Min(granted, Owner.Block - before);', thunder_armor)
        publish = 'GameplayPresentationReceipts.Publish("thunder_armor_block_committed", Owner, this, amount: added);'
        self.assertEqual(thunder_armor.count(publish), 1)
        self.assertLess(thunder_armor.index('await CreatureCmd.GainBlock'), thunder_armor.index(publish))
        self.assertRegex(thunder_armor, r'if \(added > 0\)\s*' + re.escape(publish))
        bridge = (SRC / 'Presentation/VolibearPresentationBridge.Semantics.cs').read_text(encoding='utf-8')
        self.assertIn('case "thunder_armor_block_committed": AtOwner(id, "thunder_armor"); break;', bridge)

    def test_published_sources_combined_native_emission(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'baselib', root=ROOT)
        project = ROOT / 'tests/audio_receipts/AudioReceipts.csproj'
        text = project.read_text(encoding='utf-8')
        self.assertNotIn('.local/audio-receipt-stage', text)
        self.assertIn('$(RepositoryRoot)/src/Volibear/**/*.cs', text)
        self.assertNotIn('Volibear.dll', text)
        result = runtime.run(project, args=('-p:RepositoryRoot=' + str(ROOT),), timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        match = re.search(r'AUDIO_RECEIPT_RULES_AND_COMBINED_NATIVE_EMISSION_OK checks=(\d+)', result.stdout)
        self.assertIsNotNone(match, result.stdout + result.stderr)
        self.assertGreaterEqual(int(match.group(1)), 1745)
        self.assertIn('gameplay=NOT_RUN; playback=NOT_RUN; listening=NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()
