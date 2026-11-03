using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Godot;

namespace Volibear;

/// <summary>Exactly two already-loaded, read-only animation templates for an isolated gameplay batch.</summary>
internal sealed class NativeAcceptanceArtResidency : IDisposable
{
    internal const string FramesPath = "res://VolibearArt/scenes/volibear_frames.tres";
    internal const string EffectsFramesPath = "res://VolibearArt/scenes/volibear_effect_frames.tres";
    private const long MaxEffectsEstimatedBytes = 512L * 1024 * 1024;
    private const int MaxEffectsAtlases = 48, MaxEffectsDimension = 2048, MaxEffectsFrameTextures = 1536;
    private const int MaxAnimations = 64, MaxFrameReferences = 2048, MaxFrameTextures = 1024;
    private const int MaxUniqueAtlases = 32, MaxDimension = 4096;
    private const long MaxEstimatedBytes = 2L * 1024 * 1024 * 1024;
    private static readonly HashSet<string> AtlasPaths = new(new[] {
        "idle_loop", "relaxed_loop", "weak_loop", "attack", "attack_heavy", "bite", "cast", "hurt",
        "block", "counter", "domain_enter", "domain_idle", "domain_exit", "feral_enter", "feral_idle",
        "die", "domain_attack", "domain_cast", "domain_hurt", "domain_block", "domain_weak_loop",
        "domain_die", "roar", "storm_leap", "domain_roar", "domain_storm_leap"
    }.Select(name => "res://VolibearArt/animations/atlases/" + name + ".png"), StringComparer.Ordinal);

    private static readonly HashSet<string> EffectsAtlasPaths = new(new[] {
        "claw_slash", "heavy_impact", "bite_hit", "guard_gain", "guard_hit", "guard_break", "counter_release",
        "absorb", "lightning_strike", "lightning_chain", "lightning_all", "lightning_growth", "domain_enter",
        "domain_loop", "domain_exit", "domain_suppress", "card_purify", "feral_transfer", "feral_claw", "feral_body",
        "feral_aura", "mark_bite", "wound", "weakness", "charge", "strength", "armor_retain", "armor_iron",
        "card_draw", "card_retrieve", "card_discard", "card_exhaust", "energy_gain", "cost_reduce", "card_replay",
        "lifesteal", "heal", "roar_wave", "thunder_armor", "cast_charge"
    }.Select(name => "res://VolibearArt/vfx/atlases/" + name + ".png"), StringComparer.Ordinal);

    // The native Array owns only actor[0] and effects[1]. Fingerprints contain values,
    // never Nodes, models, materials, audio or a second collection of resource refs.
    private readonly Godot.Collections.Array<SpriteFrames> held = new();
    private readonly Fingerprint?[] original = new Fingerprint?[2];
    private bool disposed;
    private readonly long[] captureCalls = new long[2];
    private readonly double[] captureTotalMs = new double[2], captureMaxMs = new double[2];
    private sealed record Fingerprint(string Digest, int Animations, int Frames, int FrameTextures,
                                      int Atlases, long EstimatedBytes);

    internal NativeAcceptanceArtResidency()
    {
        try
        {
            if (ResourceLoader.GetCachedRef(FramesPath) is not SpriteFrames frames)
                throw new InvalidOperationException("Acceptance art residency requires already-cached Volibear frames");
            held.Add(frames);
            original[0] = Capture(frames, effects: false);
            if (ResourceLoader.GetCachedRef(EffectsFramesPath) is not SpriteFrames effects)
                throw new InvalidOperationException("Acceptance art residency requires already-cached Volibear effects frames");
            held.Add(effects);
            original[1] = Capture(effects, effects: true);
            CheckTotalBudget(original[0]!, original[1]!);
            for (int index = 0; index < 2; index++)
            {
                var captured = original[index]!;
                GD.Print($"[Volibear] NATIVE_ART_RESIDENCY acquired template={(index == 0 ? "actor" : "effects")} held={held.Count} animations={captured.Animations} " +
                         $"frames={captured.Frames} frameTextures={captured.FrameTextures} atlases={captured.Atlases} " +
                         $"estimatedRgbaMipBytes={captured.EstimatedBytes} estimateNotGpuMeasurement=true");
            }
        }
        catch
        {
            held.Clear();
            original[0] = original[1] = null;
            disposed = true;
            throw;
        }
    }

    internal void Validate()
    {
        if (disposed || held.Count != 2 || original[0] is null || original[1] is null)
            throw new InvalidOperationException("Acceptance art residency is not active");
        var frames = held[0];
        var effects = held[1];
        if (!GodotObject.IsInstanceValid(frames) || !GodotObject.IsInstanceValid(effects) ||
            ResourceLoader.GetCachedRef(FramesPath) is not SpriteFrames cached ||
            !GodotObject.IsInstanceValid(cached) || cached.GetInstanceId() != frames.GetInstanceId() ||
            ResourceLoader.GetCachedRef(EffectsFramesPath) is not SpriteFrames cachedEffects ||
            !GodotObject.IsInstanceValid(cachedEffects) || cachedEffects.GetInstanceId() != effects.GetInstanceId() ||
            Capture(frames, effects: false) != original[0] || Capture(effects, effects: true) != original[1])
            throw new InvalidOperationException("Acceptance shared animation resource changed during gameplay batch");
        CheckTotalBudget(original[0]!, original[1]!);
    }

    private static void CheckTotalBudget(Fingerprint actor, Fingerprint effects)
    {
        if (checked(actor.EstimatedBytes + effects.EstimatedBytes) > MaxEstimatedBytes)
            throw new InvalidOperationException("Acceptance combined template residency exceeds fixed estimated-byte bound");
    }

