using System;
using System.Collections.Generic;
using System.Linq;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using Volibear.Content;

namespace Volibear;

/// <summary>Only native run/room lifetime for isolated acceptance; no rules or observers.</summary>
internal static class NativeAcceptanceRunHost
{
    // The pinned native loader explicitly supports lazy loading for iteration. Its
    // Enabled switch only suppresses speculative bulk loading: native cache eviction,
    // missed-resource disposal and GetAsset's real ResourceLoader fallback still run.
    // Never retain mutable Resources across cases, skip
    // native run cleanup, or extend this scope to asset/presentation acceptance.
    internal sealed class GameplayBatchScope : IDisposable
    {
        private static GameplayBatchScope? active;
        private readonly bool previous;
        private readonly FastModeType previousSpeed;
        private readonly int previousMaxFps;
        private bool disposed;
        private IDisposable? profiler, pacing;
        private NativeAcceptanceArtResidency? art;
        internal static bool IsActive => active is not null;
        internal GameplayBatchScope()
        {
            var scenario = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO");
            var release = ReleaseInfoManager.Instance.ReleaseInfo;
            if (scenario is not ("native-suite" or "card-face-acceptance" or "card-lifecycle" or "catalog-face-suite") ||
                string.IsNullOrWhiteSpace(System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN")) ||
                release is null || release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Lazy assets require a pinned isolated gameplay acceptance batch");
            if (active is not null) throw new InvalidOperationException("Gameplay batch scopes cannot overlap");
            previous = PreloadManager.Enabled;
            previousSpeed = SaveManager.Instance.PrefsSave.FastMode;
            previousMaxFps = Engine.MaxFps;
            active = this;
            try
            {
                ReapplyIfActive();
                art = new NativeAcceptanceArtResidency(); pacing = new HiddenRoomFadePacing(); profiler = LoadProfiler.StartIfRequested();
                GD.Print("[Volibear] NATIVE_HOST_GAMEPLAY mode=Instant assets=lazy nativeEviction=true maxFps=240");
            }
            catch { Dispose(); throw; }
        }
        internal static void ReapplyIfActive()
        {
            if (active is null) return;
            // NCharacterSelectScreen._Ready constructs the bootstrap settings on
            // EVERY native menu entry and resets Enabled to DoPreloading=true.
            // Reassert only our active batch's public preferences after that boundary.
            PreloadManager.Enabled = false;
            // Native Instant bypasses Cmd delays, UI fades and death VFX, and
            // shortens card tweens; this batch does not certify presentation.
            // Queue execution, choices, hooks and turn/run boundaries are untouched.
            // This is an in-memory isolated preference; never call SavePrefs here.
            SaveManager.Instance.PrefsSave.FastMode = FastModeType.Instant;
            // Reduce frame quantization only. Real-time delays, physics tick rate,
            // VSync, tween durations and native callbacks remain unchanged.
            Engine.MaxFps = 240;
        }
        internal static void ValidateArtIfActive() => active?.art?.Validate();
        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            active = null;
            try { try { art?.Validate(); } finally { art?.Dispose(); } }
            finally
            {
                try { try { profiler?.Dispose(); } finally { pacing?.Dispose(); } }
                finally
                {
                    PreloadManager.Enabled = previous;
                    SaveManager.Instance.PrefsSave.FastMode = previousSpeed;
                    Engine.MaxFps = previousMaxFps;
                    GD.Print($"[Volibear] NATIVE_HOST_GAMEPLAY restoredPreloading={previous} restoredSpeed={previousSpeed} restoredMaxFps={previousMaxFps}");
                }
            }
        }
    }

