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
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainPlayerStatContributions
{
    private sealed class Possession(ICombatState combat)
    {
        internal readonly ICombatState Combat = combat;
        internal readonly Dictionary<Creature, PossessedStat> Targets = new(ReferenceEqualityComparer.Instance);
    }
    private sealed class PossessedStat(int epoch)
    {
        internal int Epoch = epoch;
        internal int Outstanding;
    }
    private static ConditionalWeakTable<PowerModel, Possession> possessions = new();
    private sealed class PossessContext(PlayerChoiceContext parent, PowerModel source, Creature target, bool strength) : PlayerChoiceContext
    {
        internal readonly PowerModel Source = source;
        internal readonly Creature Target = target;
        internal readonly bool Strength = strength;
        internal bool Observed;
#if STS2_BETA
        public override GameActionType? GameActionType => parent.GameActionType;
        public override ulong? OwnerId => parent.OwnerId;
        public override Task SignalPlayerChoiceBegun(Player player, PlayerChoiceOptions options) => parent.SignalPlayerChoiceBegun(player, options);
#else
        public override Task SignalPlayerChoiceBegun(PlayerChoiceOptions options) => parent.SignalPlayerChoiceBegun(options);
#endif
        public override Task SignalPlayerChoiceEnded() => parent.SignalPlayerChoiceEnded();
    }
    private static void PossessDebit(Creature target, Creature source, bool strength, int amount, Ledger ledger)
    {
        PowerModel? power = strength ? source.GetPower<PossessStrengthPower>() : source.GetPower<PossessSpeedPower>();
        if (power is null) return;
        if (!possessions.TryGetValue(power, out var possession) || !ReferenceEquals(possession.Combat, target.CombatState))
        {
            possession = new Possession(target.CombatState!); possessions.Remove(power); possessions.Add(power, possession);
        }
        int epoch = strength ? ledger.StrengthEpoch : ledger.DexterityEpoch;
        if (!possession.Targets.TryGetValue(target, out var stat)) possession.Targets.Add(target, stat = new PossessedStat(epoch));
        if (stat.Epoch != epoch) { stat.Outstanding = 0; stat.Epoch = epoch; }
        stat.Outstanding = checked(stat.Outstanding + amount);
    }
    private static bool PossessCredit(PlayerChoiceContext context, Creature target, bool strength, int delta, Ledger ledger)
    {
        if (context is not PossessContext { Observed: false } refund || !ReferenceEquals(refund.Target, target) || refund.Strength != strength) return false;
        refund.Observed = true;
        if (delta <= 0 || !possessions.TryGetValue(refund.Source, out var possession) ||
            !ReferenceEquals(possession.Combat, target.CombatState) || !possession.Targets.TryGetValue(target, out var stat)) return true;
        int epoch = strength ? ledger.StrengthEpoch : ledger.DexterityEpoch;
        if (stat.Epoch != epoch) { stat.Outstanding = 0; stat.Epoch = epoch; }
        int repaid = Math.Min(stat.Outstanding, delta);
        stat.Outstanding -= repaid;
        if (strength) ledger.StrengthDebt = Math.Max(0, ledger.StrengthDebt - repaid);
        else ledger.DexterityDebt = Math.Max(0, ledger.DexterityDebt - repaid);
        return true;
    }
    private static Task<T?> PossessReturn<T>(PlayerChoiceContext context, Creature target, decimal amount, Creature? applier,
        CardModel? card, bool silent, PowerModel source) where T : PowerModel
    {
        // The beforecommit cancellation gate skips native AfterPowerAmountChanged, so cancelled
        // theft never enters Possess's native stolen dictionary and earns no native refund.
        // Keep the native requested return (including untracked prior state); only the exact
        // observed source/target debt is retired by the actual positive commit below.
        var receipt = new PossessContext(context, source, target, typeof(T) == typeof(StrengthPower));
        if (context.LastInvolvedModel is { } model) receipt.PushModel(model);
        return PowerCmd.Apply<T>(receipt, target, amount, applier, card, silent);
    }
    private static Task<StrengthPower?> ReturnStrength(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, PowerModel source) => PossessReturn<StrengthPower>(context, target, amount, applier, card, silent, source);
    private static Task<DexterityPower?> ReturnDexterity(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, PowerModel source) => PossessReturn<DexterityPower>(context, target, amount, applier, card, silent, source);
    private static IEnumerable<CodeInstruction> RewritePossess(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var owner = __originalMethod.DeclaringType!.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
            .Single(f => f.FieldType == typeof(PossessStrengthPower) || f.FieldType == typeof(PossessSpeedPower));
        bool strength = owner.FieldType == typeof(PossessStrengthPower);
        int count = 0;
        var output = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(PowerCmd) && method.Name == nameof(PowerCmd.Apply) &&
                method.IsGenericMethod && method.GetGenericArguments().Single() == (strength ? typeof(StrengthPower) : typeof(DexterityPower)) &&
                method.GetParameters().Length == 6 && method.GetParameters()[1].ParameterType == typeof(Creature))
            {
                if (instruction.blocks.Count != 0) throw new InvalidOperationException("Possess refund exception boundary changed");
                count++;
                var load = new CodeInstruction(OpCodes.Ldarg_0); load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                output.Add(load); output.Add(new CodeInstruction(OpCodes.Ldfld, owner));
                instruction.opcode = OpCodes.Call; instruction.operand = Handler(strength ? nameof(ReturnStrength) : nameof(ReturnDexterity));
            }
            output.Add(instruction);
        }
        if (count != 1) throw new InvalidOperationException("Expected one exact Possess return call");
        return output;
    }
    private static void InstallPossess(Harmony harmony)
    {
        foreach (var type in new[] { typeof(PossessStrengthPower), typeof(PossessSpeedPower) })
        {
            var state = type.GetMethod(nameof(PossessStrengthPower.AfterDeath))!.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
            var move = state.GetMethod("MoveNext", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance)!;
            _ = RewritePossess(PatchProcessor.GetOriginalInstructions(move), move).ToArray();
            harmony.Patch(move, transpiler: new HarmonyMethod(Handler(nameof(RewritePossess))));
        }
    }
}
