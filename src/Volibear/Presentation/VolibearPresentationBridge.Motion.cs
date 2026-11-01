using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

public static partial class VolibearPresentationBridge
{
    private sealed record Segment(string Clip, int Start, int End);
    private sealed record Motion(string Clip, string Trigger, int MaxStarts, string? DomainClip,
        Segment? Segment, Segment? DomainSegment, int HoldFrames, string? Arbitration, string? EntryClip);
    private static string? Text(JsonElement row, string key) =>
        row.TryGetProperty(key, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
    private static string? MotionKey(CardModel? card) => card is null ? null : BeastForms.Shape(card) switch
    {
        BeastShape.Claw => "t01",
        BeastShape.Body => "t02",
        _ => (card as VolibearCard)?.Key
    };
    private static Motion ReadMotion(JsonElement row)
    {
        Segment? segment = row.TryGetProperty("segment_start_frame", out var start)
            ? new(Text(row, "segment_applies_to_clip")!, start.GetInt32(), row.GetProperty("segment_end_frame_exclusive").GetInt32()) : null;
        Segment? domainSegment = row.TryGetProperty("domain_segment", out var domain)
            ? new(domain.GetProperty("clip").GetString()!, domain.GetProperty("start_frame").GetInt32(), domain.GetProperty("end_frame_exclusive").GetInt32()) : null;
        return new(row.GetProperty("clip").GetString()!, row.GetProperty("trigger").GetString()!,
            row.GetProperty("max_starts_per_play").GetInt32(), Text(row, "domain_variant") ?? Text(row, "domain_fallback_clip"),
            segment, domainSegment,
            row.TryGetProperty("play_as_timed_pose", out var timed) && timed.GetBoolean() ? row.GetProperty("max_hold_frames").GetInt32() : 0,
            Text(row, "domain_entry_arbitration"), Text(row, "selected_after_real_domain_entry"));
    }

    // Preserve the original Task and AsyncLocal invocation chain, including nested responder work.
    private sealed record EngageGroup(EngageGroup? Previous, OwnerScope? Scope, OwnerScope.PlayMotion? Motion, CardModel Card);
    private static readonly AsyncLocal<EngageGroup?> ActiveEngageGroup = new();
    private static void BeforeEngageGroup(CardModel card, out EngageGroup? __state)
    {
        __state = null;
        try
        {
            var scope = Owner(card.Owner.Creature);
            __state = new(ActiveEngageGroup.Value, scope, scope?.FindMotion(card), card);
            ActiveEngageGroup.Value = __state;
        }
        catch (Exception error) { Warn("engage_group_entry", error); }
    }
    private static void AfterEngageGroup(Task<IReadOnlyList<EngageCmd.Result>> __result, EngageGroup? __state)
    {
        if (__state is not { } group) return;
        ActiveEngageGroup.Value = group.Previous;
        Observe(__result, "engage_group_completed", results =>
        {
            if (results.Any(result => result.Performed && result.Completed)) group.Scope?.ForcedMotion(group.Motion);
        });
    }
    private static Exception? FinishEngageGroupInvocation(Exception? __exception, EngageGroup? __state)
    {
        if (__state is not null && ReferenceEquals(ActiveEngageGroup.Value, __state)) ActiveEngageGroup.Value = __state.Previous;
        return __exception;
    }

    private sealed partial class OwnerScope
    {
        internal sealed class PlayMotion(CardPlay play, string id, Motion binding, long action)
        {
            internal readonly CardPlay Play = play;
            internal readonly string Id = id;
            internal readonly Motion Binding = binding;
            internal readonly long Action = action;
            internal int Starts;
            internal bool EntrySelected;
        }
        private readonly List<PlayMotion> _plays = [];
        private long _motionAction;
        private AnimatedSprite2D? _motionSprite;
        private string? _motionClip;
        private int _motionEnd;
        private int _motionFramesLeft;
        private bool _changingFrame;

        internal PlayMotion? FindMotion(CardModel card) => _plays.LastOrDefault(p => ReferenceEquals(p.Play.Card, card));
        private void BeginMotion(CardPlay play, string id)
        {
            bool interruptedPose = _motionSprite is not null;
            StopMotionVisual();
            if (interruptedPose) ReturnToIdle();
            ++_motionAction; // Any newer owner card interrupts older pending visual starts.
            if (MotionKey(play.Card) is not { } key || !Motions.TryGetValue(key, out var binding)) return;
            var motion = new PlayMotion(play, id, binding, _motionAction);
            _plays.Add(motion);
            StartMotion(motion, "on_play");
        }
        internal void CardFinished(CardPlay play) => _plays.RemoveAll(p => ReferenceEquals(p.Play, play));
        internal void BlockMotion(CardPlay? play)
        {
            if (play is not null) StartMotion(_plays.LastOrDefault(p => ReferenceEquals(p.Play, play)), "after_block_gain");
        }
        internal void ForcedMotion(PlayMotion? play) => StartMotion(play, "after_forced_enemy_action");
        // Only the committed batch receipt calls this; Converted remains a per-card claw/body cue.
        internal void BatchingBeastMotion(CardModel? source)
        {
            if (!Live || source is null) return;
            if (FindMotion(source) is { } play) { StartMotion(play, "on_card_beastify"); return; }
            // A deployed source can convert cards on a later turn without a CardPlay. This is
            // one confirmed batch, not a synthetic play or one action per converted card.
            if (source is VolibearCard card && Motions.TryGetValue(card.Key, out var binding) &&
                binding.Trigger == "on_card_beastify" && binding.MaxStarts > 0)
            {
                ++_motionAction;
                string clip = _domain ? binding.DomainClip ?? binding.Clip : binding.Clip;
                PlayBoundMotion(binding, clip);
                if (StartVoices.TryGetValue(clip, out var cue)) _effects.PlaySound(Next("beast_batch_motion"), cue);
            }
        }
        private void StartMotion(PlayMotion? play, string trigger)
        {
            if (!Live || play is null || play.Action != _motionAction || play.Binding.Trigger != trigger ||
                play.Starts >= play.Binding.MaxStarts) return;
            ++play.Starts;
            string clip = _domain ? play.Binding.DomainClip ?? play.Binding.Clip : play.Binding.Clip;
            if (play.Binding.HoldFrames > 0 && _lowHealth) clip = _domain ? "domain_weak_loop" : "weak_loop";
            PlayBoundMotion(play.Binding, clip);
            if (StartVoices.TryGetValue(clip, out var cue))
            {
                if (cue == "voice.attack_01" && ++_voiceCounter % 2 == 0) cue = "voice.attack_02";
                _effects.PlaySound(play.Id + ":motion:" + play.Starts, cue);
            }
        }
        private bool DomainEntryMotion()
        {
            var play = _plays.LastOrDefault();
            if (play is null) { Pose("domain_enter"); return true; }
            if (play.Action != _motionAction || play.EntrySelected) return false;
            if (play.Binding.Arbitration == "may_replace_primary_with_domain_enter_on_actual_false_to_true")
            {
                play.EntrySelected = true;
                Pose("domain_enter");
                return true;
            }
            if (play.Binding.Arbitration == "dedicated_domain_action_replaces_full_domain_enter" && play.Binding.EntryClip is { } clip)
            {
                // Replace the running presentation in place; not a second primary action start.
                play.EntrySelected = true;
                var sprite = _node.Visuals.GetNode<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
                int frame = sprite.Frame;
                PlayBoundMotion(play.Binding, clip);
                sprite.Frame = Math.Min(frame, sprite.SpriteFrames.GetFrameCount(clip) - 1);
            }
            // Other primary actions retain their dedicated pose; ground/loop cues still announce entry.
            return false;
        }
        private void PlayBoundMotion(Motion binding, string clip)
        {
            Pose(clip);
            var segment = binding.DomainSegment?.Clip == clip ? binding.DomainSegment : binding.Segment?.Clip == clip ? binding.Segment : null;
            if (segment is null && binding.HoldFrames <= 0) return;
            var sprite = _node.Visuals.GetNode<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
            int count = sprite.SpriteFrames.GetFrameCount(clip);
            if (segment is not null && (segment.Start < 0 || segment.End > count || segment.End <= segment.Start))
                throw new InvalidOperationException($"Invalid approved segment for {clip}: {segment.Start}..{segment.End}/{count}");
            _motionSprite = sprite;
            _motionClip = clip;
            _motionEnd = segment?.End ?? 0;
            _motionFramesLeft = binding.HoldFrames;
            sprite.Frame = segment?.Start ?? 0;
            sprite.FrameChanged += MotionFrameChanged;
            sprite.AnimationChanged += MotionAnimationChanged;
        }
        private void MotionAnimationChanged()
        {
            if (!_changingFrame && _motionSprite?.Animation.ToString() != _motionClip) StopMotionVisual();
        }
        private void MotionFrameChanged() => Safe("motion_frame", () =>
        {
            if (_changingFrame || _motionSprite is not { } sprite) return;
            if (!Live || sprite.Animation.ToString() != _motionClip) { StopMotionVisual(); return; }
            bool ended = _motionEnd > 0 && sprite.Frame >= _motionEnd;
            if (_motionFramesLeft > 0) ended |= --_motionFramesLeft == 0;
            if (!ended) return;
            _changingFrame = true;
            try
            {
                StopMotionVisual();
                RefreshIdle();
                sprite.Play(_domain ? (_lowHealth ? "domain_weak_loop" : "domain_idle") : (_lowHealth ? "weak_loop" : "idle_loop"));
            }
            finally { _changingFrame = false; }
        });
        private void ReturnToIdle()
        {
            RefreshIdle();
            VolibearPresentation.Play(_node.Visuals, _domain ? (_lowHealth ? "domain_weak_loop" : "domain_idle") : (_lowHealth ? "weak_loop" : "idle_loop"));
        }
        private void StopMotionVisual()
        {
            if (_motionSprite is { } sprite && GodotObject.IsInstanceValid(sprite))
            {
                sprite.FrameChanged -= MotionFrameChanged;
                sprite.AnimationChanged -= MotionAnimationChanged;
            }
            _motionSprite = null;
            _motionClip = null;
            _motionEnd = _motionFramesLeft = 0;
        }
        private void ClearMotions()
        {
            StopMotionVisual();
            _plays.Clear();
            ++_motionAction;
        }
    }
}
