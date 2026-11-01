using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>Paid native queue inputs, actual EndTurn/PaelsEye/room replacement.
/// One earlier ability instance is an explicitly disclosed native PowerCmd fixture,
/// never reported as a second paid card. No callbacks, counters or combat resets are invoked.</summary>
internal static class CardLifecycleAcceptanceProbe
{
    internal static readonly string[] Codes = ["U02", "U04", "U19", "U21", "U25", "U26", "U32", "U34", "R16", "R18", "U07", "U08", "U20", "C17", "U13", "U26-extra", "U29", "R01", "R14", "R06", "U03", "R02", "R28", "R30"];
    internal static readonly string[] Variants = Codes.SelectMany(c => new[] { c + "-base", c + "-upgraded" }).ToArray();
    private static readonly Harmony Observer = new("Volibear.CardLifecycleAcceptanceProbe");
    private static readonly ThrowingPlayerChoiceContext Choices = new();
    private static readonly Dictionary<object, string> Refs = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Actions = [], Fixtures = [], Transitions = [], Payments = [], Effects = [], Batches = [], ExtraTurns = [], Confirmations = [], ChoiceSync = [];
    private static bool started, upgraded;
    private static string code = "";
    private static Player player = null!;
    private static CombatState combat = null!;
    private static Creature[] enemies = [];
    private static IDisposable? subscription;
    private static PlayerCombatState Pcs => player.PlayerCombatState!;
    private static Creature Owner => player.Creature;
    private static string Ref(object? value)
    { if (value is null) return "null"; if (!Refs.TryGetValue(value, out var id)) Refs.Add(value, id = "r" + (Refs.Count + 1)); return id; }
    private static void Require(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
    public static void Install()
    {
        Require(System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "card-lifecycle", "Explicit lifecycle scenario required");
        foreach (var type in new[] { typeof(Payment), typeof(Effect), typeof(ExtraTurn), typeof(SyncChoice) }) Observer.CreateClassProcessor(type).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static readonly Dictionary<object, string> RunRefs = new(ReferenceEqualityComparer.Instance);
    private static void Start(CombatState state) { if (!started) { started = true; _ = RunBatch(state); } }
    private static async Task RunBatch(CombatState initial)
    {
        try
        {
            string token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
            var configured = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_LIFECYCLE_CASES");
            var requested = configured == "all" ? Variants : !string.IsNullOrWhiteSpace(configured) ? JsonSerializer.Deserialize<string[]>(configured)! :
                new[] { System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_LIFECYCLE_CASE") ?? "" };
            Require(token.Length > 0 && requested.Length > 0 && requested.Distinct().Count() == requested.Length && requested.All(Variants.Contains), "Invalid finite lifecycle batch");
            var completed = new List<string>(); var exits = new List<object>(); var runs = new List<string>(); var current = initial;
            foreach (var variant in requested)
            {
                Require(!RunRefs.ContainsKey(current.RunState), "Each lifecycle case must have a distinct native run");
                string runRef = "run-" + (RunRefs.Count + 1); RunRefs.Add(current.RunState, runRef); runs.Add(runRef);
                await NativeAcceptanceRunHost.WaitForQuiet(current, 1);
                var result = await RunCase(current, variant, token, runRef);
                GD.Print("[Volibear] CARD_LIFECYCLE_RESULT " + result.GetRawText()); completed.Add(variant);
                var exit = await NativeAcceptanceRunHost.ExitToMainMenu(); exits.Add(new { variant, runRef, receipt = exit });
                if (completed.Count < requested.Length) current = await NativeAcceptanceRunHost.StartFresh(ModelDb.Encounter<SlimesWeak>());
            }
            GD.Print("[Volibear] CARD_LIFECYCLE_BATCH_RESULT " + JsonSerializer.Serialize(new { schema = 1, token, scenario = "card-lifecycle", requested, completed, runRefs = runs, exits, finished = true }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] CARD_LIFECYCLE_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { subscription?.Dispose(); Observer.UnpatchAll(Observer.Id); CombatManager.Instance.TurnStarted -= Start; }
    }
    private static async Task Until(Func<bool> done, string label)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (!done())
        {
            if (watch.Elapsed > TimeSpan.FromSeconds(75)) throw new TimeoutException(label);
            if (code == "R28" && MegaCrit.Sts2.Core.Nodes.Combat.NPlayerHand.Instance?.GetNodeOrNull<NClickableControl>("%SelectModeConfirmButton") is { IsEnabled: true } confirm && confirm.IsVisibleInTree())
            {
                // Optional native start-turn choices select zero through the actual focused GUI,
                // never CardSelectCmd.Selector or completing a choice task ourselves.
                confirm.GrabFocus(); await Frame();
                Require(ReferenceEquals(confirm.GetViewport().GuiGetFocusOwner(), confirm), "R28 native confirmation focus failed");
                confirm.GetViewport().PushInput(new InputEventAction { Action = MegaInput.select, Pressed = true }); await Frame();
                confirm.GetViewport().PushInput(new InputEventAction { Action = MegaInput.select, Pressed = false }); await Frame();
                Confirmations.Add(new { api = "Viewport.PushInput", selection = "optional-zero", round = combat.RoundNumber, turn = Pcs.TurnNumber });
            }
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Frame()
    { var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame); }
    private static object Snapshot() => new {
        combatRef = Ref(combat), round = combat.RoundNumber, turn = Pcs.TurnNumber, side = combat.CurrentSide.ToString(), phase = Pcs.Phase.ToString(),
        energy = Pcs.Energy, hp = Owner.CurrentHp, block = Owner.Block, strength = Owner.GetPowerAmount<StrengthPower>(), dexterity = Owner.GetPowerAmount<DexterityPower>(),
        storm = Owner.GetPowerAmount<StormChargePower>(), domain = Owner.GetPowerAmount<DomainPower>(), permanent = Owner.GetPower<DomainPower>()?.IsPermanent ?? false, lightning = LightningBatches.GetTurnCount(Owner),
        temporary = Owner.Powers.OfType<TemporaryStrengthPower>().Sum(p => p.Amount), hand = Pcs.Hand.Cards.Select(Ref).ToArray(),
        handCards = Pcs.Hand.Cards.Select(c => new { cardRef = Ref(c), type = c.GetType().Name, cost = c.EnergyCost.GetWithModifiers(CostModifiers.All) }).ToArray(),
        powers = Owner.Powers.Select(p => new { powerRef = Ref(p), type = p.GetType().Name, amount = p.Amount }).ToArray(),
        enemies = combat.Enemies.Select(e => new { enemyRef = Ref(e), id = e.CombatId, type = e.Monster!.GetType().Name, hp = e.CurrentHp, block = e.Block }).ToArray()
    };
    private static object History(int boundary)
    {
        var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
        return new {
            plays = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount, autoPlay = e.CardPlay.IsAutoPlay, spent = e.CardPlay.Resources.EnergySpent }).ToArray(),
            finished = history.OfType<CardPlayFinishedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card), index = e.CardPlay.PlayIndex, autoPlay = e.CardPlay.IsAutoPlay }).ToArray(),
            draws = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card), type = e.Card.GetType().Name, normal = e.FromHandDraw }).ToArray(),
            exhausts = history.OfType<CardExhaustedEntry>().Select(e => Ref(e.Card)).ToArray(),
            damage = history.OfType<DamageReceivedEntry>().Select(e => new { targetRef = Ref(e.Receiver), sourceRef = Ref(e.Dealer), cardRef = Ref(e.CardSource), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage, props = (int)e.Result.Props }).ToArray(),
            moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemyRef = Ref(e.Monster.Creature), move = e.Move.Id }).ToArray()
        };
    }
    private static void Subscribe()
    {
        subscription?.Dispose();
        subscription = LightningBatches.Subscribe(Owner, (_, batch) => {
            Batches.Add(new { id = batch.Id, combatRef = Ref(combat), round = batch.RoundNumber, turn = batch.PlayerTurnNumber,
                count = batch.CountThisTurn, baseDamage = batch.BaseDamage, storm = batch.StormCharge, amount = batch.Amount,
                cardRef = Ref(batch.Card), targets = batch.Targets.Select(Ref).ToArray(),
                hits = batch.Results.Select(r => new { targetRef = Ref(r.Receiver), hpLost = r.HpLost, blocked = r.Blocked }).ToArray() });
            return Task.CompletedTask;
        });
    }
    private static async Task<CardModel> Create(string name, bool upgrade = false, int replay = 0, PileType pile = PileType.Hand)
    {
        var type = typeof(Volibear_B01).Assembly.GetType("Volibear.Content.Volibear_" + name) ?? throw new InvalidOperationException("Unknown fixture card " + name);
        var canonical = (CardModel)AccessTools.Method(typeof(ModelDb), nameof(ModelDb.Card)).MakeGenericMethod(type).Invoke(null, null)!;
        var card = combat.CreateCard(canonical, player);
        Require(card.GetType() == type, "Canonical fixture card identity changed");
        if (upgrade) CardCmd.Upgrade(card);
        card.BaseReplayCount = replay;
        await CardPileCmd.Add(card, pile, CardPilePosition.Top); return card;
    }
    private static async Task Play(string name, string label, int target = -1, bool upgrade = false, int replay = 0)
    {
        var card = await Create(name, upgrade, replay); var creature = target < 0 ? null : enemies[target];
        var before = Snapshot(); int history = CombatManager.Instance.History.Entries.Count(), payments = Payments.Count, effects = Effects.Count, batches = Batches.Count;
        var previews = enemies.Select(e => new { targetRef = Ref(e), cost = TargetCosts.CostFor(card, e) }).ToArray();
        var action = new PlayCardAction(card, creature); var events = new List<string>();
        action.BeforeExecuted += _ => events.Add("before-executed"); action.BeforeCancelled += _ => events.Add("cancelled"); action.AfterFinished += _ => events.Add("after-finished");
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
        await Until(() => action.CompletionTask.IsCompleted, "Paid lifecycle action " + label); await action.CompletionTask;
        if (action.Exception is not null) throw new InvalidOperationException("Native paid lifecycle failure", action.Exception);
        Actions.Add(new { label, code = name, upgraded = upgrade, replay, cardRef = Ref(card), targetRef = Ref(creature), before, after = Snapshot(), previews,
            pile = card.Pile?.Type.ToString() ?? "None", action = new { type = action.GetType().Name, state = action.State.ToString(), actionType = action.ActionType.ToString(),
                sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(), card), events },
            payments = Payments.Skip(payments).ToArray(), effects = Effects.Skip(effects).ToArray(), batches = Batches.Skip(batches).ToArray(), history = History(history) });
    }
    private static async Task Fixture(string label, Func<Task> native)
    {
        var before = Snapshot(); int h = CombatManager.Instance.History.Entries.Count(), b = Batches.Count;
        await native(); Fixtures.Add(new { label, before, after = Snapshot(), history = History(h), batches = Batches.Skip(b).ToArray() });
    }
    private static async Task PrepareCombat(string label)
    {
        await Fixture(label, async () => {
            foreach (var card in Pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw, CardPilePosition.Bottom);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 1000m);
            await CreatureCmd.SetMaxAndCurrentHp(Owner, 1000m);
            await PlayerCmd.SetEnergy(30, player);
            for (int i = 0; i < 32; i++) await Create(code == "U25" ? "B01" : "B02", pile: PileType.Draw);
        });
    }
    private static async Task NormalizeTurn()
    {
        await Fixture("native-next-turn-energy-and-negative-modifier-isolation", async () => {
            await PlayerCmd.SetEnergy(30, player);
            foreach (var power in Owner.Powers.Where(p => p is WeakPower or FrailPower or VulnerablePower).ToArray()) await PowerCmd.Remove(power);
            foreach (var enemy in enemies) if (enemy.Block > 0) await CreatureCmd.LoseBlock(enemy, enemy.Block);
        });
    }
    private static async Task EndTurn(string label)
    {
        var before = Snapshot(); int turn = Pcs.TurnNumber, h = CombatManager.Instance.History.Entries.Count(), b = Batches.Count, extra = ExtraTurns.Count;
        PlayerCmd.EndTurn(player, canBackOut: false);
        await Until(() => Pcs.TurnNumber == turn + 1 && combat.CurrentSide == CombatSide.Player && Pcs.Phase == PlayerTurnPhase.Play, "Native lifecycle next turn");
        Transitions.Add(new { label, before, after = Snapshot(), history = History(h), batches = Batches.Skip(b).ToArray(), extraTurns = ExtraTurns.Skip(extra).ToArray() });
    }
    private static async Task DeployFirst()
    {
        int strength = upgraded ? 2 : 1;
        await Fixture("first-instance-native-PowerCmd-not-paid-card", async () => {
            switch (code)
            {
                case "R28": { var source = await Create("R28", upgraded, pile: PileType.Discard); await PowerCmd.Apply<BearSpiritPower>(Choices, Owner, upgraded ? 2 : 1, Owner, source); break; }
                case "R30": { var source = await Create("R30", upgraded, pile: PileType.Discard); await PowerCmd.Apply<WildernessPower>(Choices, Owner, upgraded ? 9 : 6, Owner, source); break; }
                case "U29": await StormChargePower.Gain(Choices, Owner, upgraded ? 3 : 2); break;
                case "R01": await DomainPower.OpenPermanent(Choices, Owner); break;
                case "R14": await PowerCmd.Apply<EndlessHuntPower>(Choices, Owner, 1, Owner, null); break;
                case "R06": await PowerCmd.Apply<UnifyPower>(Choices, Owner, 3, Owner, null); break;
                case "U03": await PowerCmd.Apply<StandingPower>(Choices, Owner, upgraded ? 3 : 6, Owner, null); break;
                case "R02": await PowerCmd.Apply<ImmovableBodyPower>(Choices, Owner, 1, Owner, null); break;
                case "U02": await PowerCmd.Apply<StormConductionPower>(Choices, Owner, upgraded ? 4 : 3, Owner, null); break;
                case "U04": await PowerCmd.Apply<BattleScarsPower>(Choices, Owner, strength, Owner, null); break;
                case "U19": await PowerCmd.Apply<LingeringStormPower>(Choices, Owner, 1, Owner, null); break;
                case "U21": await PowerCmd.Apply<ThunderAftershockPower>(Choices, Owner, 1, Owner, null); break;
                case "U25": await PowerCmd.Apply<PreyStillStandsPower>(Choices, Owner, upgraded ? 2 : 1, Owner, null); break;
                case "U26": case "U26-extra": await PowerCmd.Apply<GrowingFuryPower>(Choices, Owner, strength, Owner, null); break;
                case "U32": await PowerCmd.Apply<WelcomeThunderPower>(Choices, Owner, upgraded ? 2 : 1, Owner, null); break;
                case "U34": await PowerCmd.Apply<ThunderArmorPower>(Choices, Owner, upgraded ? 4 : 3, Owner, null); break;
                case "R16": await PowerCmd.Apply<BattleBodyPower>(Choices, Owner, 1, Owner, null); break;
                case "R18": await PowerCmd.Apply<ThunderPoolPower>(Choices, Owner, upgraded ? 6 : 4, Owner, null); break;
                default: throw new InvalidOperationException("No fixture ability mapping");
            }
        });
    }
    private static async Task AbilityEvents(string prefix)
    {
        if (code is "R28" or "R30")
        {
            await Play("T01", prefix + "-first", 0); await Play("T01", prefix + "-second", 0);
            if (code == "R30") { await Play("T02", prefix + "-body-one"); await Play("T02", prefix + "-body-two"); }
            return;
        }
        if (code == "R14")
        {
            await Play("B01", prefix + "-first", 0); await Play("B01", prefix + "-second", 0);
            await Play("B01", prefix + "-other", 1); await Play("U07", prefix + "-accumulated", 0);
            await Play("U07", prefix + "-untouched", 2); return;
        }
        if (code == "R06")
        { await Play("B01", prefix + "-first", 0); await Play("C24", prefix + "-second"); return; }
        if (code == "U32")
        {
            if (prefix == "same-turn") await Play("U07", prefix + "-initial-coupon", 2);
            await Play("B04", prefix + "-first", 0);
            await Play("U07", prefix + "-coupon", 1);
            await Play("B04", prefix + "-second", 1);
            await Play("U07", prefix + "-spent", 2); return;
        }
        string trigger = code is "U04" or "U19" or "R18" or "U03" or "R02" ? "B04" : code is "U21" or "U34" or "U29" ? "C24" : "B01";
        await Play(trigger, prefix + "-first", trigger == "C24" ? -1 : 0);
        await Play(code == "R16" ? "B04" : trigger, prefix + "-second", trigger == "C24" ? -1 : code is "U04" or "U19" or "R18" or "U03" or "R02" ? 1 : 0);
        if (code is "U25" or "U26" or "U26-extra")
        {
            await Play("B01", prefix + "-third", 1);
            await Play("B01", prefix + "-fourth", 1);
        }
    }
    private static async Task InitialHistory()
    {
        if (code == "U07")
        {
            await Play("B01", "history-replayed-attack-counts-once", 0, replay: 1);
            await Play("U07", "history-same-target", 0, upgraded);
            await Play("U07", "history-other-target", 1, upgraded);
            await Play("U07", "history-return-target", 0, upgraded);
        }
        else if (code == "U08")
        {
            await Fixture("native-target-fully-blocked", () => CreatureCmd.GainBlock(enemies[0], 100m, ValueProp.Unpowered, null));
            await Play("U08", "bite-blocked-first", 0, upgraded);
            await Fixture("native-clear-target-block", () => CreatureCmd.LoseBlock(enemies[0], enemies[0].Block));
            await Play("U08", "bite-other-target", 1, upgraded);
            await Play("U08", "bite-marked-target", 0, upgraded);
        }
        else if (code == "U20")
        {
            await Play("B02", "previous-skill");
            await Play("U20", "previous-skill-replay", 0, upgraded, replay: 1);
            await Play("U20", "previous-attack-replay", 1, upgraded, replay: 1);
        }
        else
        {
            await Play("C17", "temporary-first", upgrade: upgraded);
            if (code == "U13") { await Play("U13", "convert-temporary", upgrade: upgraded); await Play("C17", "temporary-second", upgrade: upgraded); }
            await Play("B01", "temporary-attack", 0);
        }
    }
    private static async Task FollowingHistory()
    {
        if (code == "U07") await Play("U07", "history-next-turn-reset", 0, upgraded);
        else if (code == "U08")
        {
            await Play("U08", "bite-next-turn-marked", 0, upgraded);
            await Fixture("native-new-enemy-identity", async () => {
                var fresh = await CreatureCmd.Add<LeafSlimeS>(combat); await CreatureCmd.SetMaxAndCurrentHp(fresh, 1000m);
                enemies = enemies.Append(fresh).ToArray();
            });
            await Play("U08", "bite-new-instance-unmarked", enemies.Length - 1, upgraded);
        }
        else if (code == "U20")
        {
            await Play("U20", "previous-attack-across-turn", 0, upgraded);
            await Play("B02", "previous-skill-again"); await Play("U20", "previous-skill-no-refund", 1, upgraded);
        }
        else await Play("B01", "temporary-next-turn", 0);
    }
    internal static async Task<JsonElement> RunCase(CombatState state, string variant, string token, string runRef)
    {
        try
        {
            Refs.Clear(); Actions.Clear(); Fixtures.Clear(); Transitions.Clear(); Payments.Clear(); Effects.Clear(); Batches.Clear(); ExtraTurns.Clear(); Confirmations.Clear(); ChoiceSync.Clear();
            Require(!string.IsNullOrWhiteSpace(token) && Variants.Contains(variant), "Lifecycle case/token required");
            upgraded = variant.EndsWith("-upgraded", StringComparison.Ordinal); code = variant[..variant.LastIndexOf('-')];
            combat = state; player = state.Players.Single(); enemies = state.Enemies.ToArray();
            Require(!MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn && state.Encounter is SlimesWeak && state.RoundNumber == 1 && Pcs.TurnNumber == 1 && Owner.CurrentHp == 80 && Owner.Block == 0 && !Owner.Powers.Any() && enemies.Length == 3, "Fresh native SlimesWeak required");
            Subscribe(); var original = Snapshot(); await PrepareCombat("native-created-card-and-HP-energy-isolation");
            bool ability = !new[] { "U07", "U08", "U20", "C17", "U13" }.Contains(code);
            if (code == "U26-extra") await Fixture("native-PaelsEye-extra-turn-fixture", async () => { await RelicCmd.Obtain<PaelsEye>(player); });
            if (ability)
            {
                if (code == "U21") { await Play("C24", "prior-lightning-one"); await Play("C24", "prior-lightning-two"); }
                await DeployFirst(); await Play(code == "U26-extra" ? "U26" : code, "paid-second-deployment", upgrade: upgraded);
                await AbilityEvents("same-turn");
            }
            else await InitialHistory();
            if (code == "U03") await Fixture("native-positive-retention-input", () => CreatureCmd.GainBlock(Owner, 40m, ValueProp.Unpowered, null));
            if (code == "U26-extra") await Fixture("native-Mayhem-two-unpaid-attacks-after-normal-draw", async () => {
                await Create("B01", pile: PileType.Draw); await Create("B01", pile: PileType.Draw);
                for (int i = 0; i < 5; i++) await Create("B02", pile: PileType.Draw);
                await PowerCmd.Apply<MayhemPower>(Choices, Owner, 2, Owner, null);
            });
            await EndTurn("native-normal-next-player-turn");
            if (code == "U26-extra")
            {
                await Fixture("native-remove-Mayhem-fixture-after-original-auto-phase", () => PowerCmd.Remove<MayhemPower>(Owner));
                await EndTurn("native-PaelsEye-extra-player-turn");
            }
            await NormalizeTurn();
            if (ability) await AbilityEvents("next-turn"); else await FollowingHistory();
            if (code == "U13") await EndTurn("native-second-recovery-must-not-repeat");
            await NativeAcceptanceRunHost.WaitForQuiet(combat);
            var oldCombat = combat; var beforeExit = Snapshot();
            subscription?.Dispose(); subscription = null;
            await RunManager.Instance.EnterRoom(new MapRoom());
            await RunManager.Instance.EnterRoomDebug(RoomType.Monster, model: ModelDb.Encounter<SlimesWeak>().ToMutable(), showTransition: false);
            await Until(() => CombatManager.Instance.DebugOnlyGetState() is CombatState next && !ReferenceEquals(next, oldCombat) && player.PlayerCombatState is { Phase: PlayerTurnPhase.Play } && next.CurrentSide == CombatSide.Player, "Native exit and next combat");
            combat = CombatManager.Instance.DebugOnlyGetState()!; enemies = combat.Enemies.ToArray();
            await NativeAcceptanceRunHost.WaitForQuiet(combat, 1);
            var afterReentry = Snapshot(); Subscribe(); await PrepareCombat("native-second-combat-isolation-no-power-reset");
            await Play("B01", "new-combat-first", 0); await Play("B01", "new-combat-second", 0);
            await Play("C24", "new-combat-lightning"); await Play("B04", "new-combat-engage", 1); await Play("U07", "new-combat-no-coupon", 2);
            if (code is "R28" or "R30") { await Play("T01", "new-combat-claw", 0); await Play("T02", "new-combat-body"); }
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            return JsonSerializer.SerializeToElement(new {
                schema = 1, token, runRef, scenario = "card-lifecycle", variant, code, upgraded, completed = true, version = release.Version, commit = release.Commit,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, acceptance = "paid-native-queue-controlled-first-instance-and-room-lifecycle-not-OS-input",
                playerRef = Ref(player), ownerRef = Ref(Owner), original, fixtures = Fixtures, actions = Actions, transitions = Transitions,
                confirmations = Confirmations, choiceSync = ChoiceSync,
                reentry = new { beforeExit, afterReentry, samePlayer = ReferenceEquals(player, combat.Players.Single()), combatChanged = !ReferenceEquals(oldCombat, combat) }, final = Snapshot()
            });
        }
        finally { subscription?.Dispose(); subscription = null; }
    }
    [HarmonyPatch(typeof(PlayerChoiceSynchronizer), nameof(PlayerChoiceSynchronizer.SyncLocalChoice))]
    private static class SyncChoice
    {
        private static void Postfix(Player player, uint choiceId, PlayerChoiceResult result)
        { if (ReferenceEquals(player, CardLifecycleAcceptanceProbe.player)) ChoiceSync.Add(new { choiceId, selected = result.AsCombatCards().Select(Ref).ToArray(), round = combat.RoundNumber, turn = Pcs.TurnNumber }); }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterEnergySpent))]
    private static class Payment
    {
        private static void Prefix(CardModel card, int amount)
        { if (ReferenceEquals(card.Owner, player)) Payments.Add(new { cardRef = Ref(card), amount, energy = Pcs.Energy }); }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.BeforeCardPlayed))]
    private static class Effect
    {
        private static void Postfix(CardPlay cardPlay, ref Task __result) => __result = Observe(__result, cardPlay);
        private static async Task Observe(Task original, CardPlay play)
        {
            await original;
            if (ReferenceEquals(play.Card.Owner, player)) Effects.Add(new { cardRef = Ref(play.Card), index = play.PlayIndex, count = play.PlayCount,
                autoPlay = play.IsAutoPlay, spent = play.Resources.EnergySpent, state = Snapshot() });
        }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterTakingExtraTurn))]
    private static class ExtraTurn
    {
        private static void Prefix(Player player)
        { if (ReferenceEquals(player, CardLifecycleAcceptanceProbe.player)) ExtraTurns.Add(new { playerRef = Ref(player), state = Snapshot() }); }
    }
}
