using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text.Json;
using HarmonyLib;
using SnapshotForeignFixture;
using Volibear.Core;

internal static class Program
{
    private static int checks;
    private static int ownTranspilerCalls;
    private static readonly HashSet<string> Owners = [];
    private static readonly string[] Cases = ["own-first", "foreign-first", "uncommitted-failure", "empty"];

    private static int Main(string[] args)
    {
        if (args.SequenceEqual(["--list"]))
        {
            foreach (var name in Cases) Console.WriteLine(name);
            return 0;
        }
        if (args.Length != 1 || !Cases.Contains(args[0])) return 2;
        try
        {
            Check(typeof(Harmony).Assembly.GetName().Version == new Version(2, 4, 2, 0), "real Harmony 2.4.2");
            Check(typeof(Program).Assembly != typeof(ForeignPatches).Assembly, "foreign patches use a distinct real assembly");
            if (OperatingSystem.IsLinux())
                Check(dlopen("libgcc_s.so.1", 2 | 256) != IntPtr.Zero, "libgcc preloaded for native detours");
            if (args[0] == "empty") Empty();
            else if (args[0] == "uncommitted-failure") UncommittedFailure();
            else Shared(args[0] == "own-first");
            Console.WriteLine($"PATCH_COMPATIBILITY_SNAPSHOT_PASS name={args[0]} assertions={checks} harmony=2.4.2.0 native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
        finally
        {
            foreach (var owner in Owners) new Harmony(owner).UnpatchAll(owner);
        }
    }

    [DllImport("libdl.so.2")]
    private static extern IntPtr dlopen(string file, int flags);

    private static void Check(bool condition, string reason)
    {
        checks++;
        if (!condition) throw new InvalidOperationException("Assertion failed: " + reason);
    }

    private static Harmony Owner(string id)
    {
        Owners.Add(id);
        return new Harmony(id);
    }

    private static MethodInfo OwnMethod(string name) => AccessTools.Method(typeof(Program), name)!;
    private static HarmonyMethod Own(string name) => new(OwnMethod(name));
    private static HarmonyMethod Foreign(string name) => new(typeof(ForeignPatches).GetMethod(name)!);

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Leaf(int value) => value * 2;
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int OwnLeaf(int value) => value * 3;
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int SharedAlpha(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int SharedBeta(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int SharedFactory(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int OwnOnly(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int ForeignOnly(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int TwoOwnOwners(int value) => Leaf(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int RejectedLater(int value) => Leaf(value);

    private static void OwnPrefix(ref int value) => value += 2;
    private static void OwnPostfix(ref int __result) => __result += 11;

    private static IEnumerable<CodeInstruction> OwnTranspiler(IEnumerable<CodeInstruction> instructions)
    {
        ownTranspilerCalls++;
        foreach (var item in instructions)
        {
            var copy = new CodeInstruction(item);
            if (copy.Calls(OwnMethod(nameof(Leaf))))
            {
                copy.opcode = OpCodes.Call;
                copy.operand = OwnMethod(nameof(OwnLeaf));
            }
            yield return copy;
        }
    }

    private static void InstallOwn()
    {
        var prefix = Own(nameof(OwnPrefix));
        prefix.priority = Priority.High;
        prefix.before = ["zeta", "alpha"];
        prefix.after = ["previous-z", "previous-a"];
        Owner("fixture.own").Patch(OwnMethod(nameof(SharedAlpha)), prefix: prefix,
            postfix: Own(nameof(OwnPostfix)), transpiler: Own(nameof(OwnTranspiler)));
        // Owner spelling must not determine assembly attribution.
        Owner("OtherMod.looking-owner").Patch(OwnMethod(nameof(SharedBeta)), prefix: Own(nameof(OwnPrefix)));
        Owner("fixture.own").Patch(OwnMethod(nameof(SharedFactory)), postfix: Own(nameof(OwnPostfix)));
        Owner("OtherMod.looking-owner").Patch(OwnMethod(nameof(OwnOnly)), prefix: Own(nameof(OwnPrefix)));
        Owner("fixture.own").Patch(OwnMethod(nameof(TwoOwnOwners)), prefix: Own(nameof(OwnPrefix)));
        Owner("Foreign.looking-owner").Patch(OwnMethod(nameof(TwoOwnOwners)), postfix: Own(nameof(OwnPostfix)));
    }

    private static void InstallForeign()
    {
        Owner("fixture.foreign").Patch(OwnMethod(nameof(SharedAlpha)), prefix: Foreign(nameof(ForeignPatches.Prefix)),
            transpiler: Foreign(nameof(ForeignPatches.Transpiler)), finalizer: Foreign(nameof(ForeignPatches.Finalizer)));
        Owner("Volibear").Patch(OwnMethod(nameof(SharedBeta)), postfix: Foreign(nameof(ForeignPatches.Postfix)));
        Owner("fixture.foreign").Patch(OwnMethod(nameof(SharedFactory)), prefix: Foreign(nameof(ForeignPatches.Factory)));
        Owner("Volibear").Patch(OwnMethod(nameof(ForeignOnly)), prefix: Foreign(nameof(ForeignPatches.Prefix)));
    }

    private static string[] Lines(PatchCompatibilitySnapshot.Snapshot snapshot)
    {
        var lines = new List<string>();
        snapshot.WriteTo(lines.Add);
        return lines.ToArray();
    }

    private static string MetadataFingerprint()
    {
        return string.Join('\n', Harmony.GetAllPatchedMethods().OrderBy(method => method.FullDescription(), StringComparer.Ordinal)
            .SelectMany(method =>
            {
                var info = Harmony.GetPatchInfo(method);
                if (info is null) return [];
                return info.Prefixes.Select(patch => ("prefix", patch))
                    .Concat(info.Postfixes.Select(patch => ("postfix", patch)))
                    .Concat(info.Transpilers.Select(patch => ("transpiler", patch)))
                    .Concat(info.Finalizers.Select(patch => ("finalizer", patch)))
                    .Select(item => $"{method.FullDescription()}|{item.Item1}|{item.patch.owner}|{item.patch.PatchMethod.FullDescription()}|{item.patch.priority}|{item.patch.index}|{string.Join(',', item.patch.before)}|{string.Join(',', item.patch.after)}");
            }));
    }

    private static void Shared(bool ownFirst)
    {
        if (ownFirst) { InstallOwn(); InstallForeign(); }
        else { InstallForeign(); InstallOwn(); }
        var runtimeBefore = (SharedAlpha(3), SharedBeta(4), SharedFactory(5));
        var metadataBefore = MetadataFingerprint();
        var transpilersBefore = (ownTranspilerCalls, ForeignPatches.TranspilerCalls);
        var factoriesBefore = ForeignPatches.FactoryCalls;
        Check(factoriesBefore > 0, "foreign dynamic patch factory was used for real installation");
        var snapshot = PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly);
        var repeated = PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly);
        var lines = Lines(snapshot);
        Check(snapshot.Targets.Count == 3, "only the three assembly-shared targets are emitted");
        Check(snapshot.Summary.OwnTargets == 5, "own-only and two-own-owner targets counted but not emitted");
        Check(snapshot.Summary.SharedTargets == 3, "summary shared target count");
        Check(snapshot.Summary.ScannedTargets == 6, "all successfully registered targets scanned");
        Check(snapshot.Targets.All(target => target.Status == "shared_unverified" && target.Scope == "metadata_only"), "shared never means compatible or incompatible");
        Check(snapshot.Targets.Select(target => target.Target).SequenceEqual(snapshot.Targets.Select(target => target.Target).Order(StringComparer.Ordinal)), "target output order deterministic");
        Check(lines.SequenceEqual(Lines(repeated)), "repeated captures serialize identically");
        Check(lines.Length == 4 && lines[^1].StartsWith("[Volibear] COMPAT_SCAN "), "one line per shared target and one summary");
        foreach (var line in lines.Take(3))
        {
            Check(line.StartsWith("[Volibear] COMPAT_SHARED "), "shared marker");
            using var json = JsonDocument.Parse(line["[Volibear] COMPAT_SHARED ".Length..]);
            Check(json.RootElement.GetProperty("status").GetString() == "shared_unverified", "structured shared status");
            Check(json.RootElement.GetProperty("patches").EnumerateArray().Any(patch => patch.GetProperty("is_own").GetBoolean()), "own patch records present");
            Check(json.RootElement.GetProperty("patches").EnumerateArray().Any(patch => !patch.GetProperty("is_own").GetBoolean()), "foreign patch records present");
        }
        using (var summary = JsonDocument.Parse(lines[^1]["[Volibear] COMPAT_SCAN ".Length..]))
        {
            Check(summary.RootElement.GetProperty("status").GetString() == "metadata_only", "summary is metadata-only");
            Check(summary.RootElement.GetProperty("limitations").GetString()!.Contains("Rejected patch attempts"), "uncommitted failures explicitly outside scope");
        }
        var alpha = snapshot.Targets.Single(target => target.Target.Contains(nameof(SharedAlpha)));
        Check(alpha.Target == OwnMethod(nameof(SharedAlpha)).FullDescription(), "target full signature");
        Check(alpha.TargetAssemblyVersion == "1.2.3.4", "original assembly version");
        Check(alpha.Patches.Select(patch => patch.Kind).Distinct().Order().SequenceEqual(new[] { "finalizer", "postfix", "prefix", "transpiler" }), "all active patch kinds captured");
        var ownPrefix = alpha.Patches.Single(patch => patch.IsOwn && patch.Kind == "prefix");
        Check(ownPrefix.Priority == Priority.High, "priority metadata preserved");
        Check(ownPrefix.Before.SequenceEqual(["alpha", "zeta"]) && ownPrefix.After.SequenceEqual(["previous-a", "previous-z"]), "edge arrays have canonical output order");
        Check(alpha.Patches.Where(patch => patch.IsOwn).All(patch => patch.AssemblyVersion == "1.2.3.4"), "own assembly versions recorded");
        Check(alpha.Patches.Where(patch => !patch.IsOwn).All(patch => patch.AssemblyName == "PatchCompatibility.ForeignFixture" && patch.AssemblyVersion == "5.6.7.8"), "distinct foreign assembly identity recorded");
        var beta = snapshot.Targets.Single(target => target.Target.Contains(nameof(SharedBeta)));
        Check(beta.Patches.Single(patch => patch.Owner == "Volibear").IsOwn == false, "foreign ownership is not inferred from Harmony ID");
        Check(beta.Patches.Single(patch => patch.Owner == "OtherMod.looking-owner").IsOwn, "own ownership is based on patch assembly");
        var factory = snapshot.Targets.Single(target => target.Target.Contains(nameof(SharedFactory)));
        Check(factory.Patches.Any(patch => patch.PatchMethod.Contains(nameof(ForeignPatches.Factory))), "registered factory reported without evaluating its result");
        CapabilitySnapshotChecks();
        Check((ownTranspilerCalls, ForeignPatches.TranspilerCalls) == transpilersBefore, "capture and serialization never replay transpilers");
        Check(ForeignPatches.FactoryCalls == factoriesBefore, "capture never invokes patch factories");
        Check(MetadataFingerprint() == metadataBefore, "no patch metadata or ordering changes");
        Check((SharedAlpha(3), SharedBeta(4), SharedFactory(5)) == runtimeBefore, "existing native detours preserve behavior after capture");
        foreach (var line in lines) Console.WriteLine(line);
    }

    private static void CapabilitySnapshotChecks()
    {
        var available = new PatchCompatibilitySnapshot.CapabilityRecord("ordinary_segments", "available",
            "Attack.MoveNext()", "The retained awaiter is observed.", "None.");
        var unavailable = new PatchCompatibilitySnapshot.CapabilityRecord("exact_damage_attribution", "unavailable",
            "Attack.MoveNext()", "The native producer was replaced.\nForeign implementation is not inspected.",
            "Mid-hit suppression is unavailable; ordinary segment responses remain installed.");
        var supplied = new[] { available, unavailable };
        var snapshot = PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly, supplied);
        var before = Lines(snapshot);
        supplied[0] = unavailable with { Capability = "changed_after_capture" };
        Check(snapshot.Summary.Capabilities.SequenceEqual(new[] { available, unavailable }), "capture copies the caller-owned capability list");
        Check(before.SequenceEqual(Lines(snapshot)), "later caller changes cannot rewrite a captured report");
        var collection = (IList<PatchCompatibilitySnapshot.CapabilityRecord>)snapshot.Summary.Capabilities;
        Exception? mutationError = null;
        try { collection[0] = unavailable; }
        catch (NotSupportedException error) { mutationError = error; }
        Check(mutationError is not null, "captured capability collection is read-only");
        Check(before.Length == snapshot.Targets.Count + 1, "capabilities do not add non-atomic side-channel records");
        Check(before.All(line => !line.Contains('\n')), "multiline capability reasons remain inside one escaped JSON record");
        Check(before.Take(before.Length - 1).All(line => !line.Contains("\"capabilities\"")), "capabilities occur only in the closing snapshot");
        using var json = JsonDocument.Parse(before[^1]["[Volibear] COMPAT_SCAN ".Length..]);
        var entries = json.RootElement.GetProperty("capabilities").EnumerateArray().ToArray();
        Check(entries.Length == 2, "one closing JSON summary contains every declared capability");
        Check(entries[0].GetProperty("capability").GetString() == available.Capability &&
            entries[0].GetProperty("status").GetString() == "available", "available assessment is serialized without promotion to full compatibility");
        Check(entries[1].GetProperty("capability").GetString() == unavailable.Capability &&
            entries[1].GetProperty("status").GetString() == "unavailable", "unavailable assessment is serialized distinctly");
        Check(entries[1].GetProperty("target").GetString() == unavailable.Target &&
            entries[1].GetProperty("reason").GetString() == unavailable.Reason &&
            entries[1].GetProperty("impact").GetString() == unavailable.Impact, "target, exact cause and limited behavior survive serialization");
        Check(json.RootElement.GetProperty("status").GetString() == "metadata_only", "declared capability information does not certify gameplay");
        Check(PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly).Summary.Capabilities.Count == 0,
            "absent capability declarations are not inferred from shared patches");
    }

    private static void UncommittedFailure()
    {
        var target = OwnMethod(nameof(RejectedLater));
        Owner("fixture.own").Patch(target, transpiler: Own(nameof(OwnTranspiler)));
        ForeignPatches.ExpectedAnchor = OwnMethod(nameof(Leaf));
        var failed = Foreign(nameof(ForeignPatches.RequiresOriginalAnchor));
        failed.priority = Priority.Last;
        Exception? error = null;
        try { Owner("fixture.rejected-later").Patch(target, transpiler: failed); }
        catch (Exception caught) { error = caught; }
        Check(error?.ToString().Contains("required original anchor is missing") == true, "real late foreign rewrite is rejected");
        Check(!Harmony.GetPatchInfo(target).Owners.Contains("fixture.rejected-later"), "Harmony did not commit the failed foreign patch");
        var counterBefore = ownTranspilerCalls;
        var snapshot = PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly);
        Check(snapshot.Targets.Count == 0, "uncommitted attempt cannot be invented from current metadata");
        Check(snapshot.Summary.OwnTargets == 1, "successful earlier own chain remains visible");
        Check(snapshot.Summary.Status == "metadata_only", "absence of shared metadata is not a compatibility PASS");
        Check(snapshot.Summary.Limitations.Contains("Rejected patch attempts"), "scope limitation remains explicit after rejection");
        Check(ownTranspilerCalls == counterBefore, "failure audit also never replays transpilers");
        Check(RejectedLater(4) == 12, "earlier native detour is preserved after rejected composition");
        foreach (var line in Lines(snapshot)) Console.WriteLine(line);
    }

    private static void Empty()
    {
        var snapshot = PatchCompatibilitySnapshot.Capture(typeof(Program).Assembly);
        Check(snapshot.Targets.Count == 0 && snapshot.Summary.SharedTargets == 0, "empty scan has no shared targets");
        Check(snapshot.Summary.Status == "metadata_only", "empty scan never claims compatibility");
        Check(Lines(snapshot).Length == 1, "empty scan still emits its limited summary");
        Exception? argumentError = null;
        try { PatchCompatibilitySnapshot.Capture(null!); }
        catch (ArgumentNullException error) { argumentError = error; }
        Check(argumentError is not null, "null assembly is rejected explicitly");
        foreach (var line in Lines(snapshot)) Console.WriteLine(line);
    }
}
