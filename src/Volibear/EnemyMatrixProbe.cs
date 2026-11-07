using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Core;

namespace Volibear;

/// <summary>
/// Two fresh native runs in one engine process. Only normal queued EndPlayerTurnAction
/// inputs; no enemy health/state edits and no synthetic monster execution.
/// This is a bounded natural-scheduling/isolation MVP, NOT complete enemy AI coverage.
/// </summary>
public static class EnemyMatrixProbe
{
    private const string Seed = "VOLIBEARTEST";
    private const int TurnBudget = 2;
    private static readonly Dictionary<object, string> Refs = new(ReferenceEqualityComparer.Instance);
    private static bool _started;
    private static bool _installed;
    private static readonly PropertyInfo HistoryRound = typeof(CombatHistoryEntry).GetProperty("RoundNumber", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo HistorySide = typeof(CombatHistoryEntry).GetProperty("CurrentSide", BindingFlags.Instance | BindingFlags.NonPublic)!;

    private sealed class CaseCapture(int index)
    {
        internal readonly int Index = index;
        internal CombatState? State;
        internal Exception? ObservationError;
        internal bool Ended;
        internal bool BudgetExit;
        internal int VisibleHistory;
        internal long Sequence;
        internal readonly HashSet<CombatHistoryEntry> Seen = new(ReferenceEqualityComparer.Instance);
        internal readonly List<object> History = [];
        internal readonly List<object> Clears = [];
        internal readonly List<object> Turns = [];
        internal readonly List<object> Inputs = [];
        internal readonly List<object> Boundaries = [];

        internal void OnSetup(CombatState state)
        {
            if (State is not null && !ReferenceEquals(State, state))
                ObservationError = new InvalidOperationException("Unexpected second combat in one case.");
            State = state;
        }
        internal void OnTurn(CombatState state)
        {
            if (!ReferenceEquals(state, State)) return;
            Turns.Add(new { seq = ++Sequence, combatRef = Ref(state), round = state.RoundNumber,
                side = state.CurrentSide.ToString(), turn = state.Players.Single().PlayerCombatState?.TurnNumber });
        }
        internal void OnEnded(CombatRoom room) { if (ReferenceEquals(room.CombatState, State)) Ended = true; }
        internal void OnHistoryChanged()
        {
            // Synchronous readonly copy: EndCombatInternal clears history BEFORE CombatEnded.
            // Never throw into native dispatch; the coordinator fails on the captured error.
            try
            {
                var entries = CombatManager.Instance.History.Entries.ToArray();
                if (entries.Length < VisibleHistory)
                    Clears.Add(new { seq = ++Sequence, priorVisible = VisibleHistory, exported = History.Count,
                        duringBudgetExit = BudgetExit, currentCombatRef = Ref(CombatManager.Instance.DebugOnlyGetState()) });
                VisibleHistory = entries.Length;
                if (State is null || !ReferenceEquals(State, CombatManager.Instance.DebugOnlyGetState())) return;
                foreach (var entry in entries)
                    if (Seen.Add(entry)) History.Add(CopyEntry(entry, State, ++Sequence));
            }
            catch (Exception error) { ObservationError = error; }
        }
    }

    public static void Install()
    {
        if (_installed) return;
        _installed = true;
        CombatManager.Instance.TurnStarted += StartAfterWarmup;
    }

    private static void StartAfterWarmup(CombatState state)
    {
        if (_started || state.CurrentSide != CombatSide.Player ||
            state.Players.Single().PlayerCombatState?.Phase != PlayerTurnPhase.Play) return;
        _started = true;
        CombatManager.Instance.TurnStarted -= StartAfterWarmup;
        // RunSafely observes this Task, it is NOT Task.Run and does not move Godot work off-thread.
        TaskHelper.RunSafely(Coordinate(state));
    }

    private static string? Ref(object? value)
    {
        if (value is null) return null;
        if (!Refs.TryGetValue(value, out var id)) Refs.Add(value, id = "ref-" + (Refs.Count + 1));
        return id;
    }

    private static void Stage(string name, int index = 0) => GD.Print("[Volibear] ENEMY_MATRIX_STAGE " +
        JsonSerializer.Serialize(new { name, caseIndex = index }));

    private static async Task Frame() => await NGame.Instance!.ToSignal(NGame.Instance.GetTree(), SceneTree.SignalName.ProcessFrame);

    private static async Task WaitFor(Func<bool> ready, string stage, CaseCapture? capture = null)
    {
        var clock = Stopwatch.StartNew();
        do
        {
            await Frame(); // Always leave the native event/transition stack before orchestration.
            if (capture?.ObservationError is { } error) throw new InvalidOperationException("Readonly observation failed", error);
            if (capture?.Ended == true && !capture.BudgetExit)
                throw new InvalidOperationException("Unexpected natural terminal during bounded SlimesWeak fixture: " + stage);
            if (ready()) return;
        } while (clock.Elapsed < TimeSpan.FromSeconds(120));
        throw new TimeoutException("Native matrix stage timed out: " + stage);
    }

    private static bool QuietPlay(CombatState state, int turn)
    {
        var manager = CombatManager.Instance;
        var run = RunManager.Instance;
        var player = state.Players.Single();
        return ReferenceEquals(manager.DebugOnlyGetState(), state) && manager.IsInProgress && !manager.IsOverOrEnding &&
            state.CurrentSide == CombatSide.Player && state.RoundNumber == turn &&
            player.PlayerCombatState?.Phase == PlayerTurnPhase.Play && player.PlayerCombatState.TurnNumber == turn &&
            run.ActionQueueSet.IsEmpty && run.ActionExecutor.CurrentlyRunningAction is null &&
            state.Enemies.All(enemy => !enemy.Monster!.IsPerformingMove) && PendingChoices() == 0;
    }

    private static int PendingChoices() => ((ICollection)Field(RunManager.Instance.PlayerChoiceSynchronizer, "_receivedChoices")!).Count;
    private static object? Field(object instance, string name) => instance.GetType()
        .GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)!.GetValue(instance);
    private static object? StaticField(Type type, string name) => type
        .GetField(name, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)!.GetValue(null);
    private static int Count(object value) => (int)value.GetType().GetProperty("Count")!.GetValue(value)!;
    private static int TableCount(object value) { var count = 0; foreach (var unused in (IEnumerable)value) count++; return count; }

