"""The actual C# coordinator: same-process order, strict envelopes and failure exits."""
from pathlib import Path
import unittest
from tools.runtime_test import fixture_runtime
import test_native_acceptance_host as fixture_host

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/CatalogFaceSuite.cs'


def coordinator():
    return SOURCE.read_text(encoding='utf-8').replace('namespace Volibear;', 'namespace Volibear {') + '\n}\n'


PROBES = '''
namespace Volibear {
 internal static class Trace {
  internal static System.Collections.Generic.List<string> Calls=new();
  internal static string? Fail;internal static int CleanCalls;internal static string? Selection;
  internal static Exception Error=new ApplicationException("original-stage-failure");
  internal static void Hit(string name) {Calls.Add(name);if(name=="clean")CleanCalls++;
   if(Fail==name || Fail=="clean2" && name=="clean" && CleanCalls==2)throw Error;}
 }
 internal static class NativeAcceptanceRunHost {
  internal sealed record ExitReceipt(bool RunNull,bool CombatNull,bool InProgress,bool QueueEmpty,bool ActionNull,int HistoryVisible);
  internal static Task WaitForQuiet(CombatState state,int turn) {Trace.Hit("quiet");return Task.CompletedTask;}
  internal static Task ExitToMainMenu() {Trace.Hit("exit");return Task.CompletedTask;}
  internal static void RequireClean() => Trace.Hit("clean");
  internal static Task<CombatState> StartFresh(EncounterModel encounter,string seed) {Trace.Hit("fresh");return Task.FromResult<CombatState>(null!);}
  internal static ExitReceipt CleanState() => new(true,true,false,true,true,0);
 }
 internal static class PresentationAcceptanceProbe {
  internal static Task Run(CombatState state,bool managed=false) {if(!managed)throw new Exception("premature presentation quit");Trace.Hit("presentation");return Task.CompletedTask;}
 }
 internal static class CardFaceAcceptanceProbe {
  internal static void Install(bool subscribe=true) {if(subscribe)throw new Exception("competing turn driver");Trace.Hit("install");}
  internal static Task RunBatch(CombatState state,string selection,bool managed=false) {if(!managed)throw new Exception("premature face quit");Trace.Selection=selection;Trace.Hit("faces");return Task.CompletedTask;}
 }
}
'''


