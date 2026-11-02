using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

namespace Volibear.Content;

internal static class HistoryEffects
{
    internal static bool Live(CardModel card) => card.Owner.Creature.IsAlive && card.Owner.Creature.CombatState is not null &&
        CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding;
    internal static Task Attack(PlayerChoiceContext context, CardModel card, Creature? target, decimal amount) =>
        Live(card) && target is { IsHittable: true }
            ? DamageCmd.Attack(amount).FromCard(card).Targeting(target).Execute(context) : Task.CompletedTask;
    internal static async Task Draw(PlayerChoiceContext context, CardModel card, decimal amount)
    { if (Live(card) && amount > 0) await CardPileCmd.Draw(context, amount, card.Owner); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C20")]
public sealed class Volibear_C20 : VolibearCard
{
    public Volibear_C20() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c20") { }
    public override List<(string, string)> Localization => new CardLoc("乘势追击", "造成{Damage:diff()}伤害。若本回合此前打出过攻击牌，抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(10m, Move), new CardsVar(2)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        var hadAttack = AttackHistory.PriorAttackCount(this) > 0;
        await HistoryEffects.Attack(context, this, play.Target, Value("Damage"));
        if (hadAttack) await HistoryEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 4m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U07")]
public sealed class Volibear_U07 : VolibearCard, ITargetCostCard
{
    public Volibear_U07() : base(3, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u07") { }
    public override List<(string, string)> Localization => new CardLoc("崩山", "造成{Damage:diff()}伤害。本回合每对该目标打出过1张攻击牌，本牌费用−1。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(28m, Move)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => HistoryEffects.Attack(context, this, play.Target, Value("Damage"));
    protected override void OnUpgrade() => UpgradeVar("Damage", 8m);
    public override bool TryModifyEnergyCostInCombat(CardModel card, decimal originalCost, out decimal modifiedCost)
    {
        modifiedCost = originalCost;
        if (!ReferenceEquals(card, this) || originalCost < 0 || card.EnergyCost.CostsX ||
            TargetCosts.TargetFor(card) is not { } target) return false;
        modifiedCost = Math.Max(0, originalCost - AttackHistory.PriorTargetAttackCount(card, target));
        return modifiedCost != originalCost;
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U20")]
public sealed class Volibear_U20 : VolibearCard
{
    public Volibear_U20() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u20") { }
    public override List<(string, string)> Localization => new CardLoc("势不可挡", "造成{Damage:diff()}伤害。若上一张打出的是攻击牌，获得{Energy:diff()}能量。");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(10m, Move), new DynamicVar("Energy", 2m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // This snapshot survives effect replay and nested plays, and (like frozen TS)
        // the previous card's type is not reset merely because a new turn started.
        var previousWasAttack = AttackHistory.PreviousType(this) == CardType.Attack;
        await HistoryEffects.Attack(context, this, play.Target, Value("Damage"));
        if (previousWasAttack && HistoryEffects.Live(this)) await PlayerCmd.GainEnergy(Value("Energy"), Owner);
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 4m); UpgradeVar("Energy", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U38")]
public sealed class Volibear_U38 : VolibearCard
{
    public Volibear_U38() : base(3, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u38") { }
    public override List<(string, string)> Localization => new CardLoc("雷势奔袭", "造成{Damage:diff()}伤害。本回合每造成1次雷伤，本牌费用−1。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(18m, Move)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => HistoryEffects.Attack(context, this, play.Target, Value("Damage"));
    protected override void OnUpgrade() => UpgradeVar("Damage", 6m);
    public override bool TryModifyEnergyCostInCombat(CardModel card, decimal originalCost, out decimal modifiedCost)
    {
        modifiedCost = originalCost;
        if (!ReferenceEquals(card, this) || originalCost < 0 || card.EnergyCost.CostsX) return false;
        modifiedCost = Math.Max(0, originalCost - LightningBatches.GetTurnCount(Owner.Creature));
        return modifiedCost != originalCost;
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R14")]
public sealed class Volibear_R14 : VolibearCard
{
    public Volibear_R14() : base(1, CardType.Power, CardRarity.Rare, TargetType.Self, "r14") { }
    public override List<(string, string)> Localization => new CardLoc("不休之猎", "{Cards:cond:>0?抽{Cards:diff()}张牌。|}每打出1张攻击牌后，本回合对同一目标的攻击牌费用降低1。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(0)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!HistoryEffects.Live(this)) return;
        await PowerCmd.Apply<EndlessHuntPower>(context, Owner.Creature, 1, Owner.Creature, this);
        await HistoryEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}

/// <summary>Native combat-scoped power with its own target ledger, not a multiplier
/// of the player's all-time attack history. Counts only while this power is deployed.</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_ENDLESS_HUNT_POWER")]
public sealed class EndlessHuntPower : CustomPowerModel
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/cost_reduce.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/cost_reduce.png";
    private TargetDiscountLedger<Creature> _targets = new();
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override List<(string, string)> Localization => new PowerLoc("不休之猎",
        "每打出一张单体攻击，本回合对该目标的非X费攻击再减费{Amount}。",
        "每打出一张单体攻击，本回合对该目标的非X费攻击再减费{Amount}。");

    public override Task BeforeCardPlayed(CardPlay play)
    {
        if (play.PlayIndex != 0 || !ReferenceEquals(play.Card.Owner.Creature, Owner)) return Task.CompletedTask;
        var snapshot = AttackHistory.Snapshot(play);
        if (snapshot.IsSingleTargetAttack && snapshot.Target is { } target)
        {
            _targets.Record(snapshot.TurnNumber, snapshot.PlayId, target, Amount);
            TargetCosts.RefreshHand(play.Card.Owner);
        }
        return Task.CompletedTask;
    }

    public override bool TryModifyEnergyCostInCombat(CardModel card, decimal originalCost, out decimal modifiedCost)
    {
        modifiedCost = originalCost;
        if (!ReferenceEquals(card.Owner.Creature, Owner) || card.Type != CardType.Attack ||
            card.TargetType != TargetType.AnyEnemy || card.EnergyCost.CostsX || originalCost < 0 ||
            card.Owner.PlayerCombatState is null || TargetCosts.TargetFor(card) is not { } target) return false;
        var reduction = _targets.Read(card.Owner.PlayerCombatState.TurnNumber, target, CardResolutionHooks.CurrentPlayId(card));
        modifiedCost = Math.Max(0, originalCost - reduction);
        return modifiedCost != originalCost;
    }

    protected override void AfterCloned() { base.AfterCloned(); _targets = new(); }
}
