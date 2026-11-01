using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes;

namespace Volibear;

/// <summary>Coordinates existing finite probes in one native process and isolated profile.</summary>
internal static class NativeVerificationSuite
{
    private static bool started;
    internal static void Install() => CombatManager.Instance.TurnStarted += Start;
    private static void Start(CombatState initial)
    {
        if (started) return;
        started = true;
        CombatManager.Instance.TurnStarted -= Start;
        _ = Run(initial);
    }

    private static async Task Run(CombatState initial)
    {
        string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        int pid = Environment.ProcessId;
        var completed = new List<string>();
        try
        {
            if (string.IsNullOrWhiteSpace(token)) throw new InvalidOperationException("Native suite token missing");
            await NativeAcceptanceRunHost.WaitForQuiet(initial, 1);
            GD.Print("[Volibear] NATIVE_SUITE_BEGIN " + JsonSerializer.Serialize(new { token, pid }));

            CardFaceAcceptanceProbe.Install(subscribe: false);
            await CardFaceAcceptanceProbe.RunBatch(initial,
                Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH") ?? "", managed: true);
            NativeAcceptanceRunHost.RequireClean(); completed.Add("card-faces");

            CardLifecycleAcceptanceProbe.Install(subscribe: false);
            var lifecycle = await NativeAcceptanceRunHost.StartFresh(ModelDb.Encounter<SlimesWeak>());
            await CardLifecycleAcceptanceProbe.RunBatch(lifecycle, managed: true);
            NativeAcceptanceRunHost.RequireClean(); completed.Add("card-lifecycle");

            var presentation = await NativeAcceptanceRunHost.StartFresh(ModelDb.Encounter<SlimesWeak>());
            await PresentationAcceptanceProbe.Run(presentation, managed: true);
            await NativeAcceptanceRunHost.ExitToMainMenu(); completed.Add("presentation");

            SaveLoadContractProbe.Install(start: false);
            await SaveLoadContractProbe.Run(managed: true);
            // Do not enter another room and create a different checkpoint after the
            // restore receipt. The shared host still awaits native cleanup and a frame.
            await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);
            completed.Add("save-load-same-process");

            GD.Print("[Volibear] NATIVE_SUITE_RESULT " + JsonSerializer.Serialize(new {
                schema = 1,token,pid,completed,finished = true,osInput = false,simulatedClicks = false,
                processRestarts = 0,selector = "CardSelectCmd.UseSelector",
                cleanup = NativeAcceptanceRunHost.CleanState(),
                scope = "native-paid-card-faces-lifecycle-presentation-and-checkpoint",
                exclusions = new[] { "live-multiplayer-peers", "physical-input", "human-visual-listening-review", "disk-process-restart" }
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] NATIVE_SUITE_ERROR " + JsonSerializer.Serialize(new { token,pid,completed,error = error.ToString() }));
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
