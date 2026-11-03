"""Observe original map travel Tasks through real Harmony; never drive a second trip."""
from pathlib import Path
import unittest
from tools.runtime_test import fixture_runtime
import test_native_acceptance_host as fixture_host

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/NativeProductFlowProbe.cs'
USINGS = '''using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
'''


def observation_source():
    source = SOURCE.read_text(encoding='utf-8')
    return 'private static MapTravelObservation?' + source.split('private static MapTravelObservation?', 1)[1].split('    // These two locked-game members', 1)[0]


WRAPPER = '''internal static class NativeProductFlowProbe {
 static void Need(bool ok, string message) { if(!ok) throw new InvalidOperationException(message); }
 static async Task Wait(Func<bool> done, string message) {
  var clock=System.Diagnostics.Stopwatch.StartNew();
  while(!done()) { if(clock.Elapsed.TotalSeconds>3) throw new TimeoutException(message); await Task.Delay(1); }
 }
 internal static MapTravelObservation Begin(NMapScreen map, MapCoord coord) {
  travelObservation=new();travelObservation.Expect(map,coord);return travelObservation;
 }
 internal static void Install(Harmony observer) {
  var method=AccessTools.Method(typeof(NMapScreen),nameof(NMapScreen.TravelToMapCoord),new[]{typeof(MapCoord)});
  Need(method.ReturnType==typeof(Task),"signature");
  observer.Patch(method,postfix:new HarmonyMethod(typeof(NativeProductFlowProbe),"TravelReturned"));
 }
'''


class NativeProductFlowTravel(unittest.TestCase):
    def test_observer_and_boundaries_are_read_only_and_complete(self):
        source = SOURCE.read_text(encoding='utf-8')
        observer = source.split('private static void TravelReturned', 1)[1].split(';', 1)[0]
        self.assertIn('Task __result', observer)
        self.assertIn('Observe(__instance, coord, __result)', observer)
        self.assertNotIn('ref ', observer)
        self.assertNotIn('TravelToMapCoord(', source)  # nameof only: never another direct trip
        step = source.split('private static async Task MapStep()', 1)[1].split('private static async Task RoomStep', 1)[0]
        self.assertLess(step.index('.Expect(map,'), step.index('map.OnMapPointSelectedLocally(next)'))
        self.assertLess(step.index('map.OnMapPointSelectedLocally(next)'), step.index('await travelObservation.CompletePending()'))
        self.assertLess(step.index('await travelObservation.CompletePending()'), step.index('Record("map-arrived"'))
        self.assertIn('await travelObservation.CompletePending();\n            await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);', source)
        self.assertIn('postfix: new HarmonyMethod(typeof(NativeProductFlowProbe), nameof(TravelReturned))', source)
        self.assertIn('observer.UnpatchAll(observer.Id);\n            travelObservation = null;', source)

    def test_locked_native_travel_signature_compiles(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        api = '''internal static Task NativeApi(NMapScreen screen, MapCoord coord) => screen.TravelToMapCoord(coord);'''
        fixture_host.NativeAcceptanceHostTests().build(runtime, USINGS + WRAPPER + observation_source() + api + '}',
            [runtime.data / name for name in ('sts2.dll', 'GodotSharp.dll', '0Harmony.dll')], False)

    def test_original_task_identity_pending_tail_faults_and_wrong_identity(self):
        runtime = fixture_runtime(self, 'sdk', 'harmony', root=ROOT)
        doubles = '''
namespace MegaCrit.Sts2.Core.Map { public readonly record struct MapCoord(int Row,int Col); }
namespace MegaCrit.Sts2.Core.Nodes.Screens.Map {
 public class NMapScreen {
  public TaskCompletionSource Pending=new(TaskCreationOptions.RunContinuationsAsynchronously); public int Calls;
  [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
  public Task TravelToMapCoord(MapCoord coord) { Calls++;return Pending.Task; }
 }
}
'''
        program = '''
internal static class Program {
 static int assertions;
 static void Check(bool ok) {assertions++;if(!ok) throw new Exception("assertion "+assertions);}
 static async Task<Exception?> Error(Task task) {try {await task;return null;}catch(Exception error){return error;}}
 static async Task Main() {
  var patch=new Harmony("Volibear.Test.MapTravel");NativeProductFlowProbe.Install(patch);
  var map=new NMapScreen();var coord=new MapCoord(1,2);
  var observation=NativeProductFlowProbe.Begin(map,coord);
  Task original=map.TravelToMapCoord(coord);Check(ReferenceEquals(original,map.Pending.Task));
  var complete=observation.CompletePending();await Task.Delay(10);
  Check(!complete.IsCompleted); // room/action can be done while native refresh tail remains pending
  map.Pending.SetResult();await complete;Check(map.Calls==1);await observation.CompletePending();
  map.Pending=new(TaskCreationOptions.RunContinuationsAsynchronously);observation.Expect(map,coord);
  original=map.TravelToMapCoord(coord);Check(ReferenceEquals(original,map.Pending.Task));
  var fault=new ApplicationException("native tail failure");map.Pending.SetException(fault);
  Check(ReferenceEquals(await Error(observation.CompletePending()),fault));
  foreach(int wrong in new[]{0,1,2}) {
   map=new();observation=NativeProductFlowProbe.Begin(map,coord);
   var actual=wrong==0?new NMapScreen():map;
   original=actual.TravelToMapCoord(wrong==1?new MapCoord(9,9):coord);
   if(wrong==2) actual.TravelToMapCoord(coord);
   actual.Pending.SetResult();Check(await Error(observation.CompletePending()) is InvalidOperationException);
  }
  map=new();observation=NativeProductFlowProbe.Begin(map,coord);original=map.TravelToMapCoord(coord);
  map.Pending.SetCanceled();Check(await Error(observation.CompletePending()) is TaskCanceledException);
  patch.UnpatchAll(patch.Id);
  Check(Harmony.GetPatchInfo(typeof(NMapScreen).GetMethod("TravelToMapCoord")!)?.Owners.Contains(patch.Id)!=true);
  Console.WriteLine($"MAP_TRAVEL_OBSERVATION_PASS assertions={assertions}");
 }
}
'''
        output = fixture_host.NativeAcceptanceHostTests().build(runtime,
            USINGS + doubles + WRAPPER + observation_source() + '}' + program, [runtime.harmony], True)
        self.assertIn('MAP_TRAVEL_OBSERVATION_PASS assertions=10', output)


if __name__ == '__main__':
    unittest.main()
