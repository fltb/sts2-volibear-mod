using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
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

// Small native-command adapters only. Each card below declares and orders its own effects;
// neither a card-id dispatch table nor a text-driven card interpreter lives here.
internal static partial class DirectEffects
{
    internal static async Task Attack(PlayerChoiceContext context, CardModel card, Creature? target,
                                      decimal damage, int hits = 1)
    {
        if (!Live(card) || target is null || !target.IsHittable) return;
        await DamageCmd.Attack(damage).FromCard(card).Targeting(target).WithHitCount(hits).Execute(context);
    }

    internal static async Task AttackAll(PlayerChoiceContext context, CardModel card, decimal damage)
    {
        if (!Live(card)) return;
        await DamageCmd.Attack(damage).FromCard(card)
            .TargetingAllOpponents(card.Owner.Creature.CombatState!).Execute(context);
    }

    internal static Task Block(CardModel card, CardPlay play, decimal amount) => Live(card)
        ? CreatureCmd.GainBlock(card.Owner.Creature, amount, ValueProp.Move, play) : Task.CompletedTask;
    internal static Task Draw(PlayerChoiceContext context, CardModel card, decimal count) => Live(card) && count > 0
        ? CardPileCmd.Draw(context, count, card.Owner) : Task.CompletedTask;
    internal static Task Energy(CardModel card, decimal amount) => Live(card) && amount > 0
        ? PlayerCmd.GainEnergy(amount, card.Owner) : Task.CompletedTask;
    internal static Task WeakAll(PlayerChoiceContext context, CardModel card, decimal amount) => Live(card)
        ? PowerCmd.Apply<WeakPower>(context, card.Owner.Creature.CombatState!.HittableEnemies.ToArray(),
            amount, card.Owner.Creature, card) : Task.CompletedTask;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C01")]
public sealed class Volibear_C01 : VolibearCard
{
    public Volibear_C01() : base(0, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c01") { }
    public override List<(string, string)> Localization => new CardLoc("逼近", "造成{Damage:diff()}伤害。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(6m, Move)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => DirectEffects.Attack(context, this, play.Target, Value("Damage"));
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C02")]
public sealed class Volibear_C02 : VolibearCard
{
    public Volibear_C02() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c02") { }
    public override List<(string, string)> Localization => new CardLoc("双爪", "造成{Damage:diff()}伤害，重复{Hits:diff()}次。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(5m, Move), new DynamicVar("Hits", 2m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => DirectEffects.Attack(context, this, play.Target, Value("Damage"), (int)Value("Hits"));
    protected override void OnUpgrade() => UpgradeVar("Damage", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C03")]
public sealed class Volibear_C03 : VolibearCard
{
    public Volibear_C03() : base(2, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c03") { }
    public override List<(string, string)> Localization => new CardLoc("轰雷重击", "造成{Damage:diff()}伤害。对全体造成{Lightning:diff()}雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(20m, Move), new DynamicVar("Lightning", 5m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 6m); UpgradeVar("Lightning", 2m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C05")]
public sealed class Volibear_C05 : VolibearCard
{
    public Volibear_C05() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c05") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆爪击", "领域{Domain:diff()}。造成{Damage:diff()}伤害。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(6m, Move), new DynamicVar("Domain", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C08")]
public sealed class Volibear_C08 : VolibearCard
{
    public Volibear_C08() : base(1, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c08") { }
    public override List<(string, string)> Localization => new CardLoc("撕开伤口", "造成{Damage:diff()}伤害。施加{Vulnerable:diff()}易伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(8m, Move), new PowerVar<VulnerablePower>("Vulnerable", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        if (DirectEffects.Live(this) && play.Target is { IsHittable: true } target)
            await PowerCmd.Apply<VulnerablePower>(context, target, Value("Vulnerable"), Owner.Creature, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 2m); UpgradeVar("Vulnerable", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C09")]
public sealed class Volibear_C09 : VolibearCard
{
    public Volibear_C09() : base(1, CardType.Attack, CardRarity.Common, TargetType.AllEnemies, "c09") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆横扫", "对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(6m, Move), new DynamicVar("Lightning", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.AttackAll(context, this, Value("Damage"));
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 2m); UpgradeVar("Lightning", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C10")]
public sealed class Volibear_C10 : VolibearCard
{
    public Volibear_C10() : base(2, CardType.Attack, CardRarity.Common, TargetType.AnyEnemy, "c10") { }
    public override List<(string, string)> Localization => new CardLoc("以牙还牙", "获得{Block:diff()}格挡。迎战。造成{Damage:diff()}＋吸收的伤害。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move), new DamageVar(6m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        var receipt = await DirectEffects.Engage(context, this, play.Target);
        // Read this target's actual block receipts, never the player's block delta.
        await DirectEffects.Attack(context, this, play.Target, Value("Damage") + receipt.Absorbed);
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Damage", 3m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C11")]
public sealed class Volibear_C11 : VolibearCard
{
    public Volibear_C11() : base(1, CardType.Skill, CardRarity.Common, TargetType.AnyEnemy, "c11") { }
    public override List<(string, string)> Localization => new CardLoc("正面迎敌", "获得{Block:diff()}格挡。迎战。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DirectEffects.Engage(context, this, play.Target);
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C12")]
public sealed class Volibear_C12 : VolibearCard
{
    public Volibear_C12() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self, "c12") { }
    public override List<(string, string)> Localization => new CardLoc("厚重皮毛", "获得{Block:diff()}＋力量的格挡。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(10m, Move)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        DirectEffects.Block(this, play, Value("Block") + Math.Max(0, DomainPlayerStatContributions.EffectiveStrength(Owner.Creature)));
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C18")]
public sealed class Volibear_C18 : VolibearCard
{
    public Volibear_C18() : base(1, CardType.Skill, CardRarity.Common, TargetType.AllEnemies, "c18") { }
    public override List<(string, string)> Localization => new CardLoc("显圣", "领域{Domain:diff()}。对全体施加{Weak:diff()}虚弱。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Domain", 1m), new PowerVar<WeakPower>("Weak", 2m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        await DirectEffects.WeakAll(context, this, Value("Weak"));
    }
    protected override void OnUpgrade() => UpgradeVar("Weak", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C21")]
public sealed class Volibear_C21 : VolibearCard
{
    public Volibear_C21() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self, "c21") { }
    public override List<(string, string)> Localization => new CardLoc("稳住阵脚", "获得{Block:diff()}格挡。领域{Domain:diff()}。抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(5m, Move), new DynamicVar("Domain", 1m), new CardsVar(2)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C22")]
public sealed class Volibear_C22 : VolibearCard
{
    public Volibear_C22() : base(2, CardType.Attack, CardRarity.Common, TargetType.AllEnemies, "c22") { }
    public override List<(string, string)> Localization => new CardLoc("雷震", "对全体造成{Damage:diff()}伤害和{Lightning:diff()}雷伤，重复{Hits:diff()}次。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(5m, Move), new DynamicVar("Lightning", 2m), new DynamicVar("Hits", 2m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // Native attack and its responses settle before EACH native lightning batch.
        for (var hit = 0; hit < (int)Value("Hits") && DirectEffects.Live(this); hit++)
        {
            await DirectEffects.AttackAll(context, this, Value("Damage"));
            await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        }
    }
    protected override void OnUpgrade() { UpgradeVar("Damage", 2m); UpgradeVar("Lightning", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C24")]
public sealed class Volibear_C24 : VolibearCard, INativeLightningSpell
{
    public Volibear_C24() : base(1, CardType.Skill, CardRarity.Common, TargetType.AllEnemies, "c24") { }
    public override List<(string, string)> Localization => new CardLoc("霹雳", "对全体造成{Lightning:diff()}雷伤。抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 6m), new CardsVar(1)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Lightning", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_C26")]
public sealed class Volibear_C26 : VolibearCard
{
    public Volibear_C26() : base(0, CardType.Skill, CardRarity.Common, TargetType.Self, "c26") { }
    public override List<(string, string)> Localization => new CardLoc("接地", "若本回合造成过雷伤，获得{Energy:diff()}能量。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new EnergyVar(2)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) =>
        CardResolutionHooks.PriorLightningCount(this) > 0 ? DirectEffects.Energy(this, Value("Energy")) : Task.CompletedTask;
    protected override void OnUpgrade() => UpgradeVar("Energy", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U05")]
public sealed class Volibear_U05 : VolibearCard
{
    public Volibear_U05() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u05") { }
    public override List<(string, string)> Localization => new CardLoc("挟山", "造成等同当前格挡的伤害。");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new CalculationBaseVar(0m), new ExtraDamageVar(1m),
         new CalculatedDamageVar(Move).WithMultiplier((card, _) => card.Owner.Creature.Block)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!DirectEffects.Live(this) || play.Target is not { IsHittable: true } target) return;
        await DamageCmd.Attack(Var<CalculatedDamageVar>("CalculatedDamage")).FromCard(this).Targeting(target).Execute(context);
    }
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U06")]
public sealed class Volibear_U06 : VolibearCard
{
    public Volibear_U06() : base(2, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u06") { }
    public override List<(string, string)> Localization => new CardLoc("三重撕裂", "造成{Damage:diff()}伤害，重复{Hits:diff()}次。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(8m, Move), new DynamicVar("Hits", 3m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => DirectEffects.Attack(context, this, play.Target, Value("Damage"), (int)Value("Hits"));
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U23")]
public sealed class Volibear_U23 : VolibearCard
{
    public Volibear_U23() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.AllEnemies, "u23") { }
    public override List<(string, string)> Localization => new CardLoc("迎风咆哮", "对全体施加{Weak:diff()}虚弱。获得{Block:diff()}格挡。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new PowerVar<WeakPower>("Weak", 1m), new BlockVar(9m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.WeakAll(context, this, Value("Weak"));
        await DirectEffects.Block(this, play, Value("Block"));
    }
    protected override void OnUpgrade() { UpgradeVar("Weak", 1m); UpgradeVar("Block", 3m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U24")]
public sealed class Volibear_U24 : VolibearCard
{
    public Volibear_U24() : base(2, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u24") { }
    public override List<(string, string)> Localization => new CardLoc("饮血而战", "造成{Damage:diff()}伤害，再造成{Lightning:diff()}雷伤，恢复造成雷伤的生命。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(21m, Move), new DynamicVar("Lightning", 3m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        if (!DirectEffects.Live(this) || play.Target is not { IsHittable: true } target) return;
        IReadOnlyList<LightningHit> hits = Array.Empty<LightningHit>();
        var hpLost = await LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this,
            resolved => hits = resolved);
        // Heal even if this lightning killed the final enemy; native Heal supports players
        // during combat ending. Blocked and overkill damage are not life stolen.
        if (Owner.Creature.IsAlive && hpLost > 0)
        {
            var before = Owner.Creature.CurrentHp;
            await CreatureCmd.Heal(Owner.Creature, hpLost);
            var recovered = Owner.Creature.CurrentHp - before;
            // Attribute only the actual recovered HP, in native receiver order (including redirects).
            foreach (var hit in hits)
            {
                var amount = Math.Min(recovered, hit.HpLost);
                if (amount <= 0) continue;
                GameplayPresentationReceipts.Publish("lifesteal_health_recovered", Owner.Creature,
                    this, this, hit.Receiver, amount);
                recovered -= amount;
            }
        }
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 7m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U27")]
public sealed class Volibear_U27 : VolibearCard
{
    public Volibear_U27() : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy, "u27") { }
    public override bool GainsBlock => true;
    public override List<(string, string)> Localization => new CardLoc("淬躯爪击", "造成{Damage:diff()}伤害。获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(8m, Move), new DynamicVar("BlockPerStrike", 2m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Attack(context, this, play.Target, Value("Damage"));
        // Unlike '此前', this includes the domain attachment triggered by this attack.
        await DirectEffects.Block(this, play, LightningBatches.GetTurnCount(Owner.Creature) * Value("BlockPerStrike"));
    }
    protected override void OnUpgrade() => UpgradeVar("Damage", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U28")]
public sealed class Volibear_U28 : VolibearCard, INativeLightningSpell
{
    public Volibear_U28() : base(2, CardType.Skill, CardRarity.Uncommon, TargetType.AnyEnemy, "u28") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆反扑", "获得{Block:diff()}格挡。迎战。对全体造成{Lightning:diff()}＋吸收的雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(12m, Move), new DynamicVar("Lightning", 4m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        var receipt = await DirectEffects.Engage(context, this, play.Target);
        await LightningCmd.DealAllEnemies(context, Value("Lightning") + receipt.Absorbed, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 5m); UpgradeVar("Lightning", 2m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U29")]
public sealed class Volibear_U29 : VolibearCard
{
    public Volibear_U29() : base(1, CardType.Power, CardRarity.Uncommon, TargetType.Self, "u29") { }
    public override List<(string, string)> Localization => new CardLoc("雷霆渐盛", "获得{Charge:diff()}雷势。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Charge", 2m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => StormChargePower.Gain(context, Owner.Creature, (int)Value("Charge"), this);
    protected override void OnUpgrade() => UpgradeVar("Charge", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U35")]
public sealed class Volibear_U35 : VolibearCard, INativeLightningSpell
{
    public Volibear_U35() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.AnyEnemy, "u35") { }
    public override List<(string, string)> Localization => new CardLoc("霹天雳地", "获得{Block:diff()}格挡。对全体造成{Lightning:diff()}雷伤。迎战。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(8m, Move), new DynamicVar("Lightning", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        await DirectEffects.Engage(context, this, play.Target);
    }
    protected override void OnUpgrade() { UpgradeVar("Block", 3m); UpgradeVar("Lightning", 2m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U36")]
public sealed class Volibear_U36 : VolibearCard
{
    public Volibear_U36() : base(0, CardType.Skill, CardRarity.Uncommon, TargetType.Self, "u36") { }
    public override List<(string, string)> Localization => new CardLoc("奔雷", "获得{Energy:diff()}能量。本回合此前造成过雷伤时，抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new EnergyVar(1), new CardsVar(1)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        var prior = CardResolutionHooks.PriorLightningCount(this);
        await DirectEffects.Energy(this, Value("Energy"));
        if (prior > 0) await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Energy", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U37")]
public sealed class Volibear_U37 : VolibearCard, INativeLightningSpell
{
    public Volibear_U37() : base(2, CardType.Skill, CardRarity.Uncommon, TargetType.AllEnemies, "u37") { }
    public override List<(string, string)> Localization => new CardLoc("风暴汇聚", "对全体造成{Lightning:diff()}雷伤。领域{Domain:diff()}。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 12m), new DynamicVar("Domain", 1m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await LightningCmd.DealAllEnemies(context, Value("Lightning"), this);
        await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
    }
    protected override void OnUpgrade() => UpgradeVar("Lightning", 4m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_U40")]
public sealed class Volibear_U40 : VolibearCard, INativeLightningSpell
{
    public Volibear_U40() : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.AnyEnemy, "u40") { }
    public override List<(string, string)> Localization => new CardLoc("雷路贯通", "造成{Lightning:diff()}雷伤。本回合此前已造成至少{Threshold:diff()}次雷伤时，获得{Energy:diff()}能量。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 8m), new DynamicVar("Threshold", 2m), new EnergyVar(2)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        var prior = CardResolutionHooks.PriorLightningCount(this);
        if (play.Target is { } target) await LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this);
        if (prior >= Value("Threshold")) await DirectEffects.Energy(this, Value("Energy"));
    }
    protected override void OnUpgrade() => UpgradeVar("Lightning", 4m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R01")]
public sealed class Volibear_R01 : VolibearCard
{
    public Volibear_R01() : base(3, CardType.Power, CardRarity.Rare, TargetType.Self, "r01") { }
    public override List<(string, string)> Localization => new CardLoc("风暴形态", "获得{Block:diff()}格挡。永久领域。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(10m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        await DomainPower.OpenPermanent(context, Owner.Creature, this);
    }
    protected override void OnUpgrade() { EnergyCost.UpgradeBy(-1); UpgradeVar("Block", 4m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R07")]
public sealed class Volibear_R07 : VolibearCard, INativeLightningSpell
{
    public Volibear_R07() : base(2, CardType.Skill, CardRarity.Rare, TargetType.AllEnemies, "r07") { }
    public override List<(string, string)> Localization => new CardLoc("天崩地裂", "对全体造成等同当前格挡的雷伤。");
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play) => LightningCmd.DealAllEnemies(context, Owner.Creature.Block, this);
    protected override void OnUpgrade() => EnergyCost.UpgradeBy(-1);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R09")]
public sealed class Volibear_R09 : VolibearCard, INativeLightningSpell
{
    public Volibear_R09() : base(2, CardType.Skill, CardRarity.Rare, TargetType.AllEnemies, "r09") { }
    public override List<(string, string)> Localization => new CardLoc("众敌皆来", "获得{Block:diff()}格挡。迎战全体。对全体造成等同吸收的雷伤。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new BlockVar(15m, Move)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, Value("Block"));
        if (!DirectEffects.Live(this)) return;
        // PerformAll snapshots native enemy order once, preserving each enemy's receipt.
        var receipts = await EngageCmd.PerformAll(context, this);
        await LightningCmd.DealAllEnemies(context, receipts.Sum(receipt => receipt.Absorbed), this);
    }
    protected override void OnUpgrade() => UpgradeVar("Block", 6m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R12")]
public sealed class Volibear_R12 : VolibearCard
{
    public Volibear_R12() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self, "r12") { }
    public override List<(string, string)> Localization => new CardLoc("解放本能", "抽牌至手牌达到{HandSize:diff()}张。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("HandSize", 7m)];
    protected override Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        // Frozen rare.ts requests this finite deficit ONCE. Native draw owns shuffle,
        // hand capacity and purification replacement; no 'until net gain' busy loop.
        var deficit = Math.Max(0m, Value("HandSize") - PileType.Hand.GetPile(Owner).Cards.Count);
        return DirectEffects.Draw(context, this, deficit);
    }
    protected override void OnUpgrade() => UpgradeVar("HandSize", 2m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R13")]
public sealed class Volibear_R13 : VolibearCard
{
    public Volibear_R13() : base(2, CardType.Skill, CardRarity.Rare, TargetType.Self, "r13") { }
    public override List<(string, string)> Localization => new CardLoc("重返蛮荒", "领域内恢复{Heal:diff()}生命；领域外获得领域{Domain:diff()}。获得{Strength:diff()}力量。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Heal", 4m), new DynamicVar("Domain", 1m), new PowerVar<StrengthPower>("Strength", 2m)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (!DirectEffects.Live(this)) return;
        // This branch is explicitly effect-time, unlike U36/U40's pre-play snapshot.
        if (DomainPower.IsActive(Owner.Creature)) await CreatureCmd.Heal(Owner.Creature, Value("Heal"));
        else await DomainPower.Open(context, Owner.Creature, (int)Value("Domain"), this);
        if (DirectEffects.Live(this)) await PowerCmd.Apply<StrengthPower>(context, Owner.Creature, Value("Strength"), Owner.Creature, this);
    }
    protected override void OnUpgrade() { UpgradeVar("Heal", 2m); UpgradeVar("Strength", 1m); }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R21")]
public sealed class Volibear_R21 : VolibearCard
{
    public Volibear_R21() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self, "r21") { }
    public override bool GainsBlock => true;
    public override List<(string, string)> Localization => new CardLoc("雷霆化身", "获得本回合雷伤次数×{BlockPerStrike:diff()}的格挡。抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("BlockPerStrike", 4m), new CardsVar(2)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Block(this, play, LightningBatches.GetTurnCount(Owner.Creature) * Value("BlockPerStrike"));
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("BlockPerStrike", 1m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R23")]
public sealed class Volibear_R23 : VolibearCard, INativeLightningSpell
{
    public Volibear_R23() : base(2, CardType.Skill, CardRarity.Rare, TargetType.AnyEnemy, "r23") { }
    public override List<(string, string)> Localization => new CardLoc("裂天", "造成{Lightning:diff()}雷伤，重复{Hits:diff()}次。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DynamicVar("Lightning", 8m), new DynamicVar("Hits", 3m)];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        if (play.Target is not { } target) return;
        for (var hit = 0; hit < (int)Value("Hits") && DirectEffects.Live(this) && target.IsHittable; hit++)
            await LightningCmd.Deal(context, new[] { target }, Value("Lightning"), this);
    }
    protected override void OnUpgrade() => UpgradeVar("Lightning", 3m);
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_R24")]
public sealed class Volibear_R24 : VolibearCard
{
    public Volibear_R24() : base(1, CardType.Skill, CardRarity.Rare, TargetType.Self, "r24") { }
    public override List<(string, string)> Localization => new CardLoc("雷涌", "获得等同本回合雷伤次数的能量。抽{Cards:diff()}张牌。");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new CardsVar(2)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        await DirectEffects.Energy(this, LightningBatches.GetTurnCount(Owner.Creature));
        await DirectEffects.Draw(context, this, Value("Cards"));
    }
    protected override void OnUpgrade() => UpgradeVar("Cards", 1m);
}
