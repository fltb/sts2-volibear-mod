using System;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Freeze the sandpit clock and attraction, leaving native state for resumption.</summary>
public static class DomainSandpitEffects
{
    public static bool IsSuppressed(PowerModel power) => power is SandpitPower &&
        power.Target is { IsPlayer: true } target &&
        ReferenceEquals(target.CombatState, power.Owner.CombatState) &&
        target.CombatState is { } combat && combat.ContainsCreature(target) &&
        DomainEnemyEffects.ActiveFor(power.Owner);

    internal static void Install(Harmony harmony)
    {
        // 0.107.1: the turn-start body contains only Enemy-side Decrement(this).
        // All five movement callers funnel through this one private async method.
        foreach (var name in new[] { nameof(SandpitPower.AfterSideTurnStartLate), "UpdateCreaturePositions" })
        {
            var method = AccessTools.DeclaredMethod(typeof(SandpitPower), name)
                ?? throw new MissingMethodException(typeof(SandpitPower).FullName, name);
            if (method.ReturnType != typeof(Task)) throw new InvalidOperationException("Sandpit task signature drift: " + name);
            harmony.Patch(method, prefix: new HarmonyMethod(typeof(DomainSandpitEffects), nameof(Suppress)));
        }
    }

    private static bool Suppress(SandpitPower __instance, ref Task __result)
    {
        if (!IsSuppressed(__instance)) return true;
        __result = Task.CompletedTask;
        return false;
    }
}
