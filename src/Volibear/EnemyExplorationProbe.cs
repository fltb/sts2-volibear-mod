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
using HarmonyLib;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Entities.Cards;
using Volibear.Content;
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
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.GameOverScreen;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using Volibear.Core;

namespace Volibear;

/// <summary>Bounded native Act exploration and finite paid-card enemy cycles.
/// Reuses native history/queue observation; no direct enemy execution or forced AI state.
/// Formal scheduling is not complete effect/guard coverage. The two-case MVP is unchanged.</summary>
public static class EnemyExplorationProbe
{
    private const string Seed = "VOLIBEARTEST";
    private static readonly Dictionary<object, string> Refs = new(ReferenceEqualityComparer.Instance);
    private static bool _started;
    private static bool _installed;
    private static CaseCapture? _active;
    private static readonly Harmony MoveObservation = new("Volibear.EnemyExplorationMoveObservation");

    [HarmonyPatch(typeof(MoveState), nameof(MoveState.PerformMove))]
    private static class ObserveSelectedMove
    {
        // Void prefix only: no task wrapping, arguments, return, or control-flow changes.
        private static void Prefix(MoveState __instance)
        {
            var capture = _active;
            if (capture?.State is not { } state || !ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())) return;
            try
            {
                var actor = state.Enemies.Single(e => ReferenceEquals(e.Monster?.NextMove, __instance));
                capture.MoveWindows.Add(new Dictionary<string, object?> {
                    ["startSeq"] = ++capture.Sequence, ["actorRef"] = Ref(actor), ["monsterId"] = actor.Monster!.Id.ToString(),
                    ["move"] = __instance.Id, ["round"] = state.RoundNumber, ["side"] = state.CurrentSide.ToString(),
                    ["before"] = MoveWorld(state), ["status"] = "STARTED_NOT_COMPLETED" });
            }
            catch (Exception error) { capture.ObservationError = error; }
        }
    }
    private static readonly PropertyInfo HistoryRound = typeof(CombatHistoryEntry).GetProperty("RoundNumber", BindingFlags.Instance | BindingFlags.NonPublic)!;
    private static readonly PropertyInfo HistorySide = typeof(CombatHistoryEntry).GetProperty("CurrentSide", BindingFlags.Instance | BindingFlags.NonPublic)!;

    public sealed record CaseSpec(string CaseId, string Act, string Encounter, int TurnBudget,
        string Policy, string ExpectedOutcome);
    public sealed record Selection(int Schema, string Mode, string Seed, int Ascension,
        string GameAssemblyMvid, CaseSpec[] Cases, string? PrerequisiteToken);

    // Source-derived finite cycle fixtures, not a claim about all formal enemies.
    private static readonly string[] PaidTargets = ["LEAF_SLIME_S", "LEAF_SLIME_M", "TWIG_SLIME_S"];
    private static readonly string[] PaidPolicies = ["paid-natural-off", "paid-engage-off", "paid-natural-on", "paid-engage-on"];
    private static CaseSpec[] PaidCases() => PaidTargets.SelectMany(target => PaidPolicies.Select(policy =>
        new CaseSpec("paid-" + target + "-" + policy, "ACT.OVERGROWTH", "ENCOUNTER.SLIMES_WEAK", 4,
            policy, "BUDGET_EXIT"))).ToArray();

    private static CaseSpec[] ThresholdCases() => PaidPolicies.Select(policy =>
        new CaseSpec("threshold-TUNNELER_WEAK:TUNNELER:" + policy, "ACT.HIVE", "ENCOUNTER.TUNNELER_WEAK",
            policy.EndsWith("-on") ? 4 : 5, policy, "BUDGET_EXIT")).ToArray();

    private sealed class CaseCapture(int index)
    {
        internal readonly int Index = index;
        internal CombatState? State;
        internal Exception? ObservationError;
        internal bool Ended;
        internal bool Won;
        internal int EnemyTurnOrdinal;
        internal readonly List<object> TerminalSignals = [];
        internal readonly List<object> SideSwitches = [];
        internal readonly List<object> CreatureChanges = [];
        internal readonly List<Dictionary<string, object?>> Opportunities = [];
        internal readonly HashSet<Creature> KnownCreatures = new(ReferenceEqualityComparer.Instance);
        internal bool BudgetExit;
        internal int VisibleHistory;
        internal long Sequence;
        internal readonly HashSet<CombatHistoryEntry> Seen = new(ReferenceEqualityComparer.Instance);
        internal readonly List<object> History = [];
        internal readonly List<object> Clears = [];
        internal readonly List<object> Turns = [];
        internal readonly List<object> Inputs = [];
        internal readonly List<object> PaidAttempts = [];
        internal bool AllowKnowledgeChoice;
        internal readonly HashSet<object> ChosenScreens = new(ReferenceEqualityComparer.Instance);
        internal readonly List<object> ChoiceInputs = [];
        internal readonly List<object> Boundaries = [];
        internal readonly List<Dictionary<string, object?>> MoveWindows = [];

        internal void OnSetup(CombatState state)
        {
            if (State is not null && !ReferenceEquals(State, state))
                ObservationError = new InvalidOperationException("Unexpected second combat in one case.");
            State = state;
            foreach (var creature in state.Creatures) KnownCreatures.Add(creature);
        }
        internal void OnTurn(CombatState state)
        {
            if (!ReferenceEquals(state, State)) return;
            if (state.CurrentSide == CombatSide.Enemy) EnemyTurnOrdinal++;
            if (state.CurrentSide == CombatSide.Enemy)
                foreach (var enemy in state.Enemies)
                    Opportunities.Add(new Dictionary<string, object?>
                    {
                        ["seq"] = ++Sequence, ["round"] = state.RoundNumber, ["creatureRef"] = Ref(enemy),
                        ["enemyTurnOrdinal"] = EnemyTurnOrdinal, ["side"] = enemy.Side.ToString(), ["alive"] = enemy.IsAlive,
                        ["modelId"] = enemy.Monster!.Id.ToString(), ["spawnedThisTurn"] = enemy.Monster.SpawnedThisTurn,
                        ["nextMove"] = enemy.Monster.NextMove?.Id, ["status"] = "NOT_OBSERVED",
                        ["observationPoint"] = "native-enemy-turn-start-not-inferred-executor-snapshot"
                    });
            Turns.Add(new { seq = ++Sequence, combatRef = Ref(state), round = state.RoundNumber,
                side = state.CurrentSide.ToString(), turn = state.Players.Single().PlayerCombatState?.TurnNumber,
                enemyTurnOrdinal = EnemyTurnOrdinal, enemyCandidateRefs = state.CurrentSide == CombatSide.Enemy
                    ? state.Enemies.Select(Ref).ToArray() : Array.Empty<string?>() });
        }
        internal void OnWon(CombatRoom room)
        {
            if (!ReferenceEquals(room.CombatState, State)) return;
            Won = true;
            TerminalSignals.Add(new { seq = ++Sequence, kind = "CombatWon", combatRef = Ref(State) });
        }
        internal void OnEnded(CombatRoom room)
        {
            if (!ReferenceEquals(room.CombatState, State)) return;
            Ended = true;
            TerminalSignals.Add(new { seq = ++Sequence, kind = "CombatEnded", combatRef = Ref(State),
                playerDead = State!.Players.Single().Creature.IsDead });
        }
        internal void OnSwitch(CombatState state)
        {
            if (!ReferenceEquals(state, State)) return;
            SideSwitches.Add(new { seq = ++Sequence, round = state.RoundNumber, side = state.CurrentSide.ToString(),
                enemies = state.Enemies.Select(enemy => new { creatureRef = Ref(enemy),
                    spawnedThisTurn = enemy.Monster!.SpawnedThisTurn, nextMove = enemy.Monster.NextMove?.Id }).ToArray() });
        }
        internal void OnCreatures(CombatState state)
        {
            if (!ReferenceEquals(state, State)) return;
            foreach (var creature in state.Creatures) KnownCreatures.Add(creature);
            CreatureChanges.Add(new { seq = ++Sequence, round = state.RoundNumber, side = state.CurrentSide.ToString(),
                presentCreatureRefs = state.Creatures.Select(Ref).ToArray(),
                // Registration is earlier than AfterAddedToRoom: do not inspect an uninitialized AI here.
                readyStateClaimed = false });
        }
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
                    if (Seen.Add(entry))
                    {
                        History.Add(CopyEntry(entry, State, ++Sequence));
                        if (entry is MonsterPerformedMoveEntry finishedMove)
                        {
                            var window = MoveWindows.LastOrDefault(w => Equals(w["actorRef"], Ref(finishedMove.Monster.Creature)) &&
                                Equals(w["move"], finishedMove.Move.Id) && Equals(w["status"], "STARTED_NOT_COMPLETED"));
                            if (window is not null)
                            {
                                window["historySeq"] = Sequence; window["historyRef"] = Ref(entry);
                                window["endSeq"] = ++Sequence; window["after"] = MoveWorld(State);
                                window["status"] = "COMPLETED_NATIVE_HISTORY";
                            }
                        }
                        if (entry is MonsterPerformedMoveEntry performed &&
                            (CombatSide)HistorySide.GetValue(entry)! == CombatSide.Enemy)
                        {
                            var round = (int)HistoryRound.GetValue(entry)!;
                            var opportunity = Opportunities.LastOrDefault(row => (int)row["enemyTurnOrdinal"]! == EnemyTurnOrdinal &&
                                (int)row["round"]! == round &&
                                Equals(row["creatureRef"], Ref(performed.Monster.Creature)) && Equals(row["status"], "NOT_OBSERVED"));
                            if (opportunity is not null) opportunity["status"] = "COMPLETED_NATIVE_HISTORY";
                        }
                    }
            }
            catch (Exception error) { ObservationError = error; }
        }
    }

    public static void Install()
    {
        if (_installed) return;
        _installed = true;
        MoveObservation.CreateClassProcessor(typeof(ObserveSelectedMove)).Patch();
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

    private static void Stage(string name, int index = 0) => GD.Print("[Volibear] ENEMY_EXPLORATION_STAGE " +
        JsonSerializer.Serialize(new { name, caseIndex = index, tickMs = System.Environment.TickCount64 }));

    private static async Task Frame() => await NGame.Instance!.ToSignal(NGame.Instance.GetTree(), SceneTree.SignalName.ProcessFrame);

    private static async Task WaitFor(Func<bool> ready, string stage, CaseCapture? capture = null)
    {
        var clock = Stopwatch.StartNew();
        do
        {
            await Frame(); // Always leave the native event/transition stack before orchestration.
            if (capture?.ObservationError is { } error) throw new InvalidOperationException("Readonly observation failed", error);
            if (capture?.AllowKnowledgeChoice == true) await ChooseKnowledge(capture);
            if (ready()) return;
        } while (clock.Elapsed < TimeSpan.FromSeconds(120));
        throw new TimeoutException("Native matrix stage timed out: " + stage);
    }

    private static IEnumerable<Node> Descendants(Node node)
    {
        foreach (var child in node.GetChildren())
        {
            yield return child;
            foreach (var nested in Descendants(child)) yield return nested;
        }
    }

    private static async Task ChooseKnowledge(CaseCapture capture)
    {
        if (NOverlayStack.Instance?.Peek() is not NChooseACardSelectionScreen screen ||
            capture.ChosenScreens.Contains(screen)) return;
        var holders = Descendants(screen).OfType<NCardHolder>()
            .Where(h => h.IsVisibleInTree() && h.CardNode?.Model is KnowledgeDemon.IChoosable).ToArray();
        // One explicit choice branch: Disintegration from the genuine two-candidate screen.
        // No FromIndex/AsCombatCards substitution, selector, OnChosen, or TCS completion.
        var holder = holders.FirstOrDefault(h => h.CardNode!.Model.Id.Entry == "DISINTEGRATION");
        if (holders.Length != 2 || holder is null || holder.FocusMode == Control.FocusModeEnum.None) return;
        holder.GrabFocus();
        await Frame();
        var viewport = holder.GetViewport();
        if (!ReferenceEquals(viewport.GuiGetFocusOwner(), holder))
            throw new InvalidOperationException("Knowledge native candidate focus unavailable");
        capture.ChosenScreens.Add(screen);
        var selected = holder.CardNode!.Model;
        var candidates = holders.Select(h => h.CardNode!.Model.Id.ToString()).ToArray();
        var before = ++capture.Sequence;
        viewport.PushInput(new InputEventAction { Action = MegaInput.select, Pressed = true });
        await Frame();
        var releaseSeq = ++capture.Sequence;
        viewport.PushInput(new InputEventAction { Action = MegaInput.select, Pressed = false });
        await Frame();
        capture.ChoiceInputs.Add(new { seq = before, pressSeq = before, releaseSeq, endSeq = ++capture.Sequence,
            api = "Viewport.PushInput", kind = "knowledge-disintegration-only", selectedCardRef = Ref(selected),
            selectedCardId = selected.Id.ToString(), candidates,
            pressed = new[] { true, false }, focusMatched = true, physicalInputValidated = false });
    }

    private static bool QuietPlay(CombatState state, int turn)
    {
        var manager = CombatManager.Instance;
        var run = RunManager.Instance;
        var player = state.Players.Single();
        return ReferenceEquals(manager.DebugOnlyGetState(), state) && manager.IsInProgress && !manager.IsOverOrEnding &&
            state.CurrentSide == CombatSide.Player &&
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

    private static object NativeGuardState(MonsterModel? monster) => monster switch
    {
        CorpseSlug slug => new { slug.StarterMoveIdx, slug.IsRavenous },
        Axebot axe => new { axe.StockAmount, stockOverridden = Field(axe, "_stockOverrideAmount") is not null },
        Tunneler tunneler => new { tunneler.IsStunned },
        Chomper chomper => new { chomper.ScreamFirst },
        ScrollOfBiting scroll => new { scroll.StarterMoveIdx },
        TwoTailedRat rat => new { rat.StarterMoveIndex, rat.CallForBackupCount,
            turnsUntilSummonable = Field(rat, "_turnsUntilSummonable") },
        SoulFysh fish => new { fish.IsInvisible },
        FuzzyWurmCrawler wurm => new { isPuffed = Field(wurm, "_isPuffed") },
        SneakyGremlin sneaky => new { isAwake = Field(sneaky, "_isAwake") },
        FatGremlin fat => new { isAwake = Field(fat, "_isAwake") },
        Nibbit nibbit => new { nibbit.IsAlone, nibbit.IsFront },
        PunchConstruct punch => new { punch.StartsWithFastPunch, punch.StartingHpReduction },
        CubexConstruct cubex => new { isBurrowed = Field(cubex, "_isBurrowed"), isCharging = Field(cubex, "_isCharging") },
        _ => new { }
    };

    private static object MoveWorld(CombatState state)
    {
        var player = state.Players.Single();
        return new { player = CreatureSnapshot(player.Creature),
            domain = player.Creature.GetPowerAmount<DomainPower>(),
            enemies = state.Enemies.Select(CreatureSnapshot).ToArray(),
            slots = state.Encounter!.Slots.ToArray(),
            cards = player.PlayerCombatState?.AllPiles.SelectMany(p => p.Cards).Select(c =>
                new { cardRef = Ref(c), id = c.Id.ToString(), pile = c.Pile?.Type.ToString(), type = c.Type.ToString(),
                    affliction = c.Affliction?.Id.ToString(), afflictionAmount = c.Affliction?.Amount }).ToArray() };
    }

    private static object CreatureSnapshot(Creature creature) => new
    {
        creatureRef = Ref(creature), modelRef = Ref(creature.Monster), combatId = creature.CombatId, slot = creature.SlotName,
        modelId = creature.Monster?.Id.ToString(), side = creature.Side.ToString(), hp = creature.CurrentHp,
        maxHp = creature.MaxHp, block = creature.Block, nextMove = creature.Monster?.NextMove?.Id,
        guards = NativeGuardState(creature.Monster),
        stateLog = creature.Monster?.MoveStateMachine?.StateLog.Select(s => s.Id).ToArray(),
        spawnedThisTurn = creature.Monster?.SpawnedThisTurn, alive = creature.IsAlive,
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
            case EnergySpentEntry energy:
                data["amount"] = energy.Amount;
                break;
            case CardPlayFinishedEntry finished:
                data["cardRef"] = Ref(finished.CardPlay.Card); data["cardId"] = finished.CardPlay.Card.Id.ToString();
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

    private static Selection ReadSelection(out string hash)
    {
        var path = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_MATRIX_SELECTION")
            ?? throw new InvalidOperationException("Explicit selection manifest required.");
        var bytes = File.ReadAllBytes(path);
        hash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        var selection = JsonSerializer.Deserialize<Selection>(bytes, new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidOperationException("Null selection.");
        if (selection.Schema != 1 || selection.Seed != Seed || selection.Ascension != 0 ||
            selection.GameAssemblyMvid != typeof(ModelDb).Assembly.ManifestModule.ModuleVersionId.ToString() ||
            selection.Cases is null || selection.Cases.Length == 0 || selection.Cases.Length > 80 ||
            selection.Cases.Select(c => c.CaseId).Distinct().Count() != selection.Cases.Length)
            throw new InvalidOperationException("Invalid/version-mismatched exploration selection.");
        if (selection.Mode == "smoke")
        {
            var expected = new[]
            {
                new CaseSpec("smoke-overgrowth", "ACT.OVERGROWTH", "ENCOUNTER.SLIMES_WEAK", 2, "end-turn", "BUDGET_EXIT"),
                new CaseSpec("terminal-win", "ACT.OVERGROWTH", "ENCOUNTER.SLIMES_WEAK", 32, "basic-paid-cards", "WIN"),
                new CaseSpec("terminal-loss", "ACT.OVERGROWTH", "ENCOUNTER.SLIMES_WEAK", 32, "end-turn", "LOSS"),
                new CaseSpec("smoke-underdocks", "ACT.UNDERDOCKS", "ENCOUNTER.CORPSE_SLUGS_WEAK", 2, "end-turn", "ANY"),
                new CaseSpec("smoke-hive", "ACT.HIVE", "ENCOUNTER.BOWLBUGS_WEAK", 2, "end-turn", "ANY"),
                new CaseSpec("smoke-glory", "ACT.GLORY", "ENCOUNTER.DEVOTED_SCULPTOR_WEAK", 2, "end-turn", "ANY")
            };
            if (!selection.Cases.SequenceEqual(expected)) throw new InvalidOperationException("Smoke manifest must contain exact four-Act/three-terminal fixtures.");
        }
        else if (selection.Mode == "explore")
        {
            if (string.IsNullOrWhiteSpace(selection.PrerequisiteToken) ||
                System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_EXPLORATION_APPROVED") != selection.PrerequisiteToken ||
                selection.Cases.Select(c => c.Encounter).Distinct().Count() != selection.Cases.Length ||
                selection.Cases.Any(c => c.TurnBudget != 2 || c.Policy != "end-turn" || c.ExpectedOutcome != "ANY"))
                throw new InvalidOperationException("Explore requires externally validated smoke prerequisite and explicit bounded unique cases.");
        }
        else if (selection.Mode == "paid-acceptance")
        {
            if (!selection.Cases.SequenceEqual(PaidCases()))
                throw new InvalidOperationException("Paid acceptance requires the exact twelve four-cycle fixtures.");
        }
        else if (selection.Mode == "paid-threshold")
        {
            if (!selection.Cases.SequenceEqual(ThresholdCases()))
                throw new InvalidOperationException("Threshold acceptance requires the exact four paid Tunneler fixtures.");
        }
        else if (selection.Mode == "formal-paid")
        {
            foreach (var spec in selection.Cases)
            {
                var parts = spec.CaseId.Split(':');
                if (parts.Length != 3 || parts[0] != "formal-" + spec.Encounter.Split('.')[1] ||
                    parts[2] != spec.Policy || !PaidPolicies.Contains(spec.Policy) ||
                    spec.TurnBudget is < 4 or > 16 || spec.ExpectedOutcome != "ANY" ||
                    !EnemyCatalogProbe.ResolveEncounter(spec.Encounter).AllPossibleMonsters.Any(m => m.Id.Entry == parts[1]))
                    throw new InvalidOperationException("Invalid formal paid target/cycle fixture.");
            }
        }
        else throw new InvalidOperationException("Unknown selection mode.");
        foreach (var spec in selection.Cases)
        {
            var act = ModelDb.Acts.SingleOrDefault(a => a.Id.ToString() == spec.Act)
                ?? throw new InvalidOperationException("Unregistered Act " + spec.Act);
            if (!act.AllEncounters.Any(e => !e.IsDebugEncounter && e.Id.ToString() == spec.Encounter))
                throw new InvalidOperationException("Encounter is not rooted in selected Act; event/display roots are forbidden.");
        }
        return selection;
    }

    private static bool Settled(CaseCapture capture) =>
        RunManager.Instance.ActionQueueSet.IsEmpty && RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null &&
        PendingChoices() == 0 && capture.KnownCreatures.All(c => c.Monster?.IsPerformingMove != true) &&
        Count(StaticField(typeof(CardResolutionHooks), "ActivePlays")!) == 0;

    private static async Task CloseLossUi(CaseCapture capture)
    {
        await WaitFor(() => NOverlayStack.Instance?.Peek() is NGameOverScreen screen &&
            screen.GetNode<NClickableControl>("%ContinueButton").IsEnabled, "native loss overlay ready", capture);
        var overlay = (NGameOverScreen)NOverlayStack.Instance!.Peek()!;
        // Native UI command for cleanup only, explicitly NOT physical-input acceptance.
        overlay.GetNode<NClickableControl>("%ContinueButton").ForceClick();
        await WaitFor(() => GodotObject.IsInstanceValid(overlay) &&
            overlay.GetNode<NClickableControl>("%MainMenuButton").IsEnabled, "native loss summary settled", capture);
        await NGame.Instance!.ReturnToMainMenuAfterRun();
    }

    private static async Task PaidCycle(CombatState state, CaseCapture capture, CaseSpec spec)
    {
        var player = state.Players.Single();
        var pcs = player.PlayerCombatState!;
        var turn = pcs.TurnNumber;
        bool threshold = spec.CaseId.StartsWith("threshold-");
        var targetId = spec.CaseId.Contains(':') ? spec.CaseId.Split(':')[1] :
            PaidTargets.Single(id => spec.CaseId == "paid-" + id + "-" + spec.Policy);
        var target = state.Enemies.Where(e => e.Monster!.Id.Entry == targetId && e.IsAlive)
            .OrderBy(e => e.CombatId).FirstOrDefault();
        // Explicit hand fixture only: no enemy HP/state/energy changes, no direct Engage or Domain calls.
        // Keeping the attacks non-damaging allows both exits of the two-state slime cycles to close twice.
        foreach (var existing in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(existing, PileType.Discard);
        async Task Play(CardModel card, Creature recipient)
        {
            await CardPileCmd.Add(card, PileType.Hand);
            if (!card.CanPlay(out _, out _) || !card.IsValidTarget(recipient))
            {
                capture.PaidAttempts.Add(new { seq = ++capture.Sequence, turn, targetId, cardId = card.Id.ToString(),
                    status = "NOT_PLAYABLE", reason = "native-preflight-rejected-no-payment-or-effect-claimed" });
                if (spec.CaseId.StartsWith("formal-")) return;
                throw new InvalidOperationException("Paid fixture cannot legally play " + card.Id);
            }
            var action = new PlayCardAction(card, recipient);
            var input = new Dictionary<string, object?> {
                ["seq"] = ++capture.Sequence, ["type"] = "PlayCardAction", ["actionRef"] = Ref(action),
                ["cardRef"] = Ref(card), ["cardId"] = card.Id.ToString(), ["targetRef"] = Ref(recipient),
                ["turnBefore"] = turn, ["roundBefore"] = state.RoundNumber, ["energyBefore"] = pcs.Energy,
                ["domainBefore"] = player.Creature.GetPowerAmount<DomainPower>(),
                ["enemiesBefore"] = state.Enemies.Select(CreatureSnapshot).ToArray(),
                ["cardsBefore"] = pcs.AllPiles.SelectMany(p => p.Cards).Select(c => new { cardRef = Ref(c), id = c.Id.ToString() }).ToArray(),
                ["status"] = "ENQUEUED", ["fixture"] = "created-card-hand-only" };
            capture.Inputs.Add(input);
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
            await WaitFor(() => action.CompletionTask.IsCompleted && Settled(capture) &&
                (capture.Ended || QuietPlay(state, turn)), "paid acceptance card", capture);
            await action.CompletionTask; // Fault/cancellation is not successful payment.
            input["completionObserved"] = true;
            input["energyAfter"] = player.PlayerCombatState?.Energy;
            input["domainAfter"] = player.Creature.GetPowerAmount<DomainPower>();
            input["pileAfter"] = card.Pile?.Type.ToString();
            input["enemiesAfter"] = state.Enemies.Select(CreatureSnapshot).ToArray();
            input["cardsAfter"] = pcs.AllPiles.SelectMany(p => p.Cards).Select(c => new { cardRef = Ref(c), id = c.Id.ToString() }).ToArray();
            input["endSeq"] = ++capture.Sequence;
            input["status"] = capture.Ended ? "TERMINAL" : "RETURNED_TO_PLAY";
        }
        if (spec.Policy.EndsWith("-on")) await Play(state.CreateCard<Volibear_C21>(player), player.Creature);
        if (capture.Ended) return;
        if (spec.Policy.Contains("-engage-"))
        {
            if (target is not null) await Play(threshold ? state.CreateCard<Volibear_C10>(player) : state.CreateCard<Volibear_C11>(player), target);
            else capture.PaidAttempts.Add(new { seq = ++capture.Sequence, turn, targetId,
                status = "NOT_OBSERVED", reason = "selected-model-not-live-this-cycle;no-forced-spawn" });
        }
        else if (threshold) await Play(state.CreateCard<Volibear_B01>(player), target ?? throw new InvalidOperationException("Threshold target absent"));
        else await Play(state.CreateCard<Volibear_B02>(player), player.Creature);
        // Formal paid fixtures spend the remaining fixed 3-energy budget on real C12s.
        // This is declared defensive input, not HP repair or a survival exemption.
        if (spec.CaseId.StartsWith("formal-") || threshold)
            for (int i = 0; i < (spec.Policy.EndsWith("-on") ? 1 : 2) && !capture.Ended; i++)
                if (threshold && !spec.Policy.Contains("-engage-")) await Play(state.CreateCard<Volibear_B01>(player), target!);
                else await Play(state.CreateCard<Volibear_C12>(player), player.Creature);
    }

    private static async Task<object> RunCase(int index, CaseSpec spec)
    {
        var caseClock = Stopwatch.StartNew();
        var manager = CombatManager.Instance;
        var run = RunManager.Instance;
        var capture = new CaseCapture(index) { AllowKnowledgeChoice = spec.CaseId.StartsWith("formal-") };
        var act = ModelDb.Acts.Single(a => a.Id.ToString() == spec.Act);
        var canonicalActs = ActModel.GetDefaultList().ToArray();
        canonicalActs[act.Index] = act; // Underdocks replaces slot zero; Hive/Glory never occupy slot zero.
        Stage("start-new-native-run:" + spec.CaseId, index);
        var character = ModelDb.Character<Content.VolibearCharacter>();
        var progress = SaveManager.Instance.Progress;
        var priorStats = progress.GetStatsForCharacter(character.Id);
        var priorBadgeEntries = priorStats?.Badges.Count ?? 0;
        // Native StartRunLobby.BeginRunLocally establishes this before BeginRun.
        // Our direct run API bypasses that lobby; shouldSave:false also skips the
        // end-run progress initializer. Restore only that missing fixture prerequisite.
        var characterStats = progress.GetOrCreateCharacterStats(character.Id);
        var fixturePreparation = new
        {
            source = "StartRunLobby.BeginRunLocally.GetOrCreateCharacterStats",
            reason = "direct-run-api-bypasses-lobby-and-shouldSave-false-skips-end-run-progress",
            characterId = character.Id.ToString(), statsExistedBefore = priorStats is not null,
            statsPresentAfter = ReferenceEquals(progress.GetStatsForCharacter(character.Id), characterStats),
            badgeEntriesBefore = priorBadgeEntries, badgeEntriesAfter = characterStats.Badges.Count,
            fixtureExplicitProgressSaveRequested = false
        };
        var runState = await NGame.Instance!.StartNewSingleplayerRun(character,
            shouldSave: false, canonicalActs, Array.Empty<ModifierModel>(), Seed, GameMode.Standard, ascensionLevel: 0);
        if (act.Index != 0) await run.EnterAct(act.Index, doTransition: false);
        _active = spec.Policy.StartsWith("paid-") ? capture : null;
        manager.CombatSetUp += capture.OnSetup;
        manager.TurnStarted += capture.OnTurn;
        manager.CombatEnded += capture.OnEnded;
        manager.CombatWon += capture.OnWon;
        manager.AboutToSwitchToEnemyTurn += capture.OnSwitch;
        manager.CreaturesChanged += capture.OnCreatures;
        manager.History.Changed += capture.OnHistoryChanged;
        var beforeRoomOwner = runState.Players.Single().Creature;
        var playerBeforeRoom = new { creatureRef = Ref(beforeRoomOwner), hp = beforeRoomOwner.CurrentHp, maxHp = beforeRoomOwner.MaxHp };
        var runIdentities = new { runRef = Ref(runState), playerRef = Ref(beforeRoomOwner.Player),
            playerCreatureRef = Ref(beforeRoomOwner), queueRef = Ref(run.ActionQueueSet),
            executorRef = Ref(run.ActionExecutor), choiceSyncRef = Ref(run.PlayerChoiceSynchronizer), runNodeRef = Ref(NRun.Instance) };
        object? initial = null, exit = null, terminal = null;
        string? error = null;
        var outcome = "FAILED";
        var requestedTurns = 0;
        var completedCycles = 0;
        var turnSlots = new List<object>();
        try
        {
            var encounter = EnemyCatalogProbe.ResolveEncounter(spec.Encounter);
            Stage("enter-native-room:" + spec.Encounter, index);
            await run.EnterRoomDebug(encounter.RoomType, model: encounter.ToMutable(), showTransition: false);
            await WaitFor(() => capture.State is { } s && (QuietPlay(s, 1) || capture.Ended && Settled(capture)), "first Play or terminal", capture);
            var state = capture.State!;
            if (!capture.Ended) { initial = Snapshot(state, capture); capture.Boundaries.Add(initial); }
            for (var step = 0; step < spec.TurnBudget && !capture.Ended; step++)
            {
                var player = state.Players.Single();
                var turn = player.PlayerCombatState!.TurnNumber;
                if (spec.Policy.StartsWith("paid-")) await PaidCycle(state, capture, spec);
                if (spec.Policy == "basic-paid-cards")
                {
                    for (var safety = 0; safety < 12 && !capture.Ended; safety++)
                    {
                        var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("Missing live player combat state.");
                        var card = pcs.Hand.Cards.FirstOrDefault(c =>
                            c.Id.Entry == "VOLIBEAR_B01" && c.CanPlay(out _, out _)) ??
                            pcs.Hand.Cards.FirstOrDefault(c => c.Id.Entry == "VOLIBEAR_B02" && c.CanPlay(out _, out _));
                        if (card is null) break;
                        var target = card.Id.Entry == "VOLIBEAR_B01"
                            ? state.Enemies.Where(e => e.IsAlive).OrderBy(e => e.CurrentHp).FirstOrDefault() : player.Creature;
                        if (target is null || !card.IsValidTarget(target)) break;
                        var play = new PlayCardAction(card, target);
                        var input = new Dictionary<string, object?> { ["seq"] = ++capture.Sequence,
                            ["type"] = "PlayCardAction", ["actionRef"] = Ref(play), ["cardRef"] = Ref(card),
                            ["cardId"] = card.Id.ToString(), ["targetRef"] = Ref(target), ["turnBefore"] = turn,
                            ["energyBefore"] = player.PlayerCombatState.Energy, ["status"] = "ENQUEUED" };
                        capture.Inputs.Add(input);
                        run.ActionQueueSynchronizer.RequestEnqueue(play);
                        await WaitFor(() => play.CompletionTask.IsCompleted && Settled(capture) &&
                            (capture.Ended || QuietPlay(state, turn)), "paid native card or terminal", capture);
                        input["completionObserved"] = play.CompletionTask.IsCompleted;
                        input["energyAfter"] = player.PlayerCombatState?.Energy;
                        input["status"] = capture.Ended ? "TERMINAL" : "RETURNED_TO_PLAY";
                    }
                }
                if (capture.Ended) break;
                var action = new EndPlayerTurnAction(player, turn);
                var request = new Dictionary<string, object?> { ["seq"] = ++capture.Sequence,
                    ["type"] = "EndPlayerTurnAction", ["actionRef"] = Ref(action),
                    ["turnBefore"] = turn, ["status"] = "ENQUEUED" };
                capture.Inputs.Add(request);
                requestedTurns++;
                run.ActionQueueSynchronizer.RequestEnqueue(action);
                await WaitFor(() => Settled(capture) && (capture.Ended ||
                    player.PlayerCombatState!.TurnNumber > turn && QuietPlay(state, player.PlayerCombatState.TurnNumber)),
                    "next Play or native terminal", capture);
                request["completionObserved"] = action.CompletionTask.IsCompleted;
                request["turnAfter"] = player.PlayerCombatState?.TurnNumber;
                request["status"] = capture.Ended ? "TERMINAL" : "RETURNED_TO_PLAY";
                turnSlots.Add(new { ordinal = step + 1, status = capture.Ended ? "TERMINAL" : "RETURNED_TO_PLAY" });
                if (!capture.Ended) { completedCycles++; capture.Boundaries.Add(Snapshot(state, capture)); }
            }
            for (var slot = requestedTurns + 1; slot <= spec.TurnBudget; slot++)
                turnSlots.Add(new { ordinal = slot, status = "NOT_OBSERVED" });
            outcome = capture.Ended ? capture.Won ? "WIN" : state.Players.All(p => p.Creature.IsDead) ? "LOSS" :
                throw new InvalidOperationException("Unclassified native CombatEnded") : "BUDGET_EXIT";
            terminal = new { seq = ++capture.Sequence, outcome, combatRef = Ref(state),
                combatEnded = capture.Ended, combatWon = capture.Won, inProgress = manager.IsInProgress,
                player = CreatureSnapshot(state.Players.Single().Creature),
                presentEnemies = state.Enemies.Select(CreatureSnapshot).ToArray(),
                nativeHistoryVisible = manager.History.Entries.Count(), exportedHistory = capture.History.Count,
                queueEmpty = run.ActionQueueSet.IsEmpty, runningActionRef = Ref(run.ActionExecutor.CurrentlyRunningAction),
                pendingChoices = PendingChoices() };
            var expectedMismatch = spec.ExpectedOutcome != "ANY" && outcome != spec.ExpectedOutcome
                ? "Expected " + spec.ExpectedOutcome + ", actual " + outcome : null;
            Stage("native-exit:" + outcome, index);
            if (outcome == "BUDGET_EXIT")
            {
                capture.BudgetExit = true;
                await run.EnterRoom(new MapRoom());
                await Frame();
                await NGame.Instance.ReturnToMainMenu();
            }
            else if (outcome == "LOSS") await CloseLossUi(capture);
            else await NGame.Instance.ReturnToMainMenu();
            await Frame();
            exit = AfterExit();
            if (expectedMismatch is not null) throw new InvalidOperationException(expectedMismatch);
        }
        catch (Exception exception) { error = exception.ToString(); }
        finally
        {
            if (ReferenceEquals(_active, capture)) _active = null;
            manager.CombatSetUp -= capture.OnSetup; manager.TurnStarted -= capture.OnTurn;
            manager.CombatEnded -= capture.OnEnded; manager.CombatWon -= capture.OnWon;
            manager.AboutToSwitchToEnemyTurn -= capture.OnSwitch; manager.CreaturesChanged -= capture.OnCreatures;
            manager.History.Changed -= capture.OnHistoryChanged;
        }
        var result = new
        {
            caseId = spec.CaseId, processId = System.Environment.ProcessId, policy = spec.Policy,
            paidStrategy = spec.CaseId.StartsWith("threshold-") ? "C21-if-domain;C10-plus-C12-or-three-B01;fixed-3-energy-budget" :
                spec.CaseId.StartsWith("formal-") ? "C21-if-domain;C11-or-B02;C12-fixed-remaining-3-energy-budget" : null,
            elapsedMs = caseClock.ElapsedMilliseconds,
            seed = runState.Rng.StringSeed, numericSeed = runState.Rng.Seed,
            act = runState.Act.Id.ToString(), actIndex = runState.CurrentActIndex,
            acts = runState.Acts.Select(a => new { id = a.Id.ToString(), index = a.Index }).ToArray(),
            ascension = runState.AscensionLevel, encounter = capture.State?.Encounter?.Id.ToString(),
            roomType = capture.State?.Encounter?.RoomType.ToString(), turnBudget = spec.TurnBudget,
            outcome, error, fixturePreparation, runIdentities, playerBeforeRoom, initial, boundaries = capture.Boundaries, terminal, requestedTurns, completedCycles, turnSlots,
            inputs = capture.Inputs, paidAttempts = capture.PaidAttempts, choiceInputs = capture.ChoiceInputs,
            nativeHistory = capture.History, historyClears = capture.Clears, moveWindows = capture.MoveWindows,
            turnSignals = capture.Turns, terminalSignals = capture.TerminalSignals, sideSwitches = capture.SideSwitches,
            creatureChanges = capture.CreatureChanges, opportunities = capture.Opportunities, afterExit = exit,
            unobservedMeaning = "NOT_OBSERVED-is-not-skipped-or-verified", observationError = capture.ObservationError?.ToString()
        };
        if (error is not null) throw new CaseFailedException(result, error);
        return result;
    }

    private sealed class CaseFailedException(object result, string message) : Exception(message)
    { internal readonly object Result = result; }

    private static async Task Coordinate(CombatState warmup)
    {
        var cases = new List<object>();
        string? failure = null, selectionHash = null;
        Selection? selection = null;
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        var directory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ARTIFACT_DIR");
        var release = ReleaseInfoManager.Instance.ReleaseInfo;
        try
        {
            if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(directory) ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn || release?.Version != "v0.107.1" || release.Commit != "59260271")
                throw new InvalidOperationException("Pinned native isolated environment required.");
            selection = ReadSelection(out selectionHash);
            await Frame();
            await WaitFor(() => QuietPlay(warmup, warmup.Players.Single().PlayerCombatState!.TurnNumber), "warmup quiescence");
            await RunManager.Instance.EnterRoom(new MapRoom());
            await NGame.Instance!.ReturnToMainMenu();
            await Frame();
            for (var index = 0; index < selection.Cases.Length; index++)
            {
                cases.Add(await RunCase(index + 1, selection.Cases[index]));
                GD.Print("[Volibear] ENEMY_EXPLORATION_CASE_COMPLETE " + selection.Cases[index].CaseId);
            }
        }
        catch (CaseFailedException error) { cases.Add(error.Result); failure = error.ToString(); }
        catch (Exception error) { failure = error.ToString(); }
        try
        {
            if (string.IsNullOrWhiteSpace(directory)) throw new InvalidOperationException("Missing artifacts.");
            var registered = ModelDb.Acts.SelectMany(a => a.AllEncounters).Where(e => !e.IsDebugEncounter)
                .Select(e => e.Id.ToString()).Distinct().Order().ToArray();
            var manifest = new
            {
                schema = 1, token, scenario = "enemy-exploration", acceptance = "bounded-native-exploration-only",
                processId = System.Environment.ProcessId, gameVersion = release?.Version, gameCommit = release?.Commit,
                gameAssemblyMvid = typeof(ModelDb).Assembly.ManifestModule.ModuleVersionId,
                modAssemblyMvid = typeof(EnemyExplorationProbe).Assembly.ManifestModule.ModuleVersionId,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, selection, selectionSha256 = selectionHash,
                warmup = new { combatRef = Ref(warmup), includedInCases = false },
                registeredEncounterIds = registered, eventOnlyStatus = "EVENT_SETUP_REQUIRED_NOT_RUN",
                enemyHpModified = false, playerHpModified = false, forcedMoves = false, directPerformMoveCalls = 0,
                completeAiCoverage = false, physicalInputValidated = false,
                cleanupUiPolicy = "native-enabled-gameover-continue-ForceClick-then-ReturnToMainMenuAfterRun;not-physical-input",
                runFlowAcceptance = "fixture-bypasses-ancient-choices-and-timeline",
                unexecutedSelectedCases = selection?.Cases.Skip(cases.Count)
                    .Select(c => new { c.CaseId, status = "NOT_RUN" }).ToArray(), cases, failure
            };
            var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(manifest, new JsonSerializerOptions
                { WriteIndented = true, PropertyNamingPolicy = JsonNamingPolicy.CamelCase }) + "\n");
            Directory.CreateDirectory(directory);
            File.WriteAllBytes(Path.Combine(directory, "enemy-exploration.json"), bytes);
            GD.Print("[Volibear] ENEMY_EXPLORATION_RESULT " + JsonSerializer.Serialize(new
            {
                token, scenario = "enemy-exploration", acceptance = "bounded-native-exploration-only",
                manifest = "enemy-exploration.json", bytes = bytes.Length,
                sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                caseCount = cases.Count, completed = failure is null, failure
            }));
            if (failure is not null) GD.PrintErr("[Volibear] ENEMY_EXPLORATION_ERROR " + failure);
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            Refs.Clear(); warmup = null!;
            NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(failure is null ? 0 : 2);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] ENEMY_EXPLORATION_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
