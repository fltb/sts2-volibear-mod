using Volibear.Core;

// Direct production-kernel calls. Literal expected guards derive from ENEMY-01/04,
// RUN-03 and E05/E06/E07/E14/E16, not a second opportunity implementation.
// Objects are identity fixtures, not fake native enemies/combat. No native lifecycle is run.
internal static class Program
{
    private static int assertions;
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["reserve-reentry-partial-failure"] = ReserveFailure,
        ["natural-versus-early-skip"] = NaturalEarly,
        ["round-and-separate-enemies"] = Rounds,
        ["reference-equality-collisions"] = Identity,
        ["combat-and-enemy-membership-guards"] = Membership,
        ["reset-and-combat-aba"] = ResetAba,
        ["diagnostic-entry-counts"] = DiagnosticCounts,
        ["suspended-interleaving"] = () => Interleaving().GetAwaiter().GetResult(),
    };

    private static void Expect(bool actual, bool expected, string guard)
    {
        assertions++;
        if (actual != expected) throw new Exception($"{guard}: expected {expected}, got {actual}");
    }

    private static void ReserveFailure()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new object(); var enemy = new object();
        ledger.EnsureCombat(combat);
        Expect(ledger.Consumed(combat, combat, enemy, 3), false, "available initially");
        Expect(ledger.TryReserve(combat, combat, enemy, 3), true, "reserve synchronously");
        Expect(ledger.Consumed(combat, combat, enemy, 3), true, "reserved before action starts");
        Expect(ledger.TryReserve(combat, combat, enemy, 3), false, "reentry before native action rejected");
        Expect(ledger.ObserveActionStart(combat, combat, enemy, 3), true, "real action starts after reservation");
        try { throw new InvalidOperationException("caller partially executed then failed"); }
        catch (InvalidOperationException) { }
        Expect(ledger.Consumed(combat, combat, enemy, 3), true, "failure cannot undo committed reservation");
        Expect(ledger.EarlyConsumed(combat, combat, enemy, 3), true, "normal phase still skips partial early action");
        Expect(ledger.TryReserve(combat, combat, enemy, 3), false, "no partial-action retry");
    }

    private static void NaturalEarly()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new object(); var natural = new object(); var early = new object();
        ledger.EnsureCombat(combat);
        Expect(ledger.ObserveActionStart(combat, combat, natural, 1), true, "natural entry recorded");
        Expect(ledger.Consumed(combat, combat, natural, 1), true, "natural consumes engage eligibility");
        Expect(ledger.TryReserve(combat, combat, natural, 1), false, "no engage after natural");
        Expect(ledger.EarlyConsumed(combat, combat, natural, 1), false, "natural is NOT normal-phase skip authority");
        Expect(ledger.ObserveActionStart(combat, combat, natural, 1), true, "observation does not suppress native execution");
        Expect(ledger.EarlyConsumed(combat, combat, natural, 1), false, "repeated natural observation never marks early");
        Expect(ledger.TryReserve(combat, combat, early, 1), true, "other enemy early reservation");
        Expect(ledger.ObserveActionStart(combat, combat, early, 1), true, "early real move is also observed");
        Expect(ledger.EarlyConsumed(combat, combat, early, 1), true, "observation preserves early skip");
        Expect(ledger.TryReserve(combat, combat, early, 1), false, "early plus natural not a second opportunity");
    }

    private static void Rounds()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new object(); var a = new object(); var b = new object();
        ledger.EnsureCombat(combat);
        Expect(ledger.TryReserve(combat, combat, a, 8), true, "A early round8");
        Expect(ledger.Consumed(combat, combat, b, 8), false, "A cannot consume B");
        Expect(ledger.ObserveActionStart(combat, combat, b, 8), true, "B natural round8");
        ledger.EnsureCombat(combat);
        Expect(ledger.TryReserve(combat, combat, a, 8), false, "same-combat ensure does not clear early");
        Expect(ledger.TryReserve(combat, combat, b, 8), false, "same-combat ensure does not clear natural");
        Expect(ledger.EarlyConsumed(combat, combat, a, 9), false, "no next-round scheduler skip");
        Expect(ledger.Consumed(combat, combat, b, 9), false, "natural next-round eligible");
        Expect(ledger.TryReserve(combat, combat, b, 9), true, "B early round9");
        Expect(ledger.TryReserve(combat, combat, a, 9), true, "A early round9 independent");
        Expect(ledger.TryReserve(combat, combat, a, 9), false, "A round9 repeat rejected");
        Expect(ledger.TryReserve(combat, combat, b, 9), false, "B round9 repeat rejected");
    }

    private sealed class EqualObject
    {
        public override bool Equals(object? obj) => obj is EqualObject;
        public override int GetHashCode() => 7;
    }

    private static void Identity()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new EqualObject(); var otherCombat = new EqualObject();
        var a = new EqualObject(); var b = new EqualObject();
        Expect(a.Equals(b) && a.GetHashCode() == b.GetHashCode(), true, "deterministic Equals and hash collision");
        Expect(ReferenceEquals(a, b), false, "distinct enemy references");
        ledger.EnsureCombat(combat);
        var generation = ledger.Generation;
        Expect(ledger.TryReserve(combat, combat, a, 1), true, "first equal enemy");
        Expect(ledger.Consumed(combat, combat, b, 1), false, "equal enemy is not consumed");
        Expect(ledger.TryReserve(combat, combat, b, 1), true, "second equal enemy independent");
        Expect(ledger.TryReserve(otherCombat, otherCombat, new object(), 1), false, "equal combat cannot impersonate current");
        ledger.EnsureCombat(otherCombat);
        Expect(ledger.IsCurrent(combat, generation), false, "equal combat switch invalidates old authority");
        Expect(ledger.TryReserve(otherCombat, otherCombat, a, 1), true, "new combat clears old opportunity");
        Expect(ledger.Consumed(otherCombat, otherCombat, b, 1), false, "other enemy old fact cleared too");
    }

    private static void Membership()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new object(); var foreign = new object(); var enemy = new object();
        Expect(ledger.TryReserve(combat, combat, enemy, 1), false, "no implicit authority on reserve");
        Expect(ledger.ObserveActionStart(combat, combat, enemy, 1), false, "no implicit authority on observe");
        ledger.EnsureCombat(combat);
        Expect(ledger.TryReserve(combat, foreign, enemy, 1), false, "enemy outside actual combat rejected");
        Expect(ledger.TryReserve(foreign, combat, enemy, 1), false, "stale caller combat rejected");
        Expect(ledger.ObserveActionStart(combat, foreign, enemy, 1), false, "foreign natural observation rejected");
        Expect(ledger.ObserveActionStart(foreign, combat, enemy, 1), false, "stale natural observation rejected");
        Expect(ledger.TryReserve(combat, null, enemy, 1), false, "detached enemy rejected");
        Expect(ledger.TryReserve(combat, combat, enemy, 1), true, "invalid requests did not spend valid opportunity");
        Expect(ledger.Consumed(foreign, combat, enemy, 1), false, "stale query has no authority");
        Expect(ledger.EarlyConsumed(combat, foreign, enemy, 1), false, "departed enemy not skipped");
        Expect(ledger.Consumed(null, null, enemy, 1), false, "absent combat not consumed");
    }

    private static void ResetAba()
    {
        var ledger = new EngageOpportunityLedger();
        var a = new object(); var b = new object(); var enemy = new object();
        ledger.EnsureCombat(a); var old = ledger.Generation;
        Expect(ledger.TryReserve(a, a, enemy, 1), true, "old A reservation");
        ledger.EnsureCombat(a);
        Expect(ledger.IsCurrent(a, old), true, "same actual combat preserves window");
        ledger.Reset();
        Expect(ledger.IsCurrent(a, old), false, "reset immediately revokes window");
        Expect(ledger.TryReserve(a, a, enemy, 1), false, "reset cannot be undone by late reserve");
        Expect(ledger.ObserveActionStart(a, a, enemy, 1), false, "late observation cannot reopen reset");
        ledger.EnsureCombat(a); var reopened = ledger.Generation;
        Expect(ledger.IsCurrent(a, old), false, "same object after reset is not old authority");
        Expect(ledger.IsCurrent(a, reopened), true, "fresh A authority");
        Expect(ledger.TryReserve(a, a, enemy, 1), true, "fresh A same round eligible");
        ledger.EnsureCombat(b); var middle = ledger.Generation;
        Expect(ledger.IsCurrent(a, reopened), false, "combat switch revokes even without reset event");
        Expect(ledger.TryReserve(a, a, enemy, 1), false, "late A cannot reserve in B");
        ledger.EnsureCombat(a);
        Expect(ledger.IsCurrent(a, reopened), false, "A B A cannot revive suspended A");
        Expect(ledger.IsCurrent(b, middle), false, "B authority retired");
        Expect(ledger.TryReserve(a, a, enemy, 1), true, "new A opportunity independent");
        ledger.Reset(); ledger.Reset();
        Expect(ledger.Consumed(a, a, enemy, 1), false, "repeated reset clears facts");
    }

    private static void DiagnosticCounts()
    {
        var ledger = new EngageOpportunityLedger();
        var a = new object(); var b = new object(); var early = new object(); var natural = new object();
        Expect(ledger.EarlyEntryCount == 0 && ledger.NaturalEntryCount == 0, true, "fresh ledger has no diagnostic entries");
        ledger.EnsureCombat(a);
        Expect(ledger.EarlyEntryCount == 0 && ledger.NaturalEntryCount == 0, true, "combat initialization does not create entries");
        Expect(ledger.TryReserve(a, a, early, 1) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 0,
            true, "reservation counts only early entry");
        Expect(ledger.ObserveActionStart(a, a, early, 1) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 1,
            true, "same enemy early and real action each count in their own projection");
        Expect(ledger.ObserveActionStart(a, a, natural, 1) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 2,
            true, "natural-only enemy does not create early entry");
        ledger.ObserveActionStart(a, a, natural, 1);
        Expect(ledger.NaturalEntryCount == 2, true, "repeated observation does not duplicate diagnostic entry");
        Expect(ledger.TryReserve(a, a, early, 2) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 2,
            true, "next-round replacement retains original dictionary-count semantics");
        Expect(!ledger.Consumed(a, a, early, 3) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 2,
            true, "unconsumed in queried round does not erase retained diagnostic history");
        ledger.EnsureCombat(b);
        Expect(ledger.EarlyEntryCount == 0 && ledger.NaturalEntryCount == 0, true, "combat switch clears both projections");
        Expect(ledger.TryReserve(b, b, early, 1) && ledger.EarlyEntryCount == 1 && ledger.NaturalEntryCount == 0,
            true, "new combat gets its own diagnostic entries");
        ledger.Reset();
        Expect(ledger.EarlyEntryCount == 0 && ledger.NaturalEntryCount == 0, true, "reset clears both projections");
    }

    private static async Task Interleaving()
    {
        var ledger = new EngageOpportunityLedger();
        var combat = new object(); var outer = new object(); var inner = new object();
        ledger.EnsureCombat(combat); var generation = ledger.Generation;
        var release = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        // Explicit test orchestration, NOT a replacement Perform implementation.
        async Task SuspendAfterReservation()
        {
            Expect(ledger.TryReserve(combat, combat, outer, 4), true, "outer reserves before suspension");
            await release.Task;
            Expect(ledger.IsCurrent(combat, generation), false, "late outer continuation has no authority");
        }
        var suspended = SuspendAfterReservation();
        Expect(suspended.IsCompleted, false, "controlled suspension reached");
        Expect(ledger.TryReserve(combat, combat, outer, 4), false, "interleaved same enemy denied");
        Expect(ledger.TryReserve(combat, combat, inner, 4), true, "interleaved other enemy allowed");
        Expect(ledger.ObserveActionStart(combat, combat, inner, 4), true, "inner starts");
        Expect(ledger.EarlyConsumed(combat, combat, outer, 4), true, "inner did not refund outer");
        ledger.Reset(); ledger.EnsureCombat(combat);
        var fresh = ledger.Generation;
        Expect(ledger.TryReserve(combat, combat, outer, 4), true, "fresh combat incarnation can reserve");
        release.SetResult(); await suspended;
        Expect(ledger.IsCurrent(combat, fresh), true, "late continuation cannot invalidate fresh authority");
        Expect(ledger.TryReserve(combat, combat, outer, 4), false, "fresh reservation remains consumed");
        Expect(ledger.Consumed(combat, combat, inner, 4), false, "old inner fact not carried across reset");
    }

    private static int Main(string[] args)
    {
        if (args is ["--list"]) { foreach (var name in Cases.Keys) Console.WriteLine(name); return 0; }
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run))
        { Console.Error.WriteLine("Specify exactly one known opportunity sequence or --list"); return 2; }
        try
        {
            run();
            Console.WriteLine($"ENGAGE_SEQUENCE_PASS name={args[0]} assertions={assertions} native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
