using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.AutoSlay.Helpers;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using Volibear.Content;

namespace Volibear;

/// <summary>
/// A real seeded run, driven through native action/choice/synchronizer APIs.
/// No injected cards, HP, gold, forced victory, debug-room travel or input events.
/// Card-case fixtures do not count as this run; death or missing room coverage fails.
/// </summary>
internal static class NativeProductFlowProbe
{
    private static readonly List<JsonElement> Events = [];
    private static readonly HashSet<AbstractRoom> Rooms = new(ReferenceEqualityComparer.Instance);
    private static readonly HashSet<AbstractRoom> HandledRooms = new(ReferenceEqualityComparer.Instance);
    private static readonly HashSet<Reward> AttemptedRewards = new(ReferenceEqualityComparer.Instance);
    private static readonly HashSet<NRewardsScreen> InFlightRewards = new(ReferenceEqualityComparer.Instance);
    private static int wins, cardsTaken, restChoices, purchases, historyStart;
    private static PlayCardAction? currentPlay;
    private static JsonElement? historyBeforeClear;
    private static Task? pendingEvent, pendingChest;
    private static AbstractRoom? chestRoom;
    private static Selector? flowSelector;
    // These two locked-game members have no public equivalent. They are native
    // room orchestration/read-only state, never button callbacks or input signals.
    private static readonly MethodInfo OpenChest = typeof(NTreasureRoom).GetMethod("OpenChest", BindingFlags.Instance | BindingFlags.NonPublic,
        null, Type.EmptyTypes, null) ?? throw new MissingMethodException(typeof(NTreasureRoom).FullName, "OpenChest");
    private static readonly FieldInfo TerminalRewards = typeof(NRewardsScreen).GetField("_isTerminal", BindingFlags.Instance | BindingFlags.NonPublic)
        ?? throw new MissingFieldException(typeof(NRewardsScreen).FullName, "_isTerminal");
    private static SceneTree Tree => (SceneTree)Engine.GetMainLoop();
    private static Player Player => RunManager.Instance.DebugOnlyGetState()!.Players.Single();
    private static async Task Frame() => await Tree.ToSignal(Tree, SceneTree.SignalName.ProcessFrame);
    private static void Need(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
    private static void Record(string kind, object data) => Events.Add(JsonSerializer.SerializeToElement(new { seq = Events.Count, kind, data }));
    private static IEnumerable<T> Find<T>(Node? node = null) where T : Node => UiHelper.FindAll<T>(node ?? Tree.Root);
    private static bool Usable(NClickableControl? node) => node is not null && GodotObject.IsInstanceValid(node) && node.IsInsideTree() && node.IsVisibleInTree() && node.IsEnabled;
    private static object Snapshot()
    {
        var run = RunManager.Instance.DebugOnlyGetState()!; var p = run.Players.Single();
        return new { character = p.Character.Id.Entry, seed = run.Rng.StringSeed, hp = p.Creature.CurrentHp, maxHp = p.Creature.MaxHp,
            gold = p.Gold, floor = run.TotalFloor, act = run.CurrentActIndex, room = run.CurrentRoom?.GetType().Name,
            energy = p.PlayerCombatState?.Energy,
            shouldSave = RunManager.Instance.ShouldSave,
            deck = p.Deck.Cards.Select(c => new { id = c.Id.Entry, upgrade = c.CurrentUpgradeLevel }).ToArray(),
            relics = p.Relics.Select(r => r.Id.Entry).ToArray() };
    }
    private static async Task Wait(Func<bool> condition, string label, int seconds = 90)
    {
        var clock = Stopwatch.StartNew();
        while (!condition())
        {
            if (clock.Elapsed.TotalSeconds > seconds) throw new TimeoutException(label);
            await Frame();
        }
    }
    private static async Task CompleteDecision(Task operation, string label)
    {
        var clock = Stopwatch.StartNew();
        while (!operation.IsCompleted)
        {
            Need(clock.Elapsed.TotalSeconds < 90, label + " timed out");
            // Native rest/relic/event hooks can offer a nested reward set. Its
            // real synchronizer must finish before the originating task returns.
            if (!await RewardsStep()) await Frame();
        }
        await operation;
    }
    private static JsonElement History() => JsonSerializer.SerializeToElement(new {
        plays = CombatManager.Instance.History.Entries.Skip(historyStart).OfType<CardPlayStartedEntry>().Select(e => new {
            id = e.CardPlay.Card.Id.Entry, autoPlay = e.CardPlay.IsAutoPlay, spent = e.CardPlay.Resources.EnergySpent,
            index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
        energy = CombatManager.Instance.History.Entries.Skip(historyStart).OfType<EnergySpentEntry>().Select(e => e.Amount).ToArray()
    });
    private static void BeforeHistoryClear(CombatHistory __instance)
    {
        if (currentPlay is not null && ReferenceEquals(__instance, CombatManager.Instance.History)) historyBeforeClear = History();
    }
    private static void Won(CombatRoom room)
    {
        wins++;
        Record("battle-win", new { number = wins, encounter = room.Encounter.Id.Entry, state = Snapshot() });
    }

    // In 0.107.1 CardReward always creates a screen outside TestMode; that
    // screen's OptionSelected task does not consult CardSelectCmd.Selector.
    // Supply only this decision at its real async boundary. Native CardReward
    // still reserves/synchronizes the choice, adds the selected candidate to the
    // deck and records history. No screen/button callback is invoked or forged.
    private static bool RewardChoicePrefix(NCardRewardSelectionScreen __instance,
        IReadOnlyList<CardCreationResult> ____options,
        IReadOnlyList<CardRewardAlternative> ____extraOptions, ref Task<int?> __result)
    {
        if (flowSelector is null) return true;
        __result = RewardDecision(__instance, ____options, ____extraOptions);
        return false;
    }
    private static async Task<int?> RewardDecision(NCardRewardSelectionScreen screen,
        IReadOnlyList<CardCreationResult> options, IReadOnlyList<CardRewardAlternative> alternatives)
    {
        await Wait(() => GodotObject.IsInstanceValid(screen) && screen.IsNodeReady(), "Native card reward screen not ready");
        await Frame();
        Need(flowSelector is not null && ReferenceEquals(CardSelectCmd.Selector, flowSelector), "Reward decision lost its native selector");
        var choice = flowSelector!.GetSelectedCardReward(options, alternatives);
        int index = options.ToList().FindIndex(o => ReferenceEquals(o.Card, choice.card));
        Need(index >= 0 && choice.alternative is null, "Controlled reward decision is outside native candidates");
        return index;
    }

    private sealed class Selector : ICardSelector, IDisposable
    {
        private readonly Player owner;
        private readonly IDisposable scope;
        internal Selector(Player owner)
        {
            Need(!TestMode.IsOn && CardSelectCmd.Selector is null, "Controlled flow needs an exclusive native selector");
            this.owner = owner; scope = CardSelectCmd.UseSelector(this);
        }
        public Task<IEnumerable<CardModel>> GetSelectedCards(IEnumerable<CardModel> options, int minSelect, int maxSelect)
        {
            var candidates = options.ToArray();
            Need(ReferenceEquals(CardSelectCmd.Selector, this) && minSelect >= 0 && maxSelect >= minSelect &&
                minSelect <= candidates.Length && candidates.Distinct(ReferenceEqualityComparer.Instance).Count() == candidates.Length &&
                candidates.All(c => ReferenceEquals(c.Owner, owner)), "Invalid controlled-flow card candidates");
            var selected = candidates.Take(minSelect).ToArray();
            Record("selection", new { min = minSelect, max = maxSelect, available = candidates.Select(c => c.Id.Entry).ToArray(), selected = selected.Select(c => c.Id.Entry).ToArray() });
            return Task.FromResult<IEnumerable<CardModel>>(selected);
        }
        public CardRewardSelection GetSelectedCardReward(IReadOnlyList<CardCreationResult> options, IReadOnlyList<CardRewardAlternative> alternatives)
        {
            Need(ReferenceEquals(CardSelectCmd.Selector, this) && options.Count > 0, "Native card reward has no selectable cards");
            var card = options.Select(o => o.Card).OrderBy(c => c.Type == CardType.Power ? 0 : c.Type == CardType.Attack ? 1 : 2)
                .ThenBy(c => c.EnergyCost.Canonical).ThenBy(c => c.Id.Entry, StringComparer.Ordinal).First();
            Record("card-reward-choice", new { available = options.Select(o => o.Card.Id.Entry).ToArray(), selected = card.Id.Entry });
            return new CardRewardSelection { card = card };
        }
        public void Dispose()
        {
            // Native combat/run cleanup may already have reset this exact scope.
            Need(CardSelectCmd.Selector is null || ReferenceEquals(CardSelectCmd.Selector, this), "Another selector replaced the controlled flow scope");
            scope.Dispose(); Need(CardSelectCmd.Selector is null, "Native selector leaked after controlled flow decision");
        }
    }

    private static async Task CombatStep(CombatState state)
    {
        if (!NativeAcceptanceRunHost.IsQuiet(state)) { await Frame(); return; }
        var p = state.Players.Single(); var pcs = p.PlayerCombatState!;
        var card = pcs.Hand.Cards.Where(c => c.CanPlay(out _, out _) &&
            (c.IsValidTarget(null) || state.Enemies.Any(e => e.IsAlive && c.IsValidTarget(e))))
            .OrderBy(c => c.Type == CardType.Power ? 0 : c.Type == CardType.Attack ? 1 : 2)
            .ThenBy(c => c.EnergyCost.GetWithModifiers(CostModifiers.All)).ThenBy(c => c.Id.Entry, StringComparer.Ordinal).FirstOrDefault();
        if (card is null)
        {
            int turn = pcs.TurnNumber; int round = state.RoundNumber;
            PlayerCmd.EndTurn(p, canBackOut: false);
            Record("end-turn", new { round, turn });
            await Wait(() => !CombatManager.Instance.IsInProgress || p.PlayerCombatState?.TurnNumber != turn,
                "Native end-turn did not reach the next turn");
            return;
        }
        Creature? target = card.IsValidTarget(null) ? null : state.Enemies.Where(e => e.IsAlive && card.IsValidTarget(e)).OrderBy(e => e.CurrentHp).ThenBy(e => e.CombatId).First();
        historyStart = CombatManager.Instance.History.Entries.Count(); historyBeforeClear = null;
        var before = Snapshot(); var cost = card.EnergyCost.GetWithModifiers(CostModifiers.All);
        var action = new PlayCardAction(card, target); currentPlay = action;
        try
        {
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
            await CompleteDecision(action.CompletionTask, "Native paid run action");
            var history = historyBeforeClear ?? History();
            Record("paid-action", new { id = card.Id.Entry, actionId = action.Id, type = action.GetType().Name,
                state = action.State.ToString(), context = action.PlayerChoiceContext?.GetType().Name,
                exception = action.Exception?.ToString(), target = target?.CombatId, costBefore = cost,
                before, after = Snapshot(), history });
            Need(action.Exception is null && history.GetProperty("plays").EnumerateArray().Any(e =>
                e.GetProperty("id").GetString() == card.Id.Entry && !e.GetProperty("autoPlay").GetBoolean()),
                "Native run request did not produce a real paid card play");
        }
        finally { currentPlay = null; }
    }

    private static async Task<bool> RewardsStep()
    {
        if (NOverlayStack.Instance?.Peek() is not NRewardsScreen screen) return false;
        if (InFlightRewards.Contains(screen)) return false;
        foreach (var button in Find<NRewardButton>(screen).Where(b => Usable(b) && !AttemptedRewards.Contains(b.Reward)).ToArray())
        {
            var reward = button.Reward;
            if (reward is PotionReward && !Player.HasOpenPotionSlots) { AttemptedRewards.Add(reward); continue; }
            AttemptedRewards.Add(reward); var before = Snapshot();
            bool selected;
            InFlightRewards.Add(screen);
            try
            {
                var choice = RunManager.Instance.RewardsSetSynchronizer.SelectLocalReward(reward);
                await CompleteDecision(choice, "Native reward selection"); selected = await choice;
            }
            finally { InFlightRewards.Remove(screen); }
            Need(selected && reward.SuccessfullySelected, "Native reward selection was not committed");
            if (reward is CardReward) cardsTaken++;
            Record("reward", new { type = reward.GetType().Name, selected, nativeSelected = reward.SuccessfullySelected, before, after = Snapshot() });
            // Native notification after the real synchronized command, not a button event.
            Node? parent = button.GetParent();
            while (parent is not null && parent != screen && parent is not NLinkedRewardSet) parent = parent.GetParent();
            if (parent is NLinkedRewardSet linked)
            {
                // The screen owns the linked group, not its child button. Mark
                // the unchosen alternatives skipped through the native reward.
                screen.RewardCollectedFrom(linked); linked.LinkedRewardSet.OnSkipped();
            }
            else screen.RewardCollectedFrom(button);
            await Frame(); return true;
        }
        var proceed = Find<MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton>(screen).FirstOrDefault(Usable);
        if (proceed is null) { await Frame(); return true; }
        Need(TerminalRewards.FieldType == typeof(bool), "Pinned native reward-screen contract changed");
        bool terminal = (bool)TerminalRewards.GetValue(screen)!;
        if (!terminal)
        {
            RunManager.Instance.RewardsSetSynchronizer.SkipLocalRewardsSet();
            NOverlayStack.Instance.Remove(screen);
            return true;
        }
        var run = RunManager.Instance.DebugOnlyGetState()!;
        if ((run.CurrentRoom.RoomType == RoomType.Boss || run.CurrentRoom.IsVictoryRoom) &&
            !(run.Map.SecondBossMapPoint is not null && run.CurrentMapCoord == run.Map.BossMapPoint.coord))
            RunManager.Instance.ActChangeSynchronizer.SetLocalPlayerReady();
        else await RunManager.Instance.ProceedFromTerminalRewardsScreen();
        await Wait(() => NMapScreen.Instance?.IsOpen == true || NOverlayStack.Instance?.Peek() is not NRewardsScreen,
            "Native reward completion did not open the map or resume its event");
        return true;
    }

    private static async Task MapStep()
    {
        var run = RunManager.Instance.DebugOnlyGetState()!; var map = NMapScreen.Instance!;
        var points = Find<NMapPoint>(map).ToArray();
        var current = run.VisitedMapCoords.Count == 0 ? null : points.SingleOrDefault(p => p.Point.coord.Equals(run.VisitedMapCoords[^1]));
        var legal = points.Where(p => p.IsEnabled && p.IsVisibleInTree() &&
            (current is null ? p.Point.coord.Equals(run.Map.StartingMapPoint.coord) : current.Point.Children.Contains(p.Point))).ToArray();
        if (legal.Length == 0) { await Frame(); return; }
        // Look ahead on the actual generated graph, with no map edits. Choosing
        // the first available rest may otherwise strand the route away from shops.
        var memo = new Dictionary<(NMapPoint, int), int>();
        int RouteCost(NMapPoint point, int missing)
        {
            if (memo.TryGetValue((point, missing), out int cached)) return cached;
            string kind = point.Point.PointType.ToString();
            int remaining = missing & ~(kind == "RestSite" ? 1 : kind == "Shop" ? 2 : 0);
            if (remaining == 0) return 0;
            var children = points.Where(p => point.Point.Children.Contains(p.Point)).ToArray();
            int cost = kind == "Elite" ? 40 : kind == "Monster" ? 2 : 1;
            int result = children.Length == 0 ? 10000 : cost + children.Min(p => RouteCost(p, remaining));
            memo[(point, missing)] = result; return result;
        }
        int needed = (restChoices == 0 ? 1 : 0) | (purchases == 0 ? 2 : 0);
        var next = legal.OrderBy(p => RouteCost(p, needed))
            .ThenBy(p => p.Point.PointType.ToString() == "Monster" && wins < 3 ? 0 : 1)
            .ThenBy(p => p.Point.PointType.ToString() == "Elite" ? 1 : 0).ThenBy(p => p.Point.coord.col).First();
        Record("map-choice", new { act = run.CurrentActIndex, fromRow = current?.Point.coord.row, fromCol = current?.Point.coord.col,
            row = next.Point.coord.row, col = next.Point.coord.col, type = next.Point.PointType.ToString(),
            legal = legal.Select(p => new { row = p.Point.coord.row, col = p.Point.coord.col }).ToArray() });
        var prior = run.CurrentRoom;
        // Public native entry constructs VoteForMapCoordAction and enqueues it.
        // It does not emit input/pressed signals or teleport to a debug room.
        map.OnMapPointSelectedLocally(next);
        await Wait(() => run.CurrentRoom is not null && !ReferenceEquals(run.CurrentRoom, prior) &&
            run.CurrentMapCoord == next.Point.coord && RunManager.Instance.ActionQueueSet.IsEmpty &&
            RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null, "Native map vote did not enter the chosen room");
        Record("map-arrived", new { row = run.CurrentMapCoord?.row, col = run.CurrentMapCoord?.col,
            act = run.CurrentActIndex, state = Snapshot() });
    }

    private static async Task RoomStep(AbstractRoom room)
    {
        if (room.RoomType == RoomType.RestSite)
        {
            var view = NRestSiteRoom.Instance; if (view is null) { await Frame(); return; }
            if (!HandledRooms.Contains(room))
            {
                var options = RunManager.Instance.RestSiteSynchronizer.GetLocalOptions();
                var legal = options.Select((option, index) => new { option, index }).Where(x => x.option.IsEnabled).ToArray();
                if (legal.Length == 0) { await Frame(); return; }
                var desired = Player.Creature.CurrentHp < Player.Creature.MaxHp * 0.7m ? "HEAL" : "SMITH";
                var selected = legal.OrderBy(x => x.option.OptionId == desired ? 0 : 1).ThenBy(x => x.index).First();
                view.DisableOptions();
                var before = Snapshot(); var choice = RunManager.Instance.RestSiteSynchronizer.ChooseLocalOption(selected.index);
                await CompleteDecision(choice, "Native rest option"); bool ok = await choice;
                Need(ok, "Native rest option did not complete");
                view.AfterSelectingOption(selected.option); restChoices++; HandledRooms.Add(room);
                Record("rest", new { option = selected.option.OptionId, index = selected.index, available = legal.Select(x => x.index).ToArray(), ok, before, after = Snapshot() });
            }
            if (Usable(view.ProceedButton)) NMapScreen.Instance!.Open();
            return;
        }
        if (room.RoomType == RoomType.Shop)
        {
            var view = Find<NMerchantRoom>().FirstOrDefault(); if (view is null) { await Frame(); return; }
            if (!HandledRooms.Contains(room))
            {
                if (!view.Inventory.IsOpen) { view.OpenInventory(); await Frame(); return; }
                // Buy a native card entry: no potion-capacity cancellation and no
                // removal of the attack needed to finish this ordinary run.
                var slot = view.Inventory.GetAllSlots().Where(s => s.Entry is MerchantCardEntry && s.Entry.IsStocked && s.Entry.EnoughGold)
                    .OrderBy(s => s.Entry.Cost).FirstOrDefault();
                Need(slot is not null, "Normal route reached a shop without an affordable card; purchase coverage missing");
                var before = Snapshot(); int goldBefore = Player.Gold, cost = slot!.Entry.Cost; bool stockedBefore = slot.Entry.IsStocked;
                var purchase = slot.Entry.OnTryPurchaseWrapper(view.Inventory.Inventory);
                await CompleteDecision(purchase, "Native shop purchase"); bool bought = await purchase;
                Need(bought && goldBefore - Player.Gold == cost && cost > 0, "Shop purchase did not charge native gold");
                purchases++; HandledRooms.Add(room);
                Record("shop", new { type = slot.Entry.GetType().Name, cost, stockedBefore, bought, before, after = Snapshot() });
            }
            NMapScreen.Instance!.Open(); return;
        }
        if (room.RoomType == RoomType.Event)
        {
            // Event handlers may await an embedded combat or rewards screen. Keep
            // the native task alive while the main loop services those states.
            if (pendingEvent is not null)
            {
                if (!pendingEvent.IsCompleted) { await Frame(); return; }
                await pendingEvent; pendingEvent = null;
            }
            var options = Find<NEventOptionButton>().Where(b => Usable(b) && !b.Option.IsLocked &&
                (b.Option.WillKillPlayer is null || b.Event.Owner is null || !b.Option.WillKillPlayer(b.Event.Owner))).ToArray();
            if (options.Length == 0) { await Frame(); return; }
            var option = options[0]; var before = Snapshot();
            int index = option.Event.CurrentOptions.ToList().FindIndex(o => ReferenceEquals(o, option.Option));
            Need(index >= 0 || option.Option.IsProceed, "Native event option is no longer on the current page");
            if (option.Option.IsProceed) pendingEvent = option.Option.Chosen();
            else
            {
                RunManager.Instance.EventSynchronizer.ChooseLocalOption(index);
                pendingEvent = RunManager.Instance.EventSynchronizer.AwaitPendingOptionTasks();
            }
            Record("event", new { key = option.Option.TextKey, index, before, after = Snapshot() });
            await Frame(); return;
        }
        if (room.RoomType == RoomType.Treasure)
        {
            if (!ReferenceEquals(chestRoom, room))
            {
                var view = Find<NTreasureRoom>().FirstOrDefault();
                if (view is null) { await Frame(); return; }
                Need(OpenChest.ReturnType == typeof(Task), "Pinned native chest command contract changed");
                chestRoom = room;
                pendingChest = (Task)OpenChest.Invoke(view, null)!;
                return;
            }
            if (!HandledRooms.Contains(room))
            {
                var sync = RunManager.Instance.TreasureRoomRelicSynchronizer;
                var collection = Find<NTreasureRoomRelicCollection>().FirstOrDefault(c => c.IsVisibleInTree());
                if (collection is null || sync.CurrentRelics is null || sync.CurrentRelics.Count == 0)
                {
                    if (pendingChest?.IsCompleted == true) { await pendingChest; HandledRooms.Add(room); }
                    await Frame(); return;
                }
                int before = Player.Relics.Count; sync.PickRelicLocally(0);
                await Wait(() => Player.Relics.Count > before, "Native treasure selection did not award a relic");
                HandledRooms.Add(room); Record("treasure", new { relicsBefore = before, state = Snapshot() });
            }
            if (pendingChest?.IsCompleted == true) { await pendingChest; NMapScreen.Instance!.Open(); }
            return;
        }
        if (room is CombatRoom && Usable(NCombatRoom.Instance?.ProceedButton))
        { await RunManager.Instance.ProceedFromTerminalRewardsScreen(); return; }
        if (room is MapRoom) { NMapScreen.Instance!.Open(); return; }
        await Frame();
    }
    internal static async Task Run()
    {
        string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        string outcome = "failed"; string? error = null;
        Events.Clear(); Rooms.Clear(); HandledRooms.Clear(); AttemptedRewards.Clear(); InFlightRewards.Clear();
        wins = cardsTaken = restChoices = purchases = 0;
        pendingEvent = pendingChest = null; chestRoom = null; flowSelector = null;
        var observer = new Harmony("Volibear.NativeProductFlow.HistoryObservation");
        try
        {
            Need(token.Length > 0 && !TestMode.IsOn, "Missing controlled flow identity or real native mode");
            NativeAcceptanceRunHost.RequireClean();
            observer.Patch(AccessTools.Method(typeof(CombatHistory), nameof(CombatHistory.Clear)),
                prefix: new HarmonyMethod(typeof(NativeProductFlowProbe), nameof(BeforeHistoryClear)));
            observer.Patch(AccessTools.Method(typeof(NCardRewardSelectionScreen), nameof(NCardRewardSelectionScreen.OptionSelected)),
                prefix: new HarmonyMethod(typeof(NativeProductFlowProbe), nameof(RewardChoicePrefix)));
            CombatManager.Instance.CombatWon += Won;
            var character = ModelDb.Character<VolibearCharacter>();
            SaveManager.Instance.Progress.GetOrCreateCharacterStats(character.Id);
            SaveManager.Instance.SetFtuesEnabled(false);
            var run = await NGame.Instance!.StartNewSingleplayerRun(character, false, ActModel.GetDefaultList().ToArray(),
                Array.Empty<ModifierModel>(), "VOLIBEAR-PRODUCT-FLOW", GameMode.Standard, 0);
            Record("run-start", Snapshot());
            var clock = Stopwatch.StartNew();
            using (var selector = new Selector(Player))
            {
                flowSelector = selector;
                while (true)
                {
                    Need(clock.Elapsed.TotalMinutes < 35 && Events.Count < 20000, "Controlled native run exceeded its finite budget");
                    Need(RunManager.Instance.IsInProgress && Player.Creature.IsAlive, "Native run died or ended before required product coverage");
                    var room = run.CurrentRoom;
                    if (room is not null && Rooms.Add(room)) Record("room", Snapshot());
                    if (CombatManager.Instance.IsInProgress && CombatManager.Instance.DebugOnlyGetState() is CombatState state)
                        await CombatStep(state);
                    else if (NMapScreen.Instance?.IsOpen == true)
                    {
                        if (wins >= 3 && cardsTaken >= 1 && restChoices >= 1 && purchases >= 1)
                        {
                            if (pendingEvent is not null) await pendingEvent;
                            if (pendingChest is not null) await pendingChest;
                            outcome = "completed"; break;
                        }
                        await MapStep();
                    }
                    else if (await RewardsStep()) { }
                    else if (room is not null) await RoomStep(room);
                    await Frame();
                }
                flowSelector = null;
            }
            await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);
        }
        catch (Exception exception) { error = exception.ToString(); throw; }
        finally
        {
            currentPlay = null; flowSelector = null; CombatManager.Instance.CombatWon -= Won; observer.UnpatchAll(observer.Id);
            var release = ReleaseInfoManager.Instance.ReleaseInfo;
            GD.Print("[Volibear] NATIVE_PRODUCT_FLOW_RESULT " + JsonSerializer.Serialize(new {
                schema = 1, token, pid = Environment.ProcessId, gameVersion = release?.Version.TrimStart('v'), gameCommit = release?.Commit,
                scope = "native-seeded-run-paid-actions-rewards-map-rest-shop", osInput = false, simulatedClicks = false,
                stateFixtures = false, testMode = TestMode.IsOn, rewardDecisionBoundary = "NCardRewardSelectionScreen.OptionSelected",
                outcome, error, events = Events.ToArray()
            }));
        }
    }
}
