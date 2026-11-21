// Boundary doubles only: no damage calculation, animation progression or native detours.
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.RegularExpressions;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;
using Volibear.Presentation;

internal static class Program
{
    private static int _assertions;
    internal static void Check(bool condition, string message)
    {
        _assertions++;
        if (!condition) throw new InvalidOperationException(message);
    }
    internal static void Equal<T>(T expected, T actual, string message) =>
        Check(EqualityComparer<T>.Default.Equals(expected, actual), $"{message}: expected {expected}, got {actual}");
    private static async Task<int> Main(string[] args)
    {
        try
        {
            if (args.Length != 2) throw new ArgumentException("case and repository path required");
            if (args[0].StartsWith("pipeline-")) await CardResolutionHooks.RunCase(args[0]);
            else await VolibearPresentationBridge.RunCase(args[0], args[1]);
            Console.WriteLine($"COMBAT_PRESENTATION_PASS {args[0]} assertions={_assertions} native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}

namespace Godot
{
    public class Node { public bool Valid = true; }
    public class CanvasItem : Node { }
    public readonly record struct Variant(bool Value)
    {
        public bool AsBool() => Value;
        public static implicit operator bool(Variant value) => value.Value;
    }
    public sealed class SpriteFrames
    {
        public readonly HashSet<string> Clips = new(StringComparer.Ordinal);
        public bool HasAnimation(string clip) => Clips.Contains(clip);
    }
    public sealed class AnimatedSprite2D : CanvasItem
    {
        public SpriteFrames SpriteFrames { get; } = new();
        public readonly HashSet<string> Methods = ["resume_action", "combat_impact"];
        public readonly List<(string Method, object[] Args)> Calls = [];
        public string Animation = "idle_loop";
        public bool Playing = true;
        public bool ResumeSucceeded = true;
        public bool IsPlaying() => Playing;
        public bool HasMethod(string name) => Methods.Contains(name);
        public Variant Call(string method, params object[] args)
        {
            Calls.Add((method, args));
            if (method == "resume_action" && ResumeSucceeded) { Animation = (string)args[0]; Playing = true; }
            return new(ResumeSucceeded);
        }
    }
}

namespace HarmonyLib
{
    public static class Priority { public const int First = 800; }
    public sealed class HarmonyMethod(MethodInfo method)
    {
        public MethodInfo method = method;
        public int priority;
        public string[] before = [];
    }
    public sealed class Harmony(string owner)
    {
        public readonly string Owner = owner;
        public readonly List<(MethodInfo Original, HarmonyMethod Prefix)> Patches = [];
        public void Patch(MethodInfo original, HarmonyMethod? prefix = null) => Patches.Add((original, prefix!));
    }
}

namespace MegaCrit.Sts2.Core.Combat
{
    public interface ICombatState { }
    public sealed class CombatState : ICombatState { }
    public sealed class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public bool IsInProgress = true;
        public bool IsEnding;
        public bool IsOverOrEnding => !IsInProgress || IsEnding;
        public ICombatState? State;
        public ICombatState? DebugOnlyGetState() => State;
    }
}

namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public ICombatState? CombatState;
        public long? CombatId;
        public bool IsAlive = true;
        public bool IsBear = true;
        public Player Player = null!;
        public readonly List<object> Powers = [];
    }
    public sealed class DamageResult(Creature receiver, int hpLost = 5, int blocked = 0)
    {
        public Creature Receiver = receiver;
        public int UnblockedDamage = hpLost;
        public int BlockedDamage = blocked;
        public int OverkillDamage;
    }
}

namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardType { Attack, Skill, Power }
    public sealed class CardPlay(CardModel card, int playIndex = 0)
    {
        public CardModel Card = card;
        public int PlayIndex = playIndex;
    }
}

namespace MegaCrit.Sts2.Core.Models
{
    public sealed class Player(Creature creature) { public Creature Creature = creature; }
    public sealed class CardModel(string key, Creature owner)
    {
        public string Key = key;
        public Player Owner = owner.Player;
        public CardType Type = CardType.Attack;
    }
}

namespace MegaCrit.Sts2.Core.Nodes.Combat
{
    public sealed class CreatureVisuals : CanvasItem
    {
        public AnimatedSprite2D? Sprite = new();
        public T? GetNodeOrNull<T>(string path) where T : class => Sprite as T;
    }
    public sealed class NCreature(Creature entity) : Node
    {
        public Creature Entity = entity;
        public CreatureVisuals Visuals = new();
        public void SetAnimationTrigger(string trigger) { }
    }
}

namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.ValueProps { [Flags] public enum ValueProp { None = 0, Move = 1, Unpowered = 2 } }

namespace Volibear.Presentation
{
    public sealed record EffectAnchors(CanvasItem Owner, CanvasItem? Target = null);
    public sealed record CapturedEffect(string Id, string Style, EffectAnchors Anchors, string Target, int Index, bool Blocked);
    public sealed class VolibearEffects
    {
        public readonly List<CapturedEffect> Combat = [];
        public readonly List<(string Id, string Cue)> Sounds = [];
        public readonly List<(string Id, string Style)> Accents = [];
        public int PersistentStops;
        public int AllStops;
        public void StopPersistent() => PersistentStops++;
        public void StopAll() => AllStops++;
        public bool EmitCombat(string eventId, string style, EffectAnchors anchors,
            string targetId = "", int hitIndex = 0, bool blocked = false, float intensity = 1f)
        { Combat.Add(new(eventId, style, anchors, targetId, hitIndex, blocked)); return true; }
        public bool PlaySound(string id, string cue) { Sounds.Add((id, cue)); return true; }
        public bool EmitSynergy(string id, string style, EffectAnchors anchors, string targetId = "")
        { Accents.Add((id, style)); return true; }
    }