    private static object Scopes(CombatState? state)
    {
        var lightning = (IDictionary)StaticField(typeof(LightningBatches), "Scopes")!;
        var targets = (IDictionary)StaticField(typeof(TargetCosts), "_subscriptions")!;
        return new
        {
            activePlays = Count(StaticField(typeof(CardResolutionHooks), "ActivePlays")!),
            playTasks = TableCount(StaticField(typeof(CardResolutionHooks), "_playTasks")!),
            drawTasks = TableCount(StaticField(typeof(CardResolutionHooks), "_drawTasks")!),
            purifications = TableCount(StaticField(typeof(CardResolutionHooks), "_purifications")!),
            lightningCombatRefs = lightning.Keys.Cast<object>().Select(Ref).ToArray(),
            targetSubscriptionOwnerRefs = targets.Keys.Cast<object>().Select(Ref).ToArray(),
            lightningOnlyCurrentCombat = lightning.Keys.Cast<object>().All(key => ReferenceEquals(key, state)),
            targetSubscriptionsOnlyCurrentCombat = targets.Keys.Cast<Creature>().All(owner => ReferenceEquals(owner.CombatState, state)),
            engageConsumed = EngageCmd.EarlyOpportunityEntryCount,
            engageActionRounds = EngageCmd.NaturalOpportunityEntryCount
        };
    }

