using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;

static class Program
{
    private static int checks;
    private static void Need(bool value, string message)
    {
        checks++;
        if (!value) throw new InvalidOperationException(message);
    }

    static void Main(string[] args)
    {
        string name = args[0];
        if (name == "low-health")
        {
            var low = new OwnerScope(20, 100);
            low.InitialSnapshot(); // CombatSetUp can run before native IsInProgress.
            Need(!low.IsLow, "Inactive setup must not play a pose");
            low.Tick();
            Need(!low.IsLow, "Starting state must stay silent");
            low.Playable = true;
            low.Tick();
            Need(low.IsLow, "Starting low HP must select weak pose once playable");
            Need(low.Sounds.Count == 0, "Initial snapshot must not announce a fresh low-HP transition");
            low.Tick();
            Need(low.IsLow && low.Sounds.Count == 0, "Repeated snapshots must stay idempotent");
            low.HealthChanged(34);
            Need(low.IsLow, "Low pose must survive recovery below the 35 percent exit threshold");
            low.HealthChanged(35);
            Need(!low.IsLow, "35 percent HP must leave low pose");
            low.HealthChanged(31);
            Need(!low.IsLow, "31 percent HP must not enter low pose");
            low.HealthChanged(30);
            Need(low.IsLow && low.Sounds.Count == 1, "30 percent damage transition must announce once");
            low.HealthChanged(20); low.Tick();
            Need(low.Sounds.Count == 1, "Damage within low pose must not repeat voice");
            var healthy = new OwnerScope(80, 100) { Playable = true };
            healthy.Tick();
            Need(!healthy.IsLow && healthy.Sounds.Count == 0, "Healthy opening must retain ordinary pose");
            var invalidMax = new OwnerScope(0, 0) { Playable = true };
            invalidMax.Tick();
            Need(!invalidMax.IsLow, "Zero max HP must not divide or request a low pose");
        }
        else if (name == "replay")
        {
            var owner = new OwnerScope(80, 100) { Playable = true };
            var card = new CardModel("u23");
            owner.Own(card);
            card.View = new NCard();
            owner.CardStarted(new CardPlay(card, 0), "paid");
            Need(owner.PrimaryStarts == 1 && owner.Roars == 1, "Paid play must retain its authored motion and roar");
            owner.CardStarted(new CardPlay(card, 1), "repeat-1");
            owner.CardStarted(new CardPlay(card, 2), "repeat-2");
            Need(owner.ReplayMarkers == 2, "Each actual replay must retain its card marker");
            Need(owner.PrimaryStarts == 1, "Replay must not restart primary motion");
            Need(owner.Roars == 1, "Replay must not repeat the paid-action roar");
            owner.CardStarted(new CardPlay(card, 0), "next-paid");
            Need(owner.PrimaryStarts == 2, "A new paid use of the same card must start its own motion");
            owner.Playable = false;
            owner.CardStarted(new CardPlay(card, 0), "inactive");
            owner.CardStarted(new CardPlay(card, 1), "inactive-repeat");
            Need(owner.PrimaryStarts == 2 && owner.ReplayMarkers == 2, "Inactive owner must not emit presentation");
        }
        else if (name == "card-anchor")
        {
            var owner = new OwnerScope(80, 100) { Playable = true };
            var card = new CardModel("c13");
            owner.Own(card);
            card.Captured = new NativeNode(); // Existing measured-anchor boundary, no invented card view.
            owner.AtCard("exhaust", "card_exhaust", card);
            Need(owner.Visuals.Count == 1 && owner.Visuals[0].Effect == "card_exhaust",
                "Exhaust after view removal must retain the measured card effect");
            Need(ReferenceEquals(owner.Visuals[0].Anchors.Card, card.Captured), "Must use this card's measured anchor");
            Need(owner.Sounds.SequenceEqual(["sfx.card_exhaust"]), "Committed exhaust retains exactly one sound request");
            card.Captured = null;
            owner.AtCard("hidden-exhaust", "card_exhaust", card);
            Need(owner.Visuals.Count == 1 && owner.Sounds.Count == 2, "Hidden cards without a measured anchor stay sound-only");
            card.View = new NCard();
            owner.AtCard("draw", "card_draw", card);
            Need(ReferenceEquals(owner.Visuals[^1].Anchors.Card, card.View) &&
                ReferenceEquals(owner.Visuals[^1].Anchors.Source, owner.DrawPile), "Visible draw must retain the actual card and pile anchors");
            owner.AtCard("discard", "card_discard", card);
            Need(ReferenceEquals(owner.Visuals[^1].Anchors.Target, owner.DiscardPile), "Discard retains the actual destination pile");
            var foreign = new CardModel("c13") { View = new NCard() };
            new OwnerScope(80, 100).Own(foreign);
            int count = owner.Visuals.Count, sounds = owner.Sounds.Count;
            owner.AtCard("foreign", "card_exhaust", foreign);
            owner.Playable = false;
            owner.AtCard("closed", "card_exhaust", card);
            Need(owner.Visuals.Count == count && owner.Sounds.Count == sounds, "Foreign/closed owners must not emit card presentation");
        }
        else if (name == "contact-bindings")
        {
            Godot.FileAccess.Repository = args[1];
            ContactRouting.Load();
            using var bindings = JsonDocument.Parse(File.ReadAllText(Path.Combine(args[1], "assets/animation/vfx/card_vfx_bindings.json")));
            var cards = bindings.RootElement.GetProperty("cards").EnumerateArray().ToArray();
            Need(cards.Length == 89 && ContactRouting.MotionCount == 89, "All 89 actual card bindings must load");
            foreach (var row in cards)
            {
                var cues = row.GetProperty("cues").EnumerateArray().Where(c => c.GetProperty("event").GetString() == "physical_damage_resolved").ToArray();
                if (cues.Length == 0) continue;
                var key = row.GetProperty("asset_key").GetString()!;
                Need(ContactRouting.For(new CardModel(key)) == cues[0].GetProperty("effect_id").GetString(),
                    "Native contact must retain the approved cue for " + key);
            }
            foreach (string key in new[] { "c22", "u20", "u24", "u38", "r08" })
                Need(ContactRouting.For(new CardModel(key)) == "claw_slash", "Heavy motion must not invent heavy contact for " + key);
            Need(ContactRouting.For(new CardModel("c10")) == "counter_release", "Counter contact must survive domain pose fallback");
            Need(ContactRouting.For(new CardModel("u08")) == "bite_hit", "Bite must retain its distinct contact");
            Need(ContactRouting.For(new CardModel("c03")) == "heavy_impact", "Authored heavy contact must remain heavy");
            Need(ContactRouting.For(new CardModel("t01")) == "claw_slash", "Converted claw presentation uses its form binding");
            Need(ContactRouting.For(null) == "claw_slash" && ContactRouting.For(new CardModel("foreign")) == "claw_slash",
                "Unbound ordinary attacks retain the neutral contact fallback");
        }
        else if (name == "engage-voice")
        {
            var owner = new OwnerScope(80, 100) { Playable = true };
            var card = new CardModel("c10"); owner.Own(card);
            Creature enemy = new(50, 50), other = new(50, 50);
            EngageRouting.Intent(card, enemy, null); // No real intent boundary reached.
            EngageRouting.Intent(card, enemy, other); // An unrelated native intent is not this invocation.
            Need(owner.Sounds.Count == 0 && owner.Poses.Count == 0, "Rejected/unrelated intents must not announce an engage");
            EngageRouting.Intent(card, enemy, enemy, repeats: 3);
            Need(owner.Sounds.SequenceEqual(["voice.roar"]) && owner.Poses.Count == 1,
                "One matching accepted intent must announce once despite duplicate callbacks");
            EngageRouting.Group(card, () =>
            {
                EngageRouting.Intent(card, enemy, null); // First candidate may be ineligible.
                EngageRouting.Intent(card, enemy, enemy);
                EngageRouting.Intent(card, other, other);
            });
            Need(owner.Sounds.Count == 2 && owner.Poses.Count == 3,
                "Actual group enemies keep their telegraphs but share one challenge voice");
            EngageRouting.Group(card, () => EngageRouting.Intent(card, other, other));
            Need(owner.Sounds.Count == 3, "A later PerformAll invocation must have a new voice identity");
            owner.Playable = false;
            EngageRouting.Intent(card, enemy, enemy);
            Need(owner.Sounds.Count == 3, "Ended owner must not start another challenge voice");
        }
        else throw new ArgumentException("Unknown case");
        Console.WriteLine($"PRESENTATION_BEHAVIOR_PASS {name} checks={checks} native-gameplay=NOT_RUN");
    }
}

