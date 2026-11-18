using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// Describes shared targets using successfully registered Harmony metadata only.
/// It never invokes patch factories or transpilers, reads replacement IL, changes
/// ordering, or treats a shared target as proof of compatibility or incompatibility.
/// Failed patch attempts that Harmony did not commit are outside this snapshot.
/// </summary>
public static class PatchCompatibilitySnapshot
{
    private const string Limitations =
        "Only successfully registered Harmony metadata is visible. Rejected patch attempts, " +
        "non-Harmony detours, gameplay behavior and later changes are not assessed.";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    public sealed record PatchRecord(
        string Kind,
        string Owner,
        string PatchMethod,
        string AssemblyName,
        string AssemblyVersion,
        bool IsOwn,
        int Priority,
        int RegistrationIndex,
        IReadOnlyList<string> Before,
        IReadOnlyList<string> After);

    public sealed record SharedTarget(
        string Target,
        string TargetAssemblyName,
        string TargetAssemblyVersion,
        IReadOnlyList<PatchRecord> Patches)
    {
        public string Status => "shared_unverified";
        public string Scope => "metadata_only";
    }

    public sealed record ScanSummary(int ScannedTargets, int OwnTargets, int SharedTargets)
    {
        public string Status => "metadata_only";
        public string Scope => "metadata_only";
        public string Limitations => PatchCompatibilitySnapshot.Limitations;
    }

    public sealed class Snapshot
    {
        public IReadOnlyList<SharedTarget> Targets { get; }
        public ScanSummary Summary { get; }

        internal Snapshot(IReadOnlyList<SharedTarget> targets, ScanSummary summary)
        {
            Targets = targets;
            Summary = summary;
        }

        public void WriteTo(Action<string> write)
        {
            ArgumentNullException.ThrowIfNull(write);
            foreach (var target in Targets)
                write("[Volibear] COMPAT_SHARED " + JsonSerializer.Serialize(target, JsonOptions));
            write("[Volibear] COMPAT_SCAN " + JsonSerializer.Serialize(Summary, JsonOptions));
        }
    }

    public static Snapshot Capture(Assembly ownAssembly)
    {
        ArgumentNullException.ThrowIfNull(ownAssembly);
        var methods = Harmony.GetAllPatchedMethods().ToArray();
        var shared = new List<SharedTarget>();
        var ownTargets = 0;
        foreach (var original in methods)
        {
            var info = Harmony.GetPatchInfo(original);
            if (info is null) continue;
            var patches = ReadPatches(info).Select(item => Describe(item.Kind, item.Patch, ownAssembly)).ToArray();
            if (!patches.Any(patch => patch.IsOwn)) continue;
            ownTargets++;
            if (!patches.Any(patch => !patch.IsOwn)) continue;
            var assembly = original.Module.Assembly.GetName();
            var ordered = patches.OrderBy(patch => patch.Kind, StringComparer.Ordinal)
                .ThenBy(patch => patch.Owner, StringComparer.Ordinal)
                .ThenBy(patch => patch.PatchMethod, StringComparer.Ordinal)
                .ThenBy(patch => patch.AssemblyName, StringComparer.Ordinal)
                .ThenBy(patch => patch.AssemblyVersion, StringComparer.Ordinal)
                .ThenBy(patch => patch.Priority)
                .ThenBy(patch => patch.RegistrationIndex)
                .ToArray();
            shared.Add(new(original.FullDescription(), assembly.Name ?? "<unknown>",
                assembly.Version?.ToString() ?? "<unknown>", Array.AsReadOnly(ordered)));
        }
        // This is deterministic presentation order, not claimed execution order.
        // GetSortedPatchMethods would invoke dynamic patch factories, so it is
        // deliberately not used. Priority, dependencies and index remain explicit.
        var targets = shared.OrderBy(target => target.Target, StringComparer.Ordinal)
            .ThenBy(target => target.TargetAssemblyName, StringComparer.Ordinal)
            .ThenBy(target => target.TargetAssemblyVersion, StringComparer.Ordinal)
            .ToArray();
        return new(Array.AsReadOnly(targets), new(methods.Length, ownTargets, targets.Length));
    }

    private static PatchRecord Describe(string kind, Patch patch, Assembly ownAssembly)
    {
        // PatchMethod describes the registered method. GetMethod(original) would
        // execute a patch factory and would violate the read-only scan contract.
        var method = patch.PatchMethod;
        var declaringAssembly = method.DeclaringType?.Assembly;
        var assembly = (declaringAssembly ?? method.Module.Assembly).GetName();
        return new(kind, patch.owner, method.FullDescription(), assembly.Name ?? "<unknown>",
            assembly.Version?.ToString() ?? "<unknown>", declaringAssembly == ownAssembly,
            patch.priority, patch.index,
            Array.AsReadOnly((patch.before ?? []).Order(StringComparer.Ordinal).ToArray()),
            Array.AsReadOnly((patch.after ?? []).Order(StringComparer.Ordinal).ToArray()));
    }

    private static IEnumerable<(string Kind, Patch Patch)> ReadPatches(Patches info)
    {
        foreach (var patch in info.Prefixes) yield return ("prefix", patch);
        foreach (var patch in info.Postfixes) yield return ("postfix", patch);
        foreach (var patch in info.Transpilers) yield return ("transpiler", patch);
        foreach (var patch in info.Finalizers) yield return ("finalizer", patch);
        foreach (var patch in info.InnerPrefixes) yield return ("inner_prefix", patch);
        foreach (var patch in info.InnerPostfixes) yield return ("inner_postfix", patch);
    }
}