    private static object CreatureSnapshot(Creature creature) => new
    {
        creatureRef = Ref(creature), modelRef = Ref(creature.Monster), combatId = creature.CombatId,
        modelId = creature.Monster?.Id.ToString(), side = creature.Side.ToString(), hp = creature.CurrentHp,
        maxHp = creature.MaxHp, block = creature.Block, nextMove = creature.Monster?.NextMove?.Id,
        stateLog = creature.Monster?.MoveStateMachine?.StateLog.Select(s => s.Id).ToArray(),
        powers = creature.Powers.Select(power => new { id = power.Id.ToString(), amount = power.Amount }).ToArray()
    };

    private static object Snapshot(CombatState state, CaseCapture capture)
    {
        var player = state.Players.Single();
        var pcs = player.PlayerCombatState!;
        var run = RunManager.Instance;
        return new
        {
            seq = ++capture.Sequence, runRef = Ref(run.DebugOnlyGetState()), combatRef = Ref(state), encounterRef = Ref(state.Encounter),
            playerRef = Ref(player), playerCreatureRef = Ref(player.Creature), playerCombatRef = Ref(pcs),
            queueRef = Ref(run.ActionQueueSet), executorRef = Ref(run.ActionExecutor), choiceSyncRef = Ref(run.PlayerChoiceSynchronizer),
            historyRef = Ref(CombatManager.Instance.History), historyVisible = CombatManager.Instance.History.Entries.Count(),
            historyExported = capture.History.Count, round = state.RoundNumber, turn = pcs.TurnNumber,
            side = state.CurrentSide.ToString(), phase = pcs.Phase.ToString(), queueEmpty = run.ActionQueueSet.IsEmpty,
            runningActionRef = Ref(run.ActionExecutor.CurrentlyRunningAction), pendingChoices = PendingChoices(),
            choiceIds = run.PlayerChoiceSynchronizer.ChoiceIds.ToArray(), energy = pcs.Energy,
            domain = player.Creature.GetPowerAmount<DomainPower>(), storm = player.Creature.GetPowerAmount<StormChargePower>(),
            player = CreatureSnapshot(player.Creature), enemies = state.Enemies.Select(CreatureSnapshot).ToArray(),
            cards = pcs.AllPiles.SelectMany(pile => pile.Cards).Select(card => new
                { cardRef = Ref(card), id = card.Id.ToString(), pile = card.Pile?.Type.ToString() }).ToArray(),
            deck = player.Deck.Cards.Select(card => new { cardRef = Ref(card), id = card.Id.ToString() }).ToArray(),
            scopes = Scopes(state)
        };
    }

    private static object CopyEntry(CombatHistoryEntry entry, CombatState state, long sequence)
    {
        var data = new Dictionary<string, object?>
        {
            ["seq"] = sequence, ["entryRef"] = Ref(entry), ["combatRef"] = Ref(state),
            ["kind"] = entry.GetType().Name, ["round"] = HistoryRound.GetValue(entry),
            ["side"] = HistorySide.GetValue(entry)!.ToString(), ["actorRef"] = Ref(entry.Actor),
            ["actorCombatId"] = entry.Actor?.CombatId
        };
        switch (entry)
        {
            case MonsterPerformedMoveEntry move:
                data["monsterRef"] = Ref(move.Monster); data["monsterId"] = move.Monster.Id.ToString();
                data["move"] = move.Move.Id; data["targetRefs"] = move.Targets?.Select(Ref).ToArray();
                data["actorAfter"] = CreatureSnapshot(move.Monster.Creature);
                break;
            case DamageReceivedEntry damage:
                data["receiverRef"] = Ref(damage.Receiver); data["dealerRef"] = Ref(damage.Dealer);
                data["hpLost"] = damage.Result.UnblockedDamage; data["blocked"] = damage.Result.BlockedDamage;
                data["props"] = (int)damage.Result.Props; data["cardRef"] = Ref(damage.CardSource);
                data["receiverAfter"] = CreatureSnapshot(damage.Receiver);
                break;
            case CardDrawnEntry draw:
                data["cardRef"] = Ref(draw.Card); data["cardId"] = draw.Card.Id.ToString();
                break;
            case CardPlayStartedEntry play:
                data["cardRef"] = Ref(play.CardPlay.Card); data["cardId"] = play.CardPlay.Card.Id.ToString();
                break;
        }
        return data;
    }

