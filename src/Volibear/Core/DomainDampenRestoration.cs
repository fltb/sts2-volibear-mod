using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Temporarily loans back the exact native Dampen upgrade debt, without clearing its ledger.</summary>
public static class DomainDampenRestoration
{
    private sealed class Loan { internal readonly Dictionary<CardModel, int> Cards = new(); }
    private static ConditionalWeakTable<DampenPower, Loan> loans = new();
    private static readonly Type Data = typeof(DampenPower).GetNestedType("Data", BindingFlags.NonPublic)
        ?? throw new MissingMemberException("DampenPower.Data");
    private static readonly MethodInfo GetData = typeof(PowerModel).GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
        .Single(m => m.Name == "GetInternalData" && m.IsGenericMethodDefinition).MakeGenericMethod(Data);
    private static readonly FieldInfo Ledger = Data.GetField("downgradedCardsToOldUpgradeLevels")
        ?? throw new MissingFieldException("Dampen native upgrade ledger");

    internal static void Install(Harmony harmony)
    {
        harmony.Patch(AccessTools.DeclaredMethod(typeof(DampenPower), nameof(DampenPower.AfterApplied)),
            postfix: new HarmonyMethod(typeof(DomainDampenRestoration), nameof(Applied)));
        harmony.Patch(AccessTools.DeclaredMethod(typeof(DampenPower), nameof(DampenPower.AfterRemoved)),
            prefix: new HarmonyMethod(typeof(DomainDampenRestoration), nameof(Removing)));
    }
    private static void Applied(DampenPower __instance) => Refresh(__instance);
    private static void Removing(DampenPower __instance) => ReturnLoan(__instance);

    public static void RefreshCombat(Creature domainOwner)
    {
        if (domainOwner.CombatState is not { } combat) return;
        foreach (var player in combat.Players)
            foreach (var power in player.Creature.Powers.OfType<DampenPower>().ToArray()) Refresh(power);
    }
    internal static void Refresh(DampenPower power)
    {
        if (!DomainSelfDebuffEffects.IsSuppressed(power)) { ReturnLoan(power); return; }
        var ledger = (Dictionary<CardModel, int>)Ledger.GetValue(GetData.Invoke(power, null))!;
        var loan = loans.GetOrCreateValue(power);
        foreach (var (card, original) in ledger)
        {
            if (loan.Cards.ContainsKey(card)) continue;
            int before = card.CurrentUpgradeLevel;
            for (int i = 0; i < original; i++) CardCmd.Upgrade(card);
            loan.Cards.Add(card, card.CurrentUpgradeLevel - before);
        }
    }
    private static void ReturnLoan(DampenPower power)
    {
        if (!loans.TryGetValue(power, out var loan)) return;
        // Remove the receipt before native card callbacks can re-enter us.
        loans.Remove(power);
        foreach (var (card, added) in loan.Cards)
        {
            if (added == 0) continue;
            int retained = Math.Max(0, card.CurrentUpgradeLevel - added);
            CardCmd.Downgrade(card);
            for (int i = 0; i < retained; i++) CardCmd.Upgrade(card);
        }
    }
}
