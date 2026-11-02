using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Managers;
using MegaCrit.Sts2.Core.Saves.Runs;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>
/// Finite, real two-process ENet acceptance. Shared files are test readiness barriers
/// only: cards, actions, choices, native checksums and the saved-run join payload use
/// native networking. Never installed in ordinary play; never writes save contents.
/// </summary>
internal static class MultiplayerAcceptanceProbe
{
    private static bool installed;
    private static NativeMultiplayerSession session = null!;
    private static string token = "", pair = "", role = "", control = "", root = "";
    private static readonly List<string> completed = [];
    private static readonly List<object> actions = [];
    private static readonly List<string> submitted = [];
    private static EventInfo? actionEvent;
    private static object? actionExecutor;
    private static Exception? actionError;
    private static readonly Action<GameAction> ActionObserver = ObserveAction;
    private static string Env(string name) => Environment.GetEnvironmentVariable(name)
        ?? throw new InvalidOperationException("Missing " + name);
    private static void Need(bool ok, string reason) { if (!ok) throw new InvalidOperationException(reason); }
    private static JsonElement Freeze(object value) => JsonSerializer.SerializeToElement(value);
    private static void Emit(string name, object value) => GD.Print("[Volibear] MULTIPLAYER_" + name + " " + JsonSerializer.Serialize(value));
    internal static void Install() { if (!installed) { installed = true; _ = Run(); } }