    private static object AfterExit() => new
    {
        runIsNull = RunManager.Instance.DebugOnlyGetState() is null, combatIsNull = CombatManager.Instance.DebugOnlyGetState() is null,
        inProgress = CombatManager.Instance.IsInProgress, historyVisible = CombatManager.Instance.History.Entries.Count(),
        queueEmpty = RunManager.Instance.ActionQueueSet.IsEmpty,
        runningActionRef = Ref(RunManager.Instance.ActionExecutor.CurrentlyRunningAction), scopes = Scopes(null)
    };

    private static async Task<object> RunCase(int index)
    {
        var manager = CombatManager.Instance;
        var run = RunManager.Instance;
        var capture = new CaseCapture(index);
        var canonicalActs = ActModel.GetDefaultList().ToArray();
        canonicalActs[0] = ModelDb.Act<Overgrowth>();
        Stage("start-new-native-run", index);
        var runState = await NGame.Instance!.StartNewSingleplayerRun(ModelDb.Character<Content.VolibearCharacter>(),
            shouldSave: false, canonicalActs, Array.Empty<ModifierModel>(), Seed, GameMode.Standard, ascensionLevel: 0);
        manager.CombatSetUp += capture.OnSetup;
        manager.TurnStarted += capture.OnTurn;
        manager.CombatEnded += capture.OnEnded;
        manager.History.Changed += capture.OnHistoryChanged;
        object? initial = null;
        object? exit = null;
        string? error = null;
        try
        {
            Stage("enter-native-slimes-room", index);
            await run.EnterRoomDebug(RoomType.Monster, model: ModelDb.Encounter<SlimesWeak>().ToMutable(), showTransition: false);
            await WaitFor(() => capture.State is { } s && QuietPlay(s, 1), "case first Play phase", capture);
            var state = capture.State!;
            initial = Snapshot(state, capture);
            capture.Boundaries.Add(initial);
            for (var step = 0; step < TurnBudget; step++)
            {
                var player = state.Players.Single();
                var before = player.PlayerCombatState!.TurnNumber;
                var action = new EndPlayerTurnAction(player, before);
                var enqueueSequence = ++capture.Sequence;
                Stage("enqueue-end-turn-" + before, index);
                run.ActionQueueSynchronizer.RequestEnqueue(action);
                await WaitFor(() => QuietPlay(state, before + 1), "next native player Play phase", capture);
                capture.Inputs.Add(new { seq = enqueueSequence, type = "EndPlayerTurnAction", actionRef = Ref(action),
                    turnBefore = before, turnAfter = player.PlayerCombatState.TurnNumber,
                    completionAtNextPlay = action.CompletionTask.IsCompletedSuccessfully });
                capture.Boundaries.Add(Snapshot(state, capture));
            }
            Stage("budget-exit-at-player-play", index);
            capture.BudgetExit = true;
            // Static budget stop, not a synthetic victory. Exit/Reset run through native rooms.
            await run.EnterRoom(new MapRoom());
            await Frame();
            await NGame.Instance.ReturnToMainMenu();
            await Frame();
            exit = AfterExit();
        }
        catch (Exception exception) { error = exception.ToString(); }
        finally
        {
            manager.CombatSetUp -= capture.OnSetup;
            manager.TurnStarted -= capture.OnTurn;
            manager.CombatEnded -= capture.OnEnded;
            manager.History.Changed -= capture.OnHistoryChanged;
        }
        var result = new
        {
            caseId = "NATIVE-SLIMES-" + index, processId = System.Environment.ProcessId,
            seed = runState.Rng.StringSeed, numericSeed = runState.Rng.Seed,
            act = runState.Act.Id.ToString(), actIndex = runState.CurrentActIndex,
            acts = runState.Acts.Select(act => new { id = act.Id.ToString(), index = act.Index }).ToArray(),
            ascension = runState.AscensionLevel, encounter = capture.State?.Encounter?.Id.ToString(),
            roomType = capture.State?.Encounter?.RoomType.ToString(), totalFloor = runState.TotalFloor,
            mapCoord = new { col = runState.CurrentMapCoord?.col, row = runState.CurrentMapCoord?.row },
            turnBudget = TurnBudget, outcome = error is null ? "BUDGET_EXIT" : "FAILED", error,
            initial, boundaries = capture.Boundaries, inputs = capture.Inputs, nativeHistory = capture.History,
            historyClears = capture.Clears, turnSignals = capture.Turns, afterExit = exit,
            naturalTerminal = capture.Ended, observationError = capture.ObservationError?.ToString()
        };
        if (error is not null) throw new CaseFailedException(result, error);
        return result;
    }

