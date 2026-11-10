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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>Initial prepared-card mechanism cases. Real queued card payment, not mouse input.
/// No selection-requiring case is implemented here; C19/U39 remain explicitly NOT_RUN.</summary>
internal static class PreparedContractProbe
{
    private static bool started;
    private static Player? player;
    private static readonly Harmony Observer = new("Volibear.PreparedContractObserver");
    private static readonly Dictionary<CardModel, string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly Dictionary<PowerModel, int> Powers = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Payments = [];
    private static readonly List<object> BeforeEffects = [];
    private static string? Ref(CardModel? card) => card is null ? null : Cards.TryGetValue(card, out var value)
        ? value : throw new InvalidOperationException("Unknown native card identity");
    private static int PowerRef(PowerModel power)
    {
        if (!Powers.TryGetValue(power, out var id)) Powers.Add(power, id = Powers.Count + 1);
        return id;
    }
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObservePayment)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveEffects)).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state)
    {
        if (started) return;
        started = true;
        _ = Run(state);
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PREPARED_CASE");
            if (string.IsNullOrWhiteSpace(token) || variant is not ("PR-training-dynamic-spells" or "PR-training-native-domain" or "PR-guard-instances" or "PR-replay-paid" or "PR-bite-segments"))
                throw new InvalidOperationException("Missing token or unsupported prepared case; NOT_RUN");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            player = state.Players.Single();
            var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("No player combat state");
            var owner = player.Creature;
            var enemies = state.Enemies.ToArray();
            if (enemies.Length != 3 || pcs.TurnNumber != 1 || state.RoundNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any()
                || player.Relics.Count != 1 || player.Relics[0] is not HuntersHeart)
                throw new InvalidOperationException("Expected fresh native three-slime fixture, only starter relic");
            if (enemies.Count(e => e.Monster is LeafSlimeS) != 1 || enemies.Count(e => e.Monster is TwigSlimeS) != 1 || enemies.Count(e => e.Monster is LeafSlimeM or TwigSlimeM) != 1)
                throw new InvalidOperationException("Wrong native encounter");
            var choices = new ThrowingPlayerChoiceContext();
            foreach (var card in pcs.AllPiles.SelectMany(p => p.Cards).Distinct()) Cards.Add(card, "starter-" + Cards.Count);
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
            foreach (var enemy in enemies)
            {
                await CreatureCmd.SetMaxAndCurrentHp(enemy, 500m);
                var monster = enemy.Monster!;
                string move = monster is LeafSlimeM ? "CLUMP_SHOT" : monster is TwigSlimeM ? "POKEY_POUNCE_MOVE" : "TACKLE_MOVE";
                var machine = monster.MoveStateMachine ?? throw new InvalidOperationException("Missing native move machine");
                monster.SetMoveImmediate((MoveState)machine.States[move], forceTransition: true);
            }
            await PlayerCmd.SetEnergy(10, player);
            var batches = new List<object>();
            using var subscription = LightningBatches.Subscribe(owner, (_, batch) =>
            {
                batches.Add(new { id = batch.Id, round = batch.RoundNumber, turn = batch.PlayerTurnNumber,
                    count = batch.CountThisTurn, baseDamage = batch.BaseDamage, amount = batch.Amount,
                    cardRef = Ref(batch.Card), targets = batch.Targets.Select(e => e.CombatId).ToArray(),
                    hits = batch.Results.Select(r => new { target = r.Receiver.CombatId, hpLost = r.HpLost, blocked = r.Blocked }).ToArray() });
                return Task.CompletedTask;
            });
            object Snapshot() => new { round = state.RoundNumber, turn = pcs.TurnNumber, energy = pcs.Energy,
                hp = owner.CurrentHp, block = owner.Block, enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),
                marks = enemies.Select(e => e.GetPowerAmount<BiteMarkPower>()).ToArray(),
                lightningCount = LightningBatches.GetTurnCount(owner), hand = pcs.Hand.Cards.Select(Ref).ToArray(),
                draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),
                powers = owner.Powers.Select(p => new { powerRef = PowerRef(p), type = p.GetType().Name, amount = p.Amount }).ToArray() };
            var initial = Snapshot();
            var actions = new List<object>();
            var steps = new List<object>();
            async Task<T> Create<T>(string label, bool upgraded = false) where T : CardModel
            {
                var card = state.CreateCard<T>(player ?? throw new InvalidOperationException("Fixture owner cleared")); Cards.Add(card, label);
                if (upgraded) CardCmd.Upgrade(card);
                await CardPileCmd.Add(card, pcs.Hand);
                return card;
            }
            async Task Play(CardModel card, Creature? target = null)
            {
                var before = Snapshot();
                int boundary = CombatManager.Instance.History.Entries.Count();
                var action = new PlayCardAction(card, target);
                var events = new List<object>();
                void Observe(string label, GameAction current) => events.Add(new { label, state = current.State.ToString(), id = current.Id, energy = pcs.Energy });
                action.BeforeExecuted += a => Observe("before-executed", a);
                action.BeforeCancelled += a => Observe("cancelled", a);
                action.AfterFinished += a => Observe("after-finished", a);
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
                var timer = System.Diagnostics.Stopwatch.StartNew();
                while (!action.CompletionTask.IsCompleted)
                {
                    if (timer.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException("Native prepared action timed out: " + Ref(card));
                    var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                }
                await action.CompletionTask;
                if (action.Exception is not null) throw new InvalidOperationException("Native action failed", action.Exception);
                actions.Add(new { cardRef = Ref(card), id = action.Id, target = action.TargetId, state = action.State.ToString(),
                    type = action.GetType().Name, actionType = action.ActionType.ToString(),
                    sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(), card),
                    context = action.PlayerChoiceContext?.GetType().Name, events });
                var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
                steps.Add(new { cardRef = Ref(card), before, after = Snapshot(), finalPile = card.Pile?.Type.ToString(), training = CardDamageTraining.Current(card),
                    plays = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
                    draws = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card), modelId = e.Card.Id.Entry, fromHandDraw = e.FromHandDraw }).ToArray(),
                    moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemy = e.Monster.Creature.CombatId, move = e.Move.Id }).ToArray(),
                    damage = DamageRows(history.OfType<DamageReceivedEntry>(), owner) });
            }
            object? trigger = null;
            if (variant == "PR-training-dynamic-spells")
            {
                await Play(await Create<Volibear_R06>("unify"));
                await Play(await Create<Volibear_U10>("training"));
                await Play(await Create<Volibear_R07>("thunder-block"));
                await Play(await Create<Volibear_R09>("thunder-absorb"));
                await Play(await Create<Volibear_U05>("attack"), enemies[0]);
            }
            else if (variant == "PR-training-native-domain")
            {
                await Play(await Create<Volibear_R06>("unify"));
                await Play(await Create<Volibear_U10>("training"));
                await Play(await Create<Volibear_C14>("guard"));
                await Play(await Create<Volibear_B03>("attack"), enemies[0]);
            }
            else if (variant == "PR-guard-instances")
            {
                await Play(await Create<Volibear_R06>("unify"));
                await Play(await Create<Volibear_C14>("guard-base"));
                await Play(await Create<Volibear_C14>("guard-upgrade", true));
                var leaf = enemies.Single(e => e.Monster is LeafSlimeS);
                var before = Snapshot(); int boundary = CombatManager.Instance.History.Entries.Count();
                // Native AttackCommand, deliberately not an intent estimate or power callback.
                // FromMonster already selects all native opponents; this strict single-player fixture has only owner.
                await DamageCmd.Attack(3m).FromMonster(leaf.Monster!).Execute(choices);
                trigger = new { operation = "DamageCmd.Attack.FromMonster.Execute", dealer = leaf.CombatId, before, after = Snapshot(),
                    damage = DamageRows(CombatManager.Instance.History.Entries.Skip(boundary).OfType<DamageReceivedEntry>(), owner) };
            }
            else if (variant == "PR-bite-segments")
            {
                // All setup uses actual paid cards. The marked-target replay must
                // amplify each ordinary segment while Domain stays once per play.
                await Play(await Create<Volibear_R06>("unify"));
                await Play(await Create<Volibear_C14>("guard"));
                await Play(await Create<Volibear_U02>("conduction"));
                await Play(await Create<Volibear_U08>("bite-mark"), enemies[0]);
                await Play(await Create<Volibear_U10>("training"));
                await Play(await Create<Volibear_U11>("replay"));
                await Play(await Create<Volibear_U08>("bite-trained"), enemies[0]);
                await Play(await Create<Volibear_U08>("bite-upgrade", true), enemies[0]);
            }
            else
            {
                await Play(await Create<Volibear_U11>("replay"));
                await Play(await Create<Volibear_U08>("bite-first"), enemies[0]);
                await Play(await Create<Volibear_U08>("bite-next"), enemies[0]);
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            GD.Print("[Volibear] PREPARED_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
                token, scenario = "prepared-contract", variant, completed = true,
                gameVersion = release.Version, gameCommit = release.Commit, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "native-action-queue-mechanism-not-mouse", character = player.Character.GetType().Name,
                enemyIds = enemies.Select(e => e.CombatId).ToArray(), enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(), playerId = owner.CombatId,
                cards = Cards.Select(kv => new { cardRef = kv.Value, modelId = kv.Key.Id.Entry, upgraded = kv.Key.IsUpgraded,
                    masterIndex = Array.FindIndex(player.Deck.Cards.ToArray(), c => ReferenceEquals(c, kv.Key.DeckVersion)) }).ToArray(),
                initial, actions, steps, batches, payments = Payments, beforeEffects = BeforeEffects, trigger
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] PREPARED_CONTRACT_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { player = null; CombatManager.Instance.TurnStarted -= Start; Observer.UnpatchAll(Observer.Id); }
    }
    private static object[] DamageRows(IEnumerable<DamageReceivedEntry> history, Creature owner) => history.Select(e => (object)new {
        target = e.Receiver.CombatId, playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage,
        blocked = e.Result.BlockedDamage, props = (int)e.Result.Props, cardRef = Ref(e.CardSource) }).ToArray();
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterEnergySpent))]
    private static class ObservePayment
    {
        private static void Prefix(CardModel card, int amount)
        {
            if (player is not null && ReferenceEquals(card.Owner, player))
                Payments.Add(new { cardRef = Ref(card), amount, energy = player.PlayerCombatState!.Energy });
        }
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.BeforeCardPlayed))]
    private static class ObserveEffects
    {
        private static void Postfix(CardPlay cardPlay, ref Task __result) => __result = Observe(__result, cardPlay);
        private static async Task Observe(Task original, CardPlay play)
        {
            await original;
            if (player is null || !ReferenceEquals(play.Card.Owner, player)) return;
            object? bitePreview = null;
            if (play.Card is Volibear_U08)
            {
                var bite = play.Card.DynamicVars["Bite"];
                bite.UpdateCardPreview(play.Card, CardPreviewMode.Normal, play.Target, runGlobalHooks: true);
                bitePreview = new { type = bite.GetType().Name, amount = bite.PreviewValue };
            }
            BeforeEffects.Add(new { cardRef = Ref(play.Card), index = play.PlayIndex, count = play.PlayCount,
                playId = CardResolutionHooks.CurrentPlayId(play.Card), autoPlay = play.IsAutoPlay,
                energy = player.PlayerCombatState!.Energy, spent = play.Resources.EnergySpent,
                block = player.Creature.Block, pendingTraining = player.Creature.GetPowerAmount<NextAttackTrainingPower>(),
                training = CardDamageTraining.Current(play.Card), replay = player.Creature.GetPowerAmount<NextAttackReplayPower>(), bitePreview });
        }
    }
}
