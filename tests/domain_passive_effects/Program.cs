using System.Reflection;
using System.Reflection.Emit;
using System.Collections;
using HarmonyLib;
using Volibear.Core;

// Real native metadata + real Harmony IL generation; no native gameplay or fake models.
int checks = 0;
void Check(bool result, string label) { checks++; if (!result) throw new Exception(label); }
var yes = new DomainPassiveEffects.Decision();
Check(yes.Decide(true) && yes.Cancelled, "uncommitted contribution cancelled");
Check(yes.Decide(false) && yes.Cancelled, "cancelled contribution never replayed after domain exit");
var no = new DomainPassiveEffects.Decision();
Check(!no.Decide(false) && no.State == 1, "outside-domain commit allowed");
Check(!no.Decide(true), "already committed result not rolled back after domain entry");
var t = typeof(DomainPassiveEffects);
var flags = BindingFlags.Static | BindingFlags.NonPublic;
var gen = t.GetField("_generation", flags)!;
int prior = (int)gen.GetValue(null)!;
DomainPassiveEffects.Reset();
Check((int)gen.GetValue(null)! == prior + 1, "reset advances generation");
t.GetMethod("Prepare", flags)!.Invoke(null, null);
var sources = (IDictionary)t.GetField("Sources", flags)!.GetValue(null)!;
var commands = (IDictionary)t.GetField("Commands", flags)!.GetValue(null)!;
Check(sources.Count == 12 && commands.Count == 3, "exact twelve source and three command bodies");
var harmony = new Harmony("Volibear.Passive.NativeIlTest");
try
{
    var resetMethod = typeof(MegaCrit.Sts2.Core.Combat.CombatManager).GetMethod("Reset", [typeof(bool)])!;
    Check(resetMethod.ReturnType == typeof(void) && !resetMethod.IsStatic, "exact native Reset(bool) shape");
    harmony.Patch(resetMethod, prefix: new HarmonyMethod(t.GetMethod("BeforeNativeReset", flags)!));
    Check(true, "actual abandon/menu reset detour emitted without replacing native reset");
    foreach (DictionaryEntry entry in sources)
    {
        var method = (MethodBase)entry.Key;
        harmony.Patch(method, transpiler: new HarmonyMethod(t.GetMethod("SourceCalls", flags)!));
        Check(true, "actual source IL detour emitted: " + method.DeclaringType);
    }
    foreach (DictionaryEntry entry in commands)
    {
        var method = (MethodBase)entry.Key;
        harmony.Patch(method, transpiler: new HarmonyMethod(t.GetMethod("CommandBody", flags)!));
        Check(true, "actual command IL detour emitted: " + method.DeclaringType);
    }
    foreach (DictionaryEntry entry in sources)
    {
        var method = (MethodBase)entry.Key;
        var original = PatchProcessor.GetOriginalInstructions(method).ToList();
        original.RemoveAll(c => c.operand is MethodInfo m && m.DeclaringType?.Name == "PowerCmd" && m.Name == "Apply" ||
                                c.operand is MethodInfo n && n.DeclaringType?.Name == "CreatureCmd" && n.Name == "GainBlock");
        try
        {
            _ = ((IEnumerable<CodeInstruction>)t.GetMethod("SourceCalls", flags)!.Invoke(null, [original, method])!).ToArray();
            Check(false, "missing callsite must reject");
        }
        catch (TargetInvocationException) { Check(true, "source IL mutation rejected"); }
    }
    foreach (DictionaryEntry entry in commands)
    {
        var method = (MethodBase)entry.Key;
        var il = new DynamicMethod("Mutation", typeof(void), Type.EmptyTypes).GetILGenerator();
        var original = PatchProcessor.GetOriginalInstructions(method, il).ToList();
        original.RemoveAll(c => c.operand is MethodInfo m && m.Name == "SetResult");
        try
        {
            _ = ((IEnumerable<CodeInstruction>)t.GetMethod("CommandBody", flags)!.Invoke(null, [original, il, method])!).ToArray();
            Check(false, "missing native completion anchor must reject");
        }
        catch (TargetInvocationException) { Check(true, "command IL mutation rejected"); }
    }
}
finally { harmony.UnpatchAll(harmony.Id); }
Console.WriteLine($"PASS {checks} production-decision/native-IL checks; native passive behavior and D17 gameplay NOT RUN.");
