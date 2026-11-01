using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using Volibear.Core;

namespace Volibear.Content;

// These are form definitions, not replacement entities for converted materials.
// Token rarity excludes them from ordinary rarity-based reward generation; inherited
// BaseLib.Pool metadata gives both canonical definitions the proper portrait/color pool.
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_T01")]
public sealed class Volibear_T01 : VolibearCard
{
    public Volibear_T01() : base(1, CardType.Attack, CardRarity.Token, TargetType.AnyEnemy, "t01", false) { }
    public override List<(string, string)> Localization => new CardLoc("裂骨之爪", "造成{Damage:diff()}伤害{Hits:diff()}次。");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    public override bool CanBeGeneratedInCombat => false;
    public override bool CanBeGeneratedByModifiers => false;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => base.ExtraHoverTips.Concat(MechanicHoverTips.ForText("兽形"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(7m, Move), new DynamicVar("Hits", 2m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => BeastForms.PlayShape(context, this, play, BeastShape.Claw);
    protected override void OnUpgrade() => UpgradeVar("Damage", 4m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_T02")]
public sealed class Volibear_T02 : VolibearCard
{
    public Volibear_T02() : base(1, CardType.Skill, CardRarity.Token, TargetType.AllEnemies, "t02", false) { }
    public override List<(string, string)> Localization => new CardLoc("风暴之躯", "获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。");
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    public override bool CanBeGeneratedInCombat => false;
    public override bool CanBeGeneratedByModifiers => false;
    public override bool GainsBlock => true;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => base.ExtraHoverTips.Concat(MechanicHoverTips.ForText("兽形"));
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(9m, Move), new DynamicVar("Lightning", 2m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => BeastForms.PlayShape(context, this, play, BeastShape.Body);
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Lightning", 1m); }
}
