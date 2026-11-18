using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Presentation;

// Real Harmony composition; game nodes and power projection remain test doubles.
internal static class InteropChecks
{
    private static int checks;
    private static readonly System.Reflection.FieldInfo Field =
        AccessTools.DeclaredField(typeof(NPowerContainer), "_powerNodes");
    private static readonly System.Reflection.MethodInfo Layout =
        AccessTools.DeclaredMethod(typeof(NPowerContainer), "UpdatePositions");

    private static void Need(bool ok, string why)
    {
        checks++;
        if (!ok) throw new Exception(why);
    }

    private static PowerModel Make(NCreature creature, int amount, string id, bool supported)
    {
        var model = new PowerModel { Owner = creature.Entity, Amount = amount, Id = id, Supported = supported };
        creature.Entity.Powers.Add(model);
        return model;
    }

    private static List<NPower> Project(NPowerContainer container, List<NPower> source) =>
        (List<NPower>)AccessTools.DeclaredMethod(typeof(PowerStackVisual), "LayoutNodes")
            .Invoke(null, new object[] { container, source })!;

    private static void InstallForeign() => new Harmony("Fixture.OtherUiExtension").Patch(Layout,
        transpiler: new HarmonyMethod(typeof(InteropChecks), nameof(ForeignFieldPatch)) { priority = Priority.Normal });