    public static partial class VolibearPresentationBridge
    {
        private sealed record Segment(string Clip, int Start, int End);
        private sealed record Motion(string Clip, string Trigger, int MaxStarts, string? DomainClip,
            Segment? Segment, Segment? DomainSegment, int HoldFrames, string? Arbitration, string? EntryClip);
        private sealed record DamageContact(string Effect, CombatPresentationProfile? Profile = null, string? Key = null);
        private static ConditionalWeakTable<DamageResult, DamageContact> DamageContacts = new();
        private static RoomScope? _room;
        private static readonly int _mainThread = Environment.CurrentManagedThreadId;
        private static readonly Queue<Action> Pending = new();
        private static bool QueueDispatch;
        private static long _ids;
        private static bool Bear(Creature? creature) => creature?.IsBear == true;
        private static OwnerScope? Owner(Creature creature) => _room?.GetOwner(creature);
        private static bool Valid(Node? node) => node?.Valid == true;
        private static string CreatureId(Creature creature) => $"creature:{creature.CombatId}";
        private static string? MotionKey(CardModel? card) => card?.Key;
        private static string ContactEffectFor(CardModel? card) => card?.Key == "u08" ? "bite_hit" : "claw_slash";
        private static string Next(string label) => label + ":" + ++_ids;
        private static void Warn(string label, Exception error) { }
        private static void Dispatch(string label, Action action)
        { if (QueueDispatch) Pending.Enqueue(action); else action(); }
        private static HarmonyMethod Handler(string name) => new(typeof(VolibearPresentationBridge)
            .GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic)!);
        private static MethodInfo Required(Type type, string name, params Type[] args) => type.GetMethod(name, args)!;
        private sealed class RoomScope(ICombatState combat)
        {
            internal readonly ICombatState Combat = combat;
            internal readonly Dictionary<Creature, OwnerScope> Owners = new(ReferenceEqualityComparer.Instance);
            internal readonly Dictionary<Creature, NCreature> Nodes = new(ReferenceEqualityComparer.Instance);
            internal OwnerScope? GetOwner(Creature owner) =>
                ReferenceEquals(owner.CombatState, Combat) ? Owners.GetValueOrDefault(owner) : null;
            internal NCreature? NodeFor(Creature creature) => Nodes.GetValueOrDefault(creature);
        }
        private sealed partial class OwnerScope
        {
            private readonly RoomScope _room;
            private readonly Creature _owner;
            private readonly NCreature _node;
            internal readonly VolibearEffects _effects = new();
            private bool _domain;
            private bool _disposed;
            private bool _combatStopped;
            private bool _dead;
            private bool _endingSuspended;
            private long _motionAction;
            private sealed class PlayMotion(CardPlay play, Motion binding)
            {
                internal readonly CardPlay Play = play;
                internal readonly Motion Binding = binding;
                internal int Starts = 1;
            }
            private readonly List<PlayMotion> _plays = [];
            // PRODUCTION_LIVE
            internal OwnerScope(RoomScope room, Creature owner, NCreature node)
            { _room = room; _owner = owner; _node = node; }
            private EffectAnchors Anchors(NCreature? target = null) => new(_node.Visuals, target?.Visuals);
            private void StopMotionVisual() { }
            private void StopSemanticVisuals(bool all) { }
            private void ReleaseSpiritForm() { }
            private void ReleaseCapturedAnchors(bool all) { }
            // PRODUCTION_CLEAR_MOTIONS
            // PRODUCTION_SUSPEND
            internal CardPlay Begin(CardModel card, long playId, int replay = 0, bool started = true)
            {
                CardResolutionHooks.FixtureBegin(card, playId);
                var play = new CardPlay(card, replay);
                BeginCombatPlay(play);
                var profile = CombatPresentationCatalog.For(card.Key);
                var binding = new Motion(profile.Motion, "on_play", 1, profile.DomainMotion, null, null, 0, null, null);
                if (replay == 0) _plays.Add(new(play, binding) { Starts = started ? 1 : 0 });
                return play;
            }
            internal void Finish(CardPlay play)
            { _plays.RemoveAll(p => ReferenceEquals(p.Play, play)); FinishCombatPlay(play); }
            internal void Physical(CardModel? card, IReadOnlyList<DamageResult> results, string id, long? playId)
            {
                var method = typeof(OwnerScope).GetMethod("PhysicalSegment", BindingFlags.Instance | BindingFlags.NonPublic)!;
                object?[] args = method.GetParameters().Select(p => p.ParameterType == typeof(CardModel) ? card :
                    p.ParameterType == typeof(string) ? (object)id : p.ParameterType == typeof(long?) ? playId : results).ToArray();
                method.Invoke(this, args);
            }
            // PRODUCTION_LIGHTNING
            internal void SetDomain(bool value) => _domain = value;
            internal void Deactivate(string reason)
            {
                if (reason == "death") { _dead = true; _owner.IsAlive = false; }
                if (reason == "stop") _combatStopped = true;
                if (reason == "dispose") _disposed = true;
                ClearMotions();
            }
            internal int ActivePlays => _combatPlays.Count;
        }

