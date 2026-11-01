using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;

namespace MegaCrit.Sts2.Core.Entities.Players
{
    public sealed class Player
    {
        public int Limit = 10;
        public Dictionary<PileType, CardPile> Piles = new()
        { [PileType.Hand] = new() { Type = PileType.Hand }, [PileType.Draw] = new() { Type = PileType.Draw }, [PileType.Discard] = new() { Type = PileType.Discard } };
    }
}
namespace MegaCrit.Sts2.Core.Models
{
    public sealed class CardModel
    {
        public required Player Owner;
        public required CardPile Pile;
        public ModelId Id = new();
    }
    public sealed class ModelId { public string Entry => "TEST"; }
}
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum PileType { Hand, Draw, Discard }
    public sealed class CardPile { public const int MaxCardsInHand = 10; public PileType Type; public List<CardModel> Cards = []; }
    public static class Piles { public static CardPile GetPile(this PileType pile, Player player) => player.Piles[pile]; }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.Localization { public sealed class LocString { public LocString(string table, string key) { } } }
namespace MegaCrit.Sts2.Core.CardSelection
{
    public sealed class CardSelectorPrefs
    {
        public int Maximum;
        public CardSelectorPrefs(LocString prompt, int count) { Maximum = count; }
        public CardSelectorPrefs(LocString prompt, int minimum, int maximum) { Maximum = maximum; }
    }
}
namespace BaseLib.Patches.Hooks
{
    public static class MaxHandSizePatch
    {
        public static readonly List<Player> Queries = [];
        public static int GetMaxHandSize(Player player, int baseLimit)
        {
            if (baseLimit != 10) throw new Exception("Wrong native base limit");
            Queries.Add(player);
            return player.Limit;
        }
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class CardSelectCmd
    {
        public static int Calls;
        public static Func<Player, Task>? BeforeReturn;
        public static async Task<IEnumerable<CardModel>> FromCombatPile(PlayerChoiceContext context, CardPile pile,
            Player player, MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs, Func<CardModel, bool> eligible)
        {
            Calls++;
            var cards = pile.Cards.Where(eligible).Take(prefs.Maximum).ToArray();
            if (BeforeReturn is not null) await BeforeReturn(player);
            return cards;
        }
    }
    public static class CardPileCmd
    {
        public static int Calls;
        public static Func<Player, Task>? AfterAdd;
        public static async Task Add(CardModel card, PileType destination)
        {
            Calls++;
            card.Pile.Cards.Remove(card);
            card.Pile = destination.GetPile(card.Owner);
            card.Pile.Cards.Add(card);
            if (AfterAdd is not null) await AfterAdd(card.Owner);
        }
    }
}
namespace Volibear.Core
{
    public static class CardPresentationReceipts { public static void Retrieved(CardModel card, CardModel source, PileType from) { } }
}
namespace Volibear.Content
{
    public static class DirectEffects { public static bool Live(CardModel source) => true; }
    public static class NextPlayDiscount { public static void Grant(CardModel card) { } }
    internal static partial class BeastSelection { internal static bool Live(CardModel source) => true; }
}
