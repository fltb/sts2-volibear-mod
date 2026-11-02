using System;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using Volibear.Content;

namespace Volibear;

/// <summary>Only native run/room lifetime for isolated acceptance; no rules or observers.</summary>
internal static class NativeAcceptanceRunHost
{
    private static void Timing(string stage, System.Diagnostics.Stopwatch clock) =>
        GD.Print($"[Volibear] NATIVE_HOST_TIMING stage={stage} elapsedMs={clock.ElapsedMilliseconds} fps={Engine.GetFramesPerSecond()}");
    internal sealed record ExitReceipt(bool RunNull,bool CombatNull,bool InProgress,bool QueueEmpty,bool ActionNull,int HistoryVisible);
    private static async Task Frame()
    {
        var game=NGame.Instance ?? throw new InvalidOperationException("Native game node missing");
        await game.ToSignal(game.GetTree(),SceneTree.SignalName.ProcessFrame);
    }
    internal static bool IsQuiet(CombatState state,int? turn=null) =>
        ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(),state) && CombatManager.Instance.IsInProgress &&
        !CombatManager.Instance.IsOverOrEnding && state.CurrentSide==CombatSide.Player &&
        state.Players.Single().PlayerCombatState is { Phase:PlayerTurnPhase.Play } pcs && (!turn.HasValue || pcs.TurnNumber==turn) &&
        RunManager.Instance.ActionQueueSet.IsEmpty && RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null &&
        state.Enemies.All(e => e.Monster is { IsPerformingMove:false });
    internal static async Task WaitForQuiet(CombatState state,int? turn=null)
    {
        var clock=System.Diagnostics.Stopwatch.StartNew();
        while (!IsQuiet(state,turn))
        {
            if (clock.Elapsed>TimeSpan.FromSeconds(40)) throw new TimeoutException("Native acceptance run did not reach quiet player phase");
            await Frame();
        }
    }
    internal static ExitReceipt CleanState() => new(RunManager.Instance.DebugOnlyGetState() is null,
        CombatManager.Instance.DebugOnlyGetState() is null,CombatManager.Instance.IsInProgress,
        RunManager.Instance.ActionQueueSet.IsEmpty,RunManager.Instance.ActionExecutor.CurrentlyRunningAction is null,
        CombatManager.Instance.History.Entries.Count());
    internal static void RequireClean()
    {
        var exit=CleanState();
        if (!exit.RunNull || !exit.CombatNull || exit.InProgress || !exit.QueueEmpty || !exit.ActionNull || exit.HistoryVisible!=0)
            throw new InvalidOperationException("Native prior-run cleanup incomplete: "+exit);
    }
    internal static async Task<ExitReceipt> ExitToMainMenu(bool enterMapFirst = true)
    {
        var timing=System.Diagnostics.Stopwatch.StartNew();
        var state=CombatManager.Instance.DebugOnlyGetState();
        if (state is not null && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding)
        {
            await WaitForQuiet(state);
            if (enterMapFirst)
            {
                await RunManager.Instance.EnterRoom(new MapRoom());
                await Frame();
            }
        }
        Timing("exit-map",timing);timing.Restart();
        await NGame.Instance!.ReturnToMainMenu();await Frame();RequireClean();
        Timing("exit-menu",timing);return CleanState();
    }
    internal static async Task<CombatState> StartFresh(EncounterModel encounter,string seed="volibear-native-acceptance")
    {
        RequireClean();
        var character=ModelDb.Character<VolibearCharacter>();
        // Same prerequisite as the native lobby; no explicit progress save.
        SaveManager.Instance.Progress.GetOrCreateCharacterStats(character.Id);
        var timing=System.Diagnostics.Stopwatch.StartNew();
        await NGame.Instance!.StartNewSingleplayerRun(character,shouldSave:false,ActModel.GetDefaultList().ToArray(),
            Array.Empty<ModifierModel>(),seed,GameMode.Standard,ascensionLevel:0);
        Timing("start-run",timing);timing.Restart();
        CombatState? state=null;
        void OnTurn(CombatState current) => state=current;
        CombatManager.Instance.TurnStarted+=OnTurn;
        try
        {
            await RunManager.Instance.EnterRoomDebug(encounter.RoomType,model:encounter.ToMutable(),showTransition:false);
            var clock=System.Diagnostics.Stopwatch.StartNew();
            while (state is null)
            {
                if (clock.Elapsed>TimeSpan.FromSeconds(40)) throw new TimeoutException("Native fresh combat never started");
                await Frame();
            }
            await WaitForQuiet(state,1);Timing("start-room-quiet",timing);return state;
        }
        finally { CombatManager.Instance.TurnStarted-=OnTurn; }
    }
}
