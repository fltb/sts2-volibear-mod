using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Threading.Tasks;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// Keeps this mod's native adapters after BaseLib and before otherwise-unordered ordinary
/// extensions on the same method, without changing mod discovery order. Explicit ordering
/// remains authoritative, including the internal Last/minimum-priority chain. Competing
/// replacements or contradictory ordering constraints can still be incompatible.
/// </summary>
public static class NativeTranspiler
{
    private const string BaseLibOwner = "BaseLib";

    /// <summary>Copies the complete annotation without changing the caller's metadata.</summary>
    internal static HarmonyMethod Order(HarmonyMethod patch)
    {
        // Harmony's Clone copies annotation fields but deliberately omits the method.
        var ordered = patch.Clone();
        ordered.method = patch.method;
        ordered.argumentTypes = patch.argumentTypes?.ToArray();
        ordered.before = patch.before?.ToArray();
        ordered.after = patch.after?.Contains(BaseLibOwner, StringComparer.Ordinal) == true
            ? patch.after.ToArray() : [.. patch.after ?? [], BaseLibOwner];
        if (ordered.priority == -1) ordered.priority = Priority.High;
        return ordered;
    }

    /// <summary>
    /// Applies only our annotation policy; foreign patches and mod-manager ordering are
    /// untouched. Conflicts retain their original exception and identify the shared target.
    /// Supply the original annotation: its unset priority identifies which adapters permit
    /// default ordering. The caller's annotation is never changed.
    /// </summary>
    public static MethodInfo Patch(Harmony harmony, MethodBase original,
        HarmonyMethod? prefix = null, HarmonyMethod? postfix = null,
        HarmonyMethod? transpiler = null, HarmonyMethod? finalizer = null)
    {
        if (transpiler is null) return harmony.Patch(original, prefix, postfix, null, finalizer);
        var existing = Harmony.GetPatchInfo(original)?.Transpilers.ToArray() ?? [];
        try
        {
            var ordered = Order(transpiler);
            if (transpiler.priority == -1) BeforeOrdinaryOwners(ordered, harmony.Id, existing);
            return harmony.Patch(original, prefix, postfix, ordered, finalizer);
        }
        catch (Exception error)
        {
            var owners = string.Join(", ", existing.Select(p => $"{p.owner}(priority={p.priority})"));
            throw new InvalidOperationException(
                $"Volibear transpiler installation failed: target={original.FullDescription()}; " +
                $"owner={harmony.Id}; existing_transpilers=[{owners}].", error);
        }
    }

