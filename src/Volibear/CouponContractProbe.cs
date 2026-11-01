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
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

internal static class CouponContractProbe
{
    private static bool started;
    private static Player? player;
    private static readonly Harmony Observer = new("Volibear.CouponContractObserver");
    private static readonly Dictionary<CardModel,string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Payments = [],Effects = [];
    private static Action<CardModel,Player?>? Generated;
    private static string? Ref(CardModel? card) => card is null ? null : Cards.TryGetValue(card,out var id) ? id : throw new InvalidOperationException("Unknown coupon fixture card");
    private static object Coupons() => new { attack = player!.Creature.GetPowerAmount<NextAttackDiscount>(),engage = player.Creature.GetPowerAmount<NextEngageDiscount>() };
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(Payment)).Patch(); Observer.CreateClassProcessor(typeof(Effect)).Patch();
        Observer.CreateClassProcessor(typeof(Generation)).Patch(); CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state) { if (started) return; started = true; _ = Run(state); }
    private static async Task Until(Func<bool> done,string label)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (!done())
        {
            if (watch.Elapsed > TimeSpan.FromSeconds(40)) throw new TimeoutException(label);
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree,SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_COUPON_CASE");
            var eligible = new[] { "B04","C04","C10","C11","U28","U35","R09" };
            bool matrix = variant is not null && variant.StartsWith("CP-elig-") && eligible.Contains(variant[8..]);
            if (string.IsNullOrWhiteSpace(token) || !matrix && variant is not ("CP-max-preserve" or "CP-zero-consume" or "CP-expiry" or "CP-beast-attack" or "CP-beast-skill"))
                throw new InvalidOperationException("Unsupported coupon case or missing token");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            player = state.Players.Single(); var p = player; var owner = p.Creature;
            var pcs = p.PlayerCombatState ?? throw new InvalidOperationException("No combat state");
            var enemies = state.Enemies.ToArray(); var leaf = enemies.Single(e => e.Monster is LeafSlimeS);
            if (state.RoundNumber != 1 || pcs.TurnNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() ||
                p.Relics.Count != 1 || p.Relics[0] is not HuntersHeart || enemies.Length != 3 ||
                enemies.Count(e => e.Monster is TwigSlimeS) != 1 || enemies.Count(e => e.Monster is LeafSlimeM or TwigSlimeM) != 1)
                throw new InvalidOperationException("Expected untouched native three-slime fixture");
            foreach (var card in pcs.AllPiles.SelectMany(pile => pile.Cards).Distinct()) Cards.Add(card,"starter-"+Cards.Count);
            if (Cards.Count != 10) throw new InvalidOperationException("Expected original ten cards");
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Draw);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy,500m);
            await PlayerCmd.SetEnergy(30,p);
            string? generationWindow = null;
            var generated = new List<object>();
            var conversions = new List<object>();
            CardModel? conversionMaterial = null, convertedCard = null;
            int mediumStatusCount = enemies.Any(e => e.Monster is LeafSlimeM) ? 2 : 1;
            Generated = (card,creator) =>
            {
                if (generationWindow == "beast-conversion")
                {
                    var material = conversionMaterial ?? throw new InvalidOperationException("Missing explicit conversion material");
                    bool exhausted = CombatManager.Instance.History.Entries.OfType<CardExhaustedEntry>().Any(e => ReferenceEquals(e.Card,material));
                    if (convertedCard is not null || !exhausted || material.Pile?.Type != PileType.Exhaust ||
                        !ReferenceEquals(card.Owner,p) || !ReferenceEquals(creator,p) || card.DeckVersion is not null ||
                        card.Pile?.Type != PileType.Hand || ReferenceEquals(card,material) ||
                        (variant == "CP-beast-attack" ? card is not Volibear_T01 : card is not Volibear_T02))
                        throw new InvalidOperationException("Native beast generation/exhaust provenance mismatch");
                    Cards.Add(card,"target-beast");convertedCard = card;
                    conversions.Add(new { materialRef = Ref(material),cardRef = Ref(card),sameObject = ReferenceEquals(material,card),
                        materialIndex = NetCombatCard.FromModel(material).CombatCardIndex,cardIndex = NetCombatCard.FromModel(card).CombatCardIndex,
                        materialExhausted = exhausted,originalPile = "Hand",generatedPile = card.Pile.Type.ToString() });
                    return;
                }
                var monster = state.Enemies.Select(e => e.Monster).SingleOrDefault(m => m is { IsPerformingMove:true });
                string? move = monster?.NextMove.Id;
                bool sticky = monster is TwigSlimeM && move == "STICKY_SHOT_MOVE" || monster is LeafSlimeM && move == "STICKY_SHOT";
                bool window = generationWindow == "R09" && state.CurrentSide == CombatSide.Player || generationWindow == "end-turn" && state.CurrentSide == CombatSide.Enemy;
                bool expiryGoop = variant == "CP-expiry" && generationWindow == "expiry-engage" && state.RoundNumber == 2 && pcs.TurnNumber == 2 &&
                    state.CurrentSide == CombatSide.Player && monster is LeafSlimeS && move == "GOOP_MOVE" && generated.Count == mediumStatusCount;
                if (!(window && sticky || expiryGoop) || card is not Slimed || !ReferenceEquals(card.Owner,p) || card.DeckVersion is not null || creator is not null ||
                    card.Pile?.Type != PileType.Discard || Cards.ContainsKey(card)) throw new InvalidOperationException("Unexpected native generated card provenance");
                Cards.Add(card,"generated-"+generated.Count);
                var net = NetCombatCard.FromModel(card);
                generated.Add(new { cardRef = Ref(card),modelId = card.Id.Entry,type = card.GetType().Name,cardType = card.Type.ToString(),
                    combatCardIndex = net.CombatCardIndex,sameObject = ReferenceEquals(net.ToCardModel(),card),ownerId = card.Owner.Creature.CombatId,
                    masterModelId = card.DeckVersion?.Id.Entry,creatorId = creator?.Creature.CombatId,pile = card.Pile.Type.ToString(),
                    sourceEnemy = monster!.Creature.CombatId,sourceType = monster.GetType().Name,sourceMove = move,
                    round = state.RoundNumber,turn = pcs.TurnNumber,side = state.CurrentSide.ToString(),window = generationWindow });
            };
            object Snapshot() => new { round = state.RoundNumber,turn = pcs.TurnNumber,side = state.CurrentSide.ToString(),energy = pcs.Energy,
                hp = owner.CurrentHp,block = owner.Block,enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),
                powers = owner.Powers.ToDictionary(pow => pow.GetType().Name,pow => pow.Amount),
                hand = pcs.Hand.Cards.Select(Ref).ToArray(),draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),discard = pcs.DiscardPile.Cards.Select(Ref).ToArray(),
                play = pcs.PlayPile.Cards.Select(Ref).ToArray(),exhaust = pcs.ExhaustPile.Cards.Select(Ref).ToArray(),
                forms = Cards.Keys.Where(c => BeastForms.Shape(c) != BeastShape.None).Select(c => new { cardRef = Ref(c),shape = BeastForms.Shape(c).ToString(),type = c.Type.ToString() }).ToArray() };
            var initial = Snapshot();
            async Task<CardModel> Create(string code,string label,bool upgraded = false)
            {
                CardModel card = code switch {
                    "C25" => state.CreateCard<Volibear_C25>(p),"U14" => state.CreateCard<Volibear_U14>(p),"B02" => state.CreateCard<Volibear_B02>(p),
                    "B04" => state.CreateCard<Volibear_B04>(p),"C04" => state.CreateCard<Volibear_C04>(p),"C10" => state.CreateCard<Volibear_C10>(p),
                    "C11" => state.CreateCard<Volibear_C11>(p),"U28" => state.CreateCard<Volibear_U28>(p),"U35" => state.CreateCard<Volibear_U35>(p),
                    "R09" => state.CreateCard<Volibear_R09>(p),"C01" => state.CreateCard<Volibear_C01>(p),"R29" => state.CreateCard<Volibear_R29>(p),
                    _ => throw new InvalidOperationException("Unknown fixture source") };
                Cards.Add(card,label); if (upgraded) CardCmd.Upgrade(card); await CardPileCmd.Add(card,PileType.Hand); return card;
            }
            object History(int boundary)
            {
                var entries = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
                return new { plays = entries.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card),index = e.CardPlay.PlayIndex,count = e.CardPlay.PlayCount }).ToArray(),
                    draws = entries.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card),fromHandDraw = e.FromHandDraw }).ToArray(),
                    moves = entries.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemy = e.Monster.Creature.CombatId,move = e.Move.Id }).ToArray(),
                    damage = entries.OfType<DamageReceivedEntry>().Select(e => new { target = e.Receiver.CombatId,cardRef = Ref(e.CardSource),hpLost = e.Result.UnblockedDamage,
                        blocked = e.Result.BlockedDamage,props = (int)e.Result.Props }).ToArray(),
                    generated = entries.OfType<CardGeneratedEntry>().Select(e => new { cardRef = Ref(e.Card),creatorId = e.Creator?.Creature.CombatId }).ToArray() };
            }
            var steps = new List<object>();
            async Task Play(CardModel card,string label,Creature? target = null)
            {
                var before = Snapshot(); var cardType = card.Type.ToString(); var shape = BeastForms.Shape(card).ToString();
                int boundary = CombatManager.Instance.History.Entries.Count(),paid = Payments.Count,effects = Effects.Count;
                var action = new PlayCardAction(card,target); var events = new List<object>();
                void Event(string name,GameAction current) => events.Add(new { name,state = current.State.ToString(),id = current.Id,energy = pcs.Energy });
                action.BeforeExecuted += a => Event("before-executed",a); action.BeforeCancelled += a => Event("cancelled",a); action.AfterFinished += a => Event("after-finished",a);
                generationWindow = card is Volibear_R29 && conversionMaterial is not null ? "beast-conversion" :
                    card is Volibear_R09 && BeastForms.Shape(card) == BeastShape.None ? "R09" :
                    variant == "CP-expiry" && label == "target" && card is Volibear_C10 && BeastForms.Shape(card) == BeastShape.None ? "expiry-engage" : null;
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
                await Until(() => action.CompletionTask.IsCompleted,"Native coupon action did not finish: "+label);
                await action.CompletionTask; generationWindow = null;
                if (action.Exception is not null) throw new InvalidOperationException("Native coupon action failed",action.Exception);
                steps.Add(new { label,cardRef = Ref(card),cardType,shape,before,after = Snapshot(),
                    action = new { id = action.Id,state = action.State.ToString(),type = action.GetType().Name,actionType = action.ActionType.ToString(),
                        context = action.PlayerChoiceContext?.GetType().Name,target = action.TargetId,sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(),card),events },
                    payments = Payments.Skip(paid).ToArray(),effects = Effects.Skip(effects).ToArray(),history = History(boundary) });
            }
            await Play(await Create("C25","attack-coupon"),"attack-coupon");
            if (variant == "CP-max-preserve") await Play(await Create("C25","attack-coupon-upgrade",true),"attack-coupon-upgrade");
            await Play(await Create("U14","engage-coupon"),"engage-coupon");
            object? transition = null;
            if (matrix)
            {
                string code = variant![8..]; await Play(await Create(code,"target"),"target",code == "R09" ? null : leaf);
            }
            else if (variant == "CP-max-preserve")
            {
                await Play(await Create("U14","engage-coupon-upgrade",true),"engage-coupon-upgrade");
                await Play(await Create("B02","noneligible"),"noneligible");
                var target = await Create("C10","target");
                await Play(target,"invalid-target",owner); await Play(target,"target",leaf);
            }
            else if (variant == "CP-zero-consume")
            {
                await Play(await Create("C01","zero-attack"),"zero-attack",leaf);
                await Play(await Create("B04","target"),"target",leaf);
            }
            else if (variant == "CP-expiry")
            {
                var before = Snapshot(); int boundary = CombatManager.Instance.History.Entries.Count(); generationWindow = "end-turn";
                PlayerCmd.EndTurn(p,canBackOut:false);
                await Until(() => state.RoundNumber == 2 && state.CurrentSide == CombatSide.Player && pcs.Phase == PlayerTurnPhase.Play,"Native next turn did not begin");
                generationWindow = null; transition = new { before,after = Snapshot(),history = History(boundary) };
                await Play(await Create("C10","target"),"target",leaf);
            }
            else
            {
                conversionMaterial = await Create(variant == "CP-beast-attack" ? "C10" : "U28","target");
                await Play(await Create("R29","convert"),"convert");
                var replacement = convertedCard ?? throw new InvalidOperationException("Queued R29 did not generate the native beast token");
                await Play(replacement,"target",variant == "CP-beast-attack" ? leaf : null);
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            GD.Print("[Volibear] COUPON_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
                token,variant,scenario = "coupon-contract",completed = true,gameVersion = release.Version,gameCommit = release.Commit,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,acceptance = "native-action-queue-payment-not-OS-input",
                character = p.Character.GetType().Name,playerId = owner.CombatId,enemyIds = enemies.Select(e => e.CombatId).ToArray(),enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                fixture = "fresh-native-three-slimes-energy30-enemyHp500-created-cards-explicit",
                cards = Cards.Where(kv => !kv.Value.StartsWith("generated-")).Select(kv => new { cardRef = kv.Value,modelId = kv.Key.Id.Entry,upgraded = kv.Key.IsUpgraded,
                    combatCardIndex = NetCombatCard.FromModel(kv.Key).CombatCardIndex,sameObject = ReferenceEquals(NetCombatCard.FromModel(kv.Key).ToCardModel(),kv.Key),
                    ownerId = kv.Key.Owner.Creature.CombatId,masterIndex = Array.FindIndex(p.Deck.Cards.ToArray(),c => ReferenceEquals(c,kv.Key.DeckVersion)),masterModelId = kv.Key.DeckVersion?.Id.Entry }).ToArray(),
                generated,conversions,initial,steps,transition }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] COUPON_CONTRACT_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { Generated = null; player = null; CombatManager.Instance.TurnStarted -= Start; Observer.UnpatchAll(Observer.Id); }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterCardGeneratedForCombat))]
    private static class Generation { private static void Prefix(CardModel card,Player? creator) => Generated?.Invoke(card,creator); }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterEnergySpent))]
    private static class Payment
    {
        private static void Prefix(CardModel card,int amount)
        {
            if (player is not null && ReferenceEquals(card.Owner,player)) Payments.Add(new { cardRef = Ref(card),amount,energy = player.PlayerCombatState!.Energy,coupons = Coupons() });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.BeforeCardPlayed))]
    private static class Effect
    {
        private static void Postfix(CardPlay cardPlay,ref Task __result) => __result = Observe(__result,cardPlay);
        private static async Task Observe(Task original,CardPlay play)
        {
            await original;
            if (player is null || !ReferenceEquals(play.Card.Owner,player)) return;
            Effects.Add(new { cardRef = Ref(play.Card),index = play.PlayIndex,count = play.PlayCount,autoPlay = play.IsAutoPlay,
                playId = CardResolutionHooks.CurrentPlayId(play.Card),spent = play.Resources.EnergySpent,energy = player.PlayerCombatState!.Energy,
                cardType = play.Card.Type.ToString(),shape = BeastForms.Shape(play.Card).ToString(),coupons = Coupons() });
        }
    }
}
