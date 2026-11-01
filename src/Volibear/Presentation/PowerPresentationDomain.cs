using System;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

/// <summary>Cosmetic adapter used ONLY by actual domain cancellation branches, never queries.</summary>
internal static class PowerPresentationDomain
{
    private sealed class Marker { }
    private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<object, Marker> Seen = new();
    internal static void Once(object ticket, Creature enemy, AbstractModel? source = null, CardModel? card = null, decimal amount = 1,
        MegaCrit.Sts2.Core.Combat.ICombatState? sourceCombat = null)
    {
        try
        {
            if (Seen.TryGetValue(ticket, out _)) return;
            Seen.Add(ticket, new());
            Suppressed(enemy, source, card, amount, sourceCombat: sourceCombat);
        }
        catch { }
    }

    internal static void RetaliationCancelled(PowerModel power, object[] args)
    {
        try
        {
            if (args[4] is not Creature || args[3] is not MegaCrit.Sts2.Core.ValueProps.ValueProp props) return;
            decimal amount = power is MegaCrit.Sts2.Core.Models.Powers.ReflectPower && args[2] is MegaCrit.Sts2.Core.Entities.Creatures.DamageResult result
                ? (props.IsPoweredAttack() ? result.BlockedDamage : 0)
                : power is MegaCrit.Sts2.Core.Models.Powers.ThornsPower &&
                  (props.IsPoweredAttack() || args[5] is MegaCrit.Sts2.Core.Models.Cards.Omnislice) ? power.Amount : 0;
            if (amount > 0) Suppressed(power.Owner, power, args[5] as CardModel, amount);
        }
        catch { }
    }

    internal static void Suppressed(Creature? enemy, AbstractModel? source = null, CardModel? card = null, decimal amount = 1,
        Creature? domainOwner = null, MegaCrit.Sts2.Core.Combat.ICombatState? sourceCombat = null)
    {
        try
        {
            if (enemy is not { IsEnemy: true, IsPlayer: false } || (sourceCombat ?? enemy.CombatState) is not { } combat ||
                (enemy.CombatState is not null && !ReferenceEquals(enemy.CombatState, combat))) return;
            if (domainOwner is not null)
            {
                if (ReferenceEquals(domainOwner.CombatState, combat) && DomainPower.IsActive(domainOwner))
                    GameplayPresentationReceipts.Publish("domain_suppression_applied", domainOwner, source, card, enemy, Math.Abs(amount));
                return;
            }
            foreach (var player in combat.Players)
                if (player.Creature is { } owner && owner.Player?.Character is VolibearCharacter && DomainPower.IsActive(owner))
                    GameplayPresentationReceipts.Publish("domain_suppression_applied", owner, source, card, enemy, Math.Abs(amount));
        }
        catch { /* No visual failure can change a suppression decision. */ }
    }
}