    // Pinned RoomFadeIn(false) clears alpha for Instant but falls through to an
    // 0.8s fade plus a 0.2s callback delay. Advance only that newly-created visual
    // tween, preserving its callbacks/Finished signal and the original await/Task.
    internal sealed class HiddenRoomFadePacing : IDisposable
    {
        private const string Owner = "Volibear.NativeAcceptanceHiddenFade";
        private static readonly FieldInfo TweenField = typeof(NTransition).GetField("_tween", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(typeof(NTransition).FullName, "_tween");
        private readonly Harmony harmony = new(Owner);
        private readonly MethodInfo method;
        private bool disposed;
        internal readonly record struct Observation(bool Eligible, Tween? Before);
        internal HiddenRoomFadePacing()
        {
            if (!GameplayBatchScope.IsActive || TweenField.FieldType != typeof(Tween))
                throw new InvalidOperationException("Hidden fade pacing requires the pinned guarded batch");
            method = typeof(NTransition).GetMethod("RoomFadeIn", new[] { typeof(bool) })
                ?? throw new MissingMethodException(typeof(NTransition).FullName, "RoomFadeIn(bool)");
            if (method.ReturnType != typeof(Task)) throw new InvalidOperationException("Unexpected RoomFadeIn return type");
            try
            {
                harmony.Patch(method, prefix: new HarmonyMethod(typeof(HiddenRoomFadePacing), nameof(Before)),
                    postfix: new HarmonyMethod(typeof(HiddenRoomFadePacing), nameof(After)));
            }
            catch { harmony.Unpatch(method, HarmonyPatchType.All, Owner); throw; }
        }
        private static bool Eligible(bool showTransition) => GameplayBatchScope.IsActive && !showTransition &&
            SaveManager.Instance.PrefsSave.FastMode == FastModeType.Instant && !MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn;
        private static void Before(NTransition __instance, bool showTransition, out Observation __state)
        {
            bool eligible = Eligible(showTransition);
            __state = new(eligible, eligible ? (Tween?)TweenField.GetValue(__instance) : null);
        }
        private static void After(NTransition __instance, bool showTransition, Observation __state)
        {
            if (!__state.Eligible || !Eligible(showTransition)) return;
            var tween = (Tween?)TweenField.GetValue(__instance);
            // Early native return (e.g. no transition material) created no tween.
            if (tween is null || ReferenceEquals(tween, __state.Before)) return;
            if (!tween.IsValid() || !tween.IsRunning()) return;
            bool finished = false;
            void OnFinished() => finished = true;
            tween.Finished += OnFinished;
            try
            {
                // Upper bound is 0.8 + 0.2 seconds, with 0.1 numerical slack.
                // No loop, Kill, Stop, Task substitute, or synthesized signal.
                // Godot 4.5.1 step() can return true on the frame that emits
                // Finished, so use the real signal/running state, not its return.
                tween.CustomStep(1.1);
                if (tween.IsRunning() || !finished || __instance.InTransition)
                    throw new InvalidOperationException("Pinned hidden-room visual tween did not finish within its duration bound");
                GD.Print("[Volibear] NATIVE_HOST_FADE showTransition=false customStepSeconds=1.1 finishedSignal=true");
            }
            finally { tween.Finished -= OnFinished; }
        }
        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            harmony.Unpatch(method, HarmonyPatchType.All, Owner);
        }
    }

