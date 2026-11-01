"""Source lifecycle contracts, not native abandonment/gameplay acceptance."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src/Volibear/Core/EngageCmd.cs').read_text(encoding='utf-8')
KERNEL = (ROOT / 'src/Volibear/Core/EngageOpportunityLedger.cs').read_text(encoding='utf-8')


class EngageLifecycleContracts(unittest.TestCase):
    def test_abandonment_invalidates_async_execution_contexts(self):
        self.assertIn('nameof(CombatManager.Reset), new[] { typeof(bool) }', SOURCE)
        self.assertIn('typeof(AbandonCombat)', SOURCE)
        self.assertIn('Opportunities.Reset();', SOURCE)
        self.assertIn('Generation = checked(Generation + 1);', KERNEL)
        self.assertIn('Opportunities.IsCurrent(window.Combat, window.Generation)', SOURCE)
        self.assertIn('Generation = Opportunities.Generation', SOURCE)
        self.assertIn('Generation == generation', KERNEL)
        self.assertIn('ReferenceEquals(window.Combat, CombatManager.Instance.DebugOnlyGetState())', SOURCE)
        self.assertIn('previous is not null && Live(previous) ? previous : null', SOURCE)

    def test_reservation_and_live_check_precede_actual_action(self):
        start = SOURCE.index('public static async Task<Result> Perform(')
        method = SOURCE[start:SOURCE.index('public static async Task<IReadOnlyList<Result>>', start)]
        reservation = 'if (!Opportunities.TryReserve(state, target.CombatState, target, state.RoundNumber))'
        self.assertLess(method.index(reservation), method.index('await node.PerformIntent()'))
        self.assertIn(reservation + '\n            return new(false, 0, false);', method)
        self.assertIn('Entry(enemy).EarlyRound = round;', KERNEL)
        self.assertLess(method.index('await node.PerformIntent()'), method.index('if (!Live(window)'))
        self.assertLess(method.index('if (!Live(window)'), method.index('await target.Monster.PerformMove()'))
        self.assertIn('var completed = Live(window)', method)
        self.assertIn('if (!Live(window) || receiver.IsDead', method)

    def test_natural_action_observation_uses_real_initial_move_next(self):
        start = SOURCE.index('private static class ObserveActionStart')
        method = SOURCE[start:SOURCE.index('[HarmonyPatch(typeof(Creature), nameof(Creature.TakeTurn))', start)]
        self.assertIn('GetCustomAttribute<AsyncStateMachineAttribute>()', method)
        self.assertIn('AccessTools.Method(Machine, "MoveNext")', method)
        self.assertIn('(int)State.GetValue(__instance)! != -1', method)
        self.assertIn('!ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())', method)
        self.assertIn('Opportunities.ObserveActionStart(state, monster.Creature.CombatState, monster.Creature, state.RoundNumber)', method)
        self.assertIn('Entry(enemy).ActionRound = round;', KERNEL)

    def test_single_authority_and_native_skip_distinction(self):
        self.assertIn('private static readonly EngageOpportunityLedger Opportunities = new();', SOURCE)
        self.assertNotIn('Dictionary<', SOURCE)
        self.assertNotIn('ConsumedRounds', SOURCE)
        self.assertNotIn('ActionRounds', SOURCE)
        self.assertIn('Opportunities.EnsureCombat(state)', SOURCE)
        self.assertIn('Opportunities.Consumed(state, enemy.CombatState, enemy, state.RoundNumber)', SOURCE)
        self.assertIn('Opportunities.EarlyConsumed(state, enemy.CombatState, enemy, state.RoundNumber)', SOURCE)
        skip = SOURCE[SOURCE.index('private static class SkipConsumedAction'):]
        self.assertIn('if (!EarlyConsumed(__instance)) return true;', skip)
        self.assertIn('creature.CombatState?.CurrentSide != CombatSide.Enemy || !EarlyConsumed(creature)', skip)
        self.assertNotIn('!Consumed(', skip)
        self.assertNotIn('SpawnedThisTurn', SOURCE)

    def test_probe_diagnostics_use_single_kernel_projections(self):
        self.assertIn('EarlyOpportunityEntryCount => Opportunities.EarlyEntryCount', SOURCE)
        self.assertIn('NaturalOpportunityEntryCount => Opportunities.NaturalEntryCount', SOURCE)
        for name in ('EnemyMatrixProbe.cs', 'EnemyExplorationProbe.cs'):
            with self.subTest(probe=name):
                probe = (ROOT / 'src/Volibear' / name).read_text(encoding='utf-8')
                self.assertNotIn('StaticField(typeof(EngageCmd), "ConsumedRounds")', probe)
                self.assertNotIn('StaticField(typeof(EngageCmd), "ActionRounds")', probe)
                self.assertIn('engageConsumed = EngageCmd.EarlyOpportunityEntryCount', probe)
                self.assertIn('engageActionRounds = EngageCmd.NaturalOpportunityEntryCount', probe)

    def test_native_filters_order_and_responses_preserved(self):
        for guard in ('receiver.IsDead || target.IsDead || target.Monster is null || !target.IsEnemy',
                      '!ReferenceEquals(target.CombatState, state) || !state.ContainsCreature(target)',
                      '!CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding',
                      'ReferenceEquals(window.Receiver.CombatState, window.Combat)'):
            self.assertIn(guard, SOURCE)
        self.assertIn('receiver.Player!.Relics.Cast<object>().Concat(receiver.Powers)', SOURCE)
        self.assertIn('foreach (var responder in responders)', SOURCE)
        self.assertIn('await responder.AfterEngageCompleted(completion)', SOURCE)
        self.assertIn('var targets = state.Enemies.ToArray()', SOURCE)
        self.assertIn('results.Add(await Perform(choices, target, card))', SOURCE)
        self.assertIn('window.Absorbed += __result;', SOURCE)
        self.assertEqual(SOURCE.count('await target.Monster.PerformMove()'), 1)


if __name__ == '__main__':
    unittest.main()
