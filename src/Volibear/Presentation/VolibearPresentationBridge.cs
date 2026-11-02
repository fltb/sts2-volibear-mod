using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

/// <summary>
/// Read-only bridge from committed native history/production receipts to presentation.
/// Never patches private card hooks, changes an original Task, or awaits cosmetic playback.
/// </summary>
public static partial class VolibearPresentationBridge
{
    private const string HarmonyId = "Volibear.Presentation.SemanticBridge";
    private sealed record DamageContact(string Effect);
    private static readonly Dictionary<string, Motion> Motions = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, string> ContactEffects = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, string> StartVoices = new(StringComparer.Ordinal);
    private static readonly ConcurrentQueue<Action> Pending = new();
    private static readonly HashSet<string> Warned = [];
    private static ConditionalWeakTable<DamageResult, DamageContact> DamageContacts = new();
    private static readonly AsyncLocal<EngageObservation?> ActiveEngage = new();
    private static RoomScope? _room;
    private static ICombatState? _historyState;
    private static int _historyIndex;
    private static int _mainThread;
    private static long _epoch;
    private static long _sequence;
    private static bool _installed;
    private static bool _metadataLoaded;

    /// <summary>Explicitly active primitive routes; this is not a claim that all 54 cues are wired.</summary>
    public static IReadOnlyDictionary<string, string> PrimitiveRoutes { get; } =
        new Dictionary<string, string>
        {
            ["native.card_play_started"] = "authored primary motion + action-start voice",
            ["native.creature_attacked"] = "claw_slash / heavy_impact / bite_hit",
            ["native.block_gained_positive"] = "guard_gain",
            ["native.damage_blocked_positive"] = "guard_hit",
            ["native.hp_lost_positive"] = "hurt voice/pose",
            ["native.card_drawn"] = "card_draw",
            ["native.card_discarded"] = "card_discard",
            ["native.card_exhausted"] = "card_exhaust",
            ["native.card_replay_started"] = "card_replay",
            ["lightning.batch_completed"] = "lightning_strike / lightning_all",
            ["native.storm_charge_increased"] = "lightning_growth",
            ["native.domain_state_transition"] = "domain_enter / domain_loop / domain_exit",
            ["engage.accepted_native_intent"] = "block telegraph pose (no invented block)",
            ["engage.completed_absorption_positive"] = "absorb",
            ["beast.converted"] = "feral_claw / feral_body",
            ["native.owner_died"] = "stop owned playback, death voice/pose",
            ["native.heal_internal_positive_commit"] = "heal at actual owner",
            ["native.gain_energy_positive_commit"] = "energy_gain at local energy counter or actual remote owner",
            ["native.health_ratio_state_transition"] = "weak/domain_weak pose and entry-only low_health voice",
            ["native.local_character_selected"] = "select voice attached to selected native background",
            ["native.combat_won"] = "victory voice attached to still-visible native room",
            ["committed.card_purify_or_retrieve"] = "card VFX on actual native card view; hidden cards sound-only",
            ["committed.owner_power"] = "owner VFX and sound; pending cost coupons do not invent a target card"
        };

