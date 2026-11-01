using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using Volibear.Core;

// Actual Subscription, OwnerScope, counter and ResetCombatState, not a duplicated
// subscription model. Typed native identity fixtures are never used for world reads.
// The dispatch liveness predicate is explicitly limited to Counter.IsClosed here;
// native CanUse/HP/round/turn wiring remains outside this fixture's scope.
internal static class LightningResponseAdapterTests
{
    internal static async Task Run()
    {
        var checks = 0;
        void Check(bool valid, string message)
        {
            checks++;
            if (!valid) throw new InvalidOperationException(message);
        }
        var scopes = (Dictionary<ICombatState, Dictionary<Creature, LightningBatches.OwnerScope>>)
            typeof(LightningBatches).GetField("Scopes", BindingFlags.Static | BindingFlags.NonPublic)!.GetValue(null)!;
        Check(scopes.Count == 0, "Fixture must not overwrite another scope's live state.");
        var combat = (ICombatState)RuntimeHelpers.GetUninitializedObject(typeof(CombatState));
        var owner = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        var otherOwner = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        var context = (PlayerChoiceContext)RuntimeHelpers.GetUninitializedObject(typeof(BlockingPlayerChoiceContext));
        var scope = new LightningBatches.OwnerScope();
        var other = new LightningBatches.OwnerScope();
        var release = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var calls = new List<string>();
        Task? dispatch = null;
        try
        {
            scopes.Add(combat, new Dictionary<Creature, LightningBatches.OwnerScope>(ReferenceEqualityComparer.Instance)
            { [owner] = scope, [otherOwner] = other });
            var ticket = scope.Counter.Begin(1, 1);
            Check(scope.Counter.Complete(ticket, out var count) && count == 1, "Batch count commits before dispatch.");
            var pendingOther = other.Counter.Begin(1, 1);
            var batch = new LightningBatch(ticket.Id, combat, owner, null, 1, 1, 3, 0, 3,
                Array.Empty<Creature>(), Array.Empty<LightningHit>(), count);
            var first = new LightningBatches.Subscription(scope, (actualContext, actualBatch) =>
            {
                Check(ReferenceEquals(actualContext, context) && ReferenceEquals(actualBatch, batch),
                    "Actual subscription forwards exact context and batch.");
                Check(scope.Counter.Read(1, 1) == 1, "Listener sees already committed count.");
                calls.Add("first");
                return release.Task;
            });
            var second = new LightningBatches.Subscription(scope, (_, _) => { calls.Add("second"); return Task.CompletedTask; });
            var third = new LightningBatches.Subscription(scope, (_, _) => { calls.Add("third"); return Task.CompletedTask; });
            var otherListener = new LightningBatches.Subscription(other, (_, _) => Task.CompletedTask);
            scope.Listeners.AddRange([first, second, third]); other.Listeners.Add(otherListener);
            dispatch = LightningResponseDispatch.Run(scope.Listeners,
                () => !scope.Counter.IsClosed, listener => listener.Active,
                listener => listener.Invoke(context, batch));
            Check(!dispatch.IsCompleted && calls.SequenceEqual(new[] { "first" }), "Original pending callback blocks later listeners.");
            second.Dispose(); second.Dispose();
            Check(!second.Active && !scope.Listeners.Contains(second) && scope.Listeners.Count == 2,
                "Real Dispose removes exactly one registration and is idempotent.");
            Check(first.Active && third.Active && otherListener.Active, "Disposing one instance leaves other registrations active.");
            LightningBatches.ResetCombatState();
            Check(scopes.Count == 0, "Actual reset removes all combat scope registrations.");
            Check(scope.Counter.IsClosed && other.Counter.IsClosed, "Actual reset closes both owners' counters.");
            Check(!first.Active && !third.Active && !otherListener.Active &&
                scope.Listeners.Count == 0 && other.Listeners.Count == 0,
                "Actual reset disposes all remaining registrations.");
            Check(!other.Counter.Complete(pendingOther, out _), "Other owner's old pending ticket cannot complete after reset.");
            Check(!dispatch.IsCompleted && !release.Task.IsCompleted, "Reset does not fabricate completion of the existing callback Task.");
            release.SetResult();
            await dispatch;
            Check(calls.SequenceEqual(new[] { "first" }), "After original callback settles, closed scope starts no later callback.");
            Check(scope.Counter.Read(1, 1) == 0, "Closed old combat cannot publish a live turn count.");
            Console.WriteLine($"LIGHTNING_RESPONSE_ADAPTER_PASS checks={checks} actual-subscription-reset=true native-world=NOT_RUN");
        }
        finally
        {
            LightningBatches.ResetCombatState();
            release.TrySetResult();
            if (dispatch is not null && !dispatch.IsCompleted) await dispatch;
        }
    }
}
