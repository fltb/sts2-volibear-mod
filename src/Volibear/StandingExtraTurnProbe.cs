using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
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
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

internal static class StandingExtraTurnProbe
{
    private static bool started;
    private static Player? owner;
    private static CombatState? combat;
    private static readonly Harmony Observer = new("Volibear.StandingExtraTurnObserver");
    private static readonly Dictionary<CardModel,string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Payments = [],Effects = [],Boundaries = [],ExtraTurns = [],AutoPhases = [];
    private static PowerModel? standingInstance;
    private static readonly List<object> BlockGains = [],ClearPreventers = [];
    private static bool? StandingSame()
    {
        var current = owner?.Creature.GetPower<StandingPower>();
        if (current is null) return standingInstance is null ? null : false;
        return ReferenceEquals(standingInstance,current);
    }
    private static readonly List<object> BlockTrace = [],PowerLifecycle = [];
    private static readonly Dictionary<PowerModel,string> PowerRefs = new(ReferenceEqualityComparer.Instance);
    private static readonly Dictionary<PowerModel,int> PowerEpochs = new(ReferenceEqualityComparer.Instance);
    private static readonly HashSet<PowerModel> Applying = new(ReferenceEqualityComparer.Instance);
    private static void ObservePowerAdded(PowerModel power)
    {
        if (power is not StandingPower) return;
        if (!PowerRefs.ContainsKey(power)) PowerRefs.Add(power,"standing-power-"+(PowerRefs.Count+1));
        if (!Applying.Contains(power)) PowerEpochs[power] = ++nextEpoch;
        TracePower("collection-added",power);
    }
    private static void ObservePowerRemoved(PowerModel power)
    { if (power is StandingPower && PowerRefs.ContainsKey(power)) TracePower("collection-removed",power); }
    private static int nextEpoch,nextClear;
    private static int? activeClear;
    private static bool IsOwner(Creature creature) => owner is not null && ReferenceEquals(creature,owner.Creature);
    private static void TraceBlock(string kind,int before,int after,int? clearId) => BlockTrace.Add(new {
        sequence = BlockTrace.Count+1,kind,clearId,before,after,ownerId = owner!.Creature.CombatId,combatSame = ReferenceEquals(owner.Creature.CombatState,combat),
        round = combat!.RoundNumber,turn = owner.PlayerCombatState!.TurnNumber,side = combat.CurrentSide.ToString() });
    private static void ObserveBlockChanged(int before,int after) => TraceBlock("block-changed",before,after,activeClear);
    private static void TracePower(string kind,PowerModel power,Creature? target = null,int? before = null,decimal? requested = null,CardModel? source = null,Creature? applier = null)
    {
        var creature = target ?? power.Owner;
        PowerLifecycle.Add(new { sequence = PowerLifecycle.Count+1,kind,powerRef = PowerRefs[power],epoch = PowerEpochs[power],type = power.GetType().Name,
            ownerId = creature.CombatId,ownerSame = IsOwner(creature),combatSame = ReferenceEquals(creature.CombatState,combat),round = combat!.RoundNumber,turn = owner!.PlayerCombatState!.TurnNumber,
            side = combat.CurrentSide.ToString(),amount = power.Amount,before,requested,sourceCard = Ref(source),sourceOwnerId = source?.Owner.Creature.CombatId,
            sourceSame = source is null ? (bool?)null : Cards.Any(kv => kv.Value == "standing" && ReferenceEquals(kv.Key,source)),
            sourceUpgraded = source?.IsUpgraded,sourceOwnerSame = source is null ? (bool?)null : ReferenceEquals(source.Owner,owner),
            applierId = applier?.CombatId,applierSame = applier is null ? (bool?)null : IsOwner(applier) });
    }
    [HarmonyPatch(typeof(Creature),"Block",MethodType.Setter)]
    private static class BlockWrite
    {
        private static void Prefix(Creature __instance,int value)
        { if (IsOwner(__instance)) TraceBlock("block-write",__instance.Block,value,activeClear); }
    }
    [HarmonyPatch(typeof(Creature),"ClearBlock")]
    private static class ClearScope
    {
        private static void Prefix(Creature __instance,out (int Id,int Block)? __state)
        {
            __state = null;if (!IsOwner(__instance)) return;
            activeClear = ++nextClear;__state = (nextClear,__instance.Block);
            TraceBlock("clear-enter",__instance.Block,__instance.Block,activeClear);
        }
        private static void Postfix(Creature __instance,(int Id,int Block)? __state,ref Task __result) => __result = Observe(__result,__instance,__state);
        private static async Task Observe(Task task,Creature creature,(int Id,int Block)? data)
        {
            await task;if (data is null) return;
            TraceBlock("clear-complete",data.Value.Block,creature.Block,data.Value.Id);activeClear = null;
        }
    }
    [HarmonyPatch(typeof(PowerModel),nameof(PowerModel.ApplyInternal))]
    private static class PowerApply
    {
        private static void Prefix(PowerModel __instance,Creature owner,decimal amount,out bool __state)
        {
            __state = __instance is StandingPower && IsOwner(owner);if (!__state) return;
            if (!PowerRefs.ContainsKey(__instance)) PowerRefs.Add(__instance,"standing-power-"+(PowerRefs.Count+1));
            PowerEpochs[__instance] = ++nextEpoch;Applying.Add(__instance);standingInstance ??= __instance;
            TracePower("apply-enter",__instance,owner,requested:amount);
        }
        private static void Postfix(PowerModel __instance,bool __state)
        { if (__state) { TracePower("apply-complete",__instance);Applying.Remove(__instance); } }
    }
    [HarmonyPatch(typeof(PowerModel),nameof(PowerModel.SetAmount))]
    private static class PowerAmount
    {
        private static void Prefix(PowerModel __instance,out int? __state) => __state = PowerRefs.ContainsKey(__instance) ? __instance.Amount : null;
        private static void Postfix(PowerModel __instance,int? __state)
        { if (__state is not null) TracePower("amount-write",__instance,before:__state); }
    }
    [HarmonyPatch(typeof(PowerModel),nameof(PowerModel.RemoveInternal))]
    private static class PowerRemove
    {
        private static void Prefix(PowerModel __instance,out bool __state)
        { __state = PowerRefs.ContainsKey(__instance);if (__state) TracePower("remove-enter",__instance); }
        private static void Postfix(PowerModel __instance,bool __state)
        { if (__state) TracePower("remove-complete",__instance); }
    }
    [HarmonyPatch(typeof(StandingPower),nameof(StandingPower.AfterApplied))]
    private static class StandingApplied
    {
        private static void Prefix(StandingPower __instance,Creature? applier,CardModel? cardSource)
        { if (PowerRefs.ContainsKey(__instance)) TracePower("after-applied-enter",__instance,source:cardSource,applier:applier); }
        private static void Postfix(StandingPower __instance,Creature? applier,CardModel? cardSource,ref Task __result) => __result = Observe(__result,__instance,applier,cardSource);
        private static async Task Observe(Task task,StandingPower power,Creature? applier,CardModel? source)
        { await task;if (PowerRefs.ContainsKey(power)) TracePower("after-applied-complete",power,source:source,applier:applier); }
    }
    private static Func<object>? Snapshot;
    private static Func<int,object>? History;
    private static Action<CardModel,Player?>? Generated;
    private static string? Ref(CardModel? card) => card is null ? null : Cards.TryGetValue(card,out var id) ? id : throw new InvalidOperationException("Unregistered standing card");
    private static bool? EyeUsed()
    {
        var eye = owner?.Relics.OfType<PaelsEye>().SingleOrDefault();
        return eye is null ? null : (bool)AccessTools.Property(typeof(PaelsEye),"UsedThisCombat").GetValue(eye)!;
    }
    private static object Window() => new { round = combat!.RoundNumber,turn = owner!.PlayerCombatState!.TurnNumber,side = combat.CurrentSide.ToString(),
        block = owner.Creature.Block,standing = owner.Creature.GetPowerAmount<StandingPower>(),standingSame = StandingSame(),eyeUsed = EyeUsed() };
    public static void Install()
    {
        foreach (var type in new[] { typeof(Payment),typeof(Effect),typeof(Generation),typeof(TurnEnd),typeof(ExtraTurn),typeof(MayhemPhase),typeof(BlockGain),typeof(ClearPreventer),typeof(ClearScope),typeof(BlockWrite),typeof(PowerApply),typeof(PowerAmount),typeof(PowerRemove),typeof(StandingApplied) }) Observer.CreateClassProcessor(type).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state) { if (started) return; started = true; _ = Run(state); }
    private static async Task Until(Func<bool> done,string label)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (!done())
        {
            if (watch.Elapsed > TimeSpan.FromSeconds(60)) throw new TimeoutException(label);
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree,SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_STANDING_EXTRA_TURN_CASE");
            if (string.IsNullOrWhiteSpace(token) || variant is not ("U03-base-extra-turn" or "U03-upgraded-extra-turn")) throw new InvalidOperationException("Unsupported standing case or missing token");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            owner = state.Players.Single(); combat = state; var p = owner; var creature = p.Creature;
            creature.BlockChanged += ObserveBlockChanged;
            creature.PowerApplied += ObservePowerAdded;creature.PowerRemoved += ObservePowerRemoved;
            var pcs = p.PlayerCombatState ?? throw new InvalidOperationException("No combat state");
            var enemies = state.Enemies.ToArray(); var leaf = enemies.Single(e => e.Monster is LeafSlimeS);
            if (state.RoundNumber != 1 || pcs.TurnNumber != 1 || creature.CurrentHp != 80 || creature.Block != 0 || creature.Powers.Any() ||
                p.Relics.Count != 1 || p.Relics[0] is not HuntersHeart || enemies.Length != 3 ||
                enemies.Count(e => e.Monster is TwigSlimeS) != 1 || enemies.Count(e => e.Monster is LeafSlimeM or TwigSlimeM) != 1)
                throw new InvalidOperationException("Expected untouched native three-slime fixture");
            foreach (var card in pcs.AllPiles.SelectMany(pile => pile.Cards).Distinct()) Cards.Add(card,"starter-"+Cards.Count);
            if (Cards.Count != 10) throw new InvalidOperationException("Expected original ten cards");
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Draw);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy,500m);
            await PlayerCmd.SetEnergy(30,p);
            await RelicCmd.Obtain<PaelsEye>(p);
            var generated = new List<object>();
            string? activeTransition = null;
            int mediumStatusCount = enemies.Any(e => e.Monster is LeafSlimeM) ? 2 : 1;
            Generated = (card,creator) =>
            {
                var monster = state.Enemies.Select(e => e.Monster).SingleOrDefault(m => m is { IsPerformingMove:true });
                string? move = monster?.NextMove.Id;
                bool sticky = monster is TwigSlimeM && move == "STICKY_SHOT_MOVE" || monster is LeafSlimeM && move == "STICKY_SHOT";
                bool firstEnemySticky = activeTransition == "natural-enemy-before-standing" && state.RoundNumber == 1 && pcs.TurnNumber == 1 && sticky && generated.Count < mediumStatusCount;
                bool secondEnemyGoop = activeTransition == "natural-enemy-after-extra" && state.RoundNumber == 2 && pcs.TurnNumber == 3 &&
                    monster is LeafSlimeS && move == "GOOP_MOVE" && generated.Count == mediumStatusCount;
                if (state.CurrentSide != CombatSide.Enemy || !(firstEnemySticky || secondEnemyGoop) ||
                    card is not Slimed || !ReferenceEquals(card.Owner,p) || card.DeckVersion is not null || creator is not null || card.Pile?.Type != PileType.Discard || Cards.ContainsKey(card))
                {
                    GD.Print("[Volibear] STANDING_EXTRA_TURN_GENERATION_DIAGNOSTIC " + JsonSerializer.Serialize(new { token,activeTransition,round = state.RoundNumber,turn = pcs.TurnNumber,
                        side = state.CurrentSide.ToString(),model = card.Id.Entry,ownerId = card.Owner?.Creature.CombatId,master = card.DeckVersion?.Id.Entry,
                        creatorId = creator?.Creature.CombatId,pile = card.Pile?.Type.ToString(),registeredCount = generated.Count,
                        actors = enemies.Select(e => new { id = e.CombatId,type = e.Monster!.GetType().Name,move = e.Monster.NextMove.Id,performing = e.Monster.IsPerformingMove }).ToArray() }));
                    throw new InvalidOperationException("Unexpected native generated card provenance");
                }
                Cards.Add(card,"generated-"+generated.Count); var net = NetCombatCard.FromModel(card);
                generated.Add(new { cardRef = Ref(card),modelId = card.Id.Entry,type = card.GetType().Name,cardType = card.Type.ToString(),combatCardIndex = net.CombatCardIndex,
                    sameObject = ReferenceEquals(net.ToCardModel(),card),ownerId = card.Owner.Creature.CombatId,masterModelId = card.DeckVersion?.Id.Entry,creatorId = creator?.Creature.CombatId,
                    pile = card.Pile.Type.ToString(),sourceEnemy = monster!.Creature.CombatId,sourceType = monster.GetType().Name,sourceMove = move,
                    round = state.RoundNumber,turn = pcs.TurnNumber,side = state.CurrentSide.ToString() });
            };
            Snapshot = () => new { round = state.RoundNumber,turn = pcs.TurnNumber,side = state.CurrentSide.ToString(),phase = pcs.Phase.ToString(),energy = pcs.Energy,
                hp = creature.CurrentHp,block = creature.Block,enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),powers = creature.Powers.ToDictionary(pow => pow.GetType().Name,pow => pow.Amount),
                relics = p.Relics.Select(relic => relic.GetType().Name).ToArray(),eyeUsed = EyeUsed(),standingSame = StandingSame(),
                hand = pcs.Hand.Cards.Select(Ref).ToArray(),draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),discard = pcs.DiscardPile.Cards.Select(Ref).ToArray(),
                play = pcs.PlayPile.Cards.Select(Ref).ToArray(),exhaust = pcs.ExhaustPile.Cards.Select(Ref).ToArray(),removed = Cards.Keys.Where(c => c.HasBeenRemovedFromState).Select(Ref).ToArray() };
            int EntryRound(CombatHistoryEntry e) => (int)AccessTools.Property(typeof(CombatHistoryEntry),"RoundNumber").GetValue(e)!;
            string EntrySide(CombatHistoryEntry e) => AccessTools.Property(typeof(CombatHistoryEntry),"CurrentSide").GetValue(e)!.ToString()!;
            int EntryTurn(CombatHistoryEntry e) => ((Dictionary<ulong,int>)AccessTools.Field(typeof(CombatHistoryEntry),"_playerTurnNumbers").GetValue(e)!)[p.NetId];
            bool EntryCombat(CombatHistoryEntry e) => ReferenceEquals(e.History,CombatManager.Instance.History) && ReferenceEquals(e.Actor.CombatState,state);
            object DamageRow(DamageReceivedEntry e) => new { target = e.Receiver.CombatId,cardRef = Ref(e.CardSource),hpLost = e.Result.UnblockedDamage,
                blocked = e.Result.BlockedDamage,props = (int)e.Result.Props,dealer = e.Dealer?.CombatId,
                combatSame = EntryCombat(e) && ReferenceEquals(e.Dealer?.CombatState,state),round = EntryRound(e),turn = EntryTurn(e),side = EntrySide(e) };
            object? OrderedRow(CombatHistoryEntry e) => e switch {
                DamageReceivedEntry d => new { kind = "damage",data = DamageRow(d) },
                MonsterPerformedMoveEntry m => new { kind = "move",data = (object)new { enemy = m.Monster.Creature.CombatId,move = m.Move.Id,
                    combatSame = EntryCombat(m),round = EntryRound(m),turn = EntryTurn(m),side = EntrySide(m) } },
                CardGeneratedEntry g => new { kind = "generated",data = (object)new { cardRef = Ref(g.Card),creatorId = g.Creator?.Creature.CombatId,
                    ownerId = g.Card.Owner.Creature.CombatId,combatSame = EntryCombat(g),round = EntryRound(g),turn = EntryTurn(g),side = EntrySide(g) } },
                _ => null };
            History = boundary =>
            {
                var entries = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
                return new { plays = entries.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card),index = e.CardPlay.PlayIndex,count = e.CardPlay.PlayCount,autoPlay = e.CardPlay.IsAutoPlay }).ToArray(),
                    finished = entries.OfType<CardPlayFinishedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card),autoPlay = e.CardPlay.IsAutoPlay }).ToArray(),
                    exhausts = entries.OfType<CardExhaustedEntry>().Select(e => Ref(e.Card)).ToArray(),
                    draws = entries.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card),fromHandDraw = e.FromHandDraw }).ToArray(),
                    moves = entries.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemy = e.Monster.Creature.CombatId,move = e.Move.Id }).ToArray(),
                    damage = entries.OfType<DamageReceivedEntry>().Select(DamageRow).ToArray(),
                    ordered = entries.Select(OrderedRow).Where(e => e is not null).ToArray(),
                    generated = entries.OfType<CardGeneratedEntry>().Select(e => new { cardRef = Ref(e.Card),creatorId = e.Creator?.Creature.CombatId }).ToArray() };
            };
            var snapshot = Snapshot; var history = History;
            var initial = snapshot();
            async Task<CardModel> Create(string code,string label,PileType pile = PileType.Hand,CardPilePosition position = CardPilePosition.Bottom)
            {
                CardModel card = code switch { "U03" => state.CreateCard<Volibear_U03>(p),"C24" => state.CreateCard<Volibear_C24>(p),
                    "B02" => state.CreateCard<Volibear_B02>(p),"MAYHEM" => state.CreateCard<Mayhem>(p),_ => throw new InvalidOperationException("Unknown fixture") };
                if (code == "U03" && variant == "U03-upgraded-extra-turn") CardCmd.Upgrade(card);
                Cards.Add(card,label); await CardPileCmd.Add(card,pile,position); return card;
            }
            var actions = new List<object>(); var setups = new List<object>(); var transitions = new List<object>();
            async Task Play(CardModel card,string label,Creature? target = null)
            {
                var before = snapshot(); int boundary = CombatManager.Instance.History.Entries.Count(),paid = Payments.Count,effects = Effects.Count;
                var action = new PlayCardAction(card,target);var events = new List<object>();
                action.BeforeExecuted += a => events.Add(new { name = "before-executed",state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
                action.BeforeCancelled += a => events.Add(new { name = "cancelled",state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
                action.AfterFinished += a => events.Add(new { name = "after-finished",state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
                await Until(() => action.CompletionTask.IsCompleted,"Native standing action did not finish: "+label); await action.CompletionTask;
                if (action.Exception is not null) throw new InvalidOperationException("Native standing action failed",action.Exception);
                actions.Add(new { label,cardRef = Ref(card),before,after = snapshot(),action = new { id = action.Id,state = action.State.ToString(),type = action.GetType().Name,
                    actionType = action.ActionType.ToString(),context = action.PlayerChoiceContext?.GetType().Name,target = action.TargetId,sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(),card),events },
                    payments = Payments.Skip(paid).ToArray(),effects = Effects.Skip(effects).ToArray(),history = history(boundary) });
            }
            async Task Prepare(string label,string code,string target)
            {
                var before = snapshot(); await Create(code,target,PileType.Draw,CardPilePosition.Top);
                for (int i = 4;i >= 0;i--) await Create("B02",label+"-padding-"+i,PileType.Draw,CardPilePosition.Top);
                setups.Add(new { label,operation = "CardPileCmd.Add-Top-five-padding-before-native-auto-target",target,before,after = snapshot() });
            }
            async Task EndTurn(string label,int nextTurn)
            {
                var before = snapshot(); int boundary = CombatManager.Instance.History.Entries.Count(),paid = Payments.Count,effects = Effects.Count,
                    ends = Boundaries.Count,extras = ExtraTurns.Count,autos = AutoPhases.Count,gains = BlockGains.Count,preventers = ClearPreventers.Count;
                activeTransition = label;
                PlayerCmd.EndTurn(p,canBackOut:false);
                await Until(() => pcs.TurnNumber == nextTurn && state.CurrentSide == CombatSide.Player && pcs.Phase == PlayerTurnPhase.Play,"Native player turn did not begin: "+label);
                activeTransition = null;
                transitions.Add(new { label,before,after = snapshot(),history = history(boundary),payments = Payments.Skip(paid).ToArray(),effects = Effects.Skip(effects).ToArray(),
                    boundaries = Boundaries.Skip(ends).ToArray(),extraTurns = ExtraTurns.Skip(extras).ToArray(),autoPhases = AutoPhases.Skip(autos).ToArray(),blockGains = BlockGains.Skip(gains).ToArray(),clearPreventers = ClearPreventers.Skip(preventers).ToArray() });
            }
            await Play(await Create("MAYHEM","mayhem"),"mayhem");
            await Prepare("turn2","U03","standing"); await EndTurn("natural-enemy-before-standing",2);
            var fixtureBefore = snapshot(); int fixtureGainStart = BlockGains.Count,fixturePreventerStart = ClearPreventers.Count;
            decimal fixtureGain = 40m - creature.Block;
            if (fixtureGain <= 0) throw new InvalidOperationException("Unexpected U03 entry block");
            await CreatureCmd.GainBlock(creature,fixtureGain,MegaCrit.Sts2.Core.ValueProps.ValueProp.Unpowered,null);
            var blockFixture = new { operation = "CreatureCmd.GainBlock-Unpowered-to40",amount = fixtureGain,before = fixtureBefore,after = snapshot(),
                blockGains = BlockGains.Skip(fixtureGainStart).ToArray(),clearPreventers = ClearPreventers.Skip(fixturePreventerStart).ToArray() };
            await Prepare("extra","C24","extra-thunder"); await EndTurn("paels-eye-extra-player-turn",3);
            await Prepare("turn4","C24","normal-thunder"); await EndTurn("natural-enemy-after-extra",4);
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            GD.Print("[Volibear] STANDING_EXTRA_TURN_RESULT " + JsonSerializer.Serialize(new {
                token,variant,scenario = "standing-extra-turn",schema = "standing-extra-turn-v1",completed = true,gameVersion = release.Version,gameCommit = release.Commit,testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "native-mayhem-standing-extra-and-normal-player-start-not-OS-input",fixture = "fresh-native-three-slimes-energy30-enemyHp500-created-cards-five-padding-native-block40-explicit",
                character = p.Character.GetType().Name,playerId = creature.CombatId,enemyIds = enemies.Select(e => e.CombatId).ToArray(),enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                cards = Cards.Where(kv => !kv.Value.StartsWith("generated-")).Select(kv => new { cardRef = kv.Value,modelId = kv.Key.Id.Entry,upgraded = kv.Key.IsUpgraded,
                    combatCardIndex = NetCombatCard.FromModel(kv.Key).CombatCardIndex,sameObject = ReferenceEquals(NetCombatCard.FromModel(kv.Key).ToCardModel(),kv.Key),ownerId = kv.Key.Owner.Creature.CombatId,
                    masterIndex = Array.FindIndex(p.Deck.Cards.ToArray(),c => ReferenceEquals(c,kv.Key.DeckVersion)),masterModelId = kv.Key.DeckVersion?.Id.Entry }).ToArray(),
                generated,initial,actions,setups,blockFixture,transitions,final = snapshot(),payments = Payments,effects = Effects,boundaries = Boundaries,extraTurns = ExtraTurns,autoPhases = AutoPhases,blockGains = BlockGains,clearPreventers = ClearPreventers,blockTrace = BlockTrace,powerLifecycle = PowerLifecycle }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] STANDING_EXTRA_TURN_ERROR " + error);((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { if (owner is not null) { owner.Creature.BlockChanged -= ObserveBlockChanged;owner.Creature.PowerApplied -= ObservePowerAdded;owner.Creature.PowerRemoved -= ObservePowerRemoved; } Generated = null;Snapshot = null;History = null;owner = null;combat = null;CombatManager.Instance.TurnStarted -= Start;Observer.UnpatchAll(Observer.Id); }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterBlockGained))]
    private static class BlockGain
    {
        private static void Prefix(Creature creature,decimal amount)
        { if (owner is not null && ReferenceEquals(creature,owner.Creature)) BlockGains.Add(amount); }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterPreventingBlockClear))]
    private static class ClearPreventer
    {
        private static void Prefix(AbstractModel preventer,Creature creature)
        { if (owner is not null && ReferenceEquals(creature,owner.Creature)) ClearPreventers.Add(preventer.GetType().Name); }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterCardGeneratedForCombat))]
    private static class Generation { private static void Prefix(CardModel card,Player? creator) => Generated?.Invoke(card,creator); }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterEnergySpent))]
    private static class Payment
    {
        private static void Prefix(CardModel card,int amount)
        {
            if (owner is not null && ReferenceEquals(card.Owner,owner)) Payments.Add(new { cardRef = Ref(card),amount,energy = owner.PlayerCombatState!.Energy,window = Window() });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.BeforeCardPlayed))]
    private static class Effect
    {
        private static void Postfix(CardPlay cardPlay,ref Task __result) => __result = Observe(__result,cardPlay);
        private static async Task Observe(Task original,CardPlay play)
        {
            await original;
            if (owner is null || !ReferenceEquals(play.Card.Owner,owner)) return;
            Effects.Add(new { cardRef = Ref(play.Card),index = play.PlayIndex,count = play.PlayCount,autoPlay = play.IsAutoPlay,playId = CardResolutionHooks.CurrentPlayId(play.Card),
                spent = play.Resources.EnergySpent,energy = owner.PlayerCombatState!.Energy,window = Window() });
        }
    }
