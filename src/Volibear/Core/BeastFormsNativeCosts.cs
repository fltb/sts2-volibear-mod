using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>Read the native temporary-retain bit without copying intrinsic material keywords.</summary>
internal static class BeastNativeRetain
{
    // HasSingleTurnRetain is listed in the locked API but its getter is private.
    // ShouldRetainThisTurn also includes intrinsic Retain and cannot distinguish it.
    private static readonly PropertyInfo SingleTurnProperty = typeof(CardModel).GetProperty(
        "HasSingleTurnRetain", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
        ?? throw new MissingMemberException(typeof(CardModel).FullName, "HasSingleTurnRetain");

    internal static void Validate()
    {
        if (SingleTurnProperty.PropertyType != typeof(bool) || SingleTurnProperty.GetGetMethod(true) is null)
            throw new InvalidOperationException("Native temporary-retain representation changed.");
    }

    internal static bool SingleTurn(CardModel card)
    {
        Validate();
        return (bool)SingleTurnProperty.GetValue(card)!;
    }
}

/// <summary>
/// The locked 0.107.1 API has public native modifier writers/cleanup but no reader.
/// This one checked, read-only field access snapshots local costs. It never patches
/// a getter, shares mutable cost objects, or changes the original card's metadata.
/// </summary>
internal sealed class BeastNativeCosts
{
    private static readonly FieldInfo LocalModifiers =
        typeof(CardEnergyCost).GetField("_localModifiers", BindingFlags.Instance | BindingFlags.NonPublic)
        ?? throw new MissingFieldException(typeof(CardEnergyCost).FullName, "_localModifiers");
    private readonly CardEnergyCost source;
    private readonly int materialBase;
    private readonly (LocalCostModifier Identity, LocalCostModifier Value)[] captured;

    internal static void Validate()
    {
        if (!typeof(IEnumerable<LocalCostModifier>).IsAssignableFrom(LocalModifiers.FieldType))
            throw new InvalidOperationException("Native local-cost representation changed; beast cost transfer requires review.");
    }

    private static LocalCostModifier[] Read(CardEnergyCost cost) =>
        LocalModifiers.GetValue(cost) is IEnumerable<LocalCostModifier> modifiers
            ? modifiers.ToArray()
            : throw new InvalidOperationException("Native local-cost list is unavailable.");

    private BeastNativeCosts(CardModel card)
    {
        Validate();
        source = card.EnergyCost;
        materialBase = source.GetWithModifiers(CostModifiers.None);
        captured = Read(source).Select(m => (m,
            new LocalCostModifier(m.Amount, m.Type, m.Expiration, m.IsReduceOnly))).ToArray();
        // Fail before the native exhaust if a future/custom expiration cannot be
        // represented. No unknown duration is silently widened to combat lifetime.
        const LocalCostModifierExpiration known = LocalCostModifierExpiration.EndOfCombat |
            LocalCostModifierExpiration.EndOfTurn | LocalCostModifierExpiration.WhenPlayed;
        if (captured.Any(m => (m.Value.Expiration & ~known) != 0))
            throw new InvalidOperationException("Unsupported native local-cost expiration.");
        _ = Adjustments(captured.Select(m => m.Value).ToArray());
    }

    internal static BeastNativeCosts Capture(CardModel card) => new(card);

    private BeastCostAdjustments Adjustments(IReadOnlyList<LocalCostModifier> modifiers) =>
        BeastCostTransfer.Rebase(materialBase, modifiers, (m, value) => m.Modify(value),
            m => m.Expiration.HasFlag(LocalCostModifierExpiration.EndOfTurn),
            m => m.Expiration.HasFlag(LocalCostModifierExpiration.WhenPlayed));

    internal void ApplyTo(CardModel replacement)
    {
        var live = Read(source);
        // Native exhaust reactions may have advanced a turn or played the material.
        // An already expired modifier must not be resurrected on the generated card;
        // unrelated modifiers added by those reactions belong to the material alone.
        var values = captured.Where(m => live.Any(value => ReferenceEquals(value, m.Identity)))
            .Select(m => m.Value).ToArray();
        var costs = Adjustments(values);
        replacement.EnergyCost.AddThisCombat(costs.Combat);
        replacement.EnergyCost.AddUntilPlayed(costs.UntilPlayed);
        replacement.EnergyCost.AddThisTurn(costs.ThisTurn);
        replacement.EnergyCost.AddThisTurnOrUntilPlayed(costs.ThisTurnOrPlayed);
        replacement.InvokeEnergyCostChanged();
    }
}