sealed record CardModel(string Key)
{
    internal readonly Player Owner = new();
    internal NCard? View;
    internal NativeNode? Captured;
}
sealed record CardPlay(CardModel Card, int PlayIndex);
sealed class Player { internal Creature Creature = null!; }
interface ICombatState;
sealed class CombatState : ICombatState;
sealed class Creature(int hp, int maxHp)
{
    internal int CurrentHp = hp, MaxHp = maxHp;
    internal bool IsAlive = true;
    internal ICombatState? CombatState = new CombatState();
    internal OwnerScope? Presentation;
}
class NativeNode;
sealed class NCard : NativeNode { internal static NCard? FindOnTable(CardModel card) => card.View; }
sealed class NCreature(Creature entity) { internal readonly Creature Entity = entity; }
sealed record EffectAnchors(NativeNode? Card = null, NativeNode? Source = null, NativeNode? Target = null);
sealed record Visual(string Effect, EffectAnchors Anchors);
sealed class NativeUi { internal readonly NativeNode DrawPile = new(), DiscardPile = new(); }
sealed class CombatRoom { internal readonly NativeUi Ui = new(); }
sealed class SceneRoomScope
{
    internal readonly CombatRoom Room = new();
    internal NativeNode? NodeFor(Creature _) => null;
}
sealed class Effects
{
    internal readonly List<string> Sounds = [];
    internal readonly List<Visual> Visuals = [];
    private readonly HashSet<string> heard = [];
    internal void PlaySound(string id, string cue) { if (heard.Add(id + ":" + cue)) Sounds.Add(cue); }
    internal bool RenewLoop(string _, float seconds) => true;
    internal void Emit(string id, string effect, EffectAnchors anchors, string? targetId = null, string? persistentKey = null, float leaseSeconds = 0) =>
        Visuals.Add(new(effect, anchors));
}