    private static IEnumerable<CodeInstruction> ForeignFieldPatch(IEnumerable<CodeInstruction> instructions)
    {
        int matched = 0;
        foreach (var instruction in instructions)
        {
            yield return new CodeInstruction(instruction);
            if (instruction.opcode != OpCodes.Ldfld || !Equals(instruction.operand, Field)) continue;
            matched++;
            yield return new CodeInstruction(OpCodes.Call, AccessTools.DeclaredMethod(typeof(InteropChecks), nameof(Reverse)));
        }
        if (matched == 0) throw new InvalidOperationException("Foreign UI extension lost its native field anchor");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static List<NPower> Reverse(List<NPower> source) => source.AsEnumerable().Reverse().ToList();

    private static CodeInstruction[] Rewrite(params CodeInstruction[] source) =>
        ((IEnumerable<CodeInstruction>)AccessTools.DeclaredMethod(typeof(PowerStackVisual), "LayoutTranspiler")
            .Invoke(null, new object[] { source })!).ToArray();

    private static void MetadataChecks()
    {
        var generator = new DynamicMethod("label_owner", typeof(void), Type.EmptyTypes).GetILGenerator();
        var label = generator.DefineLabel();
        var original = new CodeInstruction(OpCodes.Ldfld, Field);
        original.labels.Add(label);
        original.blocks.Add(new ExceptionBlock(ExceptionBlockType.BeginExceptionBlock));
        original.blocks.Add(new ExceptionBlock(ExceptionBlockType.EndExceptionBlock));
        var wrapped = Rewrite(original);
        Need(wrapped.Length == 3 && wrapped[0].opcode == OpCodes.Dup && wrapped[1].opcode == OpCodes.Ldfld &&
            Equals(wrapped[1].operand, Field) && wrapped[2].Calls(AccessTools.DeclaredMethod(typeof(PowerStackVisual), "LayoutNodes")),
            "Loaded field anchor is retained between receiver duplication and value projection");
        Need(wrapped[0].labels.SequenceEqual(new[] { label }) && wrapped[1].labels.Count == 0 && wrapped[2].labels.Count == 0,
            "Branches enter before the extra receiver is duplicated");
        Need(wrapped[0].blocks.Single().blockType == ExceptionBlockType.BeginExceptionBlock && wrapped[1].blocks.Count == 0 &&
            wrapped[2].blocks.Single().blockType == ExceptionBlockType.EndExceptionBlock,
            "Exception boundaries enclose the whole inserted expression");
        Need(original.labels.Count == 1 && original.blocks.Count == 2 && original.opcode == OpCodes.Ldfld,
            "Upstream instruction and metadata are not mutated");
        bool rejected = false;
        try { Rewrite(new CodeInstruction(OpCodes.Volatile), new CodeInstruction(OpCodes.Ldfld, Field)); }
        catch (InvalidOperationException error) { rejected = error.Message.Contains("prefixed _powerNodes load"); }
        Need(rejected, "Unsupported IL prefix fails with a concrete reason instead of emitting invalid IL");
        rejected = false;
        try { Rewrite(new CodeInstruction(OpCodes.Nop)); }
        catch (InvalidOperationException error) { rejected = error.Message.Contains("no longer reads _powerNodes"); }
        Need(rejected, "A removed native field anchor is reported rather than silently accepted");
    }

    internal static void Run(string order)
    {
        if (order is not ("foreign-before" or "foreign-after")) throw new ArgumentException("Unknown fixture order: " + order);
        if (order == "foreign-before") InstallForeign();
        PowerStackVisual.Install();
        if (order == "foreign-after") InstallForeign();

        int nativeLoads = PatchProcessor.GetOriginalInstructions(Layout).Count(i => i.opcode == OpCodes.Ldfld && Equals(i.operand, Field));
        var current = PatchProcessor.GetCurrentInstructions(Layout).ToArray();
        Need(current.Count(i => i.opcode == OpCodes.Ldfld && Equals(i.operand, Field)) == nativeLoads,
            "All native shared field anchors survive both transpilers");
        Need(current.Count(i => i.Calls(AccessTools.DeclaredMethod(typeof(InteropChecks), nameof(Reverse)))) == nativeLoads &&
            current.Count(i => i.Calls(AccessTools.DeclaredMethod(typeof(PowerStackVisual), "LayoutNodes"))) == nativeLoads,
            "Both extensions consume every native field read in either registration order");
        var patch = Harmony.GetPatchInfo(Layout)!.Transpilers.Single(p => p.owner == "Volibear.PowerStackVisual");
        Need(patch.priority == Priority.Normal && patch.before.Length == 0 && patch.after.Contains("BaseLib"),
            "Additive UI patch keeps normal priority without claiming precedence over other UI owners");

        var tracker = CombatManager.Instance.StateTracker;
        var creature = new NCreature();
        var container = new NPowerContainer { Size = new(128, 32) };
        container.Enter();
        var first = container.Add(Make(creature, 5, "FOREIGN_A", false));
        var last = container.Add(Make(creature, 6, "FOREIGN_B", false));
        Need(last.Position.X == 0 && first.Position.X == 32 && tracker.Count == 0,
            "Foreign-only UI retains the other extension's reversed layout and zero projection subscriptions");
        var foreignInput = new List<NPower> { last };
        Need(ReferenceEquals(Project(container, foreignInput), foreignInput),
            "Unrelated loaded list is returned by identity even when it differs from the container field");
        container.Exit();

        creature = new NCreature();
        container = new NPowerContainer { Size = new(128, 32) };
        container.Enter();
        var a = container.Add(Make(creature, 3, "OWN", true));
        var b = container.Add(Make(creature, 4, "OWN", true));
        var foreign = container.Add(Make(creature, 9, "FOREIGN", false));
        var representative = new[] { a, b }.Single(n => n.Visible);
        Need(foreign.Position.X == 0 && representative.Position.X == 32 && PowerStackVisual.DisplayedAmount(representative) == "7",
            "Grouping and the foreign reverse layout both execute without dropping either extension");
        Need(container.All.Count == 3 && creature.Entity.Powers.Count == 3 && tracker.Count == 1,
            "Composition preserves native models and one projection subscription");
        var filteredInput = new List<NPower> { b, foreign };
        var filtered = Project(container, filteredInput);
        Need(filtered.SequenceEqual(filteredInput) && b.Visible && PowerStackVisual.DisplayedAmount(b) == "7",
            "Projection uses the actual filtered input and promotes its surviving representative");
        foreignInput = new List<NPower> { foreign };
        Need(ReferenceEquals(Project(container, foreignInput), foreignInput) && tracker.Count == 0,
            "Filtering out all supported nodes returns native list and retires projection state");
        container.Exit();
        Need(tracker.Count == 0, "Composition lifecycle releases its own subscriptions");
        MetadataChecks();
        Console.WriteLine($"POWER_STACK_VISUAL_INTEROP_PASS order={order} checks={checks} production-ui=LINKED tree-and-projection=TEST-DOUBLES");
    }
}
