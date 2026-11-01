using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>Real upgrade-command/engage effects, NOT Orobas dialogue or manual payment acceptance.
/// No production implementation or responder is replaced. External comparator owns the oracle.</summary>
internal static class RelicContractProbe
{
    private static bool started;
    private static readonly Harmony Observer = new("Volibear.RelicGenerationObserver");
    private static Action<CardModel, Player?>? Generated;
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObserveGenerated)).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    [HarmonyPatch(typeof(Hook), nameof(Hook.AfterCardGeneratedForCombat))]
    private static class ObserveGenerated
    {
        // Read-only prefix: the native command has already added the card and history entry.
        private static void Prefix(CardModel card, Player? creator) => Generated?.Invoke(card, creator);
    }
    private static void Start(CombatState state)
    {
        if (started) return;
        started = true;
        _ = Run(state);
    }
    private static void Tackle(Creature enemy)
    {
        var monster = enemy.Monster ?? throw new InvalidOperationException("No native monster");
        var machine = monster.MoveStateMachine ?? throw new InvalidOperationException("No native move state machine");
        if (!machine.States.TryGetValue("TACKLE_MOVE", out var selected) || selected is not MoveState move)
            throw new InvalidOperationException("No native TACKLE_MOVE");
        monster.SetMoveImmediate(move, forceTransition: true);
        if (!ReferenceEquals(monster.NextMove, move)) throw new InvalidOperationException("Native move selection failed");
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_RELIC_CASE");
            if (string.IsNullOrWhiteSpace(token) || variant is not ("RH-starter-turns" or "RH-upgrade-turns" or "RH-starter-death" or "RH-upgrade-death"))
                throw new InvalidOperationException("Missing token or unsupported relic case");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            var player = state.Players.Single();
            var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("No player combat state");
            var owner = player.Creature;
            var enemies = state.Enemies.ToArray();
            if (enemies.Length != 3 || pcs.TurnNumber != 1 || state.RoundNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any())
                throw new InvalidOperationException("Expected fresh three-slime native encounter");
            var first = enemies.Single(e => e.Monster is LeafSlimeS);
            var second = enemies.Single(e => e.Monster is TwigSlimeS);
            if (enemies.Count(e => e.Monster is LeafSlimeM or TwigSlimeM) != 1)
                throw new InvalidOperationException("Expected native medium slime");
            var identities = enemies.Append(owner).ToDictionary(creature => creature,
                creature => creature.CombatId ?? throw new InvalidOperationException("Missing native combat identity"));
            uint Id(Creature creature) => identities[creature];
            var choices = new ThrowingPlayerChoiceContext();
            var cards = pcs.AllPiles.SelectMany(p => p.Cards).Distinct().ToArray();
            var refs = new Dictionary<CardModel, int>(ReferenceEqualityComparer.Instance);
            foreach (var card in cards) refs.Add(card, refs.Count + 1);
            int Ref(CardModel card) => refs.TryGetValue(card, out var id) ? id : throw new InvalidOperationException("Unknown native card identity");
            var cardRows = cards.Select(card => new { cardRef = Ref(card), modelId = card.Id.Entry,
                masterIndex = Array.FindIndex(player.Deck.Cards.ToArray(), c => ReferenceEquals(c, card.DeckVersion)),
                masterModelId = card.DeckVersion?.Id.Entry,
                combatCardIndex = NetCombatCard.FromModel(card).CombatCardIndex,
                sameObject = ReferenceEquals(NetCombatCard.FromModel(card).ToCardModel(), card), ownerId = Id(card.Owner.Creature) }).ToArray();
            var generated = new List<object>();
            bool allowNativeGeneration = false;
            Generated = (card, creator) =>
            {
                // Preserve the medium slime's genuine initial StickyShot, including native status creation.
                var monster = state.Enemies.Select(e => e.Monster).SingleOrDefault(m => m is { IsPerformingMove: true });
                string? move = monster?.NextMove.Id;
                bool sticky = monster is TwigSlimeM && move == "STICKY_SHOT_MOVE" || monster is LeafSlimeM && move == "STICKY_SHOT";
                if (!allowNativeGeneration || state.CurrentSide != CombatSide.Enemy || !sticky || card is not Slimed ||
                    !ReferenceEquals(card.Owner, player) || card.DeckVersion is not null || creator is not null ||
                    card.Pile?.Type != PileType.Discard || refs.ContainsKey(card))
                    throw new InvalidOperationException("Unexpected native generated card/source; not an accepted fixture identity");
                refs.Add(card, refs.Count + 1);
                var net = NetCombatCard.FromModel(card);
                generated.Add(new { cardRef = Ref(card), modelId = card.Id.Entry, type = card.GetType().Name,
                    cardType = card.Type.ToString(), combatCardIndex = net.CombatCardIndex,
                    sameObject = ReferenceEquals(net.ToCardModel(), card), ownerId = Id(card.Owner.Creature),
                    masterModelId = card.DeckVersion?.Id.Entry, masterIndex = Array.FindIndex(player.Deck.Cards.ToArray(), c => ReferenceEquals(c, card.DeckVersion)),
                    sourceEnemy = Id(monster!.Creature), sourceType = monster.GetType().Name, sourceMove = move,
                    pile = card.Pile.Type.ToString(), creatorId = creator is null ? (uint?)null : Id(creator.Creature),
                    round = state.RoundNumber, turn = pcs.TurnNumber, side = state.CurrentSide.ToString() });
            };
            var source = cards.OfType<Volibear_B04>().Single();
            object[] Inventory() => player.Relics.Select(relic => (object)new { type = relic.GetType().Name, modelId = relic.Id.Entry }).ToArray();
            var initialRelics = Inventory();
            if (player.Relics.Count != 1 || player.Relics[0] is not HuntersHeart)
                throw new InvalidOperationException("Initial relic inventory must contain only HuntersHeart");
            object? upgrade = null;
            if (variant.Contains("upgrade", StringComparison.Ordinal))
            {
                var starter = player.Relics[0];
                var touch = (TouchOfOrobas)ModelDb.Relic<TouchOfOrobas>().ToMutable();
                var setupSucceeded = touch.SetupForPlayer(player);
                var selectedStarter = touch.StarterRelic?.Entry;
                var selectedUpgrade = touch.UpgradedRelic?.Entry;
                // The native ancient relic owns its AfterObtained -> RelicCmd.Replace chain.
                await RelicCmd.Obtain(touch, player);
                upgrade = new { setupSucceeded, selectedStarter, selectedUpgrade,
                    originalStillOwned = player.Relics.Contains(starter), inventory = Inventory() };
            }
            foreach (var card in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 100m);
            Tackle(first);
            Tackle(second);
            object Snapshot() => new { round = state.RoundNumber, turn = pcs.TurnNumber, hp = owner.CurrentHp,
                block = owner.Block, hand = pcs.Hand.Cards.Select(Ref).ToArray(),
                draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),
                discard = pcs.DiscardPile.Cards.Select(Ref).ToArray(),
                play = pcs.PlayPile.Cards.Select(Ref).ToArray(), exhaust = pcs.ExhaustPile.Cards.Select(Ref).ToArray() };
            var steps = new List<object>();
            async Task Engage(string label, Creature target)
            {
                var before = Snapshot();
                int offset = CombatManager.Instance.History.Entries.Count();
                var result = await EngageCmd.Perform(choices, target, source);
                var history = CombatManager.Instance.History.Entries.Skip(offset).ToArray();
                steps.Add(new { label, target = Id(target), before, after = Snapshot(),
                    result = new { performed = result.Performed, completed = result.Completed, absorbed = result.Absorbed },
                    draws = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card), modelId = e.Card.Id.Entry, fromHandDraw = e.FromHandDraw }).ToArray(),
                    moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemy = Id(e.Monster.Creature), move = e.Move.Id }).ToArray(),
                    damage = history.OfType<DamageReceivedEntry>().Select(e => new { target = Id(e.Receiver),
                        playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage,
                        blocked = e.Result.BlockedDamage, props = (int)e.Result.Props }).ToArray() });
            }
            object? transition = null;
            bool death = variant.EndsWith("death", StringComparison.Ordinal);
            if (death)
            {
                // Invalid target must not consume the relic's still-pending first-completion award.
                await Engage("invalid-target", owner);
                await PowerCmd.Apply<StrengthPower>(choices, first, 100m, first, null);
                // Real native TACKLE kills the receiver; no completed-engage response is invoked.
                await Engage("receiver-death", first);
            }
            else
            {
                await CreatureCmd.GainBlock(owner, 100m, ValueProp.Unpowered, null);
                await Engage("first", first);
                await Engage("duplicate", first);
                await Engage("second-enemy", second);
                var before = Snapshot();
                int offset = CombatManager.Instance.History.Entries.Count();
                allowNativeGeneration = true;
                PlayerCmd.EndTurn(player, canBackOut: false);
                var timer = System.Diagnostics.Stopwatch.StartNew();
                while (state.RoundNumber < 2 || state.CurrentSide != CombatSide.Player || pcs.Phase != PlayerTurnPhase.Play)
                {
                    if (timer.Elapsed > TimeSpan.FromSeconds(20)) throw new TimeoutException("Native turn transition did not finish");
                    var tree = (SceneTree)Engine.GetMainLoop();
                    await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                }
                var history = CombatManager.Instance.History.Entries.Skip(offset).ToArray();
                allowNativeGeneration = false;
                transition = new { before, after = Snapshot(),
                    generatedHistory = history.OfType<CardGeneratedEntry>().Select(e => new { cardRef = Ref(e.Card), modelId = e.Card.Id.Entry,
                        creatorId = e.Creator is null ? (uint?)null : Id(e.Creator.Creature) }).ToArray(),
                    damage = history.OfType<DamageReceivedEntry>().Select(e => new { target = Id(e.Receiver),
                        playerTarget = ReferenceEquals(e.Receiver, owner), hpLost = e.Result.UnblockedDamage,
                        blocked = e.Result.BlockedDamage, props = (int)e.Result.Props }).ToArray(),
                    draws = history.OfType<CardDrawnEntry>().Select(e => new { cardRef = Ref(e.Card), modelId = e.Card.Id.Entry, fromHandDraw = e.FromHandDraw }).ToArray(),
                    moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => new { enemy = Id(e.Monster.Creature), move = e.Move.Id }).ToArray(),
                    firstNextMove = first.Monster!.NextMove.Id };
                // Test arrangement is separate from the observed native turn transition above.
                Tackle(first);
                await CreatureCmd.SetCurrentHp(owner, 80m);
                await CreatureCmd.GainBlock(owner, 100m, ValueProp.Unpowered, null);
                await Engage("next-turn-first", first);
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing native version");
            GD.Print("[Volibear] RELIC_CONTRACT_RESULT " + JsonSerializer.Serialize(new {
                token, scenario = "relic-contract", variant, completed = true,
                gameVersion = release.Version, gameCommit = release.Commit, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "native-upgrade-chain-effects-not-orobas-dialogue-not-payment",
                character = player.Character.GetType().Name, enemyIds = enemies.Select(Id).ToArray(),
                enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(), playerId = Id(owner),
                cards = cardRows, generated, sourceCardRef = Ref(source), initialRelics, upgrade, finalRelics = Inventory(), steps, transition
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] RELIC_CONTRACT_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { Generated = null; CombatManager.Instance.TurnStarted -= Start; Observer.UnpatchAll(Observer.Id); }
    }
}
