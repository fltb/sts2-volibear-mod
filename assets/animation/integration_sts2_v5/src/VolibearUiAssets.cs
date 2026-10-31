// integration_source_uncompiled. RitsuLib 772f280964f2efc7c7e2f29fc59844e68616dd57.
using STS2RitsuLib.Scaffolding.Characters;

namespace VolibearMod.ArtV5;

/// <summary>Only map compatible delivered textures. Scene/material slots stay explicit.</summary>
public static class VolibearUiAssets
{
    public static CharacterUiAssetSet Textures() => new(
        IconTexturePath: "res://VolibearArt/ui/images/character_icon_volibear.png",
        IconOutlineTexturePath: "res://VolibearArt/ui/images/character_icon_volibear_outline.png",
        // This RitsuLib snapshot explicitly accepts Texture2D as a select-background fallback.
        CharacterSelectBgPath: "res://VolibearArt/ui/images/character_select_background.png",
        CharacterSelectIconPath: "res://VolibearArt/ui/images/char_select_volibear.png",
        CharacterSelectLockedIconPath: "res://VolibearArt/ui/images/char_select_volibear_locked.png",
        MapMarkerPath: "res://VolibearArt/ui/images/map_marker_volibear.png");

    public const string BigEnergyIcon = "res://VolibearArt/ui/images/big_energy.png";
    public const string TextEnergyIcon = "res://VolibearArt/ui/images/text_energy.png";

    // CharacterSelectTransitionPath is a material slot; a PNG cannot be assigned there.
    // EnergyCounterPath requires a scene. Merchant/RestSite are visual-scene slots
    // with an explicit static Texture2D fallback in this RitsuLib snapshot.
    // Animated world-scene construction is separate from these UI textures.
}
