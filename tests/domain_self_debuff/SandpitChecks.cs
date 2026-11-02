using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

public class SandpitCombat : DispatchProxy
{
    protected override object? Invoke(MethodInfo? method, object?[]? args) => method!.Name == "ContainsCreature" ? true : throw new NotSupportedException(method.Name);
}
internal static class SandpitChecks
{
    private static bool active;
    private static bool Active(ref bool __result) { __result = active; return false; }
    public static void Run()
    {
        var fixture = new Harmony("Volibear.Tests.SandpitAvailabilityFixture");
        fixture.Patch(AccessTools.Method(typeof(DomainEnemyEffects), nameof(DomainEnemyEffects.ActiveFor), [typeof(Creature)]), prefix: new HarmonyMethod(typeof(SandpitChecks), nameof(Active)));
        var combat = DispatchProxy.Create<ICombatState, SandpitCombat>();
        var player = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        AccessTools.Field(typeof(Creature), "<Player>k__BackingField").SetValue(player, RuntimeHelpers.GetUninitializedObject(typeof(Player)));
        var enemy = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        player.CombatState = enemy.CombatState = combat;
        var pit = (SandpitPower)RuntimeHelpers.GetUninitializedObject(typeof(SandpitPower));
        AccessTools.Property(typeof(AbstractModel), "IsMutable").SetValue(pit, true);
        AccessTools.Property(typeof(PowerModel), "Owner").SetValue(pit, enemy);
        pit.Target = player;
        AccessTools.Field(typeof(PowerModel), "_amount").SetValue(pit, 1);
        try
        {
            active = true;
            if (!DomainSandpitEffects.IsSuppressed(pit)) throw new Exception("Sandpit target must be protected");
            pit.AfterSideTurnStartLate(CombatSide.Enemy, new[] { enemy }, combat).GetAwaiter().GetResult();
            if (pit.Amount != 1) throw new Exception("Last sandpit count must not decrement/detach during Domain");
            ((Task)AccessTools.Method(typeof(SandpitPower), "UpdateCreaturePositions").Invoke(pit, null)!).GetAwaiter().GetResult();
            active = false;
            if (DomainSandpitEffects.IsSuppressed(pit)) throw new Exception("Sandpit must resume after exit");
            active = true; player.CombatState = DispatchProxy.Create<ICombatState, SandpitCombat>();
            if (DomainSandpitEffects.IsSuppressed(pit)) throw new Exception("Cross-combat sandpit must not be suppressed");
            Console.WriteLine("SANDPIT_SEMANTICS_PASS checks=5 last-count-retained=true movement-muted=true");
        }
        finally { fixture.UnpatchAll(fixture.Id); }
    }
}