    // Opt-in observer only. No skipped originals, Task replacement, result reads,
    // resource retention, or gameplay hooks. Full-task latency includes scheduling
    // and waiting, not CPU time. Inclusive rows overlap and must not be summed.
    internal sealed class LoadProfiler : IDisposable
    {
        private const string Owner = "Volibear.NativeAcceptanceLoadProfiler";
        private readonly Harmony harmony = new(Owner);
        private static LoadProfiler? current;
        private readonly Dictionary<string, (long Ticks, int Calls)> samples = new(StringComparer.Ordinal);
        private readonly List<MethodInfo> patched = new();
        private int emitted;
        private bool disposed;
        private sealed record CompletionSample(WeakReference<LoadProfiler> Profile, string Key, long Started);
        internal static IDisposable? StartIfRequested()
        {
            if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PROFILE_LOADS") != "1") return null;
            if (!GameplayBatchScope.IsActive || current is not null)
                throw new InvalidOperationException("Load profiling requires the guarded gameplay batch scope");
            var result = new LoadProfiler();
            current = result;
            try
            {
                // Verified against 0.107.1/59260271; exact non-generic signatures.
                result.Install(typeof(AssetCache), "GetAsset", typeof(Resource), typeof(string));
                result.Install(typeof(AssetCache), "LoadAsset", typeof(Resource), typeof(string));
                result.Install(typeof(AssetCache), "GetLoadedCacheAssets", typeof(IReadOnlySet<string>));
                result.Install(typeof(AssetCache), "UnloadAssets", typeof(void), typeof(IEnumerable<string>));
                result.Install(typeof(NRun), "Create", typeof(NRun), typeof(RunState));
                result.Install(typeof(NRun), "_Ready", typeof(void));
                result.Install(typeof(NCombatRoom), "Create", typeof(NCombatRoom), typeof(ICombatRoomVisuals), typeof(CombatRoomMode));
                result.Install(typeof(NCombatRoom), "_Ready", typeof(void));
                result.Install(typeof(NSceneContainer), "SetCurrentScene", typeof(void), typeof(Control));
                // Keep synchronous-return samples and separately observe original
                // Task completion without replacing or awaiting it in the patch.
                result.Install(typeof(PreloadManager), "LoadRunAssets", typeof(Task), typeof(IEnumerable<CharacterModel>));
                result.Install(typeof(PreloadManager), "LoadActAssets", typeof(Task), typeof(ActModel));
                result.Install(typeof(PreloadManager), "LoadRoomAssets", typeof(Task), typeof(string), typeof(IEnumerable<string>));
                result.Install(typeof(PreloadManager), "LoadAssetSets", typeof(Task<AssetLoadingSession>), typeof(string), typeof(IEnumerable<string>[]));
                result.Install(typeof(RunState), "CreateForNewRun", typeof(RunState), typeof(IReadOnlyList<Player>), typeof(IReadOnlyList<ActModel>), typeof(IReadOnlyList<ModifierModel>), typeof(GameMode),
#if STS2_BETA
                    typeof(bool),
#endif
                    typeof(int), typeof(string));
                result.Install(typeof(RunManager), "GenerateMap", typeof(Task));
                result.Install(typeof(NGame), "StartNewSingleplayerRun", typeof(Task<RunState>),
#if STS2_BETA
                    typeof(Player),
#else
                    typeof(CharacterModel),
#endif
                    typeof(bool), typeof(IReadOnlyList<ActModel>), typeof(IReadOnlyList<ModifierModel>), typeof(string), typeof(GameMode),
#if STS2_BETA
                    typeof(bool),
#endif
                    typeof(int), typeof(DateTimeOffset?));
                GD.Print($"[Volibear] NATIVE_LOAD_PROFILE installed={result.patched.Count} inclusive=true taskSamples=sync-return+full-task fullTaskIncludesSchedulingAndWaits=true cpuTime=false");
                return result;
            }
            catch { result.Dispose(); throw; }
        }
        private void Install(Type type, string name, Type returns, params Type[] arguments)
        {
            var method = type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
                .Single(m => m.Name == name && !m.IsGenericMethod && m.ReturnType == returns &&
                    m.GetParameters().Select(p => p.ParameterType).SequenceEqual(arguments));
            patched.Add(method);
            harmony.Patch(method, prefix: new HarmonyMethod(typeof(LoadProfiler), nameof(Before)),
                postfix: new HarmonyMethod(typeof(LoadProfiler), typeof(Task).IsAssignableFrom(returns) ? nameof(AfterTask) : nameof(After)),
                finalizer: new HarmonyMethod(typeof(LoadProfiler), nameof(Failed)));
        }
        private static void Before(out long __state) => __state = Stopwatch.GetTimestamp();
        private static void After(MethodBase __originalMethod, object[] __args, long __state) => Record(__originalMethod, __args, __state, false);
        private static void AfterTask(MethodBase __originalMethod, object[] __args, long __state, Task __result)
        {
            Record(__originalMethod, __args, __state, false);
            var profile = current;
            if (profile is null || __result is null) return;
            var sample = new CompletionSample(new WeakReference<LoadProfiler>(profile),
                __originalMethod.DeclaringType!.Name + "." + __originalMethod.Name + ":full-task-including-waits", __state);
            // State holds no Task, arguments, model, node, or strong scope reference.
            // After scope disposal a pending callback is an inert weak observation.
            if (System.Threading.ExecutionContext.IsFlowSuppressed()) AttachCompletion(__result, sample);
            else
            {
                using (System.Threading.ExecutionContext.SuppressFlow()) AttachCompletion(__result, sample);
            }
        }
        private static void AttachCompletion(Task original, CompletionSample sample)
        {
            _ = original.ContinueWith(static (completed, state) =>
            {
                var item = (CompletionSample)state!;
                if (!item.Profile.TryGetTarget(out var target)) return;
                string status = completed.IsCanceled ? ":canceled" : completed.IsFaulted ? ":faulted" : ":success";
                target.Add(item.Key + status, Stopwatch.GetTimestamp() - item.Started);
            }, sample, System.Threading.CancellationToken.None,
                TaskContinuationOptions.ExecuteSynchronously, TaskScheduler.Default);
        }
        private static void Failed(MethodBase __originalMethod, object[] __args, long __state, Exception? __exception)
        {
            if (__exception is not null) Record(__originalMethod, __args, __state, true);
        }
        private static void Record(MethodBase method, object[] args, long start, bool failed)
        {
            var profile = current;
            if (profile is null) return;
            long elapsed = Stopwatch.GetTimestamp() - start;
            string key = method.DeclaringType!.Name + "." + method.Name;
            if (method is MethodInfo info && typeof(Task).IsAssignableFrom(info.ReturnType)) key += ":sync-before-task-return";
            if (method.DeclaringType == typeof(AssetCache) && args.Length == 1 && args[0] is string path) key += ":" + path;
            if (failed) key += ":exception";
            profile.Add(key, elapsed);
        }
        private void Add(string key, long elapsed)
        {
            lock (samples)
            {
                if (disposed) return;
                if (!samples.ContainsKey(key) && samples.Count >= 512) key = "other-bounded";
                samples.TryGetValue(key, out var old);
                samples[key] = (old.Ticks + elapsed, old.Calls + 1);
            }
        }
        internal static void Flush(string stage)
        {
            var profile = current;
            if (profile is null) return;
            KeyValuePair<string, (long Ticks, int Calls)>[] snapshot;
            lock (profile.samples)
            {
                snapshot = profile.samples.OrderByDescending(s => s.Value.Ticks)
                    .Take(Math.Min(12, Math.Max(0, 256 - profile.emitted))).ToArray();
                profile.emitted += snapshot.Length;
                profile.samples.Clear();
            }
            // Completion callbacks never invoke Godot or contend with log output.
            foreach (var sample in snapshot)
                GD.Print("[Volibear] NATIVE_LOAD_PROFILE " + JsonSerializer.Serialize(new {
                    stage, method = sample.Key, calls = sample.Value.Calls,
                    inclusiveMs = sample.Value.Ticks * 1000.0 / Stopwatch.Frequency }));
        }
        public void Dispose()
        {
            if (!ReferenceEquals(current, this)) return;
            try { Flush("scope-exit"); }
            finally
            {
                lock (samples) { disposed = true; samples.Clear(); }
                current = null;
                foreach (var method in patched) harmony.Unpatch(method, HarmonyPatchType.All, Owner);
                patched.Clear();
                GD.Print("[Volibear] NATIVE_LOAD_PROFILE uninstalled=true");
            }
        }
    }