    public static void Install()
    {
        if (_installed) return;
        _mainThread = Environment.CurrentManagedThreadId;
        // Observe existing boundaries without replacing any command or Task. The mod-owned
        // lightning entry is shared by every overload, including native card callbacks.
        var ready = Required(typeof(NCombatRoom), nameof(NCombatRoom._Ready));
        var reset = Required(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool));
        var lightning = Required(typeof(LightningCmd), "DealCore",
            typeof(PlayerChoiceContext), typeof(Creature), typeof(IEnumerable<Creature>), typeof(decimal), typeof(CardModel),
            typeof(bool), typeof(Action<IReadOnlyList<LightningHit>>));
        var engage = Required(typeof(EngageCmd), nameof(EngageCmd.Perform),
            typeof(PlayerChoiceContext), typeof(Creature), typeof(CardModel));
        var intent = Required(typeof(NCreature), nameof(NCreature.PerformIntent));
        var harmony = new Harmony(HarmonyId);
        harmony.Patch(ready, postfix: Handler(nameof(RoomReady)));
        harmony.Patch(reset, prefix: Handler(nameof(ManagerReset)));
        harmony.Patch(lightning, prefix: Handler(nameof(BeforeLightning)));
        harmony.Patch(engage, prefix: Handler(nameof(BeforeEngage)),
            postfix: Handler(nameof(AfterEngage)), finalizer: Handler(nameof(FinishEngageInvocation)));
        harmony.Patch(intent, prefix: Handler(nameof(BeforeIntent)));
        harmony.Patch(Required(typeof(EngageCmd), nameof(EngageCmd.PerformAll), typeof(PlayerChoiceContext), typeof(CardModel)),
            prefix: Handler(nameof(BeforeEngageGroup)), postfix: Handler(nameof(AfterEngageGroup)),
            finalizer: Handler(nameof(FinishEngageGroupInvocation)));
        harmony.Patch(Required(typeof(Creature), nameof(Creature.HealInternal), typeof(decimal)),
            prefix: Handler(nameof(BeforeHeal)), postfix: Handler(nameof(AfterHeal)));
        harmony.Patch(Required(typeof(PlayerCombatState), nameof(PlayerCombatState.GainEnergy), typeof(decimal)),
            prefix: Handler(nameof(BeforeEnergy)), postfix: Handler(nameof(AfterEnergy)));
        harmony.Patch(Required(typeof(CardCmd), nameof(CardCmd.Exhaust), typeof(PlayerChoiceContext), typeof(CardModel), typeof(bool), typeof(bool)),
            prefix: Handler(nameof(BeforeCardExhaust)));
        harmony.Patch(Required(typeof(CardModel), nameof(CardModel.SpendResources)), prefix: Handler(nameof(BeforeCardPayment)));
        CostPresentationReceipts.Committed += receipt => Dispatch("cost_committed", () => Owner(receipt.Owner)?.CostReduced(receipt));
        VolibearNativeAudio.Install();
        VolibearPresentationCues.Install();
        CombatManager.Instance.CombatSetUp += state => Dispatch("setup", () =>
        {
            CloseRoom();
            _historyState = state;
            _historyIndex = CombatManager.Instance.History.Entries.Count();
            EnsureRoom(state);
        });
        CombatManager.Instance.CombatEnded += _ => Dispatch("combat_end", CloseRoom);
        CombatManager.Instance.History.Changed += HistoryChanged;
        BeastForms.Converted += BeastConverted;
        PowerAudioReceipts.Install();
        CardPresentationReceipts.Committed += CardCommitted;
        GameplayPresentationReceipts.Committed += GameplayCommitted;
        InstallSemanticHooks();
        _historyState = CombatManager.Instance.DebugOnlyGetState();
        _historyIndex = CombatManager.Instance.History.Entries.Count();
        _installed = true;
        Dispatch("initial_attach", () => EnsureRoom(_historyState));
    }

    private static MethodInfo Required(Type type, string name, params Type[] arguments) =>
        AccessTools.Method(type, name, arguments) ?? throw new MissingMethodException(type.FullName, name);
    private static HarmonyMethod Handler(string name) => new(typeof(VolibearPresentationBridge), name);
    private static string Next(string kind) => $"{kind}:{Interlocked.Increment(ref _sequence)}";
    private static bool Valid(Node? node) => node is not null && GodotObject.IsInstanceValid(node)
        && node.IsInsideTree() && !node.IsQueuedForDeletion();
    private static bool Bear(Creature? creature) => creature?.Player?.Character is VolibearCharacter;
    private static string CreatureId(Creature creature) => creature.CombatId is { } id
        ? $"creature:{id}" : throw new InvalidOperationException("Presentation requires a native CombatId");
    private static string? CardId(CardModel card) => NetCombatCardDb.Instance.TryGetCardId(card, out var id)
        ? $"card:{id}" : null;

    private static void Warn(string label, Exception error)
    {
        // Presentation must not make a completed rules command fail. Diagnose once, not every frame.
        lock (Warned)
            if (Warned.Add(label)) GD.PushWarning($"[Volibear presentation:{label}] {error.GetType().Name}: {error.Message}");
    }
    private static void Safe(string label, Action action)
    {
        try { action(); }
        catch (Exception error) { Warn(label, error); }
    }
    private static void Dispatch(string label, Action action)
    {
        if (Environment.CurrentManagedThreadId == _mainThread) Safe(label, action);
        else if (Pending.Count < 1024) Pending.Enqueue(() => Safe(label, action));
    }
    private static void Observe<T>(Task<T> original, string label, Action<T> completed)
    {
        // The caller receives the EXACT original Task, including original fault/cancellation semantics.
        void Done()
        {
            if (original.IsCompletedSuccessfully)
            {
                var result = original.Result;
                Dispatch(label, () => completed(result));
            }
        }
        try
        {
            if (original.IsCompleted) Done();
            else original.GetAwaiter().OnCompleted(Done);
        }
        catch (Exception error) { Warn(label, error); }
    }

    private static void ReadMetadata()
    {
        if (_metadataLoaded) return;
        using var cardsFile = Godot.FileAccess.Open("res://VolibearArt/vfx/card_vfx_bindings.json", Godot.FileAccess.ModeFlags.Read)
            ?? throw new InvalidOperationException("Missing approved card presentation bindings");
        using var cards = JsonDocument.Parse(cardsFile.GetAsText());
        foreach (var row in cards.RootElement.GetProperty("cards").EnumerateArray())
        {
            string key = row.GetProperty("asset_key").GetString()!;
            Motions[key] = ReadMotion(row.GetProperty("primary_motion"));
            if (ReadContactEffect(row) is { } contact) ContactEffects[key] = contact;
        }
        using var voicesFile = Godot.FileAccess.Open("res://VolibearArt/audio/action_cues.json", Godot.FileAccess.ModeFlags.Read)
            ?? throw new InvalidOperationException("Missing approved action voice bindings");
        using var voices = JsonDocument.Parse(voicesFile.GetAsText());
        foreach (var row in voices.RootElement.GetProperty("clips").EnumerateArray())
        foreach (var cue in row.GetProperty("events").EnumerateArray())
        {
            var id = cue.GetProperty("cue").GetString()!;
            if (id.StartsWith("voice.", StringComparison.Ordinal) &&
                cue.GetProperty("reason").GetString() == "action-start cosmetic cue")
                StartVoices[row.GetProperty("clip").GetString()!] = id;
        }
        // Numeric/rules text and offline impact timestamps are deliberately NEVER read.
        _metadataLoaded = true;
    }
    private static string? ReadContactEffect(JsonElement row)
    {
        // Primary character motion and resolved contact are separate approved bindings.
        // Several heavy-motion cards deliberately retain a claw contact; a domain fallback
        // or later transformation must not reclassify an already-recorded native hit.
        var contacts = row.GetProperty("cues").EnumerateArray()
            .Where(cue => cue.GetProperty("event").GetString() == "physical_damage_resolved")
            .Select(cue => cue.GetProperty("effect_id").GetString()!).Distinct().ToArray();
        if (contacts.Length > 1 || contacts.Any(effect => effect is not
            ("claw_slash" or "heavy_impact" or "bite_hit" or "counter_release")))
            throw new InvalidOperationException("Invalid approved physical contact binding");
        return contacts.SingleOrDefault();
    }
    private static string ContactEffectFor(CardModel? card)
    {
        if (MotionKey(card) is { } key && ContactEffects.TryGetValue(key, out var effect)) return effect;
        return "claw_slash"; // Native/foreign ordinary attacks retain the default contact.
    }

    private static RoomScope? EnsureRoom(ICombatState? combat, NCombatRoom? readyRoom = null)
    {
        if (combat is null || !ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) ||
            (!CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsStarting) ||
            CombatManager.Instance.IsEnding) return null;
        var node = readyRoom ?? NCombatRoom.Instance;
        if (!Valid(node) || !Valid(node!.CombatVfxContainer)) return null;
        if (_room is not null && ReferenceEquals(_room.Combat, combat) && ReferenceEquals(_room.Room, node)) return _room;
        CloseRoom();
        ReadMetadata();
        _room = new RoomScope(node, combat, $"room:{node.GetInstanceId()}:combat:{++_epoch}");
        _room.DiscoverOwners();
        return _room;
    }
    private static OwnerScope? Owner(Creature creature) => Bear(creature)
        ? EnsureRoom(creature.CombatState)?.GetOwner(creature) : null;
    private static void CloseRoom()
    {
        var previous = _room;
        _room = null;
        previous?.Dispose();
        DamageContacts = new();
        while (Pending.TryDequeue(out _)) { }
    }
    private static void RoomReady(NCombatRoom __instance) => Dispatch("room_ready", () =>
        EnsureRoom(CombatManager.Instance.DebugOnlyGetState(), __instance));
    private static void ManagerReset() => Dispatch("reset", () =>
    {
        CloseRoom();
        _historyState = null;
        _historyIndex = 0;
        ActiveEngage.Value = null;
    });
    private static void BeforeLightning(Creature owner) => Dispatch("lightning_subscribe", () => Owner(owner)?.EnsureLightning());

    private static void HistoryChanged() => Dispatch("native_history", () =>
    {
        var state = CombatManager.Instance.DebugOnlyGetState();
        var entries = CombatManager.Instance.History.Entries;
        int count = entries.Count();
        if (!ReferenceEquals(state, _historyState)) { _historyState = state; _historyIndex = 0; }
        if (count < _historyIndex) _historyIndex = 0;
        int first = _historyIndex;
        var added = entries.Skip(first).ToArray();
        _historyIndex = count; // Commit cursor before callbacks; no duplicate on nested history events.
        if (EnsureRoom(state) is not { } room) return;
        for (int index = 0; index < added.Length; index++)
        {
            var entry = added[index];
            string id = $"history:{first + index}";
            Safe("native_" + entry.GetType().Name, () => RouteHistory(room, entry, id));
        }
    });

    private static void RouteHistory(RoomScope room, CombatHistoryEntry entry, string id)
    {
        if (!ReferenceEquals(room, _room)) return;
        switch (entry)
        {
            case CardPlayStartedEntry play:
                room.GetOwner(play.Actor)?.CardStarted(play.CardPlay, id);
                break;
            case CardPlayFinishedEntry finished:
                room.GetOwner(finished.Actor)?.CardFinished(finished.CardPlay);
                break;
            case DamageReceivedEntry damage:
                if (Bear(damage.Dealer))
                    DamageContacts.GetValue(damage.Result, _ => new DamageContact(ContactEffectFor(damage.CardSource)));
                room.GetOwner(damage.Receiver)?.Incoming(damage.Result, id);
                break;
            case CreatureAttackedEntry attack:
                if (room.GetOwner(attack.Actor) is { } attacker)
                {
                    for (int i = 0; i < attack.DamageResults.Count; i++)
                    {
                        var result = attack.DamageResults[i];
                        string effect = DamageContacts.TryGetValue(result, out var contact) ? contact.Effect : "claw_slash";
                        attacker.AtTarget(id + ":hit:" + i, effect, result.Receiver);
                    }
                }
                break;
            case BlockGainedEntry block when block.Amount > 0:
                room.GetOwner(block.Receiver)?.AtOwner(id, "guard_gain");
                room.GetOwner(block.Receiver)?.BlockMotion(block.CardPlay);
                break;
            case CardDrawnEntry draw:
                room.GetOwner(draw.Actor)?.AtCard(id, "card_draw", draw.Card);
                break;
            case CardDiscardedEntry discard:
                room.GetOwner(discard.Actor)?.AtCard(id, "card_discard", discard.Card);
                break;
            case CardExhaustedEntry exhaust:
                room.GetOwner(exhaust.Actor)?.AtCard(id, "card_exhaust", exhaust.Card);
                break;
        }
    }

    private static void BeforeCardExhaust(CardModel card) => Dispatch("capture_exhaust_anchor", () => Owner(card.Owner.Creature)?.RememberCard(card));
    private static void BeforeCardPayment(CardModel __instance) => Dispatch("capture_payment_anchor", () => Owner(__instance.Owner.Creature)?.RememberCard(__instance));

    private sealed record GainObservation(OwnerScope Scope, int Before);
    private static void BeforeHeal(Creature __instance, out GainObservation? __state)
    {
        __state = null;
        try { if (Owner(__instance) is { } scope) __state = new(scope, __instance.CurrentHp); }
        catch (Exception error) { Warn("heal_entry", error); }
    }
    private static void AfterHeal(Creature __instance, GainObservation? __state)
    {
        if (__state is not { } state || __instance.CurrentHp <= state.Before) return;
        Dispatch("native_heal_committed", () => state.Scope.AtOwner(Next("heal"), "heal"));
    }
    private static void BeforeEnergy(PlayerCombatState __instance, out GainObservation? __state)
    {
        __state = null;
        try
        {
            var player = _room?.Combat.Players.FirstOrDefault(p => ReferenceEquals(p.PlayerCombatState, __instance));
            if (player is not null && Owner(player.Creature) is { } scope) __state = new(scope, __instance.Energy);
        }
        catch (Exception error) { Warn("energy_entry", error); }
    }
    private static void AfterEnergy(PlayerCombatState __instance, GainObservation? __state)
    {
        if (__state is not { } state || __instance.Energy <= state.Before) return;
        Dispatch("native_energy_committed", () => state.Scope.AtOwner(Next("energy"), "energy_gain"));
    }

    private sealed class EngageObservation(EngageObservation? previous, ICombatState combat,
        Creature receiver, Creature enemy, string id, string voiceId)
    {
        internal readonly EngageObservation? Previous = previous;
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Receiver = receiver;
        internal readonly Creature Enemy = enemy;
        internal readonly string Id = id;
        internal readonly string VoiceId = voiceId;
        internal int IntentSeen;
        internal OwnerScope.PlayMotion? Motion;
        internal bool Grouped;
    }
    private static void BeforeEngage(Creature target, CardModel card, out EngageObservation? __state)
    {
        __state = null;
        try
        {
            var owner = card.Owner.Creature;
            if (!Bear(owner) || owner.CombatState is not { } state) return;
            string id = Next("engage");
            var group = ActiveEngageGroup.Value;
            bool grouped = ReferenceEquals(group?.Card, card);
            __state = new EngageObservation(ActiveEngage.Value, state, owner, target, id, grouped ? group!.Id : id)
            { Motion = Owner(owner)?.FindMotion(card), Grouped = grouped };
            ActiveEngage.Value = __state;
        }
        catch (Exception error) { Warn("engage_invocation", error); }
    }
    private static void BeforeIntent(NCreature __instance)
    {
        var invocation = ActiveEngage.Value;
        if (invocation is null || !ReferenceEquals(__instance.Entity, invocation.Enemy) ||
            Interlocked.Exchange(ref invocation.IntentSeen, 1) != 0) return;
        // EngageCmd reaches this native call only AFTER eligibility/reservation. No copied rules guard.
        Dispatch("engage_telegraph", () =>
        {
            if (ReferenceEquals(invocation.Receiver.CombatState, invocation.Combat))
            {
                Owner(invocation.Receiver)?.EngageTelegraph(invocation.VoiceId);
                Owner(invocation.Receiver)?.AtTarget(invocation.Id + ":roar", "roar_wave", invocation.Enemy);
            }
        });
    }
    private static void AfterEngage(Task<EngageCmd.Result> __result, EngageObservation? __state)
    {
        if (__state is null) return;
        ActiveEngage.Value = __state.Previous;
        var invocation = __state;
        Observe(__result, "engage_completion", result =>
        {
            if (!result.Performed || !result.Completed ||
                !ReferenceEquals(invocation.Receiver.CombatState, invocation.Combat)) return;
            var scope = Owner(invocation.Receiver);
            if (!invocation.Grouped) scope?.ForcedMotion(invocation.Motion);
            if (result.Absorbed > 0) scope?.AtOwner(invocation.Id + ":absorbed", "absorb");
        });
    }
    private static Exception? FinishEngageInvocation(Exception? __exception, EngageObservation? __state)
    {
        if (__state is not null && ReferenceEquals(ActiveEngage.Value, __state)) ActiveEngage.Value = __state.Previous;
        return __exception;
    }
    private static void CardCommitted(CommittedCardPresentation receipt) => Dispatch("card_semantic_receipt", () =>
    {
        if (_room is { } room && ReferenceEquals(receipt.Combat, room.Combat))
            Owner(receipt.Owner)?.CardAudio(receipt);
    });

    private static Task BeastConverted(PlayerChoiceContext _, BeastChange change)
    {
        Dispatch("beast_conversion", () =>
        {
            if (!ReferenceEquals(change.Card.CombatState, change.Combat)) return;
            Owner(change.Card.Owner.Creature)?.AtCard(Next("beast"),
                change.Shape == BeastShape.Claw ? "feral_claw" : "feral_body", change.Card);
        });
        return Task.CompletedTask;
    }

    private sealed class RoomScope : IDisposable
    {
        internal readonly NCombatRoom Room;
        internal readonly ICombatState Combat;
        internal readonly string Id;
        private readonly Dictionary<Creature, OwnerScope> _owners = new(ReferenceEqualityComparer.Instance);
        private readonly Godot.Timer _timer;
        private bool _disposed;
        internal RoomScope(NCombatRoom room, ICombatState combat, string id)
        {
            Room = room; Combat = combat; Id = id;
            _timer = new Godot.Timer { Name = "VolibearPresentationLease", WaitTime = 0.2, OneShot = false };
            _timer.Timeout += Tick;
            Room.TreeExiting += RoomExiting;
            Room.AddChild(_timer);
            _timer.Start();
        }
        internal NCreature? NodeFor(Creature creature) =>
            Room.CreatureNodes.Concat(Room.RemovingCreatureNodes)
                .FirstOrDefault(node => Valid(node) && ReferenceEquals(node.Entity, creature) && Valid(node.Visuals));
        internal OwnerScope? GetOwner(Creature creature)
        {
            if (_disposed || !Bear(creature) || !ReferenceEquals(creature.CombatState, Combat)) return null;
            if (_owners.TryGetValue(creature, out var existing)) return existing;
            if (!creature.IsAlive || creature.CombatId is null || NodeFor(creature) is not { } node) return null;
            var owner = new OwnerScope(this, creature, node);
            _owners.Add(creature, owner);
            owner.Initialize();
            return owner;
        }
        internal void DiscoverOwners()
        {
            foreach (var creature in Combat.PlayerCreatures) GetOwner(creature);
        }
        private void Tick() => Safe("lease_tick", () =>
        {
            for (int i = 0; i < 128 && Pending.TryDequeue(out var action); i++) action();
            if (_disposed) return;
            if (!Valid(Room) || !ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(), Combat))
            { RoomExiting(); return; }
            if (CombatManager.Instance.IsStarting) { DiscoverOwners(); return; }
            if (!CombatManager.Instance.IsInProgress)
            {
                foreach (var owner in _owners.Values) owner.StopCombat();
                return;
            }
            if (CombatManager.Instance.IsEnding)
            {
                foreach (var owner in _owners.Values) owner.SuspendEnding();
                return;
            }
            DiscoverOwners();
            foreach (var owner in _owners.Values.ToArray()) owner.Tick();
        });
        private void RoomExiting()
        {
            if (ReferenceEquals(_room, this)) CloseRoom();
            else Dispose();
        }
        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            foreach (var owner in _owners.Values) owner.Dispose();
            _owners.Clear();
            if (GodotObject.IsInstanceValid(Room)) Room.TreeExiting -= RoomExiting;
            if (GodotObject.IsInstanceValid(_timer))
            {
                _timer.Timeout -= Tick;
                _timer.Stop();
                _timer.QueueFree();
            }
        }
    }

    private sealed partial class OwnerScope : IDisposable
    {
        private readonly RoomScope _room;
        private readonly Creature _owner;
        private NCreature _node;
        private readonly VolibearEffects _effects;
        private IDisposable? _lightning;
        private bool _disposed;
        private bool _dead;
        private bool _combatStopped;
        private bool _domain;
        private bool _lowHealth;
        private sealed record CapturedCard(Vector2 Center, Vector2? Cost, ulong View, ulong At);
        private readonly Dictionary<CardModel,CapturedCard> _cardAnchors = new(ReferenceEqualityComparer.Instance);
        private readonly List<(Node2D Node,ulong Expires)> _capturedMarkers = [];
        private bool _domainEligible = true;
        private int _voiceCounter;
        private readonly string _domainKey;
        internal OwnerScope(RoomScope room, Creature owner, NCreature node)
        {
            _room = room; _owner = owner; _node = node;
            string ownerId = $"player:{owner.Player!.NetId}:{CreatureId(owner)}";
            _domainKey = ownerId + ":domain";
            _effects = VolibearEffects.Attach(room.Room.CombatVfxContainer, room.Id, ownerId);
        }
        internal void Initialize()
        {
            _owner.PowerApplied += PowerApplied;
            _owner.PowerIncreased += PowerIncreased;
            _owner.PowerDecreased += PowerDecreased;
            _owner.PowerRemoved += PowerRemoved;
            _owner.Died += Died;
            _owner.Revived += Revived;
            _owner.CurrentHpChanged += HealthChanged;
            _owner.MaxHpChanged += HealthChanged;
            SubscribeLightning();
            UpdateDomain(announce: false);
            UpdateLowHealth(announce: false);
        }
        private bool Live => !_disposed && !_combatStopped && !_dead && _owner.IsAlive &&
            CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding &&
            ReferenceEquals(_room, VolibearPresentationBridge._room) &&
            ReferenceEquals(_owner.CombatState, _room.Combat) && Valid(_node) && Valid(_node.Visuals);
        private bool OwnsLocalHud()
        {
            // The combat UI belongs to this client's player, not every creature in the room.
            return _owner.Player is { } player && ReferenceEquals(LocalContext.GetMe(_room.Combat), player);
        }
        private EffectAnchors Anchors(NCreature? target = null, CanvasItem? card = null)
        {
            return new(_node.Visuals, Target: target?.Visuals, Source: _node.Visuals.VfxSpawnPosition,
                Card: card, Energy: OwnsLocalHud() ? _room.Room.Ui.EnergyCounterContainer : _node.Visuals.VfxSpawnPosition,
                OwnerMouth: _node.Visuals.TalkPosition, OwnerHand: _node.Visuals.VfxSpawnPosition);
        }
        private bool TryCardAnchors(CanvasItem card, PileType? from, bool toDiscard, out EffectAnchors anchors)
        {
            anchors = Anchors(card: card);
            // Remote visible cards still have real view anchors, but their private piles have
            // no corresponding UI here. Keep the sound instead of borrowing this client's piles.
            if ((from is not null || toDiscard) && !OwnsLocalHud()) return false;
            if (from is not null)
            {
                CanvasItem? source = from switch
                {
                    PileType.Draw => _room.Room.Ui.DrawPile,
                    PileType.Discard => _room.Room.Ui.DiscardPile,
                    _ => null
                };
                if (!Valid(source)) return false;
                anchors = anchors with { Source = source };
            }
            if (toDiscard)
            {
                if (!Valid(_room.Room.Ui.DiscardPile)) return false;
                anchors = anchors with { Target = _room.Room.Ui.DiscardPile };
            }
            return true;
        }
        internal void EnsureLightning() => SubscribeLightning();
        private void SubscribeLightning()
        {
            // The core reset handler may run after our setup observer. Renew only a CLOSED
            // subscription; replacing an active one could drop an outer reentrant batch receipt.
            if (_lightning is LightningBatches.Subscription { Active: false }) _lightning = null;
            if (_lightning is null && _owner.IsAlive && LightningBatches.CanUse(_owner, out _))
                _lightning = LightningBatches.Subscribe(_owner, (_, batch) =>
                {
                    Dispatch("lightning_receipt", () => Lightning(batch));
                    return Task.CompletedTask;
                });
        }
        private void Lightning(LightningBatch batch)
        {
            if (!Live || !ReferenceEquals(batch.Combat, _room.Combat) || !ReferenceEquals(batch.Owner, _owner)) return;
            var actual = batch.Results.Select(hit => hit.Receiver).Distinct(ReferenceEqualityComparer.Instance).Cast<Creature>().ToArray();
            string effect = actual.Length > 1 ? "lightning_all" : "lightning_strike";
            string id = $"lightning:{batch.Id}";
            foreach (var target in actual) AtTarget(id, effect, target);
            // If all actual receivers' nodes have already gone, still emit exactly one batch sound.
            _effects.PlaySound(id, "sfx." + effect);
        }
        internal void AtOwner(string id, string effect)
        {
            if (!Live) return;
            if (!_effects.Emit(id, effect, Anchors()) && effect == "energy_gain")
                _effects.PlaySound(id, "sfx.energy_gain");
        }
        internal void AtTarget(string id, string effect, Creature target)
        {
            if (!Live || target.CombatId is null || _room.NodeFor(target) is not { } node) return;
            _effects.Emit(id, effect, Anchors(node), CreatureId(target));
        }
        internal void AtCard(string id, string effect, CardModel card)
        {
            if (!Live || !ReferenceEquals(card.Owner.Creature, _owner)) return;
            // Exhaust/replay can remove the original view before native history is published.
            // Reuse a measured same-card anchor; never invent a hidden card position.
            var node = CardAnchor(card);
            var cardId = CardId(card);
            if (Valid(node) && cardId is not null && TryCardAnchors(node!,
                    effect == "card_draw" ? PileType.Draw : null, effect == "card_discard", out var anchors))
                _effects.Emit(id, effect, anchors, cardId);
            // Missing remote/hidden cards never cause fake card nodes or guessed screen positions.
            _effects.PlaySound(id, "sfx." + effect);
        }
        private void Pose(string clip)
        {
            StopMotionVisual();
            if (Valid(_node) && Valid(_node.Visuals)) VolibearPresentation.Play(_node.Visuals, clip);
        }
        internal void CardStarted(CardPlay play, string id)
        {
            if (!Live) return;
            if (play.PlayIndex > 0)
            {
                AtCard(id, "card_replay", play.Card);
                return; // Repeated effects retain the original paid play's primary motion.
            }
            BeginMotion(play, id);
            if (MotionKey(play.Card) == "u23") AtOwner(id + ":roar", "roar_wave");
        }
        internal void Incoming(DamageResult result, string id)
        {
            if (!Live) return;
            if (result.BlockedDamage > 0) AtOwner(id, "guard_hit");
            if (result.UnblockedDamage > 0)
            {
                Pose(_domain ? "domain_hurt" : "hurt");
                _effects.PlaySound(id, ++_voiceCounter % 2 == 0 ? "voice.hurt_02" : "voice.hurt_01");
            }
        }
        internal void EngageTelegraph(string id)
        {
            if (!Live) return;
            Pose(_domain ? "domain_block" : "block");
            // Only the accepted native intent reaches here. One PerformAll invocation shares
            // its voice event across enemies, so both audio profiles announce the challenge once.
            _effects.PlaySound(id + ":challenge", "voice.roar");
        }
        internal void RememberCard(CardModel card)
        {
            if (!Live || !ReferenceEquals(card.Owner.Creature,_owner)) return;
            var view=NCard.FindOnTable(card)??FindVisibleCard(_room.Room,card);
            if (!Valid(view) || !view!.IsVisibleInTree()) return;
            var cost=view.GetNodeOrNull<Control>("%EnergyLabel");
            Vector2? costPoint=Valid(cost)&&cost!.IsVisibleInTree()?cost.GetGlobalTransformWithCanvas()*(cost.Size*0.5f):null;
            _cardAnchors[card]=new(view.GetGlobalTransformWithCanvas()*(view.Size*0.5f),costPoint,view.GetInstanceId(),Time.GetTicksMsec());
            if (_cardAnchors.Count>128) _cardAnchors.Remove(_cardAnchors.MinBy(pair=>pair.Value.At).Key);
        }
        private CanvasItem? CardAnchor(CardModel card,bool cost=false)
        {
            var view=NCard.FindOnTable(card)??FindVisibleCard(_room.Room,card);
            if (Valid(view)&&view!.IsVisibleInTree())
            {
                RememberCard(card);
                if (!cost) return view;
                var label=view.GetNodeOrNull<Control>("%EnergyLabel");
                if(Valid(label)&&label!.IsVisibleInTree())return label;
            }
            if (!_cardAnchors.TryGetValue(card,out var captured)||Time.GetTicksMsec()-captured.At>10000 || (cost&&captured.Cost is null))return null;
            // A measured old native view coordinate, not a fabricated card or guessed location.
            // This owner scope is tied to one room/epoch and is discarded on death/end/exit.
            var marker=new Node2D {Name=$"CapturedCardAnchor_{captured.View}"};
            var container=_room.Room.CombatVfxContainer;
            container.AddChild(marker);
            marker.Position=container.GetGlobalTransformWithCanvas().AffineInverse()*(cost?captured.Cost!.Value:captured.Center);
            _capturedMarkers.Add((marker,Time.GetTicksMsec()+3000)); // Cosmetic anchor lifetime only; never a settlement timer.
            return marker;
        }
        internal void CostReduced(CommittedCostPresentation receipt)
        {
            if (!Live||!ReferenceEquals(receipt.Owner,_owner)||!ReferenceEquals(receipt.Combat,_room.Combat))return;
            string id=$"cost_receipt:{receipt.Id}";
            if (CardAnchor(receipt.Card,cost:true) is { } cost && CardId(receipt.Card) is { } cardId)
                _effects.Emit(id,"cost_reduce",Anchors() with {CardCost=cost},cardId);
            _effects.PlaySound(id,"sfx.cost_reduce");
        }
        internal void CardAudio(CommittedCardPresentation receipt)
        {
            if (!Live || !ReferenceEquals(receipt.Combat, _room.Combat) || !ReferenceEquals(receipt.Owner, _owner)) return;
            string id = $"card_receipt:{receipt.Id}";
            var node = CardAnchor(receipt.Card);
            if (Valid(node) && CardId(receipt.Card) is { } cardId && TryCardAnchors(node!,
                    receipt.Effect == "card_retrieve" ? receipt.From : null, false, out var anchors))
                _effects.Emit(id, receipt.Effect, anchors, cardId);
            // Hidden/removed native cards have no invented card or guessed screen position.
            _effects.PlaySound(id, "sfx." + receipt.Effect);
        }
        private static NCard? FindVisibleCard(Node root, CardModel model)
        {
            foreach (var child in root.GetChildren())
            {
                if (child is NCard card && Valid(card) && card.IsVisibleInTree() && ReferenceEquals(card.Model, model)) return card;
                if (FindVisibleCard(child, model) is { } found) return found;
            }
            return null;
        }
        private void PowerAudio(PowerAudioReceipt? receipt)
        {
            if (receipt is not null && Live && ReferenceEquals(receipt.Combat, _room.Combat) && ReferenceEquals(receipt.Owner, _owner))
            {
                string id = $"power_transaction:{receipt.Transaction}";
                // A pending cost coupon has no committed target card yet: never decorate its source card as if discounted.
                if (receipt.Cue != "cost_reduce") AtOwner(id, receipt.Cue);
                _effects.PlaySound(id, "sfx." + receipt.Cue);
            }
        }
        private void PowerApplied(PowerModel power)
        {
            var receipt = PowerAudioReceipts.Applied(power); // Capture synchronously, before Dispatch.
            Dispatch("power_applied", () =>
            {
                PowerAudio(receipt);
                if (power is DomainPower) { _domainEligible = true; UpdateDomain(); }
                else if (power is StormChargePower && power.Amount > 0) AtOwner(Next("force"), "lightning_growth");
            });
        }
        private void PowerIncreased(PowerModel power, int amount, bool silent)
        {
            var receipt = PowerAudioReceipts.Increased(power, amount, silent);
            Dispatch("power_increased", () =>
            {
                PowerAudio(receipt);
                if (power is DomainPower) { _domainEligible = true; UpdateDomain(announce: !silent); }
                else if (power is StormChargePower && amount > 0 && !silent && _owner.Powers.Contains(power))
                    AtOwner(Next("force"), "lightning_growth");
            });
        }
        private void PowerDecreased(PowerModel power, bool silent) => Dispatch("power_decreased", () =>
        {
            if (power is DomainPower) UpdateDomain(announce: !silent);
        });
        private void PowerRemoved(PowerModel power) => Dispatch("power_removed", () =>
        {
            if (power is DomainPower) UpdateDomain();
        });
        private void HealthChanged(int before, int after) => Dispatch("native_health_pose", () => UpdateLowHealth());
        private void UpdateLowHealth(bool announce = true)
        {
            if (!Live || _owner.MaxHp <= 0) return;
            double ratio = (double)_owner.CurrentHp / _owner.MaxHp;
            // Approved animation state_rules: visual hysteresis only, never a gameplay debuff.
            bool low = _lowHealth ? ratio < 0.35 : ratio <= 0.30;
            if (low == _lowHealth) { RefreshIdle(); return; }
            _lowHealth = low;
            RefreshIdle();
            if (low && announce) _effects.PlaySound(Next("low_health"), "voice.low_health");
        }
        private void RefreshIdle()
        {
            if (!Live) return;
            string clip = _domain ? (_lowHealth ? "domain_weak_loop" : "domain_idle") : (_lowHealth ? "weak_loop" : "idle_loop");
            VolibearPresentation.SetIdle(_node.Visuals, clip);
            var sprite = _node.Visuals.GetNode<AnimatedSprite2D>("Visuals/AnimatedSprite2D");
            string current = sprite.Animation.ToString();
            if (_motionSprite is not null && !_lowHealth) return;
            if (current != clip && current is "idle_loop" or "relaxed_loop" or "weak_loop" or "domain_idle" or "domain_weak_loop")
                sprite.Play(clip);
        }
        private void UpdateDomain(bool announce = true)
        {
            bool active = Live && _domainEligible && DomainPower.IsActive(_owner);
            if (active == _domain) return;
            _domain = active;
            UpdateSpiritForm(active);
            if (active) TickSpiritForm();
            if (active)
            {
                string id = Next("domain_enter");
                if (announce) AtOwner(id, "domain_enter");
                _effects.Emit(id + ":loop", "domain_loop", Anchors(), persistentKey: _domainKey, leaseSeconds: 2f);
                RefreshIdle();
                if (announce)
                {
                    if (DomainEntryMotion()) _effects.PlaySound(id, "voice.roar");
                }
            }
            else
            {
                _effects.StopLoop(_domainKey);
                if (Live)
                {
                    RefreshIdle();
                    if (announce)
                    {
                        AtOwner(Next("domain_exit"), "domain_exit");
                        Pose("domain_exit");
                    }
                }
            }
        }
        private void ReleaseCapturedAnchors(bool all = false)
        {
            ulong now = Time.GetTicksMsec();
            for (int i = _capturedMarkers.Count - 1; i >= 0; i--)
            {
                var marker = _capturedMarkers[i];
                if (!all && Valid(marker.Node) && marker.Expires > now) continue;
                if (Valid(marker.Node)) marker.Node.QueueFree();
                _capturedMarkers.RemoveAt(i);
            }
            if (all) _cardAnchors.Clear();
            else foreach (var card in _cardAnchors.Where(pair => now - pair.Value.At > 10000).Select(pair => pair.Key).ToArray())
                _cardAnchors.Remove(card);
        }
        internal void Tick()
        {
            if (_disposed || _combatStopped) return;
            ReleaseCapturedAnchors();
            if (!Valid(_node) && _room.NodeFor(_owner) is { } rebound) _node = rebound;
            if (!_owner.IsAlive) { if (!_dead) Died(_owner); return; }
            if (!Live) return;
            TickSemanticVisuals();
            SubscribeLightning();
            UpdateDomain(announce: false);
            TickSpiritForm();
            // Setup can create this scope while IsStarting, before Live admits a snapshot.
            // Reconcile starting/restored low HP silently once the battle is playable.
            UpdateLowHealth(announce: false);
            if (_domain && !_effects.RenewLoop(_domainKey, 2f))
                _effects.Emit(Next("domain_lease"), "domain_loop", Anchors(), persistentKey: _domainKey, leaseSeconds: 2f);
        }
        private void Died(Creature _) => Dispatch("owner_death", () =>
        {
            if (_disposed || _dead) return;
            _dead = true;
            StopSemanticVisuals(false);
            ClearMotions();
            _domainEligible = false;
            bool domain = _domain;
            _domain = false;
            ReleaseSpiritForm();
            _lightning?.Dispose();
            _lightning = null;
            _effects.StopAll();
            ReleaseCapturedAnchors(all: true);
            Pose(domain ? "domain_die" : "die");
            _effects.PlaySound(Next("death"), "voice.death", leaseSeconds: 3f);
        });
        private void Revived(Creature _) => Dispatch("owner_revive", () =>
        {
            if (_disposed || _combatStopped) return;
            _dead = false;
            _domainEligible = false; // A fresh Domain rule event, not revival itself, must reopen it.
            if (_room.NodeFor(_owner) is { } node) _node = node;
            if (Valid(_node))
            {
                VolibearPresentation.SetIdle(_node.Visuals, "idle_loop");
                Pose("idle_loop");
            }
            SubscribeLightning();
            UpdateLowHealth(announce: false);
            RefreshIdle();
        });
        internal void SuspendEnding()
        {
            StopSemanticVisuals(false);
            ClearMotions();
            _domain = false;
            ReleaseSpiritForm();
            _effects.StopAll();
            ReleaseCapturedAnchors(all: true);
        }
        internal void StopCombat()
        {
            if (_combatStopped) return;
            _combatStopped = true;
            StopSemanticVisuals(true);
            ClearMotions();
            _domain = false;
            ReleaseSpiritForm();
            _lightning?.Dispose();
            _lightning = null;
            _effects.StopAll();
            ReleaseCapturedAnchors(all: true);
        }
        public void Dispose()
        {
            if (_disposed) return;
            StopCombat();
            _disposed = true;
            _owner.PowerApplied -= PowerApplied;
            _owner.PowerIncreased -= PowerIncreased;
            _owner.PowerDecreased -= PowerDecreased;
            _owner.PowerRemoved -= PowerRemoved;
            _owner.Died -= Died;
            _owner.Revived -= Revived;
            _owner.CurrentHpChanged -= HealthChanged;
            _owner.MaxHpChanged -= HealthChanged;
            _effects.Dispose();
        }
    }
}
