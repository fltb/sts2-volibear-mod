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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Afflictions;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

public static partial class DomainEnemyStatusContributions
{
    private sealed record SparkTicket(VitalSparkPower Source, Creature Target, ICombatState Combat, int Generation);
    private sealed class TaintedReceipt(ICombatState combat, Creature receiver, int actual, int retained)
    {
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Receiver = receiver;
        internal int Actual = actual;
        internal int Retained = retained;
        internal readonly HashSet<Creature> PresentationSources = [];
    }
    private static ConditionalWeakTable<PlayerChoiceContext, SparkTicket> _sparkTickets = new();
    private static ConditionalWeakTable<PowerModel, TaintedReceipt> _taintedReceipts = new();

    private static void InstallStatusPowerEffects(Harmony harmony)
    {
        foreach (var (type, name) in new[]
        {
            (typeof(GalvanicPower), "BeforeCombatStart"), (typeof(GalvanicPower), "AfterCardEnteredCombat"),
            (typeof(GalvanicPower), "AfterCardPlayed"),
            (typeof(VitalSparkPower), "BeforeCombatStart"), (typeof(VitalSparkPower), "AfterCardEnteredCombat"),
            (typeof(VitalSparkPower), "AfterCardPlayed"),
            (typeof(PaperCutsPower), "AfterDamageGiven")
        }) harmony.Patch(MoveNext(Required(type, name)), transpiler: Handler(nameof(StatusPowerCallsite)));
        // Rewrite the exact Amount contribution in Tainted, not its end-of-enemy-turn removal.
        harmony.Patch(Required(typeof(TaintedPower), nameof(TaintedPower.ModifyDamageAdditive)),
            transpiler: Handler(nameof(TaintedDamageContribution)));
    }

    private static IEnumerable<CodeInstruction> StatusPowerCallsite(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var source = __originalMethod.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Single(field => field.Name == "<>4__this" && typeof(PowerModel).IsAssignableFrom(field.FieldType));
        int matched = 0;
        foreach (var instruction in instructions)
        {
            MethodInfo? replacement = null;
            if (instruction.operand is MethodInfo method)
            {
                if (method.DeclaringType == typeof(CardCmd) && method.Name == nameof(CardCmd.Afflict) && method.IsGenericMethod &&
                    (method.GetGenericArguments()[0] == typeof(Galvanized) || method.GetGenericArguments()[0] == typeof(Tainted)))
                    replacement = Required(typeof(DomainEnemyStatusContributions), nameof(EnemyAfflict)).MakeGenericMethod(method.GetGenericArguments());
                else if (source.FieldType == typeof(GalvanicPower) && method.DeclaringType == typeof(CreatureCmd) && method.Name == nameof(CreatureCmd.Damage))
                    replacement = Required(typeof(DomainEnemyStatusContributions), nameof(GalvanicDamage));
                else if (source.FieldType == typeof(VitalSparkPower) && method.DeclaringType == typeof(PowerCmd) &&
                    method.Name == nameof(PowerCmd.Apply) && method.IsGenericMethod && method.GetGenericArguments()[0] == typeof(TaintedPower))
                    replacement = Required(typeof(DomainEnemyStatusContributions), nameof(SparkApply));
                else if (source.FieldType == typeof(PaperCutsPower) && method.DeclaringType == typeof(CreatureCmd) && method.Name == nameof(CreatureCmd.LoseMaxHp))
                    replacement = Required(typeof(DomainEnemyStatusContributions), nameof(PaperCutMaxHp));
                if (replacement is not null && !method.GetParameters().Select(p => p.ParameterType)
                    .SequenceEqual(replacement.GetParameters().SkipLast(1).Select(p => p.ParameterType)))
                    throw new InvalidOperationException("Enemy status contribution signature changed: " + method);
            }
            if (replacement is null) { yield return instruction; continue; }
            matched++;
            var load = new CodeInstruction(OpCodes.Ldarg_0);
            load.labels.AddRange(instruction.labels); load.blocks.AddRange(instruction.blocks);
            yield return load;
            yield return new CodeInstruction(OpCodes.Ldfld, source);
            yield return new CodeInstruction(OpCodes.Call, replacement);
        }
        if (matched != 1) throw new InvalidOperationException($"Enemy status power contribution count changed: {__originalMethod}: {matched}");
    }

