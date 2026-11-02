using System;
using BaseLib.Utils;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;

namespace Volibear.Presentation;

// BaseLib 3.4.7 auto-conversion wraps the original scene but does not set its
// CreatedFromFactory marker. Its merchant non-Spine prefixes therefore miss
// this path. Keep this compatibility adapter restricted to our merchant scene.
[HarmonyPatch]
internal static class VolibearMerchantIntegration
{
    public static void Install() => new Harmony("Volibear.MerchantIntegration")
        .CreateClassProcessor(typeof(VolibearMerchantIntegration)).Patch();

    private static bool IsVolibearMerchant(NMerchantCharacter merchant) =>
        merchant.GetChildCount() == 1 &&
        merchant.GetChild(0).SceneFilePath == VolibearPresentation.MerchantScenePath;

    [HarmonyPatch(typeof(NMerchantCharacter), nameof(NMerchantCharacter._Ready))]
    [HarmonyPrefix]
    private static bool Ready(NMerchantCharacter __instance)
    {
        if (!IsVolibearMerchant(__instance)) return true;
        PlayRequired(__instance, "relaxed_loop");
        return false;
    }

    [HarmonyPatch(typeof(NMerchantCharacter), nameof(NMerchantCharacter.PlayAnimation))]
    [HarmonyPrefix]
    private static bool PlayAnimation(NMerchantCharacter __instance, string anim)
    {
        if (!IsVolibearMerchant(__instance)) return true;
        PlayRequired(__instance, anim);
        return false;
    }

    private static void PlayRequired(Node merchant, string animation)
    {
        // Use the same animation-name aliases as BaseLib's merchant adapter.
        // SpriteFrames owns loop settings, just as in BaseLib CustomAnimation.
        string[] names = animation switch
        {
            "relaxed_loop" => ["idle", "Idle", animation],
            "die" => ["Die", animation],
            _ => [animation]
        };
        if (!CustomAnimation.HasCustomAnimation(merchant) ||
            !CustomAnimation.PlayCustomAnimation(merchant, names))
            throw new InvalidOperationException("Volibear merchant scene has no supported animation player.");
    }
}
