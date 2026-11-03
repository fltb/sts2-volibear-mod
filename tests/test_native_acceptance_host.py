"""Scope/real Harmony tests with doubles; native API compile, no game launch."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from xml.sax.saxutils import escape
from tools.runtime_test import fixture_runtime

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'src/Volibear/NativeAcceptanceRunHost.cs'
USINGS = '''using System;
using System.Collections.Generic;
using System.Linq;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using HarmonyLib;
using Godot;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Entities.Players;
using Volibear;
'''


def scopes():
    source = HOST.read_text(encoding='utf-8')
    return 'internal sealed class GameplayBatchScope' + source.split('internal sealed class GameplayBatchScope', 1)[1].split('    private static void Timing', 1)[0]


class NativeAcceptanceHostTests(unittest.TestCase):
    def build(self, runtime, source, references, run, extra_sources=()):
        (ROOT / '.local').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='acceptance-host-', dir=ROOT / '.local') as directory:
            folder = Path(directory)
            project = folder / 'Host.csproj'
            refs = ''.join(f'<Reference Include="{escape(Path(p).stem)}"><HintPath>{escape(str(p))}</HintPath></Reference>' for p in references)
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
                               f'<OutputType>{"Exe" if run else "Library"}</OutputType>'
                               '<TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><NuGetAudit>false</NuGetAudit>'
                               '</PropertyGroup><ItemGroup>' + refs + '</ItemGroup></Project>', encoding='utf-8')
            (folder / 'Program.cs').write_text(source, encoding='utf-8')
            for extra in extra_sources:
                (folder / extra.name).write_text(extra.read_text(encoding='utf-8'), encoding='utf-8')
            command = [str(runtime.dotnet), 'run', '--project', str(project)] if run else [str(runtime.dotnet), 'build', str(project)]
            result = subprocess.run([*command, '-c', 'Release', '--nologo'], cwd=ROOT, capture_output=True,
                                    text=True, encoding='utf-8', timeout=120, env=runtime.environment())
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_scope_restoration_and_real_harmony_observer(self):
        runtime = fixture_runtime(self, 'sdk', 'harmony', root=ROOT)
        doubles = '''
namespace Volibear {
 // Contract-only double; real native resource implementation is separately compiled.
 internal sealed class NativeAcceptanceArtResidency : IDisposable {
  internal static int Alive; internal static bool FailValidation, FailConstruction;
  internal NativeAcceptanceArtResidency() { if (FailConstruction) throw new InvalidOperationException("injected constructor failure"); Alive++; }
  internal void Validate() { if (FailValidation) throw new InvalidOperationException("art changed"); }
  public void Dispose() { Alive--; }
 }
}
namespace Godot {
 public static class Engine { public static int MaxFps { get; set; } = 60; public static ulong GetProcessFrames() => 100; public static ulong GetFramesDrawn() => 90; }
 public static class RenderingServer { public static double GetFrameSetupTimeCpu() => 2.5; }
 public static class Performance {
  public enum Monitor { TimeProcess, RenderTotalDrawCallsInFrame, PipelineCompilationsCanvas, PipelineCompilationsMesh, PipelineCompilationsSurface, PipelineCompilationsDraw, PipelineCompilationsSpecialization }
  public static int Reads;
  public static double GetMonitor(Monitor metric) { Reads++; return metric == Monitor.TimeProcess ? 0.01 : 42; }
 }
 public class Tween {
  public event Action? Finished; public bool Running = true; public double Duration = 1.0; public int Steps; public Action Callback = () => {};
  public bool IsValid() => true; public bool IsRunning() => Running;
  public bool CustomStep(double delta) { Steps++; if (delta >= Duration) { Running = false; Callback(); Finished?.Invoke(); } return true; }
 }
 public class Control {} public class Resource {} public static class GD { public static List<string> Messages = new(); public static void Print(string value) { Messages.Add(value); } } }
namespace MegaCrit.Sts2.Core.Assets {
 public class AssetCache {
  public static readonly Resource Value = new();
  public static readonly IReadOnlySet<string> Loaded = new HashSet<string> { "one", "two" };
  public int Unloaded;
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public IReadOnlySet<string> GetLoadedCacheAssets() => Loaded;
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public void UnloadAssets(IEnumerable<string> paths) { foreach (var path in paths) Unloaded++; }
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  private Resource GetAsset(string path) => LoadAsset(path);
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  private Resource LoadAsset(string path) { if (path == "error") throw new InvalidOperationException("original failure"); return Value; }
  public T GetAsset<T>(string path) where T : Resource => (T)GetAsset(path);
 }
 public class AssetLoadingSession {}
 public static class PreloadManager {
  public static bool Enabled { get; set; } = true;
  public static TaskCompletionSource Pending = new();
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public static Task LoadRunAssets(IEnumerable<CharacterModel> characters) { Pending = new(); return Pending.Task; }
  public static Task LoadActAssets(ActModel act) => Task.CompletedTask;
  private static Task LoadRoomAssets(string roomName, IEnumerable<string> additionalAssets) => Task.CompletedTask;
  private static Task<AssetLoadingSession> LoadAssetSets(string name, params IEnumerable<string>[] assetSets) => Task.FromResult(new AssetLoadingSession());
 }
}
namespace MegaCrit.Sts2.Core.Settings { public enum FastModeType { Normal, Fast, Instant } }
namespace MegaCrit.Sts2.Core.Saves {
 public sealed class Preferences { public FastModeType FastMode { get; set; } }
 public sealed class SaveManager { public static SaveManager Instance { get; } = new(); public Preferences PrefsSave { get; } = new(); }
}
namespace MegaCrit.Sts2.Core.TestSupport { public static class TestMode { public static bool IsOn { get; set; } } }
namespace MegaCrit.Sts2.Core.Debug {
 public sealed class Release { public string Version = "v0.107.1", Commit = "59260271"; }
 public sealed class ReleaseInfoManager { public static ReleaseInfoManager Instance { get; } = new(); public Release? ReleaseInfo { get; set; } = new(); }
}
namespace MegaCrit.Sts2.Core.Models { public class CharacterModel {} public class ActModel {} public class ModifierModel {} }
namespace MegaCrit.Sts2.Core.Entities.Players { public class Player {} }
namespace MegaCrit.Sts2.Core.Runs {
 public enum GameMode { Standard }
 public class RunManager { public Task GenerateMap() => Task.CompletedTask; }
 public class RunState {
  public static RunState CreateForNewRun(IReadOnlyList<Player> players, IReadOnlyList<ActModel> acts, IReadOnlyList<ModifierModel> modifiers, GameMode gameMode, int ascensionLevel, string seed) => new();
 }
}
namespace MegaCrit.Sts2.Core.Rooms { public interface ICombatRoomVisuals {} }
namespace MegaCrit.Sts2.Core.Nodes {
 public class NGame {
  public Task<RunState> StartNewSingleplayerRun(CharacterModel character, bool shouldSave, IReadOnlyList<ActModel> acts, IReadOnlyList<ModifierModel> modifiers, string seed, GameMode gameMode, int ascensionLevel = 0, DateTimeOffset? dailyTime = null) => Task.FromResult(new RunState());
 }
 public class NTransition {
  private Tween? _tween;
  public bool InTransition { get; private set; }
  public bool Fail, EarlyReturn, ExcessDuration;
  public Task? LastTask; public Tween? Current => _tween; public int Callbacks;
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public Task RoomFadeIn(bool showTransition = true) {
   if (Fail) throw new ApplicationException("native fade failure");
   if (EarlyReturn) return LastTask = Task.CompletedTask;
   InTransition = true;
   var completion = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
   _tween = new Tween { Duration = ExcessDuration ? 10 : 1, Callback = () => { Callbacks++; InTransition = false; } };
   _tween.Finished += () => completion.SetResult();
   return LastTask = completion.Task;
  }
 }
 public class NRun { public static NRun Create(RunState state) => new(); public void _Ready() {} }
 public class NSceneContainer { public void SetCurrentScene(Control node) {} }
}
namespace MegaCrit.Sts2.Core.Nodes.Rooms {
 public enum CombatRoomMode { ActiveCombat }
 public class NCombatRoom { public static NCombatRoom Create(ICombatRoomVisuals visuals, CombatRoomMode mode) => new(); public void _Ready() {} }
}
'''
        program = '''
internal static class Program {
 static int assertions;
 static void Check(bool ok) { assertions++; if (!ok) throw new Exception("assertion " + assertions); }
 static void Rejected() {
  bool rejected = false;
  try { using var scope = new NativeAcceptanceRunHost.GameplayBatchScope(); } catch (InvalidOperationException) { rejected = true; }
  Check(rejected); Check(PreloadManager.Enabled); Check(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Normal); Check(Engine.MaxFps == 60);
 }
 static void Main() {
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_PROFILE_LOADS", null);
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN", "scope-test");
  foreach (var scenario in new[] { "native-suite", "card-face-acceptance", "card-lifecycle" })
  foreach (var enabled in new[] { false, true })
  foreach (var speed in Enum.GetValues<FastModeType>())
  foreach (var cap in new[] { 0, 60, 144 })
  foreach (var fail in new[] { false, true }) {
   Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", scenario);
   PreloadManager.Enabled = enabled; SaveManager.Instance.PrefsSave.FastMode = speed; Engine.MaxFps = cap;
   try {
    using var scope = new NativeAcceptanceRunHost.GameplayBatchScope();
    Check(!PreloadManager.Enabled); Check(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Instant); Check(Engine.MaxFps == 240);
    PreloadManager.Enabled = true; SaveManager.Instance.PrefsSave.FastMode = FastModeType.Fast; Engine.MaxFps = 30;
    NativeAcceptanceRunHost.GameplayBatchScope.ReapplyIfActive();
    Check(!PreloadManager.Enabled); Check(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Instant); Check(Engine.MaxFps == 240);
    if (fail) throw new ApplicationException();
   } catch (ApplicationException) { }
   NativeAcceptanceRunHost.GameplayBatchScope.ReapplyIfActive();
   Check(PreloadManager.Enabled == enabled); Check(SaveManager.Instance.PrefsSave.FastMode == speed); Check(Engine.MaxFps == cap);
  }
  Check(!GD.Messages.Any(m => m.Contains("NATIVE_LOAD_PROFILE")));
  PreloadManager.Enabled = true; SaveManager.Instance.PrefsSave.FastMode = FastModeType.Normal; Engine.MaxFps = 60;
  foreach (var scenario in new string?[] { null, "presentation", "native-run", "multiplayer" }) {
   Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", scenario); Rejected();
  }
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", "native-suite");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN", null); Rejected();
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN", "scope-test");
  MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn = true; Rejected();
  MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn = false;
  ReleaseInfoManager.Instance.ReleaseInfo!.Commit = "wrong"; Rejected();
  ReleaseInfoManager.Instance.ReleaseInfo = null; Rejected();
  ReleaseInfoManager.Instance.ReleaseInfo = new();
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_PROFILE_LOADS", "1");
  bool guard = false;
  try { NativeAcceptanceRunHost.LoadProfiler.StartIfRequested(); } catch (InvalidOperationException) { guard = true; }
  Check(guard);
  var original = typeof(AssetCache).GetMethod("GetAsset", BindingFlags.Instance | BindingFlags.NonPublic)!;
  foreach (var fail in new[] { false, true }) {
   try {
    using var scope = new NativeAcceptanceRunHost.GameplayBatchScope();
    Check(Harmony.GetPatchInfo(original)!.Owners.Contains("Volibear.NativeAcceptanceLoadProfiler"));
    var originalTask = PreloadManager.LoadRunAssets(Array.Empty<CharacterModel>());
    Check(ReferenceEquals(originalTask, PreloadManager.Pending.Task) && !originalTask.IsCompleted);
    NativeAcceptanceRunHost.LoadProfiler.Flush("task-prefix-fixture");
    Check(GD.Messages.Last().Contains("PreloadManager.LoadRunAssets:sync-before-task-return"));
    System.Threading.Thread.Sleep(15);
    if (fail) {
     var originalFailure = new ApplicationException("asynchronous fixture failure");
     PreloadManager.Pending.SetException(originalFailure);
     bool unchangedFailure = false;
     try { originalTask.GetAwaiter().GetResult(); } catch (ApplicationException e) { unchangedFailure = ReferenceEquals(e, originalFailure); }
     Check(unchangedFailure);
    } else { PreloadManager.Pending.SetResult(); Check(originalTask.IsCompletedSuccessfully); }
    NativeAcceptanceRunHost.LoadProfiler.Flush("task-completion-fixture");
    Check(GD.Messages.Last().Contains("PreloadManager.LoadRunAssets:full-task-including-waits:" + (fail ? "faulted" : "success")));
    Check(JsonDocument.Parse(GD.Messages.Last()[GD.Messages.Last().IndexOf('{')..]).RootElement.GetProperty("inclusiveMs").GetDouble() >= 10);
    var cache = new AssetCache();
    Check(ReferenceEquals(cache.GetLoadedCacheAssets(), AssetCache.Loaded));
    int enumerations = 0;
    IEnumerable<string> Paths() { enumerations++; yield return "one"; yield return "two"; }
    cache.UnloadAssets(Paths()); Check(enumerations == 1 && cache.Unloaded == 2);
    Check(ReferenceEquals(cache.GetAsset<Resource>("resource"), AssetCache.Value));
    bool sameError = false;
    try { cache.GetAsset<Resource>("error"); } catch (InvalidOperationException e) { sameError = e.Message == "original failure"; }
    Check(sameError);
    for (int i = 0; i < 1000; i++) cache.GetAsset<Resource>("bounded-" + i);
    NativeAcceptanceRunHost.LoadProfiler.Flush("fixture");
    Check(GD.Messages.Any(m => m.Contains("inclusiveMs")));
    if (fail) throw new ApplicationException();
   } catch (ApplicationException) { }
   Check(Harmony.GetPatchInfo(original)?.Owners.Contains("Volibear.NativeAcceptanceLoadProfiler") != true);
   Check(Harmony.GetPatchInfo(typeof(PreloadManager).GetMethod("LoadRunAssets")!)?.Owners.Contains("Volibear.NativeAcceptanceLoadProfiler") != true);
   Check(PreloadManager.Enabled); Check(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Normal);
  }
  Check(GD.Messages.Any(m => m.Contains("installed=16 ")));
  Check(GD.Messages.Count(m => m.Contains("inclusiveMs")) <= 28); // two sync+completion snapshots plus two top-12 flushes
  using (var scope = new NativeAcceptanceRunHost.GameplayBatchScope()) {
   var completions = new List<TaskCompletionSource>();
   for(int i=0;i<64;i++) { PreloadManager.LoadRunAssets(Array.Empty<CharacterModel>()); completions.Add(PreloadManager.Pending); }
   Parallel.ForEach(completions, pending => pending.SetResult());
   NativeAcceptanceRunHost.LoadProfiler.Flush("parallel-completion");
   Check(GD.Messages.Any(m => m.Contains("full-task-including-waits:success") && JsonDocument.Parse(m[m.IndexOf('{')..]).RootElement.GetProperty("calls").GetInt32()==64));
   var canceled = PreloadManager.LoadRunAssets(Array.Empty<CharacterModel>());PreloadManager.Pending.SetCanceled();
   Check(ReferenceEquals(canceled,PreloadManager.Pending.Task) && canceled.IsCanceled);
   NativeAcceptanceRunHost.LoadProfiler.Flush("cancellation");
   Check(GD.Messages.Any(m => m.Contains("full-task-including-waits:canceled")));
   using(System.Threading.ExecutionContext.SuppressFlow()) {
    var suppressed=PreloadManager.LoadRunAssets(Array.Empty<CharacterModel>());
    Check(System.Threading.ExecutionContext.IsFlowSuppressed());PreloadManager.Pending.SetResult();
   }
   Check(!System.Threading.ExecutionContext.IsFlowSuppressed());
   var late = PreloadManager.LoadRunAssets(Array.Empty<CharacterModel>());
   var profile = typeof(NativeAcceptanceRunHost.LoadProfiler).GetField("current",BindingFlags.NonPublic|BindingFlags.Static)!.GetValue(null)!;
   scope.Dispose(); int messages=GD.Messages.Count;
   PreloadManager.Pending.SetResult();NativeAcceptanceRunHost.LoadProfiler.Flush("after-dispose");
   Check(late.IsCompletedSuccessfully && GD.Messages.Count==messages);
   var samples=(System.Collections.IDictionary)profile.GetType().GetField("samples",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(profile)!;
   Check(samples.Count==0);
  }
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_PROFILE_LOADS", null);
  var outside = new NTransition(); outside.RoomFadeIn(false); Check(outside.Current!.Steps == 0);
  using (var scope = new NativeAcceptanceRunHost.GameplayBatchScope()) {
   var transition = new NTransition(); var task = transition.RoomFadeIn(false);
   Check(ReferenceEquals(task, transition.LastTask)); Check(task.IsCompletedSuccessfully);
   Check(transition.Callbacks == 1); Check(transition.Current!.Steps == 1);
   task = transition.RoomFadeIn(true); Check(!task.IsCompleted && transition.Current!.Steps == 0);
   SaveManager.Instance.PrefsSave.FastMode = FastModeType.Fast;
   task = transition.RoomFadeIn(false); Check(!task.IsCompleted && transition.Current!.Steps == 0);
   SaveManager.Instance.PrefsSave.FastMode = FastModeType.Instant;
   MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn = true;
   task = transition.RoomFadeIn(false); Check(!task.IsCompleted && transition.Current!.Steps == 0);
   MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn = false;
   transition.EarlyReturn = true; var old = transition.Current;
   transition.RoomFadeIn(false); Check(old!.Steps == 0);
   transition.Fail = true; bool originalError = false;
   try { transition.RoomFadeIn(false); } catch (ApplicationException e) { originalError = e.Message == "native fade failure"; }
   Check(originalError);
  }
  var fade = typeof(NTransition).GetMethod("RoomFadeIn")!;
  Check(Harmony.GetPatchInfo(fade)?.Owners.Contains("Volibear.NativeAcceptanceHiddenFade") != true);
  bool bound = false;
  try { using var scope = new NativeAcceptanceRunHost.GameplayBatchScope(); new NTransition { ExcessDuration = true }.RoomFadeIn(false); }
  catch (InvalidOperationException) { bound = true; }
  Check(bound); Check(PreloadManager.Enabled); Check(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Normal);
  bool artFailed = false;
  try {
   using var scope = new NativeAcceptanceRunHost.GameplayBatchScope();
   NativeAcceptanceArtResidency.FailValidation = true;
   NativeAcceptanceRunHost.GameplayBatchScope.ValidateArtIfActive();
  } catch (InvalidOperationException) { artFailed = true; }
  finally { NativeAcceptanceArtResidency.FailValidation = false; }
  Check(artFailed); Check(NativeAcceptanceArtResidency.Alive == 0);
  Check(PreloadManager.Enabled && SaveManager.Instance.PrefsSave.FastMode == FastModeType.Normal);
  Check(Harmony.GetPatchInfo(fade)?.Owners.Contains("Volibear.NativeAcceptanceHiddenFade") != true);
  NativeAcceptanceArtResidency.FailConstruction = true;
  bool constructorFailed = false;
  try { using var scope = new NativeAcceptanceRunHost.GameplayBatchScope(); }
  catch (InvalidOperationException) { constructorFailed = true; }
  finally { NativeAcceptanceArtResidency.FailConstruction = false; }
  Check(constructorFailed && Engine.MaxFps == 60 && PreloadManager.Enabled && SaveManager.Instance.PrefsSave.FastMode == FastModeType.Normal);
  Engine.MaxFps = 144; NativeAcceptanceRunHost.GameplayBatchScope.ReapplyIfActive();
  Check(Engine.MaxFps == 144); Engine.MaxFps = 60;
  var metrics = NativeAcceptanceRunHost.FrameMetrics.Capture();
  Check(metrics.Contains("processFramesTotal=100 renderedFramesTotal=90 processMsLatest=10.000 renderSetupCpuMsLatest=2.500"));
  Check(Performance.Reads == 7 && metrics.Contains("pipelineSpecializationCount=42"));
  Console.WriteLine($"NATIVE_ACCEPTANCE_SCOPE_PASS assertions={assertions} native-gameplay=NOT_RUN");
 }
}
'''
        output = self.build(runtime, USINGS + doubles + '\ninternal static class NativeAcceptanceRunHost {\n' + scopes() + '}\n' + program, [runtime.harmony], True)
        self.assertIn('NATIVE_ACCEPTANCE_SCOPE_PASS assertions=1067 native-gameplay=NOT_RUN', output)

    def test_profile_interfaces_compile_against_native_assemblies(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        fixture_api = '''
internal static class NativeFixtureApi {
 internal static IReadOnlySet<string> Keys(AssetCache cache) => cache.GetLoadedCacheAssets();
 internal static void Unload(AssetCache cache, IEnumerable<string> paths) => cache.UnloadAssets(paths);
 internal static Task Move(MegaCrit.Sts2.Core.Models.CardModel card) =>
  MegaCrit.Sts2.Core.Commands.CardPileCmd.Add(card, MegaCrit.Sts2.Core.Entities.Cards.PileType.Exhaust, skipVisuals:true);
}
'''
        self.build(runtime, USINGS + '\ninternal static class NativeAcceptanceRunHost {\n' + scopes() + '\n}' + fixture_api,
                   [runtime.data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll')], False,
                   [ROOT / 'src/Volibear/NativeAcceptanceArtResidency.cs'])

    def test_empty_draw_fixture_is_only_visual_skip(self):
        source = (ROOT / 'src/Volibear/CardFaceAcceptanceProbe.cs').read_text(encoding='utf-8')
        condition = 'if (branch == "empty" && (id is "C07" or "U43" or "R25" or "U17" or "R12") || branch == "insufficient" && id == "R25")'
        move = 'foreach (var card in pcs.DrawPile.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Exhaust,skipVisuals:true);'
        self.assertEqual(source.count('skipVisuals:'), 1)
        fixture = source[source.index(condition):source.index('foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp')]
        self.assertIn(move, fixture)
        self.assertIn('Expected ten original cards', source[:source.index(condition)])
        for name in ('NativeAcceptanceRunHost.cs', 'CardLifecycleAcceptanceProbe.cs'):
            self.assertNotIn('skipVisuals:', (ROOT / 'src/Volibear' / name).read_text(encoding='utf-8'))
        host = HOST.read_text(encoding='utf-8')
        for forbidden in ('ForceSync(', 'ViewportSetMeasureRenderTime(', 'SetRenderingMethod(', 'SetUseVsync('):
            self.assertNotIn(forbidden, host)
        self.assertEqual(host.count('{FrameMetrics.Capture()}'), 1)

    def test_only_gameplay_batches_and_real_boundaries(self):
        for name in ('CardFaceAcceptanceProbe.cs', 'CardLifecycleAcceptanceProbe.cs'):
            source = (ROOT / 'src/Volibear' / name).read_text(encoding='utf-8')
            self.assertEqual(source.count('using var gameplayBatch = new NativeAcceptanceRunHost.GameplayBatchScope();'), 1)
            for required in ('NativeAcceptanceRunHost.StartFresh', 'NativeAcceptanceRunHost.ExitToMainMenu', 'RequestEnqueue(action)'):
                self.assertIn(required, source)
        host = HOST.read_text(encoding='utf-8')
        for required in ('await NGame.Instance!.ReturnToMainMenu();await Frame();RequireClean();', 'StartNewSingleplayerRun(character,shouldSave:false', 'EnterRoom(new MapRoom())'):
            self.assertIn(required, host)
        for forbidden in ('TextureResidency', 'GetDependencies(', 'ResourceLoader.Load(', '.Instantiate(', 'TimeScale', 'TestMode.IsOn =', 'SavePrefs(', 'UnloadAssets(', 'CleanUp(', 'ref Task __result', 'Task.FromResult'):
            self.assertNotIn(forbidden, host)
        profiler = host.split('internal sealed class LoadProfiler', 1)[1].split('internal static class FrameMetrics', 1)[0]
        self.assertIn('WeakReference<LoadProfiler>', profiler)
        self.assertIn('ExecutionContext.SuppressFlow()', profiler)
        self.assertIn('static (completed, state)', profiler)
        for forbidden in ('.Result', '.Exception', 'await ', '.Wait(', 'GetAwaiter(', 'ref Task __result'):
            self.assertNotIn(forbidden, profiler)
        for name in ('PresentationAcceptanceProbe.cs', 'NativeRunAcceptanceProbe.cs'):
            self.assertNotIn('GameplayBatchScope', (ROOT / 'src/Volibear' / name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
