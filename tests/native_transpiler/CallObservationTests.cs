using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using Volibear.Core;

internal static partial class Program
{
    private sealed class Observation
    {
        public readonly TaskCompletionSource<int> Completion = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public readonly object Payload = new();
        public readonly int[] ArgumentReads = new int[4];
        public readonly List<string> Events = [];
        public int NativeCalls, OwnBefore, OwnAfterEntries, OwnAfterSuccess, ForeignBefore, ForeignAfterSuccess;
        public Exception? SynchronousFailure;
    }

    private static Observation observed = null!;
    private static readonly Task ZeroTask = new TaskCompletionSource().Task;
    private static int zeroBefore, zeroNative, zeroAfter, zeroCaught, zeroFinally, zeroFailure, zeroRoute;

    private static Observation ReadObservation(Observation value) { value.ArgumentReads[0]++; return value; }
    private static decimal ReadRate(Observation value) { value.ArgumentReads[1]++; return 2.5m; }
    private static object ReadPayload(Observation value) { value.ArgumentReads[2]++; return value.Payload; }
    private static int ReadValue(Observation value) { value.ArgumentReads[3]++; return 40; }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task<int> ObservedTarget(Observation value) =>
        ObservedNative(ReadObservation(value), ReadRate(value), ReadPayload(value), ReadValue(value));

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task<int> ObservedNative(Observation value, decimal rate, object payload, int amount)
    {
        value.NativeCalls++;
        value.Events.Add("native-start");
        Check(rate == 2.5m && amount == 40 && ReferenceEquals(payload, value.Payload), "native receives the original value and reference arguments");
        if (value.SynchronousFailure is { } failure) throw failure;
        return FinishNative(value, rate, amount);
    }

    private static async Task<int> FinishNative(Observation value, decimal rate, int amount)
    {
        var completion = await value.Completion.Task;
        value.Events.Add("native-complete");
        return amount + (int)rate + completion;
    }

    private static void ObserveBefore(Observation value, decimal rate, object payload, int amount)
    {
        value.OwnBefore++;
        value.Events.Add("own-before");
        Check(rate == 2.5m && amount == 40 && ReferenceEquals(payload, value.Payload), "before observer receives original arguments");
    }

    private static async Task<int> ObserveAfter(Task<int> task, Observation value, decimal rate, object payload, int amount)
    {
        value.OwnAfterEntries++;
        Check(rate == 2.5m && amount == 40 && ReferenceEquals(payload, value.Payload), "after observer receives saved original arguments");
        var result = await task;
        value.OwnAfterSuccess++;
        value.Events.Add("own-after");
        return result + 10;
    }

    private static void ForeignObserveBefore(int amount)
    {
        observed.ForeignBefore++;
        observed.Events.Add("foreign-before");
        Check(amount == 40, "foreign sees the same argument at the native call");
    }

    private static Task<int> ForeignObserveAfter(Task<int> task) => FinishForeign(task, observed);
    private static async Task<int> FinishForeign(Task<int> task, Observation value)
    {
        var result = await task;
        value.ForeignAfterSuccess++;
        value.Events.Add("foreign-after");
        return result + 100;
    }

    private static IEnumerable<CodeInstruction> OwnObservation(IEnumerable<CodeInstruction> input, ILGenerator generator) =>
        NativeTranspiler.ObserveCall(input, generator, Method(nameof(ObservedNative)), Method(nameof(ObserveBefore)), Method(nameof(ObserveAfter)));

