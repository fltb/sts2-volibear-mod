using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Volibear.Core;
using Volibear.Presentation;
using MegaCrit.Sts2.Core.Entities.Players;

namespace Volibear;

/// <summary>One short real-combat visual fixture. PNG pixels are checked independently;
/// model/node existence is not evidence that the ring was actually drawn.</summary>
internal static class DomainVisualDevelopmentProbe
{
    private static bool installed, started;
    private static SceneTree Tree => (SceneTree)Engine.GetMainLoop();
    internal static void Install()
    {
        if (installed) return;
        if (Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") != "domain-visual")
            throw new InvalidOperationException("Dedicated domain-visual scenario required");
        installed = true;
        CombatManager.Instance.TurnStarted += OnTurn;
    }
    private static void OnTurn(CombatState state)
    {
        if (started) return;
        started = true;
        CombatManager.Instance.TurnStarted -= OnTurn;
        _ = Run(state);
    }
    private static void Need(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
    private static async Task Pause(double seconds)
    {
        var clock = Stopwatch.StartNew();
        while (clock.Elapsed.TotalSeconds < seconds) await Tree.ToSignal(Tree, SceneTree.SignalName.ProcessFrame);
    }
    private static async Task<object> Capture(string phase, string directory, NCreature view, Stopwatch clock)
    {
        await Tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        using var image = Tree.Root.GetTexture().GetImage();
        Need(image is not null && !image.IsEmpty(), "Actual viewport image missing");
        var viewport = Tree.Root.GetVisibleRect().Size;
        var ratio = new Vector2(image!.GetWidth() / viewport.X, image.GetHeight() / viewport.Y);
        var transform = view.Visuals.GetGlobalTransformWithCanvas();
        var foot = transform * new Vector2(0, -5);
        var center = foot * ratio;
        float rx = (((transform * new Vector2(DomainStormRing.Radius, -5)) - foot) * ratio).Length();
        float ry = (((transform * new Vector2(0, DomainStormRing.Radius * .24f - 5)) - foot) * ratio).Length();
        Need(rx > 20 && ry > 5 && center.X - rx * 1.3f >= 0 && center.X + rx * 1.3f < image.GetWidth() &&
            center.Y - ry * 1.3f >= 0 && center.Y + ry * 1.3f < image.GetHeight(), "Entire foot-ring pixel region must be on screen");
        var path = phase + ".png";
        Need(!File.Exists(Path.Combine(directory, path)), "Refuse to overwrite visual evidence");
        Need(image.SavePng(Path.Combine(directory, path)) == Error.Ok, "Viewport PNG write failed");
        return new { phase, path, width = image.GetWidth(), height = image.GetHeight(), at = clock.Elapsed.TotalSeconds,
            origin = "native-viewport", center = new { x = center.X, y = center.Y }, radius = new { x = rx, y = ry },
            domain = view.Entity.GetPower<DomainPower>() is not null };
    }
    private static IEnumerable<Node> Walk(Node node)
    {
        yield return node;
        foreach (var child in node.GetChildren()) foreach (var nested in Walk(child)) yield return nested;
    }
    private static async Task<object> CaptureEnergy(string phase, string directory, Player player, Stopwatch clock)
    {
        await Tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        var counter = Walk(NRun.Instance!).OfType<NEnergyCounter>().Single();
        Need(counter.IsVisibleInTree(), "Actual native energy counter must be visible");
        using var image = Tree.Root.GetTexture().GetImage();
        Need(image is not null && !image.IsEmpty(), "Actual energy viewport missing");
        var viewport = Tree.Root.GetVisibleRect().Size;
        var ratio = new Vector2(image!.GetWidth() / viewport.X, image.GetHeight() / viewport.Y);
        var transform = counter.GetGlobalTransformWithCanvas();
        var first = transform.Origin * ratio;
        var last = (transform * counter.Size) * ratio;
        Need(last.X > first.X && last.Y > first.Y && first.X >= 0 && first.Y >= 0 && last.X <= image.GetWidth() && last.Y <= image.GetHeight(), "Energy region must be inside actual viewport");
        string path = phase + ".png";
        Need(!File.Exists(Path.Combine(directory, path)), "Refuse to overwrite energy image");
        Need(image.SavePng(Path.Combine(directory, path)) == Error.Ok, "Energy PNG write failed");
        var script = counter.GetNode<Control>("Layers/RotationLayers/StormRing");
        return new { phase, path, width = image.GetWidth(), height = image.GetHeight(), origin = "native-viewport", at = clock.Elapsed.TotalSeconds,
            energy = player.PlayerCombatState!.Energy, maxEnergy = player.PlayerCombatState.MaxEnergy,
            rect = new { x = first.X, y = first.Y, width = last.X - first.X, height = last.Y - first.Y },
            script = new { node = script.GetPath().ToString(), hasValue = script.Get("_has_value").AsBool(),
                energy = script.Get("_energy_value").AsInt32(), pulse = script.Get("_pulse").AsDouble(), phase = script.Get("_phase").AsDouble() } };
    }
    private static async Task Run(CombatState state)
    {
        string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        var frames = new List<object>(); var energyFrames = new List<object>(); var clock = Stopwatch.StartNew();
        NCreature? view = null; Vector2 original = default; Tween? movement = null;
        try
        {
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            Need(token.Length > 0 && !MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn && release.Version == global::Volibear.Core.SupportedGameBuild.Version && release.Commit == global::Volibear.Core.SupportedGameBuild.Commit, "Pinned real-game fixture required");
            string directory = Path.GetFullPath(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_VISUAL_OUTPUT")
                ?? throw new InvalidOperationException("Missing isolated visual output directory"));
            Directory.CreateDirectory(directory);
            await NativeAcceptanceRunHost.WaitForQuiet(state, 1);
            var owner = state.Players.Single().Creature;
            view = NCombatRoom.Instance!.GetCreatureNode(owner)!;
            Need(view is not null && owner.GetPower<DomainPower>() is null, "Fresh real character without domain required");
            original = view!.Position;
            await Pause(.5);
            frames.Add(await Capture("before", directory, view, clock));
            await PowerCmd.Apply<DomainPower>(new ThrowingPlayerChoiceContext(), owner, 5, owner, null);
            await Pause(.35);
            frames.Add(await Capture("entered", directory, view, clock));
            await Pause(1.0);
            frames.Add(await Capture("sustained", directory, view, clock));
            // Explicit visual fixture movement of the actual actor, not synthetic input,
            // a simulated screenshot, or a replacement of the domain's follow logic.
            var destination = original + new Vector2(220, 0);
            movement = view.CreateTween();
            movement.TweenProperty(view, "position", destination, .6);
            await Pause(.8);
            Need(view.Position.DistanceTo(destination) < 1, "Actor fixture movement must really finish");
            frames.Add(await Capture("moved", directory, view, clock));
            await PowerCmd.Remove<DomainPower>(owner);
            // The authored domain_exit VFX lasts 30 frames at 24 fps (1.25s).
            // Compare after that legitimate transition, not during its blue flash.
            await Pause(1.4);
            frames.Add(await Capture("exited", directory, view, clock));
            var player = state.Players.Single();
            await PlayerCmd.SetEnergy(0, player);
            await Pause(.5);
            energyFrames.Add(await CaptureEnergy("energy-empty", directory, player, clock));
            await PlayerCmd.SetEnergy(player.PlayerCombatState!.MaxEnergy, player);
            await Pause(.5);
            energyFrames.Add(await CaptureEnergy("energy-full", directory, player, clock));
            Need(clock.Elapsed.TotalSeconds < 55, "Short visual fixture exceeded its budget");
            GD.Print("[Volibear] DOMAIN_VISUAL_RESULT " + JsonSerializer.Serialize(new { schema = 1, token, scenario = "domain-visual",
                fixture = "single-combat-power-command-actor-tween", version = release.Version, commit = release.Commit,
                testMode = false, syntheticInput = false, frames, energyFrames, elapsed = clock.Elapsed.TotalSeconds }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); Tree.Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_VISUAL_ERROR " + JsonSerializer.Serialize(new { token, frames, energyFrames, error = error.ToString() }));
            Tree.Quit(2);
        }
        finally
        {
            movement?.Kill();
            if (view is not null && GodotObject.IsInstanceValid(view)) view.Position = original;
            CombatManager.Instance.TurnStarted -= OnTurn;
        }
    }
}
