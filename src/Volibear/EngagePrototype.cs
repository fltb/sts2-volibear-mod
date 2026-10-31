using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;

namespace Volibear;

// Development-only prototype. Not installed in ordinary games.
// Absorption and completion responses deliberately remain unimplemented until
// their full damage pipeline and exceptional paths are covered by real tests.
internal static class EngagePrototype
{
    internal readonly record struct Result(bool Performed, decimal Absorbed, bool Completed);
    private sealed class Window { internal Creature Receiver = null!; internal decimal Absorbed; }
    private static readonly System.Threading.AsyncLocal<Window?> active = new();
    internal static int SkippedActions { get; private set; }
    private static CombatState? combat;
    private static readonly Dictionary<Creature, int> consumed = new();

    internal static bool Consumed(Creature creature) =>
        ReferenceEquals(creature.CombatState, combat) &&
        consumed.TryGetValue(creature, out int round) && round == combat!.RoundNumber;

    internal static async Task<Result> Perform(CombatState state, Creature target, Creature receiver,
        Func<Result, Task>? onCompleted = null)
    {
        if (state.CurrentSide != CombatSide.Player)
            throw new InvalidOperationException("Engage requires the player phase");
        if (!ReferenceEquals(combat, state))
        {
            consumed.Clear();
            combat = state;
        }
        if (target.IsDead || !ReferenceEquals(target.CombatState, state) ||
            target.Monster is null || Consumed(target))
            return new(false, 0, false);
        // Reserve before await. On failure abort the scenario, never retry a
        // partially performed move or restore eligibility after side effects.
        consumed[target] = state.RoundNumber;
        var previous = active.Value;
        var window = new Window { Receiver = receiver };
        active.Value = window;
        try { await target.Monster.PerformMove(); }
        finally { active.Value = previous; }
        var result = new Result(true, window.Absorbed,
            !receiver.IsDead && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding);
        if (result.Completed && onCompleted is not null) await onCompleted(result);
        return result;
    }

    internal static void Reset()
    {
        consumed.Clear();
        combat = null;
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.DamageBlockInternal))]
    internal static class ObserveAbsorption
    {
        private static void Postfix(Creature __instance, decimal __result)
        {
            if (active.Value is { } window && ReferenceEquals(window.Receiver, __instance))
                window.Absorbed += __result;
        }
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.TakeTurn))]
    internal static class SkipConsumedAction
    {
        private static bool Prefix(Creature __instance, ref Task __result)
        {
            if (!Consumed(__instance)) return true;
            SkippedActions++;
            __result = Task.CompletedTask;
            return false;
        }
    }
}
