using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Keep Confused's native random rolls and local modifier order; mute only its exact modifier identities.</summary>
internal static class DomainConfusedCosts
{
    private sealed record Source(ConfusedPower Power);
    private static readonly ConditionalWeakTable<LocalCostModifier, Source> sources = new();
    private static readonly FieldInfo Modifiers = AccessTools.Field(typeof(CardEnergyCost), "_localModifiers");
    internal static void Install(Harmony harmony)
    {
        harmony.Patch(AccessTools.DeclaredMethod(typeof(ConfusedPower), nameof(ConfusedPower.AfterCardDrawn)),
            transpiler: new HarmonyMethod(typeof(DomainConfusedCosts), nameof(Roll)));
        harmony.Patch(AccessTools.DeclaredMethod(typeof(CardEnergyCost), nameof(CardEnergyCost.GetWithModifiers)),
            transpiler: new HarmonyMethod(typeof(DomainConfusedCosts), nameof(Read)));
    }
    private static IEnumerable<CodeInstruction> Roll(IEnumerable<CodeInstruction> input)
    {
        int count = 0;
        var setter = AccessTools.Method(typeof(CardEnergyCost), nameof(CardEnergyCost.SetThisCombat));
        foreach (var old in input)
        {
            var code = new CodeInstruction(old);
            if (code.Calls(setter))
            {
                var load = new CodeInstruction(OpCodes.Ldarg_0); load.labels.AddRange(code.labels); code.labels.Clear();
                yield return load;
                code.opcode = OpCodes.Call; code.operand = AccessTools.Method(typeof(DomainConfusedCosts), nameof(Set)); count++;
            }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Confused cost write drift");
    }
    private static void Set(CardEnergyCost cost, int amount, bool reduceOnly, ConfusedPower power)
    {
        var modifiers = (List<LocalCostModifier>)Modifiers.GetValue(cost)!;
        int before = modifiers.Count;
        cost.SetThisCombat(amount, reduceOnly);
        if (modifiers.Count == before + 1) sources.Add(modifiers[^1], new(power));
    }
    private static IEnumerable<CodeInstruction> Read(IEnumerable<CodeInstruction> input)
    {
        int count = 0;
        foreach (var old in input)
        {
            var code = new CodeInstruction(old);
            if (code.Calls(AccessTools.Method(typeof(LocalCostModifier), nameof(LocalCostModifier.Modify))))
            { code.opcode = OpCodes.Call; code.operand = AccessTools.Method(typeof(DomainConfusedCosts), nameof(Modify)); count++; }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Confused local cost read drift");
    }
    private static int Modify(LocalCostModifier modifier, int amount) =>
        sources.TryGetValue(modifier, out var source) && DomainSelfDebuffEffects.IsSuppressed(source.Power)
            ? amount : modifier.Modify(amount);
}
