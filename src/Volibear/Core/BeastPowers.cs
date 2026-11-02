using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

namespace Volibear.Core;

public static class BeastPowers
{
    private static bool installed;
    public static void Install()
    {
        if (installed) return;
        BeastForms.Converted += OnConverted;
        installed = true;
    }
    private static async Task OnConverted(PlayerChoiceContext context, BeastChange change)
    {
        // Snapshot actual native instances, not a process-global count or retained subscriptions.
        // A new battle's owner can never inherit listeners from the previous combat.
        foreach (var power in change.Card.Owner.Creature.Powers.OfType<BearSpiritPower>().ToArray())
            if (ReferenceEquals(power.Owner.CombatState, change.Combat))
                await power.AfterConversion(context);
    }
    internal static bool Active(PowerModel power) => power.Owner.IsAlive && power.Owner.Player?.PlayerCombatState is not null &&
        power.Owner.CombatState is not null && power.Owner.Powers.Contains(power) &&
        CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding;
    internal static (int Round, int Turn) Turn(PowerModel power) =>
        (power.Owner.CombatState!.RoundNumber, power.Owner.Player!.PlayerCombatState!.TurnNumber);
}

public sealed class BearSpiritPower : CustomPowerModel
{
    private sealed class Data
    {
        internal CardModel? Source;
        internal (int, int) ConversionTurn = (-1, -1);
        internal (int, int) ShapeTurn = (-1, -1);
    }
    protected override object InitInternalData() => new Data();
    private Data State => GetInternalData<Data>();
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override PowerInstanceType InstanceType => PowerInstanceType.Instanced;
    public CardModel SourceCard => IsMutable ? State.Source ?? ModelDb.Card<Volibear_R28>() : ModelDb.Card<Volibear_R28>();
    public override string CustomPackedIconPath => Presentation.VolibearIcons.BearSpirit;
    public override string CustomBigIconPath => Presentation.VolibearIcons.BearSpiritBig;
    public override List<(string, string)> Localization => new PowerLoc("熊灵侵染",
        "每回合首次兽化后抽{Amount}张牌，首次打出兽形时获得1雷势。回合开始抽牌后，可以兽化1张手牌。",
        "每回合首次兽化后抽{Amount}张牌，首次打出兽形时获得1雷势。回合开始抽牌后，可以兽化1张手牌。");
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        State.Source = cardSource ?? throw new InvalidOperationException("Bear Spirit requires its originating card.");
        BeastPowers.Install();
        return Task.CompletedTask;
    }
    internal async Task AfterConversion(PlayerChoiceContext context)
    {
        if (!BeastPowers.Active(this) || State.ConversionTurn == BeastPowers.Turn(this)) return;
        State.ConversionTurn = BeastPowers.Turn(this); // Mark before draw/reentrant conversion.
        Flash();
        await CardPileCmd.Draw(context, Amount, Owner.Player!);
    }
    public override async Task AfterPlayerTurnStart(PlayerChoiceContext context, Player player)
    {
        if (!ReferenceEquals(Owner.Player, player) || !BeastPowers.Active(this)) return;
        // Domain's Early hook has already consumed its normal-draw duration.
        var source = State.Source ?? throw new InvalidOperationException("Missing Bear Spirit source.");
        // A resolved Power card has no pile, so native CardModel.CombatState is null.
        // The installed power owns this later effect's lifetime, not its source card.
        var hand = PileType.Hand.GetPile(player);
        var candidates = hand.Cards.Where(c => !ReferenceEquals(c, source)).ToArray();
        if (candidates.Length == 0) return;
        var selected = (await CardSelectCmd.FromHand(context, player,
            new CardSelectorPrefs(new LocString("cards", source.Id.Entry + ".beastSelectionPrompt"), 0, 1),
            c => candidates.Contains(c), source)).ToArray();
        foreach (var card in selected.Distinct(ReferenceEqualityComparer.Instance).Cast<CardModel>())
        {
            if (!BeastPowers.Active(this)) break;
            if (!ReferenceEquals(card.Pile, hand)) continue;
            var replacement = await BeastForms.Convert(context, card, source);
            if (replacement is not null && !ReferenceEquals(replacement, card))
                GameplayPresentationReceipts.Publish("feral_batch_committed", Owner, source, amount: 1);
        }
    }
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        if (!BeastPowers.Active(this) || !ReferenceEquals(play.Card.Owner.Creature, Owner) ||
            play.PlayIndex != 0 || BeastForms.Shape(play.Card) == BeastShape.None || State.ShapeTurn == BeastPowers.Turn(this)) return;
        State.ShapeTurn = BeastPowers.Turn(this);
        Flash();
        // Reuse the triggering card's exact native wrapper context. Power-application
        // listeners may request selection even though the force grant itself does not.
        await StormChargePower.Gain(CardResolutionHooks.CurrentChoices(play.Card), Owner, 1, State.Source);
    }
}

public sealed class WildernessPower : CustomPowerModel
{
    private sealed class Data
    {
        internal CardModel? Source;
        internal (int, int) ClawTurn = (-1, -1);
    }
    protected override object InitInternalData() => new Data();
    private Data State => GetInternalData<Data>();
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override PowerInstanceType InstanceType => PowerInstanceType.Instanced;
    public CardModel SourceCard => IsMutable ? State.Source ?? ModelDb.Card<Volibear_R30>() : ModelDb.Card<Volibear_R30>();
    public override string CustomPackedIconPath => Presentation.VolibearIcons.Wilderness;
    public override string CustomBigIconPath => Presentation.VolibearIcons.WildernessBig;
    public override List<(string, string)> Localization => new PowerLoc("我即荒野",
        "每回合首次打出爪形时，获得{Amount}格挡；每次打出躯形时，获得1能量。",
        "每回合首次打出爪形时，获得{Amount}格挡；每次打出躯形时，获得1能量。");
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        State.Source = cardSource ?? throw new InvalidOperationException("Wilderness requires its originating card.");
        return Task.CompletedTask;
    }
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        if (!BeastPowers.Active(this) || !ReferenceEquals(play.Card.Owner.Creature, Owner) || play.PlayIndex != 0) return;
        switch (BeastForms.Shape(play.Card))
        {
            case BeastShape.Claw when State.ClawTurn != BeastPowers.Turn(this):
                State.ClawTurn = BeastPowers.Turn(this);
                Flash();
                // Power-generated block receives native block modifiers, but is not
                // falsely attributed to a synthetic card play or the triggering claw.
                await CreatureCmd.GainBlock(Owner, Amount, ValueProp.Move, null);
                break;
            case BeastShape.Body:
                Flash();
                await PlayerCmd.GainEnergy(1, Owner.Player!);
                break;
        }
    }
}
