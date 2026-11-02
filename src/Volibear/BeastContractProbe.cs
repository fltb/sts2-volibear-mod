using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;
using VoidCard = MegaCrit.Sts2.Core.Models.Cards.Void;

namespace Volibear;

/// <summary>Explicit isolated engine fixture, not production rule branches. AutoPlay
/// observes form effects and native cleanup only; it does NOT verify manual payment.</summary>
internal static class BeastContractProbe
{
    private static bool started;
    public static void Install() => CombatManager.Instance.TurnStarted += OnTurnStarted;
    private static void OnTurnStarted(CombatState state)
    {
        if (started) return;
        started = true;
        _ = Run(state);
    }

    private sealed class Fixture(CombatState combat)
    {
        internal readonly CombatState Combat = combat;
        internal readonly Player Player = combat.Players.Single();
        internal readonly Creature[] Enemies = combat.Enemies.ToArray();
        internal readonly ThrowingPlayerChoiceContext Choices = new();
        internal readonly Dictionary<CardModel, string> Ids = new(ReferenceEqualityComparer.Instance);
        internal readonly List<object> Changes = [];
        internal string? PendingBeastName;
        internal PlayerCombatState Pcs => Player.PlayerCombatState!;
        internal string? Ref(CardModel? card)
        {
            if (card is null) return null;
            if (!Ids.TryGetValue(card, out var name)) Ids.Add(card, name = "observed-" + Ids.Count);
            return name;
        }
        internal void Name(CardModel card, string name)
        {
            if (Ids.ContainsKey(card)) throw new InvalidOperationException("Duplicate material alias.");
            Ids.Add(card, name);
        }
        internal Task Changed(PlayerChoiceContext _, BeastChange change)
        {
            if (PendingBeastName is { } name && !Ids.ContainsKey(change.Card)) Name(change.Card, name);
            PendingBeastName = null;
            Changes.Add(new { cardRef = Ref(change.Card), shape = change.Shape.ToString(),
                ownerRef = RuntimeHelpers.GetHashCode(change.Card.Owner),
                sameCombat = ReferenceEquals(change.Combat, Combat) });
            return Task.CompletedTask;
        }
        internal object Snapshot(CardModel card) => new
        {
            cardRef = Ref(card), nativeType = card.GetType().Name, modelId = card.Id.Entry,
            ownerRef = RuntimeHelpers.GetHashCode(card.Owner), masterRef = Ref(card.DeckVersion), cloneRef = Ref(card.CloneOf),
            costObjectRef = RuntimeHelpers.GetHashCode(card.EnergyCost),
            shape = BeastForms.Shape(card).ToString(), type = card.Type.ToString(), target = card.TargetType.ToString(),
            upgrade = card.IsUpgraded, canonicalCost = card.EnergyCost.Canonical, costsX = card.EnergyCost.CostsX,
            localCost = card.EnergyCost.GetWithModifiers(CostModifiers.Local),
            allCost = card.EnergyCost.GetWithModifiers(CostModifiers.All), amountToSpend = card.EnergyCost.GetAmountToSpend(),
            retain = card.ShouldRetainThisTurn, keywords = card.Keywords.Select(k => k.ToString()).OrderBy(s => s).ToArray(),
            pile = card.Pile?.Type.ToString(), presence = Pcs.AllPiles.Sum(p => p.Cards.Count(c => ReferenceEquals(c, card))),
            vars = card.DynamicVars.ToDictionary(p => p.Key, p => p.Value.BaseValue), title = card.Title
        };
        internal object HistorySince(int start)
        {
            var entries = CombatManager.Instance.History.Entries.Skip(start).ToArray();
            return new
            {
                exhausted = entries.OfType<CardExhaustedEntry>().Select(e => Ref(e.Card)).ToArray(),
                generated = entries.OfType<CardGeneratedEntry>().Select(e => Ref(e.Card)).ToArray()
            };
        }
        internal object[] Deck() => Player.Deck.Cards.Select(c => (object)new
        {
            cardRef = Ref(c), modelId = c.Id.Entry, nativeType = c.GetType().Name,
            upgrade = c.IsUpgraded, cost = c.EnergyCost.GetWithModifiers(CostModifiers.Local),
            shape = BeastForms.Shape(c).ToString(), vars = c.DynamicVars.ToDictionary(p => p.Key, p => p.Value.BaseValue)
        }).ToArray();
        internal async Task ResetBoard()
        {
            foreach (var enemy in Enemies)
            {
                await CreatureCmd.SetMaxAndCurrentHp(enemy, 100m);
                if (enemy.Block != 0) await CreatureCmd.LoseBlock(enemy, enemy.Block);
            }
            if (Player.Creature.Block != 0) await CreatureCmd.LoseBlock(Player.Creature, Player.Creature.Block);
        }
        internal async Task<object> Play(CardModel card)
        {
            await ResetBoard();
            var beforeHp = Enemies.Select(e => e.CurrentHp).ToArray();
            var blockBefore = Player.Creature.Block;
            var energyBefore = Pcs.Energy;
            var countBefore = LightningBatches.GetTurnCount(Player.Creature);
            var historyStart = CombatManager.Instance.History.Entries.Count();
            var calls = 0;
            calls++;
            await CardCmd.AutoPlay(Choices, card, card.Type == CardType.Attack ? Enemies[0] : null);
            var history = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            return new
            {
                beforeHp, afterHp = Enemies.Select(e => e.CurrentHp).ToArray(), blockBefore,
                blockAfter = Player.Creature.Block, energyBefore, energyAfter = Pcs.Energy,
                lightningBefore = countBefore, lightningAfter = LightningBatches.GetTurnCount(Player.Creature),
                playerStrength = Player.Creature.GetPowerAmount<StrengthPower>(),
                enemyVulnerable = Enemies.Select(e => e.GetPowerAmount<VulnerablePower>()).ToArray(),
                autoPlayCalls = calls, after = Snapshot(card),
                playHistory = history.OfType<CardPlayStartedEntry>().Select(e => new
                { cardRef = Ref(e.CardPlay.Card), index = e.CardPlay.PlayIndex, count = e.CardPlay.PlayCount }).ToArray(),
                damageHistory = history.OfType<DamageReceivedEntry>().Where(e => ReferenceEquals(e.Dealer, Player.Creature))
                    .Select(e => new { target = e.Receiver.CombatId, hpLost = e.Result.UnblockedDamage,
                        blocked = e.Result.BlockedDamage, props = (int)e.Result.Props, cardRef = Ref(e.CardSource) }).ToArray()
            };
        }
    }

