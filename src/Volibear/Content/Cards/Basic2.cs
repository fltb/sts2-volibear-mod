using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Content;

/// <summary>B02 · 防御 — 1 cost, gain 5 block (8 upgraded).</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_B02")]
public sealed class Volibear_B02 : VolibearCard
{
    public Volibear_B02() : base(1, CardType.Skill, CardRarity.Basic, TargetType.Self, "b02") { }

    protected override HashSet<CardTag> CanonicalTags => [CardTag.Defend];

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new BlockVar(5m, Move)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var owner = Owner ?? throw new System.InvalidOperationException("Card has no owner");
        await CreatureCmd.GainBlock(owner.Creature, Var<BlockVar>("Block").BaseValue,
                                    Move, cardPlay, false);
    }

    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

/// <summary>B03 · 霆爪 — 8 damage to one enemy, then 3 lightning damage to all enemies.</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_B03")]
public sealed class Volibear_B03 : VolibearCard
{
    public Volibear_B03() : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy, "b03") { }

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new DamageVar(8m, Move), new DynamicVar("Lightning", 3m)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var target = cardPlay.Target;
        if (target is not null)
            await DamageCmd.Attack(Var<DamageVar>("Damage").BaseValue)
                .FromCard(this
#if STS2_BETA
                , null
#endif
                )
                .Targeting(target)
                .Execute(choiceContext);
        await LightningCmd.DealAllEnemies(choiceContext, Value("Lightning"), this);
    }

    protected override void OnUpgrade()
    {
        UpgradeVar("Damage", 3m);
        UpgradeVar("Lightning", 2m);
    }
}

/// <summary>B04 · 挺身迎战 — 10 block, 6 damage, then engages the target.</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_B04")]
public sealed class Volibear_B04 : VolibearCard
{
    public Volibear_B04() : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy, "b04") { }

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new DamageVar(6m, Move), new BlockVar(10m, Move)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var owner = Owner ?? throw new System.InvalidOperationException("Card has no owner");
        await CreatureCmd.GainBlock(owner.Creature, Var<BlockVar>("Block").BaseValue,
                                    Move, cardPlay, false);
        var target = cardPlay.Target;
        if (DirectEffects.Live(this) && target is { IsHittable: true })
            await DamageCmd.Attack(Var<DamageVar>("Damage").BaseValue)
                .FromCard(this
#if STS2_BETA
                , null
#endif
                )
                .Targeting(target)
                .Execute(choiceContext);
        if (target is not null)
            await DirectEffects.Engage(choiceContext, this, target);
    }

    protected override void OnUpgrade()
    {
        UpgradeVar("Damage", 3m);
        UpgradeVar("Block", 3m);
    }
}
