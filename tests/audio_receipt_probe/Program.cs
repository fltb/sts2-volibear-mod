using System.Collections;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using Volibear;
using Volibear.Core;
using Volibear.Presentation;

const BindingFlags flags = BindingFlags.Static | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
var observer = new Harmony("Volibear.AudioReceiptProbe.EmissionOnly");
var passive = new Harmony("Volibear.DomainPassiveEffects");
int checks = 0;
void Need(bool b) { if (!b) throw new Exception("Audio observer emission assertion " + checks); checks++; }
MethodInfo Method(Type t, string n) => t.GetMethod(n, flags)!;
try
{
    // Distinguish the two REAL native forwarding paths that the original oracle conflated.
    var commands = typeof(MegaCrit.Sts2.Core.Commands.PowerCmd);
    var modify = Method(commands, "ModifyAmount");
    var generic = commands.GetMethods().Single(m => m.Name == "Apply" && m.IsGenericMethodDefinition &&
        m.GetParameters().Length == 6 && m.GetParameters()[1].ParameterType == typeof(MegaCrit.Sts2.Core.Entities.Creatures.Creature))
        .MakeGenericMethod(typeof(MegaCrit.Sts2.Core.Models.Powers.StrengthPower));
    var direct = commands.GetMethods().Single(m => m.Name == "Apply" && !m.IsGenericMethod && m.GetParameters().Length == 7);
    foreach (var entry in new[] { generic, direct })
    {
        var state = entry.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()!.StateMachineType;
        if (state.IsGenericTypeDefinition) state = state.MakeGenericType(entry.GetGenericArguments());
        var il = PatchProcessor.GetOriginalInstructions(Method(state, "MoveNext")).ToList();
        var calls = il.Select((instruction, index) => (instruction, index)).Where(p => p.instruction.Calls(modify)).ToArray();
        Need(calls.Length == 1);
        var flag = il[calls[0].index - 1];
        Need(entry == generic ? flag.opcode == OpCodes.Ldfld && flag.operand is FieldInfo field && field.Name == "silent" && field.FieldType == typeof(bool)
            : flag.LoadsConstant(0));
    }
    Method(typeof(DomainPassiveEffects), "Prepare").Invoke(null, null);
    foreach (var pair in new[] { ("Sources", "SourceCalls"), ("Commands", "CommandBody") })
        foreach (DictionaryEntry row in (IDictionary)typeof(DomainPassiveEffects).GetField(pair.Item1, flags)!.GetValue(null)!)
            passive.Patch((MethodBase)row.Key, transpiler: new(Method(typeof(DomainPassiveEffects), pair.Item2)));
    PowerAudioReceipts.Install(); DomainCardContributions.Install();
    DomainRevivalEffects.InstallPatches(observer);
    var summonInstall = typeof(DomainSummonEffects).GetMethod("InstallPatches", flags);
    if (summonInstall is not null) summonInstall.Invoke(null, [observer]); else DomainSummonEffects.Install();
    Method(typeof(AudioReceiptProbe), "InstallObservers").Invoke(null, [observer]);
    var rows = (object[])Method(typeof(AudioReceiptProbe), "InspectRuntimeBoundaries").Invoke(null, null)!;
    Need(rows.Length == 2);
    var bridge = typeof(VolibearEffects).Assembly.GetType("Volibear.Presentation.VolibearPresentationBridge", true)!;
    var owner = bridge.GetNestedType("OwnerScope", BindingFlags.NonPublic)!;
    var play = Method(typeof(VolibearEffects), "PlaySound");
    foreach (string name in new[] { "PowerAudio", "CardAudio" })
    {
        var target = Method(owner, name);
        var code = PatchProcessor.GetCurrentInstructions(target).ToList();
        Need(code.Count(c => c.Calls(play)) == 1); // Original sound call not replaced.
        Need(code.Count(c => c.Calls(Method(typeof(AudioReceiptProbe), "BeforeSound"))) == 1);
        Need(code.Count(c => c.Calls(Method(typeof(AudioReceiptProbe), "AfterSound"))) == 1);
        Need(!code.Any(c => c.operand is MethodInfo m && m.DeclaringType == typeof(AudioReceiptProbe) && typeof(Task).IsAssignableFrom(m.ReturnType)));
        var il = new DynamicMethod("MissingDispatch", typeof(void), Type.EmptyTypes).GetILGenerator();
        var bad = PatchProcessor.GetOriginalInstructions(target, il).Where(c => !c.Calls(play)).ToList();
        try { _ = ((IEnumerable<CodeInstruction>)Method(typeof(AudioReceiptProbe), "ObserveSoundCall").Invoke(null, [bad, il])!).ToArray(); Need(false); }
        catch (TargetInvocationException e) { Need(e.InnerException is InvalidOperationException); }
        catch (InvalidOperationException) { Need(true); }
    }
    var publish = Method(typeof(CardPresentationReceipts), "Publish");
    var receiptIl = PatchProcessor.GetCurrentInstructions(publish).ToList();
    Need(receiptIl.Count(c => c.Calls(Method(typeof(AudioReceiptProbe), "CardCaptured"))) == 1);
    Need(receiptIl.Count(c => c.operand is MethodInfo m && m.DeclaringType == typeof(CardReceiptPolicy) && m.Name == "Notify") == 1);
    Need(Method(typeof(AudioReceiptProbe), "PowerCaptured").ReturnType == typeof(void));
    Need(Method(typeof(AudioReceiptProbe), "FrameEntered").ReturnType == typeof(void));
    Need(Method(typeof(AudioReceiptProbe), "AfterSound").ReturnType == typeof(void));
}
finally
{
    observer.UnpatchAll(observer.Id);
    observer.UnpatchAll("Volibear.DomainCardContributions");
    observer.UnpatchAll("Volibear.Presentation.PowerAudioReceipts");
    observer.UnpatchAll("Volibear.DomainSummonEffects");
    passive.UnpatchAll(passive.Id);
}
Console.WriteLine($"AUDIO_RECEIPT_PROBE_EMISSION_OK checks={checks}; native_fixture=NOT_RUN; playback=NOT_RUN; heard=false");