    private Fingerprint Capture(SpriteFrames frames, bool effects)
    {
        int index = effects ? 1 : 0;
        long started = Stopwatch.GetTimestamp();
        try { return CaptureValues(frames, effects); }
        finally
        {
            double elapsed = Stopwatch.GetElapsedTime(started).TotalMilliseconds;
            captureCalls[index]++;
            captureTotalMs[index] += elapsed;
            captureMaxMs[index] = Math.Max(captureMaxMs[index], elapsed);
        }
    }

    private static Fingerprint CaptureValues(SpriteFrames frames, bool effects)
    {
        if (!GodotObject.IsInstanceValid(frames) || frames.ResourcePath != (effects ? EffectsFramesPath : FramesPath))
            throw new InvalidOperationException("Unexpected acceptance animation resource identity/path");
        var names = frames.GetAnimationNames();
        if (names.Length == 0 || names.Length > MaxAnimations || names.Distinct(StringComparer.Ordinal).Count() != names.Length)
            throw new InvalidOperationException("Acceptance animation count exceeds fixed bound");
        System.Array.Sort(names, StringComparer.Ordinal);
        using var bytes = new MemoryStream();
        using var writer = new BinaryWriter(bytes);
        writer.Write(frames.GetInstanceId());
        writer.Write(frames.ResourcePath);
        writer.Write(names.Length);
        var frameTextures = new HashSet<ulong>();
        var atlases = new HashSet<ulong>();
        int references = 0;
        long estimate = 0;
        foreach (var animation in names)
        {
            using var name = new StringName(animation);
            int count = frames.GetFrameCount(name);
            if (count <= 0 || count > MaxFrameReferences - references)
                throw new InvalidOperationException("Acceptance frame count exceeds fixed bound");
            references += count;
            writer.Write(animation);
            writer.Write(frames.GetAnimationLoop(name));
            writer.Write(frames.GetAnimationSpeed(name));
            writer.Write(count);
            for (int index = 0; index < count; index++)
            {
                writer.Write(frames.GetFrameDuration(name, index));
                if (frames.GetFrameTexture(name, index) is not AtlasTexture texture ||
                    !GodotObject.IsInstanceValid(texture))
                    throw new InvalidOperationException("Acceptance frames must reference the fixed compressed Volibear atlases");
                ulong textureId = texture.GetInstanceId();
                // Every ordered frame reference retains its duration and texture identity,
                // including aliases. Details are read once per identity in THIS synchronous
                // capture only; no values are reused across Validate calls.
                writer.Write(textureId);
                if (!frameTextures.Add(textureId)) continue;
                if (frameTextures.Count > (effects ? MaxEffectsFrameTextures : MaxFrameTextures))
                    throw new InvalidOperationException("Acceptance frame texture count exceeds fixed bound");
                writer.Write(texture.ResourcePath);
                WriteRect(writer, texture.Region);
                WriteRect(writer, texture.Margin);
                writer.Write(texture.FilterClip);
                if (texture.Atlas is not CompressedTexture2D atlas || !GodotObject.IsInstanceValid(atlas))
                    throw new InvalidOperationException("Acceptance frames must reference the fixed compressed Volibear atlases");
                ulong atlasId = atlas.GetInstanceId();
                writer.Write(atlasId); // Preserve each unique frame texture's atlas binding.
                if (!atlases.Add(atlasId)) continue;
                string path = atlas.ResourcePath;
                if (!(effects ? EffectsAtlasPaths : AtlasPaths).Contains(path))
                    throw new InvalidOperationException("Acceptance frames must reference the fixed compressed Volibear atlases");
                int width = atlas.GetWidth(), height = atlas.GetHeight();
                int maxDimension = effects ? MaxEffectsDimension : MaxDimension;
                if (width <= 0 || height <= 0 || width > maxDimension || height > maxDimension)
                    throw new InvalidOperationException("Acceptance atlas dimensions exceed fixed bound");
                writer.Write(path);
                writer.Write(width);
                writer.Write(height);
                writer.Write(atlas.GetRid().Id);
                // Conservative RGBA plus mip allowance, not measured GPU allocation.
                estimate = checked(estimate + (long)width * height * 6);
                if (atlases.Count > (effects ? MaxEffectsAtlases : MaxUniqueAtlases) ||
                    estimate > (effects ? MaxEffectsEstimatedBytes : MaxEstimatedBytes))
                    throw new InvalidOperationException("Acceptance atlas residency exceeds fixed count/estimated-byte bound");
            }
        }
        writer.Flush();
        return new(Convert.ToHexString(SHA256.HashData(bytes.GetBuffer().AsSpan(0, checked((int)bytes.Length)))),
                   names.Length, references, frameTextures.Count, atlases.Count, estimate);
    }

    private static void WriteRect(BinaryWriter writer, Rect2 rect)
    {
        writer.Write(rect.Position.X); writer.Write(rect.Position.Y);
        writer.Write(rect.Size.X); writer.Write(rect.Size.Y);
    }

    public void Dispose()
    {
        if (disposed) return;
        try { Validate(); }
        finally
        {
            held.Clear();
            original[0] = original[1] = null;
            disposed = true;
            for (int index = 0; index < 2; index++)
                GD.Print(FormattableString.Invariant($"[Volibear] NATIVE_ART_RESIDENCY released held={held.Count} template={(index == 0 ? "actor" : "effects")} captureCalls={captureCalls[index]} captureTotalMs={captureTotalMs[index]:F3} captureMaxMs={captureMaxMs[index]:F3}"));
            if (held.Count != 0) throw new InvalidOperationException("Acceptance art residency retained a native reference");
        }
    }
}
