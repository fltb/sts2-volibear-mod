using BaseLib.Patches.Hooks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

// The current production Retrieve/Search method bodies are compiled unchanged.
// Native selection/Add and BaseLib limit hooks are controlled boundaries.
var checks = 0;
void Check(bool value, string message) { checks++; if (!value) throw new Exception(message); }
CardModel Card(Player owner, PileType pile)
{
    var card = new CardModel { Owner = owner, Pile = pile.GetPile(owner) };
    card.Pile.Cards.Add(card);
    return card;
}
CardModel Setup(int limit, int handCount)
{
    CardSelectCmd.Calls = 0; CardSelectCmd.BeforeReturn = null;
    CardPileCmd.Calls = 0; CardPileCmd.AfterAdd = null; MaxHandSizePatch.Queries.Clear();
    var owner = new Player { Limit = limit };
    for (var i = 0; i < handCount; i++) Card(owner, PileType.Hand);
    for (var i = 0; i < 4; i++) Card(owner, PileType.Draw);
    return new CardModel { Owner = owner, Pile = new() };
}
Task Run(string path, CardModel source) => path == "retrieve"
    ? ControlledEffects.Retrieve(new PlayerChoiceContext(), source, PileType.Draw, _ => true, 3, false, false, new LocString("", ""))
    : BeastSelection.Search(new PlayerChoiceContext(), source);

foreach (var path in new[] { "retrieve", "search" })
{
    var expanded = Setup(12, 10);
    await Run(path, expanded);
    Check(CardSelectCmd.Calls == 1, path + ": modified limit12 permits selection with ten cards");
    Check(expanded.Owner.Piles[PileType.Hand].Cards.Count == (path == "retrieve" ? 12 : 11), path + ": native selection count uses remaining capacity");
    Check(MaxHandSizePatch.Queries.All(p => ReferenceEquals(p, expanded.Owner)), path + ": every capacity query uses the source owner");

    foreach (var limit in new[] { 0, 8, 10 })
    {
        var full = Setup(limit, limit);
        await Run(path, full);
        Check(CardSelectCmd.Calls == 0 && CardPileCmd.Calls == 0, path + $": full owner limit{limit} does not open selection");
    }

    var shrunk = Setup(12, 9);
    CardSelectCmd.BeforeReturn = async player => { await Task.Yield(); player.Limit = 8; };
    await Run(path, shrunk);
    Check(CardSelectCmd.Calls == 1 && CardPileCmd.Calls == 0, path + ": limit shrink while selecting prevents transfer");
    Check(shrunk.Owner.Piles[PileType.Draw].Cards.Count == 4, path + ": prevented transfer preserves original card identities/pile");

    var filled = Setup(12, 11);
    CardSelectCmd.BeforeReturn = async player => { await Task.Yield(); Card(player, PileType.Hand); };
    await Run(path, filled);
    Check(CardPileCmd.Calls == 0, path + ": hand filled during selection prevents transfer");

    var otherOwner = new Player { Limit = 0 };
    var multiplayer = Setup(12, 11);
    // Other player's capacity must not become a global/local-player limit.
    MaxHandSizePatch.GetMaxHandSize(otherOwner, CardPile.MaxCardsInHand);
    await Run(path, multiplayer);
    Check(CardPileCmd.Calls == 1 && multiplayer.Owner.Piles[PileType.Hand].Cards.Count == 12, path + ": separate owner keeps independent capacity");
}

var midBatch = Setup(12, 9);
CardPileCmd.AfterAdd = async player => { await Task.Yield(); player.Limit = player.Piles[PileType.Hand].Cards.Count; };
await Run("retrieve", midBatch);
Check(CardPileCmd.Calls == 1 && midBatch.Owner.Piles[PileType.Hand].Cards.Count == 10, "retrieve: re-read limit after each awaited Add");
Console.WriteLine($"HAND_CAPACITY_OK checks={checks} engine=STUBBED native-gameplay=NOT_RUN");
