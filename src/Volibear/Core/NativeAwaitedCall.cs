using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// Composes an awaited native operation at its consumer. The original Task producer,
/// GetAwaiter, awaiter local, completion checks and GetResult remain available to other
/// adapters. A descriptor captures the evaluated arguments before dispatch; it never
/// has to infer an operation's identity from a later ambient damage callback.
/// </summary>
internal static class NativeAwaitedCall
{
    public static IEnumerable<CodeInstruction> Compose(IEnumerable<CodeInstruction> input,
        ILGenerator generator, MethodInfo nativeMethod, MethodInfo capture, MethodInfo compose)
    {
        ArgumentNullException.ThrowIfNull(input);
        ArgumentNullException.ThrowIfNull(generator);
        ArgumentNullException.ThrowIfNull(nativeMethod);
        ArgumentNullException.ThrowIfNull(capture);
        ArgumentNullException.ThrowIfNull(compose);
        StaticMethod(nativeMethod);
        StaticMethod(capture);
        StaticMethod(compose);
        var taskType = nativeMethod.ReturnType;
        if (!taskType.IsGenericType || taskType.GetGenericTypeDefinition() != typeof(Task<>))
            throw new NotSupportedException($"Awaited-call composition requires an exact Task<T> return: {nativeMethod}.");
        var parameters = nativeMethod.GetParameters().Select(parameter => parameter.ParameterType).ToArray();
        var descriptorType = capture.ReturnType;
        if (descriptorType == typeof(void) || !Supported(descriptorType) ||
            !capture.GetParameters().Select(parameter => parameter.ParameterType).SequenceEqual(parameters))
            throw new ArgumentException("Capture must accept the native parameters and return a closed value descriptor.", nameof(capture));
        var awaiterType = typeof(TaskAwaiter<>).MakeGenericType(taskType.GetGenericArguments());
        if (compose.ReturnType != awaiterType ||
            !compose.GetParameters().Select(parameter => parameter.ParameterType).SequenceEqual([awaiterType, descriptorType]))
            throw new ArgumentException("Composition must accept the original awaiter and descriptor and return the same awaiter type.", nameof(compose));

        var code = input.Select(instruction => new CodeInstruction(instruction)).ToList();
        var calls = code.Select((instruction, index) => (instruction, index))
            .Where(site => site.instruction.Calls(nativeMethod)).ToArray();
        if (calls.Length != 1)
            throw new InvalidOperationException($"Expected one native {nativeMethod} awaited callsite; found {calls.Length}.");
        var (nativeCall, callIndex) = calls[0];
        if (nativeCall.opcode != OpCodes.Call || Prefixed(code, callIndex))
            throw new NotSupportedException("Awaited-call composition does not support instance dispatch or prefixed native calls.");
        var awaiterIndex = Next(code, callIndex + 1);
        var getAwaiter = taskType.GetMethod(nameof(Task<int>.GetAwaiter), Type.EmptyTypes)!;
        if (awaiterIndex >= code.Count || !code[awaiterIndex].Calls(getAwaiter))
            throw new InvalidOperationException("The native result must be consumed by its original GetAwaiter.");
        var awaiterCall = code[awaiterIndex];
        // A second entry at GetAwaiter could bypass capture and use an unrelated Task.
        // Exception entries likewise cannot carry the Task stack value across scopes.
        if (Prefixed(code, awaiterIndex) || awaiterCall.labels.Count != 0 ||
            awaiterCall.blocks.Any(block => block.blockType != ExceptionBlockType.EndExceptionBlock))
            throw new NotSupportedException("The native awaiter consumer must have one unprefixed entry from its producer.");
        var storeIndex = Next(code, awaiterIndex + 1);
        if (storeIndex >= code.Count || !TryLocal(code[storeIndex], store: true, address: false, out var local) ||
            code[storeIndex].operand is LocalBuilder builder && builder.LocalType != awaiterType ||
            code[storeIndex].operand is LocalVariableInfo info && info.LocalType != awaiterType)
            throw new InvalidOperationException("The native awaiter must retain its original local store.");
        var completed = AccessTools.PropertyGetter(awaiterType, nameof(TaskAwaiter<int>.IsCompleted));
        var getResult = AccessTools.Method(awaiterType, nameof(TaskAwaiter<int>.GetResult));
        var completedIndex = FindLocalCall(code, storeIndex + 1, completed, local);
        if (completedIndex < 0 || FindLocalCall(code, completedIndex + 1, getResult, local) < 0)
            throw new InvalidOperationException("The native awaiter must retain its completion and result consumers.");

        var arguments = parameters.Select(generator.DeclareLocal).ToArray();
        var descriptor = generator.DeclareLocal(descriptorType);
        var before = new List<CodeInstruction>();
        for (var index = arguments.Length - 1; index >= 0; index--)
            before.Add(new(OpCodes.Stloc, arguments[index]));
        void LoadArguments()
        {
            foreach (var argument in arguments) before.Add(new(OpCodes.Ldloc, argument));
        }
        LoadArguments();
        before.Add(new(OpCodes.Call, capture));
        before.Add(new(OpCodes.Stloc, descriptor));
        LoadArguments();
        before.Add(new CodeInstruction(nativeCall) { labels = [], blocks = [] });
        before[0].labels.AddRange(nativeCall.labels);
        before[0].blocks.AddRange(nativeCall.blocks.Where(block => block.blockType != ExceptionBlockType.EndExceptionBlock));
        before[^1].blocks.AddRange(nativeCall.blocks.Where(block => block.blockType == ExceptionBlockType.EndExceptionBlock));

        // Exactly two instructions between the original GetAwaiter and its consumer.
        // In particular no new Task producer or Task local load hides the native call.
        var after = new List<CodeInstruction> { new(OpCodes.Ldloc, descriptor), new(OpCodes.Call, compose) };
        after[^1].blocks.AddRange(awaiterCall.blocks.Where(block => block.blockType == ExceptionBlockType.EndExceptionBlock));
        awaiterCall.blocks.RemoveAll(block => block.blockType == ExceptionBlockType.EndExceptionBlock);
        // Padding already accepted by Next is not a consumer. Keep the original store
        // close to GetAwaiter after composition, without removing labelled/EH boundaries.
        code.RemoveRange(awaiterIndex + 1, storeIndex - awaiterIndex - 1);
        code.InsertRange(awaiterIndex + 1, after);
        code.RemoveAt(callIndex);
        code.InsertRange(callIndex, before);
        return code;
    }

