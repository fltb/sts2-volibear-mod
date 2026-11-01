using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainAdditionalRevivalEffects
{
    private static void InstallDispatch(Harmony harmony)
    {
        foreach (var name in new[] { nameof(Hook.ShouldStopCombatFromEnding), nameof(Hook.ShouldAllowHitting), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath) })
            harmony.Patch(AccessTools.Method(typeof(Hook), name), transpiler: new HarmonyMethod(Local(nameof(VoteDispatch))));
        // The native owner-death predicate is a noncapturing LINQ lambda, not the
        // outer RemoveAllPowersAfterDeath method. Patch its actual virtual call.
        var predicates = new[] { typeof(Creature) }.Concat(typeof(Creature).GetNestedTypes(BindingFlags.Public | BindingFlags.NonPublic))
            .SelectMany(t => t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance))
            .Where(m => m.Name.Contains("<RemoveAllPowersAfterDeath>", StringComparison.Ordinal) && m.ReturnType == typeof(bool) &&
                m.GetParameters().Select(p => p.ParameterType).SequenceEqual(new[] { typeof(PowerModel) })).ToArray();
        Require(predicates.Length == 1, "owner death removal predicate");
        harmony.Patch(predicates[0], transpiler: new HarmonyMethod(Local(nameof(VoteDispatch))));
    }
    private static bool EndingDecision(bool original, AbstractModel model)
    {
        if (model is StockPower or AdaptablePower) StopEnding((PowerModel)model, ref original);
        return original;
    }
    private static bool RemovalDecision(bool original, AbstractModel model, Creature target)
    {
        if (model is AdaptablePower or PainfulStabsPower) RemovalVote((PowerModel)model, target, ref original);
        return original;
    }
    private static bool HittingDecision(bool original, AbstractModel model, Creature target)
    {
        if (model is AdaptablePower power) AllowHitting(power, target, ref original);
        return original;
    }
    private static bool PowerRemovalDecision(bool original, PowerModel model)
    {
        if (model is AdaptablePower or PainfulStabsPower) RemovePower(model, ref original);
        return original;
    }
    private static IEnumerable<CodeInstruction> VoteDispatch(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        bool ending = __originalMethod.Name == nameof(Hook.ShouldStopCombatFromEnding);
        bool hitting = __originalMethod.Name == nameof(Hook.ShouldAllowHitting);
        bool removal = __originalMethod.Name == nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath);
        var modelType = ending || hitting || removal ? typeof(AbstractModel) : typeof(PowerModel);
        var nativeName = ending ? nameof(AbstractModel.ShouldStopCombatFromEnding) : hitting ? nameof(AbstractModel.ShouldAllowHitting) :
            removal ? nameof(AbstractModel.ShouldCreatureBeRemovedFromCombatAfterDeath) : nameof(PowerModel.ShouldPowerBeRemovedAfterOwnerDeath);
        var native = AccessTools.Method(modelType, nativeName);
        var decision = Local(ending ? nameof(EndingDecision) : hitting ? nameof(HittingDecision) : removal ? nameof(RemovalDecision) : nameof(PowerRemovalDecision));
        var model = generator.DeclareLocal(modelType); var target = generator.DeclareLocal(typeof(Creature));
        var output = new List<CodeInstruction>(); int count = 0;
        foreach (var old in input)
        {
            var instruction = new CodeInstruction(old);
            bool composed = instruction.operand is MethodInfo method && method.ReturnType == typeof(bool) &&
                (ending && method.DeclaringType?.FullName == "Volibear.Core.DomainEnemySpecialContributions" && method.Name == "EndingContribution" &&
                    method.GetParameters().Select(p => p.ParameterType).SequenceEqual(new[] { typeof(AbstractModel) }) ||
                 removal && method.DeclaringType?.FullName == "Volibear.Core.DomainRevivalEffects" && method.Name == "RemovalVote" &&
                    method.GetParameters().Select(p => p.ParameterType).SequenceEqual(new[] { typeof(AbstractModel), typeof(Creature) }));
            if (!instruction.Calls(native) && !composed) { output.Add(instruction); continue; }
            var save = new CodeInstruction(OpCodes.Stloc, hitting || removal ? target : model); Transfer(instruction, save); output.Add(save);
            if (hitting || removal) output.Add(new(OpCodes.Stloc, model));
            output.Add(new(OpCodes.Ldloc, model)); if (hitting || removal) output.Add(new(OpCodes.Ldloc, target));
            output.Add(instruction); // Preserve existing Surprise/Revival dispatch, and Steam's surrounding wrapper.
            output.Add(new(OpCodes.Ldloc, model)); if (hitting || removal) output.Add(new(OpCodes.Ldloc, target));
            output.Add(new(OpCodes.Call, decision)); count++;
        }
        Require(count == 1, "source-local vote dispatch: " + __originalMethod + " / " + count);
        return output;
    }
}