        private sealed record Scene(RoomScope Room, Creature Owner, NCreature Node, OwnerScope Scope, Creature Target, NCreature TargetNode)
        {
            internal AnimatedSprite2D Sprite => Node.Visuals.Sprite!;
            internal VolibearEffects Effects => Scope._effects;
            internal CardModel Card(string key) => new(key, Owner);
        }
        private static Scene Setup(bool newRoom = true)
        {
            var room = newRoom ? new RoomScope(new CombatState()) : _room!;
            _room = room;
            CombatManager.Instance.State = room.Combat;
            CombatManager.Instance.IsInProgress = true;
            CombatManager.Instance.IsEnding = false;
            var owner = new Creature { CombatState = room.Combat, CombatId = ++_ids };
            owner.Player = new(owner);
            var target = new Creature { CombatState = room.Combat, CombatId = ++_ids, IsBear = false };
            target.Player = new(target);
            var node = new NCreature(owner);
            foreach (var profile in CombatPresentationCatalog.Cards.Values)
            {
                node.Visuals.Sprite!.SpriteFrames.Clips.Add(profile.Motion);
                if (profile.DomainMotion is { } domain) node.Visuals.Sprite.SpriteFrames.Clips.Add(domain);
            }
            var targetNode = new NCreature(target);
            var scope = new OwnerScope(room, owner, node);
            room.Owners.Add(owner, scope);
            room.Nodes.Add(owner, node);
            room.Nodes.Add(target, targetNode);
            return new(room, owner, node, scope, target, targetNode);
        }
        private static LightningBatch Batch(Scene scene, CardModel? card, LightningVisualOrigin origin, long playId = 1)
        {
            var batch = new LightningBatch(++_ids, scene.Room.Combat, scene.Owner, card,
                1, 1, 3, 0, 3, [scene.Target], [new(scene.Target, 3, 0, 0)], 1) { VisualOrigin = origin };
            // This fixture also compiles the production receipt declaration, including optional provenance.
            typeof(LightningBatch).GetProperty("PresentationPlayId")?.SetValue(batch, playId);
            return batch;
        }
        private static int Impacts(Scene scene) => scene.Sprite.Calls.Count(c => c.Method == "combat_impact");

