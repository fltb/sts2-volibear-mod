using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Core;

namespace Volibear.Presentation;

public static partial class VolibearPresentationBridge
{
    private static ConditionalWeakTable<DamageResult, object> PresentedPhysical = new();

    private static void InstallCombatPresentation(Harmony harmony)
    {
        // BaseLib 3.4.8 forwards this trigger straight to AnimatedSprite2D.Play.
        // Intercept only its default Attack/Cast while our paid-play motion owns the actor.
        // CreatureCmd.TriggerAnim and its original Task/wait are deliberately untouched.
        var prefix = Handler(nameof(BeforeNativeAnimation));
        prefix.priority = Priority.First;
        prefix.before = ["BaseLib"];
        harmony.Patch(Required(typeof(NCreature), "SetAnimationTrigger", typeof(string)), prefix: prefix);
        CardResolutionHooks.OrdinarySegmentCommitted += OrdinarySegment;
        LightningBatches.VisualCommitted += LightningCommitted;
    }

    private static bool BeforeNativeAnimation(NCreature __instance, string trigger)
    {
        if (trigger is not ("Attack" or "attack" or "Cast" or "cast") ||
            Environment.CurrentManagedThreadId != _mainThread || !Bear(__instance.Entity)) return true;
        try { return Owner(__instance.Entity)?.ResumePrimaryMotion(trigger) != true; }
        catch (Exception error) { Warn("native_animation_arbitration", error); return true; }
    }

    private static void OrdinarySegment(ICombatState combat, Creature owner, CardModel? card,
        long? playId, IReadOnlyList<DamageResult> results)
    {
        // Capture both room and source now. An old queued continuation cannot emit in a new room.
        var room = _room;
        if (room is null || !ReferenceEquals(room.Combat, combat) || !Bear(owner)) return;
        Dispatch("ordinary_segment_committed", () =>
        {
            if (ReferenceEquals(room, _room)) room.GetOwner(owner)?.PhysicalSegment(card, results, Next("physical_segment"), playId);
        });
    }

    private static void LightningCommitted(LightningBatch batch)
    {
        var room = _room;
        if (room is null || !ReferenceEquals(room.Combat, batch.Combat)) return;
        Dispatch("lightning_visual_committed", () =>
        {
            if (ReferenceEquals(room, _room)) room.GetOwner(batch.Owner)?.Lightning(batch);
        });
    }

    private static Motion CombatMotion(string key, Motion previous)
    {
        if (!CombatPresentationCatalog.Cards.TryGetValue(key, out var profile)) return previous;
        if (previous.Clip == profile.Motion) return previous;
        // New clips own complete poses. Old frame slices and generic domain-entry replacement
        // would trim a different animation or erase the card's new identity.
        return previous with { Clip = profile.Motion, DomainClip = profile.DomainMotion,
            Segment = null, DomainSegment = null, HoldFrames = 0, Arbitration = null, EntryClip = null };
    }

    private sealed partial class OwnerScope
    {
        private sealed class CombatPlay(CardPlay play, string? key, long? nativePlayId)
        {
            internal readonly CardPlay Play = play;
            internal readonly string? Key = key;
            internal readonly long? NativePlayId = nativePlayId;
            internal readonly string MotionSequence = Next("motion_sequence");
            internal int PhysicalSegments;
            internal int LightningBatches;
        }
        private readonly List<CombatPlay> _combatPlays = [];
        private int _unscopedHits;
        private readonly HashSet<long> _shownLightning = [];
        private readonly Queue<long> _shownLightningOrder = new();

        // A killing result may set IsEnding before its damage Task returns. Allow that already
        // committed contact on the existing visible room; never reopen stopped scopes or loops.
        private bool ContactLive => !_disposed && !_combatStopped && !_dead && _owner.IsAlive &&
            ReferenceEquals(_room, VolibearPresentationBridge._room) &&
            ReferenceEquals(_owner.CombatState, _room.Combat) && Valid(_node) && Valid(_node.Visuals);

        private void BeginCombatPlay(CardPlay play) => _combatPlays.Add(new(play, MotionKey(play.Card), CardResolutionHooks.CurrentPlayId(play.Card)));
        private void FinishCombatPlay(CardPlay play) => _combatPlays.RemoveAll(p => ReferenceEquals(p.Play, play));
        private CombatPlay? CombatPlayFor(CardModel? card, long? nativePlayId = null) =>
            card is null ? null : _combatPlays.LastOrDefault(p => ReferenceEquals(p.Play.Card, card) &&
                (nativePlayId is null || p.NativePlayId == nativePlayId));

        internal bool ResumePrimaryMotion(string trigger = "Attack", int? committedIndex = null)
        {
            if (!Live) return false;
            var sprite = _node.Visuals.GetNodeOrNull<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
            if (sprite is null || _combatPlays.LastOrDefault() is not { } current) return false;
            // Replays have their own native CardPlay, but intentionally no second paid-play pose.
            // They still own the generic trigger so BaseLib cannot restart its default Attack.
            string clip;
            if (current.Play.PlayIndex > 0 && current.Key is { } key &&
                CombatPresentationCatalog.Cards.TryGetValue(key, out var replayProfile))
                clip = _domain ? replayProfile.DomainMotion ?? replayProfile.Motion : replayProfile.Motion;
            else
            {
                // Reference the active native play, not the latest global action number: a nested
                // card may finish and return control to its still-live outer play.
                if (_plays.LastOrDefault(p => ReferenceEquals(p.Play, current.Play)) is not { Starts: > 0 } play)
                    return false;
                clip = _domain ? play.Binding.DomainClip ?? play.Binding.Clip : play.Binding.Clip;
            }
            if (!sprite.SpriteFrames.HasAnimation(clip) || !sprite.HasMethod("resume_action")) return false;
            if (committedIndex is not null)
            {
                // Direct lightning damage need not send a native Cast trigger. Its confirmed
                // batch may recover an idle/interrupted cast, but never erase a fresh hurt pose.
                if (sprite.Animation.ToString() is "hurt" or "Hurt" or "hit" or "Hit" or "domain_hurt") return false;
                // The first batch should keep the paid play's existing windup/recovery progress.
                if (committedIndex == 0 && current.Play.PlayIndex == 0 &&
                    sprite.Animation.ToString() == clip && sprite.IsPlaying()) return true;
            }
            int nextSegment = committedIndex ?? (trigger is "Cast" or "cast" ? current.LightningBatches : current.PhysicalSegments);
            string sequence = current.MotionSequence + (trigger is "Cast" or "cast" ? ":cast" : ":attack");
            return sprite.Call("resume_action", clip, nextSegment, sequence).AsBool();
        }

