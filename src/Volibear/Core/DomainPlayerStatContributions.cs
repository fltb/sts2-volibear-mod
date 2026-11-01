using System;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

/// <summary>Observed enemy stat offsets, retained even when the native summed power reaches zero.
/// No native amount, applier, or generic Creature getter is changed.</summary>
public static partial class DomainPlayerStatContributions
{
    private sealed class Ledger(ICombatState combat)
    {
        internal readonly ICombatState Combat = combat;
        internal int StrengthDebt;
        internal int DexterityDebt;
        internal int StrengthEpoch, DexterityEpoch;
        internal readonly System.Collections.Generic.HashSet<Creature> StrengthPresentationSources = [], DexterityPresentationSources = [];
    }
    private static ConditionalWeakTable<Creature, Ledger> ledgers = new();
    private static ConditionalWeakTable<TenderPower, TenderReceipt> tenders = new();
    private static bool Handles(PowerModel power) => power is StrengthPower or DexterityPower;
    private static bool Enemy(Creature target, Creature? applier, CardModel? card) => card is null &&
        target.IsPlayer && target.CombatState is { } combat && combat.ContainsCreature(target) &&
        applier is { IsEnemy: true, IsPlayer: false } && ReferenceEquals(applier.CombatState, combat) &&
        combat.ContainsCreature(applier);
    private static Ledger GetLedger(Creature target)
    {
        if (ledgers.TryGetValue(target, out var ledger) && ReferenceEquals(ledger.Combat, target.CombatState)) return ledger;
        ledgers.Remove(target);
        ledger = new Ledger(target.CombatState!);
        ledgers.Add(target, ledger);
        return ledger;
    }
    internal static bool ShouldCancel(PowerModel power, Creature target, decimal delta,
        Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        bool cancel = ((Handles(power) && delta < 0 && (Enemy(target, applier, card) || IsTenderDebit(context, target))) ||
            (power is TenderPower && delta > 0 && Enemy(target, applier, card))) && DomainEnemyEffects.ActiveFor(target.CombatState);
        if (cancel && context is TenderContext tender)
        {
            tender.Receipt.DomainTouched = true;
            if (applier is null) Volibear.Presentation.PowerPresentationDomain.Suppressed(tender.Receipt.PresentationEnemy, power, card, delta, sourceCombat: tender.Receipt.Combat);
        }
        return cancel;
    }

