using System;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear;

internal static class BaselineDriver
{
    private static bool started;

    public static void Install() => CombatManager.Instance.TurnStarted += OnTurnStarted;

    private static void OnTurnStarted(CombatState state)
    {
        if (started) return;
        started = true;
        _ = Run(state);
    }

    private static async Task Run(CombatState state)
    {
        try
        {
            var player = state.Players.Single();
            var target = state.Enemies.First();
            int before = player.Creature.CurrentHp;
            var attack = await DamageCmd.Attack(6m).FromMonster(target.Monster ?? throw new InvalidOperationException("Enemy lacks monster model"))
                .WithHitCount(1).Execute(new ThrowingPlayerChoiceContext());
            var results = attack.Results.SelectMany(hit => hit).ToList();
            int after = player.Creature.CurrentHp;
            bool passed = results.Count == 1 && results[0].Receiver == player.Creature
                && results[0].BlockedDamage == 0 && results[0].UnblockedDamage == 6
                && after == before - 6;
            var strike = state.CreateCard<MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad>(player);
            bool engageEnabled = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ENGAGE") == "1";
            if (engageEnabled)
            {
                await CreatureCmd.GainBlock(player.Creature, 30m, ValueProp.Unpowered, null);
                EngageCardProbe.Selected = strike;
                EngageCardProbe.State = state;
                new HarmonyLib.Harmony("Volibear.EngageCardProbe").CreateClassProcessor(typeof(EngageCardProbe)).Patch();
            }
            int cardTargetBefore = target.CurrentHp;
            await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), strike, target);
            int cardTargetAfter = target.CurrentHp;
            passed &= cardTargetBefore - cardTargetAfter == (engageEnabled ? 7 : 6);
            var engage = EngageCardProbe.First;
            var duplicate = EngageCardProbe.Duplicate;
            if (engageEnabled)
            {
                passed &= engage is { Performed: true, Completed: true, Absorbed: 3 }
                    && duplicate is { Performed: false, Completed: false, Absorbed: 0 }
                    && player.Creature.CurrentHp == after
                    && EngageCardProbe.Order.SequenceEqual(new[] { "pre-effect-finished", "enemy-action-finished",
                        "completion-response", "duplicate-rejected", "remaining-card-effect" })
                    && EngageCardProbe.Responses == 1 && EngageCardProbe.BlockBeforeResponse == 27
                    && EngageCardProbe.BlockAfterResponse == 30 && EngageCardProbe.FollowupDamage == 1;
            }
            int roundBefore = state.RoundNumber;
            PlayerCmd.EndTurn(player, canBackOut: false);
            var deadline = System.Diagnostics.Stopwatch.StartNew();
            while (state.RoundNumber <= roundBefore || state.CurrentSide != CombatSide.Player)
            {
                if (deadline.Elapsed > TimeSpan.FromSeconds(20))
                    throw new TimeoutException("Native enemy turn did not advance to the next player round");
                await ((SceneTree)Engine.GetMainLoop()).ToSignal(
                    (SceneTree)Engine.GetMainLoop(), SceneTree.SignalName.ProcessFrame);
            }
            var moves = CombatManager.Instance.History.Entries
                .OfType<MegaCrit.Sts2.Core.Combat.History.Entries.MonsterPerformedMoveEntry>().ToList();
            int targetMoveCount = moves.Count(entry => ReferenceEquals(entry.Monster, target.Monster));
            var moveHistory = moves.Select(entry => new { monster = entry.Monster.Id.Entry, move = entry.Move.Id }).ToArray();
            passed &= targetMoveCount == 1 && moves.Count == state.Enemies.Count();
            if (engageEnabled) passed &= EngagePrototype.SkippedActions == 1;
            GD.Print("[Volibear] BASELINE_RESULT " + System.Text.Json.JsonSerializer.Serialize(new {
                scenario = "baseline", token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"),
                passed, before, after, resultCount = results.Count,
                engageOrder = EngageCardProbe.Order, engageEnabled, engage, duplicate, skippedActions = EngagePrototype.SkippedActions,
                responseCount = EngageCardProbe.Responses, responseBlockBefore = EngageCardProbe.BlockBeforeResponse,
                responseBlockAfter = EngageCardProbe.BlockAfterResponse, followupDamage = EngageCardProbe.FollowupDamage,
                targetMoveCount, moveHistory,
                roundBefore, roundAfter = state.RoundNumber,
                cardApi = "CardCmd.AutoPlay:StrikeIronclad", cardTargetBefore, cardTargetAfter,
                api = "DamageCmd.Attack", testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn
            }));
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
            var tree = (SceneTree)Engine.GetMainLoop();
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"));
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            tree.Quit(passed ? 0 : 2);
        }
        catch (Exception exception)
        {
            GD.PrintErr("[Volibear] BASELINE_ERROR " + exception);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
