using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainPlayerDebuffContributions
{
    private sealed record NullSource(Creature Source, ICombatState? Combat, HashSet<Creature> Targets);
    private static ConditionalWeakTable<PlayerChoiceContext, NullSource> nullSources = new();

    private static void InstallNullSource(Harmony harmony) => harmony.Patch(
        Machine(typeof(SlimedBerserker), "LeechingHugMove"),
        transpiler: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(BerserkerCallsite)));

    private static IEnumerable<CodeInstruction> BerserkerCallsite(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var source = AccessTools.Field(__originalMethod.DeclaringType, "<>4__this");
        if (source?.FieldType != typeof(SlimedBerserker)) throw new InvalidOperationException("Berserker Weak source changed.");
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        int count = 0;
        for (int i = 0; i < code.Count; i++)
        {
            if (code[i].operand is not MethodInfo method || method.DeclaringType != typeof(PowerCmd) ||
                method.Name != nameof(PowerCmd.Apply) || !method.IsGenericMethod ||
                !method.GetGenericArguments().SequenceEqual([typeof(WeakPower)])) continue;
            var expected = new[] { typeof(PlayerChoiceContext), typeof(IEnumerable<Creature>), typeof(decimal),
                typeof(Creature), typeof(CardModel), typeof(bool) };
            if (!method.GetParameters().Select(p => p.ParameterType).SequenceEqual(expected) ||
                method.ReturnType != typeof(Task<IReadOnlyList<WeakPower>>))
                throw new InvalidOperationException("Berserker Weak API changed.");
            // The pinned source constructs this context solely for this exact call.
            // Reject drift rather than assigning an ambient move scope to nested effects.
            int contexts = code.Take(i).Count(c => c.opcode == OpCodes.Newobj && c.operand is ConstructorInfo ctor &&
                ctor.DeclaringType == typeof(ThrowingPlayerChoiceContext));
            if (contexts != 1 || code[i].blocks.Count != 0) throw new InvalidOperationException("Berserker exact Weak context changed.");
            var load = new CodeInstruction(OpCodes.Ldarg_0);
            load.labels.AddRange(code[i].labels); code[i].labels.Clear();
            code.InsertRange(i, [load, new CodeInstruction(OpCodes.Ldfld, source)]);
            code[i + 2].opcode = OpCodes.Call; code[i + 2].operand = Own(nameof(BerserkerWeak));
            i += 2; count++;
        }
        if (count != 1) throw new InvalidOperationException("Berserker Weak callsite changed.");
        return code;
    }

    private static async Task<IReadOnlyList<WeakPower>> BerserkerWeak(PlayerChoiceContext context,
        IEnumerable<Creature> targets, decimal amount, Creature? applier, CardModel? card, bool silent, SlimedBerserker source)
    {
        if (applier is not null || card is not null || context is not ThrowingPlayerChoiceContext)
            throw new InvalidOperationException("Berserker Weak arguments changed.");
        var snapshot = targets.ToArray();
        var table = nullSources;
        table.Add(context, new NullSource(source.Creature, source.Creature.CombatState,
            new HashSet<Creature>(snapshot, ReferenceEqualityComparer.Instance)));
        try
        {
            // Native null applier is deliberately preserved: no new given-modifier,
            // history source, Artifact attribution or power.Applier is fabricated.
            return await PowerCmd.Apply<WeakPower>(context, snapshot, amount, applier, card, silent);
        }
        finally { table.Remove(context); }
    }
}
