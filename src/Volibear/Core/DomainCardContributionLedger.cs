using System;

namespace Volibear.Core;

/// <summary>
/// The positive scalar that would remain without observed enemy additions. Native
/// decrements advance both totals; external writes enter the retained total. This is
/// a counterfactual, not an invented allocation of a native shared timer to owners.
/// Favorable native negative costs are returned unchanged by the contribution adapter.
/// </summary>
internal sealed class DomainCardContributionLedger
{
    internal int Actual { get; private set; }
    internal int Retained { get; private set; }

    internal DomainCardContributionLedger(int amount, bool enemy)
    { Actual = amount; Retained = enemy ? 0 : Math.Max(0, amount); }

    internal bool Reconcile(int actual)
    {
        if (actual == Actual) return false;
        ChangeRetained(actual, enemy: false);
        return true;
    }

    internal void Change(int before, int after, bool enemy)
    {
        Reconcile(before);
        ChangeRetained(after, enemy);
    }

    private void ChangeRetained(int next, bool enemy)
    {
        long delta = (long)next - Actual;
        if (delta < 0 || !enemy)
            Retained = (int)Math.Clamp(Retained + delta, 0L, Math.Max(0L, next));
        else Retained = Math.Min(Retained, Math.Max(0, next));
        Actual = next;
    }

    internal int Effective => Actual <= 0 ? Actual : Math.Min(Actual, Retained);
}
