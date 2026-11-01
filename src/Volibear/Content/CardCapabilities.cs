using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

namespace Volibear.Content;

/// <summary>Declared by skill definitions whose own effect directly settles lightning.</summary>
public interface INativeLightningSpell { }

public static class CardCapabilities
{
    // Behavior overlays supersede the original card's declared effect. No card-name,
    // localization-text or 'has a Lightning variable' heuristic determines this tag.
    public static bool IsThunderSpell(CardModel card) => BeastForms.Shape(card) switch
    {
        BeastShape.Body => true,
        BeastShape.Claw => false,
        _ => card.Type == CardType.Skill && card is INativeLightningSpell
    };
}
