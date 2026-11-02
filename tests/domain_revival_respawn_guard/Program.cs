using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models.Monsters;
using Volibear.Core;

const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
var entry = typeof(TestSubject).GetMethod("RespawnMove", Flags)!;
var body = entry.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType.GetMethod("MoveNext", Flags)!;
var original = PatchProcessor.GetOriginalInstructions(body).ToList();
var helper = typeof(DomainAdditionalRevivalEffects).GetMethod("RespawnGuardIndex", BindingFlags.NonPublic | BindingFlags.Static)!;

int checks = 0;
void Need(bool condition, string message) { if (!condition) throw new Exception("respawn guard check: " + message); checks++; }
bool Calls(CodeInstruction instruction, string name) => instruction.operand is MethodInfo method &&
    method.DeclaringType == typeof(TestSubject) && method.Name == name;

var guard = (int)helper.Invoke(null, [original])!;
Need(guard > 0 && original[guard - 1].opcode == OpCodes.Switch, "empty-stack state dispatch");
Need(original[guard].opcode == OpCodes.Ldloc_1, "single receiver load before counter read");
Need(Calls(original[guard + 1], "get_Respawns"), "counter getter follows receiver");
Need(original[guard + 2].opcode == OpCodes.Stloc_2, "counter snapshot local");
Need(original[guard + 3].opcode == OpCodes.Ldloc_1, "setter receiver reload");
Need(original[guard + 4].opcode == OpCodes.Ldloc_2, "setter counter reload");
Need(original[guard + 5].LoadsConstant(1), "counter increment constant");
Need(original[guard + 6].opcode == OpCodes.Add, "counter increment operator");
Need(Calls(original[guard + 7], "set_Respawns"), "counter setter");
Console.WriteLine("RESPAWN_GUARD_POSITIVE_PASS actual-testsubject-il=true guard-index=" + guard);

int negatives = 0;
void Reject(Action<List<CodeInstruction>> mutate, string label)
{
    var copy = original.Select(instruction => new CodeInstruction(instruction)).ToList();
    mutate(copy);
    try { helper.Invoke(null, [copy]); }
    catch (TargetInvocationException error) when (error.InnerException is InvalidOperationException)
    {
        negatives++;
        Console.WriteLine("RESPAWN_GUARD_NEGATIVE_PASS " + label);
        return;
    }
    throw new Exception("respawn guard accepted mutated IL: " + label);
}
Reject(code => code[guard + 1] = new CodeInstruction(OpCodes.Nop), "missing-counter-getter");
Reject(code => code[guard + 2].opcode = OpCodes.Stloc_3, "wrong-counter-slot");
Reject(code => code[guard + 6].opcode = OpCodes.Sub, "wrong-counter-operator");
Reject(code => code[guard - 1].opcode = OpCodes.Nop, "non-empty-stack-guard-anchor");
Console.WriteLine("RESPAWN_GUARD_IL_PASS checks=" + checks + " negatives=" + negatives + " native-gameplay=NOT_RUN");
ReviveAwaitTests.Run();