    // Called by the one shared native PowerCmd commit adapter, immediately before mutation.
    internal static void Applied(PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (power is TenderPower tender && amount != 0 && Enemy(target, applier, card))
        {
            tenders.Remove(tender);
            tenders.Add(tender, new TenderReceipt(target.CombatState!, target) { PresentationEnemy = applier });
        }
        Commit(power, target, Math.Clamp((int)amount, -999999999, 999999999), applier, card, context);
    }
    internal static void AmountChanged(PowerModel power, int amount, Creature? applier, CardModel? card, PlayerChoiceContext context) =>
        Commit(power, power.Owner, Math.Clamp(amount, -999999999, 999999999) - power.Amount, applier, card, context);
    private static void Commit(PowerModel power, Creature target, int delta, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (!Handles(power) || !target.IsPlayer || target.CombatState is null) return;
        bool strength = power is StrengthPower;
        var ledger = GetLedger(target);
        ref int debt = ref (strength ? ref ledger.StrengthDebt : ref ledger.DexterityDebt);
        if (PossessCredit(context, target, strength, delta, ledger)) return;
        if (context is TenderContext { Observed: false } tender && ReferenceEquals(tender.Target, target) && tender.Strength == strength)
        {
            tender.Observed = true;
            tender.Committed = delta;
            var receipt = tender.Receipt;
            ref int outstanding = ref (strength ? ref receipt.StrengthOutstanding : ref receipt.DexterityOutstanding);
            ref int epoch = ref (strength ? ref receipt.StrengthEpoch : ref receipt.DexterityEpoch);
            int currentEpoch = strength ? ledger.StrengthEpoch : ledger.DexterityEpoch;
            if (epoch != currentEpoch) { outstanding = 0; epoch = currentEpoch; }
            if (tender.Debit && delta < 0)
            {
                debt = checked(debt - delta);
                outstanding = checked(outstanding - delta);
                RememberStatPresentationSource(ledger, strength, receipt.PresentationEnemy);
            }
            else if (!tender.Debit && delta > 0)
            {
                int removed = Math.Min(outstanding, delta);
                debt = Math.Max(0, debt - removed);
                outstanding -= removed;
            }
        }
        else if (delta < 0 && Enemy(target, applier, card))
        {
            debt = checked(debt - delta);
            RememberStatPresentationSource(ledger, strength, applier);
            PossessDebit(target, applier!, strength, -delta, ledger);
        }
        // Player costs/gains are independent signed contributions, not erasers of enemy debt.
    }
    private static void RememberStatPresentationSource(Ledger ledger, bool strength, Creature? enemy)
    {
        try { if (enemy is not null) (strength ? ledger.StrengthPresentationSources : ledger.DexterityPresentationSources).Add(enemy); }
        catch { }
    }
    private static int Debt(Creature target, bool strength)
    {
        if (!target.IsPlayer || !ledgers.TryGetValue(target, out var ledger) ||
            !ReferenceEquals(ledger.Combat, target.CombatState) || !ledger.Combat.ContainsCreature(target) ||
            !DomainEnemyEffects.ActiveFor(ledger.Combat)) return 0;
        int debt = strength ? ledger.StrengthDebt : ledger.DexterityDebt;
        try
        {
            if (debt > 0)
                foreach (var enemy in strength ? ledger.StrengthPresentationSources : ledger.DexterityPresentationSources)
                    if (enemy.Monster is { } source) Volibear.Presentation.PowerPresentationDomainScalars.Capture(enemy, source, ledger.Combat);
        }
        catch { }
        return debt;
    }
    public static int EffectiveStrength(Creature target) => target.GetPowerAmount<StrengthPower>() + Debt(target, true);
    public static int EffectiveDexterity(Creature target) => target.GetPowerAmount<DexterityPower>() + Debt(target, false);

    // Invoke from the FIRST active DomainPower only: a combat may contain several domain owners.
    private static bool Contributes(DomainPower domain)
    {
        if (!DomainPower.IsActive(domain.Owner) || !DomainEnemyEffects.ProtectsPlayer(domain.Owner) ||
            domain.Owner.CombatState is not { } combat) return false;
        foreach (var player in combat.Players)
            if (DomainPower.IsActive(player.Creature) && DomainEnemyEffects.ProtectsPlayer(player.Creature))
                return ReferenceEquals(player.Creature.GetPower<DomainPower>(), domain);
        return false;
    }
    public static decimal DamageContribution(DomainPower domain, Creature? dealer, ValueProp props) =>
        dealer is not null && Contributes(domain) && props.IsPoweredAttack() ? Debt(dealer, true) : 0;
    public static decimal BlockContribution(DomainPower domain, Creature target, ValueProp props, CardModel? cardSource) =>
        Contributes(domain) && props.IsPoweredCardOrMonsterMoveBlock() ? Debt(cardSource?.Owner.Creature ?? target, false) : 0;

    private static void Removing(PowerModel __instance)
    {
        if (!Handles(__instance) || __instance.Owner is not { IsPlayer: true } owner || __instance.Amount == 0 ||
            !ledgers.TryGetValue(owner, out var ledger) || !ReferenceEquals(ledger.Combat, owner.CombatState)) return;
        // Explicit cleansing removes every component. Automatic zero-sum detachment removes none.
        if (__instance is StrengthPower) { ledger.StrengthDebt = 0; ledger.StrengthEpoch++; }
        else { ledger.DexterityDebt = 0; ledger.DexterityEpoch++; }
    }
    public static void Reset() { ledgers = new(); tenders = new(); possessions = new(); }
}
