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

    // No contribution allocation is invented for mixed stacks. Even Single powers really add amounts.
    internal sealed class StackReceipt(Cause cause, int amount)
    {
        internal Cause Causes { get; private set; } = cause;
        internal int ExpectedAmount { get; private set; } = amount;
        internal string State => (Causes & Cause.Unknown) != 0 ? "unknown" : Causes switch
        { Cause.Enemy => "enemy", Cause.Player => "player", _ => "mixed" };
        internal void Change(Cause addedCause, int before, int after)
        {
            if (before != ExpectedAmount) Causes |= Cause.Unknown;
            if (after > before) Causes |= addedCause;
            ExpectedAmount = after;
        }
        internal void Check(int actual)
        {
            if (actual != ExpectedAmount) { Causes |= Cause.Unknown; ExpectedAmount = actual; }
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
        internal string ReportedUnsupported = "";
    }
    public sealed record SourceAudit(string State, int ExpectedAmount, int ActualAmount,
        bool SameCombat, bool SameOwner, string[] EnemyIds, string UnsupportedReason);

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
        if (Whitelisted(power) && _origins.TryGetValue(power, out var origin))
        {
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
        if (changed is not null) ReportUnsupported(power, changed);
    }
    private static void ReportUnsupported(PowerModel power, Origin origin)
    {
        string state = origin.Receipt.State;
        if (state is not ("mixed" or "unknown") || origin.ReportedUnsupported == state) return;
        origin.ReportedUnsupported = state;
        Godot.GD.Print("[Volibear] DOMAIN_CARD_SOURCE_UNSUPPORTED " + power.GetType().Name + " " + state +
            " contributor allocation unproven; native contribution retained");
    }
    public static SourceAudit Audit(PowerModel power)
    {
        if (!_origins.TryGetValue(power, out var origin) || origin.Generation != _generation)
            return new("untracked", power.Amount, power.Amount, false, false, [], "no-observed-native-commit");
        origin.Receipt.Check(power.Amount);
        ReportUnsupported(power, origin);
        var state = origin.Receipt.State;
        return new(state, origin.Receipt.ExpectedAmount, power.Amount,
            ReferenceEquals(origin.Combat, power.Owner.CombatState), ReferenceEquals(origin.Owner, power.Owner),
            origin.EnemyIds.Order().ToArray(), state is "mixed" or "unknown" ? "contributor-allocation-not-proven;native-contribution-preserved" : "");
    }
    private static bool Suppress(PowerModel power, CardModel card)
    {
        if (!_origins.TryGetValue(power, out var origin) || origin.Generation != _generation) return false;
        origin.Receipt.Check(power.Amount);
        ReportUnsupported(power, origin);
        // Tangled's negative cost delta is favorable to the player; the other three predicates ignore Amount entirely.
        return origin.Receipt.State == "enemy" && (power is not TangledPower || power.Amount > 0) && origin.Owner.IsPlayer &&
            ReferenceEquals(power.Owner, origin.Owner) && ReferenceEquals(card.Owner.Creature, origin.Owner) &&
            ReferenceEquals(origin.Owner.CombatState, origin.Combat) && origin.Combat.ContainsCreature(origin.Owner) &&
            origin.Owner.Powers.Contains(power) && DomainEnemyEffects.ActiveFor(origin.Combat);
        // The original enemy need NOT remain attached/alive. Its same-combat cause was captured at commit.
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool KeywordsContribution(AbstractModel model, CardModel card, ISet<CardKeyword> keywords) =>
        model is HexPower hex && Suppress(hex, card) ? false : model.TryModifyKeywordsInCombat(card, keywords);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool CostContribution(AbstractModel model, CardModel card, decimal original, out decimal modified)
    {
        if (model is TangledPower tangled && Suppress(tangled, card)) { modified = original; return false; }
        return model.TryModifyEnergyCostInCombat(card, original, out modified);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool PlayContribution(AbstractModel model, CardModel card, AutoPlayType autoPlayType) =>
        (model is SmoggyPower smog && Suppress(smog, card)) || (model is RingingPower ringing && Suppress(ringing, card)) ||
        model.ShouldPlay(card, autoPlayType);

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
