using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using Godot;
using HarmonyLib;
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
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

internal static class PreparedChoiceProbe
{
    private static bool started;
    private static Player? player;
    private static readonly Harmony Observer = new("Volibear.PreparedChoiceEffectsObserver");
    private static readonly Dictionary<CardModel,string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Payments = [];
    private static readonly List<object> Effects = [];
    private static string? Ref(CardModel? card) => card is null ? null : Cards.TryGetValue(card,out var id) ? id : throw new InvalidOperationException("Unknown choice fixture card");
    private static int Prepared(CardModel card) => CardModifier.Modifiers(card).OfType<PreparedAttackBonus>().Sum(m => m.Amount);
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(Payment)).Patch();
        Observer.CreateClassProcessor(typeof(BeforeEffects)).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state) { if (started) return; started = true; _ = Run(state); }
    private static async Task Frame()
    {
        var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree,SceneTree.SignalName.ProcessFrame);
    }
    private static async Task Until(Func<bool> predicate, string description)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (!predicate()) { if (watch.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException(description); await Frame(); }
    }
    private static IEnumerable<Node> Descendants(Node node)
    {
        yield return node;
        foreach (var child in node.GetChildren()) foreach (var nested in Descendants(child)) yield return nested;
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            string? token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            string? variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PREPARED_CHOICE_CASE");
            if (string.IsNullOrWhiteSpace(token) || variant is not ("PC-C19-fixed-replay" or "PC-C19-dynamic-replay" or "PC-U39-native-search"))
                throw new InvalidOperationException("Missing token or unsupported choice case");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            player = state.Players.Single(); var p = player;
            var pcs = p.PlayerCombatState ?? throw new InvalidOperationException("No combat state");
            var owner = p.Creature;
            var enemies = state.Enemies.ToArray();
            if (state.RoundNumber != 1 || pcs.TurnNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() ||
                p.Relics.Count != 1 || p.Relics[0] is not HuntersHeart || enemies.Length != 3 ||
                enemies.Count(e => e.Monster is LeafSlimeS) != 1 || enemies.Count(e => e.Monster is TwigSlimeS) != 1 ||
                enemies.Count(e => e.Monster is LeafSlimeM or TwigSlimeM) != 1)
                throw new InvalidOperationException("Expected untouched three-slime starter fixture");
            foreach (var card in pcs.AllPiles.SelectMany(pile => pile.Cards).Distinct()) Cards.Add(card,"starter-"+Cards.Count);
            if (Cards.Count != 10) throw new InvalidOperationException("Expected exactly original ten cards");
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Draw);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy,500m);
            await PlayerCmd.SetEnergy(10,p);
            bool search = variant == "PC-U39-native-search", dynamic = variant == "PC-C19-dynamic-replay";
            if (dynamic) await CreatureCmd.GainBlock(owner,10m,ValueProp.Unpowered,null);
            async Task<T> Create<T>(string label, PileType pile = PileType.Hand) where T:CardModel
            {
                var card = state.CreateCard<T>(p); Cards.Add(card,label); await CardPileCmd.Add(card,pile); return card;
            }
            CardModel selected, alternate, source;
            if (search)
            {
                selected = await Create<Volibear_R07>("selected",PileType.Draw);
                alternate = await Create<Volibear_R09>("alternate",PileType.Draw);
                source = await Create<Volibear_U39>("source");
            }
            else
            {
                selected = dynamic ? await Create<Volibear_U05>("selected") : await Create<Volibear_B01>("selected");
                alternate = dynamic ? await Create<Volibear_B01>("alternate") : await Create<Volibear_U05>("alternate");
                await Create<Volibear_B02>("ineligible");
                source = await Create<Volibear_C19>("source");
            }
            object Snapshot() => new { round = state.RoundNumber,turn = pcs.TurnNumber,energy = pcs.Energy,hp = owner.CurrentHp,
                block = owner.Block,enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),
                hand = pcs.Hand.Cards.Select(Ref).ToArray(),draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),
                discard = pcs.DiscardPile.Cards.Select(Ref).ToArray(),play = pcs.PlayPile.Cards.Select(Ref).ToArray(),exhaust = pcs.ExhaustPile.Cards.Select(Ref).ToArray(),
                prepared = Prepared(selected),retain = selected.ShouldRetainThisTurn,
                enhanced = Cards.Keys.Where(c => Prepared(c) != 0 || c.ShouldRetainThisTurn).Select(c => new { cardRef = Ref(c),prepared = Prepared(c),retain = c.ShouldRetainThisTurn }).ToArray(),
                powers = owner.Powers.Select(pow => new { type = pow.GetType().Name,amount = pow.Amount }).ToArray() };
            var initial = Snapshot();
            var played = new List<object>();
            selected.Played += () => played.Add(new { cardRef = Ref(selected),prepared = Prepared(selected),retain = selected.ShouldRetainThisTurn,
                enemyHp = enemies.Select(e => e.CurrentHp).ToArray() });
            using var choices = new NativeControlledChoice(p);
            var steps = new List<object>(); object? choiceEvidence = null;
            async Task Play(CardModel card, bool choose = false, Creature? target = null)
            {
                var before = Snapshot(); int boundary = CombatManager.Instance.History.Entries.Count();
                var action = new PlayCardAction(card,target);
                var events = new List<object>();
                void Event(string name,GameAction a) => events.Add(new { name,state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
                action.BeforeExecuted += a => Event("before-executed",a);
                action.AfterFinished += a => Event("after-finished",a);
                action.BeforeCancelled += a => Event("cancelled",a);
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
                if (choose)
                {
                    Control? Ui() => search ? NOverlayStack.Instance?.Peek() as NCombatPileCardSelectScreen : NPlayerHand.Instance;
                    await Until(() => choices.Requests.Count == 1 && choices.Requests[0].ChoiceId is not null && Ui() is { } ui &&
                        Descendants(ui).OfType<NCardHolder>().Any(h => h.IsVisibleInTree() && ReferenceEquals(h.CardNode?.Model,selected)),"Native choice UI not ready");
                    var request = choices.Requests.Single(); request.RequireWaiting();
                    if (!ReferenceEquals(request.Action,action)) throw new InvalidOperationException("Choice belongs to a different native action");
                    var ui = Ui() ?? throw new InvalidOperationException("Native UI disappeared");
                    var holders = Descendants(ui).OfType<NCardHolder>().ToArray();
                    var visible = holders.Where(h => h.IsVisibleInTree() && request.Available.Any(c => ReferenceEquals(c,h.CardNode?.Model)))
                        .Select(h => Ref(h.CardNode!.Model)).ToArray();
                    var excluded = request.Available.Where(c => !request.Filter(c)).Select(c => new { cardRef = Ref(c),
                        filterAccepted = request.Filter(c),holderCount = holders.Count(h => ReferenceEquals(h.CardNode?.Model,c)),
                        visibleHolderCount = holders.Count(h => h.IsVisibleInTree() && ReferenceEquals(h.CardNode?.Model,c)) }).ToArray();
                    var requested = request.Describe();
                    GD.Print("[Volibear] PREPARED_CHOICE_PENDING " + JsonSerializer.Serialize(new { token,variant,request = requested,visible,excluded }));
                    var beforeWrongId = Snapshot();
                    int historyBefore = CombatManager.Instance.History.Entries.Count(), paymentsBefore = Payments.Count, effectsBefore = Effects.Count, playedBefore = played.Count;
                    var rejected = NativeControlledChoice.ProbeFutureIdRejection(request); var afterWrongId = Snapshot();
                    var wrongBoundary = new { historyBefore,historyAfter = CombatManager.Instance.History.Entries.Count(),
                        paymentsBefore,paymentsAfter = Payments.Count,effectsBefore,effectsAfter = Effects.Count,playedBefore,playedAfter = played.Count };
                    var chosenHolder = holders.Single(h => h.IsVisibleInTree() && ReferenceEquals(h.CardNode?.Model,selected));
                    await NativeControlledChoice.SelectVisibleCandidate(request,chosenHolder);
                    if (!search)
                    {
                        var confirm = ui.GetNode<NClickableControl>("%SelectModeConfirmButton");
                        await Until(() => confirm.IsEnabled,"Native hand confirmation did not enable");
                        await NativeControlledChoice.ConfirmIfRequired(request,confirm);
                    }
                    await Until(() => request.Synced.Count == 1,"Native choice never synchronized");
                    choiceEvidence = new { request = requested,uiType = ui.GetType().Name,visible,excluded,
                        exclusionClaim = "native-filter-and-ui-exclusion-not-illegal-card-submit",beforeWrongId,rejected,afterWrongId,wrongBoundary,
                        inputs = request.Inputs.ToArray(),sync = request.Synced.ToArray() };
                }
                await Until(() => action.CompletionTask.IsCompleted,"Native paid card action did not complete");
                await action.CompletionTask;
                if (action.Exception is not null) throw new InvalidOperationException("Native queued action failed",action.Exception);
                var history = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
                steps.Add(new { cardRef = Ref(card),before,after = Snapshot(),
                    action = new { id = action.Id,state = action.State.ToString(),target = action.TargetId,type = action.GetType().Name,
                        context = action.PlayerChoiceContext?.GetType().Name,actionType = action.ActionType.ToString(),
                        sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(),card),events },
                    plays = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card),index = e.CardPlay.PlayIndex,count = e.CardPlay.PlayCount }).ToArray(),
                    draws = history.OfType<CardDrawnEntry>().Select(e => Ref(e.Card)).ToArray(),
                    moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => e.Move.Id).ToArray(),
                    damage = history.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,cardRef = Ref(e.CardSource),
                        hpLost = e.Result.UnblockedDamage,blocked = e.Result.BlockedDamage,props = (int)e.Result.Props }).ToArray() });
            }
            await Play(source,true);
            object? returned = null;
            if (!search)
            {
                await Play(await Create<Volibear_U11>("replay"));
                await Play(selected,false,enemies[0]);
                var before = Snapshot(); await CardPileCmd.Add(selected,PileType.Hand);
                returned = new { operation = "CardPileCmd.Add-same-instance-fixture-return",before,after = Snapshot(),cardRef = Ref(selected) };
                await Play(selected,false,enemies[0]);
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            GD.Print("[Volibear] PREPARED_CHOICE_RESULT " + JsonSerializer.Serialize(new {
                token,variant,scenario = "prepared-choice",completed = true,gameVersion = release.Version,gameCommit = release.Commit,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,acceptance = "controlled-native-viewport-action-not-OS-input",
                character = p.Character.GetType().Name,playerId = owner.CombatId,enemyIds = enemies.Select(e => e.CombatId).ToArray(),
                enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                cards = Cards.Select(kv => new { cardRef = kv.Value,modelId = kv.Key.Id.Entry,
                    combatCardIndex = NetCombatCard.FromModel(kv.Key).CombatCardIndex,sameObject = ReferenceEquals(NetCombatCard.FromModel(kv.Key).ToCardModel(),kv.Key),
                    ownerId = kv.Key.Owner.Creature.CombatId,masterIndex = Array.FindIndex(p.Deck.Cards.ToArray(),c => ReferenceEquals(c,kv.Key.DeckVersion)),
                    masterModelId = kv.Key.DeckVersion?.Id.Entry,upgraded = kv.Key.IsUpgraded }).ToArray(),
                initial,choice = choiceEvidence,steps,returned,played,payments = Payments,beforeEffects = Effects,requestCount = choices.Requests.Count }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] PREPARED_CHOICE_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { player = null; CombatManager.Instance.TurnStarted -= Start; Observer.UnpatchAll(Observer.Id); }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterEnergySpent))]
    private static class Payment
    {
        private static void Prefix(CardModel card,int amount)
        {
            if (player is not null && ReferenceEquals(card.Owner,player)) Payments.Add(new { cardRef = Ref(card),amount,energy = player.PlayerCombatState!.Energy });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.BeforeCardPlayed))]
    private static class BeforeEffects
    {
        private static void Postfix(CardPlay cardPlay,ref Task __result) => __result = Observe(__result,cardPlay);
        private static async Task Observe(Task original,CardPlay play)
        {
            await original;
            if (player is null || !ReferenceEquals(play.Card.Owner,player)) return;
            Effects.Add(new { cardRef = Ref(play.Card),index = play.PlayIndex,count = play.PlayCount,playId = CardResolutionHooks.CurrentPlayId(play.Card),
                autoPlay = play.IsAutoPlay,energy = player.PlayerCombatState!.Energy,spent = play.Resources.EnergySpent,
                prepared = Prepared(play.Card),retain = play.Card.ShouldRetainThisTurn,replay = player.Creature.GetPowerAmount<NextAttackReplayPower>() });
        }
    }
}
