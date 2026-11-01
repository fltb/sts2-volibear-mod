using Volibear.Core;
using Decision = Volibear.Core.DomainSummonEffects.DeathDecision;
using Ownership = Volibear.Core.DomainSummonEffects.GateOwnership;

// SUMMON-01/02/03, DEATH-01/03, EFFECT-02; D10/D12/D14/D15/D17.
// Literal expected decisions from the rules, not a second implementation. No Add or HP simulation.
internal static class Program
{
    private static int count;
    private static readonly Dictionary<string, Action> Cases = new()
    {
        ["summon-partial-boundary-close"] = SummonPartial,
        ["summon-prevented-close-independent"] = SummonPrevented,
        ["summon-known-stale-versus-unknown"] = SummonOwnership,
        ["revival-pending-confirmed-cancelled"] = RevivalPending,
        ["revival-commit-versus-domain"] = RevivalCommit,
        ["revival-reference-authority"] = RevivalIdentity,
        ["revival-unstarted-callback"] = RevivalCallback,
    };
    private static void Check(bool actual, bool expected, string rule)
    {
        count++;
        if (actual != expected) throw new Exception($"{rule}: expected {expected}, got {actual}");
    }
    private static void RejectCommit(RevivalDecision decision, string rule)
    {
        bool rejected = false;
        try { decision.Commit(); } catch (InvalidOperationException) { rejected = true; }
        Check(rejected, true, rule);
        Check(decision.Committed, false, rule + " leaves uncommitted");
    }
    private static void SummonPartial()
    {
        var batch = new Decision(false);
        Check(batch.Cancelled, false, "new batch not consumed");
        Check(batch.AtBoundary(false, false), false, "first child boundary allowed without domain");
        Check(batch.Cancelled, false, "allow does not consume cancellation");
        Check(batch.AtBoundary(false, true), true, "domain enters before later child boundary");
        Check(batch.Cancelled, true, "later cancellation committed");
        Check(batch.AtBoundary(false, false), true, "domain exit cannot restore consumed benefit");
        batch.Close();
        Check(batch.AtBoundary(false, false), true, "Close does not refund consumed cancellation");
        Check(batch.TryCancel(false), true, "entry-only path retains consumed cancellation");
        // No child exists in this fixture: allowing the first boundary is not proof of native Add.
    }
    private static void SummonPrevented()
    {
        var closed = new Decision(true);
        Check(closed.Cancelled, false, "domain seen at entry not itself consumption");
        closed.Close();
        Check(closed.AtBoundary(false, true), false, "closed before first eligible boundary cannot consume");
        Check(closed.Cancelled, false, "Close is not cancellation or fullCombatReset");
        var prevented = new Decision(true);
        Check(prevented.TryCancel(true), false, "prevented removal not eligible");
        Check(prevented.Cancelled, false, "prevented removal does not consume");
        Check(prevented.TryCancel(false), true, "later actual eligible death uses entry domain");
        Check(prevented.AtBoundary(true, false), false, "prevented callback remains allowed even after cancellation");
        Check(prevented.Cancelled, true, "prevented callback cannot undo cancellation fact");
        Check(prevented.AtBoundary(false, false), true, "eligible callback still cancelled");
        var independent = new Decision(false);
        Check(independent.AtBoundary(false, false), false, "different batch not consumed by previous batch");
        Check(independent.Cancelled, false, "independent batch starts available");
        Check(independent.AtBoundary(false, true), true, "independent batch can consume own cancellation");
        Check(closed.Cancelled, false, "other batch consumption cannot reopen closed batch");
        Check(DomainSummonEffects.CanAttachDeathBirth(true, closed.Cancelled), false, "new callback cannot acquire closed unconsumed ending-index authority");
        prevented.Close();
        Check(DomainSummonEffects.CanAttachDeathBirth(true, prevented.Cancelled), true, "new callback retains legacy consumed cancellation without refund");
        Check(DomainSummonEffects.CanAttachDeathBirth(false, false), true, "live native death capture remains eligible");
    }
    private static void SummonOwnership()
    {
        // Desired pre-create classification: unknown must not fabricate ownership;
        // known expired authority must not permit a new creation. Independent current batch stays current.
        (bool binding, long frame, long batch, Ownership expected)[] rows =
        [
            (false, 8, 8, Ownership.Unknown), (false, 7, 8, Ownership.Unknown),
            (false, 8, 7, Ownership.Unknown), (false, 7, 7, Ownership.Unknown),
            (true, 8, 8, Ownership.Current), (true, 7, 8, Ownership.StaleKnown),
            (true, 8, 7, Ownership.StaleKnown), (true, 7, 7, Ownership.StaleKnown),
        ];
        foreach (var row in rows)
            Check(DomainSummonEffects.ClassifyGate(row.binding, row.frame, row.batch, 8) == row.expected,
                true, $"binding={row.binding} frame={row.frame} batch={row.batch}: {row.expected}");
        Check(DomainSummonEffects.ClassifyGate(true, 8, 8, 8) == Ownership.Current, true,
            "classifying stale batch did not poison another current batch");
        Check(DomainSummonEffects.ClassifyGate(true, 8, 8, 9) == Ownership.StaleKnown, true,
            "next epoch retires previously current owned frame");
    }
    private static void RevivalPending()
    {
        var decision = new RevivalDecision();
        Check(decision.Confirmed, false, "pending death not confirmed");
        Check(decision.CancelIfRequired(false), false, "pending without domain allowed");
        decision.Confirm(true);
        Check(decision.Confirmed, false, "prevented removal does not confirm death");
        Check(decision.CancelIfRequired(true), false, "domain without confirmed death not cancelled");
        Check(decision.DomainSeen, true, "pending domain evidence remembered");
        Check(decision.Cancelled, false, "evidence is not confirmed cancellation");
        RejectCommit(decision, "pending cannot commit revival");
        decision.Confirm(false);
        Check(decision.Confirmed, true, "real death confirms");
        Check(decision.CancelIfRequired(false), true, "remembered domain cancels after confirmation even after exit");
        decision.Confirm(true);
        Check(decision.Confirmed, true, "later prevented notification does not erase confirmation");
        Check(decision.CancelIfRequired(false), true, "cancelled benefit stays consumed");
        RejectCommit(decision, "cancelled benefit cannot commit");
        var independent = new RevivalDecision(); independent.Confirm(false);
        Check(independent.CancelIfRequired(false), false, "independent death unaffected");
    }
    private static void RevivalCommit()
    {
        var pending = new RevivalDecision();
        RejectCommit(pending, "unconfirmed no-domain revival cannot commit");
        var allowed = new RevivalDecision(); allowed.Confirm(false);
        Check(allowed.CancelIfRequired(false), false, "confirmed without domain permitted");
        allowed.Commit();
        Check(allowed.Committed, true, "permitted benefit records commit");
        allowed.ObserveDomain(true);
        Check(allowed.DomainSeen, false, "postcommit domain cannot retroactively record pending evidence");
        Check(allowed.CancelIfRequired(true), false, "postcommit domain cannot cancel committed benefit");
        Check(allowed.Committed, true, "committed fact survives domain");
        var denied = new RevivalDecision(); denied.Confirm(false); denied.ObserveDomain(true);
        Check(denied.DomainSeen, true, "precommit domain remembered");
        RejectCommit(denied, "domain-seen benefit cannot commit even before cancellation query");
        Check(denied.CancelIfRequired(false), true, "precommit domain cancels on next decision");
        Check(allowed.Cancelled, false, "other death cancellation cannot rewrite committed instance");
    }
    private sealed class EqualObject
    {
        public override bool Equals(object? other) => other is EqualObject;
        public override int GetHashCode() => 3;
    }
    private static void RevivalIdentity()
    {
        var source = new EqualObject(); var owner = new EqualObject();
        var otherSource = new EqualObject(); var otherOwner = new EqualObject();
        Check(source.Equals(otherSource) && source.GetHashCode() == otherSource.GetHashCode(), true, "forced equality collision");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, owner, owner, true, true), true, "exact cancelled ownership");
        Check(RevivalDecision.OwnsCancelledPreservation(source, otherSource, owner, owner, owner, true, true), false, "equal source is not captured source");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, otherOwner, owner, true, true), false, "equal owner is not captured owner");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, owner, otherOwner, true, true), false, "equal target is not owner");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, owner, owner, false, true), false, "uncancelled preservation stays native");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, owner, owner, true, false), false, "stale epoch has no authority");
        Check(RevivalDecision.OwnsCancelledPreservation(source, null, owner, owner, owner, true, true), false, "missing captured source");
        Check(RevivalDecision.OwnsCancelledPreservation(source, source, owner, null, owner, true, true), false, "missing captured owner");
    }
    private static void RevivalCallback()
    {
        Check(RevivalDecision.SkipUnstartedCallback(-1, true, false), true, "owned unstarted denied benefit may skip");
        Check(RevivalDecision.SkipUnstartedCallback(-1, true, true), false, "allowed benefit must execute");
        Check(RevivalDecision.SkipUnstartedCallback(-1, false, false), false, "unowned callback must execute");
        Check(RevivalDecision.SkipUnstartedCallback(-1, false, true), false, "unowned allowed callback must execute");
        Check(RevivalDecision.SkipUnstartedCallback(0, true, false), false, "started callback cannot be skipped");
        Check(RevivalDecision.SkipUnstartedCallback(1, true, false), false, "later continuation cannot be skipped");
        Check(RevivalDecision.SkipUnstartedCallback(-2, true, false), false, "completed callback is not unstarted");
    }
    private static int Main(string[] args)
    {
        if (args is ["--list"]) { foreach (var name in Cases.Keys) Console.WriteLine(name); return 0; }
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run)) return 2;
        try { run(); Console.WriteLine($"DOMAIN_LIFECYCLE_PASS name={args[0]} assertions={count} native-gameplay=NOT_RUN"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
