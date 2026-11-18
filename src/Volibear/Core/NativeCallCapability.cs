using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Threading.Tasks;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// A late, optional adapter may bind an exact native call only while that call is
/// still present. An earlier extension may own the complete awaited operation;
/// in that case the adapter yields instead of guessing which nested call is its own.
/// This inspects the current rewrite input, never another mod's implementation.
/// </summary>
internal static class NativeCallCapability
{
    internal const int LatePriority = int.MinValue;

    internal static bool CanBindExactCall(IReadOnlyList<CodeInstruction> code, MethodInfo native,
        out string reason)
    {
        ArgumentNullException.ThrowIfNull(code);
        ArgumentNullException.ThrowIfNull(native);
        if (!native.IsStatic || native.ContainsGenericParameters || !native.ReturnType.IsGenericType ||
            native.ReturnType.GetGenericTypeDefinition() != typeof(Task<>))
            throw new ArgumentException("Exact async call binding requires a closed static Task<T> method.", nameof(native));
        var getter = native.ReturnType.GetMethod(nameof(Task.GetAwaiter), Type.EmptyTypes)!;
        var awaits = code.Select((instruction, index) => (instruction, index))
            .Where(site => site.instruction.Calls(getter)).ToArray();
        var calls = code.Select((instruction, index) => (instruction, index))
            .Where(site => site.instruction.Calls(native)).ToArray();
        if (awaits.Length != 1 || calls.Length > 1)
            throw new InvalidOperationException($"Exact native call shape drift: {native.FullDescription()}; " +
                $"native_calls={calls.Length}, awaiters={awaits.Length}, expected at most one call and one awaiter.");
        if (calls.Length == 1)
        {
            var site = calls[0];
            if (site.instruction.opcode != OpCodes.Call || site.index >= awaits[0].index ||
                site.index > 0 && code[site.index - 1].opcode.OpCodeType == OpCodeType.Prefix)
                throw new InvalidOperationException("Exact native call is not an unprefixed static producer before its awaiter: " + native.FullDescription());
            reason = "The exact native damage call is available for a synchronous, single-use provenance binding.";
            return true;
        }
        // Do not turn an accidentally deleted call into a successful degraded boot.
        // Require a concrete same-result producer feeding the retained awaiter.
        var previous = awaits[0].index - 1;
        while (previous >= 0 && code[previous].opcode == OpCodes.Nop) previous--;
        if (previous < 0 || (code[previous].opcode != OpCodes.Call && code[previous].opcode != OpCodes.Callvirt) ||
            code[previous].operand is not MethodInfo replacement || replacement.ReturnType != native.ReturnType)
            throw new InvalidOperationException("Native call is missing without a verifiable replacement task producer: " + native.FullDescription());
        reason = "The awaited operation is supplied by " + replacement.FullDescription() +
            "; the exact native damage call is no longer present. Its nested damage cannot be attributed safely.";
        return false;
    }
}
