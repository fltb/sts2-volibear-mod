using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Core;

internal static class Program
{
    private static int assertions;
    private static readonly PlayerChoiceContext Choices = new();
    private sealed class Response : IEngageResponder
    {
        internal readonly List<EngageCmd.Completion> Calls = [];
        public Task AfterEngageCompleted(EngageCmd.Completion completion)
        { Calls.Add(completion); return Task.CompletedTask; }
    }
    private sealed class Fixture
    {
        internal readonly CombatState State = new();
        internal readonly Player A, B;
        internal readonly CardModel CardA, CardB;
        internal readonly Response ResponseA = new(), ResponseB = new();
        internal Fixture()
        {
            A = Player(); B = Player();
            CardA = new() { Owner = A }; CardB = new() { Owner = B };
            A.Relics.Add(ResponseA); B.Relics.Add(ResponseB);
            CombatManager.Instance.Setup(State);
        }
        private Player Player()
        {
            var creature = new Creature { CombatState = State };
            var player = new Player { Creature = creature }; creature.Player = player;
            State.Members.Add(creature); return player;
        }
        internal Creature Enemy()
        {
            var creature = new Creature { CombatState = State, IsEnemy = true };
            creature.Monster = new() { Creature = creature };
            creature.Node = new() { Entity = creature };
            State.Members.Add(creature); return creature;
        }
        internal Task<EngageCmd.Result> Engage(Creature target, CardModel? card = null) =>
            EngageCmd.Perform(Choices, target, card ?? CardA);
    }
    private static void Check(bool ok, string why)
    { assertions++; if (!ok) throw new Exception(why); }

    private static async Task SkippedActions()
    {
        foreach (bool skipMoveNext in new[] { false, true })
        {
            var f = new Fixture(); var enemy = f.Enemy();
            enemy.Monster!.SkipEntry = !skipMoveNext; enemy.Monster.SkipMoveNext = skipMoveNext;
            var result = await f.Engage(enemy);
            Check(result is { Performed: false, Completed: false, Absorbed: 0 },
                "A third-party skipped native body must not fabricate a completed Engage");
            Check(f.ResponseA.Calls.Count == 0, "A skipped native body must not trigger completion rewards");
            Check(EngageCmd.Consumed(enemy), "No refund: another patch may already have produced partial effects");
            Check(enemy.Monster.BodyCalls == 0, "The fixture really skipped the action");
        }
    }

    private static async Task SharedOpportunityAndOriginalTargets()
    {
        var f = new Fixture(); var enemy = f.Enemy();
        enemy.Monster!.Targets.AddRange([f.B.Creature, f.A.Creature]);
        enemy.Node!.Intent = () => { f.A.Creature.DamageBlockInternal(99m); return Task.CompletedTask; };
        enemy.Monster.Body = m =>
        {
            foreach (var target in m.Targets)
                target.DamageBlockInternal(ReferenceEquals(target, f.A.Creature) ? 3m : 7m);
            return Task.CompletedTask;
        };
        var result = await f.Engage(enemy);
        Check(result is { Performed: true, Completed: true, Absorbed: 3 }, "Only initiator actual-action absorption counts, not intent effects");
        Check(enemy.Monster.Targets.SequenceEqual([f.B.Creature, f.A.Creature]), "Keep the native target allocation");
        Check(f.ResponseA.Calls.Count == 1 && f.ResponseB.Calls.Count == 0, "Reward only the initiator");
        Check(ReferenceEquals(f.ResponseA.Calls[0].Choices, Choices), "Preserve native player choice context");
        Check(await f.Engage(enemy, f.CardB) is { Performed: false, Completed: false, Absorbed: 0 },
            "The teammate shares the consumed enemy opportunity");
        Check(enemy.Monster.BodyCalls == 1, "No second action for the teammate");
    }

    private static async Task OnlyNormalEnemyPhaseSkips()
    {
        var f = new Fixture(); var enemy = f.Enemy(); var other = f.Enemy();
        await f.Engage(enemy);
        Check(NativeHooks.AllowTakeTurn(enemy), "Do not suppress another mod's player-phase TakeTurn");
        Check(NativeHooks.AllowIntent(enemy.Node!), "Player-phase intent rendering remains available");
        f.State.CurrentSide = CombatSide.Enemy;
        Check(!NativeHooks.AllowTakeTurn(enemy), "The spent normal enemy action is skipped");
        Check(!NativeHooks.AllowIntent(enemy.Node!), "The spent normal intent is skipped");
        Check(NativeHooks.AllowTakeTurn(other), "Other enemies still act");
        f.State.RoundNumber++;
        Check(NativeHooks.AllowTakeTurn(enemy), "The next normal round remains available");
    }

