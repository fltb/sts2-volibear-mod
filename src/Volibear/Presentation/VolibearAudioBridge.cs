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
        manager.PlayOneShot(eventPath, new Dictionary<string, float>(), Math.Clamp(volume, 0f, 2f));
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
        obj.Set("volume", Math.Clamp(volume, 0f, 2f));
        obj.Call("start");
        return true;
    }
}
