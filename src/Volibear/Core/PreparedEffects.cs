using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

namespace Volibear.Core;

public abstract class PreparedPower : CustomPowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override string CustomPackedIconPath => ModelDb.Power<StrengthPower>().PackedIconPath;
    public override string CustomBigIconPath => ModelDb.Power<StrengthPower>().ResolvedBigIconPath;
    protected bool Own(CardModel card) => ReferenceEquals(card.Owner.Creature, Owner);
}

public abstract class PendingCostPower : PreparedPower
{
    private bool spent;
    protected abstract bool Eligible(CardModel card);
    public override bool TryModifyEnergyCostInCombat(CardModel card, decimal originalCost, out decimal modifiedCost)
    {
        modifiedCost = originalCost;
        if (spent || !Own(card) || !Eligible(card) || card.EnergyCost.CostsX || originalCost < 0) return false;
        modifiedCost = Math.Max(0m, originalCost - Amount);
        return modifiedCost != originalCost;
    }
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        if (!spent && play.IsFirstInSeries && Own(play.Card) && Eligible(play.Card))
        {
            // Native SpendResources already ran; even zero-cost/X attacks consume it.
            spent = true;
            await PowerCmd.Remove(this);
        }
    }
    public override async Task AfterSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner)) await PowerCmd.Remove(this);
    }
}

public sealed class NextAttackDiscount : PendingCostPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/cost_reduce.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/cost_reduce.png";
    public override List<(string, string)> Localization => new PowerLoc("攻击减费", "本回合下一张实际打出的攻击减费{Amount}，最低0。", "本回合下一张实际打出的攻击减费{Amount}，最低0。同类待用减费取最大值，实际打出即消费。");
    protected override bool Eligible(CardModel card) => card.Type == CardType.Attack;
    public static async Task Grant(PlayerChoiceContext context, Creature owner, int amount)
    {
        if (amount <= 0 || !LightningBatches.CanUse(owner, out _)) return;
        var current = owner.GetPowerAmount<NextAttackDiscount>();
        if (amount > current) await PowerCmd.Apply<NextAttackDiscount>(context, owner, amount - current, owner, null);
    }
}

public sealed class NextEngageDiscount : PendingCostPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/cost_reduce.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/cost_reduce.png";
    public override List<(string, string)> Localization => new PowerLoc("迎战准备", "本回合下一张迎战牌减费1。", "本回合下一张迎战牌减费1。同类不叠加，实际打出即消费。");
    public static bool DeclaresEngage(CardModel card) => card is Volibear_B04 or Volibear_C04 or Volibear_C10 or Volibear_C11 or Volibear_U28 or Volibear_U35 or Volibear_R09;
    protected override bool Eligible(CardModel card) => DeclaresEngage(card);
    public static async Task Grant(PlayerChoiceContext context, Creature owner)
    {
        if (LightningBatches.CanUse(owner, out _) && !owner.HasPower<NextEngageDiscount>())
            await PowerCmd.Apply<NextEngageDiscount>(context, owner, 1m, owner, null);
    }
}

public sealed class NextAttackReplayPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/replay.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/replay.png";
    public override List<(string, string)> Localization => new PowerLoc("暴风再临", "本回合下一张攻击额外结算{Amount}次完整效果。", "本回合下一张攻击额外结算{Amount}次完整效果。重演不重复支付费用，不算重新打出。");
    public override int ModifyCardPlayCount(CardModel card, Creature? target, int playCount) =>
        Own(card) && card.Type == CardType.Attack ? checked(playCount + Amount) : playCount;
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        // GeneratePlayCount has frozen the native series; removing this cannot reduce it.
        if (play.IsFirstInSeries && Own(play.Card) && play.Card.Type == CardType.Attack)
            await PowerCmd.Remove(this);
    }
    public override async Task AfterSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner)) await PowerCmd.Remove(this);
    }
}

public sealed class CardDamageTraining : CardModifier, ICustomModel
{
    public override bool ApplyStacked(CardModifier incoming) { Amount += incoming.Amount; return true; }
    public override decimal ModifyDamageAdditive(Creature? target, decimal amount, ValueProp props, Creature? dealer, CardModel? cardSource) =>
        Owner is { } card && ReferenceEquals(cardSource, card) && ReferenceEquals(dealer, card.Owner.Creature) && props.IsPoweredAttack() ? Amount : 0m;
    public static int Current(CardModel card) => Modifiers(card).OfType<CardDamageTraining>().Sum(modifier => modifier.Amount);
}

public sealed class NextAttackTrainingPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/enhance.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/enhance.png";
    public override List<(string, string)> Localization => new PowerLoc("磨砺爪牙", "下一张实际打出的攻击本战每次伤害增加{Amount}。", "下一张实际打出的攻击本战每次伤害增加{Amount}。包括动态攻击与原生雷伤，复制继承，不改永久牌组。");
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        if (!play.IsFirstInSeries || !Own(play.Card) || play.Card.Type != CardType.Attack) return;
        var before = CardDamageTraining.Current(play.Card);
        CardModifier.AddModifier<CardDamageTraining>(play.Card, Amount);
        var added = CardDamageTraining.Current(play.Card) - before;
        if (added > 0)
            GameplayPresentationReceipts.Publish("card_enhancement_committed", Owner, this, play.Card, amount: added);
        await PowerCmd.Remove(this);
    }
}

