using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>Production bookkeeping, independent of Godot. One ledger per combat/player.
/// The previous card type survives turns; attack and target counters do not (frozen TS).
/// A snapshot is keyed by actual wrapper identity, never by a reusable card instance.</summary>
public sealed class PlayHistoryLedger<TType, TTarget> where TType : struct where TTarget : class
{
    public sealed record Entry(long PlayId, int Turn, TType Type, TType? PreviousType,
        int PriorAttacks, int AttackOrdinal, TTarget? Target, bool SingleAttack,
        int TargetOrdinal, int PriorTargetAttacks)
    {
        public bool Completed { get; internal set; }
    }

    private int _turn = int.MinValue;
    private int _attacks;
    private TType? _previous;
    private long? _lastPlay;
    private TTarget? _lastTarget;
    private readonly Dictionary<TTarget, int> _targets = new(ReferenceEqualityComparer.Instance);
    private readonly Dictionary<long, Entry> _plays = [];

    public int AttackCount(int turn) => turn == _turn ? _attacks : 0;
    public int TargetCount(int turn, TTarget target) => turn == _turn ? _targets.GetValueOrDefault(target) : 0;
    public int BeforeTargetCount(int turn, TTarget target, long? queryingPlay)
    {
        var count = TargetCount(turn, target);
        return Math.Max(0, count - (turn == _turn && queryingPlay.HasValue && queryingPlay == _lastPlay &&
            ReferenceEquals(_lastTarget, target) ? 1 : 0));
    }
    public TType? PreviousType => _previous;
    public Entry? Find(long playId) => _plays.GetValueOrDefault(playId);

    public Entry Record(long playId, int turn, TType type, bool attack, bool single, TTarget? target)
    {
        if (_plays.TryGetValue(playId, out var existing)) return existing;
        if (turn != _turn) { _turn = turn; _attacks = 0; _targets.Clear(); }
        var priorTarget = target is null ? 0 : _targets.GetValueOrDefault(target);
        var singleAttack = attack && single && target is not null;
        var entry = new Entry(playId, turn, type, _previous, _attacks, _attacks + (attack ? 1 : 0),
            target, singleAttack, singleAttack ? priorTarget + 1 : 0, priorTarget);
        _attacks = entry.AttackOrdinal;
        if (singleAttack) _targets[target!] = entry.TargetOrdinal;
        _previous = type;
        _lastPlay = playId;
        _lastTarget = single ? target : null;
        _plays.Add(playId, entry);
        return entry;
    }

    public void Complete(long playId)
    {
        if (!_plays.TryGetValue(playId, out var entry)) throw new InvalidOperationException("Completing an unrecorded actual play.");
        entry.Completed = true;
    }
}

public sealed record ActualPlaySnapshot(long PlayId, Player Owner, ICombatState Combat, int TurnNumber,
    CardType CardType, CardType? PriorType, int PriorAttackCount, int AttackOrdinal,
    Creature? Target, bool IsSingleTargetAttack, int TargetOrdinal, int PriorTargetAttackCount, bool Completed);

/// <summary>
/// Adapts only the verified BeforeCardPlayed/AfterCardPlayed callsites inside the
/// native OnPlayWrapper state machine. The original hooks and wrapper execute normally.
/// Install after CardResolutionHooks; the latter owns actual wrapper/task identity.
/// </summary>
public static class AttackHistory
{
    private static ConditionalWeakTable<ICombatState, Dictionary<Player, PlayHistoryLedger<CardType, Creature>>> _combats = new();
    private static bool _installed;

    private static PlayHistoryLedger<CardType, Creature> Ledger(Player owner, ICombatState combat)
    {
        var owners = _combats.GetValue(combat, _ => new(ReferenceEqualityComparer.Instance));
        if (!owners.TryGetValue(owner, out var ledger)) owners.Add(owner, ledger = new());
        return ledger;
    }

    private static int Turn(Player owner) => owner.PlayerCombatState?.TurnNumber
        ?? throw new InvalidOperationException("Card history requires a player combat state.");
    private static ICombatState Combat(Player owner) => owner.Creature.CombatState
        ?? throw new InvalidOperationException("Card history requires a combat.");
    private static long PlayId(CardModel card) => CardResolutionHooks.CurrentPlayId(card)
        ?? throw new InvalidOperationException("Attack history requires the native actual-play scope.");

    private static PlayHistoryLedger<CardType, Creature>.Entry Entry(CardModel card)
        => Ledger(card.Owner, Combat(card.Owner)).Find(PlayId(card))
           ?? throw new InvalidOperationException("Attack history must be captured before native BeforeCardPlayed hooks.");

