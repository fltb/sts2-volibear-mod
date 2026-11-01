using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>
/// Isolated real-engine effects fixture. E01/E02 call the production command directly;
/// B04 uses AutoPlay, not ordinary input/payment. Native monster delegates are never replaced.
/// </summary>
internal static class EngageContractProbe
{
    private static bool started;
    private static Creature? receiver;
    private static readonly List<EngageCmd.Result> Receipts = new();
    private static readonly List<decimal> BlockReceipts = new();
    private static readonly Harmony Observer = new("Volibear.EngageContractObserver");

    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObserveResult)).Patch();
        Observer.CreateClassProcessor(typeof(ObserveBlock)).Patch();
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }

    private static void OnTurnStarted(CombatState state)
    {
        if (started) return;
        started = true;
        _ = Run(state);
    }

    private static void SelectNativeTackle(Creature enemy)
    {
        var monster = enemy.Monster ?? throw new InvalidOperationException("Fixture enemy lacks model");
        var machine = monster.MoveStateMachine ?? throw new InvalidOperationException("No native move machine");
        if (machine.States["TACKLE_MOVE"] is not MoveState tackle)
            throw new InvalidOperationException("Missing native TACKLE_MOVE");
        monster.SetMoveImmediate(tackle, forceTransition: true);
        if (!ReferenceEquals(monster.NextMove, tackle))
            throw new InvalidOperationException("Native move fixture was not selected");
    }

    private static int Moves(Creature enemy) => CombatManager.Instance.History.Entries
        .OfType<MonsterPerformedMoveEntry>().Count(entry => ReferenceEquals(entry.Monster, enemy.Monster));

    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ENGAGE_CASE") ?? "e01";
            if (string.IsNullOrWhiteSpace(token) || variant is not ("e01" or "e02" or "b04"))
                throw new InvalidOperationException("Invalid engage fixture token/case");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Real-engine fixture cannot use TestMode");
            var player = state.Players.Single();
            var combat = player.PlayerCombatState ?? throw new InvalidOperationException("Missing player combat state");
            receiver = player.Creature;
            if (receiver.Block != 0 || receiver.CurrentHp != 80 || combat.TurnNumber != 1)
                throw new InvalidOperationException("Expected fresh 80-HP unblocked first player turn");
            if (player.Relics.OfType<Content.HuntersHeart>().Count() != 1)
                throw new InvalidOperationException("Expected exactly one production starter relic");
            var enemies = state.Enemies.ToArray();
            var target = enemies.Single(enemy => enemy.Monster is LeafSlimeS);
            var second = enemies.Single(enemy => enemy.Monster is TwigSlimeS);
            foreach (var enemy in enemies)
                await CreatureCmd.SetMaxAndCurrentHp(enemy, 50m);
            var choices = new ThrowingPlayerChoiceContext();
            await PowerCmd.Apply<StrengthPower>(choices, target, 5m, target, null);
            SelectNativeTackle(target);
            SelectNativeTackle(second);
            var card = combat.Hand.Cards.Concat(PileType.Draw.GetPile(player).Cards)
                .OfType<Content.Volibear_B04>().Single();
            if (!combat.Hand.Cards.Contains(card)) await CardPileCmd.Add(card, combat.Hand);
            int initialBlock = variant == "e01" ? 5 : variant == "e02" ? 10 : 0;
            if (initialBlock > 0)
                await CreatureCmd.GainBlock(receiver, initialBlock, ValueProp.Unpowered, null);
            Receipts.Clear();
            BlockReceipts.Clear();
            int roundBefore = state.RoundNumber;
            int turnBefore = combat.TurnNumber;
            int handBefore = combat.Hand.Cards.Count;
            int hpBefore = receiver.CurrentHp;
            int blockBefore = (int)receiver.Block;
            int enemyHpBefore = target.CurrentHp;
            if (variant == "b04") await CardCmd.AutoPlay(choices, card, target);
            else await EngageCmd.Perform(choices, target, card);
            if (Receipts.Count != 1) throw new InvalidOperationException("Missing unique production engage receipt");
            var first = Receipts[0];
            var firstBlockReceipts = BlockReceipts.ToArray();
            int hpAfter = receiver.CurrentHp;
            int blockAfter = (int)receiver.Block;
            int enemyHpAfter = target.CurrentHp;
            int handAfter = combat.Hand.Cards.Count;
            int movesAfter = Moves(target);
            int firstHandDraw = handAfter - handBefore + (variant == "b04" ? 1 : 0);

            int blocksBeforeDuplicate = BlockReceipts.Count;
            var duplicate = await EngageCmd.Perform(choices, target, card);
            int duplicateHp = receiver.CurrentHp;
            int duplicateBlock = (int)receiver.Block;
            int duplicateHand = combat.Hand.Cards.Count;
            int duplicateMoves = Moves(target);
            int duplicateDamageReceipts = BlockReceipts.Count - blocksBeforeDuplicate;

            // A second actual enemy completion in the same player turn must not award another draw.
            await CreatureCmd.GainBlock(receiver, 20m, ValueProp.Unpowered, null);
            int secondHandBefore = combat.Hand.Cards.Count;
            var secondResult = await EngageCmd.Perform(choices, second, card);
            int secondHandAfter = combat.Hand.Cards.Count;
            PlayerCmd.EndTurn(player, canBackOut: false);
            var deadline = System.Diagnostics.Stopwatch.StartNew();
            while (state.RoundNumber <= roundBefore || state.CurrentSide != CombatSide.Player
                   || combat.Phase != PlayerTurnPhase.Play)
            {
                if (deadline.Elapsed > TimeSpan.FromSeconds(20))
                    throw new TimeoutException("Native enemy phase did not finish");
                var tree = (SceneTree)Engine.GetMainLoop();
                await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            }
            int roundAfter = state.RoundNumber;
            int turnAfter = combat.TurnNumber;
            var phaseMoveCounts = enemies.Select(Moves).ToArray();
            var phaseMonsters = enemies.Select(enemy => enemy.Monster!.GetType().Name).ToArray();
            string nextNativeMove = target.Monster!.NextMove.Id;
            // Record the natural transition before arranging the second-turn attack fixture.
            // LeafSlimeS's CannotRepeat transition after TACKLE must produce GOOP.
            SelectNativeTackle(target);
            await CreatureCmd.SetCurrentHp(receiver, 80m);
            if (receiver.Block != 0) throw new InvalidOperationException("Native player turn did not clear block");
            await CreatureCmd.GainBlock(receiver, 10m, ValueProp.Unpowered, null);
            int nextHandBefore = combat.Hand.Cards.Count;
            var next = await EngageCmd.Perform(choices, target, card);
            int nextHandAfter = combat.Hand.Cards.Count;
            int nextHp = receiver.CurrentHp;
            int nextBlock = (int)receiver.Block;
            int nextMoves = Moves(target);
            int expectedAbsorbed = variant == "e01" ? 5 : 8;
            int expectedHp = variant == "e01" ? 77 : 80;
            int expectedBlock = variant == "e02" ? 2 : 0;
            bool passed = first is { Performed: true, Completed: true } && first.Absorbed == expectedAbsorbed
                && hpAfter == expectedHp && blockAfter == expectedBlock && firstHandDraw == 1
                && firstBlockReceipts.SequenceEqual(new decimal[] { expectedAbsorbed })
                && enemyHpBefore - enemyHpAfter == (variant == "b04" ? 6 : 0)
                && duplicate is { Performed: false, Completed: false, Absorbed: 0 }
                && duplicateHp == hpAfter && duplicateBlock == blockAfter && duplicateHand == handAfter
                && movesAfter == 1 && duplicateMoves == 1 && duplicateDamageReceipts == 0
                && secondResult is { Performed: true, Completed: true, Absorbed: 4 }
                && secondHandAfter == secondHandBefore && phaseMoveCounts.All(count => count == 1)
                && nextNativeMove == "GOOP_MOVE" && roundAfter == roundBefore + 1 && turnAfter == turnBefore + 1
                && next is { Performed: true, Completed: true, Absorbed: 8 }
                && nextHandAfter == nextHandBefore + 1 && nextHp == 80 && nextBlock == 2 && nextMoves == 2;
            GD.Print("[Volibear] ENGAGE_CONTRACT_RESULT " + System.Text.Json.JsonSerializer.Serialize(new
            {
                token, scenario = "engage-contract", variant, passed,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                acceptance = "effect-only-not-payment",
                api = variant == "b04" ? "CardCmd.AutoPlay:Volibear_B04" : "Core.EngageCmd.Perform",
                enemy = "LeafSlimeS", nativeMove = "TACKLE_MOVE", strength = target.GetPower<StrengthPower>()?.Amount,
                fixtureEnemyHp = 50, hpBefore, blockBefore, hpAfter, blockAfter, enemyHpBefore, enemyHpAfter,
                handBefore, handAfter, firstHandDraw, first, firstBlockReceipts, movesAfter,
                duplicate, duplicateHp, duplicateBlock, duplicateHand, duplicateMoves, duplicateDamageReceipts,
                secondResult, secondHandBefore, secondHandAfter,
                roundBefore, roundAfter, turnBefore, turnAfter, phaseMonsters, phaseMoveCounts, nextNativeMove,
                next, nextHandBefore, nextHandAfter, nextHp, nextBlock, nextMoves
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(passed ? 0 : 2);
        }
        catch (Exception exception)
        {
            GD.PrintErr("[Volibear] ENGAGE_CONTRACT_ERROR " + exception);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
            Observer.UnpatchAll(Observer.Id);
            receiver = null;
        }
    }

    // Read-only observers preserve the actual result/exception and never replace native move logic.
    [HarmonyPatch(typeof(EngageCmd), nameof(EngageCmd.Perform))]
    private static class ObserveResult
    {
        private static void Postfix(ref Task<EngageCmd.Result> __result) => __result = Record(__result);
        private static async Task<EngageCmd.Result> Record(Task<EngageCmd.Result> task)
        {
            var result = await task;
            Receipts.Add(result);
            return result;
        }
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.DamageBlockInternal))]
    private static class ObserveBlock
    {
        private static void Postfix(Creature __instance, decimal __result)
        {
            if (ReferenceEquals(__instance, receiver)) BlockReceipts.Add(__result);
        }
    }
}
