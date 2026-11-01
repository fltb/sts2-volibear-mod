using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Declared by skill definitions whose own effect directly settles lightning.</summary>
public interface INativeLightningSpell { }

public static class CardCapabilities
{
    // Native card definitions own their capability, including generated beast cards.
    // No material-card identity or localization heuristic participates in this query.
    public static bool IsThunderSpell(CardModel card) =>
        card.Type == CardType.Skill && card is INativeLightningSpell;
}
