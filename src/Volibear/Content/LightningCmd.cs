using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear.Content;

/// <summary>
/// Native non-attack lightning with an explicit batch boundary. Only these commands
/// count lightning: ordinary Unpowered damage is unrelated. The engine still owns
/// block, mitigation, damage redirection, HP loss and death.
/// </summary>
public static class LightningCmd
{
    // Existing card-facing signatures retained. Passive sources use the explicit-owner overloads.
    public static Task<int> DealAllEnemies(PlayerChoiceContext choiceContext, decimal amount,
                                           CardModel? card, ICombatState? state = null)
    {
        ArgumentNullException.ThrowIfNull(card);
        var owner = card.Owner.Creature;
        var combat = state ?? owner.CombatState;
        if (combat is null || !ReferenceEquals(combat, owner.CombatState)) return Task.FromResult(0);
        return DealCore(choiceContext, owner, combat.Enemies, amount, card, nativeCardOrigin: true);
    }

    public static Task<int> Deal(PlayerChoiceContext choiceContext, IEnumerable<Creature> targets,
                                 decimal amount, CardModel? card) => Deal(choiceContext, targets, amount, card, null);

    public static Task<int> Deal(PlayerChoiceContext choiceContext, IEnumerable<Creature> targets,
                                 decimal amount, CardModel? card,
                                 Action<IReadOnlyList<LightningHit>>? onResolved)
    {
        ArgumentNullException.ThrowIfNull(card);
        return DealCore(choiceContext, card.Owner.Creature, targets, amount, card, nativeCardOrigin: true, onResolved);
    }

    public static Task<int> DealAllEnemies(PlayerChoiceContext choiceContext, Creature owner,
                                           decimal amount, CardModel? card = null,
                                           ICombatState? state = null)
    {
        var combat = state ?? owner.CombatState;
        if (combat is null || !ReferenceEquals(combat, owner.CombatState)) return Task.FromResult(0);
        return Deal(choiceContext, owner, combat.Enemies, amount, card);
    }

    public static Task<int> Deal(PlayerChoiceContext choiceContext, Creature owner,
                                 IEnumerable<Creature> targets, decimal amount, CardModel? card = null) =>
        DealCore(choiceContext, owner, targets, amount, card, nativeCardOrigin: false);

    public static Task<int> Deal(PlayerChoiceContext choiceContext, Creature owner,
                                       IEnumerable<Creature> targets, decimal amount, CardModel? card,
                                        Action<IReadOnlyList<LightningHit>>? onResolved) =>
        DealCore(choiceContext, owner, targets, amount, card, nativeCardOrigin: false, onResolved);

    private static async Task<int> DealCore(PlayerChoiceContext choiceContext, Creature owner,
        IEnumerable<Creature> targets, decimal amount, CardModel? card, bool nativeCardOrigin,
        Action<IReadOnlyList<LightningHit>>? onResolved = null)
    {
        ArgumentNullException.ThrowIfNull(owner);
        ArgumentNullException.ThrowIfNull(targets);
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
        if (card is not null && !ReferenceEquals(card.Owner.Creature, owner))
            throw new ArgumentException("Lightning source card belongs to a different player.", nameof(card));
        if (!LightningBatches.CanUse(owner, out var combat)) return 0;

        // Freeze target identity and force BEFORE the first await. New enemies and
        // force gained by a response cannot retroactively join/modify this batch.
        var seen = new HashSet<Creature>(ReferenceEqualityComparer.Instance);
        var living = targets.Where(target => target is not null &&
            ReferenceEquals(target.CombatState, combat) && combat!.ContainsCreature(target) &&
            target.Side != owner.Side && target.IsHittable && seen.Add(target)).ToArray();
        if (living.Length == 0) return 0;
        var charge = StormChargePower.Current(owner);
        // R06/U10 affect ONLY the card's own native lightning, including dynamic
        // R07/R09 values. Explicit-owner domain/passive batches never inherit them,
        // even if they carry a source card for presentation. U12 affects EVERY batch.
        var cardBonus = nativeCardOrigin && card is not null
            ? CardDamageTraining.Current(card) + UnifyPower.NativeThunderBonus(card) : 0;
        var roundBonus = PrimalThunderPower.Current(owner);
        var snapshotAmount = amount + charge + cardBonus + roundBonus;
        // In particular base 0 + force N is NOT skipped. Even a nonempty 0+0
        // settlement follows the native zero-damage path and counts one batch.
        var scope = LightningBatches.Scope(combat!, owner);
        var ticket = scope.Counter.Begin(combat!.RoundNumber, LightningBatches.Turn(owner));
        try
        {
            var nativeResults = await CreatureCmd.Damage(choiceContext, living, snapshotAmount,
                ValueProp.Unpowered, owner, card);
            var results = nativeResults.Select(result => new LightningHit(result.Receiver,
                result.UnblockedDamage, result.BlockedDamage, result.OverkillDamage)).ToArray();
            var dealt = results.Sum(result => result.HpLost);
            // Read-only presentation receipt; never let an observer fail settlement.
            try { onResolved?.Invoke(Array.AsReadOnly(results)); }
            catch { /* Optional presentation cannot change the native result. */ }

            // A reset/end during native awaits closes this scope; don't recreate it
            // or announce post-combat effects. A turn transition invalidates the ticket.
            if (!scope.Counter.IsClosed && ReferenceEquals(owner.CombatState, combat) &&
                owner.Player?.PlayerCombatState is not null)
            {
                scope.Counter.Read(combat.RoundNumber, LightningBatches.Turn(owner));
                if (scope.Counter.Complete(ticket, out var count))
                {
                    var batch = new LightningBatch(ticket.Id, combat, owner, card,
                        ticket.Round, ticket.PlayerTurn, amount, charge, snapshotAmount,
                        Array.AsReadOnly(living), Array.AsReadOnly(results), count);
                    await LightningBatches.Notify(choiceContext, scope, batch);
                }
            }
            return dealt;
        }
        finally
        {
            // Exceptions and cancellation don't turn partial damage into a completed
            // batch. Complete already removed successful tickets, so this is harmless.
            scope.Counter.Abort(ticket);
        }
    }
}
