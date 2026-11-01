namespace Volibear.Core;

public static partial class DomainSummonEffects
{
    internal enum GateOwnership { Unknown, Current, StaleKnown }

    // Unknown is not permission to invent an owner. A known expired frame, however,
    // must not authorize a new creation at an existing pre-create boundary.
    internal static GateOwnership ClassifyGate(bool hasBinding, long frameGeneration, long batchGeneration, long generation) =>
        !hasBinding ? GateOwnership.Unknown :
        frameGeneration == generation && batchGeneration == generation ? GateOwnership.Current : GateOwnership.StaleKnown;

    // A weak ending-veto index is not an actual-Task receipt for a new callback.
    // Retain legacy consumed cancellation, but never attach a closed unconsumed attempt anew.
    internal static bool CanAttachDeathBirth(bool closed, bool cancelled) => !closed || cancelled;

    // Merely seeing Domain is not a consumed cancellation. Only a real eligible boundary calls AtBoundary.
    internal sealed class DeathDecision(bool domainAtEntry)
    {
        private bool _open = true;
        internal bool Cancelled { get; private set; }
        internal bool TryCancel(bool removalPrevented) => AtBoundary(removalPrevented, false);
        internal bool AtBoundary(bool removalPrevented, bool domainNow)
        {
            if (removalPrevented) return false;
            if (Cancelled) return true;
            if (!_open || !(domainAtEntry || domainNow)) return false;
            return Cancelled = true;
        }
        internal void Close() => _open = false;
    }
}