    // Scalar snapshots at existing phase boundaries only: no per-frame observer,
    // GPU synchronization, viewport measurement enablement, or renderer setting changes.
    // Frame counters are engine-lifetime totals; remaining metrics are scalar
    // samples from the engine, NOT measured phase totals.
    internal static class FrameMetrics
    {
        internal static string Capture() => FormattableString.Invariant($"processFramesTotal={Engine.GetProcessFrames()} renderedFramesTotal={Engine.GetFramesDrawn()} processMsLatest={Performance.GetMonitor(Performance.Monitor.TimeProcess) * 1000:F3} renderSetupCpuMsLatest={RenderingServer.GetFrameSetupTimeCpu():F3} drawCallsLatest={Performance.GetMonitor(Performance.Monitor.RenderTotalDrawCallsInFrame):F0} pipelineCanvasCount={Performance.GetMonitor(Performance.Monitor.PipelineCompilationsCanvas):F0} pipelineMeshCount={Performance.GetMonitor(Performance.Monitor.PipelineCompilationsMesh):F0} pipelineSurfaceCount={Performance.GetMonitor(Performance.Monitor.PipelineCompilationsSurface):F0} pipelineDrawCount={Performance.GetMonitor(Performance.Monitor.PipelineCompilationsDraw):F0} pipelineSpecializationCount={Performance.GetMonitor(Performance.Monitor.PipelineCompilationsSpecialization):F0}");
    }

