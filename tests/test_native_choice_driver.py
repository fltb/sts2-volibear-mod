"""Staged source guards only; no native choice case has run."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'src/Volibear/NativeControlledChoice.cs'


class NativeChoiceDriverGuards(unittest.TestCase):
    def test_actual_queued_request_and_successful_native_sync_are_observed(self):
        source = SOURCE.read_text(encoding='utf-8')
        for text in ['GameActionPlayerChoiceContext { Action: PlayCardAction action }',
                     'nameof(CardSelectCmd.FromHand)', 'nameof(CardSelectCmd.FromCombatPile)',
                     'nameof(PlayerChoiceSynchronizer.ReserveChoiceId)', 'nameof(PlayerChoiceSynchronizer.SyncLocalChoice)',
                     'GameActionState.GatheringPlayerChoice', 'NetCombatCard.FromModel(card)',
                     'ReferenceEquals(net.ToCardModel(), card)', 'request.Eligible.Any(e => ReferenceEquals(e, c))']:
            self.assertIn(text, source)

    def test_no_selector_override_private_ui_callback_or_direct_task_completion(self):
        source = SOURCE.read_text(encoding='utf-8')
        for forbidden in ['UseSelector(', 'PushSelector(', 'WaitForRemoteChoice(', '.SetResult(', '.TrySetResult(',
                          '.EmitSignal(', 'CardCmd.AutoPlay(', 'PreparedAttackBonus.Prepare(', 'AddModifier<',
                          '.Call("OnCardClicked"', '.Call("OnHolderPressed"', 'ref Task __result', 'ref bool __result']:
            self.assertNotIn(forbidden, source)
        self.assertIn('viewport.PushInput(new InputEventAction', source)
        self.assertIn('ReferenceEquals(viewport.GuiGetFocusOwner(), control)', source)
        self.assertIn('control.IsVisibleInTree()', source)
        self.assertIn('if (!confirm.IsEnabled)', source)

    def test_illegal_candidate_guard_does_not_masquerade_as_native_rejection(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('not a native rejection claim', source)
        self.assertIn('unreserved-future-choice-id-not-card-eligibility', source)
        self.assertIn('PlayerChoiceResult.FromMutableCombatCards(new[] { request.Eligible[0] })', source)
        self.assertIn('checked(request.ChoiceId!.Value + 1)', source)
        self.assertIn('syncBefore, syncAfter = request.Synced.Count', source)
        self.assertIn('if (eligible.Length <= prefs.MinSelect || CardSelectCmd.Selector is not null)', source)


if __name__ == '__main__':
    unittest.main()
