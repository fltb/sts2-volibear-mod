using System;
using MegaCrit.Sts2.Core.Combat.History;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.AutoSlay;
using MegaCrit.Sts2.Core.AutoSlay.Helpers;
using MegaCrit.Sts2.Core.AutoSlay.Handlers;
using MegaCrit.Sts2.Core.AutoSlay.Handlers.Screens;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Debug;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CharacterSelect;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.PauseMenu;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;
using MegaCrit.Sts2.Core.Platform.Steam;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Managers;
using MegaCrit.Sts2.Core.TestSupport;

namespace Volibear;

/// <summary>Normal-menu, legal paid-action driver. No bootstrap, selector override, OS input or game-state fixtures.
/// Install only for isolated native-run. Death and unsupported screens remain failures, never S09 completion.</summary>
internal static class NativeRunAcceptanceProbe
{
    private sealed record Identity(int Value);
    private static readonly ConditionalWeakTable<object, Identity> Ids = new();
    private static int _nextId, _wins, _lastEndRound = -1, _lastEndCombat;
    private static bool _installed, _active, _isolated;
    private static string? _bootstrapType = "not-observed";
    private static string _token = "missing", _mode = "", _pair = "";
    private static readonly List<JsonElement> Events = [];
    private static readonly List<object> Payments = [];
    private static readonly HashSet<int> SeenCombats = [], SeenRooms = [], UsedRest = [], UsedShop = [];
    private static readonly Rng PolicyRandom = new(314159u); // Choice RNG only; never the run/loot RNG.
    private static readonly Stopwatch Clock = new();
    private static PlayCardAction? _play;
    private static CardModel? _card;
    private static CombatState? _playCombat;
    private static JsonElement _playBefore;
    private static int _historyStart, _cost;
    private static JsonElement? _historyBeforeClear;
    private static JsonElement PlayHistory(CombatHistory history) => JsonSerializer.SerializeToElement(new {
        plays = history.Entries.Skip(_historyStart).OfType<CardPlayStartedEntry>().Select(e => new { entity = Id(e.CardPlay.Card), id = e.CardPlay.Card.Id.Entry,
            autoPlay = e.CardPlay.IsAutoPlay, spent = e.CardPlay.Resources.EnergySpent, index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
        energy = history.Entries.Skip(_historyStart).OfType<EnergySpentEntry>().Select(e => e.Amount).ToArray() });
    private static void BeforeHistoryClear(CombatHistory __instance)
    {
        if (_active && _play is not null && ReferenceEquals(__instance, CombatManager.Instance.History))
            _historyBeforeClear = PlayHistory(__instance); // Observe BEFORE native victory clears real history; never suppress Clear.
    }
    private static Task? _purchase;
    private static JsonElement _purchaseBefore;
    private static string _purchaseKind = "";
    private static int _purchaseCost;
    private static double _pendingAt;
    private static int Id(object? value) => value is null ? 0 : Ids.GetValue(value, _ => new Identity(++_nextId)).Value;
    private static string Env(string key) => System.Environment.GetEnvironmentVariable(key) ?? throw new InvalidOperationException("Missing " + key);
    private static void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
    private static void Record(string kind, object data) => Events.Add(JsonSerializer.SerializeToElement(new { seq = Events.Count, kind, data }));
    private static SceneTree Tree => (SceneTree)Engine.GetMainLoop();
    private static async Task Frame() => await Tree.ToSignal(Tree, SceneTree.SignalName.ProcessFrame);
    private static bool Usable(NClickableControl? button) => button is not null && GodotObject.IsInstanceValid(button) && button.IsEnabled && button.IsVisibleInTree();
    private static IEnumerable<T> Find<T>(Node? root = null) where T : Node => UiHelper.FindAll<T>(root ?? Tree.Root);

    // Read-only payment witness plus a guard on our synthetic UI channel. No return/argument substitution.
    private static void Payment(CardModel card, int amount)
    {
        if (_active && ReferenceEquals(card, _card))
            Payments.Add(new { card = Id(card), amount, energy = card.Owner.PlayerCombatState!.Energy });
    }
    private static void GuardClick(NClickableControl button)
    {
        if (!_active) return;
        Need(Usable(button), "Rejected disabled/hidden native UI: " + button.Name);
        Record("ui", new { type = button.GetType().Name, path = button.GetPath().ToString(), enabled = button.IsEnabled, visible = button.IsVisibleInTree() });
    }
    private static async Task Click(NClickableControl button)
    {
        Need(Usable(button), "Native UI not ready: " + button.Name);
        GuardClick(button); button.ForceClick(); await Frame(); await Frame();
    }
    private static async Task<bool> ModalStep()
    {
        if (NModalContainer.Instance?.OpenModal is not Node modal) return false;
        var type = modal.GetType().Name;
        if (type.Contains("Error", StringComparison.Ordinal)) throw new InvalidOperationException("Native error modal: " + type);
        // Only acknowledge real startup/tutorial dialogs. Never abandon a run or unlock a character.
        if (!(type.Contains("Ftue", StringComparison.Ordinal) || type is "NConfirmModLoadingPopup" or "NEarlyAccessDisclaimer" || type.Contains("Name", StringComparison.Ordinal)))
            throw new NotSupportedException("Unimplemented native modal: " + type);
        foreach (var input in Find<LineEdit>(modal).Where(x => x.Editable && x.IsVisibleInTree() && string.IsNullOrWhiteSpace(x.Text)))
        { input.Text = "VolibearAcceptance"; input.EmitSignal(LineEdit.SignalName.TextChanged, input.Text); Record("native-text-input", new { modal = type, field = input.Name.ToString() }); }
        var buttons = Find<NClickableControl>(modal).Where(Usable).ToArray();
        var button = buttons.FirstOrDefault(b => new[] { "Confirm", "Accept", "Yes", "Continue", "Ok", "Agree", "Enable" }.Any(s => b.Name.ToString().Contains(s, StringComparison.OrdinalIgnoreCase)));
        if (button is not null) await Click(button);
        return true;
    }
    private static async Task Wait(Func<bool> condition, string stage)
    {
        var timer = Stopwatch.StartNew();
        while (true)
        {
            if (timer.Elapsed.TotalSeconds > 90) throw new TimeoutException(stage);
            if (await ModalStep()) { await Frame(); continue; }
            if (condition()) return;
            await Frame();
        }
    }
    private static object Card(CardModel c) => new { entity = Id(c), id = c.Id.Entry, upgrade = c.CurrentUpgradeLevel, pile = c.Pile?.Type.ToString() };
    private static JsonElement Snapshot()
    {
        var run = RunManager.Instance.DebugOnlyGetState(); var player = run?.Players.SingleOrDefault();
        var combat = CombatManager.Instance.DebugOnlyGetState(); var pcs = player?.PlayerCombatState;
        return JsonSerializer.SerializeToElement(new { run = Id(run), combat = Id(combat), player = Id(player), room = run?.CurrentRoom?.GetType().Name,
            roomType = run?.CurrentRoom?.RoomType.ToString(), floor = run?.TotalFloor, act = run?.CurrentActIndex, actCount = run?.Acts.Count,
            character = player?.Character.Id.Entry, seed = run?.Rng.StringSeed, shouldSave = RunManager.Instance.ShouldSave,
            runActive = RunManager.Instance.IsInProgress, combatActive = CombatManager.Instance.IsInProgress,
            mapOpen = NMapScreen.Instance?.IsOpen ?? false, round = combat?.RoundNumber, phase = pcs?.Phase.ToString(),
            hp = player?.Creature.CurrentHp, maxHp = player?.Creature.MaxHp, block = player?.Creature.Block, energy = pcs?.Energy, gold = player?.Gold,
            deck = player?.Deck.Cards.Select(c => new { id = c.Id.Entry, upgrade = c.CurrentUpgradeLevel }).ToArray(),
            relics = player?.Relics.Select(r => r.Id.Entry).ToArray(),
            powers = player?.Creature.Powers.Select(p => new { type = p.GetType().Name, amount = p.Amount }).ToArray(),
            hand = pcs?.Hand.Cards.Select(Card).ToArray(),
            enemies = combat?.Enemies.Select(e => new { entity = Id(e), id = e.Monster!.Id.Entry, hp = e.CurrentHp, alive = e.IsAlive, attached = ReferenceEquals(e.CombatState, combat) }).ToArray() });
    }
    private static void Won(CombatRoom room)
    {
        _wins++; Record("battle-win", new { combat = Id(room.CombatState), encounter = room.Encounter.Id.Entry, state = Snapshot() });
    }
    private static void Ended(CombatRoom room) => Record("battle-end", new { combat = Id(room.CombatState), state = Snapshot() });
    private static void Turn(CombatState combat) => Record("turn-start", new { combat = Id(combat), side = combat.CurrentSide.ToString(), round = combat.RoundNumber });

    public static void Install()
    {
        if (_installed) return; _installed = true; _ = Run(); // Godot synchronization context only.
    }
    private static async Task StartFromMenu()
    {
        await Wait(() => NGame.Instance?.MainMenu is not null && !RunManager.Instance.IsInProgress, "normal main menu");
        Record("menu", new { runActive = RunManager.Instance.IsInProgress, combatActive = CombatManager.Instance.IsInProgress });
        var menu = NGame.Instance!.MainMenu!;
        var single = menu.GetNode<NClickableControl>("MainMenuTextButtons/SingleplayerButton");
        await Wait(() => Usable(single), "normal Singleplayer button"); await Click(single);
        await Wait(() => menu.GetNodeOrNull<Control>("Submenus/CharacterSelectScreen")?.IsVisibleInTree() == true ||
            Usable(menu.GetNodeOrNull<NClickableControl>("Submenus/SingleplayerSubmenu/StandardButton")), "normal run mode menu");
        var standard = menu.GetNodeOrNull<NClickableControl>("Submenus/SingleplayerSubmenu/StandardButton");
        if (Usable(standard)) await Click(standard!);
        await Wait(() => Find<NCharacterSelectButton>(menu).Any(b => b.IsVisibleInTree() && b.Character.Id.Entry == "VOLIBEAR_CHARACTER"), "visible registered Volibear selection");
        var character = Find<NCharacterSelectButton>(menu).Single(b => b.IsVisibleInTree() && b.Character.Id.Entry == "VOLIBEAR_CHARACTER");
        Need(!character.IsLocked, "Volibear unavailable through native selection; no unlock override");
        Record("character-select", new { id = character.Character.Id.Entry, locked = character.IsLocked, visible = character.IsVisibleInTree(), api = "NCharacterSelectButton.Select" });
        character.Select();
        var confirm = menu.GetNode<NClickableControl>("Submenus/CharacterSelectScreen/ConfirmButton");
        await Wait(() => Usable(confirm), "native embark button"); await Click(confirm);
        await Wait(() => RunManager.Instance.IsInProgress && RunManager.Instance.DebugOnlyGetState()?.CurrentRoom is not null, "native run creation");
        Need(RunManager.Instance.DebugOnlyGetState()!.Players.Single().Character.Id.Entry == "VOLIBEAR_CHARACTER", "Wrong selected character");
        Record("run-start", Snapshot());
    }
    private static object ReadCheckpoint()
    {
        var path = Path.GetFullPath(ProjectSettings.GlobalizePath(SaveManager.Instance.GetProfileScopedPath(Path.Combine(UserDataPathProvider.SavesDir, RunSaveManager.runSaveFileName))));
        var root = Path.GetFullPath(Env("VOLIBEAR_TEST_DATA_ROOT")).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Need(path.StartsWith(root, StringComparison.OrdinalIgnoreCase), "Checkpoint escaped isolated profile");
        var bytes = File.ReadAllBytes(path); using var document = JsonDocument.Parse(bytes);
        return new { sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(), bytes = bytes.Length, nativeSave = document.RootElement.Clone() };
    }
    private static async Task SaveAndQuit()
    {
        Need(!CombatManager.Instance.IsInProgress && RunManager.Instance.DebugOnlyGetState()!.CurrentRoom is not CombatRoom, "Save must be a real noncombat room");
        Record("save-boundary", Snapshot());
        await Wait(() => Usable(NRun.Instance?.GlobalUi.TopBar.Pause), "native pause");
        await Click(NRun.Instance!.GlobalUi.TopBar.Pause);
        await Wait(() => NRun.Instance?.GlobalUi.SubmenuStack.Stack.Peek() is NPauseMenu, "native pause submenu");
        var pause = (NPauseMenu)NRun.Instance!.GlobalUi.SubmenuStack.Stack.Peek()!;
        await Click(pause.GetNode<NClickableControl>("%ButtonContainer/SaveAndQuit"));
        await Wait(() => NGame.Instance?.MainMenu is not null && !RunManager.Instance.IsInProgress, "native save/menu cleanup");
        if (SaveManager.Instance.CurrentRunSaveTask is { } task) await task;
        Record("checkpoint", ReadCheckpoint());
        Record("saved-menu", new { runActive = RunManager.Instance.IsInProgress, combatActive = CombatManager.Instance.IsInProgress });
    }
    private static async Task ContinueFromMenu()
    {
        await Wait(() => NGame.Instance?.MainMenu is not null, "restart main menu");
        Record("checkpoint-before-continue", ReadCheckpoint());
        var button = NGame.Instance!.MainMenu!.GetNode<NClickableControl>("MainMenuTextButtons/ContinueButton");
        await Wait(() => Usable(button), "native Continue"); await Click(button);
        await Wait(() => RunManager.Instance.IsInProgress && RunManager.Instance.DebugOnlyGetState()?.CurrentRoom is not null, "native Continue restored run");
        await Frame(); Record("continued", Snapshot());
        Need(!CombatManager.Instance.IsInProgress, "Noncombat checkpoint restarted into combat");
    }
    private static bool Ready() => CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding &&
        CombatManager.Instance.DebugOnlyGetState() is { CurrentSide: CombatSide.Player } c &&
        c.Players.Single().PlayerCombatState?.Phase == PlayerTurnPhase.Play && !RunManager.Instance.ActionExecutor.IsPaused &&
        RunManager.Instance.ActionQueueSet.IsEmpty && RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null;
    private static async Task FinishPlay()
    {
        var action = _play!; await action.CompletionTask;
        var history = _historyBeforeClear ?? PlayHistory(CombatManager.Instance.History);
        Record("paid-action", new { before = _playBefore, after = Snapshot(), combat = Id(_playCombat), card = Card(_card!), costBefore = _cost,
            action = action.GetType().Name, actionId = action.Id, state = action.State.ToString(), exception = action.Exception?.ToString(),
            context = action.PlayerChoiceContext?.GetType().Name, paymentHooks = Payments.ToArray(),
            historyCapture = _historyBeforeClear.HasValue ? "before-native-victory-history-clear" : "action-completion",
            plays = history.GetProperty("plays"), energyHistory = history.GetProperty("energy") });
        Need(action.Exception is null, "Native paid action faulted"); _play = null; _card = null; _playCombat = null;
    }
    private static async Task CombatStep()
    {
        if (!Ready()) return;
        var combat = CombatManager.Instance.DebugOnlyGetState()!; var player = combat.Players.Single();
        if (_mode != "death-menu")
        {
            foreach (var card in player.PlayerCombatState!.Hand.Cards.OrderBy(c => c.Type == CardType.Power ? 0 : c.Type == CardType.Attack ? 1 : 2).ThenBy(c => c.Id.Entry, StringComparer.Ordinal))
            {
                if (!card.CanPlay(out _, out _)) continue;
                Creature? target = card.IsValidTarget(null) ? null : combat.Enemies.Where(e => e.IsAlive && card.IsValidTarget(e)).OrderBy(e => e.CurrentHp).ThenBy(e => e.CombatId).FirstOrDefault();
                if (!card.IsValidTarget(target)) continue;
                _card = card; _playCombat = combat; _historyStart = CombatManager.Instance.History.Entries.Count(); _historyBeforeClear = null; Payments.Clear();
                _cost = card.EnergyCost.GetWithModifiers(CostModifiers.All); _playBefore = Snapshot();
                Record("play-request", new { combat = Id(combat), card = Card(card), target = Id(target), canPlay = card.CanPlay(out _, out _), validTarget = card.IsValidTarget(target), cost = _cost, energy = player.PlayerCombatState.Energy });
                _pendingAt = Clock.Elapsed.TotalSeconds; _play = new PlayCardAction(card, target); RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(_play); return;
            }
        }
        if (_lastEndCombat == Id(combat) && _lastEndRound == combat.RoundNumber) return;
        var end = Find<NClickableControl>().FirstOrDefault(b => b.GetType().Name == "NEndTurnButton" && Usable(b));
        if (end is null) return;
        _lastEndCombat = Id(combat); _lastEndRound = combat.RoundNumber;
        Record("end-turn", Snapshot()); await Click(end);
    }
    private static readonly IScreenHandler[] Screens = [new RewardsScreenHandler(), new CardRewardScreenHandler(), new ChooseACardScreenHandler(),
        new ChooseABundleScreenHandler(), new ChooseARelicScreenHandler(), new SimpleCardSelectScreenHandler(), new DeckCardSelectScreenHandler(),
        new DeckUpgradeScreenHandler(), new DeckTransformScreenHandler(), new DeckEnchantScreenHandler(), new GameOverScreenHandler()];
    private static async Task<bool> OverlayStep()
    {
        var overlay = NOverlayStack.Instance?.Peek(); if (overlay is null) return false;
        var handler = Screens.SingleOrDefault(h => h.ScreenType == overlay.GetType());
        if (handler is null) throw new NotSupportedException("Unsupported actual overlay: " + overlay.GetType().FullName);
        var before = Snapshot(); Record("selection-open", new { type = overlay.GetType().Name, pendingPaidAction = _play is not null, state = before });
        using var timeout = new CancellationTokenSource(handler.Timeout);
        await handler.HandleAsync(PolicyRandom, timeout.Token);
        Record("selection-return", new { type = overlay.GetType().Name, before, after = Snapshot() }); return true;
    }
    private static async Task<bool> HandSelectionStep()
    {
        var hand = NPlayerHand.Instance;
        if (hand?.IsInCardSelection != true) return false;
        var confirm = hand.GetNode<NConfirmButton>("%SelectModeConfirmButton");
        if (Usable(confirm)) { Record("hand-confirm", new { mode = hand.CurrentMode.ToString(), pendingPaidAction = _play is not null }); await Click(confirm); return true; }
        var holders = Find<NHandCardHolder>(hand.GetNode<Control>("%CardHolderContainer")).Where(h => h.CardNode?.Model is not null && h.IsVisibleInTree()).ToArray();
        if (holders.Length == 0) return true;
        var selected = holders.OrderBy(h => h.CardNode!.Model!.Id.Entry, StringComparer.Ordinal).First();
        Record("hand-choice", new { pendingPaidAction = _play is not null, mode = hand.CurrentMode.ToString(), card = Id(selected.CardNode!.Model!),
            legalVisible = holders.Select(h => Id(h.CardNode!.Model!)).ToArray() });
        selected.EmitSignal(NCardHolder.SignalName.Pressed, selected); await Frame(); return true;
    }
    private static async Task MapStep()
    {
        var run = RunManager.Instance.DebugOnlyGetState()!; var map = NMapScreen.Instance!;
        var points = Find<NMapPoint>(map).ToArray();
        var current = run.VisitedMapCoords.Count == 0 ? null : points.SingleOrDefault(p => p.Point.coord.Equals(run.VisitedMapCoords[^1]));
        var legal = points.Where(p => p.IsEnabled && p.IsVisibleInTree() && (current is null ? p.Point.coord.row == 0 : current.Point.Children.Contains(p.Point))).ToArray();
        if (legal.Length == 0) return;
        int Rank(NMapPoint p) => p.Point.PointType.ToString() switch { "RestSite" => 0, "Shop" => 1, "Treasure" => 2, "Monster" => 3, _ => 4 };
        var next = legal.OrderBy(Rank).ThenBy(p => p.Point.coord.col).First();
        Record("map-choice", new { act = run.CurrentActIndex, fromRow = current?.Point.coord.row, fromCol = current?.Point.coord.col,
            row = next.Point.coord.row, col = next.Point.coord.col, type = next.Point.PointType.ToString(),
            legal = legal.Select(p => new { row = p.Point.coord.row, col = p.Point.coord.col }).ToArray() });
        await Click(next);
    }
    private static async Task RoomStep()
    {
        var run = RunManager.Instance.DebugOnlyGetState()!; var room = run.CurrentRoom!;
        if (room is CombatRoom)
        {
            var proceed = NCombatRoom.Instance?.ProceedButton; if (Usable(proceed)) await Click(proceed!); return;
        }
        if (room.RoomType == RoomType.Shop)
        {
            var shop = Find<NMerchantRoom>().FirstOrDefault(); if (shop is null) return;
            if (!UsedShop.Contains(Id(room)))
            {
                if (!shop.Inventory.IsOpen)
                {
                    if (Usable(shop.MerchantButton)) await Click(shop.MerchantButton);
                    return;
                }
                var slot = shop.Inventory.GetAllSlots().Where(s => s.Entry.IsStocked && s.Entry.EnoughGold)
                    .OrderBy(s => s is NMerchantCardRemoval ? 0 : s.Entry.GetType().Name.Contains("Relic", StringComparison.Ordinal) ? 1 : 2).ThenBy(s => s.Entry.Cost).FirstOrDefault();
                if (slot is not null)
                {
                    _purchaseBefore = Snapshot(); _purchaseKind = slot.Entry.GetType().Name; _purchaseCost = slot.Entry.Cost;
                    Record("shop-request", new { kind = _purchaseKind, cost = _purchaseCost, stocked = slot.Entry.IsStocked, enoughGold = slot.Entry.EnoughGold, before = _purchaseBefore });
                    _pendingAt = Clock.Elapsed.TotalSeconds; _purchase = slot.Entry.OnTryPurchaseWrapper(shop.Inventory.Inventory); return;
                }
                UsedShop.Add(Id(room));
            }
            var back = Find<NBackButton>(shop).FirstOrDefault(Usable); if (back is not null) { await Click(back); return; }
            if (Usable(shop.ProceedButton)) await Click(shop.ProceedButton); return;
        }
        if (room.RoomType == RoomType.RestSite)
        {
            var rest = Find<NRestSiteRoom>().FirstOrDefault(); if (rest is null) return;
            if (!UsedRest.Contains(Id(room)))
            {
                var player = run.Players.Single(); bool injured = player.Creature.CurrentHp < player.Creature.MaxHp * 0.7m;
                var choice = Find<NRestSiteButton>(rest).Where(b => b.Option.IsEnabled && Usable(b))
                    .OrderBy(b => b.Option.GetType().Name.Contains(injured ? "Heal" : "Smith", StringComparison.Ordinal) ? 0 : 1).ThenBy(b => b.Option.GetType().Name, StringComparer.Ordinal).FirstOrDefault();
                if (choice is null) return;
                UsedRest.Add(Id(room)); Record("rest-option", new { option = choice.Option.GetType().Name, enabled = choice.Option.IsEnabled, before = Snapshot() }); await Click(choice); return;
            }
            if (Usable(rest.ProceedButton)) { Record("rest-complete", Snapshot()); await Click(rest.ProceedButton); } return;
        }
        if (room.RoomType == RoomType.Treasure)
        {
            var treasure = Find<NTreasureRoom>().FirstOrDefault(); if (treasure is null) return;
            var relic = Find<NTreasureRoomRelicHolder>(treasure).FirstOrDefault(Usable);
            if (relic is not null) { Record("relic-pick", Snapshot()); await Click(relic); Record("relic-return", Snapshot()); return; }
            if (Usable(treasure.ProceedButton)) { await Click(treasure.ProceedButton); return; }
            var chest = treasure.GetNodeOrNull<NClickableControl>("Chest"); if (Usable(chest)) await Click(chest!); return;
        }
        if (room.RoomType == RoomType.Event)
        {
            var options = Find<NEventOptionButton>().Where(b => Usable(b) && (b.Option.WillKillPlayer is null || b.Event.Owner is null || !b.Option.WillKillPlayer(b.Event.Owner))).ToArray();
            if (options.Length > 0) { Record("event-choice", new { path = options[0].GetPath().ToString(), options = options.Select(b => b.GetPath().ToString()).ToArray(), state = Snapshot() }); await Click(options[0]); }
            return; // Embedded event combat is handled by the same paid-action branch, never CreatureCmd.Kill.
        }
        var genericProceed = Find<NProceedButton>().FirstOrDefault(Usable);
        if (genericProceed is not null) await Click(genericProceed);
    }
    private static async Task<string> Drive()
    {
        while (Clock.Elapsed.TotalMinutes < 40)
        {
            Need(Events.Count < 40000, "Native run observation limit");
            if ((_play is not null || _purchase is not null) && Clock.Elapsed.TotalSeconds - _pendingAt > 120)
                throw new TimeoutException("Native action/selection did not finish within 120s; no forced completion");
            if (await ModalStep()) { await Frame(); continue; }
            var run = RunManager.Instance.DebugOnlyGetState();
            if (run?.CurrentRoom is { } room && SeenRooms.Add(Id(room))) Record("room", Snapshot());
            var combat = CombatManager.Instance.DebugOnlyGetState();
            if (CombatManager.Instance.IsInProgress && combat is not null && SeenCombats.Add(Id(combat)))
                Record("battle-start", new { combat = Id(combat), encounter = combat.Encounter?.Id.Entry, state = Snapshot() });
            if (_play?.CompletionTask.IsCompleted == true) await FinishPlay();
            if (_purchase?.IsCompleted == true)
            {
                await _purchase; Record("shop-complete", new { kind = _purchaseKind, cost = _purchaseCost, before = _purchaseBefore, after = Snapshot() }); _purchase = null;
            }
            if (NOverlayStack.Instance?.Peek()?.GetType().Name == "NGameOverScreen")
            {
                bool victory = run?.CurrentRoom?.IsVictoryRoom ?? false;
                Record("game-over", new { victory, state = Snapshot() });
                if (_mode == "death-menu" && !victory)
                {
                    await OverlayStep(); await StartFromMenu(); Record("new-run-after-death", Snapshot()); return "death-menu-restarted";
                }
                return victory ? "victory" : "death";
            }
            if (await OverlayStep()) continue;
            if (await HandSelectionStep()) { await Frame(); continue; }
            if (_play is not null || _purchase is not null) { await Frame(); continue; }
            if (_mode == "three-battle-save" && _wins >= 3 && !CombatManager.Instance.IsInProgress && run?.CurrentRoom is not null and not CombatRoom)
            { await SaveAndQuit(); return "checkpoint-saved"; }
            if (_mode == "resume" && _wins >= 1 && !CombatManager.Instance.IsInProgress && (NMapScreen.Instance?.IsOpen ?? false)) return "resumed-one-battle";
            if (CombatManager.Instance.IsInProgress) await CombatStep();
            else if (NMapScreen.Instance?.IsOpen == true) await MapStep();
            else if (run?.CurrentRoom is not null) await RoomStep();
            await Frame();
        }
        throw new TimeoutException("Bounded legal native-run strategy did not reach its requested boundary");
    }
    private static async Task Run()
    {
        Harmony? observer = null; string outcome = "error"; string? error = null;
        try
        {
            _token = Env("VOLIBEAR_TEST_TOKEN"); _mode = Env("VOLIBEAR_NATIVE_RUN_MODE"); _pair = Env("VOLIBEAR_NATIVE_RUN_PAIR");
            Need(Env("VOLIBEAR_TEST_SCENARIO") == "native-run" && _mode is "three-battle-save" or "resume" or "death-menu" or "full-run", "Unsupported native-run request");
            Need(!TestMode.IsOn && !SteamInitializer.Initialized && !AutoSlayer.IsActive, "Native run requires TestMode/Steam/AutoSlayer off");
            Need(string.Equals(Path.GetFullPath(Env("VOLIBEAR_TEST_DATA_ROOT")), Path.GetFullPath(Godot.OS.GetUserDataDir()), StringComparison.OrdinalIgnoreCase), "Native run requires isolated offline user://");
            _isolated = true; _bootstrapType = BootstrapSettingsUtil.Get()?.FullName;
            Need(_bootstrapType is null, "Native debug bootstrap is selected instead of normal menu");
            await Wait(() => NGame.Instance is not null && ReleaseInfoManager.Instance.ReleaseInfo is not null, "native startup metadata");
            var bootstrap = Harmony.GetPatchInfo(AccessTools.Method(typeof(BootstrapSettingsUtil), nameof(BootstrapSettingsUtil.Get)));
            Need(bootstrap is null || !bootstrap.Owners.Any(o => o.Contains("Volibear", StringComparison.Ordinal)), "Debug bootstrap forbidden for normal-run acceptance");
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            Need(release.Version.TrimStart('v') == "0.107.1" && release.Commit == "59260271", "Pinned native version mismatch");
            if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_FAST_MODE") == "Fast") SaveManager.Instance.PrefsSave.FastMode = MegaCrit.Sts2.Core.Settings.FastModeType.Fast;
            _active = true; Clock.Start();
            observer = new Harmony("Volibear.NativeRunAcceptance.InputAndPayment");
            observer.Patch(AccessTools.Method(typeof(Hook), nameof(Hook.AfterEnergySpent)), prefix: new HarmonyMethod(typeof(NativeRunAcceptanceProbe), nameof(Payment)));
            observer.Patch(AccessTools.Method(typeof(CombatHistory), nameof(CombatHistory.Clear)), prefix: new HarmonyMethod(typeof(NativeRunAcceptanceProbe), nameof(BeforeHistoryClear)));
            observer.Patch(AccessTools.Method(typeof(UiHelper), nameof(UiHelper.Click)), prefix: new HarmonyMethod(typeof(NativeRunAcceptanceProbe), nameof(GuardClick)));
            CombatManager.Instance.CombatWon += Won; CombatManager.Instance.CombatEnded += Ended; CombatManager.Instance.TurnStarted += Turn;
            if (_mode == "resume") await ContinueFromMenu(); else await StartFromMenu();
            outcome = await Drive();
        }
        catch (Exception ex) { error = ex.ToString(); GD.PrintErr("[Volibear] NATIVE_RUN_ERROR " + error); }
        finally
        {
            _active = false; CombatManager.Instance.CombatWon -= Won; CombatManager.Instance.CombatEnded -= Ended; CombatManager.Instance.TurnStarted -= Turn;
            if (observer is not null) observer.UnpatchAll(observer.Id);
            var release = ReleaseInfoManager.Instance.ReleaseInfo;
            GD.Print("[Volibear] NATIVE_RUN_RESULT " + JsonSerializer.Serialize(new { schema = 1, token = _token, mode = _mode, pair = _pair,
                processId = System.Environment.ProcessId, scenario = "native-run", gameVersion = release?.Version.TrimStart('v'), gameCommit = release?.Commit,
                scope = "normal-native-ui-paid-actions-no-debug-bootstrap-no-game-state-fixtures", policy = "paid-greedy-v1:power-attack-skill;lowest-hp-target;rest-shop-treasure-map;choice-rng314159",
                isolatedProfile = _isolated, nativeBootstrap = _bootstrapType,
                testMode = TestMode.IsOn, steamInitialized = SteamInitializer.Initialized, autoSlayerActive = AutoSlayer.IsActive,
                outcome, error, events = Events.ToArray(), elapsedSeconds = Clock.Elapsed.TotalSeconds }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + _token); NGame.Instance!.Quit(); Tree.Quit(error is null ? 0 : 2);
        }
    }
}
