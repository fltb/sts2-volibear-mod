using System;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.TestSupport;

namespace Volibear;

/// <summary>Original full catalog followed by a finite paid face batch in the same process.</summary>
internal static class CatalogFaceSuite
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
    internal static async Task Run(CombatState initial)
    {
        string token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        int pid = System.Environment.ProcessId;
        try
        {
            var release = ReleaseInfoManager.Instance.ReleaseInfo;
            string selection = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH") ?? "";
            var cases = selection.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
            if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") != "catalog-face-suite" ||
                System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_MODE") != "cards" ||
                string.IsNullOrWhiteSpace(token) || cases.Length == 0 || cases.Distinct().Count() != cases.Length ||
                release is null || release.Version != "v0.107.1" || release.Commit != "59260271" || TestMode.IsOn)
                throw new InvalidOperationException("Catalog-face suite requires pinned native cards mode and a unique finite batch");
            await NativeAcceptanceRunHost.WaitForQuiet(initial, 1);
            GD.Print("[Volibear] CATALOG_FACE_BEGIN " + JsonSerializer.Serialize(new {
                schema = 1, token, pid, cases, presentationMode = "cards"
            }));

            // No gameplay pacing or art lease during the original 356 catalog views.
            await PresentationAcceptanceProbe.Run(initial, managed: true);
            await NativeAcceptanceRunHost.ExitToMainMenu();
            NativeAcceptanceRunHost.RequireClean();

            CardFaceAcceptanceProbe.Install(subscribe: false);
            var faces = await NativeAcceptanceRunHost.StartFresh(ModelDb.Encounter<SlimesWeak>(), "VOLIBEARTEST");
            // RunBatch owns its existing scope, per-case fresh runs, actions and exits.
            await CardFaceAcceptanceProbe.RunBatch(faces, selection, managed: true);
            NativeAcceptanceRunHost.RequireClean();
            GD.Print("[Volibear] CATALOG_FACE_RESULT " + JsonSerializer.Serialize(new {
                schema = 1, token, pid, cases, completed = new[] { "presentation", "card-faces" },
                finished = true, processRestarts = 0, cleanup = NativeAcceptanceRunHost.CleanState()
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] CATALOG_FACE_ERROR " + JsonSerializer.Serialize(new { token, pid, error = error.ToString() }));
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }
}
