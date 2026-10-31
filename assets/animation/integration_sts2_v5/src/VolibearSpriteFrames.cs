// integration_source_uncompiled
// Original integration example for this delivery, not a tested game DLL.
// Source API snapshot: RitsuLib commit 772f280964f2efc7c7e2f29fc59844e68616dd57.
// stage_assets.py places the final atlases and JSON below res://VolibearArt/.
// This V5 sample reads atlas rectangles; it does not import 940 separate textures.
using System;
using System.Collections.Generic;
using System.Text.Json;
using Godot;
using STS2RitsuLib.Scaffolding.Visuals.StateMachine;
using STS2RitsuLib.Scaffolding.Visuals.StateMachine.Backends;

namespace VolibearMod.ArtV5;

/// <summary>Per-creature presentation flags. Gameplay code owns these values.</summary>
public sealed class VolibearPlaybackFlags
{
    public bool Domain { get; set; }
    public bool LowHealth { get; set; }

    // Feral is presentation only: the card mechanic transforms cards in hand.
    // There is deliberately no public permanent Feral buff switch here.
    internal bool FeralPoseActive { get; private set; }
    internal long FeralPoseToken { get; private set; }

    internal long BeginTemporaryFeralPose()
    {
        FeralPoseActive = true;
        return ++FeralPoseToken;
    }

    public void ClearTemporaryFeralPose()
    {
        FeralPoseActive = false;
        FeralPoseToken++;
    }
}

public readonly record struct VolibearPlaybackSlice(
    string Clip, int StartFrame, int EndFrameInclusive, double TimeOffsetSeconds);

public static class VolibearSpriteFrames
{
    public static readonly string[] RequiredClips =
    {
        "idle_loop", "relaxed_loop", "weak_loop", "attack", "attack_heavy",
        "bite", "cast", "hurt", "block", "counter", "domain_enter",
        "domain_idle", "domain_exit", "feral_enter", "feral_idle", "die",
        "domain_attack", "domain_cast", "domain_hurt", "domain_block",
        "domain_weak_loop", "domain_die", "roar", "storm_leap"
    };
    public static readonly string[] RequiredVariants = { "domain_roar", "domain_storm_leap" };

    private static IEnumerable<string> RequiredSequenceNames()
    {
        foreach (var name in RequiredClips) yield return name;
        foreach (var name in RequiredVariants) yield return name;
    }

