// integration_source_uncompiled. Godot 4.5.1 APIs; no FMOD bank required.
using System;
using System.Collections.Generic;
using System.Text.Json;
using Godot;

namespace VolibearMod.ArtV5;

/// <summary>One instance per creature. Owns only this creature's audio nodes.</summary>
public partial class VolibearCueAudio : Node
{
    private sealed record Cue(string Path, bool Loop, float GainDb, int CooldownMs, int MaxVoices, string Bus);
    private readonly Dictionary<string, Cue> _cues = new(StringComparer.Ordinal);
    private readonly Dictionary<string, ulong> _lastStart = new(StringComparer.Ordinal);
    private readonly Dictionary<string, List<AudioStreamPlayer>> _voices = new(StringComparer.Ordinal);
    private readonly Dictionary<string, AudioStreamPlayer> _loops = new(StringComparer.Ordinal);
    private bool _closing;

    // The adapter supplies the remaining SFX/voice gain, including mute.
    // Account for gain already applied by Master to avoid multiplying it twice.
    // Do not assume native buses automatically inherit every FMOD mixer control.
    // The default is useful for the offline asset demo only.
    public Func<string, float> GameVolumeLinear { get; set; } = _ => 1f;

    public void LoadManifest(string path = "res://VolibearArt/audio/manifest.json")
    {
        using var f = Godot.FileAccess.Open(path, Godot.FileAccess.ModeFlags.Read)
            ?? throw new InvalidOperationException($"Missing audio manifest: {path}");
        using var d = JsonDocument.Parse(f.GetAsText());
        string folder = path[..(path.LastIndexOf('/') + 1)];
        foreach (var item in d.RootElement.GetProperty("cues").EnumerateArray())
        {
            string id = item.GetProperty("id").GetString()!;
            string relative = item.GetProperty("file").GetString()!;
            if (relative.Contains("..", StringComparison.Ordinal) || relative.Contains(':'))
                throw new InvalidOperationException($"Invalid audio path: {relative}");
            var cue = new Cue(folder + relative, item.GetProperty("loop").GetBoolean(),
                item.GetProperty("gain_db").GetSingle(), item.GetProperty("cooldown_ms").GetInt32(),
                Math.Max(1, item.GetProperty("max_voices").GetInt32()),
                item.GetProperty("bus").GetString() ?? "Sfx");
            if (!_cues.TryAdd(id, cue)) throw new InvalidOperationException($"Duplicate cue: {id}");
        }
    }

    /// <summary>Call once for a committed visual event; never once per render frame.</summary>
    public bool PlayCue(string id)
    {
        if (_closing || !_cues.TryGetValue(id, out var cue)) return false;
        if (cue.Loop && _loops.TryGetValue(id, out var oldLoop) && GodotObject.IsInstanceValid(oldLoop)) return true;
        ulong now = Time.GetTicksMsec();
        if (_lastStart.TryGetValue(id, out var last) && now - last < (ulong)Math.Max(0, cue.CooldownMs)) return false;

        if (!_voices.TryGetValue(id, out var list)) _voices[id] = list = [];
        list.RemoveAll(p => !GodotObject.IsInstanceValid(p));
        while (list.Count >= cue.MaxVoices)
        {
            var oldest = list[0]; list.RemoveAt(0);
            oldest.Stop(); oldest.Stream=null; oldest.QueueFree();
        }
        var stream = GD.Load<AudioStream>(cue.Path)?.Duplicate() as AudioStream
            ?? throw new InvalidOperationException($"Cannot load audio: {cue.Path}");
        // Duplicate before setting loop so a shared import is never mutated.
        if (stream is AudioStreamOggVorbis ogg) ogg.Loop = cue.Loop;
        else if (stream is AudioStreamWav wav) wav.LoopMode = cue.Loop ? AudioStreamWav.LoopModeEnum.Forward : AudioStreamWav.LoopModeEnum.Disabled;
        var p = new AudioStreamPlayer {Stream = stream, Bus = "Master"};
        AddChild(p);
        float mix = Math.Clamp(GameVolumeLinear(cue.Bus), 0f, 1f);
        p.VolumeDb = mix <= 0 ? float.NegativeInfinity : cue.GainDb + Mathf.LinearToDb(mix);
        p.Finished += () => { list.Remove(p); if (GodotObject.IsInstanceValid(p)) p.QueueFree(); };
        list.Add(p);
        if (cue.Loop) _loops[id] = p;
        _lastStart[id] = now;
        p.Play();
        return true;
    }

    public void RefreshGameVolume()
    {
        foreach (var (id, list) in _voices)
        {
            var cue = _cues[id];
            float mix = Math.Clamp(GameVolumeLinear(cue.Bus), 0f, 1f);
            float db = mix <= 0 ? float.NegativeInfinity : cue.GainDb + Mathf.LinearToDb(mix);
            foreach (var p in list) if (GodotObject.IsInstanceValid(p)) p.VolumeDb = db;
        }
    }

    public void StopLoop(string id)
    {
        if (!_loops.Remove(id, out var p) || !GodotObject.IsInstanceValid(p)) return;
        p.Stop(); p.Stream=null; p.QueueFree();
        if (_voices.TryGetValue(id, out var list)) list.Remove(p);
    }

    public void StopAllOwned()
    {
        foreach (var list in _voices.Values)
            foreach (var p in list) if (GodotObject.IsInstanceValid(p)) {p.Stop(); p.Stream=null; p.QueueFree();}
        _voices.Clear(); _loops.Clear();
    }

    public override void _ExitTree() { _closing = true; StopAllOwned(); }
}
