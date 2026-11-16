using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using MegaCrit.Sts2.Core.Localization;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

internal sealed record PowerStackProjection(IReadOnlyList<PowerModel> Members, string AmountText, string Description);

/// <summary>Read-only UI projection. Never merges models, changes their amounts,
/// executes hooks, or reads HoverTips (which would recurse through the UI adapter).</summary>
internal static class PowerStackPresentation
{
    private enum Rule { Sum, Maximum, Minimum, Flag, Copies, Domain, Charge, TemporaryStrength }
    // Owner's public getter asserts mutable. A placeholder has no owner at all.
    private static readonly AccessTools.FieldRef<PowerModel, Creature?> OwnerField =
        AccessTools.FieldRefAccess<PowerModel, Creature?>("_owner");

    internal static bool TryDescribe(PowerModel power, out PowerStackProjection projection)
    {
        projection = null!;
        if (power is null || !power.IsMutable || !TryRule(power, out var rule) || OwnerField(power) is not { } owner || !power.IsVisible)
            return false;
        var type = power.GetType();
        var id = power.Id;
        var members = owner.Powers.Where(p => p.IsMutable && p.GetType() == type && Equals(p.Id, id) &&
            ReferenceEquals(OwnerField(p), owner) && p.IsVisible).Distinct(ReferenceEqualityComparer.Instance).Cast<PowerModel>().ToArray();
        if (!members.Any(p => ReferenceEquals(p, power))) return false;

        long sum = members.Sum(p => (long)p.Amount);
        string amount, description;
        switch (rule)
        {
            case Rule.Flag:
                amount = "";
                description = Render(power, 1);
                break;
            case Rule.Maximum:
                long maximum = members.Max(p => (long)p.Amount);
                amount = Number(maximum);
                description = Render(power, maximum);
                if (members.Length > 1)
                {
                    if (power is WelcomeThunderPower) description = DescribeCopies(members);
                    description += VolibearLoc.SentenceSeparator + StackText("maximum");
                }
                break;
            case Rule.Minimum:
                long minimum = members.Min(p => (long)p.Amount);
                amount = Number(minimum);
                description = Render(power, minimum);
                break;
            case Rule.Copies:
                amount = Number(members.Length);
                // Distinct first-trigger clocks and separate lightning/draw/energy
                // responses must not be presented as one stronger response.
                description = DescribeCopies(members);
                break;
            case Rule.Domain:
                bool permanent = ((DomainPower)power).IsPermanent;
                long rounds = power.Amount;
                // Permanent domain lasts the whole combat; there is no counter worth
                // showing, and "本战" would only restate the default lifetime.
                amount = permanent ? "" : Number(rounds);
                description = permanent ? Template(power, "permanentDescription") : Render(power, rounds);
                break;
            case Rule.Charge:
                amount = Number(sum);
                description = StackText("charge", sum);
                break;
            case Rule.TemporaryStrength:
                amount = Number(sum);
                description = sum >= 0 ? StackText("gainStrength", sum)
                    : StackText("loseStrength", -sum);
                break;
            default:
                amount = Number(sum);
                description = Render(power, sum);
                if (power is ThunderArmorPower && members.Length > 1)
                    description = StackText("armor", sum, members.Length, values: string.Join(VolibearLoc.ListSeparator, members.Select(p => Number(p.Amount))));
                break;
        }
        projection = new PowerStackProjection(Array.AsReadOnly(members), amount, description);
        return true;
    }

    private static string DescribeCopies(PowerModel[] members) => members.Length == 1
        ? StackText("single") + VolibearLoc.SentenceSeparator + Render(members[0], members[0].Amount)
        : StackText("multiple", count: members.Length) +
            string.Join("", members.GroupBy(p => Render(p, p.Amount)).Select(group => "\n" + StackText("group", count: group.Count(), description: group.Key)));

    private static string Number(long number) => number.ToString(CultureInfo.InvariantCulture);
    private static string Template(PowerModel power, string key) =>
        new LocString("powers", power.Id.Entry + "." + key).GetRawText();

    private static string StackText(string key, long amount = 0, int count = 0, string values = "", string description = "")
    {
        var text = new LocString("static_hover_tips", "VOLIBEAR-STACK." + key);
        text.Add("Amount", (decimal)amount);
        text.Add("Count", (decimal)count);
        text.Add("Values", values);
        text.Add("Description", description);
        return text.GetFormattedText();
    }
    private static string Render(PowerModel power, long amount) => Template(power, "smartDescription").Replace("{Amount}", Number(amount), StringComparison.Ordinal);

    private static bool TryRule(PowerModel power, out Rule rule)
    {
        rule = power switch
        {
            NextAttackDiscount or WelcomeThunderPower => Rule.Maximum,
            StandingPower => Rule.Minimum,
            NextEngageDiscount or BiteMarkPower or ImmovableBodyPower => Rule.Flag,
            ThunderGuardPower or StormConductionPower or BattleScarsPower or LingeringStormPower or
                ThunderAftershockPower or PreyStillStandsPower or GrowingFuryPower or ThunderPoolPower or
                BearSpiritPower or WildernessPower => Rule.Copies,
            DomainPower => Rule.Domain,
            StormChargePower => Rule.Charge,
            VolibearChargeStrengthPower => Rule.TemporaryStrength,
            NextAttackReplayPower or NextAttackTrainingPower or UnifyPower or PrimalThunderPower or
                ThunderArmorPower or BattleBodyPower or EndlessHuntPower => Rule.Sum,
            _ => (Rule)(-1)
        };
        return (int)rule >= 0;
    }
}