    private sealed class CaseFailedException(object result, string message) : Exception(message)
    { internal readonly object Result = result; }

    private static async Task Coordinate(CombatState warmup)
    {
        var cases = new List<object>();
        string? failure = null;
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        var directory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ARTIFACT_DIR");
        var release = ReleaseInfoManager.Instance.ReleaseInfo;
        try
        {
            if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(directory) ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn || release?.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit)
                throw new InvalidOperationException("Matrix requires isolated artifacts/token, pinned native engine, TestMode=false.");
            await Frame();
            await WaitFor(() => QuietPlay(warmup, warmup.Players.Single().PlayerCombatState!.TurnNumber), "warmup quiescence");
            await RunManager.Instance.EnterRoom(new MapRoom());
            await NGame.Instance!.ReturnToMainMenu();
            await Frame();
            for (var index = 1; index <= 2; index++) cases.Add(await RunCase(index));
        }
        catch (CaseFailedException error) { cases.Add(error.Result); failure = error.ToString(); }
        catch (Exception error) { failure = error.ToString(); }
        try
        {
            if (string.IsNullOrWhiteSpace(directory)) throw new InvalidOperationException("Missing artifact directory.");
            var manifest = new
            {
                schema = 1, token, scenario = "enemy-matrix-mvp", acceptance = "natural-scheduling-isolation-only",
                processId = System.Environment.ProcessId,
                gameVersion = release?.Version, gameCommit = release?.Commit,
                gameAssemblyMvid = typeof(ModelDb).Assembly.ManifestModule.ModuleVersionId,
                modAssemblyMvid = typeof(EnemyMatrixProbe).Assembly.ManifestModule.ModuleVersionId,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, seed = Seed,
                warmup = new { combatRef = Ref(warmup), includedInCases = false, purpose = "bootstrap-install-trigger" },
                enemyHpModified = false, forcedMoves = false, directPerformMoveCalls = 0,
                completeAiCoverage = false, cases, failure
            };
            var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }) + "\n");
            Directory.CreateDirectory(directory);
            File.WriteAllBytes(Path.Combine(directory, "enemy-matrix-mvp.json"), bytes);
            GD.Print("[Volibear] ENEMY_MATRIX_RESULT " + JsonSerializer.Serialize(new
            {
                token, scenario = "enemy-matrix-mvp", acceptance = "natural-scheduling-isolation-only",
                manifest = "enemy-matrix-mvp.json", bytes = bytes.Length,
                sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                caseCount = cases.Count, completed = failure is null, failure
            }));
            if (failure is not null) GD.PrintErr("[Volibear] ENEMY_MATRIX_ERROR " + failure);
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            // Identity proof is serialized; do not retain old native models through engine shutdown.
            Refs.Clear();
            warmup = null!;
            NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(failure is null ? 0 : 2);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] ENEMY_MATRIX_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
