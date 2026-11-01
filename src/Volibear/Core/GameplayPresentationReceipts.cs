using System;
using System.Threading;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

namespace Volibear.Core;

public sealed record GameplayPresentationReceipt(long Id, ICombatState Combat, Creature Owner,
    string Kind, AbstractModel? Source, CardModel? Card, Creature? Target, decimal Amount);

/// <summary>Best-effort notifications from actual production event boundaries.
/// No subscriber may replace a command, await presentation, or change settlement.</summary>
public static class GameplayPresentationReceipts
{
    private static long sequence;
    public static event Action<GameplayPresentationReceipt>? Committed;

    public static void Publish(string kind, Creature owner, AbstractModel? source = null,
        CardModel? card = null, Creature? target = null, decimal amount = 1)
    {
        try
        {
            if (amount <= 0 || owner.Player?.Character is not VolibearCharacter || !owner.IsAlive ||
                owner.CombatState is not { } combat || !combat.ContainsCreature(owner) ||
                !ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) ||
                !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsOverOrEnding) return;
            var receipt = new GameplayPresentationReceipt(Interlocked.Increment(ref sequence), combat,
                owner, kind, source, card, target, amount);
            foreach (Action<GameplayPresentationReceipt> subscriber in Committed?.GetInvocationList() ?? [])
                try { subscriber(receipt); } catch { /* Presentation cannot fail a committed command. */ }
        }
        catch { /* Optional presentation never changes the original gameplay result. */ }
    }
}
