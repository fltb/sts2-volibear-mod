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
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainPlayerStatContributions
{
    private sealed class TenderReceipt(ICombatState combat, Creature owner)
    {
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Owner = owner;
        internal int StrengthPaid, DexterityPaid;
        internal int StrengthOutstanding, DexterityOutstanding;
        internal int StrengthEpoch, DexterityEpoch;
        internal bool DomainTouched;
        internal Creature? PresentationEnemy;
    }
    // An invocation-owned receipt, not ambient side/AsyncLocal attribution. Choice operations
    // still delegate to the original context. Nested unrelated calls fail target/stat checks.
    private sealed class TenderContext(PlayerChoiceContext parent, Creature target, bool strength, bool debit, TenderReceipt receipt) : PlayerChoiceContext
    {
        internal readonly Creature Target = target;
        internal readonly TenderReceipt Receipt = receipt;
        internal readonly bool Strength = strength, Debit = debit;
        internal int Committed;
        internal bool Observed;
        public override Task SignalPlayerChoiceBegun(PlayerChoiceOptions options) => parent.SignalPlayerChoiceBegun(options);
        public override Task SignalPlayerChoiceEnded() => parent.SignalPlayerChoiceEnded();
    }
    private static bool IsTenderDebit(PlayerChoiceContext context, Creature target) =>
        context is TenderContext { Debit: true, Observed: false } tender && ReferenceEquals(tender.Target, target);

    private static async Task<T?> TenderApply<T>(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, TenderPower tender, bool debit) where T : PowerModel
    {
        bool strength = typeof(T) == typeof(StrengthPower);
        if (!tenders.TryGetValue(tender, out var receipt) || !ReferenceEquals(receipt.Combat, target.CombatState) ||
            !ReferenceEquals(receipt.Owner, target))
        {
            if (!target.IsPlayer || target.CombatState is null) return await PowerCmd.Apply<T>(context, target, amount, applier, card, silent);
            receipt = new TenderReceipt(target.CombatState!, target) { PresentationEnemy = applier };
            tenders.Remove(tender); tenders.Add(tender, receipt);
        }
        bool active = DomainEnemyEffects.ActiveFor(target.CombatState);
        receipt.DomainTouched |= active;
        if (debit && active)
        {
            Volibear.Presentation.PowerPresentationDomain.Suppressed(receipt.PresentationEnemy, tender, card, amount, sourceCombat: receipt.Combat);
            return null;
        }
        int paid = strength ? receipt.StrengthPaid : receipt.DexterityPaid;
        // Until domain participates, preserve even native modifier/refund quirks verbatim.
        // Once it does, only a debit which really committed can earn a refund.
        decimal requested = !debit && receipt.DomainTouched ? paid : amount;
        var invocation = new TenderContext(context, target, strength, debit, receipt);
        if (context.LastInvolvedModel is { } model) invocation.PushModel(model);
        var result = await PowerCmd.Apply<T>(invocation, target, requested, applier, card, silent);
        if (debit)
        {
            if (strength) receipt.StrengthPaid += Math.Max(0, -invocation.Committed);
            else receipt.DexterityPaid += Math.Max(0, -invocation.Committed);
        }
        else
        {
            if (strength) receipt.StrengthPaid = 0; else receipt.DexterityPaid = 0;
            // Native clears CardsPlayedThisTurn after both independent stat refunds.
            if (!strength) receipt.DomainTouched = false;
        }
        return result;
    }
    private static Task<StrengthPower?> TenderStrength(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, TenderPower tender, bool debit) =>
        TenderApply<StrengthPower>(context, target, amount, applier, card, silent, tender, debit);
    private static Task<DexterityPower?> TenderDexterity(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, TenderPower tender, bool debit) =>
        TenderApply<DexterityPower>(context, target, amount, applier, card, silent, tender, debit);

    private static readonly Dictionary<MethodBase, bool> tenderSites = new();
    private static bool installed;
    private const string HarmonyId = "Volibear.DomainPlayerStatContributions";
    private static MethodInfo Handler(string name) => typeof(DomainPlayerStatContributions).GetMethod(name,
        BindingFlags.Static | BindingFlags.NonPublic) ?? throw new MissingMethodException(name);
    private static IEnumerable<CodeInstruction> RewriteTender(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        bool debit = tenderSites[__originalMethod];
        var field = __originalMethod.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)
            .Single(f => f.FieldType == typeof(TenderPower));
        int strength = 0, dexterity = 0;
        var result = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.operand is MethodInfo call && call.DeclaringType == typeof(PowerCmd) &&
                call.Name == nameof(PowerCmd.Apply) && call.IsGenericMethod &&
                call.GetParameters().Length == 6 && call.GetParameters()[1].ParameterType == typeof(Creature))
            {
                var stat = call.GetGenericArguments().Single();
                string? wrapper = stat == typeof(StrengthPower) ? nameof(TenderStrength) :
                    stat == typeof(DexterityPower) ? nameof(TenderDexterity) : null;
                if (wrapper is not null)
                {
                    if (instruction.blocks.Count != 0) throw new InvalidOperationException("Tender call exception boundary changed");
                    if (stat == typeof(StrengthPower)) strength++; else dexterity++;
                    var load = new CodeInstruction(OpCodes.Ldarg_0); load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                    result.Add(load); result.Add(new CodeInstruction(OpCodes.Ldfld, field));
                    result.Add(new CodeInstruction(debit ? OpCodes.Ldc_I4_1 : OpCodes.Ldc_I4_0));
                    instruction.opcode = OpCodes.Call; instruction.operand = Handler(wrapper);
                }
            }
            result.Add(instruction);
        }
        if (strength != 1 || dexterity != 1) throw new InvalidOperationException("Expected exactly one Tender call for each stat");
        return result;
    }
    private static void RemoveCommit(PowerModel power)
    {
        Removing(power);
        power.RemoveInternal();
    }
    private static IEnumerable<CodeInstruction> RewriteRemove(IEnumerable<CodeInstruction> instructions)
    {
        var native = typeof(PowerModel).GetMethod(nameof(PowerModel.RemoveInternal))!;
        int count = 0;
        var output = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.Calls(native))
            {
                count++; instruction.opcode = OpCodes.Call; instruction.operand = Handler(nameof(RemoveCommit));
            }
            output.Add(instruction);
        }
        if (count != 1) throw new InvalidOperationException("Expected one native PowerCmd removal commit");
        return output;
    }
    public static void Install()
    {
        if (installed) return;
        tenderSites.Clear();
        foreach (var (name, debit) in new[] { (nameof(TenderPower.AfterCardPlayed), true), (nameof(TenderPower.AfterSideTurnEnd), false) })
        {
            var native = typeof(TenderPower).GetMethod(name)!;
            var machine = native.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
                ?? throw new InvalidOperationException("Tender async state machine missing");
            var move = machine.GetMethod("MoveNext", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance)!;
            tenderSites.Add(move, debit);
            _ = RewriteTender(PatchProcessor.GetOriginalInstructions(move), move).ToArray();
        }
        var removeNative = typeof(PowerCmd).GetMethod(nameof(PowerCmd.Remove), [typeof(PowerModel)])!;
        var removeMachine = removeNative.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("PowerCmd.Remove async state machine missing");
        var removeMove = removeMachine.GetMethod("MoveNext", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance)!;
        _ = RewriteRemove(PatchProcessor.GetOriginalInstructions(removeMove)).ToArray();
        var harmony = new Harmony(HarmonyId);
        try
        {
            foreach (var site in tenderSites.Keys) harmony.Patch(site, transpiler: new HarmonyMethod(Handler(nameof(RewriteTender))));
            harmony.Patch(removeMove, transpiler: new HarmonyMethod(Handler(nameof(RewriteRemove))));
            harmony.Patch(typeof(CombatManager).GetMethod(nameof(CombatManager.Reset)), prefix: new HarmonyMethod(typeof(DomainPlayerStatContributions), nameof(Reset)));
            InstallPossess(harmony);
            installed = true;
        }
        catch { harmony.UnpatchAll(HarmonyId); Reset(); throw; }
    }
}
