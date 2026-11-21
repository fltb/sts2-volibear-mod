using System;
using Godot;
using MegaCrit.Sts2.Core.Saves;
using GDictionary = Godot.Collections.Dictionary;

namespace Volibear.Presentation;

/// <summary>Explicit visual endpoints from the resolved game event, not predicted mouse targets.</summary>
public sealed record EffectAnchors(
    CanvasItem Owner, CanvasItem? Target = null, CanvasItem? Source = null,
    CanvasItem? Card = null, CanvasItem? Energy = null, CanvasItem? OwnerHand = null,
    CanvasItem? OwnerMouth = null, CanvasItem? CardCost = null);

/// <summary>
/// One owner per battle/room. The same production Godot controller is exercised by resource tests.
/// Call only from Godot's main thread. This API neither changes nor waits for game settlement.
/// </summary>
public sealed class VolibearEffects : IDisposable
{
    public const string ScenePath = "res://VolibearArt/scenes/volibear_effects.tscn";
    private readonly Node2D _root;
    private bool _disposed;

    private VolibearEffects(Node2D root) => _root = root;

    public static VolibearEffects Attach(Node sceneOwner, string battleId, string ownerId,
        Func<string, float>? gameVolumeLinear = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(battleId);
        ArgumentException.ThrowIfNullOrWhiteSpace(ownerId);
        if (!sceneOwner.IsInsideTree()) throw new ArgumentException("Scene owner must be in the tree", nameof(sceneOwner));
        var scene = ResourceLoader.Load<PackedScene>(ScenePath)
                    ?? throw new InvalidOperationException("Missing Volibear effects scene; rebuild the resource pack");
        var root = scene.Instantiate<Node2D>();
        var gain = gameVolumeLinear;
        var provider = gain == null ? Callable.From(ReadGameVolume) : Callable.From(() => new GDictionary
        {
            ["Sfx"] = Math.Clamp(gain("Sfx"), 0f, 1f),
            ["Voice"] = Math.Clamp(gain("Voice"), 0f, 1f),
            ["Ambience"] = Math.Clamp(gain("Ambience"), 0f, 1f)
        });
        root.Call("configure", battleId, ownerId, provider);
        sceneOwner.AddChild(root);
        return new VolibearEffects(root);
    }

    /// <summary>
    /// Uses committed event identity + effect + target for bounded duplicate suppression.
    /// Loops require a persistentKey and periodic RenewLoop while authoritative state remains active.
    /// For group damage, call once per resolved target with the same eventId: sound plays only once.
    /// </summary>
    public bool Emit(string eventId, string effectId, EffectAnchors anchors, string targetId = "",
        string? persistentKey = null, float leaseSeconds = 10f, bool sound = true)
    {
        if (!Alive) return false;
        ArgumentException.ThrowIfNullOrWhiteSpace(eventId);
        if ((anchors.Target != null || anchors.Card != null) && string.IsNullOrWhiteSpace(targetId))
            throw new ArgumentException("Target/card events require a stable target entity ID", nameof(targetId));
        var endpoints = new GDictionary { ["owner"] = anchors.Owner };
        Add(endpoints, "target", anchors.Target);
        Add(endpoints, "source", anchors.Source);
        Add(endpoints, "card", anchors.Card);
        Add(endpoints, "energy", anchors.Energy);
        Add(endpoints, "hand", anchors.OwnerHand);
        Add(endpoints, "mouth", anchors.OwnerMouth);
        Add(endpoints, "cost", anchors.CardCost);
        return _root.Call("emit_effect", eventId, effectId, endpoints, targetId,
            persistentKey ?? "", leaseSeconds, sound).AsBool();
    }

    public bool PlaySound(string eventId, string cueId, string? persistentKey = null,
        float leaseSeconds = 10f, bool allowDisabled = false) => Alive &&
        _root.Call("play_sound", eventId, cueId, persistentKey ?? "", leaseSeconds, allowDisabled).AsBool();

