using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using HarmonyLib;
using Volibear.Core;

internal static partial class Program
{
    private const string Adapter = "Volibear.Adapter";
    private const string Foreign = "Foreign.Observer";
    private static readonly List<string> Trace = [];
    private static readonly HashSet<string> Owners = [];
    private static int checks;
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["metadata-copy"] = Metadata,
        ["legacy-order-conflict"] = LegacyOrderConflict,
        ["foreign-first"] = () => DefaultOrder(true),
        ["volibear-first"] = () => DefaultOrder(false),
        ["legal-registration-orders"] = LegalRegistrationOrders,
        ["explicit-foreign-order"] = ExplicitForeignOrder,
        ["indirect-foreign-order"] = IndirectForeignOrder,
        ["mixed-owner-priorities"] = MixedOwnerPriorities,
        ["explicit-tail-order"] = TailOrder,
        ["uninstall-reinstall"] = Reinstall,
        ["nop-padding"] = NopPadding,
        ["marked-nops"] = MarkedNops,
        ["real-conflict"] = RealConflict,
        ["observe-call-composition"] = ObserveComposition,
        ["observe-call-async"] = ObserveAsyncOutcomes,
        ["observe-call-zero-arguments"] = ObserveZeroArguments,
        ["observe-call-metadata"] = ObserveMetadata,
        ["observe-call-validation"] = ObserveValidation,
    };

    private static int Main(string[] args)
    {
        if (args.SequenceEqual(["--list"]))
        {
            foreach (var name in Cases.Keys) Console.WriteLine(name);
            return 0;
        }
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run)) return 2;
        try
        {
            Check(typeof(Harmony).Assembly.GetName().Version == new Version(2, 4, 2, 0), "real Harmony version");
            if (OperatingSystem.IsLinux())
                Check(dlopen("libgcc_s.so.1", 2 | 256) != IntPtr.Zero, "libgcc available for native detour");
            run();
            Console.WriteLine($"NATIVE_TRANSPILER_PASS name={args[0]} assertions={checks} harmony=2.4.2.0 native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
        finally
        {
            Cleanup();
        }
    }

    private static void Cleanup()
    {
        // Dependent adapters require the BaseLib stage while Harmony recomposes.
        foreach (var owner in Owners.OrderBy(name => name == "BaseLib")) new Harmony(owner).UnpatchAll(owner);
        Owners.Clear();
    }

    [DllImport("libdl.so.2")]
    private static extern IntPtr dlopen(string file, int flags);

    private static Harmony Owner(string name)
    {
        Owners.Add(name);
        return new Harmony(name);
    }

    private static MethodInfo Method(string name) => AccessTools.Method(typeof(Program), name)!;
    private static HarmonyMethod Patch(string name) => new(Method(name));
    private static void Check(bool condition, string message)
    {
        checks++;
        if (!condition) throw new InvalidOperationException("Assertion failed: " + message);
    }

    private static void Result(int expected, params string[] trace)
    {
        Trace.Clear();
        Check(Pipeline(2) == expected, "composed return value");
        Check(Trace.SequenceEqual(trace), "runtime effects: " + string.Join(",", Trace));
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Pipeline(int value) => Identity(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Identity(int value) { Trace.Add("native"); return value; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int ReplacedIdentity(int value) { Trace.Add("replacement"); return value + 7; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int BaseStep(int value) { Trace.Add("base"); return value + 10; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int OwnStep(int value) { Trace.Add("volibear"); return value * 2; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int ForeignStep(int value) { Trace.Add("foreign"); return value + 100; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int LastStep(int value) { Trace.Add("last"); return value + 10000; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int MinimumStep(int value) { Trace.Add("minimum"); return value * 3; }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int ExtraStep(int value) { Trace.Add("extra"); return value + 10000; }
    private static void ForeignPrefix(ref int value) { Trace.Add("prefix"); value += 3; }
    private static void ForeignPostfix(ref int __result) { Trace.Add("postfix"); __result += 1000; }

    private static IEnumerable<CodeInstruction> AddStep(IEnumerable<CodeInstruction> instructions, string name)
    {
        foreach (var original in instructions)
        {
            var instruction = new CodeInstruction(original);
            if (instruction.opcode == OpCodes.Ret)
            {
                var step = new CodeInstruction(OpCodes.Call, Method(name));
                step.labels.AddRange(instruction.labels);
                instruction.labels.Clear();
                yield return step;
            }
            yield return instruction;
        }
    }

    private static IEnumerable<CodeInstruction> BaseTransformer(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(BaseStep));
    private static IEnumerable<CodeInstruction> ForeignTransformer(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(ForeignStep));
    private static IEnumerable<CodeInstruction> OwnLoose(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(OwnStep));
    private static IEnumerable<CodeInstruction> ExtraTransformer(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(ExtraStep));
    private static IEnumerable<CodeInstruction> OwnStrict(IEnumerable<CodeInstruction> input)
    {
        var code = input.ToList();
        if (code.Count(c => c.Calls(Method(nameof(Identity)))) != 1 ||
            code.Count(c => c.Calls(Method(nameof(BaseStep)))) != 1 ||
            code.Any(c => c.Calls(Method(nameof(ForeignStep))) || c.Calls(Method(nameof(LastStep))) || c.Calls(Method(nameof(MinimumStep)))))
            throw new InvalidOperationException("native-anchor conflict");
        return AddStep(code, nameof(OwnStep));
    }

    [HarmonyPriority(Priority.Last)]
    [HarmonyAfter(Adapter)]
    [HarmonyBefore("Volibear.Minimum")]
    private static IEnumerable<CodeInstruction> LastTransformer(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(LastStep));
    private static IEnumerable<CodeInstruction> MinimumTransformer(IEnumerable<CodeInstruction> code) => AddStep(code, nameof(MinimumStep));

    private static void Base() => Owner("BaseLib").Patch(Method(nameof(Pipeline)), transpiler: Patch(nameof(BaseTransformer)));
    private static void ForeignPatches() => Owner(Foreign).Patch(Method(nameof(Pipeline)),
        prefix: Patch(nameof(ForeignPrefix)), postfix: Patch(nameof(ForeignPostfix)), transpiler: Patch(nameof(ForeignTransformer)));
    private static void Own() => NativeTranspiler.Patch(Owner(Adapter), Method(nameof(Pipeline)), transpiler: Patch(nameof(OwnStrict)));

    private static void DefaultOrder(bool foreignFirst)
    {
        Base();
        if (foreignFirst) { ForeignPatches(); Own(); }
        else { Own(); ForeignPatches(); }
        Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
        var info = Harmony.GetPatchInfo(Method(nameof(Pipeline)))!;
        Check(info.Transpilers.Single(p => p.owner == Adapter).priority == Priority.High, "default adapter priority");
        Check(info.Transpilers.Single(p => p.owner == Foreign).priority == Priority.Normal, "foreign priority untouched");
    }

    private static void LegacyOrderConflict()
    {
        Base(); ForeignPatches();
        Exception? failure = null;
        try { Owner(Adapter).Patch(Method(nameof(Pipeline)), transpiler: Patch(nameof(OwnStrict))); }
        catch (Exception error) { failure = error; }
        Check(failure?.ToString().Contains("native-anchor conflict", StringComparison.Ordinal) == true,
            "original default-priority policy fails with foreign installed first");
        Owner(Adapter).Unpatch(Method(nameof(Pipeline)), HarmonyPatchType.All, Adapter);
        Own();
        Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
    }

    private static void LegalRegistrationOrders()
    {
        // These are all permutations that respect Volibear's declared BaseLib dependency.
        foreach (var sequence in new[] { "BVF", "BFV", "FBV" })
        {
            foreach (var stage in sequence)
            {
                if (stage == 'B') Base();
                else if (stage == 'F') ForeignPatches();
                else Own();
            }
            Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
            Cleanup();
        }
    }

    private static void ExplicitForeignOrder()
    {
        Base();
        Owner(Foreign).Patch(Method(nameof(Pipeline)), prefix: Patch(nameof(ForeignPrefix)),
            postfix: Patch(nameof(ForeignPostfix)), transpiler:
                new HarmonyMethod(Method(nameof(ForeignTransformer))) { before = [Adapter] });
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(Pipeline)), transpiler: Patch(nameof(OwnLoose)));
        Result(1230, "prefix", "native", "base", "foreign", "volibear", "postfix");
        Check(!Harmony.GetPatchInfo(Method(nameof(Pipeline)))!.Transpilers.Single(p => p.owner == Adapter).before.Contains(Foreign),
            "foreign before-adapter declaration is not turned into a cycle");
        Cleanup();
        Base(); ForeignPatches();
        var annotation = new HarmonyMethod(Method(nameof(OwnLoose))) { after = [Foreign] };
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(Pipeline)), transpiler: annotation);
        Result(1230, "prefix", "native", "base", "foreign", "volibear", "postfix");
        Check(annotation.priority == -1 && annotation.before is null && annotation.after.SequenceEqual([Foreign]),
            "wrapper leaves caller's explicit after metadata unchanged");
    }

    private static void IndirectForeignOrder()
    {
        // F -> Link -> BaseLib -> Volibear is an explicit, indirect precedence chain.
        Owner(Foreign).Patch(Method(nameof(Pipeline)), prefix: Patch(nameof(ForeignPrefix)),
            postfix: Patch(nameof(ForeignPostfix)), transpiler:
                new HarmonyMethod(Method(nameof(ForeignTransformer))) { before = ["Foreign.Link"] });
        Owner("Foreign.Link").Patch(Method(nameof(Pipeline)), transpiler:
            new HarmonyMethod(Method(nameof(ExtraTransformer))) { before = ["BaseLib"] });
        Base();
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(Pipeline)), transpiler: Patch(nameof(OwnLoose)));
        Result(21230, "prefix", "native", "foreign", "extra", "base", "volibear", "postfix");
        var ours = Harmony.GetPatchInfo(Method(nameof(Pipeline)))!.Transpilers.Single(p => p.owner == Adapter);
        Check(!ours.before.Contains(Foreign) && !ours.before.Contains("Foreign.Link"), "indirect cycles are not introduced");
    }

    private static void MixedOwnerPriorities()
    {
        Base();
        var foreign = Owner(Foreign);
        foreign.Patch(Method(nameof(Pipeline)), prefix: Patch(nameof(ForeignPrefix)), postfix: Patch(nameof(ForeignPostfix)),
            transpiler: new HarmonyMethod(Method(nameof(ForeignTransformer))) { priority = Priority.First });
        foreign.Patch(Method(nameof(Pipeline)), transpiler: Patch(nameof(ExtraTransformer)));
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(Pipeline)), transpiler: Patch(nameof(OwnLoose)));
        Result(11230, "prefix", "native", "foreign", "base", "volibear", "extra", "postfix");
        var info = Harmony.GetPatchInfo(Method(nameof(Pipeline)))!;
        Check(!info.Transpilers.Single(p => p.owner == Adapter).before.Contains(Foreign), "mixed-priority owner is not forced behind adapter");
        Check(info.Transpilers.Where(p => p.owner == Foreign).Select(p => p.priority).Order().SequenceEqual([Priority.Normal, Priority.First]),
            "both external priorities preserved");
    }

    private static void TailOrder()
    {
        Base();
        // Register the last stage first to exercise explicit constraints during recomposition.
        NativeTranspiler.Patch(Owner("Volibear.Minimum"), Method(nameof(Pipeline)),
            transpiler: new HarmonyMethod(Method(nameof(MinimumTransformer)))
            { priority = int.MinValue, after = ["Volibear.Last"] });
        NativeTranspiler.Patch(Owner("Volibear.Last"), Method(nameof(Pipeline)), transpiler: Patch(nameof(LastTransformer)));
        ForeignPatches(); Own();
        Result(31390, "prefix", "native", "base", "volibear", "foreign", "last", "minimum", "postfix");
        var info = Harmony.GetPatchInfo(Method(nameof(Pipeline)))!;
        Check(info.Transpilers.Single(p => p.owner == "Volibear.Last").priority == Priority.Last, "Last preserved");
        Check(info.Transpilers.Single(p => p.owner == "Volibear.Minimum").priority == int.MinValue, "minimum preserved");
    }

    private static void Reinstall()
    {
        Base(); Own(); ForeignPatches();
        Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
        Owner(Adapter).Unpatch(Method(nameof(Pipeline)), HarmonyPatchType.All, Adapter);
        Result(1115, "prefix", "native", "base", "foreign", "postfix");
        Own();
        Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
        Owner(Foreign).Unpatch(Method(nameof(Pipeline)), HarmonyPatchType.All, Foreign);
        Result(24, "native", "base", "volibear");
        ForeignPatches();
        Result(1130, "prefix", "native", "base", "volibear", "foreign", "postfix");
        Check(Harmony.GetPatchInfo(Method(nameof(Pipeline)))!.Transpilers.Count(p => p.owner == Adapter) == 1,
            "reinstall did not duplicate adapter");
    }

    private static void Metadata()
    {
        var source = new HarmonyMethod(Method(nameof(OwnStrict)))
        {
            category = "fixture", declaringType = typeof(Program), methodName = nameof(OwnStrict),
            methodType = MethodType.Normal, argumentTypes = [typeof(IEnumerable<CodeInstruction>)],
            before = ["Volibear.Next"], after = ["Volibear.Previous"],
            reversePatchType = HarmonyReversePatchType.Snapshot, debug = false, nonVirtualDelegate = true,
        };
        var ordered = NativeTranspiler.Order(source);
        Check(!ReferenceEquals(source, ordered), "copy has separate identity");
        foreach (var field in typeof(HarmonyMethod).GetFields(BindingFlags.Public | BindingFlags.Instance))
        {
            if (field.Name is nameof(HarmonyMethod.priority) or nameof(HarmonyMethod.after)) continue;
            var left = field.GetValue(source); var right = field.GetValue(ordered);
            Check(left is Array original && right is Array copy
                ? original.Cast<object>().SequenceEqual(copy.Cast<object>()) : Equals(left, right),
                "preserved annotation " + field.Name);
        }
        Check(source.priority == -1 && ordered.priority == Priority.High, "only unset priority defaults");
        Check(source.after.SequenceEqual(["Volibear.Previous"]) &&
            ordered.after.SequenceEqual(["Volibear.Previous", "BaseLib"]), "after appended without source mutation");
        Check(!ReferenceEquals(source.before, ordered.before) && !ReferenceEquals(source.after, ordered.after) &&
            !ReferenceEquals(source.argumentTypes, ordered.argumentTypes), "mutable arrays copied");
        ordered.before[0] = "changed"; ordered.argumentTypes[0] = typeof(string);
        Check(source.before[0] == "Volibear.Next" && source.argumentTypes[0] == typeof(IEnumerable<CodeInstruction>),
            "mutating copy leaves caller metadata intact");
        Check(NativeTranspiler.Order(ordered).after.Count(p => p == "BaseLib") == 1, "ordering is idempotent");
        foreach (var priority in new[] { Priority.Normal, Priority.Last, int.MinValue })
            Check(NativeTranspiler.Order(new HarmonyMethod(Method(nameof(OwnStrict))) { priority = priority }).priority == priority,
                "explicit priority retained: " + priority);
        foreach (var annotation in new[] {
            NativeTranspiler.Order(new HarmonyMethod(typeof(Program), nameof(LastTransformer))),
            NativeTranspiler.Order(new HarmonyMethod(Method(nameof(LastTransformer)))) })
            Check(annotation.method == Method(nameof(LastTransformer)) && annotation.priority == Priority.Last &&
                annotation.before.Contains("Volibear.Minimum") && annotation.after.SequenceEqual([Adapter, "BaseLib"]),
                "For preserves method attributes");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int NopTarget(int value) => Increment(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int LegacyNopTarget(int value) => Increment(value);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Increment(int value) { Trace.Add("increment"); return value + 1; }
    private static IEnumerable<CodeInstruction> InsertPadding(IEnumerable<CodeInstruction> input)
    {
        foreach (var instruction in input)
        {
            if (instruction.Calls(Method(nameof(Increment)))) yield return new CodeInstruction(OpCodes.Nop);
            yield return new CodeInstruction(instruction);
        }
    }
    private static IEnumerable<CodeInstruction> StrictPaddingMatcher(IEnumerable<CodeInstruction> input)
    {
        var code = input.ToList();
        int call = code.FindIndex(c => c.Calls(Method(nameof(Increment))));
        if (call < 1 || code[call - 1].opcode != OpCodes.Ldarg_0)
            throw new InvalidOperationException("adjacent native argument changed");
        return AddStep(code, nameof(OwnStep));
    }
    private static IEnumerable<CodeInstruction> NormalizedPaddingMatcher(IEnumerable<CodeInstruction> input) =>
        StrictPaddingMatcher(NativeTranspiler.WithoutUnanchoredNops(input));

    private static void NopPadding()
    {
        var foreign = Owner(Foreign); var own = Owner(Adapter);
        foreign.Patch(Method(nameof(LegacyNopTarget)), transpiler: Patch(nameof(InsertPadding)));
        Exception? failure = null;
        try { own.Patch(Method(nameof(LegacyNopTarget)), transpiler: Patch(nameof(StrictPaddingMatcher))); }
        catch (Exception error) { failure = error; }
        Check(failure?.ToString().Contains("adjacent native argument changed", StringComparison.Ordinal) == true,
            "old adjacency matcher fails on a harmless nop");
        own.Unpatch(Method(nameof(LegacyNopTarget)), HarmonyPatchType.All, Adapter);
        foreign.Patch(Method(nameof(NopTarget)), prefix: Patch(nameof(ForeignPrefix)),
            postfix: Patch(nameof(ForeignPostfix)), transpiler: Patch(nameof(InsertPadding)));
        // Explicit Last forces padding to run first; success cannot come from reordering it away.
        NativeTranspiler.Patch(own, Method(nameof(NopTarget)), transpiler:
            new HarmonyMethod(Method(nameof(NormalizedPaddingMatcher))) { priority = Priority.Last });
        Trace.Clear();
        Check(NopTarget(2) == 1012, "padding-normalized function executes both mods");
        Check(Trace.SequenceEqual(["prefix", "increment", "volibear", "postfix"]), "padding runtime effects retained");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int GuardedTarget(int value)
    {
        try
        {
            if (value < 0) throw new ArgumentOutOfRangeException(nameof(value));
            return value + 1;
        }
        finally { Trace.Add("finally"); }
    }
    private static IEnumerable<CodeInstruction> MarkBoundaries(IEnumerable<CodeInstruction> input)
    {
        foreach (var original in input)
        {
            var instruction = new CodeInstruction(original);
            if (instruction.labels.Count != 0 && instruction.blocks.Count == 0)
            {
                var marker = new CodeInstruction(OpCodes.Nop);
                marker.labels.AddRange(instruction.labels); instruction.labels.Clear();
                yield return marker;
            }
            yield return instruction;
        }
    }
    private static IEnumerable<CodeInstruction> NormalizeOnly(IEnumerable<CodeInstruction> input) => NativeTranspiler.WithoutUnanchoredNops(input);

    private static void MarkedNops()
    {
        var method = new DynamicMethod("labels", typeof(void), Type.EmptyTypes);
        var label = method.GetILGenerator().DefineLabel();
        var branch = new CodeInstruction(OpCodes.Nop); branch.labels.Add(label);
        var boundary = new CodeInstruction(OpCodes.Nop); boundary.blocks.Add(new ExceptionBlock(ExceptionBlockType.BeginExceptionBlock));
        var source = new[] { new CodeInstruction(OpCodes.Nop), branch, boundary, new CodeInstruction(OpCodes.Ret) };
        var normalized = NativeTranspiler.WithoutUnanchoredNops(source).ToList();
        Check(normalized.Count == 3 && normalized[0].labels.SequenceEqual([label]) && normalized[1].blocks.Count == 1,
            "marked nop labels and EH boundaries retained");
        normalized[0].labels.Clear(); normalized[1].blocks.Clear(); normalized[2].opcode = OpCodes.Nop;
        Check(branch.labels.Count == 1 && boundary.blocks.Count == 1 && source[3].opcode == OpCodes.Ret,
            "output changes cannot contaminate upstream instructions");
        Owner(Foreign).Patch(Method(nameof(GuardedTarget)), transpiler: Patch(nameof(MarkBoundaries)));
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(GuardedTarget)), transpiler:
            new HarmonyMethod(Method(nameof(NormalizeOnly))) { priority = Priority.Last });
        Trace.Clear();
        Check(GuardedTarget(2) == 3 && Trace.SequenceEqual(["finally"]), "normal control flow and finally survive");
        Trace.Clear();
        bool thrown = false;
        try { _ = GuardedTarget(-1); }
        catch (ArgumentOutOfRangeException) { thrown = true; }
        Check(thrown && Trace.SequenceEqual(["finally"]), "exception branch and finally survive");
    }

    private static IEnumerable<CodeInstruction> ReplaceNative(IEnumerable<CodeInstruction> input)
    {
        foreach (var original in input)
        {
            var instruction = new CodeInstruction(original);
            if (instruction.Calls(Method(nameof(Identity)))) instruction.operand = Method(nameof(ReplacedIdentity));
            yield return instruction;
        }
    }
    private static void RealConflict()
    {
        Base();
        Owner(Foreign).Patch(Method(nameof(Pipeline)), prefix: Patch(nameof(ForeignPrefix)),
            postfix: Patch(nameof(ForeignPostfix)), transpiler:
                new HarmonyMethod(Method(nameof(ReplaceNative))) { priority = Priority.First });
        Exception? failure = null;
        try { Own(); }
        catch (Exception error) { failure = error; }
        Check(failure is InvalidOperationException && failure.InnerException is not null, "real conflicts still throw with inner exception");
        Check(failure!.Message.Contains(nameof(Pipeline), StringComparison.Ordinal) && failure.Message.Contains(Adapter, StringComparison.Ordinal) &&
            failure.Message.Contains("Foreign.Observer(priority=800)", StringComparison.Ordinal), "diagnostic names target, adapter and foreign priority");
        Check(failure.ToString().Contains("native-anchor conflict", StringComparison.Ordinal), "original conflict cause preserved");
        Owner(Adapter).Unpatch(Method(nameof(Pipeline)), HarmonyPatchType.All, Adapter);
        Result(1022, "prefix", "replacement", "base", "postfix");
        Check(Harmony.GetPatchInfo(Method(nameof(Pipeline)))!.Transpilers.Any(p => p.owner == Foreign), "foreign patch not removed");
    }
}
