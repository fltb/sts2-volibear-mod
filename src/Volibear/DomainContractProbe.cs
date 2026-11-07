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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;
using VoidCard = MegaCrit.Sts2.Core.Models.Cards.Void;

namespace Volibear;

/// <summary>
/// Explicit isolated real-engine fixture. AutoPlay verifies effects, NOT payment or
/// normal input. TwinStrike is a native multihit/replay proxy, not C02 acceptance.
/// Expectations live in the external runner; this records measured state and events.
/// No native enemy/card action delegates are replaced and no production flags are used.
/// </summary>
internal static class DomainContractProbe
{
    private static bool _started;
    private static Player? _observedPlayer;
    private static readonly List<int> NormalDrawDomainAmounts = [];
    private static readonly Harmony Observer = new("Volibear.DomainContractObserver");

    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObserveNormalDraw)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveBeforePlayScope)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveAfterPlayScope)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveOrdinarySegment)).Patch();
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }

    private static void OnTurnStarted(CombatState state)
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
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_CASE") ?? "d01";
            if (string.IsNullOrWhiteSpace(token) || variant is not ("d01" or "d02" or "d03" or "l02" or "draw-expiry"))
                throw new InvalidOperationException("Missing current domain fixture token or valid variant.");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Native domain fixture cannot use TestMode.");
            var player = state.Players.Single();
            var owner = player.Creature;
            var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("Missing player combat state.");
            var enemies = state.Enemies.ToArray();
            if (enemies.Length != 3 || enemies.Any(e => e.Block != 0 || e.CombatId is null) ||
                owner.CurrentHp != 80 || owner.Block != 0 || state.RoundNumber != 1 || pcs.TurnNumber != 1 ||
                owner.GetPowerAmount<DomainPower>() != 0 || StormChargePower.Current(owner) != 0 ||
                LightningBatches.GetTurnCount(owner) != 0)
                throw new InvalidOperationException("Expected fresh 3-enemy unblocked first-turn fixture.");
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100m);
            var choices = new ThrowingPlayerChoiceContext();
            var ids = new Dictionary<CardModel, string>(ReferenceEqualityComparer.Instance);
            var startingCards = pcs.AllPiles.SelectMany(p => p.Cards).ToArray();
            foreach (var card in startingCards)
                if (!ids.ContainsKey(card)) ids.Add(card, "starting-" + ids.Count);
            string? Ref(CardModel? card) => card is null ? null : ids.TryGetValue(card, out var id)
                ? id : throw new InvalidOperationException("Unbound actual card identity in observation.");
            uint EnemyRef(Creature creature) => creature.CombatId
                ?? throw new InvalidOperationException("Missing native enemy identity.");
            var batches = new List<object>();
            using var subscription = LightningBatches.Subscribe(owner, (context, batch) =>
            {
                batches.Add(new
                {
                    id = batch.Id, round = batch.RoundNumber, turn = batch.PlayerTurnNumber,
                    baseDamage = batch.BaseDamage, storm = batch.StormCharge, amount = batch.Amount,
                    count = batch.CountThisTurn, cardRef = Ref(batch.Card),
                    playId = batch.Card is null ? null : CardResolutionHooks.CurrentPlayId(batch.Card),
                    targets = batch.Targets.Select(EnemyRef).ToArray(),
                    hits = batch.Results.Select(hit => new { target = EnemyRef(hit.Receiver),
                        hpLost = hit.HpLost, blocked = hit.Blocked, overkill = hit.Overkill }).ToArray()
                });
                return Task.CompletedTask;
            });
            object data;
            if (variant == "draw-expiry")
                data = await DrawExpiry(state, player, choices, ids);
            else
            {
                var force = variant == "d01" ? 2 : variant == "l02" ? 3 : 0;
                if (force != 0) await StormChargePower.Gain(choices, owner, force);
                if (variant != "l02") await DomainPower.Open(choices, owner, 1);
                if (variant == "l02")
                    foreach (var enemy in enemies) await CreatureCmd.GainBlock(enemy, 10m, ValueProp.Unpowered, null);
                var played = new List<CardModel>();
                if (variant == "d01") played.AddRange(startingCards.OfType<Content.Volibear_B01>().Take(2));
                else if (variant is "d02" or "d03")
                {
                    var twin = state.CreateCard<TwinStrike>(player);
                    twin.BaseReplayCount = variant == "d03" ? 1 : 0;
                    ids.Add(twin, "native-twin-strike");
                    played.Add(twin);
                }
                foreach (var card in played) await CardPileCmd.Add(card, pcs.Hand);
                var beforeHp = enemies.Select(e => e.CurrentHp).ToArray();
                var beforeBlock = enemies.Select(e => (int)e.Block).ToArray();
                var historyStart = CombatManager.Instance.History.Entries.Count();
                var countBefore = LightningBatches.GetTurnCount(owner);
                var energyBefore = pcs.Energy;
                var calls = 0;
                if (variant == "l02") await Content.LightningCmd.DealAllEnemies(choices, owner, 0m);
                else foreach (var card in played)
                {
                    calls++;
                    await CardCmd.AutoPlay(choices, card, enemies[0]);
                }
                var afterHp = enemies.Select(e => e.CurrentHp).ToArray();
                var afterBlock = enemies.Select(e => (int)e.Block).ToArray();
                var countAfter = LightningBatches.GetTurnCount(owner);
                // Deliberately unrelated native non-attack damage must NOT add lightning count.
                if (variant == "l02") await NativeCompat.Damage(choices, enemies, 1m, ValueProp.Unpowered, owner, null);
                var history = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
                data = new
                {
                    inputs = new { domainRounds = variant == "l02" ? 0 : 1, storm = force,
                        fixtureEnemyHp = 100, fixtureEnemyBlock = variant == "l02" ? 10 : 0,
                        explicitLightningBase = variant == "l02" ? (int?)0 : null,
                        unrelatedUnpowered = variant == "l02" ? 1 : 0,
                        cards = played.Select(c => new { cardRef = Ref(c), type = c.GetType().Name,
                            upgrade = c.IsUpgraded, replay = c.BaseReplayCount }).ToArray() },
                    beforeHp, beforeBlock, afterHp, afterBlock,
                    finalHp = enemies.Select(e => e.CurrentHp).ToArray(),
                    finalBlock = enemies.Select(e => (int)e.Block).ToArray(),
                    countBefore, countAfter, countFinal = LightningBatches.GetTurnCount(owner),
                    domainAmount = owner.GetPowerAmount<DomainPower>(), stormAmount = StormChargePower.Current(owner),
                    energyBefore, energyAfter = pcs.Energy, actualAutoPlayCalls = calls,
                    cardPiles = played.Select(c => new { cardRef = Ref(c), pile = c.Pile?.Type.ToString(),
                        sameIdentity = pcs.AllPiles.Any(p => p.Cards.Any(actual => ReferenceEquals(actual, c))) }).ToArray(),
                    playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new
                        { cardRef = Ref(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
                    damageHistory = history.OfType<DamageReceivedEntry>().Where(e => ReferenceEquals(e.Dealer, owner))
                        .Select(e => new { target = EnemyRef(e.Receiver), hpLost = e.Result.UnblockedDamage,
                            blocked = e.Result.BlockedDamage, props = (int)e.Result.Props,
                            cardRef = Ref(e.CardSource) }).ToArray()
                };
            }
            GD.Print("[Volibear] DOMAIN_CONTRACT_RESULT " + JsonSerializer.Serialize(new
            {
                token, scenario = "domain-contract", variant, completed = true,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "effect-only-not-payment", character = player.Character.GetType().Name,
                fixtureApi = "CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add;PowerCmd;CardCmd.AutoPlay",
                api = variant == "l02" ? "LightningCmd+CreatureCmd.Damage" : variant == "draw-expiry"
                    ? "CardPileCmd.Draw+PlayerCmd.EndTurn" : "CardCmd.AutoPlay",
                proxy = variant is "d02" or "d03" ? "native-TwinStrike-not-C02-acceptance" : "none",
                enemyIds = enemies.Select(EnemyRef).ToArray(),
                enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                data, batches
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0); // External gate decides values, not this exit code.
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_CONTRACT_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            _observedPlayer = null;
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
            Observer.UnpatchAll(Observer.Id);
        }
    }

    private static async Task<object> DrawExpiry(CombatState state, Player player,
        PlayerChoiceContext choices, Dictionary<CardModel, string> ids)
    {
        var pcs = player.PlayerCombatState!;
        var owner = player.Creature;
        // Clear hand via ordinary pile movement, not fake draw hooks.
        foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
        var original = pcs.AllPiles.SelectMany(p => p.Cards).ToArray();
        var replacements = original.OfType<Content.Volibear_B01>().Take(3).Cast<CardModel>().ToArray();
        if (replacements.Length != 3) throw new InvalidOperationException("Need 3 distinct starting strikes.");
        var direct = state.CreateCard<VoidCard>(player);
        var boundary = state.CreateCard<VoidCard>(player);
        var outside = state.CreateCard<VoidCard>(player);
        ids.Add(direct, "direct-void"); ids.Add(boundary, "boundary-void"); ids.Add(outside, "outside-void");
        await PlayerCmd.SetEnergy(3m, player);
        await StormChargePower.Gain(choices, owner, 2);
        await DomainPower.Open(choices, owner, 1);
        await CardPileCmd.Add(replacements[0], PileType.Draw, CardPilePosition.Top);
        await CardPileCmd.Add(direct, PileType.Draw, CardPilePosition.Top);
        var before = CombatManager.Instance.History.Entries.Count();
        await CardPileCmd.Draw(choices, 1m, player);
        var directResult = new
        {
            energy = pcs.Energy, domain = owner.GetPowerAmount<DomainPower>(), handCount = pcs.Hand.Cards.Count,
            voidPile = direct.Pile?.Type.ToString(), replacementPile = replacements[0].Pile?.Type.ToString(),
            sameVoid = PileType.Exhaust.GetPile(player).Cards.Any(c => ReferenceEquals(c, direct)),
            sameReplacement = pcs.Hand.Cards.Any(c => ReferenceEquals(c, replacements[0])),
            drawn = CombatManager.Instance.History.Entries.Skip(before).OfType<CardDrawnEntry>()
                .Select(e => new { cardRef = ids[e.Card], fromHandDraw = e.FromHandDraw }).ToArray()
        };
        await CardPileCmd.Add(replacements[1], PileType.Draw, CardPilePosition.Top);
        await CardPileCmd.Add(boundary, PileType.Draw, CardPilePosition.Top);
        await CreatureCmd.GainBlock(owner, 100m, ValueProp.Unpowered, null);
        int roundBefore = state.RoundNumber;
        int turnBefore = pcs.TurnNumber;
        var boundaryHistoryStart = CombatManager.Instance.History.Entries.Count();
        NormalDrawDomainAmounts.Clear();
        _observedPlayer = player;
        PlayerCmd.EndTurn(player, canBackOut: false);
        var deadline = System.Diagnostics.Stopwatch.StartNew();
        while (state.RoundNumber <= roundBefore || state.CurrentSide != CombatSide.Player || pcs.Phase != PlayerTurnPhase.Play)
        {
            if (deadline.Elapsed > TimeSpan.FromSeconds(20)) throw new TimeoutException("Domain fixture next normal turn timed out.");
            var tree = (SceneTree)Engine.GetMainLoop();
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
        _observedPlayer = null;
        var boundaryResult = new
        {
            round = state.RoundNumber, turn = pcs.TurnNumber, domainAfterFullDraw = NormalDrawDomainAmounts.ToArray(),
            domainAfterEarlyHook = owner.GetPowerAmount<DomainPower>(), storm = StormChargePower.Current(owner),
            count = LightningBatches.GetTurnCount(owner), energy = pcs.Energy, handCount = pcs.Hand.Cards.Count,
            voidPile = boundary.Pile?.Type.ToString(), replacementPile = replacements[1].Pile?.Type.ToString(),
            sameVoid = PileType.Exhaust.GetPile(player).Cards.Any(c => ReferenceEquals(c, boundary)),
            sameReplacement = pcs.Hand.Cards.Any(c => ReferenceEquals(c, replacements[1])),
            drawn = CombatManager.Instance.History.Entries.Skip(boundaryHistoryStart).OfType<CardDrawnEntry>()
                .Select(e => new { cardRef = ids.TryGetValue(e.Card, out var id) ? id : e.Card.GetType().Name,
                    fromHandDraw = e.FromHandDraw }).ToArray()
        };
        await CardPileCmd.Add(replacements[2], PileType.Draw, CardPilePosition.Top);
        await CardPileCmd.Add(outside, PileType.Draw, CardPilePosition.Top);
        var outsideHistoryStart = CombatManager.Instance.History.Entries.Count();
        var outsideHandBefore = pcs.Hand.Cards.Count;
        var outsideEnergyBefore = pcs.Energy;
        await CardPileCmd.Draw(choices, 1m, player);
        var outsideResult = new
        {
            energyBefore = outsideEnergyBefore, energyAfter = pcs.Energy,
            handBefore = outsideHandBefore, handAfter = pcs.Hand.Cards.Count,
            voidPile = outside.Pile?.Type.ToString(), replacementPile = replacements[2].Pile?.Type.ToString(),
            sameVoid = pcs.Hand.Cards.Any(c => ReferenceEquals(c, outside)),
            drawn = CombatManager.Instance.History.Entries.Skip(outsideHistoryStart).OfType<CardDrawnEntry>()
                .Select(e => new { cardRef = ids[e.Card], fromHandDraw = e.FromHandDraw }).ToArray()
        };
        return new { inputs = new { domainRounds = 1, storm = 2, directDrawCount = 1,
            normalDrawCount = 5, outsideDrawCount = 1, energy = 3,
            replacementRefs = replacements.Select(c => ids[c]).ToArray(), statusType = "Void" },
            roundBefore, turnBefore, direct = directResult, boundary = boundaryResult, outside = outsideResult };
    }

    private static void TraceScope(string stage, CardModel? card, Creature? dealer = null,
        CardResolutionHooks.PlayScope? argument = null, Task? native = null, int? resultCount = null,
        ValueProp? props = null, int? nativeState = null)
    {
        var current = ((System.Threading.AsyncLocal<CardResolutionHooks.PlayScope?>)
            AccessTools.Field(typeof(CardResolutionHooks), "Current").GetValue(null)!).Value;
        var active = (IEnumerable<CardResolutionHooks.PlayScope>)
            AccessTools.Field(typeof(CardResolutionHooks), "ActivePlays").GetValue(null)!;
        GD.Print("[Volibear] DOMAIN_SCOPE_TRACE " + JsonSerializer.Serialize(new
        {
            token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"), stage,
            card = card?.GetType().Name, dealer = dealer?.CombatId,
            dealerIsOwner = card is not null && ReferenceEquals(dealer, card.Owner.Creature),
            domainActive = card is not null && DomainPower.IsActive(card.Owner.Creature),
            current = current?.Id, currentCard = current?.Card.GetType().Name,
            currentIsCard = current is not null && ReferenceEquals(current.Card, card),
            currentClosed = current?.Gate.Closed, currentAttached = current?.Gate.Attached,
            argument = argument?.Id, argumentClosed = argument?.Gate.Closed,
            active = active.Select(scope => new { id = scope.Id, card = scope.Card.GetType().Name,
                isCard = ReferenceEquals(scope.Card, card), closed = scope.Gate.Closed,
                attached = scope.Gate.Attached }).ToArray(),
            nativeId = native?.Id, nativeStatus = native?.Status.ToString(), nativeState, resultCount, props = (int?)props
        }));
    }

    [HarmonyPatch(typeof(CardResolutionHooks), "EnterPlayMove")]
    private static class ObserveBeforePlayScope
    {
        private static void Prefix(Task __0, CardModel __1, int __2)
            => TraceScope("EnterMove:enter", __1, native: __0, nativeState: __2);
        private static void Postfix(Task __0, CardModel __1, int __2, CardResolutionHooks.PlayMoveFrame __result)
            => TraceScope("EnterMove:exit", __1, argument: __result.Scope, native: __0, nativeState: __2);
    }

    [HarmonyPatch(typeof(CardResolutionHooks), "LeavePlayMove")]
    private static class ObserveAfterPlayScope
    {
        private static void Prefix(CardResolutionHooks.PlayMoveFrame __0, Task __1, int __2)
            => TraceScope("LeaveMove:enter", __0.Scope?.Card, argument: __0.Scope, native: __1, nativeState: __2);
        private static void Postfix(CardResolutionHooks.PlayMoveFrame __0, Task __1, int __2)
            => TraceScope("LeaveMove:exit", __0.Scope?.Card, argument: __0.Scope, native: __1, nativeState: __2);
    }

    [HarmonyPatch(typeof(CardResolutionHooks), nameof(CardResolutionHooks.OrdinaryAttackPipelineV1))]
    private static class ObserveOrdinarySegment
    {
        private static void Prefix(ValueProp __1, Creature? __2, CardModel? __3)
            => TraceScope("OrdinarySegment:enter", __3, __2, props: __1);
        private static void Postfix(Creature? __2, CardModel? __3, ref Task<IEnumerable<DamageResult>> __result)
            => __result = Record(__result, __2, __3);
        private static async Task<IEnumerable<DamageResult>> Record(Task<IEnumerable<DamageResult>> native,
            Creature? dealer, CardModel? card)
        {
            var results = await native;
            TraceScope("OrdinarySegment:exit", card, dealer, native: native, resultCount: results.Count());
            return results;
        }
    }

    // Observe the exact native successful Draw boundary BEFORE SetResult resumes
    // the turn-start caller. An outer async-entry postfix can be bypassed by inlining.
    [HarmonyPatch(typeof(CardResolutionHooks), "CompleteDrawMove")]
    private static class ObserveNormalDraw
    {
        private static void Postfix(object __0)
        {
            var type = __0.GetType();
            var player = (Player)AccessTools.Field(type, "Player").GetValue(__0)!;
            var fromHandDraw = (bool)AccessTools.Field(type, "FromHandDraw").GetValue(__0)!;
            if (fromHandDraw && ReferenceEquals(player, _observedPlayer))
                NormalDrawDomainAmounts.Add(player.Creature.GetPowerAmount<DomainPower>());
        }
    }
}
