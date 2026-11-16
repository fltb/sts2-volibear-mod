#if STS2_BETA
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Ancients;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;

namespace Volibear.Content;

internal static class VolibearRunStory
{
    internal static void Install()
    {
        var harmony = new Harmony("Volibear.RunStory");
        harmony.Patch(AccessTools.DeclaredMethod(typeof(AncientDialogueSet), nameof(AncientDialogueSet.GetValidDialogues)),
            prefix: new HarmonyMethod(typeof(VolibearRunStory), nameof(ChooseConversation)));
        harmony.Patch(AccessTools.DeclaredMethod(typeof(EventModel), "SetEventState"),
            prefix: new HarmonyMethod(typeof(VolibearRunStory), nameof(UseCharacterPage)));
    }

    // A global first visit and the generic repeat pool otherwise take precedence even
    // after BaseLib has populated this character's own lines. Other sets keep their rules.
    private static bool ChooseConversation(AncientDialogueSet __instance, ModelId characterId, int charVisits,
        ref IEnumerable<AncientDialogue> __result)
    {
        if (characterId.Entry != "VOLIBEAR_CHARACTER" ||
            !__instance.CharacterDialogues.TryGetValue(characterId.Entry, out var scenes) ||
            scenes.Count == 0 || scenes[0].Lines[0].LineText?.LocEntryKey is not { } first ||
            !first.Contains(".talk.VOLIBEAR_CHARACTER.", StringComparison.Ordinal))
            return true;

        int visits = Math.Max(0, charVisits);
        int index = first.StartsWith("THE_ARCHITECT.", StringComparison.Ordinal)
            ? Math.Min(visits, scenes.Count - 1) : visits % scenes.Count;
        __result = [scenes[index]];
        return false;
    }

    private static void UseCharacterPage(EventModel __instance, ref LocString description)
    {
        if (__instance is not (AromaOfChaos or SunkenTreasury) || __instance.Owner?.Character is not VolibearCharacter)
            return;
        var key = description.LocEntryKey + ".VOLIBEAR_CHARACTER";
        if (!LocString.Exists("events", key)) return;
        var page = new LocString("events", key);
        page.AddVariablesFrom(description);
        description = page;
    }
}
#endif