    private static async Task StaleRoundCannotResume()
    {
        var f = new Fixture(); var enemy = f.Enemy();
        var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        enemy.Node!.Intent = () => gate.Task;
        var pending = f.Engage(enemy);
        Check(!pending.IsCompleted, "The intent boundary really suspends");
        f.State.RoundNumber++;
        gate.SetResult(); var result = await pending;
        Check(result is { Performed: false, Completed: false, Absorbed: 0 }, "No old-round action after intent resumes");
        Check(enemy.Monster!.BodyCalls == 0 && f.ResponseA.Calls.Count == 0, "Stale intent has no body or rewards");
        enemy.Node.Intent = () => Task.CompletedTask;
        enemy.Monster.Body = _ => { f.State.RoundNumber++; return Task.CompletedTask; };
        result = await f.Engage(enemy);
        Check(!result.Completed && f.ResponseA.Calls.Count == 0, "Cross-round action has no later-round completion reward");
        f = new(); enemy = f.Enemy();
        enemy.Node!.Intent = () => { f.State.CurrentSide = CombatSide.Enemy; return Task.CompletedTask; };
        result = await f.Engage(enemy);
        Check(result is { Performed: false, Completed: false, Absorbed: 0 }, "A phase switch retires the old player-phase action");
        Check(enemy.Monster!.BodyCalls == 0, "The stale player action cannot race the native enemy scheduler");
    }

    private static async Task ConcurrentPlayersWhileReserved()
    {
        var f = new Fixture(); var enemy = f.Enemy();
        var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        enemy.Node!.Intent = () => gate.Task;
        var first = f.Engage(enemy, f.CardA);
        Check(!first.IsCompleted && EngageCmd.Consumed(enemy), "Reservation is committed before the first native await");
        var second = await f.Engage(enemy, f.CardB);
        Check(second is { Performed: false, Completed: false, Absorbed: 0 }, "Concurrent teammate cannot reserve the pending opportunity");
        Check(enemy.Monster!.BodyCalls == 0, "Neither intent completion nor teammate request fabricated an action");
        gate.SetResult(); var result = await first;
        Check(result.Performed && result.Completed && enemy.Monster.BodyCalls == 1, "Exactly one native body executes after the gate");
        Check(f.ResponseA.Calls.Count == 1 && f.ResponseB.Calls.Count == 0, "Only the actual initiator gets a completion response");
        Check(EngageCmd.EarlyOpportunityEntryCount == 1 && EngageCmd.NaturalOpportunityEntryCount == 1,
            "Both observations describe the same shared enemy opportunity");
    }

    private static async Task SuspendedActionAcrossRunReset()
    {
        foreach (bool reuseCombatObject in new[] { false, true })
        {
            var old = new Fixture(); var enemy = old.Enemy();
            var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            enemy.Monster!.Body = async _ =>
            {
                old.A.Creature.DamageBlockInternal(2m);
                await gate.Task;
                old.A.Creature.DamageBlockInternal(100m);
            };
            var pending = old.Engage(enemy);
            Check(!pending.IsCompleted && EngageCmd.Consumed(enemy), "A real body is suspended with a spent opportunity");
            CombatManager.Instance.Reset(false);
            Check(EngageCmd.EarlyOpportunityEntryCount == 0 && EngageCmd.NaturalOpportunityEntryCount == 0,
                "Native reset clears shared opportunity facts");
            var fresh = reuseCombatObject ? old : new Fixture();
            if (reuseCombatObject) CombatManager.Instance.Setup(fresh.State);
            var newEnemy = fresh.Enemy();
            Check(!EngageCmd.Consumed(newEnemy) && !EngageCmd.Consumed(enemy), "Restored combat starts with unspent opportunities");
            newEnemy.Monster!.Body = _ => { fresh.A.Creature.DamageBlockInternal(3m); return Task.CompletedTask; };
            var current = await fresh.Engage(newEnemy);
            Check(current.Completed && current.Absorbed == 3m && fresh.ResponseA.Calls.Count == 1,
                "New combat action works before the old async continuation resumes");
            gate.SetResult(); var stale = await pending;
            Check(stale is { Performed: true, Completed: false, Absorbed: 2m },
                "Old native continuation cannot accumulate absorption or award completion after reset");
            Check(fresh.ResponseA.Calls.Count == 1 && (reuseCombatObject || old.ResponseA.Calls.Count == 0),
                "No delayed reward is delivered to either incarnation");
            Check(EngageCmd.Consumed(newEnemy) && EngageCmd.EarlyOpportunityEntryCount == 1,
                "The stale continuation cannot erase or add to the fresh combat opportunity");
        }
    }

