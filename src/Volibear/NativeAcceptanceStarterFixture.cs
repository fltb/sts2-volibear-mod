using System;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

namespace Volibear;

/// <summary>Only the untouched starter setup may batch Hand-to-Draw callbacks.</summary>
internal static class NativeAcceptanceStarterFixture
{
    internal static void Validate(CombatState state)
    {
        var player = state.Players.Single();
        var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("Missing starter combat state");
        var cards = pcs.AllPiles.SelectMany(pile => pile.Cards).ToArray();
        if (state.RoundNumber != 1 || pcs.TurnNumber != 1 || player.Creature.Powers.Any() ||
            state.Enemies.Any(enemy => enemy.Powers.Any()) || player.Relics.Count != 1 ||
            player.Relics[0].GetType() != typeof(HuntersHeart) ||
            pcs.Hand.Cards.Count != 5 || pcs.DrawPile.Cards.Count != 5 ||
            !IsStarterDeck(cards) || !IsStarterDeck(player.Deck.Cards.ToArray()))
            throw new InvalidOperationException("Bulk starter setup requires untouched ten-card deck, five-card hand, sole HuntersHeart and no powers or card modifiers");
    }

    private static bool IsStarterDeck(CardModel[] cards) =>
        cards.Length == 10 && cards.Distinct().Count() == 10 &&
        cards.All(card => card.Affliction is null && card.Enchantment is null) &&
        cards.Count(card => card.GetType() == typeof(Volibear_B01)) == 4 &&
        cards.Count(card => card.GetType() == typeof(Volibear_B02)) == 4 &&
        cards.Count(card => card.GetType() == typeof(Volibear_B03)) == 1 &&
        cards.Count(card => card.GetType() == typeof(Volibear_B04)) == 1;
}
