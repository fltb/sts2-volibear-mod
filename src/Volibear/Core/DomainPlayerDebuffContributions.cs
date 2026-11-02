using System;
using System.Linq;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>
/// Six player-debuff contributions. The native power and its lifetime remain native.
/// The retained ledger is a counterfactual without enemy additions, advanced by the
/// SAME observed native amount changes, not a claim that native durations have owners.
/// In particular a skipped native duration tick does not advance this ledger.
/// Shared PowerCmd commit adapters call the three methods below; this class never
/// vetoes an unattributed global Apply or guesses origin from the active combat side.
/// </summary>
public static partial class DomainPlayerDebuffContributions
{
    private sealed class Receipt(ICombatState combat, Creature owner, int actual, int retained)
    {
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Owner = owner;
        internal int Actual = actual;
        internal int Retained = retained;
        internal readonly System.Collections.Generic.HashSet<Creature> PresentationSources = [];
    }
    private static ConditionalWeakTable<PowerModel, Receipt> receipts = new();
    private static bool installed;
    internal const string HarmonyId = "Volibear.DomainPlayerDebuffContributions";

    internal static bool Handles(PowerModel power) => power is WeakPower or FrailPower or VulnerablePower
        or ShrinkPower or ConstrictPower or ChainsOfBindingPower;

    private static bool Enemy(PowerModel power, Creature target, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (card is not null || !target.IsPlayer || target.CombatState is not { } combat) return false;
        var origin = applier;
        if (origin is null && power is WeakPower && nullSources.TryGetValue(context, out var known) &&
            known.Targets.Contains(target) && ReferenceEquals(known.Combat, combat)) origin = known.Source;
        return origin is { IsEnemy: true, IsPlayer: false } && ReferenceEquals(origin.CombatState, combat) &&
            combat.ContainsCreature(origin) && combat.ContainsCreature(target) &&
            ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState());
    }

    /// <summary>Call after native precommit awaits, before history or mutation.</summary>
    internal static bool ShouldCancel(PowerModel power, Creature target, decimal delta,
        Creature? applier, CardModel? card, PlayerChoiceContext context) => false;
    // Debuffs now commit normally: Domain temporarily mutes their contributions while
    // native duration ticks/removal continue, so leaving Domain resumes only live state.

    /// <summary>Call immediately before the real ApplyInternal. Zero is a native no-op.</summary>
    internal static void Applied(PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (!Handles(power) || !target.IsPlayer || target.CombatState is not { } combat || amount == 0m) return;
        int actual = Math.Clamp((int)amount, -999999999, 999999999);
        receipts.Remove(power);
        receipts.Add(power, new Receipt(combat, target, actual, Enemy(power, target, applier, card, context) ? 0 : actual));
        RememberPresentationSource(power, target, applier, card, context);
    }

    /// <summary>Call immediately before the real SetAmount, including decrements.</summary>
    internal static void AmountChanged(PowerModel power, int newAmount, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        if (!Handles(power) || !power.Owner.IsPlayer || power.Owner.CombatState is not { } combat) return;
        if (!receipts.TryGetValue(power, out var receipt) || !ReferenceEquals(receipt.Owner, power.Owner) ||
            !ReferenceEquals(receipt.Combat, combat))
        {
            // Unobserved existing amounts are external, never retroactively labelled enemy.
            receipts.Remove(power);
            receipt = new Receipt(combat, power.Owner, power.Amount, power.Amount);
            receipts.Add(power, receipt);
        }
        Reconcile(power, receipt);
        int next = Math.Clamp(newAmount, -999999999, 999999999);
        int delta = next - receipt.Actual;
        if (power is ShrinkPower)
        {
            // Native -1 is permanent Shrink, not a decrement. Known enemy writes
            // do not establish a retained contribution; external writes do.
            if (delta != 0 && !Enemy(power, power.Owner, applier, card, context))
                receipt.Retained = next < 0 ? -1 : Math.Max(0, receipt.Retained + delta);
        }
        else if (delta < 0)
            receipt.Retained = Math.Max(0, receipt.Retained + delta);
        else if (delta > 0 && !Enemy(power, power.Owner, applier, card, context))
            receipt.Retained = Math.Min(next, receipt.Retained + delta);
        receipt.Actual = next;
        if (delta > 0 || power is ShrinkPower && delta != 0) RememberPresentationSource(power, power.Owner, applier, card, context);
    }

    private static void RememberPresentationSource(PowerModel power, Creature target, Creature? applier, CardModel? card, PlayerChoiceContext context)
    {
        try
        {
            if (!Enemy(power, target, applier, card, context) || !receipts.TryGetValue(power, out var receipt)) return;
            var enemy = applier;
            if (enemy is null && nullSources.TryGetValue(context, out var known)) enemy = known.Source;
            if (enemy is not null) receipt.PresentationSources.Add(enemy);
        }
        catch { }
    }
    private static void PresentSuppressedContribution(PowerModel power, bool scalar)
    {
        try
        {
            if (!receipts.TryGetValue(power, out var receipt)) return;
            foreach (var enemy in receipt.PresentationSources)
                if (scalar) Volibear.Presentation.PowerPresentationDomainScalars.Capture(enemy, power);
                else Volibear.Presentation.PowerPresentationDomain.Suppressed(enemy, power, sourceCombat: receipt.Combat);
        }
        catch { }
    }

    private static void Reconcile(PowerModel power, Receipt receipt)
    {
        if (power.Amount == receipt.Actual) return;
        // Direct writes outside observed commands stay external. Never infer enemy
        // ownership from a power's original Applier after unrelated stacking.
        int delta = power.Amount - receipt.Actual;
        receipt.Retained = power is ShrinkPower && power.Amount < 0 ? -1 :
            Math.Clamp(receipt.Retained + delta, 0, Math.Max(0, power.Amount));
        receipt.Actual = power.Amount;
    }

    internal static int EffectiveAmount(PowerModel power)
    {
        if (DomainSelfDebuffEffects.IsSuppressed(power)) return 0;
        if (!receipts.TryGetValue(power, out var receipt)) return power.Amount;
        if (!ReferenceEquals(receipt.Owner, power.Owner) || !ReferenceEquals(receipt.Combat, power.Owner.CombatState) ||
            !receipt.Combat.ContainsCreature(receipt.Owner) || !receipt.Owner.Powers.Contains(power)) return power.Amount;
        Reconcile(power, receipt);
        return DomainEnemyEffects.ActiveFor(receipt.Combat) ? receipt.Retained : power.Amount;
    }

    private static bool Suppressed(PowerModel power) => DomainSelfDebuffEffects.IsSuppressed(power) || receipts.TryGetValue(power, out var receipt) &&
        DomainEnemyEffects.ActiveFor(receipt.Combat) && EffectiveAmount(power) == 0;
    public static void Reset() { receipts = new(); nullSources = new(); }
}
