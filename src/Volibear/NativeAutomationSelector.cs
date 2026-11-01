using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;

namespace Volibear;

/// <summary>
/// Scoped use of the game's own automated card-selection interface. It supplies
/// decisions only: native commands still filter candidates, enforce payment and
/// execute the queued action. This is not UI or network transport validation.
/// </summary>
internal sealed class NativeAutomationSelector : ICardSelector, IDisposable
{
    internal sealed record Selection(CardModel[] Options, int Min, int Max, PlayCardAction? Action);
    private readonly Player player;
    private readonly Func<Selection, IEnumerable<CardModel>> choose;
    private readonly Action<Selection, CardModel[]>? observe;
    private readonly bool allowTurnChoice;
    private readonly IDisposable scope;
    private bool disposed;
    internal int Count { get; private set; }

    internal NativeAutomationSelector(Player player, Func<Selection, IEnumerable<CardModel>> choose,
        Action<Selection, CardModel[]>? observe = null, bool allowTurnChoice = false)
    {
        if (TestMode.IsOn || CardSelectCmd.Selector is not null)
            throw new InvalidOperationException("Native automation needs the real run and exclusive selector ownership");
        this.player = player; this.choose = choose; this.observe = observe; this.allowTurnChoice = allowTurnChoice;
        scope = CardSelectCmd.UseSelector(this);
        if (!ReferenceEquals(CardSelectCmd.Selector, this))
        {
            scope.Dispose();
            throw new InvalidOperationException("Native selector scope did not install");
        }
    }

    public Task<IEnumerable<CardModel>> GetSelectedCards(IEnumerable<CardModel> options, int minSelect, int maxSelect)
    {
        if (disposed || !ReferenceEquals(CardSelectCmd.Selector, this))
            throw new InvalidOperationException("Native selector scope lost ownership");
        var cards = options.ToArray();
        if (minSelect < 0 || maxSelect < minSelect || minSelect > cards.Length ||
            cards.Distinct(ReferenceEqualityComparer.Instance).Count() != cards.Length ||
            cards.Any(card => !ReferenceEquals(card.Owner, player) ||
                !ReferenceEquals(NetCombatCard.FromModel(card).ToCardModel(), card)))
            throw new InvalidOperationException("Invalid native candidates or combat-card identity");
        var running = RunManager.Instance.ActionExecutor.CurrentlyRunningAction;
        var action = running as PlayCardAction;
        if (action is null && !allowTurnChoice || action is not null &&
            (!ReferenceEquals(action.NetCombatCard.ToCardModel().Owner, player) || action.CompletionTask.IsCompleted))
            throw new InvalidOperationException("Selection is not owned by the live paid action");
        var request = new Selection(cards, minSelect, maxSelect, action);
        var selected = choose(request).ToArray();
        if (selected.Length < minSelect || selected.Length > maxSelect ||
            selected.Distinct(ReferenceEqualityComparer.Instance).Count() != selected.Length ||
            selected.Any(card => !cards.Any(candidate => ReferenceEquals(candidate, card))))
            throw new InvalidOperationException("Controlled choice violates native candidates or cardinality");
        observe?.Invoke(request, selected);
        Count++;
        return Task.FromResult<IEnumerable<CardModel>>(selected);
    }

    // The pinned 0.107.1 interface returns CardRewardSelection (changed in
    // 0.105), even when this combat-only driver rejects the reward request.
    public CardRewardSelection GetSelectedCardReward(IReadOnlyList<CardCreationResult> options,
        IReadOnlyList<CardRewardAlternative> alternatives) =>
        throw new InvalidOperationException("Combat suite must not resolve an unplanned card reward");

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        bool owned = ReferenceEquals(CardSelectCmd.Selector, this);
        scope.Dispose();
        if (!owned || CardSelectCmd.Selector is not null)
            throw new InvalidOperationException("Native selector scope was changed or leaked");
    }
}