        internal static async Task RunCase(string name, string root)
        {
            var s = Setup();
            switch (name)
            {
                case "catalog":
                {
                    var approved = Regex.Matches(File.ReadAllText(Path.Combine(root,
                        "reference/bear-forge/docs/volibear/CARDS.md")), @"(?m)^\| ([BCURT]\d{2}) \|")
                        .Select(m => m.Groups[1].Value.ToLowerInvariant()).ToHashSet();
                    Program.Equal(89, approved.Count, "Approved card table must contain 89 identities");
                    Program.Check(approved.SetEquals(CombatPresentationCatalog.Cards.Keys), "Catalog must cover exactly the approved cards");
                    Program.Equal("bite_rend", CombatPresentationCatalog.For("U08").Motion, "Case-insensitive bite identity");
                    Program.Equal("stomp_chain", CombatPresentationCatalog.For("u31").Motion, "Repeated stomp identity");
                    Program.Equal("sweep", CombatPresentationCatalog.For("c09").Contact, "Sweep contact identity");
                    Program.Check(ReferenceEquals(CombatPresentationCatalog.Fallback, CombatPresentationCatalog.For("foreign")), "Foreign catalog fallback");
                    var previous = new Motion("attack", "after_forced_enemy_action", 2, "domain_attack",
                        new("attack", 2, 4), new("domain_attack", 2, 4), 15, "replace", "domain_enter");
                    var mapped = CombatMotion("c10", previous);
                    Program.Equal("counter", mapped.Clip, "New primary clip");
                    Program.Equal(previous.Trigger, mapped.Trigger, "Native committed start trigger retained");
                    Program.Equal(previous.MaxStarts, mapped.MaxStarts, "Existing start count retained");
                    Program.Check(mapped.Segment is null && mapped.DomainSegment is null && mapped.HoldFrames == 0 &&
                        mapped.Arbitration is null && mapped.EntryClip is null, "New poses must not inherit old clip slicing");
                    break;
                }
                case "segments":
                {
                    var card = s.Card("c02"); s.Scope.Begin(card, 10);
                    var one = new DamageResult(s.Target); var two = new DamageResult(s.Target);
                    s.Scope.Physical(card, [one], "one", 10);
                    s.Scope.Physical(card, [two], "two", 10);
                    Program.Equal(2, s.Effects.Combat.Count, "Each committed segment appears immediately");
                    Program.Check(s.Effects.Combat.Select(e => e.Index).SequenceEqual([0, 1]), "Committed segment indices");
                    s.Scope.Physical(null, [one, two], "aggregate", null);
                    Program.Equal(2, s.Effects.Combat.Count, "Aggregate history must not replay segment results");
                    Program.Equal(2, s.Effects.Sounds.Count, "One retained contact sound per segment");
                    Program.Equal(2, Impacts(s), "No additional body impact from deduplicated history");
                    break;
                }
                case "bite-replay":
                {
                    var card = s.Card("u08"); var play = s.Scope.Begin(card, 20);
                    s.Scope.Physical(card, [new(s.Target)], "unmarked", 20);
                    Program.Equal("bite", s.Effects.Combat.Single().Style, "An unmarked target has one real bite");
                    Program.Equal(1, s.Effects.Combat.Count, "No predicted second bite");
                    s.Scope.Finish(play);
                    play = s.Scope.Begin(card, 21);
                    s.Scope.Physical(card, [new(s.Target)], "marked-first", 21);
                    s.Scope.Physical(card, [new(s.Target)], "marked-second", 21);
                    Program.Check(s.Effects.Combat.TakeLast(2).Select(e => e.Style).SequenceEqual(["bite", "bite_tear"]), "Only actual second segment tears");
                    s.Scope.Finish(play);
                    s.Scope.Begin(card, 21, replay: 1);
                    s.Scope.Physical(card, [new(s.Target)], "replay-first", 21);
                    Program.Equal("bite", s.Effects.Combat.Last().Style, "Native replay resets bite segment index");
                    Program.Equal(0, s.Effects.Combat.Last().Index, "Replay first segment is zero");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Replay owns its native attack trigger");
                    Program.Equal("bite_rend", s.Sprite.Animation, "Replay resumes dedicated bite");
                    break;
                }
                case "target-snapshots":
                {
                    var remote = Setup(newRoom: false);
                    var card = s.Card("c09"); s.Scope.Begin(card, 30);
                    var first = new DamageResult(s.Target, 0, 8); var second = new DamageResult(remote.Target, 8);
                    s.Scope.Physical(card, [first, second], "group", 30);
                    Program.Equal(2, s.Effects.Combat.Count, "AOE emits once for each actual receiver");
                    Program.Check(s.Effects.Combat.All(e => e.Index == 0), "AOE is one segment, not two hits");
                    Program.Check(ReferenceEquals(s.TargetNode.Visuals, s.Effects.Combat[0].Anchors.Target) &&
                        ReferenceEquals(remote.TargetNode.Visuals, s.Effects.Combat[1].Anchors.Target), "Receiver geometry is not guessed");
                    Program.Check(s.Effects.Combat[0].Blocked && !s.Effects.Combat[1].Blocked, "Native block outcome remains per receiver");
                    Program.Equal(1, s.Effects.Sounds.Count, "AOE contact shares sound");
                    Program.Equal(0, remote.Effects.Combat.Count, "Remote owner does not receive another owner's receipts");
                    s.Scope.Physical(null, [new(s.Target)], "unscoped-other-card", null);
                    var old = new DamageResult(s.Target);
                    DamageContacts.Add(old, new("bite_hit", CombatPresentationCatalog.For("u08"), "u08"));
                    s.Scope.Physical(null, [old], "late-history", null);
                    Program.Equal("bite", s.Effects.Combat.Last().Style, "Unscoped history preserves bite identity without inventing a second bite from earlier unrelated hits");
                    Program.Equal("sfx.bite_hit", s.Effects.Sounds.Last().Cue, "Per-result sound snapshot survives later card identity");
                    break;
                }
                case "lightning-origins":
                {
                    var card = s.Card("r23"); s.Scope.Begin(card, 1);
                    var origins = new[] { LightningVisualOrigin.Domain, LightningVisualOrigin.Conduction, LightningVisualOrigin.Pool, LightningVisualOrigin.Counter };
                    foreach (var origin in origins) s.Scope.Lightning(Batch(s, card, origin));
                    Program.Check(s.Effects.Combat.Select(e => e.Style).SequenceEqual(["domain_echo", "chain", "ground_thunder", "retaliation"]), "Passive origins do not inherit source card eruption");
                    Program.Equal(0, Impacts(s), "Passive lightning never advances the primary body");
                    Program.Equal(0, s.Sprite.Calls.Count, "Passive lightning cannot resume the primary body either");
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card));
                    Program.Equal("eruption", s.Effects.Combat.Last().Style, "Direct card lightning uses its authored shape");
                    Program.Equal(0, s.Effects.Combat.Last().Index, "Passive lightning cannot consume a card lightning segment index");
                    Program.Equal(1, Impacts(s), "Current card lightning can advance its own body");
                    var duplicate = Batch(s, card, LightningVisualOrigin.Card);
                    s.Scope.Lightning(duplicate); s.Scope.Lightning(duplicate);
                    Program.Equal(6, s.Effects.Combat.Count, "Visual event and legacy subscription share batch identity deduplication");
                    Program.Equal(6, s.Effects.Sounds.Count, "A duplicated lightning receipt does not duplicate its audio");
                    break;
                }
                case "native-arbitration":
                {
                    var harmony = new Harmony("Volibear.Presentation"); InstallCombatPresentation(harmony);
                    var patch = harmony.Patches.Single();
                    Program.Equal("SetAnimationTrigger", patch.Original.Name, "Synchronous native visual boundary only");
                    Program.Equal(Priority.First, patch.Prefix.priority, "Arbitration precedes default prefix priority");
                    Program.Check(patch.Prefix.before.SequenceEqual(["BaseLib"]), "Exact BaseLib Harmony owner ordering");
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "No live card leaves native attack available");
                    var card = s.Card("c03"); s.Scope.Begin(card, 1);
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Dedicated attack claims generic trigger");
                    Program.Equal("ground_slam", s.Sprite.Animation, "Correct dedicated clip requested");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Cast"), "Dedicated cast can be arbitrated");
                    foreach (var trigger in new[] { "Idle", "Hit", "Hurt", "Dead", "Revive", "CustomAttack" })
                        Program.Check(BeforeNativeAnimation(s.Node, trigger), "Non-generic trigger remains native: " + trigger);
                    s.Owner.IsBear = false;
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "Foreign character remains native");
                    s.Owner.IsBear = true; s.Sprite.Methods.Remove("resume_action");
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "Missing actor method falls back to native");
                    s.Sprite.Methods.Add("resume_action"); s.Sprite.SpriteFrames.Clips.Remove("ground_slam");
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "Missing clip falls back to native");
                    s.Sprite.SpriteFrames.Clips.Add("ground_slam");
                    s.Sprite.ResumeSucceeded = false;
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "A rejected dedicated resume must leave the native trigger available");
                    s.Sprite.ResumeSucceeded = true;
                    Program.Check(await Task.Run(() => BeforeNativeAnimation(s.Node, "Attack")), "No Godot mutation from another thread");
                    break;
                }
                case "direct-lightning-motion":
                {
                    var card = s.Card("u37"); var paid = s.Scope.Begin(card, 42);
                    s.Sprite.Animation = "storm_channel"; s.Sprite.Playing = true;
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 42));
                    Program.Equal(0, s.Sprite.Calls.Count(c => c.Method == "resume_action"), "First direct batch preserves an already playing paid cast");
                    Program.Equal(1, Impacts(s), "First confirmed batch can advance the existing cast contact");
                    var firstImpact = s.Sprite.Calls.Last(c => c.Method == "combat_impact");
                    Program.Equal(2, firstImpact.Args.Length, "Direct contact explicitly supplies its actor sequence");
                    string firstSequence = (string)firstImpact.Args[1];
                    Program.Check(firstSequence.EndsWith(":cast"), "Paid direct lightning binds the cast sequence even without a resume");
                    s.Sprite.Animation = "idle_loop";
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 42));
                    var resumed = s.Sprite.Calls.Last(c => c.Method == "resume_action");
                    Program.Equal("storm_channel", (string)resumed.Args[0], "A later direct batch recovers a finished cast without a native Cast trigger");
                    Program.Equal(1, (int)resumed.Args[1], "Recovery uses this committed batch index, not the already incremented next count");
                    string paidSequence = (string)resumed.Args[2];
                    Program.Equal(firstSequence, paidSequence, "Later direct resume uses the first contact's explicit cast sequence");
                    Program.Equal(paidSequence, (string)s.Sprite.Calls.Last(c => c.Method == "combat_impact").Args[1],
                        "Direct resume and contact use the same cast sequence");
                    Program.Equal(2, Impacts(s), "Recovered actual cast receives its own contact");
                    int before = s.Sprite.Calls.Count;
                    foreach (var hurt in new[] { "hurt", "Hurt", "hit", "Hit", "domain_hurt" })
                    {
                        s.Sprite.Animation = hurt;
                        s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 42));
                        Program.Equal(hurt, s.Sprite.Animation, "Late card lightning preserves an incoming hurt pose");
                        Program.Equal(before, s.Sprite.Calls.Count, "Hurt cannot be overwritten or advanced by direct lightning");
                    }
                    Program.Equal(7, s.Effects.Combat.Count, "Preserving hurt and its native aliases does not hide real lightning contacts");
                    s.Scope.Finish(paid); s.Scope.Begin(card, 42, replay: 1);
                    s.Sprite.Animation = "storm_channel"; s.Sprite.Playing = true;
                    int beforeReplayResumes = s.Sprite.Calls.Count(c => c.Method == "resume_action");
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 42));
                    resumed = s.Sprite.Calls.Last(c => c.Method == "resume_action");
                    Program.Equal(beforeReplayResumes + 1, s.Sprite.Calls.Count(c => c.Method == "resume_action"),
                        "Replay must rebind its sequence even when the same clip is still playing");
                    Program.Equal(0, (int)resumed.Args[1], "Direct lightning replay starts with its own committed batch zero");
                    Program.Check((string)resumed.Args[2] != paidSequence, "Direct lightning replay has a distinct actor sequence");
                    Program.Equal((string)resumed.Args[2], (string)s.Sprite.Calls.Last(c => c.Method == "combat_impact").Args[1],
                        "Replay contact binds its new cast sequence instead of inheriting the paid last-hit ledger");
                    Program.Equal("storm_channel", s.Sprite.Animation, "Direct lightning replay visibly restores its cast");
                    s.Sprite.Animation = "idle_loop";
                    before = s.Sprite.Calls.Count;
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Domain, 42));
                    Program.Equal(before, s.Sprite.Calls.Count, "Domain followup cannot recover an idle body");
                    s.Sprite.ResumeSucceeded = false;
                    int impacts = Impacts(s);
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 42));
                    Program.Equal(impacts, Impacts(s), "Rejected direct cast recovery cannot advance the actor");
                    Program.Equal(10, s.Effects.Combat.Count, "Rejected body recovery preserves settled target effects");
                    break;
                }
                case "lightning-delivery":
                {
                    InstallCombatPresentation(new Harmony("Volibear.Presentation"));
                    var remote = Setup(newRoom: false);
                    var card = s.Card("r23"); s.Scope.Begin(card, 1);
                    var batch = Batch(s, card, LightningVisualOrigin.Card);
                    LightningBatches.VisualCommitted += _ => throw new InvalidOperationException("observer fault");
                    bool reachedLaterObserver = false;
                    LightningBatches.VisualCommitted += _ => reachedLaterObserver = true;
                    LightningBatches.Present(batch);
                    s.Scope.Lightning(batch); // Legacy gameplay subscription sees the same committed object.
                    Program.Equal(1, s.Effects.Combat.Count, "Visual receipt plus legacy notification paints one batch");
                    Program.Equal(1, s.Effects.Sounds.Count, "Dual receipt paths keep one existing sound");
                    Program.Equal(0, remote.Effects.Combat.Count, "Lightning stays with its actual player owner");
                    Program.Check(reachedLaterObserver, "Presentation observer errors cannot interrupt later observers");
                    QueueDispatch = true;
                    LightningBatches.Present(Batch(s, card, LightningVisualOrigin.Card));
                    Setup();
                    while (Pending.TryDequeue(out var pending)) pending();
                    QueueDispatch = false;
                    Program.Equal(1, s.Effects.Combat.Count, "Queued old lightning cannot cross room replacement");
                    break;
                }
                case "nested-ownership":
                {
                    var outer = s.Card("c03"); var first = s.Scope.Begin(outer, 50);
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Outer card begins its dedicated sequence");
                    string outerSequence = (string)s.Sprite.Calls.Last().Args[2];
                    s.Scope.Physical(outer, [new(s.Target)], "outer-hit", 50);
                    Program.Equal(outerSequence, (string)s.Sprite.Calls.Last(c => c.Method == "combat_impact").Args[1],
                        "Ordinary contact uses the attack sequence established by its native resume");
                    var inner = s.Card("u08"); var nested = s.Scope.Begin(inner, 51);
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Nested card owns its trigger");
                    Program.Equal("bite_rend", s.Sprite.Animation, "Nested bite identity");
                    Program.Check((string)s.Sprite.Calls.Last().Args[2] != outerSequence, "Nested card owns a distinct actor sequence");
                    s.Scope.Finish(nested);
                    s.Sprite.Animation = "hurt";
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Outer card resumes after nested completion or hurt");
                    Program.Equal("ground_slam", s.Sprite.Animation, "Outer dedicated motion restored");
                    Program.Equal(1, (int)s.Sprite.Calls.Last().Args[1], "Resume starts before next actual segment");
                    Program.Equal(outerSequence, (string)s.Sprite.Calls.Last().Args[2], "Outer resume retains its original actor sequence");
                    s.Scope.Finish(first);
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "Finished outer play releases native trigger");
                    break;
                }
                case "trigger-indices":
                {
                    var card = s.Card("c22"); var paid = s.Scope.Begin(card, 55);
                    s.Scope.Physical(card, [new(s.Target)], "physical-one", 55);
                    var attackImpact = s.Sprite.Calls.Last(c => c.Method == "combat_impact");
                    Program.Equal(2, attackImpact.Args.Length, "Ordinary contact supplies an explicit sequence");
                    string attackSequence = (string)attackImpact.Args[1];
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 55));
                    string castSequence = (string)s.Sprite.Calls.Last(c => c.Method == "combat_impact").Args[1];
                    Program.Check(attackSequence.EndsWith(":attack") && castSequence.EndsWith(":cast") &&
                        attackSequence[..^7] == castSequence[..^5], "Mixed card hit families have distinct sequences under the same CardPlay");
                    Program.Check(attackSequence != castSequence, "Physical zero cannot suppress lightning zero in the actor ledger");
                    s.Scope.Lightning(Batch(s, card, LightningVisualOrigin.Card, 55));
                    Program.Equal(castSequence, (string)s.Sprite.Calls.Last(c => c.Method == "combat_impact").Args[1],
                        "Each direct lightning contact keeps its cast family sequence");
                    Program.Equal(castSequence, (string)s.Sprite.Calls.Last(c => c.Method == "resume_action").Args[2],
                        "Lightning contact and recovery share a cast family sequence");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Native attack resumes the current paid play");
                    Program.Equal(1, (int)s.Sprite.Calls.Last().Args[1], "Attack uses ordinary segment progress");
                    Program.Equal(attackSequence, (string)s.Sprite.Calls.Last().Args[2], "Native Attack resumes the physical contact sequence");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Repeated native attack can retain its current sequence");
                    Program.Equal(attackSequence, (string)s.Sprite.Calls.Last().Args[2], "Attack family sequence stays stable across native triggers");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Cast"), "Native cast resumes current paid play");
                    Program.Equal(2, (int)s.Sprite.Calls.Last().Args[1], "Cast uses direct lightning progress");
                    Program.Equal(castSequence, (string)s.Sprite.Calls.Last().Args[2], "Native Cast resumes the lightning contact sequence");
                    Program.Check(!BeforeNativeAnimation(s.Node, "Cast"), "Repeated native cast retains its family sequence");
                    Program.Equal(castSequence, (string)s.Sprite.Calls.Last().Args[2], "Cast family sequence stays stable across native triggers");
                    s.Scope.Finish(paid); s.Scope.Begin(card, 55, replay: 1);
                    Program.Check(!BeforeNativeAnimation(s.Node, "Attack"), "Replay resumes its own sequence");
                    Program.Equal(0, (int)s.Sprite.Calls.Last().Args[1], "Replay does not inherit paid segment progress");
                    Program.Check(attackSequence != (string)s.Sprite.Calls.Last().Args[2], "Replay has a distinct attack sequence even in the same wrapper");
                    break;
                }
                case "stale-source":
                {
                    var outer = s.Card("c03"); s.Scope.Begin(outer, 60);
                    var inner = s.Card("u08"); var play = s.Scope.Begin(inner, 61);
                    s.Scope.Physical(outer, [new(s.Target)], "outer-late", 60);
                    Program.Equal(1, s.Effects.Combat.Count, "An actual outer receipt still has contact feedback");
                    Program.Equal(0, Impacts(s), "Outer receipt cannot advance an active nested card's body");
                    s.Scope.Physical(null, [new(s.Target)], "unscoped", null);
                    Program.Equal(0, Impacts(s), "Unscoped damage cannot advance an active card");
                    s.Scope.Finish(play); s.Scope.Begin(inner, 62);
                    s.Scope.Physical(inner, [new(s.Target)], "old-same-card", 61);
                    Program.Equal(0, Impacts(s), "Old same-card play identity cannot advance a new play");
                    s.Scope.Lightning(Batch(s, inner, LightningVisualOrigin.Card, 61));
                    Program.Equal(0, Impacts(s), "Old card lightning identity cannot advance a new play");
                    break;
                }
                case "lifecycle":
                {
                    var card = s.Card("c02"); s.Scope.Begin(card, 70);
                    QueueDispatch = true;
                    OrdinarySegment(s.Room.Combat, s.Owner, card, 70, [new(s.Target)]);
                    Setup();
                    while (Pending.TryDequeue(out var pending)) pending();
                    QueueDispatch = false;
                    Program.Equal(0, s.Effects.Combat.Count, "Queued old room receipt cannot cross a room replacement");
                    foreach (var reason in new[] { "death", "stop", "dispose" })
                    {
                        var life = Setup(); var active = life.Card("c02"); life.Scope.Begin(active, 71);
                        life.Scope.Deactivate(reason);
                        Program.Equal(0, life.Scope.ActivePlays, reason + " clears combat play state");
                        Program.Check(BeforeNativeAnimation(life.Node, "Attack"), reason + " cannot suppress native trigger");
                        life.Scope.Physical(active, [new(life.Target)], reason, 71);
                        Program.Equal(0, life.Effects.Combat.Count, reason + " cannot emit a stale contact");
                        life.Scope.Lightning(Batch(life, active, LightningVisualOrigin.Card, 71));
                        Program.Equal(0, life.Effects.Combat.Count, reason + " cannot emit stale lightning");
                    }
                    break;
                }
                case "ending-contact":
                {
                    var card = s.Card("c03"); s.Scope.Begin(card, 80);
                    s.Target.IsAlive = false;
                    CombatManager.Instance.IsEnding = true;
                    OrdinarySegment(s.Room.Combat, s.Owner, card, 80, [new(s.Target, 12)]);
                    Program.Equal(1, s.Effects.Combat.Count, "Same-room committed final hit remains visible during ending tail");
                    Program.Equal(0, Impacts(s), "Final contact must not restart an ending body's action");
                    Program.Check(BeforeNativeAnimation(s.Node, "Attack"), "Ending cannot claim new generic actions");
                    LightningCommitted(Batch(s, card, LightningVisualOrigin.Card, 80));
                    Program.Equal(2, s.Effects.Combat.Count, "Same-room committed final lightning survives the gameplay ending guard");
                    Program.Equal(0, Impacts(s), "Final lightning contact cannot restart an ending body");
                    s.Scope.SuspendEnding(); s.Scope.SuspendEnding();
                    Program.Equal(1, s.Effects.PersistentStops, "Ending suspension is idempotent and stops persistent layers once");
                    Program.Equal(0, s.Effects.AllStops, "Ending suspension cannot cut off one-shot hit tails");
                    Program.Equal(1, s.Scope.ActivePlays, "Ending preserves play identity for late committed contacts");
                    OrdinarySegment(s.Room.Combat, s.Owner, card, 80, [new(s.Target, 12)]);
                    Program.Equal(3, s.Effects.Combat.Count, "A committed contact after ending suspension still renders");
                    break;
                }
                default: throw new ArgumentException("Unknown case: " + name);
            }
        }
    }
}

