using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;
using Volibear.Presentation;

// Focused evidence fixture for the shared PowerCmd.MoveNext IL. It compiles the current
// production sources, pins the locked native completion shape, then emits the real
// PowerAudioReceipts and DomainPlayerDebuffContributions transpilers over it in the
// actual install order. No game launch, no copied adapter, no prebuilt host DLL.
internal static class Program
{
    private const string BindingError = "Debuff native amount result local changed.";
    private static readonly MethodInfo AudioBody = AccessTools.Method(typeof(PowerAudioReceipts), "CommandBody")!;
    private static readonly MethodInfo DebuffGate = AccessTools.Method(typeof(DomainPlayerDebuffContributions), "CommitGate")!;
    private static readonly MethodInfo AudioClose = AccessTools.Method(typeof(PowerAudioReceipts), "Close")!;
    private static readonly MethodInfo AudioBegin = AccessTools.Method(typeof(PowerAudioReceipts), "BeginCommit")!;
    private static readonly MethodInfo CancelCommit = AccessTools.Method(
        typeof(DomainPlayerDebuffContributions), "CancelCommit")!;
    private static readonly Type? AudioFrame = typeof(PowerAudioReceipts).GetNestedType("Frame", BindingFlags.NonPublic);
    private static readonly MethodInfo ModifyNative = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount),
        [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)])!;
    private static readonly MethodInfo ApplyNative = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Apply),
        [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature),
            typeof(CardModel), typeof(bool)])!;
    private static int checks;

    private static void Main()
    {
        var applyBody = Body(ApplyNative);
        var modifyBody = Body(ModifyNative);
        Console.WriteLine("LOCKED_METHODS apply=" + applyBody.DeclaringType!.FullName + " modify=" + modifyBody.DeclaringType!.FullName);
        Dump("ORIGINAL-MODIFY", modifyBody);

        var originalModify = Original(modifyBody);
        var originalTail = BeforeSignal(originalModify);
        Need(originalTail is { Count: >= 1 } && originalTail[^1].opcode == OpCodes.Ldloc_1,
            "locked ModifyAmount feeds SetResult from int local 1");
        Need(modifyBody.GetMethodBody()!.LocalVariables[1].LocalType == typeof(int),
            "locked ModifyAmount result local 1 is int");

        // Presentation installs later, but Harmony recomposes audio BEFORE the debuff
        // transpiler. Exercise that observed pair order and pristine debuff binding here;
        // FullInstallChainTests covers the other cooperating production owners as well.
        var debuffOnly = Emit(DebuffGate, originalModify, modifyBody);
        Need(GuardShape(debuffOnly, modifyBody, audioObserver: false),
            "debuff guard on pristine native IL keeps the result-local binding");
        var audioOutput = Emit(AudioBody, originalModify, modifyBody);
        var audioTail = BeforeSignal(audioOutput);
        Need(audioTail is { Count: >= 3 } &&
            audioTail[^1].opcode == OpCodes.Call && Equals(audioTail[^1].operand, AudioClose) &&
            audioTail[^2].operand is LocalBuilder { LocalType: var frame } && frame == AudioFrame &&
            audioTail[^3].opcode == OpCodes.Ldloc_1,
            "audio inserts exact ldloc Frame; call Close(Frame) after the int result load");
        var cooperated = Emit(DebuffGate, audioOutput, modifyBody);
        Need(GuardShape(cooperated, modifyBody, audioObserver: true),
            "debuff guard accepts only the exact audio terminal observer before SetResult");

        // The cancel branch must still execute the audio observer. Leave targets the native
        // successful epilogue, which precedes the result-branch Close; it cannot jump past Close.
        int successClose = Signal(cooperated) - 1;
        Need(cooperated[successClose].opcode == OpCodes.Call && Equals(cooperated[successClose].operand, AudioClose),
            "success branch keeps exact audio Close immediately before SetResult");
        Need(cooperated.Count(c => c.opcode == OpCodes.Call && Equals(c.operand, AudioClose)) == 2,
            "both audio terminal branches keep their Close");
        var state = AccessTools.Field(modifyBody.DeclaringType!, "<>1__state")!;
        var labels = LabelIndex(cooperated);
        var leaves = cooperated.Select((c, i) => (c, i)).Where(x => x.c.opcode == OpCodes.Leave).ToArray();
        Need(leaves.Length == audioOutput.Count(c => c.opcode == OpCodes.Leave) + 1,
            "debuff guard adds exactly one native Leave");
        Need(leaves.Any(x => x.c.operand is Label target && labels.TryGetValue(target, out int done) &&
            done > 0 && done < successClose && cooperated[done].opcode == OpCodes.Ldarg_0 &&
            cooperated[done + 1].opcode == OpCodes.Ldc_I4_S && Convert.ToInt32(cooperated[done + 1].operand) == -2 &&
            cooperated[done + 2].opcode == OpCodes.Stfld && Equals(cooperated[done + 2].operand, state)),
            "debuff cancel Leave targets the native successful epilogue before audio Close");
        Need(cooperated.Count(c => c.opcode == OpCodes.Stloc_1) ==
            audioOutput.Count(c => c.opcode == OpCodes.Stloc_1) + 1,
            "debuff guard writes the same int result local once");
        Need(cooperated.Count(c => c.Calls(CancelCommit)) == 1,
            "debuff precommit veto remains installed");

        // Apply has no result-local arm; the same cooperation must not disturb it.
        var applyCooperated = Emit(DebuffGate, Emit(AudioBody, Original(applyBody), applyBody), applyBody);
        Need(applyCooperated.Count(c => c.opcode == OpCodes.Call && Equals(c.operand, AudioClose)) == 2,
            "apply body keeps both audio terminal Closes");
        Need(applyCooperated.Count(c => c.Calls(CancelCommit)) == 1,
            "apply debuff veto remains installed");

        // Negative evidence: the binding must reject every non-exact insertion, not just
        // the old adjacency. Only the success-branch observer is mutated below.
        Reject("foreign-close", audioOutput, code =>
        {
            code[Signal(code) - 1].operand = AudioBegin;
            return code;
        });
        Reject("split-observer", audioOutput, code =>
        {
            code.Insert(Signal(code) - 1, new CodeInstruction(OpCodes.Nop));
            return code;
        });
        Reject("non-local-frame", audioOutput, code =>
        {
            code[Signal(code) - 2] = new CodeInstruction(OpCodes.Ldnull);
            return code;
        });
        Reject("extra-after-close", audioOutput, code =>
        {
            code.Insert(Signal(code), new CodeInstruction(OpCodes.Nop));
            return code;
        });
        Console.WriteLine($"DEBUFF_COMMIT_IL_PASS checks={checks} shared-body=PowerCmd.ModifyAmount audio-close=exact " +
            "result-local=int1 guard=preserved native-gameplay=NOT_RUN");
    }

    private static MethodBase Body(MethodInfo entry) => AccessTools.Method(
        entry.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext")!;
    private static List<CodeInstruction> Original(MethodBase body) =>
        PatchProcessor.GetOriginalInstructions(body).Select(c => new CodeInstruction(c)).ToList();
    private static List<CodeInstruction> Emit(MethodInfo transpiler, IEnumerable<CodeInstruction> input, MethodBase body)
    {
        var generator = new DynamicMethod("Emit" + transpiler.Name, typeof(void), Type.EmptyTypes).GetILGenerator();
        var parameters = transpiler.GetParameters();
        var args = parameters.Length == 3 ? new object[] { input, generator, body } : new object[] { input, body };
        return ((IEnumerable<CodeInstruction>)transpiler.Invoke(null, args)!).Select(c => new CodeInstruction(c)).ToList();
    }
    private static int Signal(List<CodeInstruction> code)
    {
        var setResult = code.Select((c, i) => (c, i)).Where(x => x.c.operand is MethodInfo m &&
            m.Name == "SetResult" && m.DeclaringType?.FullName?.StartsWith(
                "System.Runtime.CompilerServices.AsyncTaskMethodBuilder", StringComparison.Ordinal) == true).ToArray();
        if (setResult.Length != 1) throw new InvalidOperationException("Expected one native SetResult signal.");
        return setResult[0].i;
    }
    private static List<CodeInstruction>? BeforeSignal(List<CodeInstruction> code)
    {
        int signal = Signal(code);
        return signal < 1 ? null : code.Skip(Math.Max(0, signal - 3)).Take(Math.Min(3, signal)).ToList();
    }
    private static Dictionary<Label, int> LabelIndex(List<CodeInstruction> code)
    {
        var map = new Dictionary<Label, int>();
        for (int i = 0; i < code.Count; i++)
            foreach (var label in code[i].labels) map[label] = i;
        return map;
    }
    private static bool GuardShape(List<CodeInstruction> code, MethodBase body, bool audioObserver)
    {
        int value = Signal(code) - 1;
        if (audioObserver)
        {
            if (value < 2 || code[value].opcode != OpCodes.Call || !Equals(code[value].operand, AudioClose) ||
                code[value - 1].operand is not LocalBuilder { LocalType: var frame } || frame != AudioFrame ||
                code[value - 1].labels.Count != 0 || code[value - 1].blocks.Count != 0 ||
                code[value].labels.Count != 0 || code[value].blocks.Count != 0) return false;
            value -= 2;
        }
        return value >= 0 && code[value].opcode == OpCodes.Ldloc_1 &&
            code[value].labels.Count == 0 && code[value].blocks.Count == 0 &&
            body.GetMethodBody()!.LocalVariables[1].LocalType == typeof(int);
    }
    private static void Reject(string label, List<CodeInstruction> input,
        Func<List<CodeInstruction>, List<CodeInstruction>> mutate)
    {
        var mutated = mutate(input.Select(c => new CodeInstruction(c)).ToList());
        try
        {
            _ = Emit(DebuffGate, mutated, Body(ModifyNative));
        }
        catch (Exception error)
        {
            var inner = error is TargetInvocationException { InnerException: not null } ? error.InnerException! : error;
            if (inner is InvalidOperationException exact && exact.Message == BindingError)
            {
                checks++;
                Console.WriteLine("DEBUFF_COMMIT_IL_REJECT " + label);
                return;
            }
            throw new InvalidOperationException("Debuff binding failed with unexpected error: " + label, error);
        }
        throw new InvalidOperationException("Debuff binding accepted mutated IL: " + label);
    }
    private static void Need(bool value, string message)
    {
        checks++;
        if (!value) throw new InvalidOperationException(message);
    }
    private static void Dump(string label, MethodBase body)
    {
        var code = Original(body);
        int signal = Signal(code);
        var locals = body.GetMethodBody()!.LocalVariables;
        Console.WriteLine("LOCALS " + label + " " + string.Join(",", locals.Select(l => l.LocalIndex + ":" + l.LocalType.Name)));
        Console.WriteLine("SIGNAL " + label + " index=" + signal);
        for (int i = Math.Max(0, signal - 5); i <= Math.Min(code.Count - 1, signal); i++)
            Console.WriteLine($"  [{i}] {code[i].opcode.Name} " +
                (code[i].operand is MethodInfo m ? m.Name : code[i].operand is FieldInfo f ? f.Name : ""));
    }
}
