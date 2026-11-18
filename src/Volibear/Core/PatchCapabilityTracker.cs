using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Text;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// A transpiler sees a candidate before Harmony commits it. Publish that candidate
/// only after committed patch metadata changes; failed rewrites and diagnostic IL
/// replays cannot overwrite the capability already confirmed for the current chain.
/// This reads registered metadata only, never patch factories or transpiler output.
/// </summary>
internal sealed class PatchCapabilityTracker<T>
{
    private sealed record Pending(string Before, T Value);
    private sealed record Confirmed(string Fingerprint, T Value);
    private sealed class Entry
    {
        internal Pending? Candidate;
        internal Confirmed? Installed;
    }
    private sealed record Snapshot(string Fingerprint, HashSet<string> PatchMethods);

    private readonly object _gate = new();
    private readonly Dictionary<MethodBase, Entry> _entries = [];
    private long _revision;

    public void Observe(MethodBase target, T candidate)
    {
        ArgumentNullException.ThrowIfNull(target);
        for (var attempt = 0; attempt < 8; attempt++)
        {
            long revision;
            lock (_gate) revision = _revision;
            var readable = TrySnapshot(target, null, out var snapshot, out _);
            lock (_gate)
            {
                if (revision != _revision) continue;
                _revision++;
                if (!readable) { _entries.Remove(target); return; }
                if (!_entries.TryGetValue(target, out var entry)) _entries[target] = entry = new();
                Reconcile(entry, snapshot!);
                entry.Candidate = new(snapshot!.Fingerprint, candidate);
                return;
            }
        }
        // Concurrent rewrites did not leave one coherent metadata observation.
        // Do not let an older confirmed result describe a new, unobserved candidate.
        lock (_gate) { _entries.Remove(target); _revision++; }
    }

    public bool TryRead(MethodBase target, MethodInfo ownPatch, out T value)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentNullException.ThrowIfNull(ownPatch);
        value = default!;
        for (var attempt = 0; attempt < 8; attempt++)
        {
            long revision;
            lock (_gate) revision = _revision;
            var readable = TrySnapshot(target, ownPatch, out var snapshot, out var ownIdentity);
            lock (_gate)
            {
                if (revision != _revision) continue;
                _revision++;
                if (!readable || !snapshot!.PatchMethods.Contains(ownIdentity!))
                { _entries.Remove(target); return false; }
                if (!_entries.TryGetValue(target, out var entry)) return false;
                Reconcile(entry, snapshot);
                if (entry.Installed is not { } installed || installed.Fingerprint != snapshot.Fingerprint)
                    return false;
                value = installed.Value;
                return true;
            }
        }
        return false;
    }

    private static void Reconcile(Entry entry, Snapshot current)
    {
        if (entry.Candidate is not { } pending || pending.Before == current.Fingerprint) return;
        entry.Installed = new(current.Fingerprint, pending.Value);
        entry.Candidate = null;
        // Observe may establish this association before the first TryRead. Own-patch
        // membership is always checked by TryRead before publishing any such value.
    }

    private static bool TrySnapshot(MethodBase target, MethodInfo? ownPatch,
        out Snapshot? snapshot, out string? ownIdentity)
    {
        snapshot = null;
        ownIdentity = null;
        try
        {
            // Harmony.GetPatchInfo takes Harmony's registration lock. Never call it
            // under _gate: a concurrent transpiler already holds that lock in Observe.
            var info = Harmony.GetPatchInfo(target);
            var fingerprint = new StringBuilder();
            Append(fingerprint, MethodIdentity(target));
            var methods = new HashSet<string>(StringComparer.Ordinal);
            void Kind(string kind, IEnumerable<Patch> patches)
            {
                Append(fingerprint, kind);
                var values = patches.ToArray();
                Append(fingerprint, Number(values.Length));
                foreach (var patch in values)
                {
                    // GetMethod(target) could invoke a factory; PatchMethod only
                    // resolves the actual registered method from its metadata token.
                    var method = MethodIdentity(patch.PatchMethod);
                    methods.Add(method);
                    Append(fingerprint, method);
                    Append(fingerprint, patch.owner);
                    Append(fingerprint, Number(patch.priority));
                    Append(fingerprint, Number(patch.index));
                    Append(fingerprint, patch.debug ? "debug" : "normal");
                    Strings(fingerprint, patch.before);
                    Strings(fingerprint, patch.after);
                    if (patch.innerMethod is { } inner)
                    {
                        Append(fingerprint, MethodIdentity(inner.Method));
                        Strings(fingerprint, inner.positions.Select(Number).ToArray());
                    }
                    else Append(fingerprint, null);
                }
            }
            Kind("prefix", info?.Prefixes ?? Enumerable.Empty<Patch>());
            Kind("postfix", info?.Postfixes ?? Enumerable.Empty<Patch>());
            Kind("transpiler", info?.Transpilers ?? Enumerable.Empty<Patch>());
            Kind("finalizer", info?.Finalizers ?? Enumerable.Empty<Patch>());
            Kind("inner_prefix", info?.InnerPrefixes ?? Enumerable.Empty<Patch>());
            Kind("inner_postfix", info?.InnerPostfixes ?? Enumerable.Empty<Patch>());
            ownIdentity = ownPatch is null ? null : MethodIdentity(ownPatch);
            snapshot = new(fingerprint.ToString(), methods);
            return true;
        }
        catch (Exception)
        {
            // Missing/unreadable metadata is missing diagnostic evidence, not a new
            // gameplay dependency and never permission to claim an available feature.
            return false;
        }
    }

    private static string MethodIdentity(MethodBase method)
    {
        var identity = new StringBuilder();
        Append(identity, method.Module.ModuleVersionId.ToString("D"));
        Append(identity, Number(method.MetadataToken));
        Append(identity, method.DeclaringType is { } declaring ? TypeIdentity(declaring) : "<global>");
        Append(identity, method.Name);
        if (method is MethodInfo function) Append(identity, TypeIdentity(function.ReturnType));
        foreach (var parameter in method.GetParameters()) Append(identity, TypeIdentity(parameter.ParameterType));
        Append(identity, "generic-arguments");
        if (method.IsGenericMethod)
            foreach (var argument in method.GetGenericArguments()) Append(identity, TypeIdentity(argument));
        return identity.ToString();
    }

    private static string TypeIdentity(Type type) => type.AssemblyQualifiedName ??
        throw new NotSupportedException("Cannot confirm an open or unreadable patch method type.");
    private static string Number(int value) => value.ToString(CultureInfo.InvariantCulture);
    private static void Strings(StringBuilder output, IReadOnlyList<string>? values)
    {
        if (values is null) { Append(output, null); return; }
        Append(output, Number(values.Count));
        foreach (var value in values) Append(output, value);
    }
    private static void Append(StringBuilder output, string? value)
    {
        if (value is null) output.Append("-1:");
        else output.Append(value.Length.ToString(CultureInfo.InvariantCulture)).Append(':').Append(value);
    }
}
