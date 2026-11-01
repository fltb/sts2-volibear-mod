using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text.Json;
using HarmonyLib;
using MegaCrit.Sts2.Core.Hooks;
using Volibear.Core;
using C = Volibear.Core.DomainCardContributions.Cause;
using R = Volibear.Core.DomainCardContributions.StackReceipt;

int assertions = 0;
void Check(bool ok, string why) { assertions++; if (!ok) throw new Exception(why); }
var r = new R(C.Enemy, 1);
Check(r.State == "enemy", "initial enemy");
r.Change(C.Enemy, 1, 2); Check(r.State == "enemy", "same-side stack");
r.Change(C.Unknown, 2, 1); Check(r.State == "enemy", "native decrement has no new source");
r.Change(C.Player, 1, 2); Check(r.State == "mixed", "player contribution detected despite original Applier");
r.Change(C.Unknown, 2, 1); Check(r.State == "mixed", "no invented contributor subtraction");
r.Change(C.Enemy, 1, 2); Check(r.State == "mixed", "mixed cannot become enemy again");
var p = new R(C.Player, 1); p.Change(C.Enemy, 1, 2); Check(p.State == "mixed", "reverse mixed");
var u = new R(C.Enemy, 1); u.Change(C.Unknown, 1, 2); Check(u.State == "unknown", "unknown positive contribution");
var d = new R(C.Enemy, 1); d.Check(2); Check(d.State == "unknown", "out-of-command write detected");
var z = new R(C.Enemy, 1); z.Change(C.Player, 1, 1); Check(z.State == "enemy", "no-op contributes nothing");
var q = new R(C.Player, 1); q.Change(C.Unknown, 1, 0); Check(q.State == "player", "player decrement retained");
var mismatch = new R(C.Enemy, 1); mismatch.Change(C.Enemy, 2, 3); Check(mismatch.State == "unknown", "unobserved prior write");
var sites = DomainCardContributions.VerifyNativeIl();
Check(sites.Length == 5 && sites.All(s => s.NativeCalls == 1 && s.ReplacedCalls == 1), "five actual native callsites");
var dict = (System.Collections.IDictionary)typeof(DomainCardContributions).GetField("Sites", BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
var rewrite = typeof(DomainCardContributions).GetMethod("Rewrite", BindingFlags.NonPublic | BindingFlags.Static)!;
foreach (System.Collections.DictionaryEntry pair in dict)
{
    var method = (MethodBase)pair.Key;
    bool rejected = false;
    try { rewrite.Invoke(null, new object[] { Array.Empty<CodeInstruction>(), method }); }
    catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { rejected = true; }
    Check(rejected, "missing native call must reject " + pair.Value);
    var original = PatchProcessor.GetOriginalInstructions(method).ToList();
    rejected = false;
    try { rewrite.Invoke(null, new object[] { original.Concat(original).ToList(), method }); }
    catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { rejected = true; }
    Check(rejected, "duplicate native call must reject " + pair.Value);
}
var passive = typeof(DomainPassiveEffects);
var flags = BindingFlags.NonPublic | BindingFlags.Static;
passive.GetMethod("Prepare", flags)!.Invoke(null, null);
var existing = new Harmony("Volibear.DomainPassiveEffects");
try
{
    foreach (var pair in new[] { ("Sources", "SourceCalls"), ("Commands", "CommandBody") })
        foreach (System.Collections.DictionaryEntry item in (System.Collections.IDictionary)passive.GetField(pair.Item1, flags)!.GetValue(null)!)
            existing.Patch((MethodBase)item.Key, transpiler: new HarmonyMethod(passive.GetMethod(pair.Item2, flags)!));
    DomainCardContributions.Install();
    foreach (System.Collections.DictionaryEntry item in dict)
        Check(Harmony.GetPatchInfo((MethodBase)item.Key)!.Transpilers.Count(patch => patch.owner == "Volibear.DomainCardContributions") == 1, "combined emitted native patch");
}
finally { new Harmony("Volibear.DomainCardContributions").UnpatchAll("Volibear.DomainCardContributions"); existing.UnpatchAll(existing.Id); }
Console.WriteLine(JsonSerializer.Serialize(new { assertions, sites, combinedNativeHarmonyEmission = true, actualAssemblySha256 = Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(typeof(Hook).Assembly.Location))), engineRun = false }));