    private static async Task Barrier(string stage)
    {
        string own = Path.Combine(control, stage + "." + role + ".json");
        string peer = Path.Combine(control, stage + "." + (role == "host" ? "client" : "host") + ".json");
        Need(!File.Exists(own), "Duplicate readiness barrier: " + stage);
        string temporary = own + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(new { schema = 1, pair, stage, role, pid = Environment.ProcessId }));
        File.Move(temporary, own);
        await session.Until(() => File.Exists(peer), "peer readiness: " + stage);
        using var document = JsonDocument.Parse(File.ReadAllText(peer));
        var other = document.RootElement;
        Need(other.GetProperty("schema").GetInt32() == 1 && other.GetProperty("pair").GetString() == pair
            && other.GetProperty("stage").GetString() == stage && other.GetProperty("role").GetString() != role
            && other.GetProperty("pid").GetInt32() > 0 && other.GetProperty("pid").GetInt32() != Environment.ProcessId,
            "Invalid peer readiness identity");
    }

    private static CombatState State => CombatManager.Instance.DebugOnlyGetState()
        ?? throw new InvalidOperationException("Native combat missing");
    private static Player Local => State.Players.Single(p => p.NetId == session.NetId);
    private static Player[] Players => State.Players.OrderBy(p => p.NetId).ToArray();
    private static bool Quiet() => CombatManager.Instance.DebugOnlyGetState() is { } state
        && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding
        && state.CurrentSide == CombatSide.Player && state.Players.Count == 2
        && state.Players.All(p => p.PlayerCombatState?.Phase == PlayerTurnPhase.Play)
        && !RunManager.Instance.ActionExecutor.IsPaused && RunManager.Instance.ActionQueueSet.IsEmpty
        && RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null
        && state.Enemies.All(e => e.Monster is { IsPerformingMove: false });
    private static Task Settle(string stage) => session.Until(() =>
    {
        if (actionError is not null) throw actionError;
        return Quiet();
    }, stage);

    private static object Card(CardModel card, bool combat) => new
    {
        id = card.Id.Entry, nativeType = card.GetType().Name, upgrade = card.CurrentUpgradeLevel,
        index = combat ? (uint?)NetCombatCard.FromModel(card).CombatCardIndex : null,
        owner = card.Owner.NetId, pile = card.Pile?.Type.ToString(), type = card.Type.ToString(),
        cost = card.EnergyCost.GetWithModifiers(CostModifiers.Local),
        keywords = card.Keywords.Select(k => k.ToString()).OrderBy(k => k, StringComparer.Ordinal).ToArray(),
        masterIndex = card.Owner.Deck.Cards.ToList().IndexOf(card.DeckVersion ?? card)
    };
    private static object Powers(Creature creature) => creature.Powers
        .Select(p => new { id = p.Id.Entry, amount = p.Amount }).OrderBy(p => p.id, StringComparer.Ordinal).ToArray();
    private static JsonElement Snapshot() => Freeze(new
    {
        encounter = State.Encounter!.Id.Entry, round = State.RoundNumber, side = State.CurrentSide.ToString(),
        players = Players.Select(player => new
        {
            netId = player.NetId, character = player.Character.Id.Entry, hp = player.Creature.CurrentHp,
            maxHp = player.Creature.MaxHp, block = player.Creature.Block, gold = player.Gold,
            turn = player.PlayerCombatState!.TurnNumber, energy = player.PlayerCombatState.Energy,
            lightning = LightningBatches.GetTurnCount(player.Creature), powers = Powers(player.Creature),
            deck = player.Deck.Cards.Select(c => Card(c, false)).ToArray(),
            relics = player.Relics.Select(r => r.Id.Entry).ToArray(),
            piles = player.PlayerCombatState.AllPiles.OrderBy(p => p.Type.ToString(), StringComparer.Ordinal)
                .Select(p => new { pile = p.Type.ToString(), cards = p.Cards.Select(c => Card(c, true)).ToArray() }).ToArray()
        }).ToArray(),
        enemies = State.Enemies.Select(enemy => new
        {
            id = enemy.Monster!.Id.Entry, hp = enemy.CurrentHp, maxHp = enemy.MaxHp, block = enemy.Block,
            move = enemy.Monster.NextMove.Id, powers = Powers(enemy), engaged = EngageCmd.Consumed(enemy)
        }).ToArray()
    });

    private static async Task Stage(string stage, object metrics)
    {
        await Settle(stage);
        await Barrier(stage + "-settled");
        Emit("STAGE", new { schema = 1, token, pair, role, pid = Environment.ProcessId, stage,
            transport = session.Receipt(), state = Snapshot(), metrics });
        completed.Add(stage);
        // Both peers must snapshot before either one arranges the next fixture.
        await Barrier(stage + "-recorded");
    }

    private static void ObserveAction(GameAction action)
    {
        if (action is not PlayCardAction play) return;
        try
        {
            Need(play.Exception is null, "Native paid action faulted: " + play.Exception);
            var card = play.NetCombatCard.ToCardModel();
            actions.Add(new { owner = card.Owner.NetId, card = card.Id.Entry, index = play.NetCombatCard.CombatCardIndex,
                actionId = play.Id.ToString(), state = play.State.ToString(), context = play.PlayerChoiceContext?.GetType().Name });
        }
        catch (Exception error) { actionError = error; }
    }
    private static void ObserveQueue()
    {
        StopObservingQueue();
        actionExecutor = RunManager.Instance.ActionExecutor;
        actionEvent = actionExecutor.GetType().GetEvent("AfterActionExecuted")
            ?? throw new MissingMemberException("Native ActionExecutor.AfterActionExecuted");
        Need(actionEvent.EventHandlerType == typeof(Action<GameAction>), "Native action observer signature changed");
        actionEvent.AddEventHandler(actionExecutor, ActionObserver);
    }
    private static void StopObservingQueue()
    {
        actionEvent?.RemoveEventHandler(actionExecutor, ActionObserver);
        actionEvent = null; actionExecutor = null;
    }
    private static object[] Plays(int boundary) => CombatManager.Instance.History.Entries.Skip(boundary)
        .OfType<CardPlayStartedEntry>().Select(entry => (object)new
        {
            owner = entry.CardPlay.Card.Owner.NetId, card = entry.CardPlay.Card.Id.Entry,
            index = NetCombatCard.FromModel(entry.CardPlay.Card).CombatCardIndex,
            spent = entry.CardPlay.Resources.EnergySpent, autoPlay = entry.CardPlay.IsAutoPlay
        }).ToArray();
    private static async Task<object> Paid(string stage, CardModel? localCard, Creature? target, int count)
    {
        await Settle(stage + " before submission");
        int history = CombatManager.Instance.History.Entries.Count(), offset = actions.Count;
        await Barrier(stage + "-submit");
        if (localCard is not null)
        {
            Need(localCard.Owner.NetId == session.NetId && localCard.CanPlay(out _, out _) && localCard.IsValidTarget(target),
                "Only the legal local player's card may be submitted");
            submitted.Add(stage + ":" + localCard.Id.Entry);
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(new PlayCardAction(localCard, target));
        }
        // A client's RequestEnqueue serializes the request; its original action
        // object is NOT the executed instance. Observe the real queue and history
        // on both peers, never wait on that unexecuted object's CompletionTask.
        await session.Until(() => actions.Count - offset == count && Plays(history).Length == count, stage + " native executed actions");
        await Settle(stage + " native queue settled");
        return new { actions = actions.Skip(offset).ToArray(), plays = Plays(history) };
    }

    private static async Task ClearHands()
    {
        foreach (var player in Players)
            foreach (var card in player.PlayerCombatState!.Hand.Cards.ToArray())
                await CardPileCmd.Add(card, PileType.Draw);
    }
    private static async Task<T> Give<T>(Player owner) where T : CardModel, new()
    {
        var card = State.CreateCard<T>(owner);
        await CardPileCmd.Add(card, PileType.Hand);
        return card;
    }
    private static int Moves(Creature enemy) => CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>()
        .Count(entry => ReferenceEquals(entry.Monster, enemy.Monster));
    private static void Tackle(Creature target)
    {
        var machine = target.Monster!.MoveStateMachine;
        Need(machine.States["TACKLE_MOVE"] is MoveState, "Native LeafSlimeS TACKLE_MOVE missing");
        target.Monster.SetMoveImmediate((MoveState)machine.States["TACKLE_MOVE"], forceTransition: true);
    }

    private static string CheckpointPath()
    {
        var path = Path.GetFullPath(ProjectSettings.GlobalizePath(SaveManager.Instance.GetProfileScopedPath(
            Path.Combine(UserDataPathProvider.SavesDir, RunSaveManager.multiplayerRunSaveFileName))));
        Need(path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "Native save escaped isolated profile");
        return path;
    }
    private static string CheckpointHash() => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(CheckpointPath()))).ToLowerInvariant();
    private static JsonElement ReadCheckpoint()
    {
        using var document = JsonDocument.Parse(File.ReadAllText(CheckpointPath()));
        return document.RootElement.Clone();
    }

    private static async Task Run()
    {
        try
        {
            token = Env("VOLIBEAR_TEST_TOKEN"); pair = Env("VOLIBEAR_MULTIPLAYER_PAIR"); role = Env("VOLIBEAR_MULTIPLAYER_ROLE");
            Need(role is "host" or "client", "Invalid multiplayer role");
            control = Path.GetFullPath(Env("VOLIBEAR_MULTIPLAYER_CONTROL"));
            Need(Directory.Exists(control) && new DirectoryInfo(control).LinkTarget is null, "Missing/linked runner readiness directory");
            root = Path.GetFullPath(Env("VOLIBEAR_TEST_DATA_ROOT")).TrimEnd(Path.DirectorySeparatorChar);
            Need(Path.GetFullPath(ProjectSettings.GlobalizePath("user://")).TrimEnd(Path.DirectorySeparatorChar) == root,
                "Native user:// differs from isolated profile");
            Need(!MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn && !MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized,
                "Native multiplayer acceptance requires TestMode=false and Steam disabled");
            session = new(role == "host", ushort.Parse(Env("VOLIBEAR_MULTIPLAYER_PORT")), Barrier);
            await session.Until(() => NGame.Instance?.MainMenu is not null && SaveManager.Instance.IsProfileInitialized, "initialized native main menu");
            SaveManager.Instance.Progress.GetOrCreateCharacterStats(ModelDb.Character<VolibearCharacter>().Id);
            SaveManager.Instance.SetFtuesEnabled(false);
            // RunManager does not allocate ActionQueueSet/ActionExecutor until
            // its first SetUp call; startup must not dereference those nulls.
            Need(RunManager.Instance.DebugOnlyGetState() is null && CombatManager.Instance.DebugOnlyGetState() is null
                && !CombatManager.Instance.IsInProgress, "Fresh native main menu already has a run");
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            Emit("BEGIN", new { schema = 1, token, pair, role, pid = Environment.ProcessId, userRoot = root,
                gameVersion = release.Version, gameCommit = release.Commit, testMode = false,
                assemblyMvid = typeof(EngageCmd).Assembly.ManifestModule.ModuleVersionId.ToString(),
                transport = "native-ENet-loopback", osInput = false, simulatedClicks = false, processRestarts = 0 });

            var run = await session.Start("222222222");
            await Barrier("first-map-room");
            await session.Await(RunManager.Instance.EnterMapCoord(run.Map.StartingMapPoint.coord), "first native map combat");
            await Settle("first native combat");
            if (SaveManager.Instance.CurrentRunSaveTask is { } saving) await session.Await(saving, "native initial checkpoint write");
            var initial = Snapshot();
            string? checkpointHash = session.Host ? CheckpointHash() : null;
            JsonElement? checkpoint = session.Host ? ReadCheckpoint() : null;
            await Stage("native-checkpoint", new { nativeMapEntry = true, initialCheckpoint = true });

            await Barrier("encounter-fixture");
            var encounter = ModelDb.Encounter<SlimesWeak>();
            await session.Await(RunManager.Instance.EnterRoomDebug(encounter.RoomType, model: encounter.ToMutable(), showTransition: false),
                "native SlimesWeak controlled encounter");
            await Settle("controlled encounter");
            ObserveQueue();
            await ClearHands();
            foreach (var player in Players) await PlayerCmd.SetEnergy(30, player);
            foreach (var enemy in State.Enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 500m);
            var target = State.Enemies.Single(e => e.Monster is LeafSlimeS);
            Tackle(target);
            var engage = new Dictionary<ulong, CardModel>();
            foreach (var player in Players) engage[player.NetId] = await Give<Volibear_B04>(player);
            int moves = Moves(target), drawBoundary = CombatManager.Instance.History.Entries.Count();
            var paidEngage = await Paid("simultaneous-engage", engage[session.NetId], target, 2);
            var draws = CombatManager.Instance.History.Entries.Skip(drawBoundary).OfType<CardDrawnEntry>().Select(e => e.Card.Owner.NetId).ToArray();
            Need(Moves(target) - moves == 1 && EngageCmd.Consumed(target) && Players.All(p => p.PlayerCombatState!.Energy == 29)
                && draws.Length == 1, "Shared enemy action / paid energy / initiator-only starter draw failed");
            await Stage("simultaneous-engage", new { paid = paidEngage, enemyMoves = Moves(target) - moves, starterDrawOwners = draws,
                consumed = EngageCmd.Consumed(target), opportunityEntries = EngageCmd.EarlyOpportunityEntryCount });

            await ClearHands();
            var domain = await Give<Volibear_C05>(Players[0]);
            var lightning = await Give<Volibear_B03>(Players[1]);
            var paidDomain = await Paid("owner-domain", session.Host ? domain : null, target, 1);
            await Barrier("domain-before-teammate");
            var paidLightning = await Paid("teammate-lightning", session.Host ? null : lightning, target, 1);
            int[] domainAmounts = Players.Select(p => p.Creature.GetPowerAmount<DomainPower>()).ToArray();
            int[] lightningCounts = Players.Select(p => LightningBatches.GetTurnCount(p.Creature)).ToArray();
            Need(domainAmounts.SequenceEqual([1, 0]) && lightningCounts.SequenceEqual([1, 1]), "Domain attachment/ lightning counters crossed owners");
            await Stage("owner-scoped-domain-lightning", new { domain = paidDomain, lightning = paidLightning, domainAmounts, lightningCounts });

            await ClearHands();
            var material = new Dictionary<ulong, CardModel[]>(); var converters = new Dictionary<ulong, CardModel>();
            var deckBefore = Freeze(Players.Select(p => p.Deck.Cards.Select(c => Card(c, false)).ToArray()).ToArray());
            foreach (var player in Players)
            {
                var attack = await Give<Volibear_B01>(player); CardCmd.Upgrade(attack);
                var skill = await Give<Volibear_B02>(player);
                material[player.NetId] = [attack, skill]; converters[player.NetId] = await Give<Volibear_R29>(player);
            }
            int beastBoundary = CombatManager.Instance.History.Entries.Count();
            var paidBeast = await Paid("native-beast-identities", converters[session.NetId], null, 2);
            var conversions = Players.Select(player =>
            {
                var old = material[player.NetId]; var forms = player.PlayerCombatState!.Hand.Cards.ToArray();
                Need(forms.Length == 2 && forms[0] is Volibear_T01 && forms[1] is Volibear_T02 && forms[0].IsUpgraded && !forms[1].IsUpgraded
                    && forms.All(c => c.DeckVersion is null) && old.All(c => c.Pile?.Type == PileType.Exhaust)
                    && old.All(c => forms.All(f => !ReferenceEquals(c, f))), "Native beast identity/pile/upgrade contract failed");
                return new { owner = player.NetId, materials = old.Select(c => Card(c, true)).ToArray(), forms = forms.Select(c => Card(c, true)).ToArray() };
            }).ToArray();
            int exhausted = CombatManager.Instance.History.Entries.Skip(beastBoundary).OfType<CardExhaustedEntry>()
                .Count(e => material.Values.SelectMany(c => c).Contains(e.Card));
            int generated = CombatManager.Instance.History.Entries.Skip(beastBoundary).OfType<CardGeneratedEntry>()
                .Count(e => e.Card is Volibear_T01 or Volibear_T02);
            var deckAfter = Freeze(Players.Select(p => p.Deck.Cards.Select(c => Card(c, false)).ToArray()).ToArray());
            Need(exhausted == 4 && generated == 4 && deckBefore.GetRawText() == deckAfter.GetRawText(), "Beast native history/master deck changed");
            await Stage("native-beast-identities", new { paid = paidBeast, conversions, exhausted, generated, masterDeckUnchanged = true });

            int previousRound = State.RoundNumber, targetMoves = Moves(target);
            await Barrier("normal-turn-submit");
            // Follow NEndTurnButton's native synchronized action route. PlayerCmd
            // alone changes only this peer's readiness and never informs its partner.
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
                new EndPlayerTurnAction(Local, Local.PlayerCombatState!.TurnNumber));
            await session.Until(() => Quiet() && State.RoundNumber == previousRound + 1, "both native end-turn actions");
            Need(Moves(target) == targetMoves && !EngageCmd.Consumed(target) && Players.All(p => p.Creature.GetPowerAmount<DomainPower>() == 0)
                && Players.All(p => LightningBatches.GetTurnCount(p.Creature) == 0), "Normal turn did not skip spent action / reset domain and counters");
            await Stage("normal-turn-boundary", new { roundBefore = previousRound, roundAfter = State.RoundNumber,
                duplicateEnemyMoves = Moves(target) - targetMoves, availableAgain = !EngageCmd.Consumed(target), domainExpired = true, lightningReset = true });

            await ClearHands();
            foreach (var player in Players) await PlayerCmd.SetEnergy(30, player);
            Tackle(target); engage.Clear();
            foreach (var player in Players) engage[player.NetId] = await Give<Volibear_B04>(player);
            var paidBeforeDisconnect = await Paid("engage-before-disconnect", engage[session.NetId], target, 2);
            Need(EngageCmd.Consumed(target), "Disconnect fixture needs a real consumed opportunity");
            await Stage("engage-before-disconnect", new { paid = paidBeforeDisconnect, consumed = true });
            if (session.Host) Need(CheckpointHash() == checkpointHash, "Controlled combat unexpectedly overwrote the native room checkpoint");
            await Barrier("disconnect-ready");
            session.AllowDisconnect();
            if (!session.Host) session.DisconnectClient();
            await session.Until(() => session.Host ? session.PeerCount == 0 : !session.Connected, "native peer disconnect observed");
            Emit("DISCONNECT", new { schema = 1, token, pair, role, pid = Environment.ProcessId,
                clientConnectionClosed = true, observedPeerCount = 0, hadConsumedOpportunity = true });
            await Barrier("disconnect-observed");
            StopObservingQueue();
            // Client LocalPlayerDisconnected already starts the native error/menu
            // transition. Starting a second transition races scene cleanup.
            if (session.Host) await session.Await(NGame.Instance!.ReturnToMainMenu(), "native disconnected host cleanup");
            await session.Until(() => NGame.Instance?.MainMenu is not null && !RunManager.Instance.IsInProgress, "native main menu after disconnect");
            NModalContainer.Instance?.Clear(); // Close only the expected native disconnect error after cleanup.
            NativeAcceptanceRunHost.RequireClean();
            Need(EngageCmd.EarlyOpportunityEntryCount == 0 && EngageCmd.NaturalOpportunityEntryCount == 0,
                "Shared opportunity state survived native run cleanup");
            await Barrier("disconnected-clean");
            SerializableRun? save = null;
            object? canonicalizedAt = null;
            if (session.Host)
            {
                Need(CheckpointHash() == checkpointHash, "Native disconnect changed the saved checkpoint");
                long before = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                var loaded = SaveManager.Instance.LoadAndCanonicalizeMultiplayerRunSave(1UL);
                canonicalizedAt = new { before, after = DateTimeOffset.UtcNow.ToUnixTimeSeconds() };
                Need(loaded.Success && loaded.SaveData is not null, "Native multiplayer disk checkpoint load failed");
                save = loaded.SaveData;
                session.Calls.Add("SaveManager.LoadAndCanonicalizeMultiplayerRunSave");
            }
            await session.Load(save);
            await Settle("native two-peer saved-run restored");
            var restored = Snapshot();
            Need(initial.GetRawText() == restored.GetRawText(), "Native checkpoint restore differs from the original combat start");
            Need(EngageCmd.EarlyOpportunityEntryCount == 0 && EngageCmd.NaturalOpportunityEntryCount == 0
                && State.Enemies.All(e => !EngageCmd.Consumed(e)), "Old combat opportunity leaked into restored combat");
            await Stage("native-checkpoint-rejoin", new { originalStateRestored = true, originalPlayerIds = Players.Select(p => p.NetId).ToArray(),
                earlyEntries = EngageCmd.EarlyOpportunityEntryCount, naturalEntries = EngageCmd.NaturalOpportunityEntryCount,
                recovery = "native-room-checkpoint", arbitraryMidcombatSnapshot = false });
            await Barrier("final-cleanup");
            session.AllowDisconnect();
            // Client leaves first through the ordinary menu API; host leaves
            // after observing removal, avoiding a second forced-client transition.
            if (!session.Host) await session.Await(NGame.Instance!.ReturnToMainMenu(), "native final client cleanup");
            await session.Until(() => session.Host ? session.PeerCount == 0 : !RunManager.Instance.IsInProgress, "native final client left");
            await Barrier("final-client-clean");
            if (session.Host) await session.Await(NGame.Instance!.ReturnToMainMenu(), "native final host cleanup");
            await session.Until(() => !RunManager.Instance.IsInProgress, "native final run removed");
            NativeAcceptanceRunHost.RequireClean();
            Emit("RESULT", new { schema = 1, token, pair, role, pid = Environment.ProcessId, completed, submitted,
                nativeCalls = session.Calls, finished = true, osInput = false, simulatedClicks = false, processRestarts = 0,
                cleanup = NativeAcceptanceRunHost.CleanState(), checkpointPath = session.Host ? CheckpointPath() : null,
                checkpointSha256 = session.Host ? CheckpointHash() : null, checkpointBeforeSha256 = checkpointHash,
                checkpoint, afterLoad = session.Host ? (JsonElement?)ReadCheckpoint() : null, canonicalizedAt,
                scope = "native-two-peer-paid-actions-disconnect-checkpoint-rejoin",
                exclusions = new[] { "arbitrary-midcombat-snapshot-rejoin", "steam-transport", "remote-choice-ui", "combat-replay-playback" } });
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            StopObservingQueue();
            Emit("ERROR", new { token, pair, role, pid = Environment.ProcessId, completed, error = error.ToString() });
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
