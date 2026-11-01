using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using Volibear.Content;

namespace Volibear.Core;

/// <summary>Only cards with their own target-dependent cost implement this marker.</summary>
public interface ITargetCostCard { }

/// <summary>One native persistent power owns one ledger. Changing its Amount affects
/// subsequent grants, never retroactively multiplies discounts already granted.</summary>
public sealed class TargetDiscountLedger<T> where T : class
{
    private readonly Dictionary<T, int> _discounts = new(ReferenceEqualityComparer.Instance);
    private readonly HashSet<long> _recorded = [];
    private int _turn = int.MinValue;
    private long? _lastPlay;
    private T? _lastTarget;
    private int _lastAmount;

    public void Record(int turn, long play, T target, int amount)
    {
        if (turn != _turn)
        { _turn = turn; _discounts.Clear(); _recorded.Clear(); _lastPlay = null; _lastTarget = null; _lastAmount = 0; }
        if (!_recorded.Add(play)) return;
        amount = Math.Max(0, amount);
        _discounts[target] = checked(_discounts.GetValueOrDefault(target) + amount);
        _lastPlay = play; _lastTarget = target; _lastAmount = amount;
    }

    public int Read(int turn, T target, long? queryingPlay = null)
    {
        if (turn != _turn) return 0;
        var own = queryingPlay.HasValue && queryingPlay == _lastPlay && ReferenceEquals(target, _lastTarget) ? _lastAmount : 0;
        return Math.Max(0, _discounts.GetValueOrDefault(target) - own);
    }
}

/// <summary>
/// Native targeting bridge: the native PlayCardAction resolves its target before
/// CanPlay and SpendResources, but sets CardModel.CurrentTarget only AFTER payment.
/// This bridge passes the actual hoisted resolved target to the two native calls.
/// It never replaces payment, runs a card executor or refunds post-paid energy.
/// </summary>
public static class TargetCosts
{
    private sealed record Query(CardModel Card, Creature? Target);
    private sealed class Lease(Query? previous) : IDisposable
    {
        public void Dispose() => Current.Value = previous;
    }
    private static readonly AsyncLocal<Query?> Current = new();
    private static readonly Dictionary<Creature, IDisposable> _subscriptions = new(ReferenceEqualityComparer.Instance);
    private static bool _installed;
    private static readonly FieldInfo PreviewTarget = AccessTools.Field(typeof(NCard), "_previewTarget")
        ?? throw new MissingFieldException("NCard._previewTarget");

    private static Lease Enter(CardModel card, Creature? target)
    { var previous = Current.Value; Current.Value = new(card, target); return new(previous); }

    /// <summary>No guessed CurrentTarget fallback. Missing target context means no
    /// target discount; UI affordability establishes an explicit valid target first.</summary>
    public static Creature? TargetFor(CardModel card) => Current.Value is { } query && ReferenceEquals(query.Card, card)
        ? query.Target : null;

    private static bool Scoped(CardModel card) => Current.Value is { } query && ReferenceEquals(query.Card, card);
    private static bool Sensitive(CardModel card) => !card.IsCanonical && card.Owner?.PlayerCombatState is not null &&
        card.TargetType == TargetType.AnyEnemy && !card.EnergyCost.CostsX &&
        (card is ITargetCostCard ||
         (card.Type == CardType.Attack && card.Owner.Creature.HasPower<EndlessHuntPower>()));

    public static int CostFor(CardModel card, Creature? target)
    {
        using var scope = Enter(card, target);
        return card.EnergyCost.GetWithModifiers(CostModifiers.All);
    }

    private static Creature? CheapestValidTarget(CardModel card)
    {
        Creature? best = null;
        var bestCost = int.MaxValue;
        foreach (var target in card.Owner.Creature.CombatState?.Enemies ?? [])
        {
            if (!card.IsValidTarget(target)) continue;
            var cost = CostFor(card, target);
            if (cost < bestCost) { best = target; bestCost = cost; }
        }
        return best;
    }

