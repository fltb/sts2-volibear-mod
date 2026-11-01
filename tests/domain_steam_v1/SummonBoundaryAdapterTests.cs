using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using Volibear.Core;

// Invoke the real adapter gate on its actual private Frame/Binding/Batch types.
// Native objects are uninitialized typed identity fixtures: no world state, Add,
// native await or post-Add cleanup is executed. Stale/unknown paths must not read them.
internal static class SummonBoundaryAdapterTests
{
    private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    private const BindingFlags Static = BindingFlags.Static | BindingFlags.NonPublic;
    internal static void Run()
    {
        var type = typeof(DomainSummonEffects);
        var batchType = type.GetNestedType("Batch", BindingFlags.NonPublic)!;
        var store = type.GetField("Tasks", Static)!.GetValue(null)!;
        var begin = store.GetType().GetMethod("Begin", Instance)!;
        var close = type.GetMethod("Close", Static)!;
        var frameType = type.GetNestedType("Frame", BindingFlags.NonPublic)!;
        var generation = type.GetField("_generation", Static)!;
        var gate = type.GetMethod("CancelAtGate", Static)!;
        var owner = RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        var combat = RuntimeHelpers.GetUninitializedObject(typeof(CombatState));
        var task = new TaskCompletionSource().Task;
        var checks = 0;
        var probeType = typeof(Volibear.DomainSummonD17Probe);
        var armed = probeType.GetField("_armed", Static)!;
        var probeGates = (List<object>)probeType.GetField("Gates", Static)!.GetValue(null)!;
        var observe = probeType.GetMethod("ObserveGate", Static)!;
        var variant = probeType.GetField("_variant", Static)!;
        var savedVariant = variant.GetValue(null);
        Check(!(bool)armed.GetValue(null)! && probeGates.Count == 0,
            "Typed gate fixture must not replace active native probe state.");
        object Make(Type target, params object?[] args) =>
            Activator.CreateInstance(target, Instance, null, args, null)!;
        void Check(bool value, string message)
        {
            checks++;
            if (!value) throw new InvalidOperationException(message);
        }
        void CheckGate(object? batch, long frameGeneration, bool expected, string name, bool closeFirst = false)
        {
            var binding = batch is null ? null : begin.Invoke(store,
                [batch, batchType.GetField("Generation", Instance)!.GetValue(batch), true, null, -1]);
            var frame = Make(frameType, binding, task, frameGeneration, null);
            if (closeFirst)
            {
                close.Invoke(null, [frame]);
                Check(binding!.GetType().GetField("Payload", Instance)!.GetValue(binding) is null,
                    name + ": real terminal close detaches strong payload without losing known identity");
            }
            var actual = (bool)gate.Invoke(null, [frame, "typed-fixture.pre-create"])!;
            var beforeRows = probeGates.Count;
            observe.Invoke(null, [frame, name, actual]);
            Check(probeGates.Count == beforeRows + (binding is null ? 0 : 1),
                name + ": real probe records only known retired metadata");
            if (binding is not null)
            {
                var row = probeGates[^1]; var rowType = row.GetType();
                Check((string)rowType.GetProperty("scope")!.GetValue(row)! == "retired-or-closed-summon" &&
                    (bool)rowType.GetProperty("known")!.GetValue(row)! &&
                    (bool)rowType.GetProperty("blocked")!.GetValue(row)! == actual &&
                    rowType.GetProperty("cancelled") is null && rowType.GetProperty("snapshot") is null,
                    name + ": retired receipt does not fabricate Domain cancellation or read world snapshot");
            }
            Check(actual == expected, name + ": real adapter disposition");
            Check(ReferenceEquals(frameType.GetProperty("Native", Instance)!.GetValue(frame), task),
                name + ": original fixture Task unchanged");
            if (batch is not null)
            {
                var decision = batchType.GetField("Decision", Instance)!.GetValue(batch)!;
                Check(!(bool)decision.GetType().GetProperty("Cancelled", Instance)!.GetValue(decision)!,
                    name + ": stale authority rejection is not a new Domain cancellation");
            }
        }
        DomainSummonEffects.Reset();
        try
        {
            // Parent/player stay null. Any accidental live-world/Domain-removal
            // branch in the actual observer fails rather than accepting a fake scene.
            variant.SetValue(null, "fabricator-cancel-close");
            armed.SetValue(null, true);
            var before = (long)generation.GetValue(null)!;
            var oldBatch = Make(batchType, owner, combat, false);
            DomainSummonEffects.Reset();
            var current = (long)generation.GetValue(null)!;
            var freshBatch = Make(batchType, owner, combat, false);
            CheckGate(null, current, false, "unknown-current");
            CheckGate(null, before, false, "unknown-old-is-not-owned");
            CheckGate(oldBatch, before, true, "known-old-frame-and-batch");
            CheckGate(oldBatch, current, true, "known-old-batch-current-frame");
            CheckGate(freshBatch, before, true, "known-old-frame-current-batch");
            CheckGate(freshBatch, checked(current + 1), true, "known-impossible-future-frame");
            CheckGate(freshBatch, current, true, "known-closed-local-current-frame", closeFirst: true);
            Check(!(bool)probeType.GetField("_windowUsed", Static)!.GetValue(null)! &&
                probeType.GetField("_removal", Static)!.GetValue(null) is null &&
                probeType.GetField("_firstBatch", Static)!.GetValue(null) is null,
                "Retired-only observation must not open a Domain-removal window or assign a current batch.");
            Console.WriteLine($"SUMMON_GATE_ADAPTER_PASS cases=7 checks={checks} typed-frames-only=true native-gameplay=NOT_RUN");
        }
        finally
        {
            armed.SetValue(null, false); variant.SetValue(null, savedVariant); probeGates.Clear();
            DomainSummonEffects.Reset();
        }
    }
}