        internal void PhysicalSegment(CardModel? source, IReadOnlyList<DamageResult> results, string id, long? nativePlayId = null)
        {
            if (!ContactLive) return;
            var fresh = results.Where(result => !PresentedPhysical.TryGetValue(result, out _)).ToArray();
            if (fresh.Length == 0) return;
            var play = CombatPlayFor(source, nativePlayId);
            int index = play is null ? _unscopedHits++ : play.PhysicalSegments++;
            string? fallbackKey = play?.Key ?? MotionKey(source);
            bool sounded = false;
            foreach (var result in fresh)
            {
                PresentedPhysical.Add(result, new object());
                DamageContacts.TryGetValue(result, out var snapshot);
                var key = snapshot?.Key ?? fallbackKey;
                var profile = snapshot?.Profile ?? CombatPresentationCatalog.For(key);
                // Aggregate fallback lacks a CardPlay boundary. Its global direction counter
                // cannot establish that a snapshotted U08 result was the marked second bite.
                string style = CombatPresentationCatalog.ContactFor(key, profile, play is null ? 0 : index);
                if (result.Receiver.CombatId is null || _room.NodeFor(result.Receiver) is not { } target) continue;
                _effects.EmitCombat(id, style, Anchors(target), CreatureId(result.Receiver), index,
                    blocked: result.BlockedDamage > 0 && result.UnblockedDamage <= 0,
                    intensity: 1f + Math.Min(0.4f, (result.BlockedDamage + result.UnblockedDamage) / 100f));
                // Group targets share one existing contact sound, retaining the selected audio pack.
                if (!sounded)
                {
                    _effects.PlaySound(id, "sfx." + (snapshot?.Effect ?? ContactEffectFor(source)));
                    sounded = true;
                }
            }
            if (play is not null && ReferenceEquals(play, _combatPlays.LastOrDefault()))
                ImpactFrame(index, play.MotionSequence + ":attack");
        }

        private void ImpactFrame(int index, string sequence)
        {
            // Passive lightning never calls this: it must not steal the body's primary action.
            if (!Live || _node.Visuals.GetNodeOrNull<AnimatedSprite2D>("Visuals/AnimatedSprite2D") is not { } sprite)
                return;
            if (sprite.HasMethod("combat_impact")) sprite.Call("combat_impact", index, sequence);
        }

        private void LightningVisuals(LightningBatch batch, string id)
        {
            var play = CombatPlayFor(batch.Card, batch.PresentationPlayId);
            // Linked/passive lightning may carry its source card for attribution. It owns
            // neither that card's main cast count nor the actor's primary contact frame.
            int index = batch.VisualOrigin == LightningVisualOrigin.Card && play is not null
                ? play.LightningBatches++ : _unscopedHits++;
            var profile = CombatPresentationCatalog.For(play?.Key ?? MotionKey(batch.Card));
            string style = batch.VisualOrigin switch
            {
                LightningVisualOrigin.Domain => "domain_echo",
                LightningVisualOrigin.Conduction => "chain",
                LightningVisualOrigin.Pool => "ground_thunder",
                LightningVisualOrigin.Counter => "retaliation",
                LightningVisualOrigin.Passive => batch.Results.Count > 1 ? "fork" : "bolt",
                _ => profile.Lightning
            };
            // Each redirected/native result retains its own receiver and block outcome.
            foreach (var hit in batch.Results)
            {
                if (hit.Receiver.CombatId is null || _room.NodeFor(hit.Receiver) is not { } target) continue;
                _effects.EmitCombat(id, style, Anchors(target), CreatureId(hit.Receiver), index,
                    blocked: hit.Blocked > 0 && hit.HpLost <= 0,
                    intensity: 1f + Math.Min(0.4f, batch.StormCharge / 30f));
            }
            if (batch.VisualOrigin == LightningVisualOrigin.Card && play is not null &&
                ReferenceEquals(play, _combatPlays.LastOrDefault()) && ResumePrimaryMotion("Cast", index))
                ImpactFrame(index, play.MotionSequence + ":cast");
        }

        internal void CombatAccent(string id, string style, Creature? target = null)
        {
            if (!Live) return;
            if (target is null) _effects.EmitSynergy(id, style, Anchors());
            else if (target.CombatId is not null && _room.NodeFor(target) is { } node)
                _effects.EmitSynergy(id, style, Anchors(node), CreatureId(target));
        }

        internal void BlockAccent(string id, CardPlay? cardPlay)
        {
            var profile = CombatPresentationCatalog.For(MotionKey(cardPlay?.Card));
            CombatAccent(id, profile.Accent is "armor" or "thunder_armor" ? profile.Accent : "guard");
        }

        private void ClearCombatPresentation()
        {
            _combatPlays.Clear();
            _unscopedHits = 0;
            _shownLightning.Clear();
            _shownLightningOrder.Clear();
        }
    }
}
