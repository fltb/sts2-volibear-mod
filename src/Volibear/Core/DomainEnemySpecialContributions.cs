using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Exact native theft and sandpit finisher contributions, not whole-power removal.
/// Counters, native detachment, card interactions and stolen-gold death rewards stay native.</summary>
public static partial class DomainEnemySpecialContributions
{
    private const string HarmonyId = "Volibear.DomainEnemySpecialContributions";
    private static readonly object InstallLock = new();
    private static readonly Dictionary<MethodBase, string> Sites = new();
    private static bool installed;

    private static bool SuppressTargeted(PowerModel power) =>
        power.Target is { IsPlayer: true } target && power.Owner is { IsEnemy: true, IsPlayer: false } owner &&
        ReferenceEquals(target.CombatState, owner.CombatState) && owner.CombatState is { } combat &&
        combat.ContainsCreature(target) && DomainEnemyEffects.ActiveFor(owner);

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task Steal(ThieveryPower power)
    {
        if (!SuppressTargeted(power)) return power.Steal();
        Volibear.Presentation.PowerPresentationDomain.Suppressed(power.Owner, power);
        return Task.CompletedTask;
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task AfterRemoved(PowerModel power, Creature oldOwner)
    {
        // PowerCmd already detached this power, after its real decrement/amount hooks.
        // Sandpit's only removal payload is the eating animation, hiding the player/pets,
        // and force-killing player/Osty. It has no cleanup to replay later.
        // Dead-owner cleanup remains native, including the native early return.
        if (power is SandpitPower && !oldOwner.IsDead && ReferenceEquals(power.Owner, oldOwner) && SuppressTargeted(power))
        {
            Volibear.Presentation.PowerPresentationDomain.Suppressed(oldOwner, power);
            return Task.CompletedTask;
        }
        return power.AfterRemoved(oldOwner);
    }

    // FleeMove is invoked through its native MoveState delegate, not a tiny inlined getter.
    // Cancel before ToggleIsInteractable(false)/FleeTrigger, not after the enemy is hidden.
    private static bool Flee(FatGremlin __instance, ref Task __result)
    {
        if (!DomainEnemyEffects.ActiveFor(__instance.Creature)) return true;
        Volibear.Presentation.PowerPresentationDomain.Suppressed(__instance.Creature, __instance);
        __result = Task.CompletedTask;
        return false;
    }

    private static MethodInfo Method(Type owner, string name, params Type[] parameters) => owner.GetMethod(name,
        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly,
        null, parameters, null) ?? throw new MissingMethodException(owner.FullName, name);
    private static MethodInfo Handler(string name) => Method(typeof(DomainEnemySpecialContributions), name,
        name switch
        {
            nameof(Steal) => [typeof(ThieveryPower)],
            nameof(AfterRemoved) => [typeof(PowerModel), typeof(Creature)],
            nameof(Flee) => [typeof(FatGremlin), typeof(Task).MakeByRefType()],
            nameof(Rewrite) => [typeof(IEnumerable<CodeInstruction>), typeof(MethodBase)],
            _ => throw new InvalidOperationException("Unknown special contribution handler")
        });
    private static MethodInfo Machine(MethodInfo native) => Method(native.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Expected native async state machine: " + native), "MoveNext");

    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        string kind = Sites[__originalMethod];
        var native = kind == "steal" ? Method(typeof(ThieveryPower), nameof(ThieveryPower.Steal)) :
            Method(typeof(PowerModel), nameof(PowerModel.AfterRemoved), typeof(Creature));
        var wrapper = Handler(kind == "steal" ? nameof(Steal) : nameof(AfterRemoved));
        if (native.ReturnType != wrapper.ReturnType || !new[] { native.DeclaringType! }
            .Concat(native.GetParameters().Select(p => p.ParameterType)).SequenceEqual(wrapper.GetParameters().Select(p => p.ParameterType)))
            throw new InvalidOperationException("Special contribution signature drift");
        int count = 0;
        var output = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.Calls(native))
            {
                count++;
                instruction.opcode = OpCodes.Call;
                instruction.operand = wrapper;
            }
            output.Add(instruction);
        }
        if (count != 1) throw new InvalidOperationException($"Expected one {kind} contribution, found {count}: {__originalMethod}");
        return output;
    }

    public static void Install()
    {
        lock (InstallLock)
        {
            if (installed) return;
            Sites.Clear();
#if STS2_BETA
            Sites.Add(Machine(Method(typeof(GremlinMerc), "Steal")), "steal");
#else
            foreach (string move in new[] { "GimmeMove", "DoubleSmashMove", "HeheMove" })
                Sites.Add(Machine(Method(typeof(GremlinMerc), move, typeof(IReadOnlyList<Creature>))), "steal");
#endif
            Sites.Add(Machine(Method(typeof(PowerCmd), nameof(PowerCmd.Remove), typeof(PowerModel))), "removed");
            var flee = Method(typeof(FatGremlin), "FleeMove", typeof(IReadOnlyList<Creature>));
            if (flee.ReturnType != typeof(Task)) throw new InvalidOperationException("Native FatGremlin flee signature changed");
            foreach (var site in Sites.Keys) _ = Rewrite(PatchProcessor.GetOriginalInstructions(site), site).ToArray();
            var harmony = new Harmony(HarmonyId);
            try
            {
                foreach (var site in Sites.Keys) harmony.Patch(site, transpiler: new HarmonyMethod(Handler(nameof(Rewrite))));
                harmony.Patch(flee, prefix: new HarmonyMethod(Handler(nameof(Flee))));
                InstallSurprise(harmony);
                DomainSandpitEffects.Install(harmony);
                installed = true;
            }
            catch { harmony.UnpatchAll(HarmonyId); throw; }
        }
    }
}
