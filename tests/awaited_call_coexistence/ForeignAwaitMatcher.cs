using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;

internal static partial class Program
{
    // Independent foreign fixture, not RitsuLib or game code. Its compatibility
    // contract matches the audited async matcher: nearest Task producer in the
    // previous 12 instructions, awaiter store within four, same-local IsCompleted
    // and GetResult. Merely finding any native call is intentionally insufficient.
    private static IEnumerable<CodeInstruction> ForeignReplace(IEnumerable<CodeInstruction> input)
    {
        var code = input.Select(c => new CodeInstruction(c)).ToList();
        var sites = new List<int>();
        var awaiter = typeof(TaskAwaiter<Result[]>);
        for (var i = 0; i < code.Count; i++)
        {
            if (code[i].operand is not MethodInfo { Name: "GetAwaiter" } getter || getter.ReturnType != awaiter) continue;
            var producer = -1;
            for (var p = i - 1; p >= Math.Max(0, i - 12); p--)
                if (PushedType(code[p]) is { } pushed && getter.DeclaringType!.IsAssignableFrom(pushed)) { producer = p; break; }
            if (producer < 0 || !code[producer].Calls(Native)) continue;
            var store = -1;
            for (var p = i + 1; p < Math.Min(code.Count, i + 5); p++)
                if (IsStore(code[p])) { store = p; break; }
            if (store < 0) continue;
            var local = LocalIndex(code[store]);
            var completed = -1;
            for (var p = store + 1; p < Math.Min(code.Count, store + 13); p++)
                if (CallsMember(code[p], awaiter, "get_IsCompleted") && LoadsLocal(code[p - 1], local)) { completed = p; break; }
            if (completed < 0) continue;
            var result = -1;
            for (var p = completed + 1; p < code.Count; p++)
                if (CallsMember(code[p], awaiter, "GetResult") && LoadsLocal(code[p - 1], local)) { result = p; break; }
            if (result < 0) continue;
            sites.Add(producer);
            i = result;
        }
        if (sites.Count != 1) throw new InvalidOperationException("Foreign strict awaited producer contract: expected one native site; found " + sites.Count);
        var index = sites[0];
        var original = code[index];
        var extra = new CodeInstruction(OpCodes.Ldc_I4, 37);
        extra.labels.AddRange(original.labels);
        extra.blocks.AddRange(original.blocks.Where(b => b.blockType != ExceptionBlockType.EndExceptionBlock));
        var replacement = new CodeInstruction(OpCodes.Call, Method(nameof(ForeignDamage)));
        replacement.blocks.AddRange(original.blocks.Where(b => b.blockType == ExceptionBlockType.EndExceptionBlock));
        code.RemoveAt(index);
        code.InsertRange(index, [extra, replacement]);
        return code;
    }

    private static bool CallsMember(CodeInstruction instruction, Type declaring, string name) =>
        (instruction.opcode == OpCodes.Call || instruction.opcode == OpCodes.Callvirt) &&
        instruction.operand is MethodInfo method && method.DeclaringType == declaring && method.Name == name;

    private static Type? PushedType(CodeInstruction instruction) => instruction.operand switch
    {
        MethodInfo method when instruction.opcode == OpCodes.Call || instruction.opcode == OpCodes.Callvirt => method.ReturnType,
        FieldInfo field when instruction.opcode == OpCodes.Ldfld || instruction.opcode == OpCodes.Ldsfld => field.FieldType,
        LocalBuilder local when instruction.IsLdloc() => local.LocalType,
        LocalVariableInfo local when instruction.IsLdloc() => local.LocalType,
        _ => null,
    };

    private static bool IsStore(CodeInstruction instruction) => instruction.opcode == OpCodes.Stloc || instruction.opcode == OpCodes.Stloc_S ||
        instruction.opcode == OpCodes.Stloc_0 || instruction.opcode == OpCodes.Stloc_1 || instruction.opcode == OpCodes.Stloc_2 || instruction.opcode == OpCodes.Stloc_3;

    private static int LocalIndex(CodeInstruction instruction)
    {
        if (instruction.opcode == OpCodes.Stloc_0 || instruction.opcode == OpCodes.Ldloc_0) return 0;
        if (instruction.opcode == OpCodes.Stloc_1 || instruction.opcode == OpCodes.Ldloc_1) return 1;
        if (instruction.opcode == OpCodes.Stloc_2 || instruction.opcode == OpCodes.Ldloc_2) return 2;
        if (instruction.opcode == OpCodes.Stloc_3 || instruction.opcode == OpCodes.Ldloc_3) return 3;
        return instruction.operand switch { LocalBuilder local => local.LocalIndex, LocalVariableInfo local => local.LocalIndex,
            int index => index, byte index => index, sbyte index => index, short index => index, ushort index => index, _ => -1 };
    }

    private static bool LoadsLocal(CodeInstruction instruction, int index) => index >= 0 && LocalIndex(instruction) == index &&
        (instruction.IsLdloc() || instruction.opcode == OpCodes.Ldloca || instruction.opcode == OpCodes.Ldloca_S);
}
