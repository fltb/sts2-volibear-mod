using Volibear.Core;

// LIGHTNING-05 / DEPLOY-01: direct production dispatcher and counter calls.
// Listener/delegate fixtures do not stand in for native worlds or Subscription.Dispose.
internal static class Program
{
    private sealed class Listener(Func<Task> callback)
    {
        internal bool Active = true;
        internal Task Invoke() => callback();
    }
    private static int count;
    private static readonly Dictionary<string, Func<Task>> Cases = new()
    {
        ["serial-controlled-await"] = Serial,
        ["snapshot-add-next-batch"] = Added,
        ["inactive-removal-and-live-order"] = Inactive,
        ["closed-scope-after-await"] = Closed,
        ["fault-after-counter-commit"] = Fault,
        ["cancel-after-counter-commit"] = Cancel,
        ["same-delegate-distinct-instances"] = Instances,
        ["nested-independent-snapshots"] = Nested,
        ["empty-snapshot-no-world-read"] = Empty,
    };
    private static void Check(bool actual, bool expected, string rule)
    {
        count++;
        if (actual != expected) throw new Exception($"{rule}: expected {expected}, got {actual}");
    }
    private static void Trace(List<string> actual, params string[] expected)
    {
        count++;
        if (!actual.SequenceEqual(expected)) throw new Exception($"Trace expected [{string.Join(',', expected)}], actual [{string.Join(',', actual)}]");
    }
    private static TaskCompletionSource Gate() => new(TaskCreationOptions.RunContinuationsAsynchronously);