    public static int PriorAttackCount(CardModel card) => Entry(card).PriorAttacks;
    public static CardType? PreviousType(CardModel card) => Entry(card).PreviousType;
    public static int CurrentAttackOrdinal(CardPlay play) => Entry(play.Card).AttackOrdinal;
    public static int CurrentTargetOrdinal(CardPlay play) => Entry(play.Card).TargetOrdinal;
    public static int AttackCount(Player owner) => owner.Creature.CombatState is { } combat && owner.PlayerCombatState is not null
        ? Ledger(owner, combat).AttackCount(Turn(owner)) : 0;
    public static int TargetAttackCount(Player owner, Creature target) =>
        owner.Creature.CombatState is { } combat && owner.PlayerCombatState is not null && ReferenceEquals(target.CombatState, combat)
            ? Ledger(owner, combat).TargetCount(Turn(owner), target) : 0;

    /// <summary>Frozen TS beforeTarget query: live target count minus this play only
    /// while it remains the last recorded targeted play. Unlike C20/U20's before
    /// snapshot, a nested actual play can change this query.</summary>
    public static int PriorTargetAttackCount(CardModel card, Creature target)
    {
        var combat = card.Owner.Creature.CombatState;
        if (combat is null || card.Owner.PlayerCombatState is null) return 0;
        var ledger = Ledger(card.Owner, combat);
        return ledger.BeforeTargetCount(Turn(card.Owner), target, CardResolutionHooks.CurrentPlayId(card));
    }

    public static ActualPlaySnapshot Snapshot(CardPlay play)
    {
        var entry = Entry(play.Card);
        return new(entry.PlayId, play.Card.Owner, Combat(play.Card.Owner), entry.Turn, entry.Type,
            entry.PreviousType, entry.PriorAttacks, entry.AttackOrdinal, entry.Target,
            entry.SingleAttack, entry.TargetOrdinal, entry.PriorTargetAttacks, entry.Completed);
    }

    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony("Volibear.AttackHistory");
        try
        {
            var wrapper = AccessTools.Method(typeof(CardModel), nameof(CardModel.OnPlayWrapper),
                [typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(ResourceInfo), typeof(bool)])
                ?? throw new MissingMethodException("CardModel.OnPlayWrapper");
            var machine = wrapper.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
                ?? throw new InvalidOperationException("Native play wrapper lost its state machine.");
            harmony.Patch(AccessTools.Method(machine, "MoveNext"),
                transpiler: new HarmonyMethod(typeof(AttackHistory), nameof(HookCallsites)));
            harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]),
                prefix: new HarmonyMethod(typeof(AttackHistory), nameof(Reset)));
            CombatManager.Instance.CombatEnded += _ => Reset();
            CombatManager.Instance.CombatSetUp += _ => Reset();
            _installed = true;
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }

    private static IEnumerable<CodeInstruction> HookCallsites(IEnumerable<CodeInstruction> instructions)
    {
        var before = AccessTools.Method(typeof(Hook), nameof(Hook.BeforeCardPlayed), [typeof(ICombatState), typeof(CardPlay)]);
        var after = AccessTools.Method(typeof(Hook), nameof(Hook.AfterCardPlayed),
            [typeof(ICombatState), typeof(PlayerChoiceContext), typeof(CardPlay)]);
        var code = instructions.ToList();
        var beforeCount = 0;
        var afterCount = 0;
        foreach (var instruction in code)
        {
            if (instruction.opcode != OpCodes.Call && instruction.opcode != OpCodes.Callvirt) continue;
            if (Equals(instruction.operand, before))
            { instruction.opcode = OpCodes.Call; instruction.operand = AccessTools.Method(typeof(AttackHistory), nameof(BeforeNativeHooks)); beforeCount++; }
            else if (Equals(instruction.operand, after))
            { instruction.opcode = OpCodes.Call; instruction.operand = AccessTools.Method(typeof(AttackHistory), nameof(AfterNativeHooks)); afterCount++; }
        }
        if (beforeCount != 1 || afterCount != 1)
            throw new InvalidOperationException($"Native actual-play hook callsites drifted: before={beforeCount}, after={afterCount}.");
        return code;
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task BeforeNativeHooks(ICombatState combat, CardPlay play)
    {
        TargetCosts.ObserveOwner(play.Card.Owner);
        var ledger = Ledger(play.Card.Owner, combat);
        var id = PlayId(play.Card);
        if (play.PlayIndex == 0)
        {
            // AnyEnemy is the native counterpart of frozen metadata variant.target.
            // RandomEnemy/AllEnemies never acquire per-target count from their hits.
            ledger.Record(id, Turn(play.Card.Owner), play.Card.Type, play.Card.Type == CardType.Attack,
                play.Card.TargetType == TargetType.AnyEnemy, play.Target);
        }
        else if (ledger.Find(id) is null)
            throw new InvalidOperationException("Native replay has no initial actual-play snapshot.");
        return Hook.BeforeCardPlayed(combat, play);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task AfterNativeHooks(ICombatState combat, PlayerChoiceContext context, CardPlay play)
    {
        if (play.IsLastInSeries) Ledger(play.Card.Owner, combat).Complete(PlayId(play.Card));
        await Hook.AfterCardPlayed(combat, context, play);
        TargetCosts.RefreshHand(play.Card.Owner);
    }

    public static void Reset() => _combats = new();
}