class CatalogFaceSuiteNative(unittest.TestCase):
    def test_entry_reuses_original_managed_probes_without_pacing_catalog(self):
        source = SOURCE.read_text(encoding='utf-8')
        entry = (ROOT / 'src/Volibear/ModEntry.cs').read_text(encoding='utf-8')
        self.assertIn('else if (scenario == "catalog-face-suite")\n            {\n                DevelopmentBootstrap.Install(installDriver: false);\n                CatalogFaceSuite.Install();', entry)
        ordered = ['WaitForQuiet(initial, 1)', 'CATALOG_FACE_BEGIN ', 'PresentationAcceptanceProbe.Run(initial, managed: true)',
                   'ExitToMainMenu()', 'CardFaceAcceptanceProbe.Install(subscribe: false)', 'StartFresh(',
                   'CardFaceAcceptanceProbe.RunBatch(faces, selection, managed: true)', 'CATALOG_FACE_RESULT ', 'SHUTDOWN_BEGIN ', 'NGame.Instance!.Quit()']
        positions = [source.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(source.count('RequireClean();'), 2)
        self.assertEqual(source.count('NGame.Instance!.Quit()'), 1)
        self.assertIn('CombatManager.Instance.TurnStarted -= Start;', source)
        for forbidden in ('GameplayBatchScope', 'FastMode', 'MaxFps', 'PreloadManager', 'HiddenRoomFade', 'ArtResidency', 'Task.Run(', 'TestMode.IsOn ='):
            self.assertNotIn(forbidden, source)
        primary = (ROOT / 'src/Volibear/NativeVerificationSuite.cs').read_text(encoding='utf-8')
        self.assertIn('Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH") ?? "", managed: true', primary)
        self.assertEqual(primary.count('await Phase('), 7)

    def test_locked_native_api_compile(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        fixture_host.NativeAcceptanceHostTests().build(runtime, coordinator() + PROBES,
            [runtime.data / name for name in ('sts2.dll', 'GodotSharp.dll')], False)

    def test_actual_coordinator_success_guard_and_stage_failure_contracts(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        doubles = '''
namespace Godot {
 public class SceneTree {public static int? Code;public void Quit(int code=0){Code=code;}}
 public static class Engine {public static object GetMainLoop()=>new SceneTree();}
 public static class GD {public static System.Collections.Generic.List<string> Lines=new();public static void Print(string value)=>Lines.Add(value);public static void PrintErr(string value)=>Lines.Add(value);}
}
namespace MegaCrit.Sts2.Core.Combat {public class CombatState {} public class CombatManager {public static CombatManager Instance=new();public event Action<CombatState>? TurnStarted;}}
namespace MegaCrit.Sts2.Core.Debug {public class Release {public string Version="v0.107.1",Commit="59260271";} public class ReleaseInfoManager {public static ReleaseInfoManager Instance=new();public Release? ReleaseInfo=new();}}
namespace MegaCrit.Sts2.Core.Models {public class EncounterModel {} public static class ModelDb {public static T Encounter<T>() where T:EncounterModel,new()=>new();}}
namespace MegaCrit.Sts2.Core.Models.Encounters {public class SlimesWeak:EncounterModel {}}
namespace MegaCrit.Sts2.Core.Nodes {public class NGame {public static NGame Instance=new();public static int Quits;public void Quit(){Quits++;}}}
namespace MegaCrit.Sts2.Core.TestSupport {public static class TestMode {public static bool IsOn;}}
'''
        program = '''
internal static class Program {
 static int assertions;
 static void Check(bool ok){assertions++;if(!ok)throw new Exception("assertion "+assertions);}
 static void Reset(){
  Volibear.Trace.Calls.Clear();Volibear.Trace.Fail=null;Volibear.Trace.CleanCalls=0;GD.Lines.Clear();SceneTree.Code=null;NGame.Quits=0;
  ReleaseInfoManager.Instance.ReleaseInfo=new();TestMode.IsOn=false;
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","catalog-face-suite");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_MODE","cards");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN","current-token");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH","B01-base-plain,B02-upgrade-plain");
 }
 static JsonElement Receipt(string prefix)=>JsonDocument.Parse(GD.Lines.Single(l=>l.Contains(prefix)).Split(prefix)[1]).RootElement;
 static void Failed(){Check(SceneTree.Code==2 && NGame.Quits==0);Check(!GD.Lines.Any(l=>l.Contains("CATALOG_FACE_RESULT ")));Check(GD.Lines.Count(l=>l.Contains("CATALOG_FACE_ERROR "))==1);}
 static async Task Main(){
  Reset();await Volibear.CatalogFaceSuite.Run(new CombatState());
  Check(SceneTree.Code==0 && NGame.Quits==1);
  Check(Volibear.Trace.Calls.SequenceEqual(new[]{"quiet","presentation","exit","clean","install","fresh","faces","clean"}));
  Check(Volibear.Trace.Selection=="B01-base-plain,B02-upgrade-plain");
  var begin=Receipt("CATALOG_FACE_BEGIN ");var end=Receipt("CATALOG_FACE_RESULT ");
  Check(begin.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"schema","token","pid","cases","presentationMode"}));
  Check(end.EnumerateObject().Select(p=>p.Name).SequenceEqual(new[]{"schema","token","pid","cases","completed","finished","processRestarts","cleanup"}));
  Check(begin.GetProperty("pid").GetInt32()==Environment.ProcessId && end.GetProperty("pid").GetInt32()==Environment.ProcessId);
  Check(begin.GetProperty("presentationMode").GetString()=="cards" && end.GetProperty("token").GetString()=="current-token");
  Check(end.GetProperty("completed").EnumerateArray().Select(v=>v.GetString()).SequenceEqual(new[]{"presentation","card-faces"}));
  Check(end.GetProperty("cases").EnumerateArray().Select(v=>v.GetString()).SequenceEqual(new[]{"B01-base-plain","B02-upgrade-plain"}));
  Check(end.GetProperty("finished").GetBoolean() && end.GetProperty("processRestarts").GetInt32()==0);
  var cleanup=end.GetProperty("cleanup");
  Check(cleanup.EnumerateObject().Count()==6 && cleanup.GetProperty("RunNull").GetBoolean() && cleanup.GetProperty("CombatNull").GetBoolean() && !cleanup.GetProperty("InProgress").GetBoolean() && cleanup.GetProperty("QueueEmpty").GetBoolean() && cleanup.GetProperty("ActionNull").GetBoolean() && cleanup.GetProperty("HistoryVisible").GetInt32()==0);
  foreach(var failure in new[]{"quiet","presentation","exit","clean","install","fresh","faces","clean2"}){
   Reset();Volibear.Trace.Fail=failure;await Volibear.CatalogFaceSuite.Run(new CombatState());Failed();
   Check(GD.Lines.Last().Contains("original-stage-failure"));
   if(failure=="presentation")Check(!Volibear.Trace.Calls.Contains("faces"));
  }
  foreach(var invalid in new[]{"scenario","mode","token","empty","duplicate","version","commit","release","testmode"}){
   Reset();switch(invalid){
    case "scenario":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","presentation-acceptance");break;
    case "mode":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_MODE","all");break;
    case "token":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"," ");break;
    case "empty":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH","");break;
    case "duplicate":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH","B01-base-plain,B01-base-plain");break;
    case "version":ReleaseInfoManager.Instance.ReleaseInfo!.Version="wrong";break;
    case "commit":ReleaseInfoManager.Instance.ReleaseInfo!.Commit="wrong";break;
    case "release":ReleaseInfoManager.Instance.ReleaseInfo=null;break;
    case "testmode":TestMode.IsOn=true;break;
   }
   await Volibear.CatalogFaceSuite.Run(new CombatState());Failed();Check(Volibear.Trace.Calls.Count==0);Check(!GD.Lines.Any(l=>l.Contains("CATALOG_FACE_BEGIN ")));
  }
  Console.WriteLine($"CATALOG_FACE_COORDINATOR_PASS assertions={assertions}");
 }
}
'''
        output = fixture_host.NativeAcceptanceHostTests().build(runtime, coordinator() + PROBES + doubles + program, [], True)
        self.assertIn('CATALOG_FACE_COORDINATOR_PASS assertions=', output)


if __name__ == '__main__':
    unittest.main()
