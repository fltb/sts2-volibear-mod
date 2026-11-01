using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear.Content;

internal static class BeastSelection
{
    internal static bool Live(CardModel source) => source.Owner.Creature.IsAlive && source.CombatState is not null &&
        CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding;

    // Capture before any conversion-trigger draw. Newly drawn cards cannot enter a batch.
    internal static async Task Transform(PlayerChoiceContext context, CardModel source, int maximum,
        Func<CardModel, bool>? filter = null, bool optional = false, bool all = false,
        bool discount = true, bool oldDays = false, CardPlay? play = null)
    {
        if (!Live(source)) return;
        var hand = PileType.Hand.GetPile(source.Owner);
        var candidates = hand.Cards.Where(c => !ReferenceEquals(c, source) && (filter?.Invoke(c) ?? true)).ToArray();
        var count = Math.Min(maximum, candidates.Length);
        if (count == 0) return;
        var selected = all ? candidates : (await CardSelectCmd.FromHand(context, source.Owner,
            new CardSelectorPrefs(new LocString("cards", source.Id.Entry + ".beastSelectionPrompt"), optional ? 0 : count, count),
            c => candidates.Contains(c), source)).ToArray();
        foreach (var card in selected)
        {
            if (!Live(source)) break;
            if (!ReferenceEquals(card.Pile, hand)) continue;
            var shape = await BeastForms.Convert(context, card);
            // Display-only set-zero wording does NOT replace the shared -1 coupon.
            if (discount && (!oldDays || shape == BeastShape.Claw)) NextPlayDiscount.Grant(card);
            if (oldDays && shape == BeastShape.Body && Live(source))
                await CreatureCmd.GainBlock(source.Owner.Creature, 4m, ValueProp.Move, play);
        }
    }

    internal static async Task Search(PlayerChoiceContext context, CardModel source)
    {
        if (!Live(source)) return;
        var hand = PileType.Hand.GetPile(source.Owner);
        if (hand.Cards.Count >= CardPile.MaxCardsInHand) return;
        var draw = PileType.Draw.GetPile(source.Owner);
        if (draw.Cards.Count == 0) return;
        var selected = (await CardSelectCmd.FromCombatPile(context, draw, source.Owner,
            new CardSelectorPrefs(new LocString("cards", source.Id.Entry + ".selectionScreenPrompt"), 1), _ => true)).ToArray();
        foreach (var card in selected)
        {
            if (!Live(source) || hand.Cards.Count >= CardPile.MaxCardsInHand) break;
            if (ReferenceEquals(card.Pile, draw))
            {
                await CardPileCmd.Add(card, PileType.Hand);
                CardPresentationReceipts.Retrieved(card, source, PileType.Draw);
            }
        }
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U41")]
public sealed class Volibear_U41 : VolibearCard
{
    public Volibear_U41() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u41") { }
    public override List<(string, string)> Localization => new CardLoc("破皮见骨", "造成{Damage:diff()}伤害。兽化1张攻击手牌，其本回合下次打出时设为0费。",
        ("beastSelectionPrompt", "选择1张攻击手牌兽化。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(3m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (BeastSelection.Live(this) && play.Target is { IsHittable: true } target)
            await DamageCmd.Attack(Value("Damage")).FromCard(this).Targeting(target).Execute(context);
        await BeastSelection.Transform(context, this, 1, c => c.Type == CardType.Attack);
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U42")]
public sealed class Volibear_U42 : VolibearCard
{
    public Volibear_U42() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u42") { }
    public override List<(string, string)> Localization => new CardLoc("蛮荒护体", "获得{Block:diff()}格挡。兽化1张非攻击手牌，其本回合下次打出时设为0费。",
        ("beastSelectionPrompt", "选择1张非攻击手牌兽化。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(3m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (BeastSelection.Live(this)) await CreatureCmd.GainBlock(Owner.Creature, Value("Block"), Move, play);
        await BeastSelection.Transform(context, this, 1, c => c.Type != CardType.Attack);
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U43")]
public sealed class Volibear_U43 : VolibearCard
{
    public Volibear_U43() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u43") { }
    public override List<(string, string)> Localization => new CardLoc("循着本能", "检索1张牌，兽化1张手牌，其本回合下次打出时设为0费。",
        ("selectionScreenPrompt", "选择1张牌加入手牌。"), ("beastSelectionPrompt", "选择1张手牌兽化。"));
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await BeastSelection.Search(context, this);
        await BeastSelection.Transform(context, this, 1);
    }
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R27")]
public sealed class Volibear_R27 : VolibearCard
{
    public Volibear_R27() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self, "r27") { }
    public override List<(string, string)> Localization => new CardLoc("旧日重临", "兽化至多{Convert:diff()}张手牌。每张爪形本回合下次打出时设为0费；每张躯形使你获得4格挡。",
        ("beastSelectionPrompt", "选择至多{Amount}张手牌兽化。"));
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Convert", 2m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        BeastSelection.Transform(context, this, (int)Value("Convert"), optional: true, oldDays: true, play: play);
    protected override void OnUpgrade() => UpgradeVar("Convert", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R28")]
public sealed class Volibear_R28 : VolibearCard
{
    public Volibear_R28() : base(1, CardType.Power, CardRarity.Rare, TargetType.Self, "r28") { }
    public override List<(string, string)> Localization => new CardLoc("熊灵侵染", "打出及每回合开始，可选兽化1张手牌。每回合首次兽化后，抽{Cards:diff()}张牌。每回合首次打出兽形时，获得1雷势。",
        ("beastSelectionPrompt", "可以选择1张手牌兽化。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(1)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!BeastSelection.Live(this)) return;
        BeastPowers.Install();
        // Deploy BEFORE conversion so this instance also reacts to its initial conversion.
        await PowerCmd.Apply<BearSpiritPower>(context, Owner.Creature, Value("Cards"), Owner.Creature, this);
        await BeastSelection.Transform(context, this, 1, optional: true, discount: false);
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R29")]
public sealed class Volibear_R29 : VolibearCard
{
    public Volibear_R29() : base(3, CardType.Skill, CardRarity.Rare, TargetType.Self, "r29") { }
    public override List<(string, string)> Localization => new CardLoc("不再为人", "兽化所有手牌，其本回合下次打出时设为0费。");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        BeastSelection.Transform(context, this, CardPile.MaxCardsInHand, all: true);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R30")]
public sealed class Volibear_R30 : VolibearCard
{
    public Volibear_R30() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self, "r30") { }
    public override List<(string, string)> Localization => new CardLoc("我即荒野", "兽化1张手牌，其本回合下次打出时设为0费。每回合首次打出爪形时，获得{Block:diff()}格挡；每次打出躯形时，获得1能量。",
        ("beastSelectionPrompt", "选择1张手牌兽化。"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(6m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // Frozen ordering is conversion first, deployment second (unlike R28).
        await BeastSelection.Transform(context, this, 1);
        if (BeastSelection.Live(this))
            await PowerCmd.Apply<WildernessPower>(context, Owner.Creature, Value("Block"), Owner.Creature, this);
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}