namespace Volibear.Core
{
    public static class LightningBatches
    {
        public static event Action<LightningBatch>? VisualCommitted;
        // PRODUCTION_LIGHTNING_PRESENT
    }
    public interface IOrdinarySegmentResponder
    { Task AfterOrdinarySegment(PlayerChoiceContext context, CardModel card, DamageResult[] results); }
    internal static class DomainPower
    {
        internal static readonly List<string> Trace = [];
        internal static Task AttachAfterOrdinarySegment(PlayerChoiceContext context, CardResolutionHooks.PlayScope scope)
        { Trace.Add("domain"); return Task.CompletedTask; }
    }
    public static partial class CardResolutionHooks
    {
        internal sealed class GateState { internal bool Closed; }
        internal sealed class PlayScope(CardModel card, long id)
        {
            internal readonly CardModel Card = card;
            internal readonly long Id = id;
            internal readonly GateState Gate = new();
        }
        private static readonly AsyncLocal<PlayScope?> Current = new();
        public static long? CurrentPlayId(CardModel card) => Current.Value is { } scope &&
            !scope.Gate.Closed && ReferenceEquals(card, scope.Card) ? scope.Id : null;
        internal static void FixtureBegin(CardModel card, long id) => Current.Value = new(card, id);
        // PRODUCTION_PIPELINE
        private sealed class Responder : IOrdinarySegmentResponder
        {
            public Task AfterOrdinarySegment(PlayerChoiceContext context, CardModel card, DamageResult[] results)
            { DomainPower.Trace.Add("responder"); return Task.CompletedTask; }
        }
        internal static async Task RunCase(string name)
        {
            var combat = new CombatState();
            var owner = new Creature { CombatState = combat, CombatId = 1 };
            owner.Player = new(owner);
            owner.Powers.Add(new Responder());
            var card = new CardModel("c02", owner);
            var target = new Creature { CombatState = combat, CombatId = 2 };
            var results = new DamageResult[] { new(target) };
            var context = new PlayerChoiceContext();
            CombatManager.Instance.State = combat;
            CombatManager.Instance.IsInProgress = true;
            CombatManager.Instance.IsEnding = false;
            FixtureBegin(card, 101);
            int events = 0;
            OrdinarySegmentCommitted += (actualCombat, dealer, source, id, snapshot) =>
            {
                events++; DomainPower.Trace.Add("receipt");
                Program.Check(ReferenceEquals(combat, actualCombat) && ReferenceEquals(owner, dealer) &&
                    ReferenceEquals(card, source) && id == 101, "Receipt preserves combat, owner, source and play identity");
                Program.Check(ReferenceEquals(results[0], snapshot[0]), "Receipt preserves native result identity");
                try { ((IList<DamageResult>)snapshot)[0] = new(target); throw new InvalidOperationException("Mutable receipt"); }
                catch (NotSupportedException) { }
            };
            switch (name)
            {
                case "pipeline-order":
                {
                    OrdinarySegmentCommitted += (_, _, _, _, _) => throw new InvalidOperationException("visual observer fault");
                    OrdinarySegmentCommitted += (_, _, _, _, _) => DomainPower.Trace.Add("second-observer");
                    var native = new TaskCompletionSource<IEnumerable<DamageResult>>(TaskCreationOptions.RunContinuationsAsynchronously);
                    var task = OrdinaryAttackPipelineV1(context, ValueProp.Move, owner, card, () =>
                    { DomainPower.Trace.Add("native-dispatch"); return native.Task; });
                    Program.Equal(0, events, "Pending native damage has no completed receipt");
                    Program.Check(!task.IsCompleted, "Pipeline retains native await");
                    native.SetResult(results);
                    var returned = (await task).ToArray();
                    Program.Check(DomainPower.Trace.SequenceEqual(["native-dispatch", "receipt", "second-observer", "domain", "responder"]),
                        "Receipt follows native success and precedes domain/responders; observer failure is isolated");
                    Program.Check(ReferenceEquals(results[0], returned[0]), "Pipeline returns original native result identities");
                    break;
                }
                case "pipeline-fault-cancel":
                {
                    var failure = new InvalidOperationException("native failure");
                    try
                    {
                        await OrdinaryAttackPipelineV1(context, ValueProp.Move, owner, card,
                            () => Task.FromException<IEnumerable<DamageResult>>(failure));
                        throw new Exception("Native fault was swallowed");
                    }
                    catch (InvalidOperationException error) { Program.Check(ReferenceEquals(failure, error), "Original native fault retained"); }
                    using var cancellation = new CancellationTokenSource(); cancellation.Cancel();
                    try
                    {
                        await OrdinaryAttackPipelineV1(context, ValueProp.Move, owner, card,
                            () => Task.FromCanceled<IEnumerable<DamageResult>>(cancellation.Token));
                        throw new Exception("Native cancellation was swallowed");
                    }
                    catch (OperationCanceledException error) { Program.Equal(cancellation.Token, error.CancellationToken, "Native cancellation token retained"); }
                    Program.Equal(0, events, "Fault/cancellation cannot manufacture settled contacts");
                    Program.Equal(0, DomainPower.Trace.Count, "Fault/cancellation cannot enter domain or responders");
                    break;
                }
                case "pipeline-scope":
                {
                    var native = new TaskCompletionSource<IEnumerable<DamageResult>>();
                    var task = OrdinaryAttackPipelineV1(context, ValueProp.Move, owner, card, () => native.Task);
                    Current.Value!.Gate.Closed = true;
                    native.SetResult(results); await task;
                    Program.Equal(0, events, "Closed paid scope cannot emit a late receipt");
                    Program.Equal(0, DomainPower.Trace.Count, "Closed scope prevents domain continuation");
                    FixtureBegin(card, 101);
                    owner.CombatState = new CombatState();
                    await OrdinaryAttackPipelineV1(context, ValueProp.None, owner, card, () => Task.FromResult<IEnumerable<DamageResult>>(results));
                    Program.Equal(0, events, "Mismatched live combat cannot emit a receipt");
                    owner.CombatState = combat;
                    await OrdinaryAttackPipelineV1(context, ValueProp.Unpowered, owner, card, () => Task.FromResult<IEnumerable<DamageResult>>(results));
                    Program.Equal(1, events, "Ordinary callsite identifies a segment even with Unpowered flags");
                    Program.Check(DomainPower.Trace.SequenceEqual(["receipt"]), "Non-Move segment does not change domain semantics");
                    break;
                }
                default: throw new ArgumentException(name);
            }
        }
    }
}
