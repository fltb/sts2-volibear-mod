using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>
/// Serves Volibear's card portraits from the mod folder. The game resolves portraits through a
/// res:// atlas, so the getter is redirected for this mod's cards only; every other card keeps
/// the shipped artwork untouched.
/// </summary>
public static class VolibearPortraits
{
    public static void Install()
    {
        var harmony = new Harmony("Volibear.Portraits");
        var portrait = typeof(CardModel).GetProperty(nameof(CardModel.Portrait))?.GetGetMethod(true);
        if (portrait is null)
        {
            GD.PrintErr("[Volibear] PORTRAIT_PATCH missing CardModel.Portrait");
            return;
        }
        harmony.Patch(portrait, postfix: new HarmonyMethod(typeof(VolibearPortraits), nameof(AfterPortrait)));
        GD.Print("[Volibear] PORTRAIT_PATCH ok");
    }

    /// <summary>Portrait relative to the art root, e.g. cards/production/.../b01.png.</summary>
    public static string RelativePath(VolibearCard card) =>
        $"cards/production/sts2/Volibear/images/card_portraits/{card.Key}.png";

    public static string BigPath(VolibearCard card) =>
        $"cards/production/sts2/Volibear/images/card_portraits/big/{card.Key}.png";

    private static void AfterPortrait(CardModel __instance, ref Texture2D __result)
    {
        if (__instance is not VolibearCard card) return;
        var texture = VolibearAssets.Texture(RelativePath(card));
        if (texture is not null) __result = texture;
    }
}
