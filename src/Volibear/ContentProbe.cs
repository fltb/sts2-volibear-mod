using System;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

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

    private static async Task CaptureWindow(string filename)
    {
        if (DisplayServer.GetName() == "headless") return;
        var directory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ARTIFACT_DIR")
            ?? throw new InvalidOperationException("Window capture requires isolated artifact path");
        var game = MegaCrit.Sts2.Core.Nodes.NGame.Instance!;
        await game.ToSignal(game.GetTree().CreateTimer(0.5), SceneTreeTimer.SignalName.Timeout);
        await game.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        using var image = game.GetViewport().GetTexture().GetImage();
        var path = System.IO.Path.Combine(directory, filename);
        if (image.SavePng(path) != Error.Ok) throw new InvalidOperationException("Screenshot failed: " + path);
        GD.Print("[Volibear] WINDOW_CAPTURE " + path);
    }

    private static async Task Run(CombatState state)
    {
        try
        {
            if (!Content.VolibearLoc.Installed) Content.VolibearLoc.Install();
            var player = state.Players.Single();
            var combat = player.PlayerCombatState
                ?? throw new InvalidOperationException("Content fixture requires PlayerCombatState");
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            if (string.IsNullOrWhiteSpace(token))
                throw new InvalidOperationException("Content fixture requires a current run token");
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Content fixture must execute with TestMode disabled");

            // Arrange existing starting-deck combat entities, not generated replacements.
            // CardPileCmd runs normal pile movement; AutoPlay below measures effects only.
            var startingCards = combat.Hand.Cards.Concat(PileType.Draw.GetPile(player).Cards).ToList();
            CardModel attack = startingCards.OfType<Content.Volibear_B01>().First();
            CardModel defend = startingCards.OfType<Content.Volibear_B02>().First();
            CardModel claw = startingCards.OfType<Content.Volibear_B03>().Single();
            var cards = new[] { attack, defend, claw };
            foreach (var card in cards)
            {
                if (!combat.Hand.Cards.Contains(card))
                    await CardPileCmd.Add(card, combat.Hand);
                if (!combat.Hand.Cards.Contains(card))
                    throw new InvalidOperationException("Failed to arrange content card in hand");
            }
            await CaptureWindow("content-before.png");
            var enemies = state.Enemies.ToList();
            if (enemies.Count < 2 || enemies.Any(enemy => enemy.Block != 0) || player.Creature.Block != 0)
                throw new InvalidOperationException("Content fixture needs unblocked SlimesWeak targets");
            var originalEnemyHp = enemies.Select(enemy => enemy.CurrentHp).ToArray();
            foreach (var enemy in enemies)
                await CreatureCmd.SetMaxAndCurrentHp(enemy, 50m);
            if (enemies.Any(enemy => enemy.CurrentHp != 50))
                throw new InvalidOperationException("Content fixture HP normalization failed");
            // Explicit HP fixture avoids random starting HP and overkill truncating measurements.
            var attackTarget = enemies.Last();
            int attackBefore = attackTarget.CurrentHp;
            await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), attack, attackTarget);
            int attackAfter = attackTarget.CurrentHp;
            int attackDelta = attackBefore - attackAfter;

            int blockBefore = (int)player.Creature.Block;
            await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), defend, player.Creature);
            int blockAfter = (int)player.Creature.Block;
            int blockGain = blockAfter - blockBefore;

            var enemyBefore = enemies.Select(enemy => enemy.CurrentHp).ToArray();
            await CardCmd.AutoPlay(new ThrowingPlayerChoiceContext(), claw, enemies[0]);
            var enemyAfter = enemies.Select(enemy => enemy.CurrentHp).ToArray();
            var lightningDeltas = enemyBefore.Zip(enemyAfter, (before, after) => before - after).ToArray();

            var result = new
            {
                token, scenario = "content", api = "CardCmd.AutoPlay",
                acceptance = "effect-only-not-payment",
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                cards = cards.Select(card => card.GetType().Name).ToArray(),
                character = player.Character.GetType().Name,
                startingHp = player.Character.StartingHp,
                deckSize = player.Deck.Cards.Count(),
                attackBefore, attackAfter, attackDelta,
                blockBefore, blockAfter, blockGain,
                enemyBefore, enemyAfter, enemyCount = enemies.Count,
                originalEnemyHp, fixtureEnemyHp = 50,
                fixtureApi = "CreatureCmd.SetMaxAndCurrentHp;CardPileCmd.Add",
                enemyDeltas = lightningDeltas,
                played = cards.Length,
                passed = attackDelta == 6 && blockGain == 5 && lightningDeltas.Length == state.Enemies.Count
                         && lightningDeltas.Length >= 2 && lightningDeltas[0] == 11
                         && lightningDeltas.Skip(1).All(delta => delta == 3)
                         && enemyAfter.All(hp => hp > 0) && attackAfter > 0
                         && player.Character.StartingHp == 80 && player.Deck.Cards.Count() == 10,
            };
            await CaptureWindow("content-after.png");
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
        finally
        {
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
