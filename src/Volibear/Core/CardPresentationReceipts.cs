using System;
using System.Threading;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

public sealed record CommittedCardPresentation(long Id, ICombatState Combat, Creature Owner,
    CardModel Card, AbstractModel Source, string Effect, PileType From);

/// <summary>Synchronous, best-effort, read-only notifications AFTER the actual native move.
/// No subscriber can replace/await the card command or make its effect fail.</summary>
public static class CardPresentationReceipts
{
    private static long sequence;
    public static event Action<CommittedCardPresentation>? Committed;

    internal static void Purified(CardModel card, DomainPower source, PileType from)
    {
        try
        {
            if (card.Pile?.Type != PileType.Exhaust || !ReferenceEquals(card.Owner.Creature, source.Owner)) return;
            Publish(card, source, "card_purify", from);
        }
        catch { /* Optional presentation never changes purification or its replacement draw. */ }
    }
    internal static void Retrieved(CardModel card, CardModel source, PileType from)
    {
        try
        {
            if (from is not (PileType.Draw or PileType.Discard) || card.Pile?.Type != PileType.Hand ||
                !ReferenceEquals(card.Owner, source.Owner)) return;
            Publish(card, source, "card_retrieve", from);
        }
        catch { /* Optional presentation never changes retrieval or its following discount. */ }
    }
    private static void Publish(CardModel card, AbstractModel source, string effect, PileType from)
    {
        var owner = card.Owner.Creature;
        if (owner.CombatState is not { } combat || !CardReceiptPolicy.Allows(effect, from.ToString(),
            (card.Pile?.Type ?? PileType.None).ToString(), true, ReferenceEquals(card.CombatState, combat),
            owner.IsAlive && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding)) return;
        var receipt = new CommittedCardPresentation(Interlocked.Increment(ref sequence), combat, owner, card, source, effect, from);
        CardReceiptPolicy.Notify(Committed, receipt);
    }
}