    private static void BeforeOrdinaryOwners(HarmonyMethod ordered, string owner, HarmonyLib.Patch[] existing)
    {
        // High alone is insufficient when an ordinary foreign owner was registered before
        // BaseLib. Express the local dependency on our patch; never edit the foreign patch.
        var edges = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
        void Edge(string first, string last)
        {
            if (!edges.TryGetValue(first, out var next)) edges[first] = next = new(StringComparer.Ordinal);
            next.Add(last);
        }
        void Constraints(string id, IEnumerable<string> before, IEnumerable<string> after)
        {
            foreach (var next in before) Edge(id, next);
            foreach (var previous in after) Edge(previous, id);
        }
        foreach (var patch in existing) Constraints(patch.owner, patch.before, patch.after);
        Constraints(owner, ordered.before ?? [], ordered.after ?? []);
        bool Reaches(string first, string last)
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            var pending = new Stack<string>(); pending.Push(first);
            while (pending.TryPop(out var current))
            {
                if (current == last) return true;
                if (!seen.Add(current) || !edges.TryGetValue(current, out var next)) continue;
                foreach (var item in next) pending.Push(item);
            }
            return false;
        }
        var before = (ordered.before ?? []).ToList();
        foreach (var group in existing.GroupBy(p => p.owner))
        {
            if (group.Key == owner || group.Key == BaseLibOwner || group.Key == "Volibear" ||
                group.Key.StartsWith("Volibear.", StringComparison.Ordinal) ||
                group.Any(p => p.priority != Priority.Normal) || Reaches(group.Key, owner)) continue;
            if (!before.Contains(group.Key, StringComparer.Ordinal)) before.Add(group.Key);
            Edge(owner, group.Key);
        }
        ordered.before = before.ToArray();
    }

    /// <summary>
    /// Observes one static, Task-returning call without replacing its native operand.
    /// Arguments are evaluated once and saved in locals. The optional before observer
    /// accepts those arguments and returns void; the optional after observer accepts
    /// the native task followed by those arguments and returns the same task type.
    /// Existing labels and exception boundaries cover the entire inserted sequence.
    /// This preserves the call anchor, not arbitrary foreign assumptions about adjacent IL.
    /// </summary>
    public static IEnumerable<CodeInstruction> ObserveCall(IEnumerable<CodeInstruction> instructions,
        ILGenerator generator, MethodInfo native, MethodInfo? before = null, MethodInfo? after = null)
    {
        ArgumentNullException.ThrowIfNull(instructions);
        ArgumentNullException.ThrowIfNull(generator);
        ArgumentNullException.ThrowIfNull(native);
        if (before is null && after is null)
            throw new ArgumentException("At least one call observer is required.");

        static bool Supported(Type type) => !type.IsByRef && !type.IsPointer && !type.IsByRefLike &&
            !type.ContainsGenericParameters && !type.IsFunctionPointer;
        static void StaticMethod(MethodInfo method)
        {
            if (!method.IsStatic || method.ContainsGenericParameters ||
                (method.CallingConvention & CallingConventions.VarArgs) != 0 ||
                method.GetParameters().Any(p => !Supported(p.ParameterType)))
                throw new NotSupportedException($"Call observation requires a closed static method with value parameters: {method}.");
        }
        StaticMethod(native);
        if (!typeof(Task).IsAssignableFrom(native.ReturnType))
            throw new NotSupportedException($"Call observation requires a Task return type: {native}.");
        var parameters = native.GetParameters().Select(p => p.ParameterType).ToArray();
        if (before is not null)
        {
            StaticMethod(before);
            if (before.ReturnType != typeof(void) ||
                !before.GetParameters().Select(p => p.ParameterType).SequenceEqual(parameters))
                throw new ArgumentException($"Before observer must return void and accept the native parameters: {before}.", nameof(before));
        }
        if (after is not null)
        {
            StaticMethod(after);
            if (after.ReturnType != native.ReturnType ||
                !after.GetParameters().Select(p => p.ParameterType).SequenceEqual(new[] { native.ReturnType }.Concat(parameters)))
                throw new ArgumentException($"After observer must accept the native task and parameters and return the same task type: {after}.", nameof(after));
        }

        var code = instructions.Select(instruction => new CodeInstruction(instruction)).ToList();
        var matches = code.Select((instruction, index) => (instruction, index))
            .Where(site => site.instruction.Calls(native)).ToArray();
        if (matches.Length != 1)
            throw new InvalidOperationException($"Expected one native {native} callsite; found {matches.Length}.");
        var (call, position) = matches[0];
        if (call.opcode != OpCodes.Call || position > 0 && code[position - 1].opcode.OpCodeType == OpCodeType.Prefix)
            throw new NotSupportedException($"Call observation does not support instance dispatch or IL prefixes: {native}.");

        var locals = parameters.Select(generator.DeclareLocal).ToArray();
        var inserted = new List<CodeInstruction>();
        for (var index = locals.Length - 1; index >= 0; index--)
            inserted.Add(new CodeInstruction(OpCodes.Stloc, locals[index]));
        void LoadArguments()
        {
            foreach (var local in locals) inserted.Add(new CodeInstruction(OpCodes.Ldloc, local));
        }
        if (before is not null)
        {
            LoadArguments();
            inserted.Add(new CodeInstruction(OpCodes.Call, before));
        }
        LoadArguments();
        inserted.Add(new CodeInstruction(call) { labels = [], blocks = [] });
        if (after is not null)
        {
            LoadArguments();
            inserted.Add(new CodeInstruction(OpCodes.Call, after));
        }

        inserted[0].labels.AddRange(call.labels);
        inserted[0].blocks.AddRange(call.blocks.Where(block => block.blockType != ExceptionBlockType.EndExceptionBlock));
        inserted[^1].blocks.AddRange(call.blocks.Where(block => block.blockType == ExceptionBlockType.EndExceptionBlock));
        code.RemoveAt(position);
        code.InsertRange(position, inserted);
        return code;
    }

    /// <summary>
    /// Ignores harmless padding when matching native instructions. Branch targets and
    /// exception boundaries stay at their original instruction; no metadata is moved.
    /// Copies retain labels/blocks so a later rewrite cannot mutate the upstream stream.
    /// </summary>
    public static IEnumerable<CodeInstruction> WithoutUnanchoredNops(IEnumerable<CodeInstruction> instructions)
    {
        foreach (var instruction in instructions)
        {
            if (instruction.opcode == OpCodes.Nop && instruction.labels.Count == 0 && instruction.blocks.Count == 0)
                continue;
            yield return new CodeInstruction(instruction);
        }
    }
}