    private static void Timing(string stage, System.Diagnostics.Stopwatch clock)
    {
        GD.Print($"[Volibear] NATIVE_HOST_TIMING stage={stage} elapsedMs={clock.ElapsedMilliseconds} fps={Engine.GetFramesPerSecond()} maxFps={Engine.MaxFps} speed={SaveManager.Instance.PrefsSave.FastMode} preload={PreloadManager.Enabled} gcPauseTotalMs={GC.GetTotalPauseDuration().TotalMilliseconds:F1} gen2Collections={GC.CollectionCount(2)} {FrameMetrics.Capture()}");
        LoadProfiler.Flush(stage);
    }
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
        GameplayBatchScope.ValidateArtIfActive();
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
        GameplayBatchScope.ValidateArtIfActive();
        GameplayBatchScope.ReapplyIfActive();
        Timing("exit-menu",timing);return CleanState();
    }
    internal static async Task<CombatState> StartFresh(EncounterModel encounter,string seed="volibear-native-acceptance")
    {
        RequireClean();
        GameplayBatchScope.ValidateArtIfActive();
        GameplayBatchScope.ReapplyIfActive();
        var character=ModelDb.Character<VolibearCharacter>();
        // Same prerequisite as the native lobby; no explicit progress save.
        SaveManager.Instance.Progress.GetOrCreateCharacterStats(character.Id);
        var timing=System.Diagnostics.Stopwatch.StartNew();
        await ProbeGameCompat.StartRun(character,shouldSave:false,ActModel.GetDefaultList().ToArray(),
            Array.Empty<ModifierModel>(),seed,GameMode.Standard,ascensionLevel:0);
        Timing("start-run",timing);timing.Restart();
        CombatState? state=null;
        void OnTurn(CombatState current) => state=current;
        CombatManager.Instance.TurnStarted+=OnTurn;
        try
        {
            await RunManager.Instance.EnterRoomDebug(encounter.RoomType,model:encounter.ToMutable(),showTransition:false);
            Timing("start-room-entered",timing);
            var clock=System.Diagnostics.Stopwatch.StartNew();
            while (state is null)
            {
                if (clock.Elapsed>TimeSpan.FromSeconds(40)) throw new TimeoutException("Native fresh combat never started");
                await Frame();
            }
            await WaitForQuiet(state,1);
            GameplayBatchScope.ValidateArtIfActive();
            Timing("start-room-quiet",timing);return state;
        }
        finally { CombatManager.Instance.TurnStarted-=OnTurn; }
    }
}
