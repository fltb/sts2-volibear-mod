"""Execute the production timing helper; verify existing suite order and cleanup."""
from pathlib import Path
import re
import tempfile
import unittest
from tools.runtime_test import fixture_runtime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/NativeVerificationSuite.cs'
STAGES = ['domain-suppression', 'architect-ending', 'card-faces', 'card-lifecycle',
          'presentation', 'product-flow', 'save-load-same-process']


class NativeSuitePhaseTiming(unittest.TestCase):
    def test_existing_phase_order_and_native_cleanup_are_preserved(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'await Phase\("([^"]+)"', source), STAGES)
        self.assertEqual(re.findall(r'completed.Add\("([^"]+)"', source), STAGES)
        self.assertEqual(source.count('NATIVE_SUITE_PHASE '), 1)
        self.assertEqual(source.count('NativeAcceptanceRunHost.RequireClean();'), 5)
        self.assertEqual(source.count('NativeAcceptanceRunHost.ExitToMainMenu('), 3)
        self.assertEqual(source.count('NativeAcceptanceRunHost.StartFresh('), 3)
        self.assertEqual(source.count('NGame.Instance!.Quit()'), 1)
        for call in ('DomainSuppressionAcceptanceProbe.RunManaged()', 'ArchitectEndingAcceptanceProbe.RunManaged()',
                     'CardFaceAcceptanceProbe.RunBatch(', 'CardLifecycleAcceptanceProbe.RunBatch(',
                     'PresentationAcceptanceProbe.Run(', 'NativeProductFlowProbe.Run()', 'SaveLoadContractProbe.Run('):
            self.assertEqual(source.count(call), 1)
        for forbidden in ('Task.WhenAll', 'Task.Run(', 'Task.Delay(', 'continue;', 'TestMode.IsOn ='):
            self.assertNotIn(forbidden, source)
        self.assertIn('await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);\n                completed.Add("save-load-same-process");', source)

    def test_helper_measures_full_await_once_and_propagates_original_failures(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        source = SOURCE.read_text(encoding='utf-8')
        helper = 'internal static async Task Phase' + source.split('internal static async Task Phase', 1)[1].split('    private static async Task Run', 1)[0]
        program = '''using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
internal static class GD { internal static List<string> Lines = new(); internal static void Print(string line) => Lines.Add(line); }
internal static class NativeVerificationSuite {
''' + helper + '''
}
internal static class Program {
 static int assertions;
 static void Check(bool ok) { assertions++; if (!ok) throw new Exception("assertion " + assertions); }
 static JsonElement Last() => JsonDocument.Parse(GD.Lines[^1].Split("NATIVE_SUITE_PHASE ")[1]).RootElement;
 static async Task Main() {
  int calls = 0;
  var pending = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
  var task = NativeVerificationSuite.Phase("success", () => { calls++; return pending.Task; });
  Check(calls == 1 && GD.Lines.Count == 0 && !task.IsCompleted);
  await Task.Delay(20); pending.SetResult(); await task;
  Check(GD.Lines.Count == 1);
  Check(Last().GetProperty("name").GetString() == "success" && Last().GetProperty("status").GetString() == "success");
  Check(Last().GetProperty("elapsedMs").GetInt64() >= 10);
  foreach (bool synchronous in new[] { false, true }) {
   var error = new InvalidOperationException("original failure");
   Exception? observed = null; int before = GD.Lines.Count;
   try { await NativeVerificationSuite.Phase("failure", () => { if (synchronous) throw error; return Task.FromException(error); }); }
   catch (Exception caught) { observed = caught; }
   Check(ReferenceEquals(error, observed)); Check(GD.Lines.Count == before + 1);
   Check(Last().GetProperty("status").GetString() == "failure");
   Check(Last().GetProperty("elapsedMs").GetInt64() >= 0);
  }
  Console.WriteLine($"SUITE_PHASE_HELPER_PASS assertions={assertions}");
 }
}
'''
        (ROOT / '.local').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='suite-phase-', dir=ROOT / '.local') as directory:
            folder = Path(directory)
            project = folder / 'Phase.csproj'
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                               '<TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><NuGetAudit>false</NuGetAudit>'
                               '</PropertyGroup></Project>', encoding='utf-8')
            (folder / 'Program.cs').write_text(program, encoding='utf-8')
            result = runtime.run(project, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('SUITE_PHASE_HELPER_PASS assertions=12', result.stdout)


if __name__ == '__main__':
    unittest.main()
