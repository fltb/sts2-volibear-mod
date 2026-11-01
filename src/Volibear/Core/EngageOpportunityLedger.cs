using System;
using System.Collections.Generic;

namespace Volibear.Core;

/// <summary>
/// Opportunity facts only: no native action, scheduler, liveness or spawn eligibility policy.
/// The adapter supplies the actual current combat and round on the game thread.
/// Reservation is synchronous and irreversible until a new round/combat; a failed move is not refunded.
/// </summary>
internal sealed class EngageOpportunityLedger
{
    private sealed class Opportunity
    {
        internal int? EarlyRound;
        internal int? ActionRound;
    }

    private readonly Dictionary<object, Opportunity> opportunities = new(ReferenceEqualityComparer.Instance);
    private object? combat;
    internal long Generation { get; private set; }

    // Preserve diagnostic semantics of the former dictionaries: retained entries in
    // this combat, not merely enemies whose opportunity is spent in the current round.
    internal int EarlyEntryCount => CountEntries(early: true);
    internal int NaturalEntryCount => CountEntries(early: false);
    private int CountEntries(bool early)
    {
        var count = 0;
        foreach (var value in opportunities.Values)
            if (early ? value.EarlyRound.HasValue : value.ActionRound.HasValue) count++;
        return count;
    }

    internal void Reset()
    {
        Generation = checked(Generation + 1);
        opportunities.Clear();
        combat = null;
    }

    // Only the adapter's verified actual-combat entry points may establish authority.
    internal void EnsureCombat(object state)
    {
        ArgumentNullException.ThrowIfNull(state);
        if (ReferenceEquals(combat, state)) return;
        Reset(); // Also invalidates suspended windows across A -> B -> A without a Reset event.
        combat = state;
    }

    internal bool IsCurrent(object? state, long generation) =>
        combat is not null && ReferenceEquals(combat, state) && Generation == generation;

    private bool Matches(object? state, object? enemyCombat) =>
        combat is not null && ReferenceEquals(combat, state) && ReferenceEquals(combat, enemyCombat);

    internal bool EarlyConsumed(object? state, object? enemyCombat, object enemy, int round) =>
        Matches(state, enemyCombat) && opportunities.TryGetValue(enemy, out var value) && value.EarlyRound == round;

    internal bool Consumed(object? state, object? enemyCombat, object enemy, int round) =>
        Matches(state, enemyCombat) && opportunities.TryGetValue(enemy, out var value) &&
        (value.EarlyRound == round || value.ActionRound == round);

    internal bool TryReserve(object? state, object? enemyCombat, object enemy, int round)
    {
        if (!Matches(state, enemyCombat) || Consumed(state, enemyCombat, enemy, round)) return false;
        Entry(enemy).EarlyRound = round;
        return true;
    }

    internal bool ObserveActionStart(object? state, object? enemyCombat, object enemy, int round)
    {
        if (!Matches(state, enemyCombat)) return false;
        Entry(enemy).ActionRound = round;
        return true;
    }

    private Opportunity Entry(object enemy)
    {
        if (!opportunities.TryGetValue(enemy, out var value))
            opportunities.Add(enemy, value = new Opportunity());
        return value;
    }
}
