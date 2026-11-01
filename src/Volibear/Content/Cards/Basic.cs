using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;

namespace Volibear.Content;

/// <summary>B01 · 打击 — 1 cost, 6 damage (9 upgraded). Plain single-target attack.</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_B01")]
public sealed class Volibear_B01 : VolibearCard
{
    public Volibear_B01() : base(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy, "b01") { }

    protected override HashSet<CardTag> CanonicalTags => [CardTag.Strike];

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new DamageVar(6m, Move)];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        var target = cardPlay.Target;
        if (target is null) return;
        await DamageCmd.Attack(Var<DamageVar>("Damage").BaseValue)
            .FromCard(this)
            .Targeting(target)
            .Execute(choiceContext);
    }

    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}
