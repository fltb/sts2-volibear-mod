using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using BaseLib.Patches.Hooks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear.Content;

/// <summary>
/// Shared non-stacking next-play coupon. Native cost modifiers own expiration;
/// this BaseLib marker owns identity/non-stacking and is cloned with its card.
/// C15, R10, U25 and beast discounts must all grant this same coupon kind.
/// </summary>
public sealed class NextPlayDiscount : CardModifier, ICustomModel
{
    public static void Grant(CardModel card)
    {
        if (!DirectEffects.Live(card) || Modifiers(card).OfType<NextPlayDiscount>().Any()) return;
        // Add only on a new grant, never OnInitialApplication: native card cloning
        // already copies local cost modifiers, so a copied marker must not add twice.
        var presentation = CostPresentationReceipts.Capture(card);
        AddModifier<NextPlayDiscount>(card, 1);
        card.EnergyCost.AddThisTurnOrUntilPlayed(-1);
        card.InvokeEnergyCostChanged();
        CostPresentationReceipts.LocalReductionCommitted(presentation);
    }

    private void Clear()
    {
        if (Owner is { } card) RemoveModifier(card, this);
    }

    public override Task AfterCardPlayed(PlayerChoiceContext context, CardPlay play)
    {
        if (ReferenceEquals(Owner, play.Card) && play.PlayIndex == play.PlayCount - 1) Clear();
        return Task.CompletedTask;
    }

    public override Task AfterSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants)
    {
        if (Owner is { } card && participants.Contains(card.Owner.Creature)) Clear();
        return Task.CompletedTask;
    }

    public override Task AfterCombatEnd(CombatRoom room)
    {
        Clear();
        return Task.CompletedTask;
    }
}

/// <summary>Native temporary-strength accounting, including its native end-turn reversal.</summary>
public sealed class VolibearChargeStrengthPower : TemporaryStrengthPower, ICustomPower
{
    public override AbstractModel OriginModel => ModelDb.Card<Volibear_C17>();
    public string? CustomPackedIconPath => ModelDb.Power<FlexPotionPower>().PackedIconPath;
    public string? CustomBigIconPath => ModelDb.Power<FlexPotionPower>().ResolvedBigIconPath;
    public string? CustomBigBetaIconPath => ModelDb.Power<FlexPotionPower>().ResolvedBigIconPath;
}

internal static class ControlledEffects
{
    internal static async Task ExhaustAnother(PlayerChoiceContext context, CardModel source)
    {
        if (!DirectEffects.Live(source)) return;
        var selected = await CardSelectCmd.FromHand(context, source.Owner,
            new CardSelectorPrefs(CardSelectorPrefs.ExhaustSelectionPrompt, 1),
            card => !ReferenceEquals(card, source), source);
        foreach (var card in selected)
            if (DirectEffects.Live(source) && card.Pile?.Type == PileType.Hand && !ReferenceEquals(card, source))
                await CardCmd.Exhaust(context, card);
    }

    internal static async Task Retrieve(PlayerChoiceContext context, CardModel source, PileType from,
        Func<CardModel, bool> eligible, int maximum, bool optional, bool discount, LocString prompt)
    {
        if (!DirectEffects.Live(source)) return;
        var hand = PileType.Hand.GetPile(source.Owner);
        var space = MaxHandSizePatch.GetMaxHandSize(source.Owner, CardPile.MaxCardsInHand) - hand.Cards.Count;
        if (space <= 0) return;
        var pile = from.GetPile(source.Owner);
        var original = pile.Cards.ToArray();
        var count = Math.Min(Math.Min(space, maximum), original.Count(eligible));
        if (count <= 0) return;
        var selected = (await CardSelectCmd.FromCombatPile(context, pile, source.Owner,
            new CardSelectorPrefs(prompt, optional ? 0 : count, count), eligible)).ToArray();
        // Frozen recover() iterates original discard order, not UI click order.
        // Search follows the selected sequence, retaining the original card entities.
        var ordered = from == PileType.Discard ? original.Where(selected.Contains).ToArray() : selected;
        foreach (var card in ordered)
        {
            if (!DirectEffects.Live(source) || hand.Cards.Count >= MaxHandSizePatch.GetMaxHandSize(source.Owner, CardPile.MaxCardsInHand)) break;
            if (!ReferenceEquals(card.Pile, pile)) continue;
            await CardPileCmd.Add(card, PileType.Hand);
            CardPresentationReceipts.Retrieved(card, source, from);
            if (discount && card.Pile?.Type == PileType.Hand) NextPlayDiscount.Grant(card);
        }
    }