    private static async Task NestedAndFailureCleanup()
    {
        var f = new Fixture(); var outer = f.Enemy(); var inner = f.Enemy();
        EngageCmd.Result nested = default;
        inner.Monster!.Body = _ => { f.A.Creature.DamageBlockInternal(3m); return Task.CompletedTask; };
        outer.Monster!.Body = async _ =>
        {
            f.A.Creature.DamageBlockInternal(2m);
            nested = await f.Engage(inner);
            f.A.Creature.DamageBlockInternal(4m);
        };
        var result = await f.Engage(outer);
        Check(result.Absorbed == 6m && nested.Absorbed == 3m, "Nested windows own their absorption");
        Check(result.Completed && nested.Completed && f.ResponseA.Calls.Count == 2, "Each actual nested action completes once");
        var bad = f.Enemy(); var after = f.Enemy();
        bad.Monster!.Body = _ => { f.A.Creature.DamageBlockInternal(11m); throw new InvalidOperationException("move-failed"); };
        try { await f.Engage(bad); throw new Exception("Native exception was swallowed"); }
        catch (InvalidOperationException e) when (e.Message == "move-failed") { }
        Check(EngageCmd.Consumed(bad), "A partly executed fault is never refunded");
        Check(f.ResponseA.Calls.Count == 2, "Failed move has no completion reward");
        after.Monster!.Body = _ => { f.A.Creature.DamageBlockInternal(5m); return Task.CompletedTask; };
        result = await f.Engage(after);
        Check(result.Absorbed == 5m && result.Completed, "Failure did not leak absorption into a later window");
    }

    private static async Task DeathBoundaries()
    {
        var f = new Fixture(); var enemy = f.Enemy(); bool teammateActed = false;
        enemy.Monster!.Body = _ =>
        { f.A.Creature.IsDead = true; teammateActed = true; f.B.Creature.DamageBlockInternal(7m); return Task.CompletedTask; };
        var result = await f.Engage(enemy);
        Check(result.Performed && !result.Completed && result.Absorbed == 0m, "Dead initiator earns no reward or teammate absorption");
        Check(teammateActed && f.ResponseA.Calls.Count == 0, "Initiator death does not cancel the native multi-target action");
        f = new(); enemy = f.Enemy(); f.Enemy();
        enemy.Monster!.Body = m => { m.Creature.IsDead = true; return Task.CompletedTask; };
        result = await f.Engage(enemy);
        Check(result.Completed && f.ResponseA.Calls.Count == 1, "Enemy death during a real action may still complete Engage");
        f = new(); enemy = f.Enemy();
        enemy.Node!.Intent = () => { enemy.IsDead = true; return Task.CompletedTask; };
        result = await f.Engage(enemy);
        Check(result is { Performed: false, Completed: false, Absorbed: 0 } && enemy.Monster!.BodyCalls == 0,
            "Target death before action does not count as an action");
    }

    private static async Task StableGroupSnapshot()
    {
        var f = new Fixture(); var a = f.Enemy(); var b = f.Enemy(); Creature? summoned = null;
        var order = new List<Creature>();
        var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        a.Monster!.Body = async _ => { order.Add(a); summoned = f.Enemy(); await gate.Task; };
        b.Monster!.Body = _ => { order.Add(b); return Task.CompletedTask; };
        var pending = EngageCmd.PerformAll(Choices, f.CardA);
        Check(order.SequenceEqual([a]) && !pending.IsCompleted, "Group execution is serial across real awaits");
        gate.SetResult(); var results = await pending;
        Check(order.SequenceEqual([a, b]) && results.Count == 2 && results.All(r => r.Completed), "Stable initial enemy order");
        Check(summoned is not null && summoned.Monster!.BodyCalls == 0 && !EngageCmd.Consumed(summoned),
            "Mid-card summons are not appended to the group snapshot");
        foreach (bool reset in new[] { false, true })
        {
            f = new(); a = f.Enemy(); b = f.Enemy();
            a.Monster!.Body = _ =>
            {
                if (reset) CombatManager.Instance.Setup(f.State);
                else f.State.RoundNumber++;
                return Task.CompletedTask;
            };
            results = await EngageCmd.PerformAll(Choices, f.CardA);
            Check(results.Count == 1 && b.Monster!.BodyCalls == 0,
                "A group cannot continue into another round or a reset incarnation of the same combat");
        }
    }

    private static readonly Dictionary<string, Func<Task>> Cases = new()
    {
        ["skipped-actions"] = SkippedActions,
        ["shared-opportunity-original-targets"] = SharedOpportunityAndOriginalTargets,
        ["normal-enemy-phase-only"] = OnlyNormalEnemyPhaseSkips,
        ["stale-round"] = StaleRoundCannotResume,
        ["concurrent-reservation"] = ConcurrentPlayersWhileReserved,
        ["suspended-run-reset"] = SuspendedActionAcrossRunReset,
        ["nested-failure-cleanup"] = NestedAndFailureCleanup,
        ["death-boundaries"] = DeathBoundaries,
        ["stable-group-snapshot"] = StableGroupSnapshot,
    };
    private static async Task<int> Main(string[] args)
    {
        if (args is ["--list"]) { foreach (var name in Cases.Keys) Console.WriteLine(name); return 0; }
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run)) return 2;
        try
        {
            EngageCmd.Install(); await run();
            Console.WriteLine($"ENGAGE_ADAPTER_PASS name={args[0]} assertions={assertions} native-gameplay=NOT_RUN multiplayer-network=NOT_RUN");
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e); return 1; }
    }
}
