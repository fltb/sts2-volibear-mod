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
        var committed = 0;
        var visited = new HashSet<CardModel>(ReferenceEqualityComparer.Instance);
        foreach (var card in selected)
        {
            if (!Live(source)) break;
            if (!visited.Add(card) || !ReferenceEquals(card.Pile, hand)) continue;
            var replacement = await BeastForms.Convert(context, card, source);
            if (replacement is null) continue;
            var shape = BeastForms.Shape(replacement);
            if (!ReferenceEquals(replacement, card)) committed++;
            if (!Live(source) || !ReferenceEquals(replacement.Owner, source.Owner)) continue;
            // Display-only set-zero wording does NOT replace the shared -1 coupon.
            if (discount && (!oldDays || shape == BeastShape.Claw)) NextPlayDiscount.Grant(replacement);
            if (oldDays && shape == BeastShape.Body && Live(source))
                await CreatureCmd.GainBlock(source.Owner.Creature, 4m, ValueProp.Move, play);
        }
        if (committed > 0)
            GameplayPresentationReceipts.Publish("feral_batch_committed", source.Owner.Creature, source, amount: committed);
    }

    internal static async Task Search(PlayerChoiceContext context, CardModel source)
    {
        if (!Live(source)) return;
        var hand = PileType.Hand.GetPile(source.Owner);
        if (hand.Cards.Count >= MaxHandSizePatch.GetMaxHandSize(source.Owner, CardPile.MaxCardsInHand)) return;
        var draw = PileType.Draw.GetPile(source.Owner);
        if (draw.Cards.Count == 0) return;
        var selected = (await CardSelectCmd.FromCombatPile(context, draw, source.Owner,
            new CardSelectorPrefs(new LocString("cards", source.Id.Entry + ".selectionScreenPrompt"), 1), _ => true)).ToArray();
        foreach (var card in selected)
        {
            if (!Live(source) || hand.Cards.Count >= MaxHandSizePatch.GetMaxHandSize(source.Owner, CardPile.MaxCardsInHand)) break;
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
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(3m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (BeastSelection.Live(this) && play.Target is { IsHittable: true } target)
            await DamageCmd.Attack(Value("Damage")).FromCard(this
#if STS2_BETA
                , null
#endif
                ).Targeting(target).Execute(context);
        await BeastSelection.Transform(context, this, 1, c => c.Type == CardType.Attack);
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U42")]
public sealed class Volibear_U42 : VolibearCard
{
    public Volibear_U42() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u42") { }
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
    public override bool GainsBlock => true;
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
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        BeastSelection.Transform(context, this, CardPile.MaxCardsInHand, all: true);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R30")]
public sealed class Volibear_R30 : VolibearCard
{
    public Volibear_R30() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self, "r30") { }
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
