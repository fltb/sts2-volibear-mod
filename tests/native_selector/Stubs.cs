// API fixtures only. No game implementation, UI, network, or Harmony is simulated.
namespace MegaCrit.Sts2.Core.Entities.CardRewardAlternatives { public class CardRewardAlternative; }
namespace MegaCrit.Sts2.Core.Entities.Cards { public class CardCreationResult; }
namespace MegaCrit.Sts2.Core.Entities.Players { public class Player; }
namespace MegaCrit.Sts2.Core.Models
{
    public class CardModel(MegaCrit.Sts2.Core.Entities.Players.Player owner)
    {
        public MegaCrit.Sts2.Core.Entities.Players.Player Owner { get; } = owner;
        public CardModel? NetworkResolution { get; set; }
    }
}
namespace MegaCrit.Sts2.Core.Entities.Multiplayer
{
    public sealed class NetCombatCard(MegaCrit.Sts2.Core.Models.CardModel card)
    {
        public static NetCombatCard FromModel(MegaCrit.Sts2.Core.Models.CardModel card) => new(card);
        public MegaCrit.Sts2.Core.Models.CardModel ToCardModel() => card.NetworkResolution ?? card;
    }
}
namespace MegaCrit.Sts2.Core.GameActions
{
    public class PlayCardAction(MegaCrit.Sts2.Core.Models.CardModel card)
    {
        public MegaCrit.Sts2.Core.Entities.Multiplayer.NetCombatCard NetCombatCard { get; } = new(card);
        public Task CompletionTask { get; set; } = new TaskCompletionSource().Task;
    }
}
namespace MegaCrit.Sts2.Core.Runs
{
    public sealed class Executor { public object? CurrentlyRunningAction { get; set; } }
    public sealed class RunManager
    {
        public static RunManager Instance { get; } = new();
        public Executor ActionExecutor { get; } = new();
    }
}
namespace MegaCrit.Sts2.Core.TestSupport
{
    // Independent pinned-API boundary: 0.107.1 returns the reward selection
    // struct, not the nullable CardModel used by pre-0.105 implementations.
    public readonly record struct CardRewardSelection;
    public static class TestMode { public static bool IsOn { get; set; } }
    public interface ICardSelector
    {
        Task<IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>> GetSelectedCards(IEnumerable<MegaCrit.Sts2.Core.Models.CardModel> cards, int min, int max);
        CardRewardSelection GetSelectedCardReward(IReadOnlyList<MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult> cards,
            IReadOnlyList<MegaCrit.Sts2.Core.Entities.CardRewardAlternatives.CardRewardAlternative> alternatives);
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class CardSelectCmd
    {
        public static MegaCrit.Sts2.Core.TestSupport.ICardSelector? Selector { get; set; }
        public static IDisposable UseSelector(MegaCrit.Sts2.Core.TestSupport.ICardSelector selector)
        { var old=Selector;Selector=selector;return new Scope(old); }
        private sealed class Scope(MegaCrit.Sts2.Core.TestSupport.ICardSelector? old) : IDisposable
        { public void Dispose() => Selector=old; }
    }
}
