using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear;

internal static class WeakDurationChecks
{
    private static int decrements;
    private static bool Decrement(PowerModel power, ref Task __result)
    {
        decrements++;
        AccessTools.Field(typeof(PowerModel), "_amount").SetValue(power, power.Amount - 1);
        __result = Task.CompletedTask;
        return false;
    }
    private static bool Swallow(ref Task __result) { __result = Task.CompletedTask; return false; }
    internal static void Run()
    {
        int checks = 0;
        void Need(bool value, string label) { checks++; if (!value) throw new Exception(label); }
        var h = new Harmony("Volibear.Tests.WeakDuration");
        var swallow = new Harmony("Volibear.Tests.WeakDuration.Mutation");
        var weak = (WeakPower)RuntimeHelpers.GetUninitializedObject(typeof(WeakPower));
        typeof(AbstractModel).GetProperty("IsMutable", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(weak, true);
        var owner = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        void Reset(bool skip = true)
        {
            AccessTools.Field(typeof(PowerModel), "_amount").SetValue(weak, 2);
            weak.SkipNextDurationTick = skip; decrements = 0;
        }
        DomainSuppressionAcceptanceProbe.WeakDurationStep[] Expected() => [
            new("applied", 2, true), new("player-end", 2, true),
            new("first-enemy-end", 2, false), new("next-enemy-end", 1, false) ];
        DomainSuppressionAcceptanceProbe.WeakDurationStep[] Observe() =>
            DomainSuppressionAcceptanceProbe.ObserveWeakDuration(weak, owner, new ThrowingPlayerChoiceContext()).GetAwaiter().GetResult();
        try
        {
            // Retain the native Weak side test and native TickDownDuration skip branch.
            // Only the final decrement's command/scene boundary is a deterministic seam.
            h.Patch(AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Decrement)), prefix: new(typeof(WeakDurationChecks), nameof(Decrement)));
            var apply = typeof(PowerCmd).GetMethods().Single(m => m.Name == nameof(PowerCmd.Apply) && !m.IsGenericMethod);
            var applyBody = AccessTools.Method(apply.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
            Need(PatchProcessor.GetOriginalInstructions(applyBody).Count(c => c.Calls(AccessTools.PropertySetter(typeof(PowerModel), nameof(PowerModel.SkipNextDurationTick)))) == 1,
                "locked application retains one native skip-tick setter");
            Reset(); var trace = Observe();
            Need(trace.SequenceEqual(Expected()), "real Weak callback plus real TickDownDuration obey Player/no-tick, Enemy/skip, Enemy/decrement");
            Need(decrements == 1 && weak.Amount == 1 && !weak.SkipNextDurationTick, "one decrement only after skip is consumed");
            Reset(false);
            Need(!Observe().SequenceEqual(Expected()), "missing native initial skip is rejected, not adjusted to observed output");
            swallow.Patch(AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.TickDownDuration)), prefix: new(typeof(WeakDurationChecks), nameof(Swallow)));
            Reset();
            Need(!Observe().SequenceEqual(Expected()) && decrements == 0, "suppressed native clock mutation is rejected");
            Console.WriteLine($"WEAK_NATIVE_DURATION_PASS checks={checks} actual-side-and-skip-callbacks=true decrement-command-seam=true gameplay=NOT_RUN");
        }
        finally { swallow.UnpatchAll(swallow.Id); h.UnpatchAll(h.Id); }
    }
}
