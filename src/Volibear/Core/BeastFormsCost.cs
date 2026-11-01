using System;
using System.Collections.Generic;

namespace Volibear.Core;

/// <summary>Native relative adjustments with the four native combat cost lifetimes.</summary>
internal readonly record struct BeastCostAdjustments(int Combat, int UntilPlayed, int ThisTurn, int ThisTurnOrPlayed);

internal static class BeastCostTransfer
{
    /// <summary>
    /// Preserve the material's local discount (never its surcharge) at each native
    /// cleanup boundary. Four relative adjustments encode those four states; after
    /// transfer the engine alone owns cost reads, clone copying and expiration.
    /// Relative adjustments also respect later base-cost changes and Set(...) calls.
    /// </summary>
    internal static BeastCostAdjustments Rebase<T>(int materialBase, IReadOnlyList<T> modifiers,
        Func<T, int, int> apply, Func<T, bool> expiresOnTurn, Func<T, bool> expiresOnPlay)
    {
        materialBase = Math.Max(0, materialBase);
        int Discount(bool turnEnded, bool played)
        {
            var value = materialBase;
            foreach (var modifier in modifiers)
                if (!(turnEnded && expiresOnTurn(modifier)) && !(played && expiresOnPlay(modifier)))
                    value = apply(modifier, value);
            return Math.Max(0, checked(materialBase - value));
        }
        var initial = Discount(false, false);
        var afterPlay = Discount(false, true);
        var afterTurn = Discount(true, false);
        var afterBoth = Discount(true, true);
        return new BeastCostAdjustments(-afterBoth,
            checked(afterBoth - afterTurn), checked(afterBoth - afterPlay),
            checked(afterPlay + afterTurn - afterBoth - initial));
    }
}
