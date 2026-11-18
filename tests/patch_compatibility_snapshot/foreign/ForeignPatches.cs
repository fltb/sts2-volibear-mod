using System.Reflection;
using HarmonyLib;

namespace SnapshotForeignFixture;

public static class ForeignPatches
{
    public static int TranspilerCalls;
    public static int FactoryCalls;
    public static MethodInfo? ExpectedAnchor;

    public static void Prefix(ref int value) => value += 5;
    public static void Postfix(ref int __result) => __result += 7;
    public static Exception? Finalizer(Exception? __exception) => __exception;

    public static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
    {
        TranspilerCalls++;
        return instructions;
    }

    public static MethodInfo Factory(MethodBase original)
    {
        FactoryCalls++;
        return typeof(ForeignPatches).GetMethod(nameof(Prefix))!;
    }

    public static IEnumerable<CodeInstruction> RequiresOriginalAnchor(IEnumerable<CodeInstruction> instructions)
    {
        var code = instructions.ToList();
        if (ExpectedAnchor is null || code.Count(instruction => instruction.Calls(ExpectedAnchor)) != 1)
            throw new InvalidOperationException("Foreign fixture: required original anchor is missing.");
        return code;
    }
}