    // Called synchronously around each exact native callsite. SpendResources reads
    // GetAmountToSpend before its first await in 0.107.1; its native initial MoveNext
    // therefore sees this target. The caller's scope is restored even on exceptions.
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool CanPlayResolved(CardModel card, out UnplayableReason reason, out AbstractModel? preventer, Creature? target)
    {
        using var scope = Enter(card, target);
        return card.CanPlay(out reason, out preventer);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task<(int, int)> SpendResolved(CardModel card, Creature? target)
    {
        using var scope = Enter(card, target);
        var presentation = CostPresentationReceipts.Capture(card);
        var original = card.SpendResources();
        CostPresentationReceipts.ObserveNativePayment(presentation, original);
        return original;
    }

    private static void BeforeTargeting(CardModel __instance, Creature? target, out Lease? __state)
    { __state = Sensitive(__instance) ? Enter(__instance, target) : null; }
    private static void BeforeCanPlay(CardModel __instance, out Lease? __state)
    {
        __state = null;
        if (Sensitive(__instance) && !Scoped(__instance))
            __state = Enter(__instance, CheapestValidTarget(__instance));
    }
    private static void BeforeVisuals(NCard __instance, out Lease? __state)
    {
        __state = null;
        var card = __instance.Model;
        if (card is null || !Sensitive(card) || Scoped(card)) return;
        var target = PreviewTarget.GetValue(__instance) as Creature;
        __state = Enter(card, target ?? CheapestValidTarget(card));
    }
    private static Exception? Restore(Exception? __exception, Lease? __state)
    { __state?.Dispose(); return __exception; }

    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony("Volibear.TargetCosts");
        try
        {
            VerifyNativePaymentTiming();
            var action = AccessTools.Method(typeof(PlayCardAction), "ExecuteAction")
                ?? throw new MissingMethodException("PlayCardAction.ExecuteAction");
            var machine = action.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
                ?? throw new InvalidOperationException("PlayCardAction lost native async state machine.");
            harmony.Patch(AccessTools.Method(machine, "MoveNext"), transpiler: Handler(nameof(ResolvedTargetCallsites)));
            harmony.Patch(AccessTools.Method(typeof(CardModel), nameof(CardModel.CanPlayTargeting), [typeof(Creature)]),
                prefix: Handler(nameof(BeforeTargeting)), finalizer: Handler(nameof(Restore)));
            harmony.Patch(AccessTools.Method(typeof(CardModel), nameof(CardModel.CanPlay),
                [typeof(UnplayableReason).MakeByRefType(), typeof(AbstractModel).MakeByRefType()]),
                prefix: Handler(nameof(BeforeCanPlay)), finalizer: Handler(nameof(Restore)));
            foreach (var method in new[] { "UpdateVisuals", "UpdateEnergyCostVisuals", "UpdateEnergyCostColor", "UpdateStarCostVisuals" })
                harmony.Patch(AccessTools.Method(typeof(NCard), method) ?? throw new MissingMethodException("NCard", method),
                    prefix: Handler(nameof(BeforeVisuals)), finalizer: Handler(nameof(Restore)));
            harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]), prefix: Handler(nameof(Reset)));
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            CombatManager.Instance.TurnStarted += OnTurnStarted;
            _installed = true;
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }

    private static HarmonyMethod Handler(string method) => new(typeof(TargetCosts), method);

    private static void VerifyNativePaymentTiming()
    {
        var spend = AccessTools.Method(typeof(CardModel), nameof(CardModel.SpendResources));
        var machine = spend.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Native SpendResources lost its async state machine.");
        var code = PatchProcessor.GetOriginalInstructions(AccessTools.Method(machine, "MoveNext"));
        bool CostRead(CodeInstruction instruction) => instruction.operand is MethodInfo method &&
            method.DeclaringType == typeof(CardEnergyCost) && method.Name == nameof(CardEnergyCost.GetAmountToSpend);
        var read = code.FindIndex(CostRead);
        var firstAwait = code.FindIndex(instruction => instruction.operand is MethodInfo method &&
            (method.Name is "AwaitUnsafeOnCompleted" or "AwaitOnCompleted"));
        if (read < 0 || firstAwait < 0 || read >= firstAwait || code.Count(CostRead) != 1)
            throw new InvalidOperationException("Native payment cost read no longer occurs once before its first await; target-scoped adapter refused.");
    }
    private static IEnumerable<CodeInstruction> ResolvedTargetCallsites(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var targets = __originalMethod.DeclaringType!.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
            .Where(field => field.FieldType == typeof(Creature)).ToArray();
        if (targets.Length != 1) throw new InvalidOperationException($"Expected one resolved PlayCardAction target field, found {targets.Length}.");
        var nativeCanPlay = AccessTools.Method(typeof(CardModel), nameof(CardModel.CanPlay),
            [typeof(UnplayableReason).MakeByRefType(), typeof(AbstractModel).MakeByRefType()]);
        var nativeSpend = AccessTools.Method(typeof(CardModel), nameof(CardModel.SpendResources), Type.EmptyTypes);
        var result = new List<CodeInstruction>();
        var canPlayCount = 0;
        var spendCount = 0;
        foreach (var instruction in instructions)
        {
            if ((instruction.opcode == OpCodes.Call || instruction.opcode == OpCodes.Callvirt) &&
                (Equals(instruction.operand, nativeCanPlay) || Equals(instruction.operand, nativeSpend)))
            {
                var canPlay = Equals(instruction.operand, nativeCanPlay);
                var load = new CodeInstruction(OpCodes.Ldarg_0);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                load.blocks.AddRange(instruction.blocks); instruction.blocks.Clear();
                result.Add(load);
                result.Add(new CodeInstruction(OpCodes.Ldfld, targets[0]));
                instruction.opcode = OpCodes.Call;
                instruction.operand = AccessTools.Method(typeof(TargetCosts), canPlay ? nameof(CanPlayResolved) : nameof(SpendResolved));
                if (canPlay) canPlayCount++; else spendCount++;
            }
            result.Add(instruction);
        }
        if (canPlayCount != 1 || spendCount != 1)
            throw new InvalidOperationException($"Native payment/preflight callsites drifted: CanPlay={canPlayCount}, SpendResources={spendCount}.");
        return result;
    }

    private static void OnTurnStarted(CombatState combat)
    {
        foreach (var owner in combat.Players) { ObserveOwner(owner); RefreshHand(owner); }
    }
    internal static void ObserveOwner(Player owner)
    {
        if (_subscriptions.ContainsKey(owner.Creature) || !owner.Creature.IsAlive || owner.PlayerCombatState is null ||
            owner.Creature.CombatState is null || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsOverOrEnding ||
            !ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(), owner.Creature.CombatState)) return;
        _subscriptions.Add(owner.Creature, LightningBatches.Subscribe(owner.Creature, (_, _) =>
        { RefreshHand(owner); return Task.CompletedTask; }));
    }
    public static void RefreshHand(Player owner)
    {
        if (owner.PlayerCombatState is null) return;
        foreach (var card in owner.PlayerCombatState.Hand.Cards.ToArray()) card.InvokeEnergyCostChanged();
    }
    public static void Reset()
    {
        Current.Value = null;
        foreach (var subscription in _subscriptions.Values) subscription.Dispose();
        _subscriptions.Clear();
    }
}
