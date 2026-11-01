using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using Volibear.Core;

namespace Volibear.Content;

/// <summary>Native additive hover tips; no new keyword flags, model registrations or rule hooks.</summary>
internal static class MechanicHoverTips
{
    internal static IEnumerable<IHoverTip> ForCard(VolibearCard card)
    {
        var text = card.Description.GetRawText();
        foreach (var tip in ForText(text)) yield return tip;
        // Read the existing shared ledger only. Inspecting a card cannot reserve,
        // reset or consume an action, and is not a second eligibility engine.
        var owner = card.Owner?.Creature;
        var combat = owner?.CombatState;
        if (!text.Contains("迎战", StringComparison.Ordinal) || owner is not { IsAlive: true } ||
            combat is null || combat.CurrentSide != CombatSide.Player ||
            !ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) ||
            !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsOverOrEnding ||
            !combat.ContainsCreature(owner)) yield break;
        var spent = combat.Enemies.Where(enemy => enemy.IsAlive &&
            ReferenceEquals(enemy.CombatState, combat) && combat.ContainsCreature(enemy) && EngageCmd.Consumed(enemy))
            .Select(enemy => enemy.Name).ToArray();
        var description = new LocString("static_hover_tips", spent.Length == 0
            ? "VOLIBEAR-ENGAGE_STATE.empty" : "VOLIBEAR-ENGAGE_STATE.spent");
        if (spent.Length > 0) description.Add("Enemies", string.Join("、", spent));
        yield return new HoverTip(new LocString("static_hover_tips", "VOLIBEAR-ENGAGE_STATE.title"), description)
            { Id = "VOLIBEAR-ENGAGE_STATE" };
    }

    internal static IEnumerable<IHoverTip> ForText(string? text, string? omitTitle = null)
    {
        foreach (var entry in MechanicGlossary.Match(text, omitTitle))
            yield return new HoverTip(
                new LocString("static_hover_tips", "VOLIBEAR-" + entry.Key + ".title"),
                new LocString("static_hover_tips", "VOLIBEAR-" + entry.Key + ".description"))
                { Id = "VOLIBEAR-" + entry.Key };
    }

    // A converted foreign card must display only its current form's rules.
    internal static IEnumerable<IHoverTip> ForBeast(bool claw) =>
        ForText(claw ? "裂骨之爪" : "风暴之躯 雷伤");
}
