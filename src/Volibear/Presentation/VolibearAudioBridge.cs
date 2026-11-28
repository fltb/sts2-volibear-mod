using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Audio;

namespace Volibear.Presentation;

/// <summary>
/// Routes our FMOD events through the game's own one-shot entry point instead of
/// creating instances ourselves: the game owns playback, the bank only needs to be
/// registered. Missing events are logged and skipped, never handed to the addon.
/// </summary>
internal static class VolibearAudioBridge
{
    internal const string BankPath = "res://VolibearArt/audio/fmod/Volibear.bank";
    internal const string EventPrefix = "event:/volibear/";

    private static readonly Dictionary<string, string> Guids = new(StringComparer.Ordinal);
    private static bool _mapLoaded;
    private static bool _bankWarningShown;

    internal static bool IsVolibearEvent(string path) =>
        path.StartsWith(EventPrefix, StringComparison.Ordinal);

    internal static void EnsureBank()
    {
        var server = Engine.GetSingleton("FmodServer");
        if (server is null) return;
        try
        {
            server.Call("load_bank", BankPath, 0);
        }
        catch (Exception error)
        {
            if (_bankWarningShown) return;
            _bankWarningShown = true;
            GD.PushWarning("[Volibear] FMOD bank load failed: " + error.Message);
        }
    }

    internal static string? GuidFor(string eventPath)
    {
        if (!_mapLoaded)
        {
            _mapLoaded = true;
            using var file = Godot.FileAccess.Open("res://VolibearArt/audio/fmod/GUIDs.txt", Godot.FileAccess.ModeFlags.Read);
            while (file is not null && !file.EofReached())
            {
                var line = file.GetLine().Trim();
                var space = line.IndexOf(' ');
                if (space > 0) Guids[line[(space + 1)..].Trim()] = line[..space].Trim();
            }
        }
        return Guids.TryGetValue(eventPath, out var guid) ? guid : null;
    }

    private static bool _gainLogged;

    /// <summary>
    /// The gain the game's native SFX travel through (master bus squared, then SFX bus
    /// squared). Our bank's events land on the FMOD root bus, where neither of those buses
    /// attenuates them, so the cue applies the same chain itself before handing the volume
    /// to NAudioManager. This keeps a cue's level equal to the native layer it was anchored to.
    /// </summary>
    internal static float SfxBusGain() => VolibearEffects.SfxChainGain();

    /// <summary>Plays one of our cues through NAudioManager, exactly like a native sound.</summary>
    internal static bool PlayCue(string eventPath, float volume)
    {
        if (GuidFor(eventPath) is null)
        {
            GD.PushWarning("[Volibear] FMOD event missing from GUID map: " + eventPath);
            return false;
        }
        var manager = NAudioManager.Instance;
        if (manager is null) return false;
        manager.PlayOneShot(eventPath, new Dictionary<string, float>(), volume);
        return true;
    }

    /// <summary>
    /// Runs inside the game's PlayOneShot prefix: resolve our path to the loaded
    /// bank's GUID and start it. Returns true when the sound was started here.
    /// </summary>
    internal static bool PlayMapped(string eventPath, float volume)
    {
        var guid = GuidFor(eventPath);
        if (guid is null)
        {
            GD.PushWarning("[Volibear] FMOD event missing from GUID map: " + eventPath);
            return false;
        }
        var server = Engine.GetSingleton("FmodServer");
        if (server is null) return false;
        EnsureBank();
        var instance = server.Call("create_event_instance_with_guid", guid);
        if (instance.VariantType == Variant.Type.Nil)
        {
            GD.PushWarning("[Volibear] FMOD event not loaded: " + eventPath);
            return false;
        }
        var obj = instance.AsGodotObject();
        if (obj is null) return false;
        // No artificial ceiling: the authored level is the level. Only a non-finite
        // value is rejected, because FMOD cannot represent it.
        var applied = volume * SfxBusGain();
        if (!float.IsFinite(applied)) return false;
        GD.Print($"[Volibear] CUE {eventPath} vol={applied:0.####}");
        if (!_gainLogged)
        {
            _gainLogged = true;
            LogMixState(server, volume, applied);
        }
        obj.Set("volume", applied);
        obj.Call("start");
        return true;
    }

    /// <summary>One-shot diagnostic: what the game's buses actually hold when a cue plays.</summary>
    private static void LogMixState(GodotObject server, float requested, float applied)
    {
        var buses = "";
        try
        {
            if (server.Call("get_all_buses").AsGodotArray() is { } list)
            {
                foreach (var entry in list)
                {
                    var bus = entry.AsGodotObject();
                    if (bus is null) continue;
                    var path = bus.Call("get_path").AsString();
                    var volume = bus.Call("get_volume").AsSingle();
                    buses += $"{path}={volume:0.###} ";
                }
            }
        }
        catch (Exception error)
        {
            buses = "unavailable(" + error.GetType().Name + ")";
        }
        var sliders = VolibearEffects.ChainSliders();
        GD.Print($"[Volibear] AUDIO requested={requested:0.###} applied={applied:0.###} " +
                 $"master={sliders.Master:0.###} sfx={sliders.Sfx:0.###} chain={sliders.Master * sliders.Master * sliders.Sfx * sliders.Sfx:0.####} " +
                 $"buses: {buses}".TrimEnd());
    }
}
