using System.Collections.Generic;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

namespace Volibear.Content;

// Ordering follows the frozen executable TS compositions, not the prose sentence order.
internal static class PersistentEffects
{
    internal static Task<T?> Deploy<T>(PlayerChoiceContext context, CardModel card, decimal amount)
        where T : PowerModel => PowerCmd.Apply<T>(context, card.Owner.Creature, amount, card.Owner.Creature, card);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U02")]
public sealed class Volibear_U02 : VolibearCard
{
    public Volibear_U02() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.AllEnemies, "u02") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 6m), new DynamicVar("Conduction", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        await PersistentEffects.Deploy<StormConductionPower>(context, this, Value("Conduction"));
    }
    protected override void OnUpgrade() { UpgradeVar("Lightning", 3m); UpgradeVar("Conduction", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U03")]
public sealed class Volibear_U03 : VolibearCard
{
    public Volibear_U03() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u03") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(5m, Move), new DynamicVar("Decay", 6m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await StandingPower.Deploy(context, Owner.Creature, (int)Value("Decay"), this);
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Decay", -3m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U04")]
public sealed class Volibear_U04 : VolibearCard
{
    public Volibear_U04() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u04") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(6m, Move), new DynamicVar("Strength", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await PersistentEffects.Deploy<BattleScarsPower>(context, this, Value("Strength"));
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Strength", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U19")]
public sealed class Volibear_U19 : VolibearCard
{
    public Volibear_U19() : base(2, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u19") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Draw", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Draw(context, this, Value("Draw"));
        await DomainPower.Open(context, Owner.Creature, 1, this);
        await PersistentEffects.Deploy<LingeringStormPower>(context, this, 1);
    }
    protected override void OnUpgrade() => UpgradeVar("Draw", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U21")]
public sealed class Volibear_U21 : VolibearCard
{
    public Volibear_U21() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u21") { }
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => PersistentEffects.Deploy<ThunderAftershockPower>(context, this, 1);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U25")]
public sealed class Volibear_U25 : VolibearCard
{
    public Volibear_U25() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u25") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Draw", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Draw(context, this, 1);
        await PersistentEffects.Deploy<PreyStillStandsPower>(context, this, Value("Draw"));
    }
    protected override void OnUpgrade() => UpgradeVar("Draw", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U26")]
public sealed class Volibear_U26 : VolibearCard
{
    public Volibear_U26() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u26") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Strength", 1m), new DynamicVar("Storm", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // uncommon.ts deploys the per-instance responder BEFORE initial strength.
        await PersistentEffects.Deploy<GrowingFuryPower>(context, this, Value("Strength"));
        await PowerCmd.Apply<StrengthPower>(context, Owner.Creature, 1, Owner.Creature, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Strength", 1m); UpgradeVar("Storm", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U32")]
public sealed class Volibear_U32 : VolibearCard
{
    public Volibear_U32() : base(2, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u32") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Discount", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DomainPower.Open(context, Owner.Creature, 1, this);
        await WelcomeThunderPower.Prepare(context, Owner.Creature, (int)Value("Discount"), this);
        await PersistentEffects.Deploy<WelcomeThunderPower>(context, this, Value("Discount"));
    }
    protected override void OnUpgrade() { EnergyCost.UpgradeBy(-1); UpgradeVar("Discount", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U34")]
public sealed class Volibear_U34 : VolibearCard
{
    public Volibear_U34() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u34") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(4m, Move), new DynamicVar("Armor", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await PersistentEffects.Deploy<ThunderArmorPower>(context, this, Value("Armor"));
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Armor", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R02")]
public sealed class Volibear_R02 : VolibearCard
{
    public Volibear_R02() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self, "r02") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // rare.ts becomes immovable before granting its card block.
        await ImmovableBodyPower.Deploy(context, Owner.Creature, this);
        await DirectEffects.Block(this, play, Value("Block"));
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R16")]
public sealed class Volibear_R16 : VolibearCard
{
    public Volibear_R16() : base(1, CardType.Power, CardRarity.Rare, TargetType.Self, "r16") { }
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(0m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await PersistentEffects.Deploy<BattleBodyPower>(context, this, 1);
        if (IsUpgraded) await DirectEffects.Block(this, play, Value("Block"));
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 5m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R18")]
public sealed class Volibear_R18 : VolibearCard, ITomeCard
{
    public Volibear_R18() : base(2, CardType.Power, CardRarity.Rare, TargetType.AllEnemies, "r18") { }
    // Dusty Tome has no default Ancient-rarity candidate in this fixed 89-card
    // design. BaseLib's supported interface selects this existing card; the
    // native relic still owns its upgrade, permanent-deck add and save identity.
    public MegaCrit.Sts2.Core.Models.CharacterModel TomeCharacter =>
        MegaCrit.Sts2.Core.Models.ModelDb.Character<VolibearCharacter>();
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 6m), new DynamicVar("Pool", 4m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        await PersistentEffects.Deploy<ThunderPoolPower>(context, this, Value("Pool"));
    }
    protected override void OnUpgrade() { UpgradeVar("Lightning", 3m); UpgradeVar("Pool", 2m); }
}
