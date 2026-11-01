using BaseLib.Utils.NodeFactories;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace Volibear.Presentation;

/// <summary>BaseLib 3.4.7 native-node visual adapter. No Spine or borrowed character scene.</summary>
public static class VolibearPresentation
{
    public const string CombatScenePath = "res://VolibearArt/scenes/volibear_combat.tscn";
    public const string SelectionScenePath = "res://VolibearArt/scenes/volibear_selection.tscn";
    public const string IconScenePath = "res://VolibearArt/scenes/volibear_icon.tscn";
    public const string EnergyScenePath = "res://VolibearArt/scenes/volibear_energy.tscn";
    public const string RestScenePath = "res://VolibearArt/scenes/volibear_rest.tscn";
    public const string MerchantScenePath = "res://VolibearArt/scenes/volibear_merchant.tscn";
    public const string TrailScenePath = "res://VolibearArt/scenes/volibear_trail.tscn";
    public const string TransitionMaterialPath = "res://VolibearArt/scenes/volibear_transition.tres";
    public const float DeathAnimationSeconds = 40f / 24f;
    private static bool _trailRegistered;

    /// <summary>Call once during mod initialization, after BaseLib initialization.</summary>
    public static void RegisterSceneConversions()
    {
        if (_trailRegistered) return;
        _ = new VolibearTrailFactory();
        NodeFactory.RegisterSceneType<MegaCrit.Sts2.Core.Nodes.Vfx.NCardTrailVfx>(TrailScenePath);
        _trailRegistered = true;
    }

    // Conversion supplies the game root type while retaining native children/unique markers.
    // BaseLib CustomAnimation discovers Visuals/AnimatedSprite2D and forwards game triggers.
    public static NCreatureVisuals CreateCombatVisuals() =>
        NodeFactory<NCreatureVisuals>.CreateFromScene(CombatScenePath);

    /// <summary>Explicit presentation events can address any of the 26 authored clips.</summary>
    public static void Play(NCreatureVisuals visuals, string clip)
    {
        var sprite = visuals.GetNode<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
        if (!sprite.SpriteFrames.HasAnimation(clip))
            throw new System.ArgumentException($"Unknown Volibear animation: {clip}", nameof(clip));
        sprite.Stop();
        sprite.Play(clip);
    }

    /// <summary>Choose the return pose without changing gameplay state or interrupting an action.</summary>
    public static void SetIdle(NCreatureVisuals visuals, string clip)
    {
        var sprite = visuals.GetNode<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
        if (!sprite.SpriteFrames.HasAnimation(clip) || !sprite.SpriteFrames.GetAnimationLoop(clip))
            throw new System.ArgumentException($"Not a looping Volibear pose: {clip}", nameof(clip));
        sprite.Set("return_animation", clip);
    }
}
