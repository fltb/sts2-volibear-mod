using System;

namespace Volibear.Core;

/// <summary>One actual death's pending benefit, deliberately longer-lived than Kill's Task.</summary>
public sealed class RevivalDecision
{
    public bool Confirmed { get; private set; }
    public bool DomainSeen { get; private set; }
    public bool Cancelled { get; private set; }
    public bool Committed { get; private set; }
    public void ObserveDomain(bool active) { if (active && !Committed) DomainSeen = true; }
    public void Confirm(bool removalPrevented) { if (!removalPrevented) Confirmed = true; }
    public bool CancelIfRequired(bool active)
    {
        ObserveDomain(active);
        if (Confirmed && !Committed && DomainSeen) Cancelled = true;
        return Cancelled;
    }
    public static bool OwnsCancelledPreservation(object source, object? capturedSource, object owner,
        object? capturedOwner, object targetOwner, bool cancelled, bool sameEpoch) =>
        cancelled && sameEpoch && ReferenceEquals(source, capturedSource) &&
        ReferenceEquals(owner, capturedOwner) && ReferenceEquals(owner, targetOwner);
    public static bool SkipUnstartedCallback(int state, bool ownsTicket, bool benefitAllowed) =>
        state == -1 && ownsTicket && !benefitAllowed;
    public void Commit()
    {
        if (Cancelled || DomainSeen || !Confirmed) throw new InvalidOperationException("Invalid resurrection commit.");
        Committed = true;
    }
}
