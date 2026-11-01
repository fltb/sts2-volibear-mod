using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

public static partial class DomainPlayerDebuffContributions
{
    // The adjacent finite stat adapter can participate in this SAME native gate.
    // It owns its own source/debt policy, not a second overlapping PowerCmd transpiler.
    internal static Func<PowerModel, Creature, decimal, Creature?, CardModel?, PlayerChoiceContext, bool>? StatCancellation;

    private static bool CancelCommit(PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, PlayerChoiceContext context) =>
        ShouldCancel(power, target, amount, applier, card, context) ||
        DomainEnemyStatusContributions.ShouldCancelTainted(power, target, amount, applier, card, context) ||
        StatCancellation?.Invoke(power, target, amount, applier, card, context) == true;

    private static void InstallCommitGates(Harmony harmony)
    {
        foreach (var (name, args) in new[]
        {
            (nameof(PowerCmd.Apply), new[] { typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature),
                typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool) }),
            (nameof(PowerCmd.ModifyAmount), new[] { typeof(PlayerChoiceContext), typeof(PowerModel), typeof(decimal),
                typeof(Creature), typeof(CardModel), typeof(bool) })
        })
        {
            var method = AccessTools.Method(typeof(PowerCmd), name, args)
                ?? throw new MissingMethodException("Native debuff commit method missing: " + name);
            var machine = method.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()?.StateMachineType
                ?? throw new InvalidOperationException("Native debuff commit machine missing.");
            harmony.Patch(AccessTools.Method(machine, "MoveNext"), transpiler:
                new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(CommitGate))
                {
                    after = ["Volibear.DomainPassiveEffects", "Volibear.DomainCardContributions"],
                    priority = Priority.Last
                });
        }
    }

    private static IEnumerable<CodeInstruction> CommitGate(IEnumerable<CodeInstruction> input,
        ILGenerator generator, MethodBase __originalMethod)
    {
        var machine = __originalMethod.DeclaringType!;
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        bool apply = machine.Name.StartsWith("<Apply>", StringComparison.Ordinal);
        FieldInfo Field(string name, Type type)
        {
            var field = AccessTools.Field(machine, name);
            if (field?.FieldType != type) throw new InvalidOperationException("Debuff native state field changed: " + name);
            return field;
        }
        var power = Field("power", typeof(PowerModel));
        var target = Field(apply ? "target" : "<owner>5__2", typeof(Creature));
        var amount = Field(apply ? "<modifiedAmount>5__3" : "<modifiedOffset>5__4", typeof(decimal));
        var applier = Field("applier", typeof(Creature));
        var card = Field("cardSource", typeof(CardModel));
        var context = Field("choiceContext", typeof(PlayerChoiceContext));
        var state = Field("<>1__state", typeof(int));
        int finish = code.Select((c, i) => (c, i)).Single(x => x.c.operand is MethodInfo method &&
            method.Name == "SetResult" && method.DeclaringType?.FullName?.StartsWith("System.Runtime.CompilerServices.AsyncTaskMethodBuilder", StringComparison.Ordinal) == true).i;
        int end = code.FindLastIndex(c => c.blocks.Any(b => b.blockType == ExceptionBlockType.EndExceptionBlock));
        if (end < 0 || end + 3 >= finish || code[end + 1].opcode != OpCodes.Ldarg_0 ||
            !code[end + 2].LoadsConstant(-2) || code[end + 3].opcode != OpCodes.Stfld || !Equals(code[end + 3].operand, state))
            throw new InvalidOperationException("Debuff native successful epilogue changed.");
        if (!apply && (code[finish - 1].opcode != OpCodes.Ldloc_1 ||
            __originalMethod.GetMethodBody()!.LocalVariables[1].LocalType != typeof(int)))
            throw new InvalidOperationException("Debuff native amount result local changed.");
        var done = generator.DefineLabel(); code[end + 1].labels.Add(done);
        int anchor;
        if (apply)
        {
            // The second CanReceivePowers check is AFTER the original BeforeApplied
            // await/GetResult. This anchor survives the other adapters' commit wrappers.
            int can = code.FindLastIndex(c => c.Calls(AccessTools.PropertyGetter(typeof(Creature), nameof(Creature.CanReceivePowers))));
            anchor = can - 2;
            if (anchor < 0 || code[anchor].opcode != OpCodes.Ldarg_0 || code[anchor + 1].opcode != OpCodes.Ldfld ||
                !Equals(code[anchor + 1].operand, target))
                throw new InvalidOperationException("Debuff new-apply precommit anchor changed.");
        }
        else
        {
            int history = code.Select((c, i) => (c, i)).Single(x => x.c.operand is MethodInfo method &&
                method.Name == "PowerReceived").i;
            anchor = history - 10;
            if (anchor < 0 || !code[anchor].Calls(AccessTools.PropertyGetter(typeof(CombatManager), nameof(CombatManager.Instance))) ||
                code[anchor + 1].operand is not MethodInfo getter || getter.Name != "get_History")
                throw new InvalidOperationException("Debuff stacked prehistory anchor changed.");
        }
        if (code[anchor].blocks.Count != 0) throw new InvalidOperationException("Debuff gate crosses native EH boundary.");
        var allowed = generator.DefineLabel();
        var guard = new List<CodeInstruction>();
        foreach (var field in new[] { power, target, amount, applier, card, context })
        {
            guard.Add(new CodeInstruction(OpCodes.Ldarg_0));
            guard.Add(new CodeInstruction(OpCodes.Ldfld, field));
        }
        guard.Add(new CodeInstruction(OpCodes.Call, Own(nameof(CancelCommit))));
        guard.Add(new CodeInstruction(OpCodes.Brfalse, allowed));
        if (!apply)
            guard.AddRange([new CodeInstruction(OpCodes.Ldarg_0), new CodeInstruction(OpCodes.Ldfld, power),
                new CodeInstruction(OpCodes.Callvirt, AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Amount))),
                new CodeInstruction(OpCodes.Stloc_1)]);
        guard.Add(new CodeInstruction(OpCodes.Leave, done));
        guard[0].labels.AddRange(code[anchor].labels); code[anchor].labels.Clear();
        code[anchor].labels.Add(allowed);
        code.InsertRange(anchor, guard);
        return code;
    }
}