public sealed class UnifyPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/enhance.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/enhance.png";
    public override List<(string, string)> Localization => new PowerLoc("天人合一", "本战攻击与雷法的自身攻击、原生雷伤增加{Amount}。", "本战攻击与雷法的自身攻击、原生雷伤增加{Amount}。不强化领域附雷或反雷。");
    public override decimal ModifyDamageAdditive(Creature? target, decimal amount, ValueProp props, Creature? dealer, CardModel? cardSource) =>
        ReferenceEquals(dealer, Owner) && cardSource is not null && Own(cardSource) && props.IsPoweredAttack() ? Amount : 0m;
    public static int NativeThunderBonus(CardModel card) => card.Type == CardType.Attack || CardCapabilities.IsThunderSpell(card)
        ? card.Owner.Creature.GetPowerAmount<UnifyPower>() : 0;
}

public sealed class PrimalThunderPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/thunder_growth.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/thunder_growth.png";
    public override List<(string, string)> Localization => new PowerLoc("原始力量", "本轮每批雷伤增加{Amount}。", "本轮每批雷伤增加{Amount}。数值在打出时按当前正力量锁定，敌方阶段结束后失效。");
    public override async Task AfterSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants)
    {
        // Engage performs a real enemy action, not an enemy-side end: it does not expire this.
        if (side == CombatSide.Enemy) await PowerCmd.Remove(this);
    }
    public static int Current(Creature owner) => Math.Max(0, owner.GetPowerAmount<PrimalThunderPower>());
}

public sealed class ThunderGuardPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/counter_thunder.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/counter_thunder.png";
    // Each C14 application must settle its OWN lightning batch, not sum into one hit.
    public override PowerInstanceType InstanceType => PowerInstanceType.Instanced;
    public override List<(string, string)> Localization => new PowerLoc("反雷", "受到每段攻击后，对攻击者造成{Amount}雷伤。", "受到每段攻击后，对攻击者造成{Amount}雷伤。完全格挡也触发；双方仍可受伤且战斗未结束时结算。下次玩家回合开始失效。");
    public override async Task AfterDamageReceived(PlayerChoiceContext context, Creature target, DamageResult result,
        ValueProp props, Creature? dealer, CardModel? cardSource)
    {
        if (!ReferenceEquals(target, Owner) || !Owner.IsHittable || !props.IsPoweredAttack() || dealer is null ||
            dealer.Side == Owner.Side || !dealer.IsHittable || !LightningBatches.CanUse(Owner, out var combat) ||
            !ReferenceEquals(dealer.CombatState, combat)) return;
        await LightningCmd.Deal(context, Owner, new[] { dealer }, Amount, null, hits =>
        {
            foreach (var hit in hits)
            {
                var resolved = hit.HpLost + hit.Blocked;
                if (resolved > 0)
                    GameplayPresentationReceipts.Publish("counter_thunder_resolved", Owner, this,
                        target: hit.Receiver, amount: resolved);
            }
        });
    }
    public override async Task BeforeSideTurnStart(PlayerChoiceContext context, CombatSide side,
        IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        if (participants.Contains(Owner)) await PowerCmd.Remove(this);
    }
}

