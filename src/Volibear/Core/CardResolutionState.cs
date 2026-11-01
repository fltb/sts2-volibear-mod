using System;

namespace Volibear.Core;

/// <summary>One real OnPlayWrapper invocation, not one native replay CardPlay.</summary>
public sealed class CardResolutionPlayGate
{
    public bool Attached { get; private set; }
    public bool Closed { get; private set; }

    public bool TryAttach(bool domainActive)
    {
        if (Closed || Attached || !domainActive) return false;
        Attached = true; // Reserve before awaiting lightning / recursive responses.
        return true;
    }

    public void Close() => Closed = true;
}

/// <summary>
/// Domain duration is consumed only after the next normal starting draw boundary.
/// Extra turns share the engine RoundNumber and do not consume another normal round.
/// A domain opened during a starting draw does not spend a round on that same draw.
/// </summary>
public sealed class CardResolutionDrawClock(int openedRound)
{
    private int _lastDrawRound = openedRound;

    public bool TryConsumeNormalDraw(int round)
    {
        if (round <= _lastDrawRound) return false;
        _lastDrawRound = round;
        return true;
    }
}

public static class CardResolutionDuration
{
    // Native PowerModel.SetAmount clamps to +/-999999999 before serialization.
    // Reserve its positive ceiling for permanent duration; Extend refuses to let
    // finite stacking reach it. Never feed this sentinel to damage calculations.
    public const int Permanent = 999_999_999;

    public static int Extend(int current, int rounds)
    {
        if (rounds <= 0 || rounds == Permanent) throw new ArgumentOutOfRangeException(nameof(rounds));
        if (current == Permanent) return Permanent;
        var result = checked(current + rounds);
        if (result >= Permanent) throw new ArgumentOutOfRangeException(nameof(rounds));
        return result;
    }
}
