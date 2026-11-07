using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Runs;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;
using VoidCard = MegaCrit.Sts2.Core.Models.Cards.Void;

namespace Volibear;

/// <summary>Raw native mechanism observations, not payment/input or formal enemy acceptance.
/// External fixture comparator owns all expected values. No gameplay method is replaced.</summary>
internal static class PersistentContractProbe
{
    private static readonly Harmony Observer = new("Volibear.PersistentContractObserver");
    private static readonly Dictionary<CardModel, string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly Dictionary<PowerModel, int> Powers = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> BeforeEffects = [];
    private static readonly List<object> AbsorptionEvents = [];
    private static bool _observeEngage;
    private static bool _extraObserve;
    private static bool _phaseObserve;
    private static bool _engagementObserve;
    private static bool _nestedObserve;
    private static CardModel? _paymentCard;
    private static readonly List<object> PaymentEvents = [];
    private static readonly List<object> PaymentBeforeEffects = [];
    private static readonly List<object> NestedFinishes = [];
    private static readonly List<object> DrawResponses = [];
    private static readonly List<object> FinishedEffects = [];
    private static readonly List<decimal> PhaseBlockGains = [];
    private static readonly List<string> ClearPreventers = [];
    private static Player? _player;
    private static bool _started;
    private static string? CardRef(CardModel? card) => card is null ? null : Cards.TryGetValue(card, out var id)
        ? id : throw new InvalidOperationException("Unregistered native card identity");
    private static int PowerRef(PowerModel power)
    {
        if (!Powers.TryGetValue(power, out var id)) Powers.Add(power, id = Powers.Count + 1);
        return id;
    }
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObserveBeforeEffects)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveAbsorption)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveFinished)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveDrawResponse)).Patch();
        Observer.CreateClassProcessor(typeof(ObservePayment)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveBlockGain)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveClearPreventer)).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state)
    {
        if (_started) return;
        _started = true;
        _ = Run(state);
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PERSISTENT_CASE");
            if (!string.IsNullOrWhiteSpace(token) && variant is ("PP-U25-live-finish-count" or "PP-U32-max-coupon"))
            {
                await Special(state, token, variant);
                return;
            }
            if (!string.IsNullOrWhiteSpace(token) && variant is ("PP-U04-independent-first" or "PP-U19-draw-before-extend" or "PP-R18-independent-batches"))
            {
                await Engagement(state, token, variant);
                return;
            }
            if (!string.IsNullOrWhiteSpace(token) && variant is ("PP-U02-instances" or "PP-U02-domain-order" or
                "PP-U03-min-stack" or "PP-U03-other-retention" or "PP-U03-clamp-priority" or "PP-R16-positive-own-block" or "PP-R16-passive-block-excluded" or "PP-U34-per-batch"))
            {
                await Additional(state, token, variant);
                return;
            }
            if (string.IsNullOrWhiteSpace(token) || variant is not ("PP-U21-deploy-at-three" or "PP-U21-two-independent" or
                "PP-U26-before-effects" or "PP-U25-replay" or "PP-U25-purification" or "PP-R02-unpowered" or "PP-R02-no-consumption"))
                throw new InvalidOperationException("Missing token or unsupported persistent fixture; not a pass");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            var player = state.Players.Single();
            var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("Missing player combat state");
            var owner = player.Creature;
            var enemies = state.Enemies.ToArray();
            bool nativeClamp = variant == "PP-R02-no-consumption";
            if (enemies.Length != (nativeClamp ? 2 : 3) || owner.CurrentHp != 80 || owner.Block != 0 || state.RoundNumber != 1 || pcs.TurnNumber != 1 ||
                owner.Powers.Any() || LightningBatches.GetTurnCount(owner) != 0 || enemies.Any(e => e.Block != 0 || e.CombatId is null))
                throw new InvalidOperationException("Expected fresh three-enemy first-turn fixture");
            var context = new ThrowingPlayerChoiceContext();
            _player = player;
            foreach (var card in pcs.AllPiles.SelectMany(p => p.Cards).Distinct()) Cards.Add(card, "starting-" + Cards.Count);
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100m);
            await PlayerCmd.SetEnergy(variant.StartsWith("PP-U21", StringComparison.Ordinal) ? 0 : 3, player);
            var batches = new List<object>();
            using var subscription = LightningBatches.Subscribe(owner, (_, batch) =>
            {
                batches.Add(new { id = batch.Id, round = batch.RoundNumber, turn = batch.PlayerTurnNumber,
                    count = batch.CountThisTurn, baseDamage = batch.BaseDamage, storm = batch.StormCharge,
                    amount = batch.Amount, cardRef = CardRef(batch.Card),
                    targets = batch.Targets.Select(e => e.CombatId).ToArray(),
                    hits = batch.Results.Select(r => new { target = r.Receiver.CombatId, hpLost = r.HpLost, blocked = r.Blocked }).ToArray() });
                return Task.CompletedTask;
            });
            object Snapshot(string label) => new { label, round = state.RoundNumber, turn = pcs.TurnNumber,
                energy = pcs.Energy, hp = owner.CurrentHp, block = owner.Block,
                enemyHp = enemies.Select(e => e.CurrentHp).ToArray(), lightningCount = LightningBatches.GetTurnCount(owner),
                powers = owner.Powers.Select(p => new { powerRef = PowerRef(p), type = p.GetType().Name, amount = p.Amount }).ToArray() };
            var snapshots = new List<object> { Snapshot("initial") };
            int historyStart = CombatManager.Instance.History.Entries.Count();
            var inputs = new List<object>();
            async Task Apply<T>(int amount) where T : PowerModel
            {
                inputs.Add(new { op = "PowerCmd.Apply", type = typeof(T).Name, amount });
                await PowerCmd.Apply<T>(context, owner, amount, owner, null);
            }
            async Task Play(CardModel card)
            {
                await CardPileCmd.Add(card, pcs.Hand);
                inputs.Add(new { op = "CardCmd.AutoPlay", cardRef = CardRef(card), type = card.GetType().Name,
                    replay = card.BaseReplayCount, target = enemies[0].CombatId });
                await CardCmd.AutoPlay(context, card, enemies[0]);
            }
            CardModel CreateAttack(string id, int replay = 0)
            {
                var card = state.CreateCard<Volibear_B01>(player);
                Cards.Add(card, id);
                card.BaseReplayCount = replay;
                return card;
            }
            object? draw = null;
            object? engage = null;
            if (variant.StartsWith("PP-U21", StringComparison.Ordinal))
            {
                int initial = variant == "PP-U21-deploy-at-three" ? 3 : 5;
                for (int i = 0; i < initial; i++) await LightningCmd.DealAllEnemies(context, owner, 0);
                snapshots.Add(Snapshot("before-deploy"));
                await Apply<ThunderAftershockPower>(1);
                if (initial == 5) await Apply<ThunderAftershockPower>(1);
                snapshots.Add(Snapshot("after-deploy"));
                for (int i = initial + 1; i <= (initial == 3 ? 4 : 8); i++)
                {
                    inputs.Add(new { op = "LightningCmd.DealAllEnemies", baseDamage = 0 });
                    await LightningCmd.DealAllEnemies(context, owner, 0);
                    snapshots.Add(Snapshot("batch-" + i));
                }
            }
            else if (variant == "PP-U26-before-effects")
            {
                await Apply<GrowingFuryPower>(1);
                await Apply<GrowingFuryPower>(2);
                await Play(CreateAttack("first"));
                snapshots.Add(Snapshot("after-first"));
                await Play(CreateAttack("second", 1));
                snapshots.Add(Snapshot("after-second"));
            }
            else if (variant.StartsWith("PP-U25", StringComparison.Ordinal))
            {
                await Apply<PreyStillStandsPower>(1);
                if (variant == "PP-U25-purification") await DomainPower.Open(context, owner, 1);
                await Play(CreateAttack("first"));
                snapshots.Add(Snapshot("after-first"));
                var drawnAttack = CreateAttack("drawn-attack");
                await CardPileCmd.Add(drawnAttack, PileType.Draw, CardPilePosition.Top);
                CardModel? status = null;
                if (variant == "PP-U25-purification")
                {
                    status = state.CreateCard<VoidCard>(player);
                    Cards.Add(status, "direct-status");
                    await CardPileCmd.Add(status, PileType.Draw, CardPilePosition.Top);
                }
                await Play(CreateAttack("second", variant == "PP-U25-replay" ? 1 : 0));
                snapshots.Add(Snapshot("after-second"));
                draw = new { attackRef = CardRef(drawnAttack), type = drawnAttack.GetType().Name,
                    cost = drawnAttack.EnergyCost.GetWithModifiers(CostModifiers.Local), pile = drawnAttack.Pile?.Type.ToString(),
                    identityInHand = pcs.Hand.Cards.Any(c => ReferenceEquals(c, drawnAttack)),
                    statusRef = CardRef(status), statusPile = status?.Pile?.Type.ToString(),
                    statusIdentityInExhaust = status is not null && PileType.Exhaust.GetPile(player).Cards.Any(c => ReferenceEquals(c, status)),
                    targetCount = AttackHistory.TargetAttackCount(player, enemies[0]) };
            }
            else if (nativeClamp)
            {
                if (enemies.Any(e => e.Monster is not Chomper) ||
                    enemies[0].Monster!.NextMove.Id != "CLAMP_MOVE" || enemies[1].Monster!.NextMove.Id != "SCREECH_MOVE")
                    throw new InvalidOperationException("Expected untouched native ChompersNormal opening moves at ascension zero");
                var source = CreateAttack("engage-source");
                var rewardDraw = CreateAttack("engage-draw");
                await CardPileCmd.Add(rewardDraw, PileType.Draw, CardPilePosition.Top);
                for (int i = 0; i < 2; i++)
                {
                    inputs.Add(new { op = "ImmovableBodyPower.Deploy", cardRef = CardRef(source) });
                    await ImmovableBodyPower.Deploy(context, owner, source);
                }
                await CreatureCmd.GainBlock(owner, 5, ValueProp.Unpowered, null);
                snapshots.Add(Snapshot("before-engage"));
                int Moves(int index) => CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>()
                    .Count(e => ReferenceEquals(e.Monster, enemies[index].Monster));
                var movesBefore = enemies.Select(e => e.Monster!.NextMove.Id).ToArray();
                var moveCountsBefore = new[] { Moves(0), Moves(1) };
                bool consumedBefore = EngageCmd.Consumed(enemies[0]);
                inputs.Add(new { op = "EngageCmd.Perform", cardRef = CardRef(source), target = enemies[0].CombatId });
                _observeEngage = true;
                var receipt = await EngageCmd.Perform(context, enemies[0], source);
                _observeEngage = false;
                snapshots.Add(Snapshot("after-engage"));
                bool consumedAfter = EngageCmd.Consumed(enemies[0]);
                var movesAfterEngage = enemies.Select(e => e.Monster!.NextMove.Id).ToArray();
                var moveCountsAfter = new[] { Moves(0), Moves(1) };
                var duplicate = await EngageCmd.Perform(context, enemies[0], source);
                snapshots.Add(Snapshot("after-duplicate"));
                var duplicateCounts = new[] { Moves(0), Moves(1) };
                inputs.Add(new { op = "PlayerCmd.EndTurn" });
                PlayerCmd.EndTurn(player, canBackOut: false);
                var deadline = System.Diagnostics.Stopwatch.StartNew();
                while (state.RoundNumber <= 1 || state.CurrentSide != CombatSide.Player || pcs.Phase != PlayerTurnPhase.Play)
                {
                    if (deadline.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException("Chomper native phase timed out");
                    var tree = (SceneTree)Engine.GetMainLoop();
                    await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                }
                snapshots.Add(Snapshot("after-native-phase"));
                engage = new { target = enemies[0].CombatId, consumedBefore, consumedAfter,
                    consumedNextTurn = EngageCmd.Consumed(enemies[0]), movesBefore, movesAfterEngage,
                    movesNextTurn = enemies.Select(e => e.Monster!.NextMove.Id).ToArray(),
                    moveCountsBefore, moveCountsAfter, duplicateCounts, moveCountsNextTurn = new[] { Moves(0), Moves(1) },
                    receipt = new { performed = receipt.Performed, completed = receipt.Completed, absorbed = receipt.Absorbed },
                    duplicate = new { performed = duplicate.Performed, completed = duplicate.Completed, absorbed = duplicate.Absorbed },
                    absorption = AbsorptionEvents,
                    stateLogs = enemies.Select(e => e.Monster!.MoveStateMachine!.StateLog.Select(s => s.Id).ToArray()).ToArray() };
            }
            else
            {
                await Apply<ImmovableBodyPower>(1);
                await CreatureCmd.GainBlock(owner, 5, ValueProp.Unpowered, null);
                snapshots.Add(Snapshot("before-damage"));
                inputs.Add(new { op = "CreatureCmd.Damage", amount = 8, props = (int)ValueProp.Unpowered });
                await NativeCompat.Damage(context, owner, 8, ValueProp.Unpowered, enemies[0], null);
                snapshots.Add(Snapshot("after-damage"));
            }
            var history = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing release metadata");
            GD.Print("[Volibear] PERSISTENT_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
                token, scenario = "persistent-contract", variant, completed = true,
                gameVersion = release.Version, gameCommit = release.Commit,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "mechanism-autoplay-not-payment-not-formal-enemy", character = player.Character.GetType().Name,
                enemyIds = enemies.Select(e => e.CombatId).ToArray(), enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                inputs, snapshots, beforeEffects = BeforeEffects, batches, draw, engage,
                playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = CardRef(e.CardPlay.Card),
                    index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
                drawHistory = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = CardRef(e.Card), fromHandDraw = e.FromHandDraw }).ToArray(),
                damageHistory = history.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,
                    playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage,
                    props = (int)e.Result.Props, cardRef = CardRef(e.CardSource) }).ToArray()
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception e)
        {
            GD.PrintErr("[Volibear] PERSISTENT_CONTRACT_ERROR " + e);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            _player = null;
            CombatManager.Instance.TurnStarted -= Start;
            Observer.UnpatchAll(Observer.Id);
        }
    }

    private static async Task Special(CombatState state, string token, string variant)
    {
        if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("Native only");
        var player = state.Players.Single(); var owner = player.Creature; var pcs = player.PlayerCombatState!;
        var enemies = state.Enemies.ToArray(); var context = new ThrowingPlayerChoiceContext();
        if (enemies.Length != 3 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() || state.RoundNumber != 1 || pcs.TurnNumber != 1)
            throw new InvalidOperationException("Fresh special fixture required");
        _player = player;
        foreach (var card in pcs.AllPiles.SelectMany(p => p.Cards).Distinct()) Cards.Add(card, "starting-" + Cards.Count);
        foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
        var removedRelics = player.Relics.Select(r => r.GetType().Name).ToArray();
        foreach (var relic in player.Relics.ToArray()) await RelicCmd.Remove(relic);
        foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100);
        await PlayerCmd.SetEnergy(3, player);
        bool nested = variant == "PP-U25-live-finish-count";
        var eliminated = new List<object>();
        if (nested)
            foreach (var enemy in enemies.Skip(1))
            {
                await CreatureCmd.Kill(enemy);
                eliminated.Add(new { enemy = enemy.CombatId, hp = enemy.CurrentHp, dead = enemy.IsDead,
                    stillHittable = state.HittableEnemies.Contains(enemy) });
            }
        object Snapshot() => new { round = state.RoundNumber, turn = pcs.TurnNumber, hp = owner.CurrentHp, block = owner.Block,
            energy = pcs.Energy, enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),
            powers = owner.Powers.Select(p => new { powerRef = PowerRef(p), type = p.GetType().Name, amount = p.Amount }).ToArray(),
            targetCount = AttackHistory.TargetAttackCount(player, enemies[0]), lightning = LightningBatches.GetTurnCount(owner) };
        object? special;
        int boundary = CombatManager.Instance.History.Entries.Count();
        if (nested)
        {
            var prey = await PowerCmd.Apply<PreyStillStandsPower>(context, owner, 1, owner, null)
                ?? throw new InvalidOperationException("Prey not applied");
            await PowerCmd.Apply<HellraiserPower>(context, owner, 1, owner, null);
            object PreyState()
            {
                var data = typeof(PowerModel).GetField("_internalData", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(prey)
                    ?? throw new InvalidOperationException("Native per-instance data absent");
                object Field(string name) => data.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)!.GetValue(data)!;
                return new { powerRef = PowerRef(prey), usedRound = Field("UsedRound"), usedTurn = Field("UsedTurn") };
            }
            var before = Snapshot(); var allowanceBefore = PreyState();
            var first = state.CreateCard<Volibear_B01>(player); Cards.Add(first, "first");
            var outer = state.CreateCard<MegaCrit.Sts2.Core.Models.Cards.PommelStrike>(player); Cards.Add(outer, "outer");
            var inner = state.CreateCard<MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad>(player); Cards.Add(inner, "inner");
            await CardPileCmd.Add(first, pcs.Hand);
            _nestedObserve = true;
            await CardCmd.AutoPlay(context, first, enemies[0]);
            await CardPileCmd.Add(inner, PileType.Draw, CardPilePosition.Top);
            await CardPileCmd.Add(outer, pcs.Hand);
            await CardCmd.AutoPlay(context, outer, enemies[0]);
            _nestedObserve = false;
            special = new { before, after = Snapshot(), allowanceBefore, allowanceAfter = PreyState(), finishes = NestedFinishes,
                cards = new CardModel[] { first, outer, inner }.Select(c => new { cardRef = CardRef(c), type = c.GetType().Name,
                    cost = c.EnergyCost.GetWithModifiers(CostModifiers.Local), pile = c.Pile?.Type.ToString(),
                    isStrike = c.Tags.Contains(CardTag.Strike) }).ToArray() };
        }
        else
        {
            await PowerCmd.Apply<WelcomeThunderPower>(context, owner, 1, owner, null);
            await PowerCmd.Apply<WelcomeThunderPower>(context, owner, 2, owner, null);
            var source = state.CreateCard<Volibear_B01>(player); Cards.Add(source, "fixture-source");
            string initialMove = enemies[0].Monster!.NextMove.Id;
            var receipt = await EngageCmd.Perform(context, enemies[0], source);
            var paid = state.CreateCard<MegaCrit.Sts2.Core.Models.Cards.Bludgeon>(player); Cards.Add(paid, "paid");
            await CardPileCmd.Add(paid, pcs.Hand); _paymentCard = paid;
            object PaymentState() => new { energy = pcs.Energy, coupon = owner.GetPowerAmount<NextAttackDiscount>(),
                canonicalCost = paid.EnergyCost.Canonical, cost = paid.EnergyCost.GetWithModifiers(CostModifiers.All),
                pile = paid.Pile?.Type.ToString(), hp = enemies[0].CurrentHp, paymentEvents = PaymentEvents.Count };
            var before = Snapshot(); var beforeInvalid = PaymentState(); var actions = new List<object>();
            async Task Queue(string role, Creature target)
            {
                var action = new PlayCardAction(paid, target); var events = new List<object>();
                void Observe(string label, GameAction current) => events.Add(new { label, state = current.State.ToString(),
                    id = current.Id, energy = pcs.Energy, coupon = owner.GetPowerAmount<NextAttackDiscount>(), pile = paid.Pile?.Type.ToString() });
                action.BeforeExecuted += a => Observe("before-executed", a);
                action.BeforeCancelled += a => Observe("cancelled", a);
                action.AfterFinished += a => Observe("after-finished", a);
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
                var watch = System.Diagnostics.Stopwatch.StartNew();
                while (!action.CompletionTask.IsCompleted)
                {
                    if (watch.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException("Native payment action timed out: " + role);
                    var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                }
                await action.CompletionTask;
                if (action.Exception is not null) throw new InvalidOperationException("Native action failed", action.Exception);
                actions.Add(new { role, id = action.Id, target = action.TargetId, state = action.State.ToString(),
                    type = action.GetType().Name, actionType = action.ActionType.ToString(),
                    sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(), paid),
                    context = action.PlayerChoiceContext?.GetType().Name, events });
            }
            await Queue("invalid-self-target", owner); var afterInvalid = PaymentState();
            await Queue("valid-enemy-target", enemies[0]); var afterValid = PaymentState();
            special = new { initialMove, receipt = new { performed = receipt.Performed, completed = receipt.Completed, absorbed = receipt.Absorbed },
                before, after = Snapshot(), beforeInvalid, afterInvalid, afterValid, actions, paymentEvents = PaymentEvents, paymentBeforeEffects = PaymentBeforeEffects };
            _paymentCard = null;
        }
        var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray(); var release = ReleaseInfoManager.Instance.ReleaseInfo!;
        GD.Print("[Volibear] PERSISTENT_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
            token, scenario = "persistent-contract", variant, completed = true, schema = "special-v1", gameVersion = release.Version, gameCommit = release.Commit,
            testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, character = player.Character.GetType().Name,
            acceptance = nested ? "native-nested-autoplay-not-payment" : "native-action-queue-not-mouse",
            enemyIds = enemies.Select(e => e.CombatId).ToArray(), enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
            removedRelics, eliminated, special, beforeEffects = BeforeEffects,
            playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = CardRef(e.CardPlay.Card), index = e.CardPlay.PlayIndex,
                count = e.CardPlay.PlayCount, autoPlay = e.CardPlay.IsAutoPlay, spent = e.CardPlay.Resources.EnergySpent }).ToArray(),
            drawHistory = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = CardRef(e.Card), fromHandDraw = e.FromHandDraw }).ToArray(),
            energyHistory = history.OfType<EnergySpentEntry>().Select(e => e.Amount).ToArray(),
            damageHistory = history.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId, playerTarget = ReferenceEquals(e.Receiver, owner),
                hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage, props = (int)e.Result.Props, cardRef = CardRef(e.CardSource) }).ToArray()
        }));
        GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
    }

    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterEnergySpent))]
    private static class ObservePayment
    {
        private static void Prefix(CardModel card, int amount)
        {
            if (_player is not null && ReferenceEquals(card, _paymentCard))
                PaymentEvents.Add(new { cardRef = CardRef(card), amount, energy = _player.PlayerCombatState!.Energy,
                    coupon = _player.Creature.GetPowerAmount<NextAttackDiscount>() });
        }
    }

    private static async Task Engagement(CombatState state, string token, string variant)
    {
        if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("Native only");
        var player = state.Players.Single(); var owner = player.Creature; var pcs = player.PlayerCombatState!;
        var enemies = state.Enemies.ToArray();
        if (enemies.Length != 3 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() || state.RoundNumber != 1 || pcs.TurnNumber != 1)
            throw new InvalidOperationException("Fresh three-enemy fixture required");
        _player = player; var context = new ThrowingPlayerChoiceContext();
        foreach (var card in pcs.AllPiles.SelectMany(p => p.Cards).Distinct()) Cards.Add(card, "starting-" + Cards.Count);
        foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
        var removedRelics = player.Relics.Select(r => r.GetType().Name).ToArray();
        foreach (var relic in player.Relics.ToArray()) await RelicCmd.Remove(relic);
        foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100);
        await PlayerCmd.SetEnergy(3, player);
        var source = state.CreateCard<Volibear_B01>(player); Cards.Add(source, "fixture-source");
        CardModel? status = null;
        if (variant == "PP-U04-independent-first") await PowerCmd.Apply<BattleScarsPower>(context, owner, 1, owner, null);
        else if (variant == "PP-U19-draw-before-extend")
        {
            await PowerCmd.Apply<LingeringStormPower>(context, owner, 1, owner, null);
            status = state.CreateCard<VoidCard>(player); Cards.Add(status, "direct-status");
            await CardPileCmd.Add(status, PileType.Draw, CardPilePosition.Top);
        }
        else
        {
            await PowerCmd.Apply<ThunderPoolPower>(context, owner, 4, owner, null);
            await PowerCmd.Apply<ThunderPoolPower>(context, owner, 6, owner, null);
        }
        object Snapshot(string label) => new { label, round = state.RoundNumber, turn = pcs.TurnNumber, hp = owner.CurrentHp,
            block = owner.Block, energy = pcs.Energy, enemyHp = enemies.Select(e => e.CurrentHp).ToArray(), count = LightningBatches.GetTurnCount(owner),
            powers = owner.Powers.Select(p => new { powerRef = PowerRef(p), type = p.GetType().Name, amount = p.Amount }).ToArray() };
        var stages = new List<object> { Snapshot("before") };
        var moves = enemies.Select(e => e.Monster!.NextMove.Id).ToArray();
        var receipts = new List<object>(); var batches = new List<object>();
        int boundary = CombatManager.Instance.History.Entries.Count();
        using var subscription = LightningBatches.Subscribe(owner, (_, batch) =>
        {
            batches.Add(new { id = batch.Id, round = batch.RoundNumber, turn = batch.PlayerTurnNumber, count = batch.CountThisTurn,
                baseDamage = batch.BaseDamage, storm = batch.StormCharge, amount = batch.Amount, cardRef = CardRef(batch.Card),
                targets = batch.Targets.Select(e => e.CombatId).ToArray(),
                hits = batch.Results.Select(h => new { target = h.Receiver.CombatId, hpLost = h.HpLost, blocked = h.Blocked }).ToArray() });
            return Task.CompletedTask;
        });
        async Task Engage(int index)
        {
            var receipt = await EngageCmd.Perform(context, enemies[index], source);
            receipts.Add(new { target = enemies[index].CombatId, performed = receipt.Performed, completed = receipt.Completed,
                absorbed = receipt.Absorbed, consumed = EngageCmd.Consumed(enemies[index]) });
        }
        _engagementObserve = true;
        await Engage(0); stages.Add(Snapshot("after-first"));
        if (variant == "PP-U04-independent-first")
        {
            await PowerCmd.Apply<BattleScarsPower>(context, owner, 2, owner, null);
            stages.Add(Snapshot("after-second-deploy"));
        }
        if (variant != "PP-U19-draw-before-extend") { await Engage(1); stages.Add(Snapshot("after-second")); }
        if (variant == "PP-R18-independent-batches")
        {
            PlayerCmd.EndTurn(player, canBackOut: false);
            var watch = System.Diagnostics.Stopwatch.StartNew();
            while (state.RoundNumber <= 1 || state.CurrentSide != CombatSide.Player || pcs.Phase != PlayerTurnPhase.Play)
            {
                if (watch.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException("Pool native phase timed out");
                var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            }
            stages.Add(Snapshot("after-native-phase"));
        }
        _engagementObserve = false;
        var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
        var release = ReleaseInfoManager.Instance.ReleaseInfo!;
        GD.Print("[Volibear] PERSISTENT_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
            token, scenario = "persistent-contract", variant, completed = true, schema = "engagement-v1",
            gameVersion = release.Version, gameCommit = release.Commit, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
            acceptance = "mechanism-autoplay-not-payment-not-formal-enemy", character = player.Character.GetType().Name,
            enemyIds = enemies.Select(e => e.CombatId).ToArray(), enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
            removedRelics, initialMoves = moves, stages, receipts, batches, drawResponses = DrawResponses,
            consumed = enemies.Select(EngageCmd.Consumed).ToArray(),
            status = status is null ? null : new { cardRef = CardRef(status), pile = status.Pile?.Type.ToString(),
                inHand = pcs.Hand.Cards.Any(c => ReferenceEquals(c, status)), inExhaust = PileType.Exhaust.GetPile(player).Cards.Any(c => ReferenceEquals(c, status)) },
            playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = CardRef(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
            drawHistory = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = CardRef(e.Card), fromHandDraw = e.FromHandDraw }).ToArray(),
            moveHistory = history.OfType<MonsterPerformedMoveEntry>().Select(e => e.Monster.Creature.CombatId).ToArray(),
            damageHistory = history.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,
                playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage,
                props = (int)e.Result.Props, cardRef = CardRef(e.CardSource) }).ToArray()
        }));
        GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
        MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
    }

    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterCardDrawn))]
    private static class ObserveDrawResponse
    {
        private static void Postfix(CardModel card, bool fromHandDraw, ref Task __result) => __result = Observe(__result, card, fromHandDraw);
        private static async Task Observe(Task task, CardModel card, bool fromHandDraw)
        {
            await task;
            if (!_engagementObserve || _player is null || !ReferenceEquals(card.Owner, _player)) return;
            DrawResponses.Add(new { cardRef = CardRef(card), fromHandDraw, domain = _player.Creature.GetPowerAmount<DomainPower>(),
                energy = _player.PlayerCombatState!.Energy, pile = card.Pile?.Type.ToString() });
        }
    }

    private static async Task Additional(CombatState state, string token, string variant)
    {
        if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("Native only");
        var player = state.Players.Single();
        var owner = player.Creature;
        var pcs = player.PlayerCombatState!;
        var enemies = state.Enemies.ToArray();
        bool conduction = variant.StartsWith("PP-U02", StringComparison.Ordinal);
        bool standing = variant.StartsWith("PP-U03", StringComparison.Ordinal);
        if (enemies.Length != (conduction ? 2 : 3) || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() ||
            state.RoundNumber != 1 || pcs.TurnNumber != 1) throw new InvalidOperationException("Fresh fixture required");
        _player = player;
        var context = new ThrowingPlayerChoiceContext();
        foreach (var card in pcs.AllPiles.SelectMany(p => p.Cards).Distinct()) Cards.Add(card, "starting-" + Cards.Count);
        foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
        var removedRelics = player.Relics.Select(r => r.GetType().Name).ToArray();
        foreach (var relic in player.Relics.ToArray()) await RelicCmd.Remove(relic);
        foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100);
        await PlayerCmd.SetEnergy(3, player);
        var source = state.CreateCard<Volibear_B01>(player);
        Cards.Add(source, "fixture-source");
        var preparations = new List<object>();
        int preparationStart = CombatManager.Instance.History.Entries.Count();
        if (standing)
        {
            // Fixture preparation uses actual moves. Observed boundary begins only AFTER
            // all early-consumed actions and the explicit HP/block starting-state setup.
            foreach (var enemy in enemies)
            {
                var move = enemy.Monster!.NextMove.Id;
                var result = await EngageCmd.Perform(context, enemy, source);
                preparations.Add(new { enemy = enemy.CombatId, move, performed = result.Performed,
                    completed = result.Completed, absorbed = result.Absorbed, consumed = EngageCmd.Consumed(enemy) });
            }
            await CreatureCmd.SetCurrentHp(owner, 80);
            if (owner.Block > 0) await NativeCompat.LoseBlock(owner, owner.Block);
        }
        var preparationHistory = CombatManager.Instance.History.Entries.Skip(preparationStart).ToArray();
        var setup = new List<object>();
        async Task Apply<T>(int amount) where T : PowerModel
        {
            setup.Add(new { type = typeof(T).Name, amount });
            await PowerCmd.Apply<T>(context, owner, amount, owner, null);
        }
        CardModel? played = null;
        if (variant == "PP-U02-instances")
        {
            await Apply<StormConductionPower>(3); await Apply<StormConductionPower>(4);
        }
        else if (variant == "PP-U02-domain-order")
        {
            await DomainPower.Open(context, owner, 1); await Apply<StormConductionPower>(3);
            await StormChargePower.Gain(context, owner, 2);
        }
        else if (standing)
        {
            var values = variant == "PP-U03-min-stack" ? new[] { 6, 3, 6 } : new[] { 3 };
            foreach (int value in values)
            {
                setup.Add(new { type = "StandingPower.Deploy", amount = value });
                await StandingPower.Deploy(context, owner, value, source);
            }
            if (variant == "PP-U03-other-retention") await Apply<BarricadePower>(1);
            if (variant == "PP-U03-clamp-priority")
            {
                // Native cap-style relic: without 留甲 it would clamp the retained block to 10.
                await RelicCmd.Obtain<SturdyClamp>(player);
                setup.Add(new { type = "SturdyClamp.Obtain", amount = 1 });
            }
            await CreatureCmd.GainBlock(owner, 20, ValueProp.Unpowered, null);
        }
        else if (variant == "PP-U34-per-batch")
        {
            await Apply<ThunderArmorPower>(3); await Apply<ThunderArmorPower>(4);
            foreach (var enemy in enemies) await CreatureCmd.GainBlock(enemy, 10, ValueProp.Unpowered, null);
        }
        else if (variant == "PP-R16-positive-own-block")
        {
            await Apply<BattleBodyPower>(2);
            played = state.CreateCard<MegaCrit.Sts2.Core.Models.Cards.IronWave>(player);
            played.BaseReplayCount = 1;
        }
        else
        {
            await Apply<BattleBodyPower>(1); await Apply<ThunderArmorPower>(3);
            await DomainPower.Open(context, owner, 1);
        }
        if (!standing && variant != "PP-U34-per-batch")
        {
            played ??= state.CreateCard<Volibear_B01>(player);
            Cards.Add(played, "played");
            await CardPileCmd.Add(played, pcs.Hand);
        }
        object Snapshot() => new { round = state.RoundNumber, turn = pcs.TurnNumber, hp = owner.CurrentHp, block = owner.Block,
            energy = pcs.Energy, enemyHp = enemies.Select(e => e.CurrentHp).ToArray(), enemyBlock = enemies.Select(e => e.Block).ToArray(),
            count = LightningBatches.GetTurnCount(owner), powers = owner.Powers.Select(p => new { powerRef = PowerRef(p), type = p.GetType().Name, amount = p.Amount }).ToArray() };
        var before = Snapshot();
        int boundary = CombatManager.Instance.History.Entries.Count();
        var batches = new List<object>();
        using var subscription = LightningBatches.Subscribe(owner, (_, batch) =>
        {
            batches.Add(new { id = batch.Id, round = batch.RoundNumber, turn = batch.PlayerTurnNumber, count = batch.CountThisTurn,
                baseDamage = batch.BaseDamage, storm = batch.StormCharge, amount = batch.Amount, cardRef = CardRef(batch.Card),
                targets = batch.Targets.Select(e => e.CombatId).ToArray(),
                hits = batch.Results.Select(h => new { target = h.Receiver.CombatId, hpLost = h.HpLost, blocked = h.Blocked }).ToArray() });
            return Task.CompletedTask;
        });
        _extraObserve = true;
        _phaseObserve = standing;
        if (standing)
        {
            PlayerCmd.EndTurn(player, canBackOut: false);
            var watch = System.Diagnostics.Stopwatch.StartNew();
            while (state.RoundNumber <= 1 || state.CurrentSide != CombatSide.Player || pcs.Phase != PlayerTurnPhase.Play)
            {
                if (watch.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException("Standing native player start timed out");
                var tree = (SceneTree)Engine.GetMainLoop();
                await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            }
        }
        else if (variant == "PP-U34-per-batch") await LightningCmd.DealAllEnemies(context, owner, 1);
        else await CardCmd.AutoPlay(context, played!, enemies[0]);
        _extraObserve = false;
        _phaseObserve = false;
        var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
        var release = ReleaseInfoManager.Instance.ReleaseInfo!;
        GD.Print("[Volibear] PERSISTENT_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
            token, scenario = "persistent-contract", variant, completed = true, schema = "additional-v1",
            gameVersion = release.Version, gameCommit = release.Commit, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
            acceptance = "mechanism-autoplay-not-payment-not-formal-enemy", character = player.Character.GetType().Name,
            enemyIds = enemies.Select(e => e.CombatId).ToArray(), enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
            fixturePreparation = new { removedRelics, restoredHpAfterPreparation = standing, preparations,
                moves = preparationHistory.OfType<MonsterPerformedMoveEntry>().Select(e => e.Monster.Creature.CombatId).ToArray(),
                damage = preparationHistory.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,
                    playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage,
                    props = (int)e.Result.Props, cardRef = CardRef(e.CardSource) }).ToArray(),
                measurementHistoryBoundary = boundary, preparationHistoryStart = preparationStart },
            setup, before, after = Snapshot(), batches, beforeEffects = BeforeEffects, finishedEffects = FinishedEffects,
            played = played is null ? null : new { cardRef = CardRef(played), type = played.GetType().Name, replay = played.BaseReplayCount },
            phaseBlockGains = PhaseBlockGains, clearPreventers = ClearPreventers,
            movesAfterBoundary = history.OfType<MonsterPerformedMoveEntry>().Select(e => e.Monster.Creature.CombatId).ToArray(),
            consumedAfterBoundary = enemies.Select(EngageCmd.Consumed).ToArray(),
            drawHistory = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = CardRef(e.Card), fromHandDraw = e.FromHandDraw }).ToArray(),
            playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = CardRef(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
            damageHistory = history.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,
                playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage,
                props = (int)e.Result.Props, cardRef = CardRef(e.CardSource) }).ToArray()
        }));
        GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
        MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
        ((SceneTree)Engine.GetMainLoop()).Quit(0);
    }

    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterBlockGained))]
    private static class ObserveBlockGain
    {
        private static void Prefix(Creature creature, decimal amount)
        {
            if (_phaseObserve && _player is not null && ReferenceEquals(creature, _player.Creature)) PhaseBlockGains.Add(amount);
        }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterPreventingBlockClear))]
    private static class ObserveClearPreventer
    {
        private static void Prefix(AbstractModel preventer, Creature creature)
        {
            if (_phaseObserve && _player is not null && ReferenceEquals(creature, _player.Creature)) ClearPreventers.Add(preventer.GetType().Name);
        }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterCardPlayed))]
    private static class ObserveFinished
    {
        private static void Postfix(CardPlay cardPlay, ref Task __result) => __result = Observe(__result, cardPlay);
        private static async Task Observe(Task task, CardPlay play)
        {
            await task;
            if (_nestedObserve && _player is not null && ReferenceEquals(play.Card.Owner, _player))
            {
                var snapshot = AttackHistory.Snapshot(play);
                NestedFinishes.Add(new { cardRef = CardRef(play.Card), playId = snapshot.PlayId,
                    capturedTargetOrdinal = snapshot.TargetOrdinal, liveTargetCount = play.Target is null ? 0 : AttackHistory.TargetAttackCount(_player, play.Target),
                    actualCompleted = snapshot.Completed });
            }
            if (!_extraObserve || _player is null || !ReferenceEquals(play.Card.Owner, _player)) return;
            FinishedEffects.Add(new { cardRef = CardRef(play.Card), index = play.PlayIndex, count = play.PlayCount,
                playId = CardResolutionHooks.CurrentPlayId(play.Card), actualCompleted = AttackHistory.Snapshot(play).Completed,
                strength = _player.Creature.GetPowerAmount<StrengthPower>(), dexterity = _player.Creature.GetPowerAmount<DexterityPower>() });
        }
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.DamageBlockInternal))]
    private static class ObserveAbsorption
    {
        private static void Postfix(Creature __instance, decimal amount, ValueProp props, decimal __result)
        {
            if (_observeEngage && _player is not null && ReferenceEquals(__instance, _player.Creature))
                AbsorptionEvents.Add(new { requested = amount, props = (int)props, absorbed = __result,
                    blockAfter = __instance.Block, hpBeforeLoss = __instance.CurrentHp });
        }
    }

    [HarmonyPatch(typeof(Hook), nameof(Hook.BeforeCardPlayed))]
    private static class ObserveBeforeEffects
    {
        private static void Postfix(CardPlay cardPlay, ref Task __result) => __result = Observe(__result, cardPlay);
        private static async Task Observe(Task original, CardPlay play)
        {
            await original; // Read only, after all native pre-effect responses, before native OnPlay.
            if (_player is null || !ReferenceEquals(play.Card.Owner, _player)) return;
            if (ReferenceEquals(play.Card, _paymentCard)) PaymentBeforeEffects.Add(new { cardRef = CardRef(play.Card),
                energy = _player.PlayerCombatState!.Energy, coupon = _player.Creature.GetPowerAmount<NextAttackDiscount>(),
                spent = play.Resources.EnergySpent, autoPlay = play.IsAutoPlay });
            BeforeEffects.Add(new { cardRef = CardRef(play.Card), index = play.PlayIndex, count = play.PlayCount,
                playId = CardResolutionHooks.CurrentPlayId(play.Card), ordinal = AttackHistory.CurrentAttackOrdinal(play),
                strength = _player.Creature.GetPowerAmount<StrengthPower>(), storm = StormChargePower.Current(_player.Creature) });
        }
    }
}
