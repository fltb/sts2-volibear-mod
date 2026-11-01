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
        else if (name == "owner-anchors")
        {
            var room = new SceneRoomScope();
            var local = new OwnerScope(80, 100, room) { Playable = true };
            var remote = new OwnerScope(80, 100, room) { Playable = true };
            var localCard = new CardModel("c13") { View = new NCard() };
            var remoteCard = new CardModel("c13") { View = new NCard() };
            local.Own(localCard); remote.Own(remoteCard);

            local.AtOwner("local-energy", "energy_gain");
            Need(ReferenceEquals(local.Visuals[^1].Anchors.Energy, room.Room.Ui.EnergyCounterContainer),
                "Local energy must use the actual local HUD");
            remote.AtOwner("remote-energy", "energy_gain");
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Energy, remote.WorldAnchor) &&
                ReferenceEquals(remote.Visuals[^1].Anchors.Owner, remote.CreatureVisuals),
                "Remote energy must use its own actual creature anchor");

            int count = remote.Visuals.Count;
            remote.AtCard("remote-draw", "card_draw", remoteCard);
            remote.AtCard("remote-discard", "card_discard", remoteCard);
            Need(remote.Visuals.Count == count, "Remote draw and discard must not borrow local pile UI");
            Need(remote.Sounds.SequenceEqual(["sfx.card_draw", "sfx.card_discard"]),
                "Remote private piles retain committed draw/discard sound");
            local.AtCard("local-draw", "card_draw", localCard);
            Need(ReferenceEquals(local.Visuals[^1].Anchors.Source, local.DrawPile) &&
                ReferenceEquals(local.Visuals[^1].Anchors.Card, localCard.View),
                "Local draw retains the actual source and visible card");
            local.AtCard("local-discard", "card_discard", localCard);
            Need(ReferenceEquals(local.Visuals[^1].Anchors.Target, local.DiscardPile),
                "Local discard retains the actual destination");

            foreach (var from in new[] { PileType.Draw, PileType.Discard })
            {
                var id = 100 + (int)from;
                local.CardAudio(new(id, room.Combat, local.Player.Creature, localCard, localCard, "card_retrieve", from));
                Need(ReferenceEquals(local.Visuals[^1].Anchors.Source,
                        from == PileType.Draw ? local.DrawPile : local.DiscardPile),
                    "Local retrieval uses the actual recorded source pile");
                int sounds = remote.Sounds.Count;
                remote.CardAudio(new(id, room.Combat, remote.Player.Creature, remoteCard, remoteCard, "card_retrieve", from));
                Need(remote.Visuals.Count == count && remote.Sounds.Count == sounds + 1,
                    "Remote retrieval is sound-only for either private source pile");
            }
            foreach (var kind in new[] { "scry_selection_opened", "selected_card_discarded" })
            {
                var id = kind == "scry_selection_opened" ? 200 : 201;
                local.Gameplay(new(id, room.Combat, local.Player.Creature, kind, localCard, localCard, null, 1));
                Need(ReferenceEquals(kind == "scry_selection_opened" ? local.Visuals[^1].Anchors.Source : local.Visuals[^1].Anchors.Target,
                        kind == "scry_selection_opened" ? local.DrawPile : local.DiscardPile),
                    "Local selection semantics keep their actual pile endpoints");
                int sounds = remote.Sounds.Count;
                remote.Gameplay(new(id, room.Combat, remote.Player.Creature, kind, remoteCard, remoteCard, null, 1));
                Need(remote.Visuals.Count == count && remote.Sounds.Count == sounds + 1,
                    "Remote selection semantics must not borrow the local HUD");
            }

            remote.AtCard("remote-exhaust", "card_exhaust", remoteCard);
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Card, remoteCard.View) &&
                ReferenceEquals(remote.Visuals[^1].Anchors.Owner, remote.CreatureVisuals),
                "Remote visible exhaust uses its actual card and creature");
            remote.CardAudio(new(300, room.Combat, remote.Player.Creature, remoteCard, remoteCard, "card_purify", PileType.Hand));
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Card, remoteCard.View),
                "Remote purification still renders on the actual visible card");
            remote.Gameplay(new(301, room.Combat, remote.Player.Creature, "card_charge_changed", remoteCard, remoteCard, null, 1));
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Owner, remoteCard.View),
                "Remote committed card enhancement keeps its real card anchor");

            count = remote.Visuals.Count;
            int previousSounds = remote.Sounds.Count;
            remoteCard.View = null;
            remote.AtCard("remote-hidden", "card_exhaust", remoteCard);
            Need(remote.Visuals.Count == count && remote.Sounds.Count == previousSounds + 1,
                "Hidden remote cards remain sound-only without invented coordinates");
            remoteCard.View = new NCard();
            previousSounds = remote.Sounds.Count;
            remote.CardAudio(new(302, new CombatState(), remote.Player.Creature, remoteCard, remoteCard, "card_purify", PileType.Hand));
            remote.Gameplay(new(303, room.Combat, local.Player.Creature, "card_charge_changed", localCard, localCard, null, 1));
            Need(remote.Visuals.Count == count && remote.Sounds.Count == previousSounds,
                "Other combat/owner receipts cannot emit in this scope");

            room.Combat.LocalPlayer = remote.Player;
            remote.AtOwner("switched-local", "energy_gain");
            local.AtOwner("switched-remote", "energy_gain");
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Energy, room.Room.Ui.EnergyCounterContainer) &&
                ReferenceEquals(local.Visuals[^1].Anchors.Energy, local.WorldAnchor),
                "The local player's identity is resolved from this combat for each event");
            remote.AtCard("switched-draw", "card_draw", remoteCard);
            Need(ReferenceEquals(remote.Visuals[^1].Anchors.Source, remote.DrawPile),
                "The newly local owner receives the real draw pile");
            count = local.Visuals.Count;
            local.AtCard("switched-old-draw", "card_draw", localCard);
            Need(local.Visuals.Count == count, "The previous local owner no longer owns the local piles");

            room.Combat.LocalPlayer = null;
            count = remote.Visuals.Count;
            remote.AtCard("no-local-draw", "card_draw", remoteCard);
            Need(remote.Visuals.Count == count, "An absent local player cannot donate the local HUD to any owner");
            remote.AllowVisuals = false;
            previousSounds = remote.Sounds.Count;
            remote.AtOwner("missing-energy-node", "energy_gain");
            Need(remote.Visuals.Count == count && remote.Sounds.Count == previousSounds + 1 &&
                remote.Sounds[^1] == "sfx.energy_gain", "Unlocatable energy visuals retain the committed sound");
        }
        else if (name == "native-audio")
        {
            var fabricated = new[]
            {
                "event:/sfx/characters/volibear_character/volibear_character_select",
                "event:/sfx/characters/volibear_character/volibear_character_attack",
                "event:/sfx/characters/volibear_character/volibear_character_cast",
                "event:/sfx/characters/volibear_character/volibear_character_die",
                "event:/sfx/ui/wipe_volibear_character"
            };
            foreach (string path in fabricated)
            {
                Need(!NativeAudioPolicy.BeforeNativeOneShot(path), "Nonexistent Volibear default must not reach FMOD");
                Need(NativeAudioPolicy.BeforeNativeOneShot(path + "_legitimate_extension"),
                    "A legitimate added event must not be suppressed by prefix matching");
                Need(NativeAudioPolicy.BeforeNativeOneShot(path.Replace("volibear_character", "ironclad")),
                    "Other characters' native voices must remain unchanged");
            }
            foreach (string? path in new[] { null, "", "event:/sfx/ui/card_play", "event:/sfx/characters/volibear_character/roar",
                "res://VolibearArt/audio/ogg/voice_select.ogg", "res://another_mod/attack.ogg", "user://custom.ogg", "uid://example" })
                Need(NativeAudioPolicy.BeforeNativeOneShot(path), "Only the exact missing defaults belong to this filter");
        }
        else if (name == "character-compat")
        {
            var table = new MegaCrit.Sts2.Core.Localization.LocTable();
            table.Values["OTHER_CHARACTER.title"] = "Unrelated character";
            Volibear.Content.VolibearLoc.AfterGetTable("characters", ref table);
            foreach (string key in new[] { "title", "titleObject", "description", "pronounSubject", "pronounObject",
                "pronounPossessive", "possessiveAdjective", "cardsModifierTitle", "cardsModifierDescription",
                "eventDeathPrevention", "aromaPrinciple", "goldMonologue", "banter.alive.endTurnPing", "banter.dead.endTurnPing" })
                Need(table.Values.TryGetValue("VOLIBEAR_CHARACTER." + key, out var text) && !string.IsNullOrWhiteSpace(text),
                    "Actual native character key must resolve: " + key);
            Need(table.Values["OTHER_CHARACTER.title"] == "Unrelated character", "Localization must preserve other characters");
            Need(!table.Values["VOLIBEAR_CHARACTER.eventDeathPrevention"].Contains("{0}"),
                "The native death-prevention getter supplies no unnamed format argument");
            var reloaded = new MegaCrit.Sts2.Core.Localization.LocTable();
            Volibear.Content.VolibearLoc.AfterGetTable("characters", ref reloaded);
            Need(reloaded.Values["VOLIBEAR_CHARACTER.cardsModifierTitle"] == table.Values["VOLIBEAR_CHARACTER.cardsModifierTitle"],
                "A newly loaded native language table receives the same complete character text");
            var relics = new MegaCrit.Sts2.Core.Localization.LocTable();
            Volibear.Content.VolibearLoc.AfterGetTable("relics", ref relics);
            Need(relics.Values.ContainsKey("SEA_GLASS.VOLIBEAR_CHARACTER.title"), "The native character-specific Sea Glass title resolves");
            var ancients = new MegaCrit.Sts2.Core.Localization.LocTable();
            Volibear.Content.VolibearLoc.AfterGetTable("ancients", ref ancients);
            string[] expected = ["THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-0r.ancient",
                "THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-1r.char", "THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-2r.ancient"];
            Need(ancients.Values.Keys.Order().SequenceEqual(expected.Order()),
                "The finale has one contiguous conversation, with the native repeat suffix on every line");
            Need(ancients.Values.Values.All(text => !string.IsNullOrWhiteSpace(text)), "Every finale line contains finished text");
            var character = new CharacterAssets();
            string[] paths = [character.CustomArmPointingTexturePath, character.CustomArmRockTexturePath,
                character.CustomArmPaperTexturePath, character.CustomArmScissorsTexturePath];
            Need(paths.Distinct().Count() == 4 && paths.All(p => p.StartsWith("res://VolibearArt/ui/images/multiplayer_hand_volibear_")),
                "Every native hand state resolves its own explicit character resource");
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

abstract record AbstractModel;
sealed record CardModel(string Key) : AbstractModel
{
    internal Player Owner = new();
    internal NCard? View;
    internal NativeNode? Captured;
}
sealed record CardPlay(CardModel Card, int PlayIndex);
sealed class Player { internal Creature Creature = null!; }
interface ICombatState { Player? LocalPlayer { get; set; } }
sealed class CombatState : ICombatState { public Player? LocalPlayer { get; set; } }
static class LocalContext { internal static Player? GetMe(ICombatState combat) => combat.LocalPlayer; }
enum PileType { None, Draw, Discard, Hand, Exhaust }
sealed record CommittedCardPresentation(long Id, ICombatState Combat, Creature Owner,
    CardModel Card, AbstractModel Source, string Effect, PileType From);
sealed record GameplayPresentationReceipt(long Id, ICombatState Combat, Creature Owner,
    string Kind, AbstractModel? Source, CardModel? Card, Creature? Target, decimal Amount);
sealed class Creature(int hp, int maxHp)
{
    internal int CurrentHp = hp, MaxHp = maxHp;
    internal bool IsAlive = true;
    internal ICombatState? CombatState = new CombatState();
    internal OwnerScope? Presentation;
    internal Player? Player;
}
class CanvasItem { internal bool Alive = true; }
class NativeNode : CanvasItem;
sealed class NCard : NativeNode { internal static NCard? FindOnTable(CardModel card) => card.View; }
sealed class NativeVisuals : NativeNode { internal readonly NativeNode VfxSpawnPosition = new(), TalkPosition = new(); }
sealed class NCreature(Creature entity) : NativeNode
{
    internal readonly Creature Entity = entity;
    internal readonly NativeVisuals Visuals = new();
}
sealed record EffectAnchors(CanvasItem Owner, CanvasItem? Target = null, CanvasItem? Source = null,
    CanvasItem? Card = null, CanvasItem? Energy = null, CanvasItem? OwnerHand = null,
    CanvasItem? OwnerMouth = null, CanvasItem? CardCost = null);
sealed record Visual(string Effect, EffectAnchors Anchors);
sealed class NativeUi { internal readonly NativeNode DrawPile = new(), DiscardPile = new(), EnergyCounterContainer = new(); }
sealed class CombatRoom { internal readonly NativeUi Ui = new(); }
sealed class SceneRoomScope
{
    internal readonly CombatRoom Room = new();
    internal readonly CombatState Combat = new();
    internal NCreature? NodeFor(Creature _) => null;
}
sealed class Effects
{
    internal readonly List<string> Sounds = [];
    internal readonly List<Visual> Visuals = [];
    internal bool AllowVisuals = true;
    private readonly HashSet<string> heard = [];
    internal void PlaySound(string id, string cue) { if (heard.Add(id + ":" + cue)) Sounds.Add(cue); }
    internal bool RenewLoop(string _, float seconds) => true;
    internal bool Emit(string id, string effect, EffectAnchors anchors, string? targetId = null,
        string? persistentKey = null, float leaseSeconds = 0, bool sound = true)
    {
        if (!AllowVisuals) return false;
        Visuals.Add(new(effect, anchors));
        return true;
    }
}

sealed class OwnerScope
{
    private readonly Creature _owner;
    private readonly SceneRoomScope _room;
    private readonly Effects _effects = new();
    private NCreature _node;
    internal OwnerScope(int hp, int maxHp, SceneRoomScope? room = null)
    {
        _room = room ?? new();
        _owner = new(hp, maxHp) { CombatState = _room.Combat };
        _owner.Player = new() { Creature = _owner };
        _room.Combat.LocalPlayer ??= _owner.Player;
        _node = new(_owner);
    }
    private bool _disposed = false, _combatStopped = false, _dead = false, _domain = false, _lowHealth;
    private readonly string _domainKey = "domain";
    internal bool Playable;
    private bool Live => Playable && !_dead && !_disposed && !_combatStopped;
    internal bool IsLow => _lowHealth;
    internal List<string> Sounds => _effects.Sounds;
    internal List<Visual> Visuals => _effects.Visuals;
    internal readonly List<string> Poses = [];
    private readonly Dictionary<Creature, string> _markTargets = [];
    internal int PrimaryStarts;
    internal int Roars => Visuals.Count(v => v.Effect == "roar_wave");
    internal int ReplayMarkers => Visuals.Count(v => v.Effect == "card_replay");
    internal NativeNode DrawPile => _room.Room.Ui.DrawPile;
    internal NativeNode DiscardPile => _room.Room.Ui.DiscardPile;
    internal NativeNode WorldAnchor => _node.Visuals.VfxSpawnPosition;
    internal NativeNode CreatureVisuals => _node.Visuals;
    internal Player Player => _owner.Player!;
    internal bool AllowVisuals { set => _effects.AllowVisuals = value; }
    internal void Own(CardModel card) { card.Owner = _owner.Player!; _owner.Presentation = this; }
    internal sealed class PlayMotion;
    internal PlayMotion? FindMotion(CardModel _) => null;
    internal void InitialSnapshot() => UpdateLowHealth(announce: false);
    internal void HealthChanged(int hp) { _owner.CurrentHp = hp; UpdateLowHealth(); }
    private static bool Valid(CanvasItem? node) => node is { Alive: true };
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
    internal void AtTarget(string id, string effect, Creature _) { }
    private void Pose(string clip) => Poses.Add(clip);
    private void BatchingBeastMotion(CardModel? _) { }
    private void BindMark(Creature _, string key, string id, bool sound) { }
    private static string CreatureId(Creature creature) => creature.GetHashCode().ToString();

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

static class NativeAudioPolicy
{
    // PRODUCTION_AUDIO
}

sealed class CharacterAssets
{
    // PRODUCTION_ARMS
}

namespace Volibear.Content
{
    static class MechanicGlossary { internal static Dictionary<string, string> Localization() => []; }
    static class InlineModelLocalization
    {
        internal static void Merge(string _, MegaCrit.Sts2.Core.Localization.LocTable table) { }
    }
}

namespace MegaCrit.Sts2.Core.Localization
{
    public sealed class LocTable
    {
        internal readonly Dictionary<string, string> Values = [];
        internal void MergeWith(Dictionary<string, string> entries)
        {
            foreach (var pair in entries) Values[pair.Key] = pair.Value;
        }
    }
    sealed class LocManager
    {
        internal static LocManager Instance { get; } = new();
        internal LocTable GetTable(string _) => new();
    }
}

namespace Godot
{
    static class GD
    {
        internal static void Print(string _) { }
        internal static void PrintErr(string message) => throw new InvalidOperationException(message);
    }
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