#if STS2_BETA
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterSideTurnEnd))]
#else
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterTurnEnd))]
#endif
    private static class TurnEnd
    {
        private static void Prefix(out object? __state) => __state = owner is null ? null : Window();
        private static void Postfix(CombatSide side,IEnumerable<Creature> participants,object? __state,ref Task __result) => __result = Observe(__result,side,participants.ToArray(),__state);
        private static async Task Observe(Task original,CombatSide side,Creature[] participants,object? before)
        {
            await original;if (before is null || owner is null) return;
            Boundaries.Add(new { hook = "Hook.AfterTurnEnd",side = side.ToString(),participants = participants.Select(c => c.CombatId).ToArray(),before,after = Window() });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterTakingExtraTurn))]
    private static class ExtraTurn
    {
        private static void Prefix(out object? __state) => __state = owner is null ? null : Window();
        private static void Postfix(Player player,object? __state,ref Task __result) => __result = Observe(__result,player,__state);
        private static async Task Observe(Task original,Player player,object? before)
        {
            await original;if (before is null || owner is null) return;
            ExtraTurns.Add(new { hook = "Hook.AfterTakingExtraTurn",playerId = player.Creature.CombatId,before,after = Window() });
        }
    }
    private sealed record Phase(object Before,int HistoryIndex,int PaymentsIndex,int EffectsIndex,int GainsIndex,int PreventersIndex,string Context);
    [HarmonyPatch(typeof(MayhemPower),nameof(MayhemPower.AfterAutoPrePlayPhaseEntered))]
    private static class MayhemPhase
    {
        private static void Prefix(PlayerChoiceContext choiceContext,Player player,out Phase? __state) => __state = owner is null || !ReferenceEquals(player,owner) || Snapshot is null ? null :
            new Phase(Snapshot(),CombatManager.Instance.History.Entries.Count(),Payments.Count,Effects.Count,BlockGains.Count,ClearPreventers.Count,choiceContext.GetType().Name);
        private static void Postfix(Phase? __state,ref Task __result) => __result = Observe(__result,__state);
        private static async Task Observe(Task original,Phase? phase)
        {
            await original;if (phase is null || Snapshot is null || History is null) return;
            AutoPhases.Add(new { hook = "MayhemPower.AfterAutoPrePlayPhaseEntered",context = phase.Context,before = phase.Before,after = Snapshot(),
                history = History(phase.HistoryIndex),payments = Payments.Skip(phase.PaymentsIndex).ToArray(),effects = Effects.Skip(phase.EffectsIndex).ToArray(),blockGains = BlockGains.Skip(phase.GainsIndex).ToArray(),clearPreventers = ClearPreventers.Skip(phase.PreventersIndex).ToArray() });
        }
    }
}