    private static bool SuppressPowerContribution(PowerModel source, Creature receiver)
    {
        bool suppressed = EnemySource(source, receiver, out var enemy) && DomainEnemyEffects.ProtectsPlayer(receiver);
        // Only concrete afflict/damage/max-HP execution calls use this gate.
        if (suppressed) Volibear.Presentation.PowerPresentationDomain.Suppressed(enemy, source, sourceCombat: receiver.CombatState);
        return suppressed;
    }
    private static Task<T?> EnemyAfflict<T>(CardModel card, decimal amount, PowerModel source) where T : AfflictionModel =>
        SuppressPowerContribution(source, card.Owner.Creature) ? Task.FromResult<T?>(null) : CardCmd.Afflict<T>(card, amount);
#if STS2_BETA
    // PBE's Galvanic callsite dropped the dealer argument and carries the card play.
    private static Task<IEnumerable<DamageResult>> GalvanicDamage(PlayerChoiceContext context, Creature target, decimal amount,
        ValueProp props, CardModel? card, CardPlay? play, GalvanicPower source) =>
        SuppressPowerContribution(source, target) ? Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>()) :
            CreatureCmd.Damage(context, target, amount, props, card, play);
#else
    private static Task<IEnumerable<DamageResult>> GalvanicDamage(PlayerChoiceContext context, Creature target, decimal amount,
        ValueProp props, Creature? dealer, CardModel? card, GalvanicPower source) =>
        SuppressPowerContribution(source, target) ? Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>()) :
            CreatureCmd.Damage(context, target, amount, props, dealer, card);