    private static bool Supported(Type type) => !type.IsByRef && !type.IsPointer && !type.IsByRefLike &&
        !type.IsFunctionPointer && !type.ContainsGenericParameters;

    private static void StaticMethod(MethodInfo method)
    {
        if (!method.IsStatic || method.ContainsGenericParameters ||
            (method.CallingConvention & CallingConventions.VarArgs) != 0 ||
            method.GetParameters().Any(parameter => !Supported(parameter.ParameterType)))
            throw new NotSupportedException($"Awaited-call composition requires closed static methods with value parameters: {method}.");
    }

    private static bool Prefixed(IReadOnlyList<CodeInstruction> code, int index) =>
        index > 0 && code[index - 1].opcode.OpCodeType == OpCodeType.Prefix;

    private static int Next(IReadOnlyList<CodeInstruction> code, int index)
    {
        while (index < code.Count && code[index].opcode == OpCodes.Nop &&
            code[index].labels.Count == 0 && code[index].blocks.Count == 0) index++;
        return index;
    }

    private static int FindLocalCall(IReadOnlyList<CodeInstruction> code, int start, MethodInfo method, int local)
    {
        for (var index = start; index < code.Count; index++)
            if (code[index].Calls(method) && index > 0 &&
                TryLocal(code[index - 1], store: false, address: true, out var receiver) && receiver == local)
                return index;
        return -1;
    }

    private static bool TryLocal(CodeInstruction instruction, bool store, bool address, out int index)
    {
        index = -1;
        var opcode = instruction.opcode;
        if (store)
        {
            if (opcode == OpCodes.Stloc_0) { index = 0; return true; }
            if (opcode == OpCodes.Stloc_1) { index = 1; return true; }
            if (opcode == OpCodes.Stloc_2) { index = 2; return true; }
            if (opcode == OpCodes.Stloc_3) { index = 3; return true; }
            if (opcode != OpCodes.Stloc && opcode != OpCodes.Stloc_S) return false;
        }
        else if (address && opcode != OpCodes.Ldloca && opcode != OpCodes.Ldloca_S) return false;
        index = instruction.operand switch
        {
            LocalBuilder builder => builder.LocalIndex,
            LocalVariableInfo info => info.LocalIndex,
            int value => value,
            short value => value,
            ushort value => value,
            byte value => value,
            sbyte value => value,
            _ => -1,
        };
        return index >= 0;
    }
}