    // An independent foreign adapter duplicates the last native argument, observes it,
    // and wraps the returned task. It does not use the production observation helper.
    private static IEnumerable<CodeInstruction> ForeignObservation(IEnumerable<CodeInstruction> input)
    {
        var matches = 0;
        foreach (var source in input)
        {
            var instruction = new CodeInstruction(source);
            if (!instruction.Calls(Method(nameof(ObservedNative)))) { yield return instruction; continue; }
            matches++;
            var duplicate = new CodeInstruction(OpCodes.Dup);
            duplicate.labels.AddRange(instruction.labels);
            duplicate.blocks.AddRange(instruction.blocks.Where(block => block.blockType != ExceptionBlockType.EndExceptionBlock));
            var after = new CodeInstruction(OpCodes.Call, Method(nameof(ForeignObserveAfter)));
            after.blocks.AddRange(instruction.blocks.Where(block => block.blockType == ExceptionBlockType.EndExceptionBlock));
            instruction.labels.Clear(); instruction.blocks.Clear();
            yield return duplicate;
            yield return new CodeInstruction(OpCodes.Call, Method(nameof(ForeignObserveBefore)));
            yield return instruction;
            yield return after;
        }
        if (matches != 1) throw new InvalidOperationException("foreign native-call anchor was removed");
    }

    private static void InstallObservation(bool foreignFirst)
    {
        void OwnObserver() => NativeTranspiler.Patch(Owner(Adapter), Method(nameof(ObservedTarget)),
            transpiler: new HarmonyMethod(Method(nameof(OwnObservation))) { priority = Priority.Normal });
        void ForeignObserver() => Owner(Foreign).Patch(Method(nameof(ObservedTarget)), transpiler: Patch(nameof(ForeignObservation)));
        if (foreignFirst) { ForeignObserver(); OwnObserver(); }
        else { OwnObserver(); ForeignObserver(); }
    }

    private static void ObserveComposition()
    {
        foreach (var foreignFirst in new[] { false, true })
        {
            InstallObservation(foreignFirst);
            observed = new Observation();
            var result = ObservedTarget(observed);
            Check(!result.IsCompleted && observed.OwnAfterEntries == 1, "native task remains asynchronous and is passed to observer once");
            observed.Completion.SetResult(3);
            Check(result.GetAwaiter().GetResult() == 155, "native result and both independently installed observer effects survive");
            Check(observed.ArgumentReads.All(count => count == 1), "argument expressions are evaluated exactly once");
            Check(observed.NativeCalls == 1 && observed.OwnBefore == 1 && observed.OwnAfterSuccess == 1 &&
                observed.ForeignBefore == 1 && observed.ForeignAfterSuccess == 1, "both before and after observers run exactly once");
            var before = foreignFirst ? new[] { "foreign-before", "own-before" } : ["own-before", "foreign-before"];
            var after = foreignFirst ? new[] { "own-after", "foreign-after" } : ["foreign-after", "own-after"];
            Check(observed.Events.SequenceEqual([.. before, "native-start", "native-complete", .. after]), "shared-call observers retain their installed nesting order");
            var patches = Harmony.GetPatchInfo(Method(nameof(ObservedTarget)))!.Transpilers;
            Check(patches.All(patch => patch.priority == Priority.Normal), "observation does not claim higher priority than foreign adapters");
            Check(!patches.Single(patch => patch.owner == Adapter).before.Contains(Foreign), "observation does not add foreign-owner precedence");
            Cleanup();
        }
    }

