using System.Collections.Concurrent;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using HarmonyLib;
using Volibear.Core;

internal static partial class Program
{
    private const string OwnId = "Fixture.OrdinarySegments";
    private const string ForeignId = "Fixture.ForeignHitHooks";
    private const string BindingId = "Fixture.PreciseDamageBinding";
    private const string PaddingId = "Fixture.AwaiterPadding";
    private const string GuardId = "Fixture.CapabilityGuard", ReplayId = "Fixture.ReplayProducer";
    private static readonly Harmony Own = new(OwnId), Foreign = new(ForeignId), Binding = new(BindingId);
    private static readonly Harmony Padding = new(PaddingId);
    private static readonly Harmony Guard = new(GuardId), Replay = new(ReplayId);
    private static readonly SteamNativeEntryBinding Channel = new();
    private static readonly AsyncLocal<object?> Paid = new();
    private static readonly AsyncLocal<int> Derived = new();
    private static readonly MethodInfo Native = Method(nameof(NativeDamage));
    private static readonly MethodInfo ExecuteMachine = AccessTools.Method(Method(nameof(Execute)).GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
    private static readonly string[] Cases = ["own-first", "foreign-first", "yield-and-restore", "legacy-producer-conflict", "awaiter-padding", "committed-capability", "validation"];
    private static int assertions;
    private static bool preciseBinding;
    private static string bindingReason = "";
    private static PatchCapabilityTracker<bool> capability = new();
    private static bool rejectRewrite, replayReplacement;

    private sealed class Result(int segment, int target, decimal value)
    {
        internal readonly int Segment = segment, Target = target;
        internal decimal Value = value;
    }

    private sealed class Request
    {
        internal readonly string Name;
        internal readonly int Segments;
        internal readonly int[] Targets = [10, 20];
        internal readonly object Dealer = new(), Card = new(), PaidScope = new();
        internal readonly decimal Amount = 2.5m;
        internal readonly int[] Reads = new int[6];
        internal readonly ConcurrentQueue<string> Events = new();
        internal readonly ConcurrentQueue<object?> Tickets = new();
        internal readonly TaskCompletionSource[] Before, Native, After, Tail;
        internal readonly TaskCompletionSource[] BeforeEntered, NativeEntered, AfterEntered, TailEntered, LoopDone;
        internal readonly Result[][] ForeignResults, OwnResults;
        internal readonly Exception Error = new InvalidOperationException("fixture-failure");
        internal readonly CancellationToken Cancel = new(canceled: true);
        internal int Captures, NativeCalls, ChildCalls, ForeignCalls, Tails, Loops, Finalized;
        internal string Failure = "";
        internal bool DerivedDamage, SkipNative;
        internal Request? Nested;
        internal Request(string name, int segments = 1, bool paused = false)
        {
            Name = name; Segments = segments;
            Before = Signals(segments, !paused); Native = Signals(segments, !paused);
            After = Signals(segments, !paused); Tail = Signals(segments, !paused);
            BeforeEntered = Signals(segments); NativeEntered = Signals(segments);
            AfterEntered = Signals(segments); TailEntered = Signals(segments); LoopDone = Signals(segments);
            ForeignResults = new Result[segments][]; OwnResults = new Result[segments][];
        }
        internal void Mark(string value) => Events.Enqueue(value);
    }

    private sealed record Observation(Request Request, int Segment, IEnumerable<int> Targets, decimal Amount,
        object Dealer, object Card, object? PaidScope);
    private readonly struct Awaitable(TaskAwaiter<Result[]> awaiter)
    { public TaskAwaiter<Result[]> GetAwaiter() => awaiter; }

    private static TaskCompletionSource[] Signals(int count, bool completed = false) => Enumerable.Range(0, count).Select(_ =>
    {
        var signal = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        if (completed) signal.SetResult();
        return signal;
    }).ToArray();

    private static void Check(bool value, string why)
    { Interlocked.Increment(ref assertions); if (!value) throw new InvalidOperationException("Assertion failed: " + why); }
    private static MethodInfo Method(string name) => AccessTools.Method(typeof(Program), name)!;
    private static async Task Wait(Task task) => await task.WaitAsync(TimeSpan.FromSeconds(10));
    private static Request ReadRequest(Request value) { Interlocked.Increment(ref value.Reads[0]); return value; }
    private static int ReadSegment(Request value, int segment) { Interlocked.Increment(ref value.Reads[1]); return segment; }
    private static IEnumerable<int> ReadTargets(Request value) { Interlocked.Increment(ref value.Reads[2]); return value.Targets; }
    private static decimal ReadAmount(Request value) { Interlocked.Increment(ref value.Reads[3]); return value.Amount; }
    private static object ReadDealer(Request value) { Interlocked.Increment(ref value.Reads[4]); return value.Dealer; }
    private static object ReadCard(Request value) { Interlocked.Increment(ref value.Reads[5]); return value.Card; }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<Result[]> Execute(Request request)
    {
        var all = new List<Result>();
        try
        {
            for (var i = 0; i < request.Segments; i++)
            {
                var results = await NativeDamage(ReadRequest(request), ReadSegment(request, i), ReadTargets(request),
                    ReadAmount(request), ReadDealer(request), ReadCard(request));
                all.AddRange(results);
                Interlocked.Increment(ref request.Loops);
                request.Mark("loop:" + i);
                request.LoopDone[i].TrySetResult();
            }
            return all.ToArray();
        }
        finally { Interlocked.Increment(ref request.Finalized); request.Mark("finally"); }
    }

    private static async Task<Result[]> PaidExecute(Request request)
    {
        var previous = Paid.Value;
        Paid.Value = request.PaidScope;
        try { return await Execute(request); }
        finally { Paid.Value = previous; }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<Result[]> NativeDamage(Request request, int segment, IEnumerable<int> targets,
        decimal amount, object dealer, object card)
    {
        var ticket = Channel.Consume();
        request.Tickets.Enqueue(ticket);
        Check(ReferenceEquals(targets, request.Targets) && amount == request.Amount &&
            ReferenceEquals(dealer, request.Dealer) && ReferenceEquals(card, request.Card), "native receives original argument values");
        var child = Derived.Value > 0;
        if (child) Interlocked.Increment(ref request.ChildCalls); else Interlocked.Increment(ref request.NativeCalls);
        request.Mark((child ? "child-native:" : "native:") + segment);
        if (!child) request.NativeEntered[segment].TrySetResult();
        await request.Native[segment].Task;
        if (!child) Fail(request, "native");
        return targets.Select((target, index) => new Result(segment, target, amount + index)).ToArray();
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<Result[]> ForeignDamage(Request request, int segment, IEnumerable<int> targets,
        decimal amount, object dealer, object card, int injected)
    {
        Check(injected == 37, "foreign replacement receives its independently inserted argument");
        Interlocked.Increment(ref request.ForeignCalls);
        request.Mark("foreign-before:" + segment);
        request.BeforeEntered[segment].TrySetResult();
        await request.Before[segment].Task;
        Fail(request, "before");
        if (request.DerivedDamage)
        {
            Derived.Value++;
            try { _ = await NativeDamage(request, segment, targets, amount, dealer, card); }
            finally { Derived.Value--; }
        }
        if (request.Nested is { } nested && segment == 0)
        {
            _ = await PaidExecute(nested);
            Check(ReferenceEquals(Paid.Value, request.PaidScope), "nested attack restores the outer paid scope");
        }
        var results = request.SkipNative
            ? request.Targets.Select(target => new Result(segment, target, 900)).ToArray()
            : await NativeDamage(request, segment, targets, amount, dealer, card);
        request.Mark("foreign-after:" + segment);
        request.AfterEntered[segment].TrySetResult();
        await request.After[segment].Task;
        Fail(request, "after");
        foreach (var result in results) result.Value += 100;
        request.ForeignResults[segment] = results;
        return results;
    }

    private static Observation Capture(Request request, int segment, IEnumerable<int> targets,
        decimal amount, object dealer, object card)
    {
        Interlocked.Increment(ref request.Captures);
        request.Mark("capture:" + segment);
        Check(ReferenceEquals(Paid.Value, request.PaidScope), "descriptor captures the actual paid scope before foreign hooks");
        Fail(request, "capture");
        return new(request, segment, targets, amount, dealer, card, Paid.Value);
    }

    private static TaskAwaiter<Result[]> Compose(TaskAwaiter<Result[]> native, Observation observation) =>
        FinishOwn(native, observation).GetAwaiter();

    private static async Task<Result[]> FinishOwn(TaskAwaiter<Result[]> native, Observation observation)
    {
        var results = await new Awaitable(native);
        var request = observation.Request; var segment = observation.Segment;
        Check(ReferenceEquals(observation.PaidScope, request.PaidScope), "completion retains the captured paid scope");
        Check(ReferenceEquals(observation.Targets, request.Targets) && observation.Amount == request.Amount &&
            ReferenceEquals(observation.Dealer, request.Dealer) && ReferenceEquals(observation.Card, request.Card), "completion retains all captured arguments");
        Interlocked.Increment(ref request.Tails);
        request.Mark("own-tail:" + segment);
        request.TailEntered[segment].TrySetResult();
        await request.Tail[segment].Task;
        Fail(request, "tail");
        foreach (var result in results) result.Value += 10;
        request.OwnResults[segment] = results;
        return results;
    }

    private static void Fail(Request request, string stage)
    {
        if (request.Failure == stage) throw request.Error;
        if (request.Failure == "cancel-" + stage) throw new OperationCanceledException(request.Cancel);
    }

    private static IEnumerable<CodeInstruction> ComposeNative(IEnumerable<CodeInstruction> input, ILGenerator generator) =>
        NativeAwaitedCall.Compose(input, generator, Native, Method(nameof(Capture)), Method(nameof(Compose)));

    // This optional late adapter exercises the production capability decision and
    // exact-entry handoff. It never adopts a foreign helper as a native call.
    private static IEnumerable<CodeInstruction> BindNative(IEnumerable<CodeInstruction> input)
    {
        var code = input.Select(c => new CodeInstruction(c)).ToList();
        preciseBinding = NativeCallCapability.CanBindExactCall(code, Native, out bindingReason);
        capability.Observe(ExecuteMachine, preciseBinding);
        if (!preciseBinding) return code;
        code.Single(c => c.Calls(Native)).operand = Method(nameof(DispatchNative));
        return code;
    }

    private static Task<Result[]> DispatchNative(Request request, int segment, IEnumerable<int> targets,
        decimal amount, object dealer, object card)
    {
        using var dispatch = Channel.Dispatch(request);
        return NativeDamage(request, segment, targets, amount, dealer, card);
    }

    private static void InstallOwn() => NativeTranspiler.Patch(Own, ExecuteMachine,
        transpiler: new HarmonyMethod(Method(nameof(ComposeNative))));
    private static void InstallForeign() => Foreign.Patch(ExecuteMachine,
        transpiler: new HarmonyMethod(Method(nameof(ForeignReplace))) { priority = Priority.Last });
    private static void InstallBinding()
    {
        Channel.Install(Binding, Native);
        NativeTranspiler.Patch(Binding, ExecuteMachine,
            transpiler: new HarmonyMethod(Method(nameof(BindNative))) { priority = NativeCallCapability.LatePriority });
    }

    private static void Verify(Request request, Result[] actual, bool foreign, bool own, bool bound)
    {
        Check(request.Reads.All(count => count == request.Segments), "every original argument evaluated once per segment: " + request.Name);
        Check(request.Captures == (own ? request.Segments : 0) && request.Tails == (own ? request.Segments : 0), "one own composition per segment, not per target");
        Check(request.ForeignCalls == (foreign ? request.Segments : 0), "foreign hooks execute once per segment");
        Check(request.NativeCalls == (request.SkipNative ? 0 : request.Segments), "native execution respects foreign skip behavior");
        Check(request.ChildCalls == (request.DerivedDamage ? request.Segments : 0), "derived same-argument damage executes independently");
        Check(request.Loops == request.Segments && request.Finalized == 1 && actual.Length == request.Segments * request.Targets.Length,
            "all segments and targets complete with one finally");
        Check(request.Tickets.All(ticket => bound ? ReferenceEquals(ticket, request) : ticket is null), "precise native provenance never claims foreign or child calls");
        for (var segment = 0; segment < request.Segments; segment++)
        {
            var expected = own ? request.OwnResults[segment] : foreign ? request.ForeignResults[segment] : null;
            if (expected is not null)
                Check(actual.Where(result => result.Segment == segment).SequenceEqual(expected), "result object identity and ordering survive composition");
            var rows = actual.Where(result => result.Segment == segment).ToArray();
            for (var target = 0; target < rows.Length; target++)
                Check(rows[target].Value == (request.SkipNative ? 900 : request.Amount + target) + (foreign ? 100 : 0) + (own ? 10 : 0), "both observable damage contributions preserved");
        }
    }

    private static async Task Drive(Request request)
    {
        for (var i = 0; i < request.Segments; i++)
        {
            await Wait(request.BeforeEntered[i].Task);
            Check(request.Loops == i && request.Tails == i, "next segment waits for the entire prior segment");
            request.Before[i].TrySetResult();
            await Wait(request.NativeEntered[i].Task);
            Check(request.Tails == i, "own tail does not precede native completion");
            request.Native[i].TrySetResult();
            await Wait(request.AfterEntered[i].Task);
            Check(request.Tails == i, "own tail waits for foreign after hooks");
            request.After[i].TrySetResult();
            await Wait(request.TailEntered[i].Task);
            Check(request.Loops == i, "native continuation awaits the composed tail");
            request.Tail[i].TrySetResult();
            await Wait(request.LoopDone[i].Task);
        }
    }

    private static async Task Composition(bool foreignFirst)
    {
        if (foreignFirst) InstallForeign();
        InstallOwn(); InstallBinding();
        if (!foreignFirst) InstallForeign();
        Check(!preciseBinding && !string.IsNullOrWhiteSpace(bindingReason), "optional precise binding yields with an explicit reason");
        var metadata = Harmony.GetPatchInfo(ExecuteMachine)!;
        Check(metadata.Transpilers.Single(p => p.owner == ForeignId).priority == Priority.Last, "foreign priority left unchanged");
        var gated = new Request("gated multi-hit AOE", 3, paused: true);
        var task = PaidExecute(gated);
        await Drive(gated);
        var actual = await task;
        Verify(gated, actual, foreign: true, own: true, bound: false);
        Check(gated.Events.SequenceEqual(Enumerable.Range(0, 3).SelectMany(i => new[] { "capture:" + i, "foreign-before:" + i, "native:" + i,
            "foreign-after:" + i, "own-tail:" + i, "loop:" + i }).Append("finally")), "actual async effect ordering is exact");

        var derived = new Request("same-argument child") { DerivedDamage = true };
        Verify(derived, await PaidExecute(derived), foreign: true, own: true, bound: false);
        var skipped = new Request("foreign replacement result") { SkipNative = true };
        Verify(skipped, await PaidExecute(skipped), foreign: true, own: true, bound: false);
        var inner = new Request("nested", 2);
        var outer = new Request("outer", 2) { Nested = inner };
        var outerResult = await PaidExecute(outer);
        Verify(outer, outerResult, foreign: true, own: true, bound: false);
        Verify(inner, inner.OwnResults.SelectMany(row => row).ToArray(), foreign: true, own: true, bound: false);
        Check(Paid.Value is null && Derived.Value == 0, "paid and child contexts restore after nested work");

        var first = new Request("parallel A", 2, paused: true);
        var second = new Request("parallel B", 2, paused: true);
        var one = PaidExecute(first); var two = PaidExecute(second);
        await Task.WhenAll(Drive(second), Drive(first));
        Verify(first, await one, foreign: true, own: true, bound: false);
        Verify(second, await two, foreign: true, own: true, bound: false);

        foreach (var failure in new[] { "capture", "before", "native", "after", "tail", "cancel-before", "cancel-native", "cancel-after", "cancel-tail" })
        {
            var broken = new Request(failure) { Failure = failure };
            var failed = PaidExecute(broken);
            try { await failed; throw new Exception("Expected operation failure: " + failure); }
            catch (OperationCanceledException error) when (failure.StartsWith("cancel-", StringComparison.Ordinal))
            { Check(error.CancellationToken == broken.Cancel && failed.IsCanceled, "cancellation status and token retained"); }
            catch (Exception error) when (ReferenceEquals(error, broken.Error))
            { Check(failed.IsFaulted, "original exception identity and task failure retained"); }
            Check(broken.Finalized == 1 && broken.Loops == 0, "failure executes native finally without a successful continuation");
            Check(broken.Tails == (failure.EndsWith("tail", StringComparison.Ordinal) ? 1 : 0), "success-only ordinary tail is skipped on earlier failure");
            Check(Paid.Value is null, "failure cannot leak the paid scope");
        }
        var later = new Request("later ordinary attack");
        Verify(later, await PaidExecute(later), foreign: true, own: true, bound: false);
    }

    private static async Task YieldAndRestore()
    {
        InstallOwn(); InstallBinding();
        Check(preciseBinding, "native capability starts available");
        var before = new Request("native before foreign", 2);
        Verify(before, await PaidExecute(before), foreign: false, own: true, bound: true);
        InstallForeign();
        Check(!preciseBinding, "later foreign replacement makes optional binding yield");
        var during = new Request("foreign active", 2) { DerivedDamage = true };
        Verify(during, await PaidExecute(during), foreign: true, own: true, bound: false);
        Foreign.UnpatchAll(ForeignId);
        Check(preciseBinding, "removing foreign replacement restores exact native binding");
        var restored = new Request("native restored", 2);
        Verify(restored, await PaidExecute(restored), foreign: false, own: true, bound: true);
        InstallForeign(); Own.UnpatchAll(OwnId);
        var foreignOnly = new Request("ordinary adapter removed");
        Verify(foreignOnly, await PaidExecute(foreignOnly), foreign: true, own: false, bound: false);
        InstallOwn();
        var reinstalled = new Request("ordinary adapter restored");
        Verify(reinstalled, await PaidExecute(reinstalled), foreign: true, own: true, bound: false);
    }

    private static IEnumerable<CodeInstruction> LegacyTaskWrapper(IEnumerable<CodeInstruction> input)
    {
        foreach (var source in input)
        {
            yield return new CodeInstruction(source);
            if (source.Calls(Native)) yield return new(OpCodes.Call, Method(nameof(LegacyTask)));
        }
    }
    private static Task<Result[]> LegacyTask(Task<Result[]> task) => task;

    private static void LegacyConflict()
    {
        Own.Patch(ExecuteMachine, transpiler: new HarmonyMethod(Method(nameof(LegacyTaskWrapper))) { priority = Priority.High });
        Exception? failure = null;
        try { InstallForeign(); } catch (Exception error) { failure = error; }
        Check(failure?.ToString().Contains("strict awaited producer contract", StringComparison.Ordinal) == true,
            "independent foreign matcher rejects the old post-call Task wrapper");
        Check(Harmony.GetPatchInfo(ExecuteMachine)!.Transpilers.All(p => p.owner != ForeignId), "failed matcher does not register a false compatible patch");
    }

    private static IEnumerable<CodeInstruction> PadAwaiter(IEnumerable<CodeInstruction> input)
    {
        var getter = typeof(Task<Result[]>).GetMethod(nameof(Task<Result[]>.GetAwaiter))!;
        foreach (var source in input)
        {
            yield return new CodeInstruction(source);
            if (!source.Calls(getter)) continue;
            yield return new(OpCodes.Nop); yield return new(OpCodes.Nop); yield return new(OpCodes.Nop);
        }
    }

    private static async Task AwaiterPadding()
    {
        Padding.Patch(ExecuteMachine, transpiler: new HarmonyMethod(Method(nameof(PadAwaiter))) { priority = Priority.First });
        InstallForeign(); // The foreign four-instruction window accepts the uncomposed padded site.
        Check(Harmony.GetPatchInfo(ExecuteMachine)!.Transpilers.Any(p => p.owner == ForeignId), "foreign matcher initially accepts harmless awaiter padding");
        InstallOwn();
        var request = new Request("padded awaiter", 2);
        Verify(request, await PaidExecute(request), foreign: true, own: true, bound: false);
    }

    private static IEnumerable<CodeInstruction> RewriteGuard(IEnumerable<CodeInstruction> input)
    {
        if (rejectRewrite) throw new InvalidOperationException("late-guard-rejected-candidate");
        return input;
    }

    private static IEnumerable<CodeInstruction> ReplayProducer(IEnumerable<CodeInstruction> input) =>
        replayReplacement ? ForeignReplace(input) : input;

    private static void ConfirmCapability(bool expected, string reason)
    {
        Check(capability.TryRead(ExecuteMachine, Method(nameof(BindNative)), out var actual) && actual == expected, reason);
    }

    private static void Reject(Action action, string reason)
    {
        Exception? rejected = null;
        try { action(); } catch (Exception error) { rejected = error; }
        Check(rejected?.ToString().Contains("late-guard-rejected-candidate", StringComparison.Ordinal) == true, reason);
    }

    private static async Task CommittedCapability()
    {
        InstallOwn();
        Replay.Patch(ExecuteMachine, transpiler: new HarmonyMethod(Method(nameof(ReplayProducer))) { priority = Priority.Last });
        Guard.Patch(ExecuteMachine, transpiler: new HarmonyMethod(Method(nameof(RewriteGuard)))
            { priority = int.MinValue, after = [BindingId] });
        InstallBinding();
        ConfirmCapability(true, "a completed installation confirms available capability");

        // A tool may replay transpilers with changed dynamic state without committing
        // a replacement. Production diagnostics must retain the installed evidence.
        replayReplacement = true;
        var replayed = PatchProcessor.GetCurrentInstructions(ExecuteMachine).ToArray();
        replayReplacement = false;
        Check(replayed.Any(c => c.Calls(Method(nameof(ForeignDamage)))) && !preciseBinding,
            "test-only replay really produced a contradictory unavailable candidate");
        ConfirmCapability(true, "replaying instructions cannot replace committed capability");
        var replaySurvivor = new Request("installed chain after diagnostic replay");
        Verify(replaySurvivor, await PaidExecute(replaySurvivor), foreign: false, own: true, bound: true);

        rejectRewrite = true;
        Reject(InstallForeign, "late guard rejects installation after capability observation");
        Check(!preciseBinding, "failed installation really observed an unavailable candidate");
        Check(Harmony.GetPatchInfo(ExecuteMachine)!.Transpilers.All(p => p.owner != ForeignId), "rejected foreign patch is absent from committed metadata");
        ConfirmCapability(true, "rejected unavailable candidate cannot overwrite installed availability");
        var failedInstallSurvivor = new Request("installed chain after rejected foreign install");
        Verify(failedInstallSurvivor, await PaidExecute(failedInstallSurvivor), foreign: false, own: true, bound: true);

        rejectRewrite = false;
        InstallForeign();
        ConfirmCapability(false, "successfully committed foreign replacement confirms yielded capability");
        rejectRewrite = true;
        Reject(() => Foreign.UnpatchAll(ForeignId), "late guard rejects foreign unpatch after available candidate observation");
        Check(preciseBinding, "failed unpatch really observed an available candidate");
        Check(Harmony.GetPatchInfo(ExecuteMachine)!.Transpilers.Any(p => p.owner == ForeignId), "rejected unpatch retains the foreign patch in committed metadata");
        ConfirmCapability(false, "rejected available candidate cannot overwrite committed yielding");
        var failedUnpatchSurvivor = new Request("foreign chain after rejected removal");
        Verify(failedUnpatchSurvivor, await PaidExecute(failedUnpatchSurvivor), foreign: true, own: true, bound: false);

        rejectRewrite = false;
        Foreign.UnpatchAll(ForeignId);
        ConfirmCapability(true, "successful unpatch restores committed native capability");
        Binding.UnpatchAll(BindingId);
        Check(!capability.TryRead(ExecuteMachine, Method(nameof(BindNative)), out _), "removed own adapter cannot report a stale capability");

        capability = new PatchCapabilityTracker<bool>();
        rejectRewrite = true;
        Reject(InstallBinding, "first binding attempt is rejected after its observation");
        Check(!capability.TryRead(ExecuteMachine, Method(nameof(BindNative)), out _), "an uncommitted first attempt has no confirmed capability");
        rejectRewrite = false;
    }

    private static int BadCapture(int value) => value;
    private static Task<Result[]> BadCompose(TaskAwaiter<Result[]> awaiter, Observation value) => Task.FromResult(Array.Empty<Result>());
    private static void Validation()
    {
        foreach (var change in new[] { "missing", "duplicate", "capture-signature", "compose-signature", "call-prefix", "awaiter-label", "awaiter-begin-exception" })
        {
            var generator = new DynamicMethod("validation", typeof(void), Type.EmptyTypes).GetILGenerator();
            var original = PatchProcessor.GetOriginalInstructions(ExecuteMachine, generator).Select(c => new CodeInstruction(c)).ToList();
            var code = original.Select(c => new CodeInstruction(c)).ToList();
            var native = code.FindIndex(c => c.Calls(Native));
            var getter = code.FindIndex(native + 1, c => c.operand is MethodInfo { Name: "GetAwaiter" });
            if (change == "missing") code.RemoveAt(native);
            if (change == "duplicate") code.Insert(native, new CodeInstruction(code[native]));
            if (change == "call-prefix") code.Insert(native, new CodeInstruction(OpCodes.Tailcall));
            if (change == "awaiter-label") code[getter].labels.Add(generator.DefineLabel());
            if (change == "awaiter-begin-exception") code[getter].blocks.Add(new ExceptionBlock(ExceptionBlockType.BeginExceptionBlock));
            Exception? error = null;
            try { _ = NativeAwaitedCall.Compose(code, generator, Native,
                Method(change == "capture-signature" ? nameof(BadCapture) : nameof(Capture)),
                Method(change == "compose-signature" ? nameof(BadCompose) : nameof(Compose))).ToArray(); }
            catch (Exception caught) { error = caught; }
            Check(error is not null, "invalid awaited composition rejected: " + change);
        }
        var il = new DynamicMethod("capability", typeof(void), Type.EmptyTypes).GetILGenerator();
        var baseline = PatchProcessor.GetOriginalInstructions(ExecuteMachine, il).ToList();
        Check(NativeCallCapability.CanBindExactCall(baseline, Native, out _), "original native capability recognized");
        var foreign = ForeignReplace(baseline).ToArray();
        Check(!NativeCallCapability.CanBindExactCall(foreign, Native, out var reason) && !string.IsNullOrWhiteSpace(reason), "foreign producer produces explicit capability yielding");
        var duplicate = baseline.Select(c => new CodeInstruction(c)).ToList(); duplicate.Add(new CodeInstruction(OpCodes.Call, Native));
        Exception? drift = null;
        try { _ = NativeCallCapability.CanBindExactCall(duplicate, Native, out _); } catch (Exception error) { drift = error; }
        Check(drift is not null, "duplicate native calls remain an explicit contract failure");
    }

    [DllImport("libdl.so.2")]
    private static extern IntPtr dlopen(string file, int flags);

    private static int Main(string[] args)
    {
        if (args.SequenceEqual(["--list"])) { foreach (var name in Cases) Console.WriteLine(name); return 0; }
        if (args.Length != 1 || !Cases.Contains(args[0])) return 2;
        try
        {
            Check(typeof(Harmony).Assembly.GetName().Version == new Version(2, 4, 2, 0), "real Harmony 2.4.2");
            if (OperatingSystem.IsLinux()) Check(dlopen("libgcc_s.so.1", 2 | 256) != IntPtr.Zero, "native detour dependency available");
            switch (args[0])
            {
                case "own-first": Composition(false).GetAwaiter().GetResult(); break;
                case "foreign-first": Composition(true).GetAwaiter().GetResult(); break;
                case "yield-and-restore": YieldAndRestore().GetAwaiter().GetResult(); break;
                case "legacy-producer-conflict": LegacyConflict(); break;
                case "awaiter-padding": AwaiterPadding().GetAwaiter().GetResult(); break;
                case "committed-capability": CommittedCapability().GetAwaiter().GetResult(); break;
                case "validation": Validation(); break;
            }
            Console.WriteLine($"AWAITED_CALL_COEXISTENCE_PASS name={args[0]} assertions={assertions} real-harmony=2.4.2.0 foreign-matcher=fixture native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        finally
        {
            rejectRewrite = false; replayReplacement = false;
            Binding.UnpatchAll(BindingId); Foreign.UnpatchAll(ForeignId); Own.UnpatchAll(OwnId); Padding.UnpatchAll(PaddingId);
            Guard.UnpatchAll(GuardId); Replay.UnpatchAll(ReplayId);
            Channel.Reset(); Paid.Value = null; Derived.Value = 0;
        }
    }
}