    internal static async Task Scry(PlayerChoiceContext context, CardModel source, int count, LocString prompt)
    {
        if (!DirectEffects.Live(source)) return;
        var draw = PileType.Draw.GetPile(source.Owner);
        // In this engine top is index 0 (CardPileCmd.Draw); no shuffle/refill here.
        var looked = draw.Cards.Take(count).ToArray();
        if (looked.Length == 0) return;
        HashSet<CardModel> selected;
        using (new ScryPresentationScope(context, source, looked))
            selected = (await CardSelectCmd.FromSimpleGrid(context, looked, source.Owner,
                new CardSelectorPrefs(prompt, 0, looked.Length))).ToHashSet();
        foreach (var card in looked)
        {
            if (!DirectEffects.Live(source)) break;
            if (selected.Contains(card) && ReferenceEquals(card.Pile, draw))
            {
                // A pile move, not CardCmd.Discard: no hand-discard event is invented.
                await CardPileCmd.Add(card, PileType.Discard);
                if (card.Pile?.Type == PileType.Discard)
                    GameplayPresentationReceipts.Publish("selected_card_discarded", source.Owner.Creature, source, card);
            }
        }
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C04")]
public sealed class Volibear_C04 : VolibearCard
{
    public Volibear_C04() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c04") { }
    public override List<(string, string)> Localization => new CardLoc("擂首一击", "造成{Damage:diff()}伤害。施加{Weak:diff()}虚弱。迎战。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(9m, Move), new PowerVar<WeakPower>("Weak", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        if (DirectEffects.Live(this) && play.Target is { IsHittable: true } target)
            await PowerCmd.Apply<WeakPower>(context, target, Value("Weak"), Owner.Creature, this);
        await DirectEffects.Engage(context, this, play.Target);
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C06")]
public sealed class Volibear_C06 : VolibearCard
{
    public Volibear_C06() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c06") { }
    public override List<(string, string)> Localization => new CardLoc("进逼", "造成{Damage:diff()}伤害。若目标打算攻击，获得{Block:diff()}格挡；否则抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(8m, Move), new BlockVar(6m, Move), new CardsVar(1)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // TS conditional(..., attack) chooses before damage/reactions can change intent.
        var attacking = play.Target?.Monster?.IntendsToAttack == true;
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        if (attacking) await DirectEffects.Block(this, play, Value("Block"));
        else await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 3m); UpgradeVar("Block", 2m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C07")]
public sealed class Volibear_C07 : VolibearCard
{
    public Volibear_C07() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c07") { }
    public override List<(string, string)> Localization => new CardLoc("追嗅", "造成{Damage:diff()}伤害。检索{Search:diff()}张攻击。",
        ("selectionScreenPrompt", "选择{Amount}张攻击加入手牌。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(8m, Move), new DynamicVar("Search", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        await ControlledEffects.Retrieve(context, this, PileType.Draw, card => card.Type == CardType.Attack,
            (int)Value("Search"), false, false, SelectionScreenPrompt);
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C13")]
public sealed class Volibear_C13 : VolibearCard
{
    public Volibear_C13() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self, "c13") { }
    public override List<(string, string)> Localization => new CardLoc("呼吸", "消耗1张手牌，抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(3)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await ControlledEffects.ExhaustAnother(context, this);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C15")]
public sealed class Volibear_C15 : VolibearCard
{
    public Volibear_C15() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self, "c15") { }
    public override List<(string, string)> Localization => new CardLoc("重整爪牙", "回收1张攻击或雷法，减费1。",
        ("selectionScreenPrompt", "选择1张攻击或雷法加入手牌。"));
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        ControlledEffects.Retrieve(context, this, PileType.Discard,
            card => card.Type == CardType.Attack || CardCapabilities.IsThunderSpell(card),
            1, false, true, SelectionScreenPrompt);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C17")]
public sealed class Volibear_C17 : VolibearCard
{
    public Volibear_C17() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self, "c17") { }
    public override List<(string, string)> Localization => new CardLoc("蓄力", "本回合获得{Strength:diff()}力量。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<StrengthPower>("Strength", 4m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (DirectEffects.Live(this))
            // BeforeApplied on TemporaryStrengthPower grants Strength. Do not apply twice.
            await PowerCmd.Apply<VolibearChargeStrengthPower>(context, Owner.Creature, Value("Strength"), Owner.Creature, this);
    }
    protected override void OnUpgrade() => UpgradeVar("Strength", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U13")]
public sealed class Volibear_U13 : VolibearCard
{
    public Volibear_U13() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u13") { }
    public override List<(string, string)> Localization => new CardLoc("力量归身", "获得{Strength:diff()}力量。将临时力量转为本场战斗持续生效的力量。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<StrengthPower>("Strength", 2m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!DirectEffects.Live(this)) return;
        await PowerCmd.Apply<StrengthPower>(context, Owner.Creature, Value("Strength"), Owner.Creature, this);
        var temporary = Owner.Creature.Powers.OfType<TemporaryStrengthPower>()
            .Where(power => power.Type == PowerType.Buff && power.Amount > 0).ToArray();
        foreach (var power in temporary)
        {
            if (!DirectEffects.Live(this)) break;
            // Native positive subclasses only supply OriginModel. Remove does not run
            // AfterSideTurnEnd's Strength reversal; negative restoration obligations stay.
            await PowerCmd.Remove(power);
        }
    }
    protected override void OnUpgrade() => UpgradeVar("Strength", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U15")]
public sealed class Volibear_U15 : VolibearCard
{
    public Volibear_U15() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u15") { }
    public override List<(string, string)> Localization => new CardLoc("暴风换气", "消耗1张手牌，抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(2)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await ControlledEffects.ExhaustAnother(context, this);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U17")]
public sealed class Volibear_U17 : VolibearCard
{
    public Volibear_U17() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u17") { }
    public override List<(string, string)> Localization => new CardLoc("古老直觉", "预见{Scry:diff()}。抽{Cards:diff()}张牌。",
        ("selectionScreenPrompt", "选择任意张牌移至弃牌堆，其余牌保持顺序。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Scry", 3m), new CardsVar(1)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await ControlledEffects.Scry(context, this, (int)Value("Scry"), SelectionScreenPrompt);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Scry", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U31")]
public sealed class Volibear_U31 : VolibearCard
{
    public Volibear_U31() : base(0, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u31") { }
    protected override bool HasEnergyCostX => true;
    public override List<(string, string)> Localization => new CardLoc("万钧连踏", "重复X次：造成{Damage:diff()}伤害，再对所有敌人造成{Lightning:diff()}雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(5m, Move), new DynamicVar("Lightning", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // Native wrapper captured payment once. No energy reread or second payment.
        var iterations = ResolveEnergyXValue();
        for (var hit = 0; hit < iterations && DirectEffects.Live(this); hit++)
        {
            await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
            await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        }
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R05")]
public sealed class Volibear_R05 : VolibearCard
{
    public Volibear_R05() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self, "r05") { }
    public override bool GainsBlock => true;
    public override List<(string, string)> Localization => new CardLoc("全身之力", "格挡变为{Multiplier:diff()}倍。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Multiplier", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!DirectEffects.Live(this)) return;
        var extra = Owner.Creature.Block * (Value("Multiplier") - 1m);
        // Native Entrench uses this exact Unpowered|Move path: no Dex/Frail reapplied.
        await CreatureCmd.GainBlock(Owner.Creature, extra, ValueProp.Unpowered | Move, play);
    }
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R08")]
public sealed class Volibear_R08 : VolibearCard
{
    public Volibear_R08() : base(3, CardType.Attack, CardRarity.Rare, TargetType.RandomEnemy, "r08") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆万钧", "随机攻击{Hits:diff()}次，每次造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Hits", 4m), new DamageVar(10m, Move), new DynamicVar("Lightning", 5m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        for (var hit = 0; hit < (int)Value("Hits") && DirectEffects.Live(this); hit++)
        {
            var candidates = Owner.Creature.CombatState!.HittableEnemies.ToArray();
            if (candidates.Length == 0) break;
            // Same RNG stream as AttackCommand.TargetingRandomOpponents. Freeze ONE
            // target for attack + lightning; replays consume fresh choices, as TS does.
            var target = Owner.RunState.Rng.CombatTargets.NextItem(candidates)!;
            await DirectEffects.Attack(context, this, target, Value("Damage"));
            await LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this);
        }
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 3m); UpgradeVar("Lightning", 3m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R10")]
public sealed class Volibear_R10 : VolibearCard
{
    public Volibear_R10() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self, "r10") { }
    public override List<(string, string)> Localization => new CardLoc("这场战斗尚未结束", "回收至多{Recover:diff()}张攻击，减费1。",
        ("selectionScreenPrompt", "选择至多{Amount}张攻击加入手牌。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Recover", 3m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        ControlledEffects.Retrieve(context, this, PileType.Discard, card => card.Type == CardType.Attack,
            (int)Value("Recover"), true, true, SelectionScreenPrompt);
    protected override void OnUpgrade() => UpgradeVar("Recover", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R17")]
public sealed class Volibear_R17 : VolibearCard, INativeLightningSpell
{
    public Volibear_R17() : base(0, CardType.Skill, CardRarity.Rare, TargetType.AnyEnemy, "r17") { }
    protected override bool HasEnergyCostX => true;
    public override List<(string, string)> Localization => new CardLoc("天雷决", "获得X{IfUpgraded:show:＋1}雷势。造成{Lightning:diff()}雷伤，共X{IfUpgraded:show:＋1}次。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 6m), new DynamicVar("Bonus", 0m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // Frozen x-cost.ts distinguishes paidX+upgrade here from U31's modified X
        // iterations. Native captured payment is shared by every effect replay.
        var effectiveX = EnergyCost.CapturedXValue + (int)Value("Bonus");
        await StormChargePower.Gain(context, Owner.Creature, effectiveX, this);
        if (play.Target is not { } target) return;
        for (var hit = 0; hit < effectiveX && DirectEffects.Live(this); hit++)
            await LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this);
    }
    protected override void OnUpgrade() => UpgradeVar("Bonus", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R25")]
public sealed class Volibear_R25 : VolibearCard
{
    public Volibear_R25() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self, "r25") { }
    public override List<(string, string)> Localization => new CardLoc("风暴重临", "领域{Domain:diff()}。检索至多{Search:diff()}张技能。",
        ("selectionScreenPrompt", "选择至多{Amount}张技能加入手牌。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Domain", 2m), new DynamicVar("Search", 2m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        await ControlledEffects.Retrieve(context, this, PileType.Draw, card => card.Type == CardType.Skill,
            (int)Value("Search"), true, false, SelectionScreenPrompt);
    }
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R31")]
public sealed class Volibear_R31 : VolibearCard
{
    public Volibear_R31() : base(2, CardType.Attack, CardRarity.Rare, TargetType.AnyEnemy, "r31") { }
    public override List<(string, string)> Localization => new CardLoc("天声震落", "获得{Block:diff()}格挡。领域{Domain:diff()}。移除目标格挡。造成{Damage:diff()}伤害，对所有敌人造成{Lightning:diff()}雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move), new DynamicVar("Domain", 1m), new DamageVar(20m, Move), new DynamicVar("Lightning", 6m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        if (DirectEffects.Live(this) && play.Target is { IsHittable: true } target)
        {
            var before = target.Block;
            await CreatureCmd.LoseBlock(target, target.Block);
            var removed = before - target.Block;
            if (removed > 0)
                GameplayPresentationReceipts.Publish("target_block_removed", Owner.Creature, this, this, target, removed);
        }
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
    }
    protected override void OnUpgrade()
    {
        UpgradeVar("Block", 4m); UpgradeVar("Domain", 1m);
        UpgradeVar("Damage", 8m); UpgradeVar("Lightning", 3m);
    }
}
