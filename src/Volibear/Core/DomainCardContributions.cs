using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Four exact card-effect contributions, not affliction writes or card generation.
/// Actual native command commits establish provenance; tiny virtual overrides are not patched.</summary>
public static class DomainCardContributions
{
    private const string HarmonyId = "Volibear.DomainCardContributions";
    private static readonly object InstallLock = new();
    private static bool _installed;
    private static int _generation;
    private static ConditionalWeakTable<PowerModel, Origin> _origins = new();
    private static readonly Dictionary<MethodBase, string> Sites = new();
    [Flags] internal enum Cause { Unknown = 1, Enemy = 2, Player = 4 }

    // Native shared amounts stay untouched. Tangled uses a positive-cost counterfactual;
    // the other three predicates ignore Amount and combine independent causes by OR.
    internal sealed class StackReceipt(Cause cause, int amount)
    {
        private readonly DomainCardContributionLedger _scalar = new(amount, cause == Cause.Enemy);
        internal Cause Causes { get; private set; } = cause;
        internal int ExpectedAmount => _scalar.Actual;
        internal int EffectiveAmount => _scalar.Effective;
        internal bool HasRetainedPredicate => (Causes & (Cause.Player | Cause.Unknown)) != 0;
        internal string State => (Causes & Cause.Unknown) != 0 ? "unknown" : Causes switch
        { Cause.Enemy => "enemy", Cause.Player => "player", _ => "mixed" };
        internal void Change(Cause addedCause, int before, int after)
        {
            if (before != ExpectedAmount) Causes |= Cause.Unknown;
            if (after > before) Causes |= addedCause;
            _scalar.Change(before, after, addedCause == Cause.Enemy);
        }
        internal void Check(int actual)
        {
            if (_scalar.Reconcile(actual)) Causes |= Cause.Unknown;
        }
    }
    private sealed class Origin(ICombatState combat, Creature owner, Cause cause, int amount, int generation)
    {
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Owner = owner;
        internal readonly int Generation = generation;
        internal readonly StackReceipt Receipt = new(cause, amount);
        internal readonly HashSet<string> EnemyIds = new();
        internal readonly HashSet<Creature> EnemySources = new(ReferenceEqualityComparer.Instance);
        internal bool ReportedUnknown;
    }
    public sealed record SourceAudit(string State, int ExpectedAmount, int ActualAmount,
        bool SameCombat, bool SameOwner, string[] EnemyIds, string UnsupportedReason,
        int RetainedAmount = 0, bool RetainedPredicate = false);