    private static void ObserveAsyncOutcomes()
    {
        foreach (var foreignFirst in new[] { false, true })
        {
            InstallObservation(foreignFirst);
            observed = new Observation();
            var fault = new ApplicationException("native async failure");
            var failed = ObservedTarget(observed);
            observed.Completion.SetException(fault);
            Exception? caught = null;
            try { _ = failed.GetAwaiter().GetResult(); } catch (Exception error) { caught = error; }
            Check(ReferenceEquals(caught, fault) && failed.IsFaulted, "original asynchronous exception is preserved");
            Check(observed.NativeCalls == 1 && observed.OwnBefore == 1 && observed.ForeignBefore == 1 &&
                observed.OwnAfterEntries == 1 && observed.OwnAfterSuccess == 0 && observed.ForeignAfterSuccess == 0,
                "failed native task does not run successful-completion observers");

            observed = new Observation();
            using var cancellation = new CancellationTokenSource();
            cancellation.Cancel();
            var cancelled = ObservedTarget(observed);
            observed.Completion.SetCanceled(cancellation.Token);
            OperationCanceledException? cancellationError = null;
            try { _ = cancelled.GetAwaiter().GetResult(); } catch (OperationCanceledException error) { cancellationError = error; }
            Check(cancelled.IsCanceled && cancellationError?.CancellationToken == cancellation.Token, "task cancellation and token are preserved");
            Check(observed.NativeCalls == 1 && observed.OwnAfterEntries == 1 && observed.OwnAfterSuccess == 0 &&
                observed.ForeignAfterSuccess == 0, "cancellation does not refresh or complete successful observations");

            observed = new Observation { SynchronousFailure = fault };
            caught = null;
            try { _ = ObservedTarget(observed); } catch (Exception error) { caught = error; }
            Check(ReferenceEquals(caught, fault), "synchronous native call failure remains synchronous");
            Check(observed.NativeCalls == 1 && observed.OwnBefore == 1 && observed.ForeignBefore == 1 &&
                observed.OwnAfterEntries == 0 && observed.ForeignAfterSuccess == 0, "no after observer is entered when the native call throws synchronously");
            Cleanup();
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task ZeroTarget() => ZeroNative();
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task ZeroNative()
    {
        zeroNative++;
        if (zeroFailure == 2) throw new ApplicationException("native failure");
        return ZeroTask;
    }
    private static void BeforeZero()
    {
        zeroBefore++;
        if (zeroFailure == 1) throw new ApplicationException("before failure");
    }
    private static Task AfterZero(Task task)
    {
        zeroAfter++;
        if (zeroFailure == 3) throw new ApplicationException("after failure");
        return task;
    }
    private static IEnumerable<CodeInstruction> ZeroBoth(IEnumerable<CodeInstruction> input, ILGenerator generator) =>
        NativeTranspiler.ObserveCall(input, generator, Method(nameof(ZeroNative)), Method(nameof(BeforeZero)), Method(nameof(AfterZero)));
    private static IEnumerable<CodeInstruction> ZeroBeforeOnly(IEnumerable<CodeInstruction> input, ILGenerator generator) =>
        NativeTranspiler.ObserveCall(input, generator, Method(nameof(ZeroNative)), before: Method(nameof(BeforeZero)));
    private static IEnumerable<CodeInstruction> ZeroAfterOnly(IEnumerable<CodeInstruction> input, ILGenerator generator) =>
        NativeTranspiler.ObserveCall(input, generator, Method(nameof(ZeroNative)), after: Method(nameof(AfterZero)));
    private static void ResetZero(int failure = 0)
    {
        zeroBefore = zeroNative = zeroAfter = zeroCaught = zeroFinally = zeroRoute = 0;
        zeroFailure = failure;
    }

    private static void ObserveZeroArguments()
    {
        foreach (var (transformer, before, after) in new[] {
            (nameof(ZeroBeforeOnly), 1, 0), (nameof(ZeroAfterOnly), 0, 1), (nameof(ZeroBoth), 1, 1) })
        {
            NativeTranspiler.Patch(Owner(Adapter), Method(nameof(ZeroTarget)),
                transpiler: new HarmonyMethod(Method(transformer)) { priority = Priority.Normal });
            ResetZero();
            Check(ReferenceEquals(ZeroTarget(), ZeroTask), "zero-argument observation retains the task when observers pass it through");
            Check(zeroNative == 1 && zeroBefore == before && zeroAfter == after, "optional before and after observers are independently supported");
            Cleanup();
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task ProtectedZeroTarget()
    {
        try { return ZeroNative(); }
        catch (ApplicationException) { zeroCaught++; return Task.CompletedTask; }
        finally { zeroFinally++; }
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task BranchedZeroTarget(bool first)
    {
        if (first) { zeroRoute = 1; goto invoke; }
        zeroRoute = 2;
    invoke:
        return ZeroNative();
    }

    private static void ObserveMetadata()
    {
        var generator = new DynamicMethod("observation-metadata", typeof(void), Type.EmptyTypes).GetILGenerator();
        var label = generator.DefineLabel();
        var call = new CodeInstruction(OpCodes.Call, Method(nameof(ObservedNative)));
        call.labels.Add(label);
        call.blocks.Add(new ExceptionBlock(ExceptionBlockType.BeginExceptionBlock));
        call.blocks.Add(new ExceptionBlock(ExceptionBlockType.EndExceptionBlock));
        var tail = new CodeInstruction(OpCodes.Ret);
        var rewritten = NativeTranspiler.ObserveCall([call, tail], generator, Method(nameof(ObservedNative)),
            Method(nameof(ObserveBefore)), Method(nameof(ObserveAfter))).ToList();
        Check(rewritten[0].opcode == OpCodes.Stloc && rewritten[0].labels.SequenceEqual([label]), "branch labels move before argument spilling");
        Check(rewritten[0].blocks.Select(block => block.blockType).SequenceEqual([ExceptionBlockType.BeginExceptionBlock]), "exception entry covers before observation and native call");
        Check(rewritten[^2].Calls(Method(nameof(ObserveAfter))) && rewritten[^2].blocks.Select(block => block.blockType)
            .SequenceEqual([ExceptionBlockType.EndExceptionBlock]), "exception end follows the final task observer");
        var retained = rewritten.Single(instruction => instruction.Calls(Method(nameof(ObservedNative))));
        Check(retained.labels.Count == 0 && retained.blocks.Count == 0 && rewritten.Count(instruction => instruction.Calls(Method(nameof(ObservedNative)))) == 1,
            "native call operand is retained once with no duplicated metadata");
        rewritten[0].labels.Clear(); rewritten[^2].blocks.Clear(); retained.operand = Method(nameof(ZeroNative)); rewritten[^1].opcode = OpCodes.Nop;
        Check(call.labels.Count == 1 && call.blocks.Count == 2 && call.Calls(Method(nameof(ObservedNative))) && tail.opcode == OpCodes.Ret,
            "rewriting and consumer mutations leave source instructions and metadata untouched");

        var protectedCall = PatchProcessor.GetOriginalInstructions(Method(nameof(ProtectedZeroTarget)))
            .Single(instruction => instruction.Calls(Method(nameof(ZeroNative))));
        Check(protectedCall.blocks.Any(block => block.blockType == ExceptionBlockType.BeginExceptionBlock), "real fixture starts its protected region on the native call");
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(ProtectedZeroTarget)),
            transpiler: new HarmonyMethod(Method(nameof(ZeroBoth))) { priority = Priority.Normal });
        foreach (var failure in new[] { 0, 1, 2, 3 })
        {
            ResetZero(failure);
            _ = ProtectedZeroTarget();
            Check(zeroFinally == 1 && zeroCaught == (failure == 0 ? 0 : 1), "original catch/finally contains native and observer failures");
            Check(zeroBefore == 1 && zeroNative == (failure == 1 ? 0 : 1) && zeroAfter == (failure is 0 or 3 ? 1 : 0),
                "protected observers and native dispatch execute only along the original path");
        }
        var branchCall = PatchProcessor.GetOriginalInstructions(Method(nameof(BranchedZeroTarget)))
            .Single(instruction => instruction.Calls(Method(nameof(ZeroNative))));
        Check(branchCall.labels.Count > 0, "real branch fixture targets the native call");
        NativeTranspiler.Patch(Owner(Adapter), Method(nameof(BranchedZeroTarget)),
            transpiler: new HarmonyMethod(Method(nameof(ZeroBoth))) { priority = Priority.Normal });
        foreach (var branch in new[] { false, true })
        {
            ResetZero();
            Check(ReferenceEquals(BranchedZeroTarget(branch), ZeroTask) && zeroRoute == (branch ? 1 : 2), "original branch reaches the unchanged native task");
            Check(zeroBefore == 1 && zeroNative == 1 && zeroAfter == 1, "branch entry cannot skip the before observer");
        }
    }

    private static Task<int> BadBeforeReturn(Observation value, decimal rate, object payload, int amount) => Task.FromResult(amount);
    private static void BadBeforeParameters(int amount) { }
    private static Task BadAfterReturn(Task<int> task, Observation value, decimal rate, object payload, int amount) => task;
    private static Task<int> BadAfterParameters(Task<int> task, Observation value) => task;
    private static Task<int> ByReferenceNative(ref int value) => Task.FromResult(value);
    private static Task<T> OpenNative<T>(T value) => Task.FromResult(value);
    private static Task<int> VarargNative(__arglist) => Task.FromResult(1);
    private sealed class InstanceNativeHolder { public Task<int> Native(int value) => Task.FromResult(value); }

    private static void ObserveValidation()
    {
        var generator = new DynamicMethod("observation-invalid", typeof(void), Type.EmptyTypes).GetILGenerator();
        var native = Method(nameof(ObservedNative));
        var before = Method(nameof(ObserveBefore));
        var after = Method(nameof(ObserveAfter));
        CodeInstruction Call() => new(OpCodes.Call, native);
        void Reject<T>(Action action, string reason) where T : Exception
        {
            Exception? failure = null;
            try { action(); } catch (Exception error) { failure = error; }
            Check(failure is T, reason + ": " + failure);
        }
        Reject<InvalidOperationException>(() => NativeTranspiler.ObserveCall([], generator, native, before, after), "missing native call fails closed");
        Reject<InvalidOperationException>(() => NativeTranspiler.ObserveCall([Call(), Call()], generator, native, before, after), "duplicate native calls are ambiguous");
        Reject<NotSupportedException>(() => NativeTranspiler.ObserveCall([new(OpCodes.Tailcall), Call()], generator, native, before, after), "tail-call prefix is rejected");
        Reject<NotSupportedException>(() => NativeTranspiler.ObserveCall([new(OpCodes.Callvirt, native)], generator, native, before, after), "callvirt is outside the static-call contract");
        Reject<ArgumentException>(() => NativeTranspiler.ObserveCall([Call()], generator, native), "an observer must be supplied");
        Reject<ArgumentException>(() => NativeTranspiler.ObserveCall([Call()], generator, native, Method(nameof(BadBeforeReturn))), "before must return void");
        Reject<ArgumentException>(() => NativeTranspiler.ObserveCall([Call()], generator, native, Method(nameof(BadBeforeParameters))), "before parameters must exactly match");
        Reject<ArgumentException>(() => NativeTranspiler.ObserveCall([Call()], generator, native, after: Method(nameof(BadAfterReturn))), "after must retain exact task type");
        Reject<ArgumentException>(() => NativeTranspiler.ObserveCall([Call()], generator, native, after: Method(nameof(BadAfterParameters))), "after parameters must include original arguments");
        foreach (var unsupported in new[] { Method(nameof(ByReferenceNative)), Method(nameof(OpenNative)), Method(nameof(VarargNative)),
            AccessTools.Method(typeof(InstanceNativeHolder), nameof(InstanceNativeHolder.Native))! })
            Reject<NotSupportedException>(() => NativeTranspiler.ObserveCall([new(OpCodes.Call, unsupported)], generator, unsupported, before),
                "unsupported native signature " + unsupported.Name);
        Reject<NotSupportedException>(() => NativeTranspiler.ObserveCall([new(OpCodes.Call, Method(nameof(Identity)))], generator,
            Method(nameof(Identity)), Method(nameof(BadBeforeParameters))), "non-task return cannot be observed by this async adapter");
    }
}
