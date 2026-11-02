using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear.Content;

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C14")]
public sealed class Volibear_C14 : VolibearCard
{
    public Volibear_C14() : base(2, CardType.Skill, CardRarity.Common, TargetType.Self, "c14") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆护身", "获得{Block:diff()}格挡。领域{Domain:diff()}。反雷{Retaliation:diff()}。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move), new DynamicVar("Domain", 1m), new DynamicVar("Retaliation", 3m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        if (DirectEffects.Live(this))
            await PowerCmd.Apply<ThunderGuardPower>(context, Owner.Creature, Value("Retaliation"), Owner.Creature, this);
    }
    protected override void OnUpgrade()
    {
        UpgradeVar("Block", 3m); UpgradeVar("Retaliation", 2m);
        RemoveKeyword(CardKeyword.Exhaust);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C19")]
public sealed class Volibear_C19 : VolibearCard
{
    public Volibear_C19() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self, "c19") { }
    public override List<(string, string)> Localization => new CardLoc("追猎准备", "选择1张手牌中的攻击牌，使其获得保留和蓄势{Prepared:diff()}。",
        ("selectionScreenPrompt", "选择1张攻击，使其获得保留与蓄势。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Prepared", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!DirectEffects.Live(this)) return;
        var selected = await CardSelectCmd.FromHand(context, Owner, new CardSelectorPrefs(SelectionScreenPrompt, 1),
            card => card.Type == CardType.Attack && !ReferenceEquals(card, this), this);
        foreach (var card in selected)
            if (DirectEffects.Live(this) && card.Pile?.Type == PileType.Hand)
                PreparedAttackBonus.Prepare(card, (int)Value("Prepared"), this);
    }
    protected override void OnUpgrade() => UpgradeVar("Prepared", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C25")]
public sealed class Volibear_C25 : VolibearCard
{
    public Volibear_C25() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self, "c25") { }
    public override List<(string, string)> Localization => new CardLoc("雷引", "获得{Charge:diff()}雷势。本回合下一张攻击减费1。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Charge", 1m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await StormChargePower.Gain(context, Owner.Creature, (int)Value("Charge"), this);
        await NextAttackDiscount.Grant(context, Owner.Creature, 1);
    }
    protected override void OnUpgrade() => UpgradeVar("Charge", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U08")]
public sealed class Volibear_U08 : VolibearCard
{
    public Volibear_U08() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u08") { }
    public override List<(string, string)> Localization => new CardLoc("暴怒撕咬", "获得{Block:diff()}格挡。造成{Damage:diff()}伤害，对咬痕目标追加{Bite:diff()}伤害。施加咬痕。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(6m, Move), new DamageVar(10m, Move), new DynamicVar("Bite", 6m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        var damage = Value("Damage") + (play.Target is { } target && BiteMarks.BeforePlay(this, target) ? Value("Bite") : 0m);
        await DirectEffects.Attack(context, this, play.Target, damage);
    }
    public override Task AfterDamageGiven(PlayerChoiceContext context, Creature? dealer, DamageResult result,
        ValueProp props, Creature target, CardModel? cardSource)
    {
        // Runs at the real hit receipt, BEFORE the ordinary segment's domain attachment.
        return ReferenceEquals(cardSource, this) && ReferenceEquals(dealer, Owner.Creature) && props.IsPoweredAttack()
            ? BiteMarks.Register(context, this, target) : Task.CompletedTask;
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Damage", 4m); UpgradeVar("Bite", 3m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U10")]
public sealed class Volibear_U10 : VolibearCard
{
    public Volibear_U10() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u10") { }
    public override List<(string, string)> Localization => new CardLoc("磨砺爪牙", "抽{Cards:diff()}张牌。下一张攻击强化{Training:diff()}。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(1), new DynamicVar("Training", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Draw(context, this, Value("Cards"));
        if (DirectEffects.Live(this)) await PowerCmd.Apply<NextAttackTrainingPower>(context, Owner.Creature, Value("Training"), Owner.Creature, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Cards", 1m); UpgradeVar("Training", 2m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U11")]
public sealed class Volibear_U11 : VolibearCard
{
    public Volibear_U11() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u11") { }
    public override List<(string, string)> Localization => new CardLoc("暴风再临", "本回合下一张攻击获得重演。");
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (DirectEffects.Live(this)) await PowerCmd.Apply<NextAttackReplayPower>(context, Owner.Creature, 1m, Owner.Creature, this);
    }
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U12")]
public sealed class Volibear_U12 : VolibearCard
{
    public Volibear_U12() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u12") { }
    public override List<(string, string)> Localization => new CardLoc("原始力量", "本轮雷伤增加等同于当前力量的数值。抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(1)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        var strength = Math.Max(0, DomainPlayerStatContributions.EffectiveStrength(Owner.Creature));
        if (strength > 0 && DirectEffects.Live(this))
            await PowerCmd.Apply<PrimalThunderPower>(context, Owner.Creature, strength, Owner.Creature, this);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U14")]
public sealed class Volibear_U14 : VolibearCard
{
    public Volibear_U14() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u14") { }
    public override List<(string, string)> Localization => new CardLoc("迎战准备", "获得{Block:diff()}格挡。本回合下一张迎战牌减费1。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(5m, Move)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await NextEngageDiscount.Grant(context, Owner.Creature);
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); RemoveKeyword(CardKeyword.Exhaust); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U39")]
public sealed class Volibear_U39 : VolibearCard
{
    public Volibear_U39() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u39") { }
    public override List<(string, string)> Localization => new CardLoc("雷暴先兆", "获得{Block:diff()}格挡。领域{Domain:diff()}。检索1张雷法。",
        ("selectionScreenPrompt", "选择1张雷法加入手牌。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(4m, Move), new DynamicVar("Domain", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        await ControlledEffects.Retrieve(context, this, PileType.Draw, CardCapabilities.IsThunderSpell, 1, false, false, SelectionScreenPrompt);
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R06")]
public sealed class Volibear_R06 : VolibearCard
{
    public Volibear_R06() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self, "r06") { }
    public override List<(string, string)> Localization => new CardLoc("天人合一", "获得{Strength:diff()}力量和{Block:diff()}格挡。本场战斗中，所有攻击牌与雷法强化{Training:diff()}。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<StrengthPower>("Strength", 3m), new BlockVar(10m, Move), new DynamicVar("Training", 3m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (DirectEffects.Live(this)) await PowerCmd.Apply<StrengthPower>(context, Owner.Creature, Value("Strength"), Owner.Creature, this);
        await DirectEffects.Block(this, play, Value("Block"));
        if (DirectEffects.Live(this)) await PowerCmd.Apply<UnifyPower>(context, Owner.Creature, Value("Training"), Owner.Creature, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Strength", 1m); UpgradeVar("Block", 4m); }
}
