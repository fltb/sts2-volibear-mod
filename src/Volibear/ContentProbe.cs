using System;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

namespace Volibear;

/// <summary>
/// Development probe: starts a Volibear run and plays the character's own cards in a real combat,
/// measuring the actual state change instead of trusting that the code compiled.
/// </summary>
internal static class ContentProbe
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
            if (!Content.VolibearLoc.Installed) Content.VolibearLoc.Install();
            var player = state.Players.Single();
            var handCards = player.PlayerCombatState.Hand.Cards.ToList();
            GD.Print($"[Volibear] PROBE hand={string.Join(",", handCards.Select(c => c.GetType().Name))}");

            var target = state.Enemies.First();
            int attackDelta = -1, blockGain = -1;
            var lightningDeltas = Array.Empty<int>();

            var attack = handCards.FirstOrDefault(c => c is Content.Volibear_B01);
            if (attack is not null)
            {
                int before = target.CurrentHp;
                await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), attack, target);
                attackDelta = before - target.CurrentHp;
            }

            var defend = handCards.FirstOrDefault(c => c is Content.Volibear_B02);
            if (defend is not null)
            {
                int blockBefore = (int)player.Creature.Block;
                await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), defend, player.Creature);
                blockGain = (int)player.Creature.Block - blockBefore;
            }

            var claw = handCards.FirstOrDefault(c => c is Content.Volibear_B03);
            if (claw is not null)
            {
                var enemies = state.Enemies.ToList();
                var before = enemies.Select(e => e.CurrentHp).ToArray();
                await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), claw, target);
                lightningDeltas = before.Zip(enemies.Select(e => e.CurrentHp), (b, a) => b - a).ToArray();
            }

            var result = new
            {
                character = player.Character.GetType().Name,
                startingHp = player.Character.StartingHp,
                deckSize = player.Deck.Cards.Count(),
                handSize = handCards.Count,
                attackDelta,
                blockGain,
                enemyDeltas = lightningDeltas,
                played = new[] { attack, defend, claw }.Count(c => c is not null),
                passed = attackDelta == 6 && blockGain == 5 && lightningDeltas.Length == state.Enemies.Count
                         && lightningDeltas.Length > 0 && lightningDeltas[0] == 11
                         && lightningDeltas.Skip(1).All(delta => delta == 3),
            };
            GD.Print("[Volibear] CONTENT_RESULT " + JsonSerializer.Serialize(result));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"));
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(result.passed ? 0 : 2);
        }
        catch (Exception exception)
        {
            GD.PrintErr("[Volibear] CONTENT_PROBE_ERROR " + exception);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
