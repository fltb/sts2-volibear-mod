using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
#if STS2_BETA
using VictoryResult = MegaCrit.Sts2.Core.Entities.Save.PostRunProgressUpdateResult;
#else
using VictoryResult = MegaCrit.Sts2.Core.Saves.SerializableRun;
#endif
using MegaCrit.Sts2.Core.Audio.Debug;
using Volibear.Content;

namespace Volibear.Presentation;

/// <summary>Only the Architect victory's final kill sequence changes. Run bookkeeping,
/// dialogue, network readiness and the stock victory screen keep their native path.</summary>
internal static class VolibearArchitectEnding
{
    private const string Id = "Volibear.ArchitectEnding";
    private sealed record Victory(RunState State, VictoryResult Snapshot);
    private static readonly ConditionalWeakTable<RunManager, Victory> Victories = new();
    private static readonly ConditionalWeakTable<RunState, Victory> Completed = new();
    internal static bool IsDomainVictory(RunState state) => Completed.TryGetValue(state, out _);
    private static void TerminalState(RunState __instance, ref bool __result) => __result |= IsDomainVictory(__instance);
    private static readonly MethodInfo NativeKillAll = AccessTools.DeclaredMethod(typeof(RunManager), "GuaranteeKillAllPlayers");
    private static readonly MethodInfo NativeEnd = AccessTools.DeclaredMethod(typeof(RunManager), nameof(RunManager.OnEnded));
    private static bool installed;
    internal static event Action<Creature>? DomainEntered;
    internal static event Action<VictoryResult>? VictoryShown;

    internal static void Install()
    {
        if (installed) return;
        var harmony = new Harmony(Id);
        try
        {
            harmony.Patch(NativeBody(), transpiler: new(typeof(VolibearArchitectEnding), nameof(Rewrite)));
            harmony.Patch(AccessTools.PropertyGetter(typeof(RunState), nameof(RunState.IsGameOver)),
                postfix: new(typeof(VolibearArchitectEnding), nameof(TerminalState)));
            installed = true;
        }
        catch { harmony.UnpatchAll(Id); throw; }
    }
    internal static MethodInfo NativeBody() => AccessTools.DeclaredMethod(
        AccessTools.DeclaredMethod(typeof(RunManager), "WinRun").GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
    internal static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> instructions)
    {
        var code = instructions.ToList();
        if (code.Count(c => c.Calls(NativeEnd)) != 1 || code.Count(c => c.Calls(NativeKillAll)) != 1)
            throw new InvalidOperationException("Locked Architect victory callsites changed");
        int end = code.FindIndex(c => c.Calls(NativeEnd)), kill = code.FindIndex(c => c.Calls(NativeKillAll));
        if (end >= kill) throw new InvalidOperationException("Victory must be recorded before its final presentation");
        code[end].opcode = System.Reflection.Emit.OpCodes.Call;
        code[end].operand = AccessTools.DeclaredMethod(typeof(VolibearArchitectEnding), nameof(RecordVictory));
        code[kill].opcode = System.Reflection.Emit.OpCodes.Call;
        code[kill].operand = AccessTools.DeclaredMethod(typeof(VolibearArchitectEnding), nameof(FinishVictory));
        return code;
    }
    private static bool Applies(RunManager manager) => !manager.IsAbandoned && manager.DebugOnlyGetState() is { } state &&
        state.CurrentRoom is EventRoom room && room.LocalMutableEvent is TheArchitect &&
        state.Players.Any(p => p.Character is VolibearCharacter && p.Creature.IsAlive);

    private static VictoryResult RecordVictory(RunManager manager, bool isVictory)
    {
        // Keep the exact snapshot returned by the sole native victory record call.
        var snapshot = manager.OnEnded(isVictory);
        Victories.Remove(manager);
        if (isVictory && Applies(manager)) Victories.Add(manager, new(manager.DebugOnlyGetState()!, snapshot));
        return snapshot;
    }
    private static async Task FinishVictory(RunManager manager)
    {
        if (manager.DebugOnlyGetState() is { } completed && IsDomainVictory(completed)) { Victories.Remove(manager); return; }
        if (!Victories.TryGetValue(manager, out var victory) || !ReferenceEquals(manager.DebugOnlyGetState(), victory.State) || !Applies(manager))
        {
            Victories.Remove(manager);
            await (Task)NativeKillAll.Invoke(manager, null)!;
            return;
        }
        Victories.Remove(manager);
        foreach (var player in victory.State.Players)
        {
            if (player.Character is VolibearCharacter && player.Creature.IsAlive)
            {
                EnterDomain(player.Creature);
                DomainEntered?.Invoke(player.Creature);
            }
            else await CreatureCmd.Kill(player.Creature, force: true);
            await Cmd.CustomScaledWait(0.25f, 0.5f);
        }
        await Cmd.Wait(1.5f);
        Completed.Add(victory.State, victory);
        #if !STS2_BETA
        ShowVictory(victory.Snapshot);
#endif
        VictoryShown?.Invoke(victory.Snapshot);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void EnterDomain(Creature creature) => VolibearPresentationBridge.EnterArchitectDomain(creature);
    #if !STS2_BETA
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void ShowVictory(VictoryResult snapshot)
    {
        if (TestMode.IsOn) return;
        var run = NRun.Instance ?? throw new InvalidOperationException("Native victory run view missing");
        run.RunMusicController.StopMusic();
        NDebugAudioManager.Instance?.StopAll();
        (NAudioManager.Instance ?? throw new InvalidOperationException("Native victory audio missing")).PlayMusic("event:/temp/sfx/game_over");
        run.ShowGameOverScreen(snapshot);
    }
#endif
}
