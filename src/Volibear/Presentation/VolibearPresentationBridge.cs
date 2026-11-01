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
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
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
public static class VolibearPresentationBridge
{
    private const string HarmonyId = "Volibear.Presentation.SemanticBridge";
    private sealed record Motion(string Clip, string? DomainClip);
    private sealed record DamageMotion(string Clip);
    private static readonly Dictionary<string, Motion> Motions = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, string> StartVoices = new(StringComparer.Ordinal);
    private static readonly ConcurrentQueue<Action> Pending = new();
    private static readonly HashSet<string> Warned = [];
    private static ConditionalWeakTable<DamageResult, DamageMotion> DamageMotions = new();
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
            ["native.owner_died"] = "stop owned playback, death voice/pose"
        };

    public static void Install()
    {
        if (_installed) return;
        _mainThread = Environment.CurrentManagedThreadId;
        // Resolve every boundary first. No private OnPlay/MoveNext/settlement hook is patched.
        var ready = Required(typeof(NCombatRoom), nameof(NCombatRoom._Ready));
        var reset = Required(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool));
        var lightning = Required(typeof(LightningCmd), nameof(LightningCmd.Deal),
            typeof(PlayerChoiceContext), typeof(Creature), typeof(IEnumerable<Creature>), typeof(decimal), typeof(CardModel));
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
            var motion = row.GetProperty("primary_motion");
            Motions[row.GetProperty("asset_key").GetString()!] = new Motion(
                motion.GetProperty("clip").GetString()!,
                motion.TryGetProperty("domain_variant", out var domain) ? domain.GetString() : null);
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
    private static string MotionFor(CardModel? card, Creature owner)
    {
        if (card is VolibearCard bearCard && Motions.TryGetValue(bearCard.Key, out var motion))
            return DomainPower.IsActive(owner) && motion.DomainClip is not null ? motion.DomainClip : motion.Clip;
        return "attack";
    }
    private static string ContactEffect(string clip) => clip switch
    {
        "bite" => "bite_hit",
        "attack_heavy" or "storm_leap" or "domain_storm_leap" => "heavy_impact",
        _ => "claw_slash"
    };

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
        DamageMotions = new();
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
            case DamageReceivedEntry damage:
                if (Bear(damage.Dealer))
                    DamageMotions.GetValue(damage.Result, _ => new DamageMotion(MotionFor(damage.CardSource, damage.Dealer!)));
                room.GetOwner(damage.Receiver)?.Incoming(damage.Result, id);
                break;
            case CreatureAttackedEntry attack:
                if (room.GetOwner(attack.Actor) is { } attacker)
                {
                    for (int i = 0; i < attack.DamageResults.Count; i++)
                    {
                        var result = attack.DamageResults[i];
                        string clip = DamageMotions.TryGetValue(result, out var motion) ? motion.Clip : "attack";
                        attacker.AtTarget(id + ":hit:" + i, ContactEffect(clip), result.Receiver);
                    }
                }
                break;
            case BlockGainedEntry block when block.Amount > 0:
                room.GetOwner(block.Receiver)?.AtOwner(id, "guard_gain");
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

    private sealed class EngageObservation(EngageObservation? previous, ICombatState combat,
        Creature receiver, Creature enemy, string id)
    {
        internal readonly EngageObservation? Previous = previous;
        internal readonly ICombatState Combat = combat;
        internal readonly Creature Receiver = receiver;
        internal readonly Creature Enemy = enemy;
        internal readonly string Id = id;
        internal int IntentSeen;
    }
    private static void BeforeEngage(Creature target, CardModel card, out EngageObservation? __state)
    {
        __state = null;
        try
        {
            var owner = card.Owner.Creature;
            if (!Bear(owner) || owner.CombatState is not { } state) return;
            __state = new EngageObservation(ActiveEngage.Value, state, owner, target, Next("engage"));
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
                Owner(invocation.Receiver)?.EngageTelegraph();
        });
    }
    private static void AfterEngage(Task<EngageCmd.Result> __result, EngageObservation? __state)
    {
        if (__state is null) return;
        ActiveEngage.Value = __state.Previous;
        var invocation = __state;
        Observe(__result, "engage_completion", result =>
        {
            if (!result.Performed || !result.Completed || result.Absorbed <= 0 ||
                !ReferenceEquals(invocation.Receiver.CombatState, invocation.Combat)) return;
            Owner(invocation.Receiver)?.AtOwner(invocation.Id + ":absorbed", "absorb");
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

    private sealed class OwnerScope : IDisposable
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
            SubscribeLightning();
            UpdateDomain(announce: false);
        }
        private bool Live => !_disposed && !_combatStopped && !_dead && _owner.IsAlive &&
            CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding &&
            ReferenceEquals(_room, VolibearPresentationBridge._room) &&
            ReferenceEquals(_owner.CombatState, _room.Combat) && Valid(_node) && Valid(_node.Visuals);
        private EffectAnchors Anchors(NCreature? target = null, NCard? card = null) =>
            new(_node.Visuals, Target: target?.Visuals, Source: _node.Visuals.VfxSpawnPosition,
                Card: card, Energy: _room.Room.Ui.EnergyCounterContainer,
                OwnerMouth: _node.Visuals.TalkPosition);
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
            if (Live) _effects.Emit(id, effect, Anchors());
        }
        internal void AtTarget(string id, string effect, Creature target)
        {
            if (!Live || target.CombatId is null || _room.NodeFor(target) is not { } node) return;
            _effects.Emit(id, effect, Anchors(node), CreatureId(target));
        }
        internal void AtCard(string id, string effect, CardModel card)
        {
            if (!Live || !ReferenceEquals(card.Owner.Creature, _owner)) return;
            var node = NCard.FindOnTable(card);
            var cardId = CardId(card);
            if (Valid(node) && cardId is not null)
            {
                var anchors = Anchors(card: node);
                if (effect == "card_draw") anchors = anchors with { Source = _room.Room.Ui.DrawPile };
                if (effect == "card_discard") anchors = anchors with { Target = _room.Room.Ui.DiscardPile };
                _effects.Emit(id, effect, anchors, cardId);
            }
            // Missing remote/hidden cards never cause fake card nodes or guessed screen positions.
            _effects.PlaySound(id, "sfx." + effect);
        }
        private void Pose(string clip)
        {
            if (Valid(_node) && Valid(_node.Visuals)) VolibearPresentation.Play(_node.Visuals, clip);
        }
        internal void CardStarted(CardPlay play, string id)
        {
            if (!Live) return;
            if (play.PlayIndex > 0) { AtCard(id, "card_replay", play.Card); return; }
            // Other characters' cards do not acquire Volibear pose bindings by string resemblance.
            if (play.Card is not VolibearCard) return;
            string clip = MotionFor(play.Card, _owner);
            Pose(clip);
            if (StartVoices.TryGetValue(clip, out var cue))
            {
                if (cue == "voice.attack_01" && ++_voiceCounter % 2 == 0) cue = "voice.attack_02";
                _effects.PlaySound(id, cue);
            }
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
        internal void EngageTelegraph()
        {
            if (Live) Pose(_domain ? "domain_block" : "block");
        }
        internal void CardAudio(CommittedCardPresentation receipt)
        {
            if (Live && ReferenceEquals(receipt.Combat, _room.Combat) && ReferenceEquals(receipt.Owner, _owner))
                _effects.PlaySound($"card_receipt:{receipt.Id}", "sfx." + receipt.Effect);
        }
        private void PowerAudio(PowerAudioReceipt? receipt)
        {
            if (receipt is not null && Live && ReferenceEquals(receipt.Combat, _room.Combat) && ReferenceEquals(receipt.Owner, _owner))
                _effects.PlaySound($"power_transaction:{receipt.Transaction}", "sfx." + receipt.Cue);
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
        private void UpdateDomain(bool announce = true)
        {
            bool active = Live && _domainEligible && DomainPower.IsActive(_owner);
            if (active == _domain) return;
            _domain = active;
            if (active)
            {
                string id = Next("domain_enter");
                if (announce) AtOwner(id, "domain_enter");
                _effects.Emit(id + ":loop", "domain_loop", Anchors(), persistentKey: _domainKey, leaseSeconds: 2f);
                VolibearPresentation.SetIdle(_node.Visuals, "domain_idle");
                if (announce)
                {
                    Pose("domain_enter");
                    _effects.PlaySound(id, "voice.roar");
                }
            }
            else
            {
                _effects.StopLoop(_domainKey);
                if (Live)
                {
                    VolibearPresentation.SetIdle(_node.Visuals, "idle_loop");
                    if (announce)
                    {
                        AtOwner(Next("domain_exit"), "domain_exit");
                        Pose("domain_exit");
                    }
                }
            }
        }
        internal void Tick()
        {
            if (_disposed || _combatStopped) return;
            if (!Valid(_node) && _room.NodeFor(_owner) is { } rebound) _node = rebound;
            if (!_owner.IsAlive) { if (!_dead) Died(_owner); return; }
            if (!Live) return;
            SubscribeLightning();
            UpdateDomain(announce: false);
            if (_domain && !_effects.RenewLoop(_domainKey, 2f))
                _effects.Emit(Next("domain_lease"), "domain_loop", Anchors(), persistentKey: _domainKey, leaseSeconds: 2f);
        }
        private void Died(Creature _) => Dispatch("owner_death", () =>
        {
            if (_disposed || _dead) return;
            _dead = true;
            _domainEligible = false;
            bool domain = _domain;
            _domain = false;
            _lightning?.Dispose();
            _lightning = null;
            _effects.StopAll();
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
        });
        internal void SuspendEnding()
        {
            _domain = false;
            _effects.StopAll();
        }
        internal void StopCombat()
        {
            if (_combatStopped) return;
            _combatStopped = true;
            _domain = false;
            _lightning?.Dispose();
            _lightning = null;
            _effects.StopAll();
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
            _effects.Dispose();
        }
    }
}