    private static async Task Run(CombatState state)
    {
        Fixture? fixture = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_BEAST_CASE") ?? "f01";
            if (string.IsNullOrWhiteSpace(token) || variant is not ("f01" or "f02"))
                throw new InvalidOperationException("Missing current token or unknown beast fixture.");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode prohibited.");
            fixture = new Fixture(state);
            var f = fixture;
            if (f.Enemies.Length != 3 || f.Enemies.Any(e => e.CombatId is null) || state.RoundNumber != 1 ||
                f.Pcs.TurnNumber != 1 || f.Pcs.Energy != 3 || f.Player.Creature.CurrentHp != 80 ||
                f.Player.Creature.GetPowerAmount<DomainPower>() != 0 || StormChargePower.Current(f.Player.Creature) != 0 ||
                LightningBatches.GetTurnCount(f.Player.Creature) != 0)
                throw new InvalidOperationException("Expected fresh 3-enemy, 80HP, 3-energy, no-domain/force fixture.");
            // Name master entities before naming their original combat copies.
            foreach (var master in f.Player.Deck.Cards) f.Name(master, "master-" + f.Ids.Count);
            var originals = f.Pcs.AllPiles.SelectMany(p => p.Cards).ToArray();
            var starter = originals.OfType<Volibear_B01>().First();
            f.Name(starter, "starter-claw");
            if (starter.DeckVersion is null || !f.Player.Deck.Cards.Any(c => ReferenceEquals(c, starter.DeckVersion)))
                throw new InvalidOperationException("Starter is not an actual combat copy of the native master deck.");
            foreach (var card in originals) await CardPileCmd.Add(card, PileType.Discard);
            var deckBefore = f.Deck();
            BeastForms.Converted += f.Changed;
            var data = variant == "f01" ? await F01(f, starter) : await F02(f);
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No runtime release metadata.");
            GD.Print("[Volibear] BEAST_CONTRACT_RESULT " + JsonSerializer.Serialize(new
            {
                token, scenario = "beast-contract", variant, completed = true,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "effect-only-not-payment", character = f.Player.Character.GetType().Name,
                gameVersion = release.Version, gameCommit = release.Commit,
                fixtureApi = "CombatState.CreateCard;CardPileCmd.Add;CardCmd.Upgrade;CreatureCmd.SetMaxAndCurrentHp",
                api = "BeastForms.Convert;CardCmd.Exhaust;CardPileCmd.AddGeneratedCardToCombat;CardCmd.AutoPlay;CardPileCmd.Draw;PlayerCmd.EndTurn",
                enemyIds = f.Enemies.Select(e => e.CombatId).ToArray(),
                enemyTypes = f.Enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                deckBefore, deckAfter = f.Deck(), changes = f.Changes, data
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] BEAST_CONTRACT_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            if (fixture is not null) BeastForms.Converted -= fixture.Changed;
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }

    private static async Task<object> F01(Fixture f, CardModel starter)
    {
        var rows = new List<object>();
        async Task Row(string name, CardModel card, bool upgrade = false, bool retain = false, bool draw = false)
        {
            if (!f.Ids.ContainsKey(card)) f.Name(card, name);
            if (upgrade) CardCmd.Upgrade(card);
            if (retain) card.GiveSingleTurnRetain();
            await CardPileCmd.Add(card, draw ? PileType.Draw : PileType.Hand, CardPilePosition.Top);
            var before = f.Snapshot(card);
            var historyStart = CombatManager.Instance.History.Entries.Count();
            f.PendingBeastName = name + "-beast";
            var converted = await BeastForms.Convert(f.Choices, card)
                ?? throw new InvalidOperationException("Native beast replacement did not commit.");
            var afterMaterial = f.Snapshot(card);
            var afterConversion = f.Snapshot(converted);
            var conversionHistory = f.HistorySince(historyStart);
            var beforeDrawEnergy = f.Pcs.Energy;
            if (draw) await CardPileCmd.Draw(f.Choices, 1, f.Player);
            var afterDrawEnergy = f.Pcs.Energy;
            var afterDraw = f.Snapshot(converted);
            var play = await f.Play(converted);
            rows.Add(new { name, before, returnedShape = BeastForms.Shape(converted).ToString(),
                newEntity = !ReferenceEquals(card, converted), afterMaterial, afterConversion, conversionHistory,
                drawCalls = draw ? 1 : 0, beforeDrawEnergy, afterDrawEnergy, afterDraw, play });
        }
        await Row("starter-claw", starter, retain: true);
        await Row("native-bash", f.Combat.CreateCard<Bash>(f.Player));
        await Row("native-defend", f.Combat.CreateCard<DefendIronclad>(f.Player));
        await Row("native-power", f.Combat.CreateCard<Inflame>(f.Player), upgrade: true);

        // Positive control: the same native status class MUST lose energy when not converted.
        var control = f.Combat.CreateCard<VoidCard>(f.Player);
        f.Name(control, "native-void-control");
        await CardPileCmd.Add(control, PileType.Draw, CardPilePosition.Top);
        var controlBefore = f.Pcs.Energy;
        await CardPileCmd.Draw(f.Choices, 1, f.Player);
        var controlAfter = f.Pcs.Energy;
        var controlSnapshot = f.Snapshot(control);
        await CardPileCmd.Add(control, PileType.Exhaust);
        await PlayerCmd.GainEnergy(1, f.Player);
        var controlRestored = f.Pcs.Energy;
        await Row("native-status", f.Combat.CreateCard<VoidCard>(f.Player), draw: true);
        await Row("native-curse", f.Combat.CreateCard<Injury>(f.Player));
        await Row("native-x", f.Combat.CreateCard<Whirlwind>(f.Player));
        return new { rows, voidControl = new { beforeEnergy = controlBefore, afterEnergy = controlAfter,
            restoredEnergy = controlRestored, drawCalls = 1, snapshot = controlSnapshot } };
    }

    private static async Task<object> F02(Fixture f)
    {
        CardModel card = f.Combat.CreateCard<Bludgeon>(f.Player);
        f.Name(card, "native-bludgeon");
        await CardPileCmd.Add(card, PileType.Hand);
        card.AddKeyword(CardKeyword.Retain);
        card.EnergyCost.SetThisTurnOrUntilPlayed(2);
        var before = f.Snapshot(card);
        var historyStart = CombatManager.Instance.History.Entries.Count();
        f.PendingBeastName = "native-bludgeon-beast";
        var material = card;
        var first = await BeastForms.Convert(f.Choices, material)
            ?? throw new InvalidOperationException("Native beast replacement did not commit.");
        card = first;
        var afterMaterial = f.Snapshot(material);
        var afterConversion = f.Snapshot(card);
        var conversionHistory = f.HistorySince(historyStart);
        historyStart = CombatManager.Instance.History.Entries.Count();
        var second = await BeastForms.Convert(f.Choices, card);
        var afterRepeat = f.Snapshot(card);
        var repeatHistory = f.HistorySince(historyStart);
        card.EnergyCost.SetThisTurnOrUntilPlayed(1);
        var afterNewSet = f.Snapshot(card);
        var firstPlay = await f.Play(card);
        await CardPileCmd.Add(card, PileType.Hand);
        var recycled = f.Snapshot(card);
        CardCmd.Upgrade(card);
        var afterUpgrade = f.Snapshot(card);
        BeastForms.SetZeroThisTurnOrUntilPlayed(card);
        var afterZero = f.Snapshot(card);
        var upgradedPlay = await f.Play(card);
        await CardPileCmd.Add(card, PileType.Hand);
        BeastForms.SetZeroThisTurnOrUntilPlayed(card);
        var beforeTurn = f.Snapshot(card);
        await CreatureCmd.GainBlock(f.Player.Creature, 100m, ValueProp.Unpowered, null);
        int roundBefore = f.Combat.RoundNumber, turnBefore = f.Pcs.TurnNumber;
        PlayerCmd.EndTurn(f.Player, canBackOut: false);
        var timeout = System.Diagnostics.Stopwatch.StartNew();
        while (f.Combat.RoundNumber <= roundBefore || f.Combat.CurrentSide != CombatSide.Player || f.Pcs.Phase != PlayerTurnPhase.Play)
        {
            if (timeout.Elapsed > TimeSpan.FromSeconds(20)) throw new TimeoutException("Beast fixture next turn timed out.");
            await ((SceneTree)Engine.GetMainLoop()).ToSignal(Engine.GetMainLoop(), SceneTree.SignalName.ProcessFrame);
        }
        return new { before, firstShape = BeastForms.Shape(first).ToString(), afterMaterial, afterConversion,
            newEntity = !ReferenceEquals(material, first), conversionHistory,
            secondShape = second is null ? "None" : BeastForms.Shape(second).ToString(),
            sameOnRepeat = ReferenceEquals(first, second), repeatHistory, afterRepeat, afterNewSet, firstPlay, recycled, afterUpgrade, afterZero, upgradedPlay, beforeTurn,
            afterTurn = f.Snapshot(card), roundBefore, turnBefore, roundAfter = f.Combat.RoundNumber,
            turnAfter = f.Pcs.TurnNumber, energyAfterTurn = f.Pcs.Energy, hpAfterTurn = f.Player.Creature.CurrentHp };
    }
}
