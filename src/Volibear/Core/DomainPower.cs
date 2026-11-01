using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

namespace Volibear.Core;

/// <summary>
/// Domain duration, attack attachment and drawn-card purification only.
/// Enemy-benefit suppression/cancelled resurrection are separate integration work;
/// this power does not pretend to implement those policies by removing whole powers.
/// </summary>
public sealed class DomainPower : CustomPowerModel
{
    private CardResolutionDrawClock? _drawClock;
    public override string CustomPackedIconPath => Presentation.VolibearIcons.Domain;
    public override string CustomBigIconPath => Presentation.VolibearIcons.DomainBig;
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public bool IsPermanent => Amount == CardResolutionDuration.Permanent;
    public override int DisplayAmount => IsPermanent ? 0 : Amount;
    public override LocString Description => IsPermanent
        ? new LocString("powers", Id.Entry + ".permanentDescription") : base.Description;
    protected override string SmartDescriptionLocKey => IsPermanent
        ? Id.Entry + ".permanentDescription" : base.SmartDescriptionLocKey;
    public override List<(string, string)> Localization => new PowerLoc(
        "领域", "领域剩余{Amount}轮。覆盖下次正常起手抽牌，抽完后扣1轮。每张实际攻击首段普通攻击后附加4点全体雷伤。抽到状态或诅咒时，净化消耗并补抽1张。",
        "领域剩余{Amount}轮。覆盖下次正常起手抽牌，抽完后扣1轮。每张实际攻击首段普通攻击后附加4点全体雷伤，重演共享机会。抽到状态或诅咒时，净化消耗并补抽1张。",
        ("permanentDescription", "领域持续本战。每张实际攻击首段普通攻击后附加4点全体雷伤；重演共享机会。抽到状态或诅咒时，净化消耗并补抽1张。"));

    public static bool IsActive(Creature owner) => owner.CombatState is not null && owner.IsAlive &&
        !CombatManager.Instance.IsOverOrEnding && owner.GetPowerAmount<DomainPower>() > 0;

    public static Task<DomainPower?> Open(PlayerChoiceContext context, Creature owner, int rounds,
                                          CardModel? card = null)
    {
        CardResolutionHooks.Install();
        var current = owner.GetPowerAmount<DomainPower>();
        CardResolutionDuration.Extend(current, rounds); // Validate without changing permanent state.
        if (!LightningBatches.CanUse(owner, out _)) return Task.FromResult<DomainPower?>(null);
        if (current == CardResolutionDuration.Permanent) return Task.FromResult(owner.GetPower<DomainPower>());
        return PowerCmd.Apply<DomainPower>(context, owner, rounds, owner, card);
    }

    public static Task<DomainPower?> OpenPermanent(PlayerChoiceContext context, Creature owner,
                                                   CardModel? card = null)
    {
        CardResolutionHooks.Install();
        if (!LightningBatches.CanUse(owner, out _)) return Task.FromResult<DomainPower?>(null);
        var current = owner.GetPowerAmount<DomainPower>();
        if (current == CardResolutionDuration.Permanent) return Task.FromResult(owner.GetPower<DomainPower>());
        return PowerCmd.Apply<DomainPower>(context, owner, CardResolutionDuration.Permanent - current, owner, card);
    }

    public override async Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        _drawClock = new CardResolutionDrawClock(CombatState.RoundNumber);
        await DomainRevivalEffects.AfterDomainOpened(Owner);
        await DomainSteamEruptionEffects.AfterDomainOpened(Owner);
    }

    public override async Task AfterPlayerTurnStartEarly(PlayerChoiceContext context, Player player)
    {
        if (!ReferenceEquals(Owner.Player, player)) return;
        // Native ResetPlayerTurn awaits the complete Draw(fromHandDraw:true), including
        // nested purification replacements, BEFORE this early hook. R28 should use the
        // normal AfterPlayerTurnStart hook, which consequently sees the expired domain.
        _drawClock ??= new CardResolutionDrawClock(CombatState.RoundNumber);
        if (_drawClock.TryConsumeNormalDraw(CombatState.RoundNumber) && !IsPermanent)
            await PowerCmd.Decrement(this);
    }

    public override async Task AfterCardDrawnEarly(PlayerChoiceContext context, CardModel card, bool fromHandDraw)
    {
        if (!ReferenceEquals(card.Owner.Creature, Owner) ||
            !CardResolutionHooks.TryBeginPurification(card, this)) return;
        if (CombatManager.Instance.IsOverOrEnding) return;
        // The exact drawn identity was muted before native Add/hand-entry hooks.
        // External exhaust listeners still run; the card's own harmful hooks do not.
        var purificationFrom = card.Pile?.Type ?? PileType.None;
        await CardCmd.Exhaust(context, card);
        CardPresentationReceipts.Purified(card, this, purificationFrom);
        if (!CombatManager.Instance.IsOverOrEnding)
            await CardPileCmd.Draw(context, 1m, card.Owner, fromHandDraw: false);
    }

    internal static async Task AttachAfterOrdinarySegment(PlayerChoiceContext context,
                                                          CardResolutionHooks.PlayScope scope)
    {
        var owner = scope.Card.Owner.Creature;
        if (scope.Card.Type != CardType.Attack || !scope.Gate.TryAttach(IsActive(owner))) return;
        await LightningCmd.DealAllEnemies(context, owner, 4m, scope.Card);
    }
}