sealed class OwnerScope(int hp, int maxHp)
{
    private readonly Creature _owner = new(hp, maxHp);
    private readonly SceneRoomScope _room = new();
    private readonly Effects _effects = new();
    private NativeNode _node = new();
    private bool _disposed = false, _combatStopped = false, _dead = false, _domain = false, _lowHealth;
    private readonly string _domainKey = "domain";
    internal bool Playable;
    private bool Live => Playable && !_dead && !_disposed && !_combatStopped;
    internal bool IsLow => _lowHealth;
    internal List<string> Sounds => _effects.Sounds;
    internal List<Visual> Visuals => _effects.Visuals;
    internal readonly List<string> Poses = [];
    internal int PrimaryStarts, Roars;
    internal int ReplayMarkers => Visuals.Count(v => v.Effect == "card_replay");
    internal NativeNode DrawPile => _room.Room.Ui.DrawPile;
    internal NativeNode DiscardPile => _room.Room.Ui.DiscardPile;
    internal void Own(CardModel card) { card.Owner.Creature = _owner; _owner.Presentation = this; }
    internal sealed class PlayMotion;
    internal PlayMotion? FindMotion(CardModel _) => null;
    internal void InitialSnapshot() => UpdateLowHealth(announce: false);
    internal void HealthChanged(int hp) { _owner.CurrentHp = hp; UpdateLowHealth(); }
    private static bool Valid(NativeNode? node) => node is not null;
    private static EffectAnchors Anchors(NativeNode? card = null) => new(Card: card);
    private static string? CardId(CardModel card) => card.Key;
    private static NativeNode? CardAnchor(CardModel card) => card.View ?? card.Captured;
    private static string Next(string value) => value;
    private void Died(Creature _) => _dead = true;
    private void ReleaseCapturedAnchors() { }
    private void TickSemanticVisuals() { }
    private void SubscribeLightning() { }
    private void UpdateDomain(bool announce) { }
    private void RefreshIdle() { }
    private static string MotionKey(CardModel card) => card.Key;
    private void BeginMotion(CardPlay _, string id) => PrimaryStarts++;
    private void AtOwner(string id, string effect) { if (effect == "roar_wave") Roars++; }
    internal void AtTarget(string id, string effect, Creature _) { }
    private void Pose(string clip) => Poses.Add(clip);

    // PRODUCTION_METHODS
}

static class ContactRouting
{
    private static bool _metadataLoaded;
    private static readonly Dictionary<string, string> Motions = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, string> ContactEffects = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, string> StartVoices = new();
    private static string? MotionKey(CardModel? card) => card?.Key;
    private static string ReadMotion(JsonElement row) => row.GetProperty("clip").GetString()!;
    internal static int MotionCount => Motions.Count;
    internal static void Load() => ReadMetadata();
    internal static string For(CardModel? card) => ContactEffectFor(card);

    // PRODUCTION_METADATA
}

static class EngageRouting
{
    private static readonly AsyncLocal<EngageObservation?> ActiveEngage = new();
    private static readonly AsyncLocal<EngageGroup?> ActiveEngageGroup = new();
    private static long sequence;
    private static string Next(string kind) => kind + ":" + ++sequence;
    private static bool Bear(Creature owner) => owner.Presentation is not null;
    private static OwnerScope? Owner(Creature owner) => owner.Presentation;
    private static void Warn(string _, Exception error) => throw error;
    private static void Dispatch(string _, Action action) => action();
    internal static void Intent(CardModel card, Creature target, Creature? actual, int repeats = 1)
    {
        BeforeEngage(target, card, out var state);
        try { if (actual is not null) for (int i = 0; i < repeats; i++) BeforeIntent(new(actual)); }
        finally { FinishEngageInvocation(null, state); }
    }
    internal static void Group(CardModel card, Action action)
    {
        BeforeEngageGroup(card, out var state);
        try { action(); }
        finally { FinishEngageGroupInvocation(null, state); }
    }

    // PRODUCTION_ENGAGE
}

namespace Godot
{
    // Only resource reading is substituted. Metadata parsing/routing above is the
    // exact production method body; this is not a native Godot scene-graph test.
    sealed class FileAccess(string path) : IDisposable
    {
        internal static string Repository = "";
        internal enum ModeFlags { Read }
        internal static FileAccess Open(string resource, ModeFlags _) => new(Path.Combine(Repository,
            resource.Replace("res://VolibearArt/", "assets/animation/")));
        internal string GetAsText() => File.ReadAllText(path);
        public void Dispose() { }
    }
}
