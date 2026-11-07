using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

namespace Volibear.Core;

public enum BeastShape { None = 0, Claw = 1, Body = 2 }
public sealed record BeastChange(CardModel Card, BeastShape Shape, ICombatState Combat);

/// <summary>
/// Exhaust the material through the native command, then generate a native beast
/// card in its former pile. The material and the new card have independent identity.
/// Native commands own exhaust/generation reactions, overflow, clones and replay.
/// </summary>
public static class BeastForms
{
    // Only guards an unfinished consume/create transaction. It never changes a card's
    // behavior, survives a completed conversion, or needs serialization/reset hooks.
    private static readonly HashSet<CardModel> Converting = new(ReferenceEqualityComparer.Instance);

    /// <summary>Raised once after a new beast has entered combat and native generation reactions have settled.</summary>
    public static event Func<PlayerChoiceContext, BeastChange, Task>? Converted;

    public static BeastShape Shape(CardModel card) => card switch
    {
        Volibear_T01 => BeastShape.Claw,
        Volibear_T02 => BeastShape.Body,
        _ => BeastShape.None
    };

    /// <summary>
    /// Returns the generated card, the same card for an existing beast, or null when
    /// the operation cannot continue. Callers must use the returned native identity.
    /// "Same location" means the original pile with native Bottom insertion; an
    /// exhaust response filling the hand retains the engine's normal overflow rule.
    /// </summary>
    public static async Task<CardModel?> Convert(PlayerChoiceContext context, CardModel card, CardModel? source = null)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(card);
        card.AssertMutable();
        var combat = card.CombatState;
        var owner = card.Owner;
        var pile = card.Pile;
        if (combat is null || owner?.PlayerCombatState is null || pile?.IsCombatPile != true ||
            ReferenceEquals(card, card.DeckVersion))
            throw new InvalidOperationException("Beast conversion requires a combat card, never a master-deck entity.");
        if (!Live(owner, combat) || pile.Type is PileType.Play or PileType.Exhaust ||
            source is not null && !ReferenceEquals(source.Owner, owner)) return null;
        if (Shape(card) != BeastShape.None) return card;
        lock (Converting)
            if (!Converting.Add(card)) return null;

        try
        {
            var shape = card.Type == CardType.Attack ? BeastShape.Claw : BeastShape.Body;
            var upgraded = card.IsUpgraded;
            var retain = card.GetKeywordsWithSources(KeywordSources.Local).Contains(CardKeyword.Retain);
            var singleTurnRetain = BeastNativeRetain.SingleTurn(card);
            var coupon = CardModifier.Modifiers(card).OfType<NextPlayDiscount>().FirstOrDefault();
            // Validate and capture before consuming anything. Only this narrow adapter
            // reads native local costs; it never writes a native private field.
            var costs = BeastNativeCosts.Capture(card);
            var history = CombatManager.Instance.History;
            var historyBoundary = history.Entries.Count();
            await CardCmd.Exhaust(context, card);

            // Exhaust listeners may move/remove the material, fill the hand, end combat
            // or kill its owner. Do not undo any of those normal native reactions.
            if (!Live(owner, combat) || !ReferenceEquals(card.Owner, owner) ||
                !ReferenceEquals(pile.Type.GetPile(owner), pile)) return null;
            // A cooperating mod may veto the native command. Its successful Task is
            // not evidence of consumption, and old history cannot pay for a new form.
            if (!ReferenceEquals(CombatManager.Instance.History, history) ||
                !history.Entries.Skip(historyBoundary).OfType<CardExhaustedEntry>()
                    .Any(entry => ReferenceEquals(entry.Card, card))) return null;

            CardModel replacement = shape == BeastShape.Claw
                ? combat.CreateCard<Volibear_T01>(owner)
                : combat.CreateCard<Volibear_T02>(owner);
            if (upgraded) CardCmd.Upgrade(replacement);
            if (retain && card.GetKeywordsWithSources(KeywordSources.Local).Contains(CardKeyword.Retain))
                CardCmd.ApplyKeyword(replacement, CardKeyword.Retain);
            if (singleTurnRetain && BeastNativeRetain.SingleTurn(card)) replacement.GiveSingleTurnRetain();
            costs.ApplyTo(replacement);
            // Copy only our shared coupon marker, never arbitrary material modifiers,
            // enchantments, afflictions, CloneOf or DeckVersion. The native cost was
            // already transferred, so Grant would add an erroneous second discount.
            if (coupon is not null && CardModifier.Modifiers(card).Any(m => ReferenceEquals(m, coupon)))
                CardModifier.AddModifier<NextPlayDiscount>(replacement, 1);

            var result = await CardPileCmd.AddGeneratedCardToCombat(replacement, pile.Type, owner, CardPilePosition.Bottom);
            if (!result.success)
            {
                if (replacement.Pile is null) combat.RemoveCard(replacement);
                return null;
            }
            var generated = result.cardAdded;
            if (!ReferenceEquals(generated.Owner, owner) || Shape(generated) != shape) return null;
            if (Live(owner, combat))
            {
                GameplayPresentationReceipts.Publish("feral_target_confirmed", owner.Creature, source, generated);
                var listeners = Converted;
                if (listeners is not null)
                    foreach (Func<PlayerChoiceContext, BeastChange, Task> listener in listeners.GetInvocationList())
                    {
                        if (!Live(owner, combat) || !ReferenceEquals(generated.Owner, owner)) break;
                        await listener(context, new BeastChange(generated, shape, combat));
                    }
            }
            return generated;
        }
        finally
        {
            lock (Converting) Converting.Remove(card);
        }
    }

    // Kept as a startup API check; there are no beast Harmony patches to install.
    public static void Install() { BeastNativeCosts.Validate(); BeastNativeRetain.Validate(); }

    public static void SetZeroThisTurnOrUntilPlayed(CardModel card)
    {
        if (Shape(card) == BeastShape.None) throw new InvalidOperationException("Expected a beast form.");
        card.EnergyCost.SetThisTurnOrUntilPlayed(0, reduceOnly: true);
        card.InvokeEnergyCostChanged();
    }

    public static async Task PlayShape(PlayerChoiceContext context, CardModel card, CardPlay play, BeastShape shape)
    {
        if (card.CombatState is not { } combat || !Live(card.Owner, combat)) return;
        if (shape == BeastShape.Claw)
        {
            if (play.Target is { IsHittable: true } target)
                await DamageCmd.Attack(card.DynamicVars["Damage"].BaseValue).FromCard(card
#if STS2_BETA
                , null
#endif
                )
                    .Targeting(target).WithHitCount(2).Execute(context);
        }
        else if (shape == BeastShape.Body)
        {
            await CreatureCmd.GainBlock(card.Owner.Creature, card.DynamicVars["Block"].BaseValue, ValueProp.Move, play);
            if (Live(card.Owner, combat)) await LightningCmd.DealAllEnemies(context, card.DynamicVars["Lightning"].BaseValue, card);
        }
        else throw new ArgumentOutOfRangeException(nameof(shape));
    }

    private static bool Live(Player owner, ICombatState combat) => owner.Creature.IsAlive &&
        owner.PlayerCombatState is not null && ReferenceEquals(owner.Creature.CombatState, combat) &&
        CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding;
}
