using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Ancients;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.GameOverScreen;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using Volibear.Content;
using Volibear.Presentation;

namespace Volibear;

/// <summary>Two isolated event-room fixtures, not a completed three-act gameplay run.</summary>
internal static class ArchitectEndingAcceptanceProbe
{
    private static int victoryCalls, lossCalls;
    private static SerializableRun? victorySnapshot;
    private static bool observing;
    private static bool installed, started;
    internal static void Install()
    {
        if (installed) return;
        Need(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "architect-ending", "Dedicated architect-ending scenario required");
        installed = true;
        CombatManager.Instance.TurnStarted += OnTurn;
    }
    private static void OnTurn(CombatState state)
    {
        if (started) return;
        started = true;
        CombatManager.Instance.TurnStarted -= OnTurn;
        _ = RunStandalone(state);
    }
    private static async Task RunStandalone(CombatState initial)
    {
        string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        try
        {
            await NativeAcceptanceRunHost.WaitForQuiet(initial, 1);
            await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);
            // The focused developer batch reuses this process for self-debuff and both endings.
            await DomainSuppressionAcceptanceProbe.RunManaged("self");
            await RunManaged();
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] ARCHITECT_ENDING_ERROR " + JsonSerializer.Serialize(new { token, error = error.ToString() }));
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { CombatManager.Instance.TurnStarted -= OnTurn; }
    }
    private static void Recorded(bool isVictory, SerializableRun __result)
    {
        if (!observing) return;
        if (isVictory) { victoryCalls++; victorySnapshot = __result; } else lossCalls++;
    }
    private static void Need(bool ok, string label) { if (!ok) throw new InvalidOperationException(label); }
    private static async Task Until(Func<bool> predicate)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        var tree = NGame.Instance!.GetTree();
        while (!predicate())
        {
            if (clock.Elapsed > TimeSpan.FromSeconds(60)) throw new TimeoutException("Architect native event/ending did not complete");
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    internal static async Task RunManaged()
    {
        string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
        Need(token.Length > 0 && !MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, "isolated real game token required");
        var release = ReleaseInfoManager.Instance.ReleaseInfo!;
        Need(release.Version == global::Volibear.Core.SupportedGameBuild.Version && release.Commit == global::Volibear.Core.SupportedGameBuild.Commit, "locked native version required");
        NativeAcceptanceRunHost.RequireClean();
        var observer = new Harmony("Volibear.Tests.ArchitectEnding.NativeObservation");
        observer.Patch(AccessTools.Method(typeof(RunManager), nameof(RunManager.OnEnded)), postfix: new(typeof(ArchitectEndingAcceptanceProbe), nameof(Recorded)));
        var rows = new List<object>();
        try
        {
            foreach (bool bear in new[] { true, false })
            {
                CharacterModel character = bear ? ModelDb.Character<VolibearCharacter>() : ModelDb.Character<Ironclad>();
                SaveManager.Instance.Progress.GetOrCreateCharacterStats(character.Id);
                await NGame.Instance!.StartNewSingleplayerRun(character, shouldSave: true, ActModel.GetDefaultList().ToArray(),
                    Array.Empty<ModifierModel>(), "volibear-architect-ending-" + (bear ? "bear" : "stock"), GameMode.Standard, ascensionLevel: 0);
                var manager = RunManager.Instance; var run = manager.DebugOnlyGetState()!;
                // Keep the native previous-room save so the Architect save has its normal backup.
                await SaveManager.Instance.SaveRun(null);
                await manager.SetActInternal(run.Acts.Count - 1);
                var room = (EventRoom)await manager.EnterRoomDebug(RoomType.Event, model: ModelDb.Event<TheArchitect>(), showTransition: false);
                var story = (TheArchitect)room.LocalMutableEvent;
                await Until(() => story.CurrentOptions.Count == 1 && NCombatRoom.Instance?.GetCreatureNode(run.Players.Single().Creature) is not null);
                await SaveManager.Instance.SaveRun(null);
                var player = run.Players.Single(); var creature = player.Creature;
                var node = NCombatRoom.Instance!.GetCreatureNode(creature)!;
                var body = bear ? node.Visuals.GetNode<Node2D>("Visuals") : null;
                float scaleBefore = body?.Scale.X ?? 1f;
                int hpBefore = creature.CurrentHp, winsBefore = SaveManager.Instance.Progress.Wins;
                bool saveBefore = SaveManager.Instance.HasRunSave;
                Need(hpBefore > 0 && saveBefore && !run.IsGameOver, "native living saved run before ending");
                int deaths = 0, domainEntries = 0;
                void Died(Creature c) { if (ReferenceEquals(c, creature)) deaths++; }
                void Entered(Creature c) { if (ReferenceEquals(c, creature)) domainEntries++; }
                creature.Died += Died; VolibearArchitectEnding.DomainEntered += Entered;
                victoryCalls = lossCalls = 0; victorySnapshot = null; observing = true;
                int options = 0;
                try
                {
                    var dialogue = (AncientDialogue)AccessTools.Property(typeof(TheArchitect), "Dialogue").GetValue(story)!;
                    Need(dialogue.Lines.Count is > 0 and <= 12, "bounded real native dialogue");
                    for (; options < dialogue.Lines.Count; options++)
                    {
                        await Until(() => story.CurrentOptions.Count == 1);
                        manager.EventSynchronizer.ChooseLocalOption(0);
                        await manager.EventSynchronizer.AwaitPendingOptionTasks();
                    }
                    await Until(() => NOverlayStack.Instance?.Peek() is NGameOverScreen);
                    var screen = (NGameOverScreen)NOverlayStack.Instance!.Peek()!;
                    var screenSnapshot = AccessTools.Field(typeof(NGameOverScreen), "_serializableRun").GetValue(screen);
                    var domain = VolibearPresentationBridge.ArchitectDomainVisual(creature);
                    var sprite = bear ? body!.GetNode<AnimatedSprite2D>("AnimatedSprite2D") : null;
                    bool shader = sprite?.Material is ShaderMaterial material && material.Shader.Code.Contains("tex.a * 0.84");
                    int arcs = domain?.GetChildren().OfType<Line2D>().Count(l => l.Points.Length > 0) ?? 0;
                    int hpAfter = creature.CurrentHp, winsAfter = SaveManager.Instance.Progress.Wins;
                    Need(victoryCalls == 1 && winsAfter == winsBefore + 1 && !SaveManager.Instance.HasRunSave, "single native victory persisted and active save removed");
                    Need(run.IsGameOver && room.IsVictoryRoom, "stock terminal victory screen context");
                    GD.Print("[Volibear] ARCHITECT_ENDING_OBSERVED " + JsonSerializer.Serialize(new {
                        bear, hpBefore, hpAfter, deaths, domainEntries, entered = domain?.Entered, shader, arcs,
                        scaleBefore, scaleAfter = body?.Scale.X, originalSnapshot = ReferenceEquals(screenSnapshot, victorySnapshot),
                        victoryCalls, lossCalls, abandoned = manager.IsAbandoned }));
                    Need(bear ? hpAfter == hpBefore && deaths == 0 && domainEntries == 1 && domain is { Entered: true } && shader && arcs == 6 &&
                        Math.Abs(body!.Scale.X / scaleBefore - 1.22f) < .001f && ReferenceEquals(screenSnapshot, victorySnapshot) && lossCalls == 0
                        : hpAfter == 0 && deaths == 1 && domainEntries == 0 && domain is null && lossCalls == 1,
                        "character-scoped final domain replaces death; stock control keeps native path");
                    rows.Add(new { family = bear ? "volibear" : "ironclad", character = character.GetType().Name, optionsChosen = options,
                        before = new { hp = hpBefore, wins = winsBefore, saved = saveBefore },
                        after = new { hp = hpAfter, wins = winsAfter, saved = SaveManager.Instance.HasRunSave, gameOver = run.IsGameOver,
                            victoryRoom = room.IsVictoryRoom, screen = screen.GetType().Name, deaths, domainEntries },
                        records = new { victoryCalls, lossCalls, originalSnapshot = ReferenceEquals(screenSnapshot, victorySnapshot) },
                        visual = new { entered = domain?.Entered ?? false, shader, arcs, scaleRatio = bear ? body!.Scale.X / scaleBefore : 1f,
                            animation = sprite?.Animation.ToString() ?? "" } });
                }
                finally { observing = false; creature.Died -= Died; VolibearArchitectEnding.DomainEntered -= Entered; }
                await NativeAcceptanceRunHost.ExitToMainMenu(false);
            }
            GD.Print("[Volibear] ARCHITECT_ENDING_RESULT " + JsonSerializer.Serialize(new { schema = 1, token, scenario = "architect-ending",
                fixture = "isolated-architect-events-not-full-run", version = release.Version, commit = release.Commit, testMode = false, cases = rows, passed = true }));
        }
        finally { observing = false; observer.UnpatchAll(observer.Id); }
    }
}