    /// <summary>
    /// Reads the actual delivery schema and each atlas JSON rectangle.
    /// Does not guess frame counts, file names, or trimmed bounds.
    /// </summary>
    public static SpriteFrames Load(string manifestResourcePath)
    {
        if (!manifestResourcePath.StartsWith("res://", StringComparison.Ordinal))
            throw new ArgumentException("Expected a res:// manifest path.", nameof(manifestResourcePath));

        using var file = Godot.FileAccess.Open(manifestResourcePath, Godot.FileAccess.ModeFlags.Read);
        if (file == null)
            throw new InvalidOperationException($"Cannot read {manifestResourcePath}; include JSON in PCK export.");

        using var document = JsonDocument.Parse(file.GetAsText());
        var root = document.RootElement;
        if (root.GetProperty("schema_version").GetInt32() != 1)
            throw new InvalidOperationException("Unsupported animation manifest schema.");

        var directory = manifestResourcePath[..(manifestResourcePath.LastIndexOf('/') + 1)];
        var result = new SpriteFrames();
        if (result.HasAnimation("default")) result.RemoveAnimation("default");
        var seen = new HashSet<string>(StringComparer.Ordinal);

        var sequences = new List<JsonElement>();
        foreach (var clip in root.GetProperty("clips").EnumerateArray()) sequences.Add(clip);
        if (root.TryGetProperty("variants", out var variants))
            foreach (var variant in variants.EnumerateArray()) sequences.Add(variant);
        foreach (var clip in sequences)
        {
            var name = clip.GetProperty("name").GetString();
            if (string.IsNullOrWhiteSpace(name) || !seen.Add(name))
                throw new InvalidOperationException("Empty or duplicate clip name.");
            var fps = clip.TryGetProperty("fps", out var clipFps)
                ? clipFps.GetDouble() : root.GetProperty("fps").GetDouble();
            if (!double.IsFinite(fps) || fps <= 0)
                throw new InvalidOperationException($"Invalid FPS: {name}");

            result.AddAnimation(name);
            result.SetAnimationSpeed(name, fps);
            result.SetAnimationLoop(name, clip.GetProperty("loop").GetBoolean());

            var atlas = clip.GetProperty("atlas");
            var imagePath = atlas.GetProperty("image").GetString()
                ?? throw new InvalidOperationException($"Missing atlas image: {name}");
            var jsonPath = atlas.GetProperty("json").GetString()
                ?? throw new InvalidOperationException($"Missing atlas JSON: {name}");
            foreach (var relativePath in new[] {imagePath, jsonPath})
            {
                if (relativePath.StartsWith('/') || relativePath.Contains('\\') ||
                    relativePath.Contains(':') || relativePath.Contains("..", StringComparison.Ordinal))
                    throw new InvalidOperationException($"Expected a manifest-relative atlas path: {relativePath}");
            }
            var atlasTexture = GD.Load<Texture2D>(directory + imagePath)
                ?? throw new InvalidOperationException($"Missing imported texture: {imagePath}");
            using var atlasFile = Godot.FileAccess.Open(directory + jsonPath, Godot.FileAccess.ModeFlags.Read)
                ?? throw new InvalidOperationException($"Missing atlas metadata: {jsonPath}");
            using var atlasDocument = JsonDocument.Parse(atlasFile.GetAsText());
            var count = 0;
            foreach (var frame in atlasDocument.RootElement.GetProperty("frames").EnumerateArray())
            {
                var durationMs = frame.GetProperty("duration_ms").GetDouble();
                if (!double.IsFinite(durationMs) || durationMs <= 0)
                    throw new InvalidOperationException($"Invalid frame duration: {name}/{count}");
                var rect = frame.GetProperty("rect");
                var region = new Rect2(rect[0].GetSingle(), rect[1].GetSingle(), rect[2].GetSingle(), rect[3].GetSingle());
                if (region.Position.X < 0 || region.Position.Y < 0 ||
                    region.End.X > atlasTexture.GetWidth() || region.End.Y > atlasTexture.GetHeight())
                    throw new InvalidOperationException($"Atlas rectangle outside texture: {name}/{count}");
                var texture = new AtlasTexture {Atlas = atlasTexture, Region = region, FilterClip = true};

                // SpriteFrames uses relative frame duration: seconds = duration / FPS.
                // 41.666... ms at 24 FPS therefore becomes 1.0, not 0.041666.
                result.AddFrame(name, texture, durationMs * fps / 1000.0);
                count++;
            }
            if (count == 0 || count != clip.GetProperty("frame_count").GetInt32())
                throw new InvalidOperationException($"Frame count mismatch: {name}");
        }
        foreach (var name in RequiredSequenceNames())
            if (!seen.Contains(name)) throw new InvalidOperationException($"Required clip missing: {name}");
        return result;
    }

