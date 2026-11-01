using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.PauseMenu;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Managers;
using MegaCrit.Sts2.Core.Saves.Runs;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>Actual disk checkpoint + native pause/continue lifecycle. ForceClick is not physical input.
/// Explicit native acquisition fixtures; independent schema2, no save bytes are written here.</summary>
internal static class SaveLoadCatalogProbe
{
    private static bool _installed;
    private static CardModel? _paymentCard;
    private sealed record PaymentReceipt(string id, int amount, int energy);
    private static readonly List<PaymentReceipt> PaymentReceipts = [];
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterEnergySpent))]
    private static class ObservePayment
    {
        private static void Prefix(CardModel card, int amount)
        {
            if (ReferenceEquals(card, _paymentCard))
                PaymentReceipts.Add(new(card.Id.Entry, amount, card.Owner.PlayerCombatState!.Energy));
        }
    }
    private static readonly Dictionary<object, int> Refs = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Events = [];
    private static int Ref(object value) { if (!Refs.TryGetValue(value, out var id)) Refs.Add(value, id = Refs.Count + 1); return id; }
    private static string Env(string name) => System.Environment.GetEnvironmentVariable(name) ?? throw new InvalidOperationException("Missing " + name);
    private static void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
    private static JsonElement Freeze(object value) => JsonSerializer.SerializeToElement(value);
    private static async Task Frame() { var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame); }
    private static async Task Wait(Func<bool> ready, string stage)
    {
        var clock = Stopwatch.StartNew();
        while (!ready()) { if (clock.Elapsed.TotalSeconds > 90) throw new TimeoutException(stage); await Frame(); }
    }
    private static void RequireCatalogCase()
    {
        if (Env("VOLIBEAR_TEST_SCENARIO") != "save-load-catalog" || Env("VOLIBEAR_SAVE_CASE") != "S3")
            throw new NotSupportedException("NOT_SUPPORTED: save-load-catalog supports only S3");
    }
    public static void Install()
    {
        RequireCatalogCase();
        if (_installed) return; _installed = true;
        new Harmony("Volibear.SaveCatalogProbe.PaymentObservation").CreateClassProcessor(typeof(ObservePayment)).Patch();
        _ = Run(); // Godot's main-thread async context; never Task.Run.
    }
    private static bool Ready() => CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding &&
        CombatManager.Instance.DebugOnlyGetState() is CombatState state &&
        state.CurrentSide == CombatSide.Player && state.Players.Count == 1 &&
        state.Players[0].PlayerCombatState?.Phase == PlayerTurnPhase.Play &&
        !RunManager.Instance.ActionExecutor.IsPaused && RunManager.Instance.ActionQueueSet.IsEmpty &&
        RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null;
    private static object Card(CardModel card)
    {
        var deck = card.Owner.Deck.Cards.ToList();
        return new { entity = Ref(card), id = card.Id.Entry, nativeType = card.GetType().Name, upgrade = card.CurrentUpgradeLevel,
            type = card.Type.ToString(), rarity = card.Rarity.ToString(), target = card.TargetType.ToString(), shape = BeastForms.Shape(card).ToString(), converted = false,
            canonicalCost = card.EnergyCost.Canonical, cost = card.EnergyCost.GetWithModifiers(CostModifiers.Local),
            allCost = card.EnergyCost.GetWithModifiers(CostModifiers.All), costsX = card.EnergyCost.CostsX,
            vars = card.DynamicVars.ToDictionary(p => p.Key, p => new { kind = p.Value.GetType().Name, baseValue = p.Value.BaseValue, enchantedValue = p.Value.EnchantedValue, previewValue = p.Value.PreviewValue }),
            title = card.Title, description = card.GetDescriptionForPile(PileType.None),
            serialized = JsonSerializer.SerializeToElement(card.ToSerializable(), JsonSerializationUtility.GetTypeInfo<SerializableCard>()),
            keywords = card.Keywords.Select(k => k.ToString()).OrderBy(k => k).ToArray(),
            enchantment = card.Enchantment?.Id.Entry, pile = card.Pile?.Type.ToString(),
            owner = Ref(card.Owner), masterIndex = deck.IndexOf(card.DeckVersion ?? card),
            masterEntity = card.DeckVersion is null ? (int?)null : Ref(card.DeckVersion) };
    }
    private static JsonElement Snapshot()
    {
        var run = RunManager.Instance.DebugOnlyGetState()!; var combat = CombatManager.Instance.DebugOnlyGetState()!;
        var player = combat.Players.Single(); var pcs = player.PlayerCombatState!;
        return Freeze(new { runEntity = Ref(run), combatEntity = Ref(combat), playerEntity = Ref(player), creatureEntity = Ref(player.Creature),
            character = player.Character.Id.Entry, shouldSave = RunManager.Instance.ShouldSave, seed = run.Rng.StringSeed,
            room = (run.CurrentRoom ?? throw new InvalidOperationException("Missing room")).GetType().Name,
            encounter = (combat.Encounter ?? throw new InvalidOperationException("Missing encounter")).Id.Entry,
            round = combat.RoundNumber, turn = pcs.TurnNumber, energy = pcs.Energy, hp = player.Creature.CurrentHp,
            maxHp = player.Creature.MaxHp, block = player.Creature.Block, gold = player.Gold,
            deck = player.Deck.Cards.Select(Card).ToArray(), relics = player.Relics.Select((r, index) => new {
                entity = Ref(r), id = r.Id.Entry, type = r.GetType().Name, owner = Ref(r.Owner), slot = index, melted = r.IsMelted,
                serialized = JsonSerializer.SerializeToElement(r.ToSerializable(), JsonSerializationUtility.GetTypeInfo<SerializableRelic>()) }).ToArray(),
            powers = player.Creature.Powers.Select(p => new { type = p.GetType().Name, amount = p.Amount }).ToArray(),
            piles = pcs.AllPiles.ToDictionary(p => p.Type.ToString(), p => p.Cards.Select(Card).ToArray()),
            enemies = combat.Enemies.Select(e => new { entity = Ref(e), id = e.Monster!.Id.Entry, hp = e.CurrentHp, maxHp = e.MaxHp, block = e.Block, move = e.Monster.NextMove.Id }).ToArray() });
    }
    private static string CheckpointPath(string root)
    {
        var path = Path.GetFullPath(ProjectSettings.GlobalizePath(SaveManager.Instance.GetProfileScopedPath(
            Path.Combine(UserDataPathProvider.SavesDir, RunSaveManager.runSaveFileName))));
        var normalized = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        Need(path.StartsWith(normalized, StringComparison.OrdinalIgnoreCase), "Save path escaped isolated user://");
        return path;
    }
    private static JsonElement ReadCheckpoint(string root)
    {
        var path = CheckpointPath(root);
        Need(File.Exists(path), "Native checkpoint not created");
        using var json = JsonDocument.Parse(File.ReadAllText(path));
        return json.RootElement.Clone(); // Observe actual native disk bytes; never write/rewrite a save.
    }
    private static void Click(NClickableControl button, string name)
    {
        Need(button.IsEnabled && button.IsVisibleInTree(), "Native button not interactable: " + name);
        Events.Add(new { op = "native-ui-forceclick", button = name }); button.ForceClick();
    }
    private static async Task QuitToMenu()
    {
        await Wait(() => NRun.Instance?.GlobalUi.TopBar.Pause is { IsEnabled: true } button && button.IsVisibleInTree(), "enabled native pause button");
        Click(NRun.Instance!.GlobalUi.TopBar.Pause, "Pause");
        await Wait(() => NRun.Instance?.GlobalUi.SubmenuStack.Stack.Peek() is NPauseMenu, "native pause menu");
        var pause = (NPauseMenu)NRun.Instance!.GlobalUi.SubmenuStack.Stack.Peek()!;
        Click(pause.GetNode<NClickableControl>("%ButtonContainer/SaveAndQuit"), "SaveAndQuit");
        await Wait(() => NGame.Instance?.MainMenu is not null && !RunManager.Instance.IsInProgress, "native SaveAndQuit completion");
        if (SaveManager.Instance.CurrentRunSaveTask is { } saving) await saving;
        Need(!CombatManager.Instance.IsInProgress, "Combat survived menu cleanup");
    }
    private static async Task Continue()
    {
        await Wait(() => NGame.Instance?.MainMenu?.GetNodeOrNull<NClickableControl>("MainMenuTextButtons/ContinueButton") is { IsEnabled: true } button &&
            button.IsVisibleInTree(), "enabled native menu Continue");
        Click(NGame.Instance!.MainMenu!.GetNode<NClickableControl>("MainMenuTextButtons/ContinueButton"), "Continue");
        await Wait(Ready, "native Continue restored active combat");
    }
    private static async Task<object> Interrupt()
    {
        var state = (CombatState)CombatManager.Instance.DebugOnlyGetState()!;
        var player = state.Players.Single(); var pcs = player.PlayerCombatState!;
        var choices = new ThrowingPlayerChoiceContext();
        CardModel Find(string id) => pcs.AllPiles.SelectMany(p => p.Cards).First(c => c.Id.Entry == id && c.CurrentUpgradeLevel == 0 && c.DeckVersion is not null);
        async Task InHand(CardModel card)
        {
            if (card.Pile?.Type == PileType.Hand) return;
            Events.Add(new { op = "state-fixture-native-move-to-hand", id = card.Id.Entry, entity = Ref(card) });
            await CardPileCmd.Add(card, PileType.Hand);
        }
        var defend = Find("VOLIBEAR_B02"); await InHand(defend);
        int boundary = CombatManager.Instance.History.Entries.Count();
        // Native Self cards are untargeted actions. Supplying the owner causes
        // IsValidTarget to reject the play before payment, despite a Finished action.
        Need(defend.CanPlay(out _, out _) && defend.IsValidTarget(null), "B02 is not legally payable with a null Self target");
        var energyBefore = pcs.Energy; var blockBefore = player.Creature.Block;
        var action = new PlayCardAction(defend, null);
        PaymentReceipts.Clear(); _paymentCard = defend;
        try
        {
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
            await Wait(() => action.CompletionTask.IsCompleted, "native B02 payment action"); await action.CompletionTask;
        }
        finally { _paymentCard = null; }
        Need(action.Exception is null, "Native action faulted");
        await Wait(Ready, "native action queue settled");
        var plays = CombatManager.Instance.History.Entries.Skip(boundary).OfType<CardPlayStartedEntry>()
            .Select(p => new { id = p.CardPlay.Card.Id.Entry, autoPlay = p.CardPlay.IsAutoPlay, spent = p.CardPlay.Resources.EnergySpent,
                index = p.CardPlay.PlayIndex, count = p.CardPlay.PlayCount }).ToArray();
        var energyHistory = CombatManager.Instance.History.Entries.Skip(boundary).OfType<EnergySpentEntry>().Select(e => e.Amount).ToArray();
        Need(PaymentReceipts.Count == 1 && PaymentReceipts[0].amount == 1 && PaymentReceipts[0].energy == energyBefore - 1 &&
            energyHistory.Length == 1 && energyHistory[0] == 1, "Native AfterEnergySpent/history witness missing");
        Need(action.PlayerChoiceContext is GameActionPlayerChoiceContext && plays.Length == 1 &&
            plays[0].id == "VOLIBEAR_B02" && !plays[0].autoPlay && plays[0].spent == 1 &&
            pcs.Energy == energyBefore - 1 && player.Creature.Block == blockBefore + 5 && defend.Pile?.Type == PileType.Discard,
            "B02 interruption did not actually pay, gain block and discard; Finished alone is insufficient");
        return new { kind = "paid-base-defend-state-fixture", payment = new { action = action.GetType().Name, state = action.State.ToString(), actionId = action.Id,
            context = action.PlayerChoiceContext?.GetType().Name, history = plays, afterEnergySpent = PaymentReceipts.ToArray(), energyHistory } };
    }
    private static async Task<object> PrepareCatalog(RunState run)
    {
        var player = run.Players.Single();
        var removed = player.Deck.Cards.Select(c => new { entity = Ref(c), id = c.Id.Entry, upgrade = c.CurrentUpgradeLevel }).ToArray();
        Need(removed.Length == 10, "S3 must begin with the actual starter deck");
        await CardPileCmd.RemoveFromDeck(player.Deck.Cards.ToArray(), showPreview: false);
        var registry = AccessTools.Field(typeof(ModelDb), "_contentById").GetValue(null) as Dictionary<ModelId, AbstractModel>
            ?? throw new InvalidOperationException("Native registry unavailable");
        var canonical = registry.Values.OfType<VolibearCard>().Where(c => c.GetType().Assembly == typeof(VolibearCard).Assembly)
            .OrderBy(c => c.Id.Entry, StringComparer.Ordinal).ToArray();
        Need(canonical.Length == 89 && canonical.Select(c => c.Id).Distinct().Count() == 89, "Exactly89 canonical card IDs required");
        var acquired = new List<object>();
        foreach (var model in canonical)
            foreach (var level in new[] { 0, 1 })
            {
                var card = run.CreateCard(model, player);
                await CardPileCmd.Add(card, PileType.Deck, skipVisuals: true);
                var beforeKeywords = card.Keywords.Select(k => k.ToString()).Order().ToArray();
                if (level == 1)
                {
                    Need(card.IsUpgradable, "Catalog face is not natively upgradable: " + card.Id);
                    CardCmd.Upgrade(card);
                }
                Need(card.CurrentUpgradeLevel == level && card.Pile?.Type == PileType.Deck && ReferenceEquals(card.Owner, player), "Native master acquisition/upgrade failed");
                acquired.Add(new { entity = Ref(card), id = card.Id.Entry, upgrade = card.CurrentUpgradeLevel, upgraderCalled = level == 1,
                    owner = Ref(player), deckIndex = player.Deck.Cards.ToList().IndexOf(card), beforeKeywords,
                    afterKeywords = card.Keywords.Select(k => k.ToString()).Order().ToArray(),
                    serialized = JsonSerializer.SerializeToElement(card.ToSerializable(), JsonSerializationUtility.GetTypeInfo<SerializableCard>()) });
            }
        Need(player.Deck.Cards.Count == 178, "S3 master count must be exactly178");
        return new { kind = "explicit-native-catalog-master-construction-not-natural-acquisition", removed,
            registryIds = canonical.Select(c => c.Id.Entry).ToArray(), acquired };
    }
    private static async Task Run()
    {
        string token = "missing";
        try
        {
            token = Env("VOLIBEAR_TEST_TOKEN"); var pair = Env("VOLIBEAR_SAVE_PAIR"); var phase = Env("VOLIBEAR_SAVE_PHASE");
            var mode = Env("VOLIBEAR_SAVE_MODE"); var caseId = Env("VOLIBEAR_SAVE_CASE"); var seed = Env("VOLIBEAR_SAVE_SEED");
            RequireCatalogCase();
            Need((mode == "same-process" && phase == "same") || (mode == "restart" && phase is "prepare" or "resume"), "Invalid phase/mode");
            Need(!MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, "TestMode forbidden");
            var expectedRoot = Path.GetFullPath(Env("VOLIBEAR_TEST_DATA_ROOT")).TrimEnd(Path.DirectorySeparatorChar);
            var userRoot = Path.GetFullPath(ProjectSettings.GlobalizePath("user://")).TrimEnd(Path.DirectorySeparatorChar);
            Need(string.Equals(userRoot, expectedRoot, StringComparison.OrdinalIgnoreCase), "Actual user:// differs from isolated root");
            await Wait(() => NGame.Instance?.MainMenu is not null && SaveManager.Instance.IsProfileInitialized, "initialized real main menu");
            Need(SaveManager.Instance.CurrentProfileId == 1, "Unexpected test profile");
            JsonElement? checkpoint = null, afterMenu = null, initial = null, interrupted = null, resumed = null, afterLoad = null;
            object? fixture = null, interruption = null, resumedCase = null, route = null;
            if (phase != "resume")
            {
                Need(!SaveManager.Instance.HasRunSave, "Prepare refuses existing run");
                var character = ModelDb.Character<VolibearCharacter>();
                var statsBefore = SaveManager.Instance.Progress.GetStatsForCharacter(character.Id);
                SaveManager.Instance.Progress.GetOrCreateCharacterStats(character.Id);
                SaveManager.Instance.SetFtuesEnabled(false);
                var run = await NGame.Instance!.StartNewSingleplayerRun(character, true, ActModel.GetDefaultList().ToArray(),
                    Array.Empty<ModifierModel>(), seed, GameMode.Standard, 0);
                Need(!run.ExtraFields.StartedWithNeow && run.CurrentRoom is MapRoom,
                    "Fresh-profile route not MapRoom/no-Neow; do not bypass native event flow");
                var preparation = await PrepareCatalog(run);
                fixture = new { directRunApi = true, statsExistedBefore = statsBefore is not null,
                    statsPresent = SaveManager.Instance.Progress.GetStatsForCharacter(character.Id) is not null,
                    ftuesDisabledInIsolatedProfile = true, shouldSave = RunManager.Instance.ShouldSave, startedWithNeow = run.ExtraFields.StartedWithNeow,
                    masterPreparation = preparation };
                await RunManager.Instance.EnterMapCoord(run.Map.StartingMapPoint.coord);
                Need(run.CurrentRoom is CombatRoom, "Starting room is not combat; native reachable-room traversal required, not accepted as combat");
                await Wait(Ready, "first actual native combat");
                if (SaveManager.Instance.CurrentRunSaveTask is { } save) await save;
                checkpoint = ReadCheckpoint(userRoot); initial = Snapshot();
                interruption = await Interrupt();
                interrupted = Snapshot();
                await QuitToMenu(); afterMenu = ReadCheckpoint(userRoot);
            }
            else
            {
                Need(SaveManager.Instance.HasRunSave, "Resume requires existing pair checkpoint");
                checkpoint = ReadCheckpoint(userRoot);
            }
            if (phase != "prepare")
            {
                await Continue();
                resumed = Snapshot(); afterLoad = ReadCheckpoint(userRoot);
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            GD.Print("[Volibear] SAVE_CATALOG_RESULT " + JsonSerializer.Serialize(new { schemaVersion = 2, scenario = "save-load-catalog", token, pair, phase, mode, caseId, roomKind = "active-entry",
                pid = System.Environment.ProcessId, userRoot, checkpointPath = CheckpointPath(userRoot),
                gameVersion = release.Version, gameCommit = release.Commit, testMode = false,
                assemblyMvid = typeof(BeastForms).Assembly.ManifestModule.ModuleVersionId.ToString(),
                acceptance = "native-save-catalog-programmatic-ui-not-G6", seed,
                fixture, events = Events, checkpoint, afterMenu, initial, interruption, interrupted, resumed, afterLoad, resumedCase, route }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] SAVE_CATALOG_PROBE_ERROR " + token + " " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
