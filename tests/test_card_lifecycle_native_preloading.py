"""Restore the native loading completion boundary only during same-run reentry."""
from pathlib import Path
import unittest
from tools.runtime_test import fixture_runtime
import test_native_acceptance_host as fixture_host

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/CardLifecycleAcceptanceProbe.cs'


def scope():
    source = SOURCE.read_text(encoding='utf-8')
    return 'internal sealed class NativeRoomPreloadingScope' + source.split('internal sealed class NativeRoomPreloadingScope', 1)[1].split('    private static object Snapshot()', 1)[0]


USINGS = '''using System;using System.Threading;using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.TestSupport;
'''
HOST = '''internal static class NativeAcceptanceRunHost {internal static class GameplayBatchScope {internal static bool IsActive=true;}}'''


class LifecycleNativePreloading(unittest.TestCase):
    def test_only_original_reentry_task_is_scoped_without_other_changes(self):
        source = SOURCE.read_text(encoding='utf-8')
        body = source.split('await RunManager.Instance.EnterRoom(new MapRoom());', 1)[1]
        self.assertIn('using (var nativePreloading = new NativeRoomPreloadingScope())\n                await RunManager.Instance.EnterRoomDebug(RoomType.Monster, model: ModelDb.Encounter<SlimesWeak>().ToMutable(), showTransition: false);\n            await Until(', body)
        self.assertEqual(source.count('new NativeRoomPreloadingScope()'), 1)
        self.assertEqual(source.count('RunManager.Instance.EnterRoomDebug('), 1)
        self.assertNotIn('AwaitRoomRetirement', source)
        self.assertNotIn('CARD_LIFECYCLE_ROOM_BOUNDARY', source)
        self.assertIn('!ReferenceEquals(next, oldCombat)', source)
        self.assertIn('ReferenceEquals(player, combat.Players.Single())', source)
        self.assertIn('await NativeAcceptanceRunHost.WaitForQuiet(combat, 1);', source)
        for forbidden in ('Delay(', 'Sleep(', 'CustomStep', 'ResourceLoader', 'GC.', 'FastMode', 'MaxFps', 'skipVisuals', 'Harmony', 'TestMode.IsOn ='):
            self.assertNotIn(forbidden, scope())

    def test_locked_native_preload_and_reentry_api_compile(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        api = '''internal static class NativeApi {
 internal static Task Enter() => MegaCrit.Sts2.Core.Runs.RunManager.Instance.EnterRoomDebug(
 MegaCrit.Sts2.Core.Rooms.RoomType.Monster,
 model: MegaCrit.Sts2.Core.Models.ModelDb.Encounter<MegaCrit.Sts2.Core.Models.Encounters.SlimesWeak>().ToMutable(), showTransition:false);
}'''
        fixture_host.NativeAcceptanceHostTests().build(runtime, USINGS + HOST + scope() + api,
            [runtime.data / name for name in ('sts2.dll', 'GodotSharp.dll')], False)

    def test_entire_original_task_restore_success_failure_cancellation_and_guards(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        doubles = '''
namespace MegaCrit.Sts2.Core.Debug {
 public class Release {public string Version="v0.107.1",Commit="59260271";}
 public class ReleaseInfoManager {public static ReleaseInfoManager Instance=new();public Release? ReleaseInfo=new();}
}
namespace MegaCrit.Sts2.Core.Assets {public static class PreloadManager {public static bool Enabled;}}
namespace MegaCrit.Sts2.Core.TestSupport {public static class TestMode {public static bool IsOn;}}
'''
        program = '''
internal static class Program {
 static int assertions;
 static void Check(bool ok){assertions++;if(!ok)throw new Exception("assertion "+assertions);}
 static void Valid(){
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","card-lifecycle");
  Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN","current-token");
  ReleaseInfoManager.Instance.ReleaseInfo=new();TestMode.IsOn=false;NativeAcceptanceRunHost.GameplayBatchScope.IsActive=true;
 }
 static async Task Enter(Task original){using(var preload=new NativeRoomPreloadingScope())await original;}
 static async Task Main(){
  foreach(string scenario in new[]{"card-lifecycle","native-suite"})foreach(bool previous in new[]{false,true})foreach(string result in new[]{"success","failure","cancel"}){
   Valid();Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO",scenario);PreloadManager.Enabled=previous;
   var native=new TaskCompletionSource();var error=new ApplicationException("original-native-entry-failure");
   using var cancellation=new CancellationTokenSource();
   var entered=Enter(native.Task);Check(PreloadManager.Enabled && !entered.IsCompleted);
   // This represents native loading/room-entry work after the original method yielded.
   Check(PreloadManager.Enabled);Exception? caught=null;
   if(result=="success")native.SetResult();
   else if(result=="failure")native.SetException(error);
   else {cancellation.Cancel();native.SetCanceled(cancellation.Token);}
   try{await entered;}catch(Exception e){caught=e;}
   Check(PreloadManager.Enabled==previous);
   Check(result=="success"?caught==null:result=="failure"?ReferenceEquals(caught,error):caught is OperationCanceledException canceled && canceled.CancellationToken==cancellation.Token);
  }
  foreach(bool previous in new[]{false,true})foreach(string invalid in new[]{"scenario","catalog","token","blank","version","commit","release","testmode","inactive"}){
   Valid();PreloadManager.Enabled=previous;
   switch(invalid){
    case "scenario":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","presentation-acceptance");break;
    case "catalog":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO","catalog-face-suite");break;
    case "token":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN",null);break;
    case "blank":Environment.SetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"," ");break;
    case "version":ReleaseInfoManager.Instance.ReleaseInfo!.Version="wrong";break;
    case "commit":ReleaseInfoManager.Instance.ReleaseInfo!.Commit="wrong";break;
    case "release":ReleaseInfoManager.Instance.ReleaseInfo=null;break;
    case "testmode":TestMode.IsOn=true;break;
    case "inactive":NativeAcceptanceRunHost.GameplayBatchScope.IsActive=false;break;
   }
   bool rejected=false;try{using var preload=new NativeRoomPreloadingScope();}catch(InvalidOperationException){rejected=true;}
   Check(rejected && PreloadManager.Enabled==previous);
  }
  foreach(bool previous in new[]{false,true}){
   Valid();PreloadManager.Enabled=previous;var preload=new NativeRoomPreloadingScope();preload.Dispose();
   Check(PreloadManager.Enabled==previous);PreloadManager.Enabled=!previous;preload.Dispose();Check(PreloadManager.Enabled==!previous);
  }
  Console.WriteLine($"NATIVE_ROOM_PRELOAD_PASS assertions={assertions}");
 }
}
'''
        output = fixture_host.NativeAcceptanceHostTests().build(runtime, USINGS + HOST + doubles + scope() + program, [], True)
        self.assertIn('NATIVE_ROOM_PRELOAD_PASS assertions=70', output)


if __name__ == '__main__':
    unittest.main()
