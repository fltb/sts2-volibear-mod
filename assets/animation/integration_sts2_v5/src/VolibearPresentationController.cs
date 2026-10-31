// integration_source_uncompiled. Presentation only: never changes damage, powers, cards or RNG.
using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using STS2RitsuLib.Scaffolding.Visuals.StateMachine;
using STS2RitsuLib.Scaffolding.Visuals.StateMachine.Backends;

namespace VolibearMod.ArtV5;

public readonly record struct PresentationCue(double Seconds, string? AudioId, string? EffectId,
    Vector2 SourceGlobal, Vector2 TargetGlobal);

/// <summary>
/// Attach once per creature. The host mod supplies committed action IDs, target positions,
/// cue schedules and current game volume. This class does not install gameplay patches.
/// </summary>
public partial class VolibearPresentationController : Node
{
    public VolibearPlaybackFlags Flags { get; } = new();
    public ModAnimStateMachine Machine { get; private set; } = null!;
    public VolibearCueAudio Audio { get; private set; } = null!;
    public VolibearVfxPlayer Effects { get; private set; } = null!;
    private AnimatedSprite2D _sprite = null!;
    private readonly List<PresentationCue> _pending = [];
    private int _nextCue;
    private long _lastCommittedSequence = -1;
    private string? _activeClip;
    private bool _closing;
    private long _animationStarts;
    private bool _configured;

    public ModAnimStateMachine Configure(AnimatedSprite2D sprite, Node2D effectHolder,
        Func<string,float> currentGameVolume)
    {
        if(_configured) throw new InvalidOperationException("Configure once per creature presentation instance.");
        ArgumentNullException.ThrowIfNull(currentGameVolume);
        _configured = true;
        _sprite = sprite;
        _sprite.SpriteFrames = VolibearSpriteFrames.Load("res://VolibearArt/animations/manifest.json");
        _sprite.Centered = false;
        _sprite.Offset = -new Vector2(250,442); // Delivered foot pivot; no body layer reassembly.
        Audio = new VolibearCueAudio {GameVolumeLinear = currentGameVolume}; AddChild(Audio); Audio.LoadManifest();
        Effects = new VolibearVfxPlayer(); effectHolder.AddChild(Effects); Effects.LoadManifest();
        // Flush last-frame events before the backend returns to idle.
        _sprite.AnimationFinished += FinishTimeline;
        Machine = VolibearSpriteFrames.CreateMachine(sprite, Flags);
        Machine.AnimationStarted += OnAnimationStarted;
        return Machine;
    }

    /// <summary>
    /// Schedule a single committed action. Sequence numbers are unique and increasing
    /// per creature. Replays/duplicate network delivery cannot replay its sounds.
    /// </summary>
    public bool Present(string trigger, long committedSequence, IReadOnlyList<PresentationCue> cues)
    {
        if (_closing || committedSequence <= _lastCommittedSequence) return false;
        _lastCommittedSequence = committedSequence;
        CancelPendingTimeline();
        long startsBefore = _animationStarts;
        Machine.SetTrigger(trigger);
        if (_animationStarts == startsBefore) return false; // Unknown/rejected/dead-state trigger.
        _activeClip = Machine.Current?.Id;
        if (_activeClip == null) return false;
        double duration = Duration(_activeClip);
        foreach (var cue in cues)
            if (!double.IsFinite(cue.Seconds) || cue.Seconds < 0 || cue.Seconds > duration)
                throw new ArgumentOutOfRangeException(nameof(cues), "Cue time must be within this clip.");
        _pending.AddRange(cues.OrderBy(c => c.Seconds));
        DispatchUntil(0);
        return true;
    }

    private void OnAnimationStarted(ModAnimState state)
    {
        _animationStarts++;
        // Any unrelated trigger invalidates the previous action's future cues.
        CancelPendingTimeline();
        if(state.Id is "die" or "domain_die") { Audio.StopAllOwned(); Effects.StopAllOwned(); }
        if(state.Id == "domain_exit") { Audio.StopLoop("sfx.domain_loop"); Effects.StopLoop("domain_loop"); }
    }

    public override void _Process(double delta)
    {
        if (_closing || _activeClip == null || !_sprite.IsPlaying() || _sprite.Animation.ToString() != _activeClip) return;
        double fps = _sprite.SpriteFrames.GetAnimationSpeed(_activeClip);
        double time = 0;
        for (int i=0;i<_sprite.Frame;i++) time += _sprite.SpriteFrames.GetFrameDuration(_activeClip,i)/fps;
        time += _sprite.SpriteFrames.GetFrameDuration(_activeClip,_sprite.Frame)*_sprite.FrameProgress/fps;
        DispatchUntil(time);
    }

    private double Duration(string id)
    {
        double sum=0, fps=_sprite.SpriteFrames.GetAnimationSpeed(id);
        for(int i=0;i<_sprite.SpriteFrames.GetFrameCount(id);i++) sum += _sprite.SpriteFrames.GetFrameDuration(id,i)/fps;
        return sum;
    }
    private void FinishTimeline()
    {
        if (_activeClip != null) DispatchUntil(Duration(_activeClip));
        CancelPendingTimeline();
    }
    private void DispatchUntil(double time)
    {
        while(_nextCue < _pending.Count && _pending[_nextCue].Seconds <= time+1e-6)
        {
            var c=_pending[_nextCue++];
            if(c.AudioId!=null) Audio.PlayCue(c.AudioId);
            if(c.EffectId!=null) Effects.Spawn(c.EffectId,c.SourceGlobal,c.TargetGlobal);
        }
    }
    public void CancelPendingTimeline() { _pending.Clear(); _nextCue=0; _activeClip=null; }
    public void EndCombat()
    {
        CancelPendingTimeline();
        Flags.ClearTemporaryFeralPose();
        Audio?.StopAllOwned(); Effects?.StopAllOwned();
    }
    public override void _ExitTree()
    {
        _closing=true;
        EndCombat();
        if (Machine != null)
        {
            Machine.AnimationStarted -= OnAnimationStarted;
            if(GodotObject.IsInstanceValid(_sprite))
            {
                Machine.Backend.Stop();
                if(Machine.Backend is AnimatedSprite2DBackend backend) backend.Dispose();
            }
            Machine.Dispose();
        }
        if(GodotObject.IsInstanceValid(_sprite)) _sprite.AnimationFinished -= FinishTimeline;
        if(GodotObject.IsInstanceValid(Effects)) Effects.QueueFree();
    }
}
