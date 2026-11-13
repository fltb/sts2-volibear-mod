using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

/// <summary>Read-only projection onto the native power and creature hover entry points.
/// Never removes a power or executes a gameplay hook to predict a contribution.</summary>
internal static class PowerPresentationDisabled
{
    private const string HarmonyId = "Volibear.PowerPresentationDisabled";
    private static bool installed;

    // Contribution adapters, not a blanket Buff filter. Strength/Dexterity, combat
    // facts, enemy debuffs and unknown third-party powers deliberately stay native.
    internal static readonly HashSet<string> EnemyPowers = new(
        MechanicGlossary.SuppressedContributions.SelectMany(entry => entry.Words), StringComparer.Ordinal);

    internal static bool IsCreatureSuppressed(Creature creature) =>
        creature.Powers.Any(IsSuppressed) ||
        (DomainEnemyEffects.ActiveFor(creature) && MechanicEnemyHoverTips.HasMechanics(creature));

    private static string DisabledDescription(PowerModel power)
    {
        if (DomainSelfDebuffEffects.IsSuppressed(power)) return Text("selfDescription").GetFormattedText();
        if (DomainSandpitEffects.IsSuppressed(power)) return
            new LocString("static_hover_tips", "VOLIBEAR-ENEMY-SANDPIT.description").GetFormattedText() + "\n" + Text("description").GetFormattedText();
        var contribution = MechanicGlossary.SuppressedContributions.Single(entry => entry.Words.Contains(power.GetType().Name));
        return new LocString("static_hover_tips", "VOLIBEAR-CONTRIBUTION-" + contribution.Key).GetFormattedText();
    }

    internal static bool IsSuppressed(PowerModel power)
    {
        if (power.IsCanonical) return false;
        if (DomainSelfDebuffEffects.IsSuppressed(power) || DomainSandpitEffects.IsSuppressed(power)) return true;
        if (power is MegaCrit.Sts2.Core.Models.Powers.VigorPower && power.Amount <= 0) return false;
        return power.GetType().Assembly == typeof(PowerModel).Assembly &&
            EnemyPowers.Contains(power.GetType().Name) && DomainEnemyEffects.ActiveFor(power.Owner);
    }

    internal static LocString Text(string key) => new("static_hover_tips", "VOLIBEAR-DISABLED." + key);

    internal static IEnumerable<IHoverTip> PowerTips(PowerModel power, IEnumerable<IHoverTip> original)
    {
        bool suppressed = IsSuppressed(power);
        bool found = false;
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var tips = original.ToArray();
        foreach (var tip in tips)
        {
            seen.Add(tip.Id);
            if (suppressed && tip is HoverTip native && tip.Id == power.Id.ToString())
            {
                found = true;
                yield return new HoverTip(power, native.Description + "\n\n" + Text("badge").GetFormattedText() + "\n" + DisabledDescription(power), native.IsSmart);
            }
            else yield return tip;
        }
        // Invisible powers have no native icon/tip; expose their real name on the creature.
        if (suppressed && !found)
            yield return new HoverTip(power.Title, Text("badge").GetFormattedText() + "\n" + DisabledDescription(power))
#if !STS2_BETA
                { Id = "VOLIBEAR-DISABLED-" + power.Id }
#endif
                ;
        if (power.GetType().Assembly != typeof(PowerPresentationDisabled).Assembly) yield break;
        foreach (var tip in MechanicHoverTips.ForText(power.Title.GetRawText() + "\n" + power.Description.GetRawText()))
            if (seen.Add(tip.Id)) yield return tip;
    }

    internal static IEnumerable<IHoverTip> CreatureTips(Creature creature, IEnumerable<IHoverTip> original)
    {
        foreach (var tip in original) yield return tip;
        foreach (var tip in MechanicEnemyHoverTips.ForCreature(creature, DomainEnemyEffects.ActiveFor(creature))) yield return tip;
        // Only verified contribution adapters receive a badge/summary. An active
        // domain alone must never claim that every special action is suppressed.
        if (DomainEnemyEffects.ActiveFor(creature) && IsCreatureSuppressed(creature))
            yield return new HoverTip(Text("enemyTitle"), Text("enemyDescription"))
#if !STS2_BETA
                { Id = "VOLIBEAR-DISABLED-ENEMY" }
#endif
                ;
        else if (creature.Powers.Any(IsSuppressed))
            yield return new HoverTip(Text("selfTitle"), Text("selfDescription"))
#if !STS2_BETA
                { Id = "VOLIBEAR-DISABLED-SELF" }
#endif
                ;
    }

    private static void PowerHover(PowerModel __instance, ref IEnumerable<IHoverTip> __result) =>
        __result = PowerTips(__instance, __result);
    private static void CreatureHover(Creature __instance, ref IEnumerable<IHoverTip> __result) =>
        __result = CreatureTips(__instance, __result);
    private static void PowerReady(NPower __instance) => PowerPresentationDisabledVisual.Attach(__instance);
    private static void PowerModelChanged(NPower __instance) => PowerPresentationDisabledVisual.ModelChanged(__instance);
    private static void CreatureReady(NCreature __instance) => PowerPresentationDisabledVisual.Attach(__instance);

    internal static void Install()
    {
        if (installed) return;
        var h = new Harmony(HarmonyId);
        try
        {
            h.Patch(AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.HoverTips)),
                postfix: new(typeof(PowerPresentationDisabled), nameof(PowerHover)));
            h.Patch(AccessTools.PropertyGetter(typeof(Creature), nameof(Creature.HoverTips)),
                postfix: new(typeof(PowerPresentationDisabled), nameof(CreatureHover)));
            h.Patch(AccessTools.DeclaredMethod(typeof(NPower), nameof(NPower._Ready)),
                postfix: new(typeof(PowerPresentationDisabled), nameof(PowerReady)));
            h.Patch(AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)),
                postfix: new(typeof(PowerPresentationDisabled), nameof(PowerModelChanged)));
            h.Patch(AccessTools.DeclaredMethod(typeof(NCreature), nameof(NCreature._Ready)),
                postfix: new(typeof(PowerPresentationDisabled), nameof(CreatureReady)));
            installed = true;
        }
        catch { h.UnpatchAll(HarmonyId); throw; }
    }
}
