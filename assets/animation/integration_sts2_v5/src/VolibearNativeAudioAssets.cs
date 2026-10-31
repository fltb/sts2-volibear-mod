// integration_source_uncompiled. Optional native character-slot route; not used by the offline player.
using STS2RitsuLib.Scaffolding.Characters;

namespace VolibearMod.ArtV5;

public static class VolibearNativeAudioAssets
{
    /// <summary>
    /// Uses BaseLib's actual NAudioManager.PlayOneShot resource-path bridge.
    /// If the host chooses this route, do not replay these same character voices
    /// from the custom cue timeline. Select a single owner for each event.
    /// </summary>
    public static CharacterAudioAssetSet CharacterSlots() => new(
        CharacterSelectSfx: "res://VolibearArt/audio/ogg/voice_select.ogg",
        CharacterTransitionSfx: "res://VolibearArt/audio/ogg/cast_charge.ogg",
        AttackSfx: "res://VolibearArt/audio/ogg/voice_attack_01.ogg",
        CastSfx: "res://VolibearArt/audio/ogg/voice_cast.ogg",
        DeathSfx: "res://VolibearArt/audio/ogg/voice_death.ogg");
}
