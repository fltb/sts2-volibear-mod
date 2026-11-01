using System.Threading;

namespace Volibear.Presentation;

/// <summary>One exact native command invocation, not a time window. Rejected preliminary
/// events do not consume the transaction; a committed event can consume it only once.</summary>
internal sealed class AudioCommitGate
{
    private int emitted;
    internal bool TryCommit(bool samePowerAndOwner, bool registered, bool positiveDelta,
        bool positiveResult, bool silent) => samePowerAndOwner && registered && positiveDelta &&
        positiveResult && !silent && Interlocked.CompareExchange(ref emitted, 1, 0) == 0;
}
