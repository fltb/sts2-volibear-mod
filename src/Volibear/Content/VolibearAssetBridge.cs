using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>
/// Until the character's own scenes ship inside an asset pack, every res:// lookup the engine
/// derives from the character id is pointed at an existing character's asset, and the combat
/// visuals are delegated. Gameplay is then testable without pretending the art is finished.
/// </summary>
public static class VolibearAssetBridge
{
    private static readonly Dictionary<string, string> PlaceholderPaths = new()
    {
        ["IconPath"] = "res://scenes/ui/character_icons/ironclad_icon.tscn",
        ["EnergyCounterPath"] = "res://scenes/combat/energy_counters/ironclad_energy_counter.tscn",
        ["MerchantAnimPath"] = "res://scenes/merchant/characters/ironclad_merchant.tscn",
        ["RestSiteAnimPath"] = "res://scenes/rest_site/characters/ironclad_rest_site.tscn",
        ["CharacterSelectBg"] = "res://scenes/screens/char_select/char_select_bg_ironclad.tscn",
        ["CharacterSelectIconPath"] = "res://images/packed/character_select/char_select_ironclad.png",
        ["CharacterSelectLockedIconPath"] = "res://images/packed/character_select/char_select_ironclad_locked.png",
        ["CharacterSelectTransitionPath"] = "res://materials/transitions/ironclad_transition_mat.tres",
        ["MapMarkerPath"] = "res://images/packed/map/icons/map_marker_ironclad.png",
        ["TrailPath"] = "res://scenes/vfx/card_trail_ironclad.tscn",
        ["VisualsPath"] = "res://scenes/creature_visuals/ironclad.tscn",
        ["IconTexturePath"] = "res://images/ui/top_panel/character_icon_ironclad.png",
    };

    public static void Install()
    {
        var harmony = new Harmony("Volibear.AssetBridge");
        var patched = 0;
        foreach (var name in PlaceholderPaths.Keys)
        {
            var info = typeof(CharacterModel).GetProperty(name,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var getter = info?.GetGetMethod(true);
            if (getter is null)
            {
                GD.PrintErr($"[Volibear] ASSET_BRIDGE missing {name}");
                continue;
            }
            harmony.Patch(getter, postfix: new HarmonyMethod(typeof(VolibearAssetBridge), nameof(Substitute)));
            patched++;
        }
        GD.Print($"[Volibear] ASSET_BRIDGE patched={patched}");

        var createVisuals = AccessTools.Method(typeof(CharacterModel), "CreateVisuals");
        if (createVisuals is null)
        {
            GD.PrintErr("[Volibear] ASSET_BRIDGE missing CreateVisuals");
            return;
        }
        harmony.Patch(createVisuals, prefix: new HarmonyMethod(typeof(VolibearAssetBridge), nameof(ReplaceVisuals)));
    }

    /// <summary>Combat visuals come from the placeholder character until the atlas is wired.</summary>
    private static bool ReplaceVisuals(CharacterModel __instance,
                                       ref MegaCrit.Sts2.Core.Nodes.Combat.NCreatureVisuals? __result)
    {
        if (__instance is not VolibearCharacter) return true;
        __result = ModelDb.Character<MegaCrit.Sts2.Core.Models.Characters.Ironclad>().CreateVisuals();
        return false;
    }

    private static void Substitute(CharacterModel __instance, MethodBase __originalMethod, ref string __result)
    {
        if (__instance is not VolibearCharacter) return;
        var name = __originalMethod.Name.StartsWith("get_") ? __originalMethod.Name[4..] : __originalMethod.Name;
        if (PlaceholderPaths.TryGetValue(name, out var path)) __result = path;
    }
}
