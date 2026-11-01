using System;

namespace Volibear.Core;

/// <summary>One selected native combat card and its master. No restoration or synthetic debt.</summary>
internal sealed class DomainHopperDecision
{
    internal enum Phase { Selected, CombatAdmitted, CombatRemoved, Cancelled, MasterCommitted }
    internal Phase State { get; private set; }
    internal bool AdmitCombat(bool current, bool domain)
    {
        if (State != Phase.Selected) throw new InvalidOperationException("Hopper combat admission repeated.");
        State = current && !domain ? Phase.CombatAdmitted : Phase.Cancelled;
        return State == Phase.CombatAdmitted;
    }
    internal void CombatCompleted()
    {
        if (State != Phase.CombatAdmitted) throw new InvalidOperationException("Hopper combat removal without admission.");
        State = Phase.CombatRemoved;
    }
    internal bool AdmitMaster(bool current, bool domain)
    {
        if (State == Phase.Cancelled) return false;
        if (State != Phase.CombatRemoved) throw new InvalidOperationException("Hopper master admission out of order.");
        if (current && !domain) return true;
        State = Phase.Cancelled;
        return false;
    }
    // Physical master removal is the irreversible fact. Later Domain cannot cancel its cleanup.
    internal void MasterCommitted()
    {
        if (State != Phase.CombatRemoved) throw new InvalidOperationException("Hopper master commit out of order.");
        State = Phase.MasterCommitted;
    }
    internal bool FinishCommitted => State == Phase.MasterCommitted;
}