    /// <summary>
    /// A committed hit's geometry follows the actual visual Bounds and CenterPos.
    /// Index changes stroke direction only; this method does not schedule damage,
    /// select an enemy, play duplicate audio, or wait for the visual to finish.
    /// </summary>
    public bool EmitCombat(string eventId, string style, EffectAnchors anchors,
        string targetId = "", int hitIndex = 0, bool blocked = false, float intensity = 1f)
    {
        if (!Alive) return false;
        ArgumentException.ThrowIfNullOrWhiteSpace(eventId);
        if ((anchors.Target != null || anchors.Card != null) && string.IsNullOrWhiteSpace(targetId))
            throw new ArgumentException("Combat target/card events require a stable entity ID", nameof(targetId));
        var endpoints = new GDictionary { ["owner"] = anchors.Owner };
        Add(endpoints, "target", anchors.Target);
        Add(endpoints, "source", anchors.Source);
        Add(endpoints, "card", anchors.Card);
        Add(endpoints, "hand", anchors.OwnerHand);
        Add(endpoints, "mouth", anchors.OwnerMouth);
        var options = new GDictionary
        {
            ["hit_index"] = Math.Max(0, hitIndex),
            ["blocked"] = blocked,
            ["intensity"] = float.IsFinite(intensity) ? Math.Clamp(intensity, 0.45f, 1.8f) : 1f
        };
        return _root.Call("emit_combat", eventId, style, endpoints, targetId, options).AsBool();
    }

    public bool EmitSynergy(string eventId, string style, EffectAnchors anchors, string targetId = "") =>
        EmitCombat(eventId, style, anchors, targetId);

    internal bool HasPrivateSound(string cue) => Alive && _root.Call("has_private_sound", cue).AsBool();

    public bool RenewLoop(string key, float leaseSeconds = 10f) =>
        Alive && _root.Call("renew_loop", key, leaseSeconds).AsBool();

    public void StopLoop(string key, bool fadeAudio = true)
    {
        if (Alive) _root.Call("stop_loop", key, fadeAudio);
    }

    public void StopAll()
    {
        if (Alive) _root.Call("stop_all");
    }

    /// <summary>Stop sustained fields at combat ending; let committed hit tails expire.</summary>
    public void StopPersistent()
    {
        if (Alive) _root.Call("stop_persistent");
    }

    public int ActiveVisuals => Alive ? _root.Call("active_visuals").AsInt32() : 0;
    public int ActiveVoices => Alive ? _root.Call("active_voices").AsInt32() : 0;

    public void Dispose()
    {
        if (!Alive) { _disposed = true; return; }
        _root.Call("stop_all");
        _root.QueueFree();
        _disposed = true;
    }

    private bool Alive => !_disposed && GodotObject.IsInstanceValid(_root)
                           && _root.IsInsideTree() && !_root.IsQueuedForDeletion();

    private static void Add(GDictionary dictionary, string key, CanvasItem? node)
    {
        if (node != null) dictionary[key] = node;
    }

    // NAudioManager applies squared slider gains to FMOD; these independent native players
    // must honor the same settings explicitly. We never change the global Godot bus/driver.
    private static GDictionary ReadGameVolume()
    {
        var settings = SaveManager.Instance.SettingsSave;
        bool focused = DisplayServer.GetName() == "headless" || DisplayServer.WindowIsFocused();
        float master = !focused && SaveManager.Instance.PrefsSave.MuteInBackground
            ? 0f : Math.Clamp(settings.VolumeMaster, 0f, 1f);
        float sfx = Math.Clamp(settings.VolumeSfx, 0f, 1f);
        float ambience = Math.Clamp(settings.VolumeAmbience, 0f, 1f);
        return new GDictionary
        {
            ["Sfx"] = master * master * sfx * sfx,
            ["Voice"] = master * master * sfx * sfx,
            ["Ambience"] = master * master * ambience * ambience
        };
    }
}
