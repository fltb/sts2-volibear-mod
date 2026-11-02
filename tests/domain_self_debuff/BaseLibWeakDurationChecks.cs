using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear;
using Volibear.Content;

internal static class BaseLibWeakDurationChecks
{
    private static TaskCompletionSource pending = null!;
    // Only the native application/scene boundary is replaced. The actual BaseLib
    // postfix, its awaited wrapper, all predicates, Weak hook and TickDownDuration run.
    private static bool Apply(PowerModel power, Creature applier, ref Task __result)
    {
        power.Applier = applier;
        power.SkipNextDurationTick = true;
        __result = pending.Task;
        return false;
    }
    private static bool Decrement(PowerModel power, ref Task __result)
    {
        AccessTools.Field(typeof(PowerModel), "_amount").SetValue(power, power.Amount - 1);
        __result = Task.CompletedTask; return false;
    }
    private static T Empty<T>() => (T)RuntimeHelpers.GetUninitializedObject(typeof(T));
    private static void Set(object o, string name, object value) => AccessTools.Field(o.GetType(), name).SetValue(o, value);
    internal static void Run()
    {
        int checks = 0;
        void Need(bool ok, string label) { checks++; if (!ok) throw new Exception(label); }
        var owner = Empty<Creature>(); var player = Empty<Player>(); var state = Empty<CombatState>();
        Set(owner, "<Player>k__BackingField", player); Set(owner, "<Side>k__BackingField", CombatSide.Player);
        owner.CombatState = state;
        var enemy = Empty<Creature>(); Set(enemy, "<Side>k__BackingField", CombatSide.Enemy);
        var weak = Empty<WeakPower>();
        typeof(AbstractModel).GetProperty("IsMutable", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)!.SetValue(weak, true);
        var h = new Harmony("Volibear.Tests.BaseLibWeakDuration");
        try
        {
            h.CreateClassProcessor(typeof(BaseLib.Patches.Utils.SelfApplyDebuffPatch)).Patch();
            var apply = typeof(PowerCmd).GetMethods().Single(m => m.Name == nameof(PowerCmd.Apply) && !m.IsGenericMethod);
            h.Patch(apply, prefix: new(typeof(BaseLibWeakDurationChecks), nameof(Apply)));
            h.Patch(AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Decrement)), prefix: new(typeof(BaseLibWeakDurationChecks), nameof(Decrement)));
            Need(Harmony.GetPatchInfo(apply)!.Postfixes.Any(p => p.PatchMethod.DeclaringType == typeof(BaseLib.Patches.Utils.SelfApplyDebuffPatch)), "actual required BaseLib postfix installed on Apply");
            foreach (var kind in new[] { "custom-self", "enemy-source", "stock-self", "enemy-phase" })
            {
                Set(player, "<Character>k__BackingField", kind == "stock-self" ? Empty<Ironclad>() : (CharacterModel)Empty<VolibearCharacter>());
                state.CurrentSide = kind == "enemy-phase" ? CombatSide.Enemy : CombatSide.Player;
                Set(weak, "_amount", 2); pending = new TaskCompletionSource();
                Task wrapped = PowerCmd.Apply(new ThrowingPlayerChoiceContext(), weak, owner, 2m, kind == "enemy-source" ? enemy : owner, null);
                Need(!wrapped.IsCompleted && weak.SkipNextDurationTick, "BaseLib waits for native application completion: " + kind);
                pending.SetResult(); wrapped.GetAwaiter().GetResult();
                bool expectedSkip = kind != "custom-self";
                Need(weak.SkipNextDurationTick == expectedSkip, "complete awaited Apply chain gives exact scoped skip rule: " + kind);
                var trace = DomainSuppressionAcceptanceProbe.ObserveWeakDuration(weak, owner, new ThrowingPlayerChoiceContext()).GetAwaiter().GetResult();
                Need(trace[0] == new DomainSuppressionAcceptanceProbe.WeakDurationStep("applied", 2, expectedSkip) &&
                     trace[1] == new DomainSuppressionAcceptanceProbe.WeakDurationStep("player-end", 2, expectedSkip) &&
                     trace[2] == new DomainSuppressionAcceptanceProbe.WeakDurationStep("first-enemy-end", expectedSkip ? 2 : 1, false) &&
                     trace[3] == new DomainSuppressionAcceptanceProbe.WeakDurationStep("next-enemy-end", expectedSkip ? 1 : 0, false),
                     "actual dependency wrapper plus native lifetime trace: " + kind);
            }
            Console.WriteLine($"BASELIB_WEAK_DURATION_PASS checks={checks} actual-postfix-and-await=true apply-decrement-scene-seams=true gameplay=NOT_RUN");
        }
        finally { h.UnpatchAll(h.Id); }
    }
}
