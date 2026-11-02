// Test double, not gameplay: only the shared engagement ledger is stubbed. The
// canonical guard must return before this is ever queried; a hit therefore fails
// the test instead of quietly reading mutable combat state.
using MegaCrit.Sts2.Core.Entities.Creatures;

namespace Volibear.Core;

internal static class EngageCmd
{
    internal static int Queries;

    public static bool Consumed(Creature enemy)
    {
        Queries++;
        throw new InvalidOperationException(
            "mutable engagement ledger queried for a canonical card preview: " + enemy.Name);
    }
}
