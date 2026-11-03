"""Public-only product pacing restoration; SDK execution and real native API compile."""
from pathlib import Path
import unittest
from tools.runtime_test import fixture_runtime
import test_native_acceptance_host as fixture_host

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/NativeProductFlowProbe.cs'
USINGS = '''using System;
using Godot;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using MegaCrit.Sts2.Core.TestSupport;
'''


def helper():
    source = SOURCE.read_text(encoding='utf-8')
    return 'internal sealed class PublicPacingScope' + source.split('internal sealed class PublicPacingScope', 1)[1].split('    internal static async Task Run()', 1)[0]


class NativeProductFlowPacing(unittest.TestCase):
    def test_only_public_preferences_cover_unchanged_ordinary_run(self):
        source = SOURCE.read_text(encoding='utf-8')
        scope = helper()
        for forbidden in ('PreloadManager', 'Harmony', 'CustomStep', 'NativeAcceptanceArtResidency',
                          'GameplayBatchScope', 'TimeScale', 'SavePrefs', 'PhysicsTicks', 'VSync'):
            self.assertNotIn(forbidden, scope)
        run = source.split('    internal static async Task Run()', 1)[1]
        self.assertEqual(run.count('using var pacing = new PublicPacingScope();'), 1)
        self.assertLess(run.index('NativeAcceptanceRunHost.RequireClean();'), run.index('using var pacing'))
        self.assertLess(run.index('using var pacing'), run.index('StartNewSingleplayerRun('))
        self.assertLess(run.index('StartNewSingleplayerRun('), run.index('ExitToMainMenu(enterMapFirst: false)'))
        self.assertIn('"VOLIBEAR-PRODUCT-FLOW", GameMode.Standard, 0', run)
        self.assertIn('stateFixtures = false, testMode = TestMode.IsOn', run)
        self.assertNotIn('FastMode =', run)
        self.assertNotIn('MaxFps =', run)
        self.assertIn('ActionQueueSynchronizer.RequestEnqueue(action)', source)

    def test_native_public_api_compile(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        fixture_host.NativeAcceptanceHostTests().build(runtime, USINGS + helper(),
            [runtime.data / name for name in ('sts2.dll', 'GodotSharp.dll')], False)

    def test_restoration_noop_guards_and_constructor_failure(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        doubles = '''
namespace Godot {
 public static class Engine {
  private static int cap=60; public static bool FailNextWrite;
  public static int MaxFps { get => cap; set { if(FailNextWrite) { FailNextWrite=false; throw new ApplicationException("setter failure"); } cap=value; } }
 }
 public static class GD { public static int Prints; public static void Print(string text) { Prints++; } }
}
namespace MegaCrit.Sts2.Core.Settings { public enum FastModeType { Normal, Fast, Instant } }
namespace MegaCrit.Sts2.Core.Saves {
 public class Preferences { public FastModeType FastMode {get;set;} }
 public class SaveManager { public static SaveManager Instance {get;}=new(); public Preferences PrefsSave {get;}=new(); }
}
namespace MegaCrit.Sts2.Core.Debug {
 public class Release { public string Version="v0.107.1", Commit="59260271"; }
 public class ReleaseInfoManager { public static ReleaseInfoManager Instance {get;}=new(); public Release? ReleaseInfo {get;set;}=new(); }
}
namespace MegaCrit.Sts2.Core.TestSupport { public static class TestMode {public static bool IsOn {get;set;}} }
'''
        program = '''
internal static class Program {
 static int assertions;
 static void Check(bool value) {assertions++; if(!value) throw new Exception("assertion "+assertions);}
 static void Unchanged() => Check(Engine.MaxFps==60 && SaveManager.Instance.PrefsSave.FastMode==FastModeType.Normal);
 static void Rejected() {
  bool rejected=false; try {using var scope=new PublicPacingScope();} catch(InvalidOperationException) {rejected=true;}
  Check(rejected); Unchanged();
 }
 static void Main() {
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","native-suite");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN","pacing-test");
  foreach(var cap in new[]{0,60,144}) foreach(var speed in Enum.GetValues<FastModeType>()) foreach(var fail in new[]{false,true}) {
   Engine.MaxFps=cap; SaveManager.Instance.PrefsSave.FastMode=speed;
   var scope=new PublicPacingScope();
   try {Check(Engine.MaxFps==240 && SaveManager.Instance.PrefsSave.FastMode==FastModeType.Instant); if(fail) throw new ApplicationException();}
   catch(ApplicationException) {} finally {scope.Dispose();scope.Dispose();}
   Check(Engine.MaxFps==cap && SaveManager.Instance.PrefsSave.FastMode==speed);
  }
  Engine.MaxFps=60; SaveManager.Instance.PrefsSave.FastMode=FastModeType.Normal;
  foreach(var scenario in new string?[]{null,"presentation","native-product-flow","native-run","card-face-acceptance","domain-suppression","architect-ending"}) {
   Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO",scenario);
   Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN",null); ReleaseInfoManager.Instance.ReleaseInfo=null;TestMode.IsOn=true;
   int prints=GD.Prints; using(var scope=new PublicPacingScope()) {Unchanged();} Unchanged();Check(GD.Prints==prints);
  }
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","native-suite");TestMode.IsOn=false;ReleaseInfoManager.Instance.ReleaseInfo=new();
  foreach(var token in new string?[]{null,""," "}) {Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN",token);Rejected();}
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN","pacing-test");
  ReleaseInfoManager.Instance.ReleaseInfo!.Version="wrong";Rejected();
  ReleaseInfoManager.Instance.ReleaseInfo=new(){Commit="wrong"};Rejected();
  ReleaseInfoManager.Instance.ReleaseInfo=null;Rejected();ReleaseInfoManager.Instance.ReleaseInfo=new();
  TestMode.IsOn=true;Rejected();TestMode.IsOn=false;
  Engine.FailNextWrite=true;bool constructorFailed=false;
  try {using var scope=new PublicPacingScope();}catch(ApplicationException e){constructorFailed=e.Message=="setter failure";}
  Check(constructorFailed);Unchanged();
  Console.WriteLine($"PRODUCT_PUBLIC_PACING_PASS assertions={assertions}");
 }
}
'''
        output = fixture_host.NativeAcceptanceHostTests().build(runtime, USINGS + doubles + helper() + program, [], True)
        self.assertIn('PRODUCT_PUBLIC_PACING_PASS assertions=73', output)


if __name__ == '__main__':
    unittest.main()