/// <summary>Only C19 is fixed-segment-only; U10/R06 deliberately include calculated attacks.</summary>
public sealed class PreparedAttackBonus : CardModifier, ICustomModel
{
    private static readonly FieldInfo Calculated = AccessTools.Field(typeof(AttackCommand), "_calculatedDamageVar")
        ?? throw new MissingFieldException("AttackCommand._calculatedDamageVar");
    private List<(AttackCommand Command, long Play)> commands = [];
    public override bool ApplyStacked(CardModifier incoming) { Amount += incoming.Amount; return true; }
    public override void AfterClonedOnCard(CardModel card) { commands = []; completionCard = null; }
    public override Task BeforeAttack(AttackCommand command)
    {
        if (Owner is { } card && ReferenceEquals(command.ModelSource, card) && CardResolutionHooks.CurrentPlayId(card) is { } play)
        {
            commands.RemoveAll(entry => entry.Play != play);
            commands.Add((command, play));
        }
        return Task.CompletedTask;
    }
    public override Task AfterAttack(PlayerChoiceContext context, AttackCommand command)
    {
        commands.RemoveAll(entry => ReferenceEquals(entry.Command, command));
        return Task.CompletedTask;
    }
    public override decimal ModifyDamageAdditive(Creature? target, decimal amount, ValueProp props, Creature? dealer, CardModel? cardSource)
    {
        if (Owner is not { } card || !ReferenceEquals(cardSource, card) || !ReferenceEquals(dealer, card.Owner.Creature) || !props.IsPoweredAttack()) return 0m;
        if (CardResolutionHooks.CurrentPlayId(card) is { } play)
        {
            // Runtime truth comes from the actual native command, including non-Volibear cards.
            var active = commands.LastOrDefault(entry => entry.Play == play);
            return active.Command is not null && Calculated.GetValue(active.Command) is null ? Amount : 0m;
        }
        // Preview fallback is exact for the 89-card pool. Foreign mixed fixed/calculated
        // card previews cannot identify a segment; runtime above never guesses.
        return HasFixedAttack(card) ? Amount : 0m;
    }
    public static bool HasFixedAttack(CardModel card) =>
        card.Type == CardType.Attack && (card is VolibearCard ? card is not Volibear_U05 :
            card.DynamicVars.Values.Any(variable => variable is DamageVar) &&
            !card.DynamicVars.Values.Any(variable => variable is CalculatedDamageVar));
    private CardModel? completionCard;
    public override Task BeforeCardPlayed(CardPlay play)
    {
        if (ReferenceEquals(Owner, play.Card) && play.IsFirstInSeries)
        {
            completionCard = play.Card;
            completionCard.Played -= Complete;
            completionCard.Played += Complete;
        }
        return Task.CompletedTask;
    }
    private void Complete()
    {
        if (completionCard is not { } card) return;
        card.Played -= Complete;
        completionCard = null;
        if (ReferenceEquals(Owner, card)) RemoveModifier(card, this);
    }
    public static void Prepare(CardModel card, int amount, CardModel? source = null)
    {
        var retained = card.Keywords.Contains(CardKeyword.Retain);
        CardCmd.ApplyKeyword(card, CardKeyword.Retain);
        if (!retained && card.Keywords.Contains(CardKeyword.Retain))
            GameplayPresentationReceipts.Publish("card_retain_added", card.Owner.Creature, source, card);
        var before = Modifiers(card).OfType<PreparedAttackBonus>().Sum(modifier => modifier.Amount);
        AddModifier<PreparedAttackBonus>(card, amount);
        var added = Modifiers(card).OfType<PreparedAttackBonus>().Sum(modifier => modifier.Amount) - before;
        if (added > 0)
            GameplayPresentationReceipts.Publish("card_charge_changed", card.Owner.Creature, source, card, amount: added);
    }
}

/// <summary>Combat/owner/target identity, first actual play only. Never overwritten by replay.</summary>
public static class BiteMarks
{
    private static readonly ConditionalWeakTable<ICombatState, Dictionary<Creature, Dictionary<Creature, long>>> Marks = new();
    private static Dictionary<Creature, long> Ledger(Creature owner, ICombatState combat)
    {
        var owners = Marks.GetValue(combat, _ => new(ReferenceEqualityComparer.Instance));
        if (!owners.TryGetValue(owner, out var targets)) owners.Add(owner, targets = new(ReferenceEqualityComparer.Instance));
        return targets;
    }
    public static bool Has(Creature owner, Creature target) =>
        owner.CombatState is { } combat && Marks.TryGetValue(combat, out var owners) &&
        owners.TryGetValue(owner, out var targets) && targets.ContainsKey(target);

    public static bool BeforePlay(CardModel card, Creature target)
    {
        var combat = card.Owner.Creature.CombatState;
        if (combat is null) return false;
        return Ledger(card.Owner.Creature, combat).TryGetValue(target, out var first) && CardResolutionHooks.CurrentPlayId(card) != first;
    }
    public static async Task Register(PlayerChoiceContext context, CardModel card, Creature target)
    {
        var combat = card.Owner.Creature.CombatState;
        if (combat is null) return;
        var play = CardResolutionHooks.CurrentPlayId(card) ?? throw new InvalidOperationException("Bite requires native play identity.");
        // Record fully-blocked and lethal actual hits even when native powers cannot be added.
        if (!Ledger(card.Owner.Creature, combat).TryAdd(target, play)) return;
        GameplayPresentationReceipts.Publish("bite_mark_added", card.Owner.Creature, card, card, target);
        if (target.IsHittable && LightningBatches.CanUse(card.Owner.Creature, out _))
            await PowerCmd.Apply<BiteMarkPower>(context, target, 1m, card.Owner.Creature, card);
    }
}

public sealed class BiteMarkPower : PreparedPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/bite_mark.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/bite_mark.png";
    // This is an identity mark, not a removable Strength-like buff/debuff; Artifact must not erase it.
    public override PowerType Type => PowerType.None;
    public override PowerStackType StackType => PowerStackType.Single;
    public override PowerInstanceType InstanceType => PowerInstanceType.InstancedPerApplier;
    public override List<(string, string)> Localization => new PowerLoc("咬痕", "暴怒撕咬对已有咬痕的目标追加伤害。", "暴怒撕咬对已有咬痕的目标追加伤害。同一次实际出牌的重演读取施加前的咬痕。");
}