#endif
    private static Task PaperCutMaxHp(PlayerChoiceContext context, Creature target, decimal amount,
#if STS2_BETA
        CardModel? fromCard,
#else
        bool fromCard,
#endif
        PaperCutsPower source) =>
        SuppressPowerContribution(source, target) ? Task.CompletedTask : CreatureCmd.LoseMaxHp(context, target, amount, fromCard);

    private static async Task<TaintedPower?> SparkApply(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, VitalSparkPower source)
    {
        // Keep the actual native null applier/card and original choice context. The
        // exact callsite establishes a ticket, not a global null-applier heuristic.
        bool enemy = applier is null && card is null && EnemySource(source, target, out _);
        _sparkTickets.TryGetValue(context, out var previous);
        _sparkTickets.Remove(context);
        if (enemy) _sparkTickets.Add(context, new SparkTicket(source, target, target.CombatState!, _generation));
        context.PushModel(source);
        try { return await PowerCmd.Apply<TaintedPower>(context, target, amount, applier, card, silent); }
        finally
        {
            context.PopModel(source);
            _sparkTickets.Remove(context);
            if (previous is not null && previous.Generation == _generation) _sparkTickets.Add(context, previous);
        }
    }

    private static bool EnemyTainted(Creature target, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (!target.IsPlayer || target.CombatState is not { } combat || card is not null) return false;
        if (applier is not null) return applier.IsEnemy && !applier.IsPlayer && ReferenceEquals(applier.CombatState, combat) && combat.ContainsCreature(applier);
        return _sparkTickets.TryGetValue(context, out var ticket) && ticket.Generation == _generation &&
            ReferenceEquals(ticket.Target, target) && ReferenceEquals(ticket.Combat, combat) &&
            ReferenceEquals(context.LastInvolvedModel, ticket.Source);
    }

    // Shared PowerCmd precommit/commit adapters call these, just like the finite
    // Weak/Frail/stat adapters. No second patch competes for those mutation sites.
    internal static bool ShouldCancelTainted(PowerModel power, Creature target, decimal delta,
        Creature? applier, CardModel? card, PlayerChoiceContext context) => power is TaintedPower && delta > 0m &&
        EnemyTainted(target, applier, card, context) && DomainEnemyEffects.ProtectsPlayer(target);
    internal static void AppliedTainted(PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (power is not TaintedPower || !target.IsPlayer || target.CombatState is not { } combat || amount == 0m) return;
        int actual = Math.Clamp((int)amount, -999999999, 999999999);
        _taintedReceipts.Remove(power);
        _taintedReceipts.Add(power, new TaintedReceipt(combat, target, actual, EnemyTainted(target, applier, card, context) ? 0 : actual));
        RememberTaintedSource(power, target, applier, card, context);
    }
    internal static void TaintedAmountChanged(PowerModel power, int amount,
        Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (power is not TaintedPower || !power.Owner.IsPlayer || power.Owner.CombatState is not { } combat) return;
        if (!_taintedReceipts.TryGetValue(power, out var receipt) || !ReferenceEquals(receipt.Combat, combat) || !ReferenceEquals(receipt.Receiver, power.Owner))
        {
            receipt = new TaintedReceipt(combat, power.Owner, power.Amount, power.Amount);
            _taintedReceipts.Remove(power); _taintedReceipts.Add(power, receipt);
        }
        ReconcileTainted(power, receipt);
        int next = Math.Clamp(amount, -999999999, 999999999), delta = next - receipt.Actual;
        if (delta < 0) receipt.Retained = Math.Max(0, receipt.Retained + delta);
        else if (delta > 0 && !EnemyTainted(power.Owner, applier, card, context)) receipt.Retained = Math.Min(next, receipt.Retained + delta);
        receipt.Actual = next;
        if (delta > 0) RememberTaintedSource(power, power.Owner, applier, card, context);
    }
    private static void RememberTaintedSource(PowerModel power, Creature target, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        try
        {
            if (!EnemyTainted(target, applier, card, context) || !_taintedReceipts.TryGetValue(power, out var receipt)) return;
            var enemy = applier;
            if (enemy is null && _sparkTickets.TryGetValue(context, out var ticket)) enemy = ticket.Source.Owner;
            if (enemy is not null) receipt.PresentationSources.Add(enemy);
        }
        catch { }
    }
    private static void ReconcileTainted(PowerModel power, TaintedReceipt receipt)
    {
        if (power.Amount == receipt.Actual) return;
        receipt.Retained = Math.Clamp(receipt.Retained + power.Amount - receipt.Actual, 0, Math.Max(0, power.Amount));
        receipt.Actual = power.Amount;
    }
    private static int EffectiveTaintedAmount(PowerModel power)
    {
        if (!_taintedReceipts.TryGetValue(power, out var receipt) || !ReferenceEquals(receipt.Receiver, power.Owner) ||
            !ReferenceEquals(receipt.Combat, power.Owner.CombatState) || !power.Owner.Powers.Contains(power)) return power.Amount;
        ReconcileTainted(power, receipt);
        bool domain = DomainEnemyEffects.ProtectsPlayer(power.Owner);
        try
        {
            if (domain && receipt.Retained < power.Amount)
                foreach (var enemy in receipt.PresentationSources) Volibear.Presentation.PowerPresentationDomainScalars.Capture(enemy, power);
        }
        catch { }
        return domain ? receipt.Retained : power.Amount;
    }
    private static IEnumerable<CodeInstruction> TaintedDamageContribution(IEnumerable<CodeInstruction> instructions)
    {
        var getter = AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Amount));
        int matched = 0;
        foreach (var instruction in instructions)
        {
            if (instruction.Calls(getter))
            {
                matched++; instruction.opcode = OpCodes.Call;
                instruction.operand = Required(typeof(DomainEnemyStatusContributions), nameof(EffectiveTaintedAmount));
            }
            yield return instruction;
        }
        if (matched != 1) throw new InvalidOperationException($"Tainted additive contribution changed: {matched}");
    }
    private static void ResetStatusPowerEffects() { _sparkTickets = new(); _taintedReceipts = new(); }
}