    /// <summary>
    /// Standard game triggers plus this project's explicit extensions.
    /// Rest priority is a project decision: domain+weak > domain > weak > short feral pose > normal.
    /// This function does not define health thresholds or implement card effects.
    /// </summary>
    public static ModAnimStateMachine CreateMachine(AnimatedSprite2D sprite, VolibearPlaybackFlags flags)
    {
        ArgumentNullException.ThrowIfNull(sprite);
        ArgumentNullException.ThrowIfNull(flags);
        if (sprite.SpriteFrames == null)
            throw new InvalidOperationException("Load SpriteFrames before creating the state machine.");

        var builder = ModAnimStateMachineBuilder.Create();
        foreach (var name in RequiredSequenceNames())
        {
            if (!sprite.SpriteFrames.HasAnimation(name) || sprite.SpriteFrames.GetFrameCount(name) == 0)
                throw new InvalidOperationException($"Missing animation on sprite: {name}");
            var state = builder.AddState(name, sprite.SpriteFrames.GetAnimationLoop(name));
            if (name == "idle_loop") state.AsInitial();
        }

        bool terminal = false;
        void IdleRoutes(string trigger, bool allowWhileDead = false)
        {
            builder.AddAnyState(trigger, "domain_weak_loop", () => (!terminal || allowWhileDead) && flags.Domain && flags.LowHealth);
            builder.AddAnyState(trigger, "domain_idle", () => (!terminal || allowWhileDead) && flags.Domain && !flags.LowHealth);
            builder.AddAnyState(trigger, "weak_loop", () => (!terminal || allowWhileDead) && !flags.Domain && flags.LowHealth);
            builder.AddAnyState(trigger, "feral_idle", () => (!terminal || allowWhileDead) && !flags.Domain && !flags.LowHealth && flags.FeralPoseActive);
            builder.AddAnyState(trigger, "idle_loop", () => (!terminal || allowWhileDead) && !flags.Domain && !flags.LowHealth && !flags.FeralPoseActive);
        }
        void ActionRoutes(string trigger, string normal, string domain)
        {
            builder.AddAnyState(trigger, domain, () => !terminal && flags.Domain);
            builder.AddAnyState(trigger, normal, () => !terminal && !flags.Domain);
        }

        IdleRoutes("Idle");
        IdleRoutes("Revive", allowWhileDead: true); // Explicit idle fallback, not a supplied revive clip.
        ActionRoutes("Attack", "attack", "domain_attack");
        ActionRoutes("Cast", "cast", "domain_cast");
        ActionRoutes("Hit", "hurt", "domain_hurt");
        ActionRoutes("Dead", "die", "domain_die");
        builder.AddAnyState("Relaxed", "relaxed_loop", () => !terminal);

        // Extension triggers: the game will not emit these without project hooks.
        // Domain has four action variants. Reuse its attack for the three
        // specialized damage actions, preserving the domain's logical action branch.
        // Clean V5 atlases share neutral body colors; domain VFX/tint is separate.
        ActionRoutes("HeavyAttack", "attack_heavy", "domain_attack");
        ActionRoutes("Bite", "bite", "domain_attack");
        ActionRoutes("Counter", "counter", "domain_attack");
        ActionRoutes("Block", "block", "domain_block");
        ActionRoutes("Roar", "roar", "domain_roar");
        ActionRoutes("StormLeap", "storm_leap", "domain_storm_leap");
        builder.AddAnyState("DomainEnter", "domain_enter", () => !terminal);
        builder.AddAnyState("DomainExit", "domain_exit", () => !terminal);
        ActionRoutes("FeralEnter", "feral_enter", "domain_cast");
        builder.AddAnyState("FeralPose", "feral_idle", () => !terminal && !flags.Domain && !flags.LowHealth && flags.FeralPoseActive);
        builder.AddAnyState("LowHealth", "domain_weak_loop", () => !terminal && flags.Domain && flags.LowHealth);
        builder.AddAnyState("LowHealth", "weak_loop", () => !terminal && !flags.Domain && flags.LowHealth);

        // Build starts the initial state. Do not also run sprite.Play("idle_loop")
        // in a second update loop: the state machine owns body playback.
        var machine = builder.Build(new AnimatedSprite2DBackend(sprite));
        machine.AnimationStarted += state =>
        {
            // Godot Play(same_name) can resume an existing animation. A newly
            // triggered one-shot should start at frame zero even on repeated hits.
            if (!state.IsLooping) sprite.SetFrameAndProgress(0, 0f);
            if (state.Id is "die" or "domain_die") terminal = true;
            else if (IsRest(state.Id)) terminal = false; // Reached after explicit Revive when dead.
        };
        machine.AnimationCompleted += state =>
        {
            // A hand-transform card's brief feral action never creates a lasting
            // body form. Default completion returns to actual domain/weak/normal.
            if (state.Id == "feral_enter") flags.ClearTemporaryFeralPose();
            // No fixed WithNext("idle_loop"): that would lose the active domain
            // or low-health state after every hit/attack. Resolve at completion.
            if (state.Id is not ("die" or "domain_die") && !state.IsLooping) machine.SetTrigger("Idle");
        };
        machine.SetTrigger("Idle"); // Honor restored per-creature flags on scene creation.
        return machine;
    }

    public static void RefreshIdleIfResting(ModAnimStateMachine machine)
    {
        if (machine.Current is { } state && IsRest(state.Id)) machine.SetTrigger("Idle");
    }

