using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Runs;

namespace Volibear.Core;

/// <summary>Source-exact Hopper theft admission. Native attack, existing stolen-card return,
/// escape and reward processing are untouched. C removal and M removal are separate commits.</summary>
public static partial class DomainHopperEffects
{
    private const string HarmonyId = "Volibear.DomainHopperEffects";
    private static bool installed;
    private static long epoch;
    private enum Kind { Root, Steal, MasterSingle, MasterMany }
    private sealed class Root(ThievingHopper source)
    {
        internal readonly ThievingHopper Source = source;
        internal readonly ICombatState? Combat = source.Creature.CombatState;
        internal readonly long Epoch = Volatile.Read(ref epoch);
        internal readonly Dictionary<CardModel, Theft> Cards = new(ReferenceEqualityComparer.Instance);
    }
    private sealed class Theft(Root root, CardModel card)
    {
        internal readonly Root Root = root;
        internal readonly CardModel Card = card;
        internal readonly CardModel Master = card.DeckVersion ?? throw new InvalidOperationException("Hopper selected card without master.");
        internal readonly DomainHopperDecision Decision = new();
        internal SwipePower? Swipe;
    }
    private sealed record Context(Root Root, Theft? Theft = null);
    private sealed record Frame(SummonLifetime<Context>.Binding? Binding, Kind Kind);
    private static readonly SummonLifetime<Context> Lifetimes = new();
    private static readonly AsyncLocal<SummonTicket<Context>?> Pending = new();

