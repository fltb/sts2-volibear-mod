using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Audio;

namespace Volibear.Presentation;

/// <summary>
/// The locked CharacterModel invents FMOD keys from the model ID. Volibear's
/// authored resource audio is dispatched by its committed presentation bridge;
/// these five nonexistent default events must not also reach the native bank.
/// </summary>
internal static class VolibearNativeAudio
{
    internal const string HarmonyId = "Volibear.Presentation.NativeAudioDefaults";
    private static bool installed;

    internal static MethodInfo NativeOneShot()
    {
        // Both native one-shot overloads converge here. BaseLib uses the same
        // entry for res:// audio, which remains completely untouched by this filter.
        var method = AccessTools.DeclaredMethod(typeof(NAudioManager), nameof(NAudioManager.PlayOneShot),
            [typeof(string), typeof(Dictionary<string, float>), typeof(float)]);
        if (method is null || method.ReturnType != typeof(void))
            throw new MissingMethodException("Pinned NAudioManager.PlayOneShot(string, Dictionary<string,float>, float)");
        return method;
    }

    internal static void Install()
    {
        if (installed) return;
        new Harmony(HarmonyId).Patch(NativeOneShot(),
            prefix: new HarmonyMethod(typeof(VolibearNativeAudio), nameof(BeforeNativeOneShot)));
        installed = true;
    }

    internal static bool BeforeNativeOneShot(string? path)
    {
        // Exact matches only: do not silence another character, user resource,
        // added event, or even another mod's legitimate event under this prefix.
        return path is not (
            "event:/sfx/characters/volibear_character/volibear_character_select" or
            "event:/sfx/characters/volibear_character/volibear_character_attack" or
            "event:/sfx/characters/volibear_character/volibear_character_cast" or
            "event:/sfx/characters/volibear_character/volibear_character_die" or
            "event:/sfx/ui/wipe_volibear_character");
    }
}