    private static bool Whitelisted(PowerModel power) => power.GetType() == typeof(HexPower) ||
        power.GetType() == typeof(TangledPower) || power.GetType() == typeof(SmoggyPower) || power.GetType() == typeof(RingingPower);
    private static Cause Classify(ICombatState combat, Creature? applier, CardModel? card)
    {
        if (applier is null || !ReferenceEquals(combat, applier.CombatState) || !combat.ContainsCreature(applier)) return Cause.Unknown;
        if (applier.IsEnemy && !applier.IsPlayer && card is null && applier.CombatId is not null) return Cause.Enemy;
        if (applier.IsPlayer && (card is null || ReferenceEquals(card.Owner.Creature, applier))) return Cause.Player;
        return Cause.Unknown;
    }
    private static void RememberEnemy(Origin origin, Cause cause, Creature? source)
    {
        if (cause != Cause.Enemy || source is null) return;
        origin.EnemySources.Add(source);
        if (source.CombatId is { } id) origin.EnemyIds.Add(id.ToString()!);
    }
    private static void ApplyCommit(PowerModel power, Creature target, decimal amount, bool silent, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        DomainEnemyStatusContributions.AppliedTainted(power, target, amount, applier, card, context);
        DomainPlayerDebuffContributions.Applied(power, target, amount, applier, card, context);
        DomainPlayerStatContributions.Applied(power, target, amount, applier, card, context);
        // Prepare provenance before SetAmount/ApplyPowerInternal invoke synchronous observers.
        if (Whitelisted(power) && target.IsPlayer && target.CombatState is { } combat && amount != 0m)
        {
            var cause = Classify(combat, applier, card);
            var origin = new Origin(combat, target, cause, Math.Clamp((int)amount, -999999999, 999999999), _generation);
            RememberEnemy(origin, cause, applier);
            _origins.Remove(power); _origins.Add(power, origin);
        }
        power.ApplyInternal(target, amount, silent);
    }
    private static void AmountCommit(PowerModel power, int amount, bool silent, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        DomainEnemyStatusContributions.TaintedAmountChanged(power, amount, applier, card, context);
        DomainPlayerDebuffContributions.AmountChanged(power, amount, applier, card, context);
        DomainPlayerStatContributions.AmountChanged(power, amount, applier, card, context);
        Origin? changed = null;
        if (Whitelisted(power) && power.Owner.IsPlayer && power.Owner.CombatState is { } combat)
        {
            if (!_origins.TryGetValue(power, out var origin) || origin.Generation != _generation ||
                !ReferenceEquals(origin.Owner, power.Owner) || !ReferenceEquals(origin.Combat, combat))
            {
                // Observe a new enemy addition even when the prior value came from
                // another mod or restoration. Only the prior value stays unattributed.
                origin = new Origin(combat, power.Owner, Cause.Unknown, power.Amount, _generation);
                _origins.Remove(power); _origins.Add(power, origin);
            }
            changed = origin;
            var cause = Classify(origin.Combat, applier, card);
            // A previously proven actual argument remains attributable after departure, but never after reuse in another combat.
            if (cause == Cause.Unknown && card is null && applier is not null && applier.IsEnemy && !applier.IsPlayer &&
                origin.EnemySources.Contains(applier) && (applier.CombatState is null || ReferenceEquals(applier.CombatState, origin.Combat)))
                cause = Cause.Enemy;
            var actual = Math.Clamp(amount, -999999999, 999999999);
            if (!ReferenceEquals(power.Owner, origin.Owner) || !ReferenceEquals(power.Owner.CombatState, origin.Combat)) cause = Cause.Unknown;
            if (actual > power.Amount) RememberEnemy(origin, cause, applier);
            origin.Receipt.Change(cause, power.Amount, actual);
        }
        // Native negative ticks/removal are never filtered. Unknown/untracked mutations never gain enemy attribution.
        power.SetAmount(amount, silent);
        if (changed is not null) ReportUnknown(power, changed);
    }
    private static void ReportUnknown(PowerModel power, Origin origin)
    {
        if (origin.Receipt.State != "unknown" || origin.ReportedUnknown) return;
        origin.ReportedUnknown = true;
        Godot.GD.Print("[Volibear] DOMAIN_CARD_SOURCE_UNATTRIBUTED " + power.GetType().Name +
            " unobserved contributions retained; observed enemy cost additions remain isolated");
    }
    public static SourceAudit Audit(PowerModel power)
    {
        if (!_origins.TryGetValue(power, out var origin) || origin.Generation != _generation)
            return new("untracked", power.Amount, power.Amount, false, false, [], "no-observed-native-commit");
        origin.Receipt.Check(power.Amount);
        ReportUnknown(power, origin);
        var state = origin.Receipt.State;
        return new(state, origin.Receipt.ExpectedAmount, power.Amount,
            ReferenceEquals(origin.Combat, power.Owner.CombatState), ReferenceEquals(origin.Owner, power.Owner),
            origin.EnemyIds.Order().ToArray(), state == "unknown" ? "unattributed-contributions-preserved" : "",
            origin.Receipt.EffectiveAmount, origin.Receipt.HasRetainedPredicate);
    }
    private static Origin? ActiveOrigin(PowerModel power, CardModel card)
    {
        if (!_origins.TryGetValue(power, out var origin) || origin.Generation != _generation) return null;
        origin.Receipt.Check(power.Amount);
        ReportUnknown(power, origin);
        return origin.Owner.IsPlayer &&
            ReferenceEquals(power.Owner, origin.Owner) && ReferenceEquals(card.Owner.Creature, origin.Owner) &&
            ReferenceEquals(origin.Owner.CombatState, origin.Combat) && origin.Combat.ContainsCreature(origin.Owner) &&
            origin.Owner.Powers.Contains(power) && DomainEnemyEffects.ActiveFor(origin.Combat) ? origin : null;
        // The original enemy need NOT remain attached/alive. Its same-combat cause was captured at commit.
    }
    private static bool Suppress(PowerModel power, CardModel card) =>
        DomainSelfDebuffEffects.IsSuppressed(power) ||
        ActiveOrigin(power, card) is { } origin && !origin.Receipt.HasRetainedPredicate;
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool KeywordsContribution(AbstractModel model, CardModel card, ISet<CardKeyword> keywords)
    {
        if (model is HexPower hex && Suppress(hex, card))
        {
            if (card.Affliction is MegaCrit.Sts2.Core.Models.Afflictions.Hexed && !keywords.Contains(CardKeyword.Ethereal))
                CaptureCardSuppression(hex);
            return false;
        }
        return model.TryModifyKeywordsInCombat(card, keywords);
    }
    private static void CaptureCardSuppression(PowerModel power)
    {
        try
        {
            if (_origins.TryGetValue(power, out var origin))
                foreach (var enemy in origin.EnemySources) Volibear.Presentation.PowerPresentationDomainScalars.Capture(enemy, power);
        }
        catch { }
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool CostContribution(AbstractModel model, CardModel card, decimal original, out decimal modified)
    {
        if (model is PowerModel power && DomainSelfDebuffEffects.IsSuppressed(power))
        {
            modified = original;
            return false;
        }
        bool changed = model.TryModifyEnergyCostInCombat(card, original, out modified);
        if (changed && model is TangledPower tangled && tangled.Amount > 0 &&
            ActiveOrigin(tangled, card) is { } origin && card.Affliction is MegaCrit.Sts2.Core.Models.Afflictions.Entangled)
        {
            int suppressed = tangled.Amount - origin.Receipt.EffectiveAmount;
            if (suppressed > 0)
            {
                // Subtract only this observed positive enemy part. Foreign modifiers on
                // the native contribution and independent player cost additions survive.
                modified -= suppressed;
                CaptureCardSuppression(tangled);
                return modified != original;
            }
        }
        return changed;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool PlayContribution(AbstractModel model, CardModel card, AutoPlayType autoPlayType)
    {
        if ((model is PowerModel power && DomainSelfDebuffEffects.IsSuppressed(power)) ||
            (model is SmoggyPower smog && Suppress(smog, card)) || (model is RingingPower ringing && Suppress(ringing, card)))
        {
            // These pinned native predicates only read their per-turn counter/card affliction.
            // Evaluate for presentation only inside the actual action's admitted ShouldPlay call.
            try
            {
                if (Volibear.Presentation.PowerPresentationDomainScalars.IsCapturing && !model.ShouldPlay(card, autoPlayType))
                    CaptureCardSuppression((PowerModel)model);
            }
            catch { }
            return true;
        }
        return model.ShouldPlay(card, autoPlayType);
    }

    public static void Reset() { _generation++; _origins = new(); }
    private static MethodInfo Method(Type owner, string name, params Type[] parameters) =>
        owner.GetMethod(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly,
            null, parameters, null) ?? throw new MissingMethodException(owner.FullName, name);
    private static MethodInfo Handler(string name) => typeof(DomainCardContributions).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)
        ?? throw new MissingMethodException(name);
    private static MethodInfo Machine(MethodInfo native) => Method(native.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Expected actual native async state machine: " + native), "MoveNext");
    private static MethodInfo ApplyNative() => Method(typeof(PowerCmd), nameof(PowerCmd.Apply), typeof(PlayerChoiceContext), typeof(PowerModel),
        typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool));
    private static MethodInfo ModifyNative() => Method(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount), typeof(PlayerChoiceContext), typeof(PowerModel),
        typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool));
    private static void Discover()
    {
        var reset = Method(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool));
        if (reset.IsStatic || reset.ReturnType != typeof(void)) throw new InvalidOperationException("Native reset signature changed");
        Sites.Clear();
        Sites.Add(Method(typeof(Hook), nameof(Hook.ModifyKeywordsInCombat), typeof(ICombatState), typeof(CardModel), typeof(ISet<CardKeyword>)), "keywords");
        Sites.Add(Method(typeof(Hook), nameof(Hook.ModifyEnergyCostInCombat), typeof(ICombatState), typeof(CardModel), typeof(decimal)), "cost");
        Sites.Add(Method(typeof(Hook), nameof(Hook.ShouldPlay), typeof(ICombatState), typeof(CardModel), typeof(AbstractModel).MakeByRefType(), typeof(AutoPlayType)), "play");
        Sites.Add(Machine(ApplyNative()), "apply"); Sites.Add(Machine(ModifyNative()), "amount");
    }
    public sealed record IlSite(string Method, string Kind, int NativeCalls, int ReplacedCalls);
    public static IlSite[] VerifyNativeIl()
    {
        lock (InstallLock)
        {
            Discover();
            return Sites.Select(pair =>
            {
                var before = PatchProcessor.GetOriginalInstructions(pair.Key).ToList();
                var after = Rewrite(before, pair.Key).ToList();
                var wrapper = Replacement(pair.Value).Wrapper;
                int count = after.Count(c => c.Calls(wrapper));
                if (count != 1) throw new InvalidOperationException("Exact native contribution/commit wrapper count changed");
                return new IlSite(pair.Key.DeclaringType!.FullName + "." + pair.Key.Name, pair.Value, 1, count);
            }).ToArray();
        }
    }
    private static (MethodInfo Native, MethodInfo Wrapper) Replacement(string kind) => kind switch
    {
        "keywords" => (Method(typeof(AbstractModel), nameof(AbstractModel.TryModifyKeywordsInCombat), typeof(CardModel), typeof(ISet<CardKeyword>)), Handler(nameof(KeywordsContribution))),
        "cost" => (Method(typeof(AbstractModel), nameof(AbstractModel.TryModifyEnergyCostInCombat), typeof(CardModel), typeof(decimal), typeof(decimal).MakeByRefType()), Handler(nameof(CostContribution))),
        "play" => (Method(typeof(AbstractModel), nameof(AbstractModel.ShouldPlay), typeof(CardModel), typeof(AutoPlayType)), Handler(nameof(PlayContribution))),
        "apply" => (Method(typeof(PowerModel), nameof(PowerModel.ApplyInternal), typeof(Creature), typeof(decimal), typeof(bool)), Handler(nameof(ApplyCommit))),
        "amount" => (Method(typeof(PowerModel), nameof(PowerModel.SetAmount), typeof(int), typeof(bool)), Handler(nameof(AmountCommit))),
        _ => throw new InvalidOperationException("Unrecognized exact IL site")
    };
    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        if (!Sites.TryGetValue(__originalMethod, out var kind)) throw new InvalidOperationException("Unknown native site");
        var (native, wrapper) = Replacement(kind);
        var sourceParameters = new[] { native.DeclaringType! }.Concat(native.GetParameters().Select(p => p.ParameterType)).ToList();
        bool commit = kind is "apply" or "amount";
        if (commit) sourceParameters.AddRange([typeof(Creature), typeof(CardModel), typeof(PlayerChoiceContext)]);
        if (wrapper.ReturnType != native.ReturnType || !sourceParameters.SequenceEqual(wrapper.GetParameters().Select(p => p.ParameterType)))
            throw new InvalidOperationException("Native contribution/commit signature drift: " + native);
        FieldInfo? applier = null, card = null, context = null;
        if (commit)
        {
            applier = __originalMethod.DeclaringType!.GetField("applier", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            card = __originalMethod.DeclaringType!.GetField("cardSource", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            context = __originalMethod.DeclaringType!.GetField("choiceContext", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (applier?.FieldType != typeof(Creature) || card?.FieldType != typeof(CardModel) || context?.FieldType != typeof(PlayerChoiceContext))
                throw new InvalidOperationException("Native async provenance fields changed");
        }
        int matched = 0;
        var output = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.Calls(native))
            {
                matched++;
                if (commit)
                {
                    // Labels must target argument loading, not jump over the provenance arguments.
                    if (instruction.blocks.Count != 0) throw new InvalidOperationException("Exception boundary at native commit call");
                    var load = new CodeInstruction(OpCodes.Ldarg_0); load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                    output.Add(load); output.Add(new CodeInstruction(OpCodes.Ldfld, applier));
                    output.Add(new CodeInstruction(OpCodes.Ldarg_0)); output.Add(new CodeInstruction(OpCodes.Ldfld, card));
                    output.Add(new CodeInstruction(OpCodes.Ldarg_0)); output.Add(new CodeInstruction(OpCodes.Ldfld, context));
                }
                instruction.opcode = OpCodes.Call; instruction.operand = wrapper;
            }
            output.Add(instruction);
        }
        if (matched != 1) throw new InvalidOperationException($"Expected one {kind} native call, found {matched}");
        return output;
    }
    public static void Install()
    {
        lock (InstallLock)
        {
            if (_installed) return;
            VerifyNativeIl();
            var harmony = new Harmony(HarmonyId);
            try
            {
                foreach (var site in Sites.Keys) harmony.Patch(site, transpiler: new HarmonyMethod(Handler(nameof(Rewrite)))
                { after = ["Volibear.DomainPassiveEffects"], priority = Priority.Last });
                harmony.Patch(Method(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool)), prefix: new HarmonyMethod(typeof(DomainCardContributions), nameof(Reset)));
                _installed = true;
            }
            catch { harmony.UnpatchAll(HarmonyId); Reset(); throw; }
        }
    }
}