    /// <summary>
    /// For C10/U28/R09 after the separate challenge/guard action already finished.
    /// Normal: counter frames 14..31. Domain: full domain_attack, never seek to 14.
    /// Returns the event-time offset, or null when the trigger was rejected.
    /// This function performs no damage, block, resource spending or card effects.
    /// </summary>
    public static VolibearPlaybackSlice? PlayPostChallengeCounter(AnimatedSprite2D sprite,
        ModAnimStateMachine machine, VolibearPlaybackFlags flags)
    {
        bool useDomain = flags.Domain;
        string clip = useDomain ? "domain_attack" : "counter";
        machine.SetTrigger("Counter");
        if (machine.Current?.Id != clip) return null;

        // SetTrigger synchronously raises AnimationStarted, whose restart-at-zero
        // handler has already run. Seek only AFTER that handler completed.
        int firstFrame = useDomain ? 0 : 14;
        var frames = sprite.SpriteFrames;
        int count = frames.GetFrameCount(clip);
        double fps = frames.GetAnimationSpeed(clip);
        if ((!useDomain && count != 32) || count <= firstFrame || fps <= 0)
            throw new InvalidOperationException("Counter slice no longer matches this delivery's frame contract.");
        sprite.SetFrameAndProgress(firstFrame, 0f);
        double offsetSeconds = 0;
        for (int i = 0; i < firstFrame; i++) offsetSeconds += frames.GetFrameDuration(clip, i) / fps;
        return new VolibearPlaybackSlice(clip, firstFrame, count - 1, offsetSeconds);
    }

    /// <summary>
    /// Optional short feral_idle pose, separate from the hand-transform mechanic.
    /// It expires automatically; overlapping requests cannot cancel a newer timer.
    /// Default FeralEnter does not call this method.
    /// </summary>
    public static void PlayTemporaryFeralPose(AnimatedSprite2D sprite,
        ModAnimStateMachine machine, VolibearPlaybackFlags flags, double seconds = 0.5)
    {
        if (flags.Domain || flags.LowHealth || !IsRest(machine.Current?.Id ?? ""))
            return;
        if (!sprite.IsInsideTree())
            throw new InvalidOperationException("Temporary pose timer requires an active scene tree.");
        if (!double.IsFinite(seconds) || seconds <= 0)
            throw new ArgumentOutOfRangeException(nameof(seconds));

        var token = flags.BeginTemporaryFeralPose();
        var timer = new Godot.Timer { OneShot = true, WaitTime = Math.Clamp(seconds, 0.05, 0.5) };
        sprite.AddChild(timer);
        timer.Timeout += () =>
        {
            if (flags.FeralPoseToken == token)
            {
                flags.ClearTemporaryFeralPose();
                RefreshIdleIfResting(machine);
            }
            timer.QueueFree();
        };
        machine.SetTrigger("FeralPose");
        if (machine.Current?.Id == "feral_idle") sprite.SetFrameAndProgress(0, 0f);
        timer.Start();
    }

    public static void EndTemporaryFeralPose(ModAnimStateMachine machine, VolibearPlaybackFlags flags)
    {
        flags.ClearTemporaryFeralPose();
        RefreshIdleIfResting(machine);
    }

    /// <summary>
    /// This project's configurable visual hysteresis, not a vanilla-game fact.
    /// Defaults: enter at <=30% HP, exit at >=35% HP.
    /// Call from the project's health-change hook, then RefreshIdleIfResting.
    /// </summary>
    public static void UpdateLowHealth(VolibearPlaybackFlags flags, double hp, double maxHp,
        double enterAt = 0.30, double exitAt = 0.35)
    {
        if (!double.IsFinite(hp) || !double.IsFinite(maxHp) || maxHp <= 0 ||
            !double.IsFinite(enterAt) || !double.IsFinite(exitAt) ||
            enterAt < 0 || exitAt > 1 || enterAt >= exitAt)
            throw new ArgumentOutOfRangeException(nameof(maxHp), "Invalid HP or hysteresis thresholds.");
        double ratio = hp / maxHp;
        flags.LowHealth = flags.LowHealth ? ratio < exitAt : ratio <= enterAt;
        if (flags.LowHealth) flags.ClearTemporaryFeralPose();
    }

    private static bool IsRest(string id) =>
        id is "idle_loop" or "weak_loop" or "domain_idle" or "domain_weak_loop" or "feral_idle";
}