    public static void Install()
    {
        if (installed) return;
        var harmony = new Harmony(HarmonyId);
        try
        {
            InstallPatches(harmony);
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]),
                prefix: new HarmonyMethod(typeof(DomainHopperEffects), nameof(Reset)));
            installed = true;
        }
        catch { harmony.UnpatchAll(HarmonyId); throw; }
    }
    public static void Reset() => Interlocked.Increment(ref epoch);

    private static bool Current(Root root) => root.Epoch == Volatile.Read(ref epoch) && root.Combat is not null &&
        ReferenceEquals(root.Combat, CombatManager.Instance.DebugOnlyGetState()) &&
        ReferenceEquals(root.Source.Creature.CombatState, root.Combat) && root.Combat.ContainsCreature(root.Source.Creature) &&
        root.Source.Creature.IsEnemy && !root.Source.Creature.IsPlayer && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding;
    private static bool Domain(Root root) => DomainEnemyEffects.ActiveFor(root.Source.Creature);
    private static Context? Payload(Frame frame)
    {
        if (frame.Binding is { Closed: true }) throw new InvalidOperationException("Closed Hopper source resumed at a contribution boundary.");
        return frame.Binding?.Payload;
    }
    private static bool Matches(Theft theft) => ReferenceEquals(theft.Card.DeckVersion, theft.Master) &&
        ReferenceEquals(theft.Card.Owner, theft.Master.Owner);

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Frame Enter(Task native, int state, object source, int kindValue)
    {
        var kind = (Kind)kindValue;
        var binding = state == -1 ? null : Lifetimes.Find(native, source, kindValue);
        if (state == -1)
        {
            Context? context = null;
            if (kind == Kind.Root) context = new Context(new Root((ThievingHopper)source));
            else if (Pending.Value is { } ticket)
            {
                // A mismatched claim is a barrier, never permission to borrow an ancestor.
                Pending.Value = null;
                ticket.TryClaim(kindValue, source, out context);
            }
            if (context is not null) binding = Lifetimes.Begin(context, context.Root.Epoch, false, source, kindValue);
        }
        return new Frame(binding, kind);
    }
    private static ISummonRegistration? Registration(Frame frame) => frame.Binding;
    private static void Leave(Frame frame, ref AsyncTaskMethodBuilder builder, int state) => Lifetimes.VerifyReturn(frame.Binding, ref builder, state);
    private static void Close(Frame frame) => Lifetimes.Close(frame.Binding, static _ => { });
    private static Task Forward(Kind kind, object source, Context? context, Func<Task> native)
    {
        var previous = Pending.Value;
        Pending.Value = new SummonTicket<Context>(context, (int)kind, source);
        try { return native(); } // Original Task and synchronous exception; no proxy await or catch.
        finally { Pending.Value = previous; }
    }

    private static Task RemoveCombat(CardModel card, bool visuals, Frame frame)
    {
        // This wrapper exists only at the native Hopper root callsite.
        if (Payload(frame) is not { } context) return Task.CompletedTask;
        var theft = new Theft(context.Root, card);
        if (!context.Root.Cards.TryAdd(card, theft)) throw new InvalidOperationException("Hopper selected same card twice.");
        if (!Matches(theft) || card.Pile?.Type is not (PileType.Draw or PileType.Discard) || theft.Master.Pile?.Type != PileType.Deck)
            throw new InvalidOperationException("Hopper selected card identity/pile changed.");
        if (!theft.Decision.AdmitCombat(Current(context.Root), Domain(context.Root)))
        {
            if (Current(context.Root)) Volibear.Presentation.PowerPresentationDomain.Once(theft, context.Root.Source.Creature, context.Root.Source, card);
            return Task.CompletedTask;
        }
        return CardPileCmd.RemoveFromCombat(card, visuals);
    }
    private static void Enqueue(List<CardModel> cards, CardModel card, Frame frame)
    {
        if (Payload(frame) is not { } context) return;
        if (!context.Root.Cards.TryGetValue(card, out var theft)) throw new InvalidOperationException("Hopper enqueue lacks exact admission.");
        if (theft.Decision.State == DomainHopperDecision.Phase.Cancelled) return;
        if (card.Pile is not null || !card.HasBeenRemovedFromState || !Matches(theft))
            throw new InvalidOperationException("Native Hopper combat removal incomplete.");
        theft.Decision.CombatCompleted();
        cards.Add(card);
    }
    private static Task Steal(SwipePower swipe, CardModel card, Frame frame)
    {
        if (Payload(frame) is not { } context) return Task.CompletedTask;
        if (!context.Root.Cards.TryGetValue(card, out var theft) || !Matches(theft)) throw new InvalidOperationException("Hopper Steal lacks exact card.");
        if (theft.Swipe is not null) throw new InvalidOperationException("Hopper Swipe reused.");
        theft.Swipe = swipe;
        if (!theft.Decision.AdmitMaster(Current(theft.Root), Domain(theft.Root)))
        {
            if (Current(theft.Root)) Volibear.Presentation.PowerPresentationDomain.Once(theft, theft.Root.Source.Creature, theft.Root.Source, card);
            return Task.CompletedTask;
        }
        return Forward(Kind.Steal, swipe, new Context(theft.Root, theft), () => swipe.Steal(card));
    }
    private static Task MasterSingle(CardModel card, bool preview, Frame frame)
    {
        var context = Payload(frame);
        if (context?.Theft is { } theft && (!ReferenceEquals(card, theft.Master) || preview))
            throw new InvalidOperationException("Hopper master call arguments changed.");
        return Forward(Kind.MasterSingle, card, context, () => CardPileCmd.RemoveFromDeck(card, preview));
    }
    private static Task MasterMany(IReadOnlyList<CardModel> cards, bool preview, Frame frame)
    {
        var context = Payload(frame);
        if (context?.Theft is { } theft && (cards.Count != 1 || !ReferenceEquals(cards[0], theft.Master) || preview))
            throw new InvalidOperationException("Hopper master collection changed.");
        return Forward(Kind.MasterMany, cards, context, () => CardPileCmd.RemoveFromDeck(cards, preview));
    }
    private static void MasterPile(CardModel card, bool silent, Frame frame)
    {
        if (Payload(frame)?.Theft is not { } theft) { card.RemoveFromCurrentPile(silent); return; }
        if (!ReferenceEquals(card, theft.Master) || !Matches(theft) || card.Pile?.Type != PileType.Deck)
            throw new InvalidOperationException("Hopper master precommit identity/pile changed.");
        // This callsite is after the ORIGINAL BeforeCardRemoved await/GetResult, not Steal entry.
        if (!theft.Decision.AdmitMaster(Current(theft.Root), Domain(theft.Root)))
        {
            if (Current(theft.Root)) Volibear.Presentation.PowerPresentationDomain.Once(theft, theft.Root.Source.Creature, theft.Root.Source, card);
            return;
        }
        try { card.RemoveFromCurrentPile(silent); }
        finally
        {
            if (card.Pile is null) theft.Decision.MasterCommitted();
        }
    }
    private static void MasterState(CardModel card, Frame frame)
    {
        if (Payload(frame)?.Theft is not { } theft) { card.RemoveFromState(); return; }
        if (!ReferenceEquals(card, theft.Master)) throw new InvalidOperationException("Hopper master state target changed.");
        if (theft.Decision.FinishCommitted) card.RemoveFromState();
    }
    private static void LootStolen(PlayerMapPointHistoryEntry history, int amount, Frame frame)
    {
        var theft = Payload(frame)?.Theft;
        if (theft is null || theft.Decision.FinishCommitted) history.MarkLootStolen(amount);
    }
    private static Task Apply(PlayerChoiceContext choices, PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, Frame frame)
    {
        if (Payload(frame) is not { } context) return Task.CompletedTask;
        var theft = context.Root.Cards.Values.SingleOrDefault(t => ReferenceEquals(t.Swipe, power))
            ?? throw new InvalidOperationException("Hopper Swipe mount lacks exact source.");
        if (!theft.Decision.FinishCommitted) return Task.CompletedTask;
        // Already committed theft: do NOT domain-gate native bookkeeping or existing return obligations.
        return PowerCmd.Apply(choices, power, target, amount, applier, card, silent);
    }
}