    private static async Task Serial()
    {
        var events = new List<string>(); var release = Gate();
        var listeners = new[] {
            new Listener(async () => { events.Add("first-enter"); await release.Task; events.Add("first-exit"); }),
            new Listener(() => { events.Add("second"); return Task.CompletedTask; }),
        };
        var task = LightningResponseDispatch.Run(listeners,
            () => { events.Add("live"); return true; },
            listener => { events.Add("active"); return listener.Active; }, listener => listener.Invoke());
        Check(task.IsCompleted, false, "dispatch awaits real suspended callback");
        Trace(events, "live", "active", "first-enter");
        release.SetResult(); await task;
        Check(task.IsCompletedSuccessfully, true, "dispatch completes after callback");
        Trace(events, "live", "active", "first-enter", "first-exit", "live", "active", "second");
    }
    private static async Task Added()
    {
        var events = new List<string>(); var listeners = new List<Listener>(); bool added = false;
        var late = new Listener(() => { events.Add("late"); return Task.CompletedTask; });
        listeners.Add(new Listener(() => {
            events.Add("first");
            if (!added) { listeners.Add(late); added = true; }
            return Task.CompletedTask;
        }));
        listeners.Add(new Listener(() => { events.Add("second"); return Task.CompletedTask; }));
        await LightningResponseDispatch.Run(listeners, () => true, x => x.Active, x => x.Invoke());
        Check(listeners.Count == 3, true, "callback really added a listener");
        Trace(events, "first", "second");
        events.Clear();
        await LightningResponseDispatch.Run(listeners, () => true, x => x.Active, x => x.Invoke());
        Trace(events, "first", "second", "late");
    }
    private static async Task Inactive()
    {
        var events = new List<string>(); var listeners = new List<Listener>();
        var removed = new Listener(() => { events.Add("removed-called"); return Task.CompletedTask; });
        var initiallyInactive = new Listener(() => { events.Add("inactive-called"); return Task.CompletedTask; }) { Active = false };
        listeners.Add(new Listener(() => {
            events.Add("first"); removed.Active = false; listeners.Remove(removed); return Task.CompletedTask;
        }));
        listeners.Add(removed); listeners.Add(initiallyInactive);
        listeners.Add(new Listener(() => { events.Add("last"); return Task.CompletedTask; }));
        int liveReads = 0, activeReads = 0;
        await LightningResponseDispatch.Run(listeners, () => { liveReads++; return true; },
            x => { activeReads++; return x.Active; }, x => x.Invoke());
        Trace(events, "first", "last");
        Check(listeners.Contains(removed), false, "fixture removal actually applied");
        Check(liveReads == 4 && activeReads == 4, true, "snapshot entries each checked, including inactive");
        events.Clear(); liveReads = activeReads = 0;
        await LightningResponseDispatch.Run(listeners, () => { liveReads++; return false; },
            x => { activeReads++; return x.Active; }, x => x.Invoke());
        Trace(events);
        Check(liveReads == 1, true, "denied world stops at first snapshot entry");
        Check(activeReads == 0, true, "denied world never reads active or invokes");
    }
    private static async Task Closed()
    {
        var counter = new LightningCounter(); var ticket = counter.Begin(1, 1);
        Check(counter.Complete(ticket, out var completed) && completed == 1, true, "real count committed before notify");
        var events = new List<string>(); var release = Gate(); int activeReads = 0;
        var listeners = new[] {
            new Listener(async () => { events.Add("first-enter"); await release.Task; events.Add("first-exit"); }),
            new Listener(() => { events.Add("second"); return Task.CompletedTask; }),
        };
        var task = LightningResponseDispatch.Run(listeners, () => !counter.IsClosed,
            x => { activeReads++; return x.Active; }, x => x.Invoke());
        Trace(events, "first-enter");
        counter.Close();
        Check(counter.IsClosed, true, "actual counter closed while first callback suspended");
        Check(task.IsCompleted, false, "closing does not fabricate callback completion");
        release.SetResult(); await task;
        Trace(events, "first-enter", "first-exit");
        Check(activeReads == 1, true, "closed scope rejects later listener before active read");
        var fresh = new LightningCounter(); var freshEvents = new List<string>();
        await LightningResponseDispatch.Run(new[] { new Listener(() => { freshEvents.Add("fresh"); return Task.CompletedTask; }) },
            () => !fresh.IsClosed, x => x.Active, x => x.Invoke());
        Trace(freshEvents, "fresh");
    }
    private static async Task Fault()
    {
        var counter = new LightningCounter(); var ticket = counter.Begin(2, 3);
        Check(counter.Complete(ticket, out var completed) && completed == 1, true, "actual complete before faulting notification");
        var original = new InvalidOperationException("listener failure"); var release = Gate();
        var events = new List<string>();
        var listeners = new[] {
            new Listener(async () => { events.Add("first"); await release.Task; throw original; }),
            new Listener(() => { events.Add("forbidden-tail"); return Task.CompletedTask; }),
        };
        var task = LightningResponseDispatch.Run(listeners, () => !counter.IsClosed, x => x.Active, x => x.Invoke());
        Check(task.IsCompleted, false, "faulting callback first suspends");
        release.SetResult(); Exception? caught = null;
        try { await task; } catch (Exception error) { caught = error; }
        Check(ReferenceEquals(caught, original), true, "same fault object propagates");
        Check(task.IsFaulted, true, "dispatcher task faults");
        Trace(events, "first");
        Check(counter.Read(2, 3) == 1, true, "listener fault cannot undo real completed count");
        Check(counter.Complete(ticket, out completed), false, "fault cannot make old ticket replayable");
        var next = counter.Begin(2, 3);
        Check(counter.Complete(next, out completed) && completed == 2, true, "next genuine batch can commit");
    }
    private static async Task Cancel()
    {
        var counter = new LightningCounter(); var ticket = counter.Begin(4, 4);
        Check(counter.Complete(ticket, out var completed) && completed == 1, true, "actual complete before cancellation");
        using var cancellation = new CancellationTokenSource();
        var original = new OperationCanceledException("listener cancelled", cancellation.Token);
        var release = Gate(); var events = new List<string>();
        var listeners = new[] {
            new Listener(async () => { events.Add("first"); await release.Task; throw original; }),
            new Listener(() => { events.Add("forbidden-tail"); return Task.CompletedTask; }),
        };
        var task = LightningResponseDispatch.Run(listeners, () => !counter.IsClosed, x => x.Active, x => x.Invoke());
        Check(task.IsCompleted, false, "cancellable callback really waits");
        cancellation.Cancel(); release.SetResult(); Exception? caught = null;
        try { await task; } catch (Exception error) { caught = error; }
        Check(ReferenceEquals(caught, original), true, "same cancellation exception propagates");
        Check(task.IsCanceled, true, "dispatcher task retains cancellation status");
        Check(caught is OperationCanceledException errorWithToken && errorWithToken.CancellationToken == cancellation.Token, true, "same cancellation token");
        Trace(events, "first");
        Check(counter.Read(4, 4) == 1, true, "cancellation does not undo committed count");
        Check(counter.Complete(ticket, out completed), false, "cancelled notification does not refund batch ticket");
        var next = counter.Begin(4, 4);
        Check(counter.Complete(next, out completed) && completed == 2, true, "next genuine batch still commits");
    }
    private static async Task Instances()
    {
        int calls = 0; Func<Task> callback = () => { calls++; return Task.CompletedTask; };
        var first = new Listener(callback); var second = new Listener(callback);
        Check(ReferenceEquals(first, second), false, "distinct deployment fixtures");
        await LightningResponseDispatch.Run(new[] { first, second }, () => true, x => x.Active, x => x.Invoke());
        Check(calls == 2, true, "same callback object receives one call per instance");
        first.Active = false;
        await LightningResponseDispatch.Run(new[] { first, second }, () => true, x => x.Active, x => x.Invoke());
        Check(calls == 3, true, "deactivating first does not deactivate second");
    }
    private static async Task Nested()
    {
        var events = new List<string>(); var listeners = new List<Listener>(); bool nested = false;
        var late = new Listener(() => { events.Add("late-inner"); return Task.CompletedTask; });
        listeners.Add(new Listener(async () => {
            if (nested) { events.Add("first-inner"); return; }
            events.Add("first-outer"); listeners.Add(late); nested = true;
            await LightningResponseDispatch.Run(listeners, () => true, x => x.Active, x => x.Invoke());
            nested = false; events.Add("outer-resume");
        }));
        listeners.Add(new Listener(() => { events.Add(nested ? "second-inner" : "second-outer"); return Task.CompletedTask; }));
        await LightningResponseDispatch.Run(listeners, () => true, x => x.Active, x => x.Invoke());
        Check(listeners.Count == 3, true, "nested dispatch receives newly added listener");
        Trace(events, "first-outer", "first-inner", "second-inner", "late-inner", "outer-resume", "second-outer");
    }
    private static async Task Empty()
    {
        int enumerations = 0;
        IEnumerable<Listener> EmptyListeners() { enumerations++; yield break; }
        await LightningResponseDispatch.Run(EmptyListeners(),
            () => throw new Exception("empty snapshot must not read world"),
            _ => throw new Exception("empty snapshot must not read active"),
            _ => throw new Exception("empty snapshot must not invoke"));
        Check(enumerations == 1, true, "empty input snapshotted exactly once");
        int reads = 0, calls = 0;
        await LightningResponseDispatch.Run(new[] { new Listener(() => { calls++; return Task.CompletedTask; }) },
            () => { reads++; return true; }, x => x.Active, x => x.Invoke());
        Check(reads == 1 && calls == 1, true, "nonempty allowed control reads world and invokes");
    }
    private static async Task<int> Main(string[] args)
    {
        if (args is ["--list"]) { foreach (var name in Cases.Keys) Console.WriteLine(name); return 0; }
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run)) return 2;
        try { await run(); Console.WriteLine($"LIGHTNING_RESPONSE_PASS name={args[0]} assertions={count} native-gameplay=NOT_RUN"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
