using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Content;

/// <summary>B02 · 防御 — 1 cost, gain 5 block (8 upgraded).</summary>
public sealed class Volibear_B02 : VolibearCard
{
    public Volibear_B02() : base(1, CardType.Skill, CardRarity.Basic, TargetType.Self, "b02") { }

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new BlockVar(5m, (ValueProp)0)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var owner = Owner ?? throw new System.InvalidOperationException("Card has no owner");
        await CreatureCmd.GainBlock(owner.Creature, Var<BlockVar>("Block").BaseValue,
                                    (ValueProp)0, cardPlay, false);
    }

    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

/// <summary>B03 · 霆爪 — 8 damage to one enemy, then 3 lightning damage to all enemies.</summary>
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
                .FromCard(this)
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

/// <summary>B04 · 挺身迎战 — 8 block, 6 damage, then engages the target.</summary>
public sealed class Volibear_B04 : VolibearCard
{
    public Volibear_B04() : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy, "b04") { }

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new DamageVar(6m, Move), new BlockVar(8m, (ValueProp)0)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var owner = Owner ?? throw new System.InvalidOperationException("Card has no owner");
        await CreatureCmd.GainBlock(owner.Creature, Var<BlockVar>("Block").BaseValue,
                                    (ValueProp)0, cardPlay, false);
        var target = cardPlay.Target;
        if (target is not null)
            await DamageCmd.Attack(Var<DamageVar>("Damage").BaseValue)
                .FromCard(this)
                .Targeting(target)
                .Execute(choiceContext);
        // TODO(engage): register the engage declaration and run the enemy's remaining moves.
    }

    protected override void OnUpgrade()
    {
        UpgradeVar("Damage", 3m);
        UpgradeVar("Block", 3m);
    }
}
