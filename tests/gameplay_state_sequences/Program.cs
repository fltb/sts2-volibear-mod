using Volibear.Core;

// These are sequences over the actual production kernels compiled by this project.
// They do not execute payment, damage, UI, native scheduling or a duplicate battle model.
var checks = 0;
var cases = new Dictionary<string, Action>(StringComparer.Ordinal)
{
    ["card-domain-replay-close"] = CardDomainReplayClose,
    ["domain-two-clocks"] = DomainTwoClocks,
    ["lightning-pending-epoch-close"] = LightningPendingEpochClose,
    ["beast-native-cost-lifetime"] = BeastNativeCostLifetime,
    ["steam-death-evidence"] = SteamDeathEvidence,
    ["steam-commit-and-identity"] = SteamCommitAndIdentity,
    ["steam-terminal-guards"] = SteamTerminalGuards,
    ["steam-veto-and-retirement"] = SteamVetoAndRetirement,
};
if (args.Length == 1 && args[0] == "--list")
{
    foreach (var name in cases.Keys) Console.WriteLine(name);
    return;
}
if (args.Length > 1 || (args.Length == 1 && !cases.ContainsKey(args[0])))
    throw new ArgumentException("Exactly one known state sequence, --list, or no arguments required.");
foreach (var name in args.Length == 0 ? cases.Keys.ToArray() : args)
{
    checks = 0;
    cases[name]();
    Console.WriteLine($"STATE_SEQUENCE_PASS name={name} assertions={checks} native-gameplay=NOT_RUN");
}
void Check(bool condition, string message)
{
    checks++;
    if (!condition) throw new InvalidOperationException(message);
}
void Reject<T>(Action action, string message) where T : Exception
{
    var rejected = false;
    try { action(); } catch (T) { rejected = true; }
    Check(rejected, message);
}
SteamEruptionDecision Episode() => new(new object(), new object(), new object(), 1, 1);

void CardDomainReplayClose()
{
    var counter = new LightningCounter();
    var play = new CardResolutionPlayGate();
    Check(counter.Read(1, 1) == 0, "Initial batch count.");
    Check(!play.TryAttach(false) && !play.Attached, "First series without Domain must not reserve.");
    Check(play.TryAttach(true), "Later series of this play may attach after Domain opens.");
    var first = counter.Begin(1, 1);
    Check(!play.TryAttach(true), "Reentry while first batch pending cannot attach again.");
    Check(counter.Read(1, 1) == 0, "Pending batch is not committed.");
    Check(counter.Complete(first, out var count) && count == 1, "First completion commits one batch.");
    Check(!play.TryAttach(true), "Replay after completion still shares the reservation.");
    counter.Abort(first);
    Check(counter.Read(1, 1) == 1, "Finally Abort cannot roll back completed count.");
    Check(!counter.Complete(first, out count) && count == 1, "Repeated completion cannot replay response credit.");
    play.Close();
    Check(play.Closed && !play.TryAttach(true), "Closed play cannot revive.");
    var second = new CardResolutionPlayGate();
    Check(second.TryAttach(true), "A new actual play owns a new reservation.");
    var pending = counter.Begin(1, 1);
    second.Close();
    // Gate close and combat-counter close are separate production responsibilities.
    counter.Close();
    Check(!counter.Complete(pending, out _) && counter.Read(1, 1) == 0, "Combat close invalidates pending batch.");
    Check(!second.TryAttach(true), "Late response cannot reopen closed second play.");
    var nextCombat = new LightningCounter();
    var fresh = nextCombat.Begin(1, 1);
    Check(nextCombat.Complete(fresh, out count) && count == 1, "A different combat's own counter is independent.");
}

void DomainTwoClocks()
{
    var clock = new CardResolutionDrawClock(4);
    var duration = CardResolutionDuration.Extend(0, 1);
    duration = CardResolutionDuration.Extend(duration, 2);
    var lightning = new LightningCounter();
    var batch = lightning.Begin(4, 7);
    Check(lightning.Complete(batch, out var count) && count == 1, "Batch committed in current player turn.");
    Check(duration == 3, "Finite extension is additive and does not replace clock.");
    for (var turn = 8; turn <= 10; turn++)
    {
        Check(lightning.Read(4, turn) == 0, "Extra player turn resets lightning count.");
        Check(!clock.TryConsumeNormalDraw(4), "Same-round extra turn must not consume Domain duration.");
        Check(duration == 3, "Unconsumed duration stays unchanged.");
    }
    Check(clock.TryConsumeNormalDraw(5), "Next normal round consumes once after its full draw boundary.");
    duration--;
    Check(duration == 2 && !clock.TryConsumeNormalDraw(5), "Duplicate normal boundary cannot consume again.");
    Check(!clock.TryConsumeNormalDraw(3), "Stale draw notification cannot rewind clock.");
    duration = CardResolutionDuration.Permanent;
    Check(CardResolutionDuration.Extend(duration, 2) == duration, "Finite extension cannot downgrade permanent.");
    Check(clock.TryConsumeNormalDraw(6), "Clock advancing and permanent non-decrement are distinct responsibilities.");
    Check(CardResolutionDuration.Extend(duration, 1) == CardResolutionDuration.Permanent,
        "Extension after a later clock tick preserves permanent; native decrement adapter NOT_RUN.");
    Reject<ArgumentOutOfRangeException>(() => CardResolutionDuration.Extend(CardResolutionDuration.Permanent - 2, 2), "Finite arithmetic cannot create permanent sentinel.");
}

void LightningPendingEpochClose()
{
    var counter = new LightningCounter();
    var outer = counter.Begin(1, 1);
    var inner = counter.Begin(1, 1);
    var late = counter.Begin(1, 1);
    counter.Abort(inner);
    Check(!counter.Complete(inner, out var count) && count == 0, "Abort only consumes its own pending ticket.");
    Check(counter.Complete(outer, out count) && count == 1, "Outer survives inner abort.");
    var another = counter.Begin(1, 1);
    Check(counter.Read(1, 2) == 0, "Changing player turn resets count and pending set.");
    Check(!counter.Complete(late, out _) && !counter.Complete(another, out _), "All previous-turn pending tickets are stale.");
    // Returning to equal numeric round/turn must not restore an old generation.
    Check(counter.Read(1, 1) == 0, "Numeric epoch ABA starts another generation.");
    Check(!counter.Complete(late, out _) && !counter.Complete(outer, out _), "Old pending and completed tickets cannot revive after ABA.");
    var fresh = counter.Begin(1, 1);
    counter.Abort(inner);
    Check(counter.Complete(fresh, out count) && count == 1, "Old Abort cannot cancel a new generation's ticket.");
    var unfinished = counter.Begin(1, 1);
    counter.Close(); counter.Close();
    Check(counter.IsClosed && counter.Read(1, 1) == 0, "Repeated Close remains terminal.");
    Check(!counter.Complete(unfinished, out _), "Closing invalidates unfinished work.");
    Reject<InvalidOperationException>(() => counter.Begin(2, 2), "No Begin after combat close.");
}

void BeastNativeCostLifetime()
{
    var modifiers = new[] { new NativeModifier(-1, false, false, false), new NativeModifier(1, false, true, false) };
    var transfer = BeastCostTransfer.Rebase(3, modifiers, ApplyNative, m => m.Turn, m => m.Play);
    Check(transfer.Combat == -1 && transfer.ThisTurn == 1 && transfer.UntilPlayed == 0 && transfer.ThisTurnOrPlayed == 0,
        "A temporary surcharge may mask a combat discount without widening its lifetime.");
    Check(1 + transfer.Combat + transfer.ThisTurn == 1, "No inherited surcharge or discount while masking modifier survives.");
    Check(1 + transfer.Combat == 0, "Native turn cleanup exposes the inherited combat discount.");
    Check(3 + transfer.Combat == 2, "Later native base changes retain the discount rather than a permanent cap.");
    var absolute = new[] { new NativeModifier(2, true, true, true) };
    transfer = BeastCostTransfer.Rebase(3, absolute, ApplyNative, m => m.Turn, m => m.Play);
    Check(transfer.ThisTurnOrPlayed == -1 && transfer.Combat == 0 && transfer.ThisTurn == 0 && transfer.UntilPlayed == 0,
        "Absolute material Set(2) becomes the native -1 difference with either cleanup boundary.");
    transfer = BeastCostTransfer.Rebase(3, Array.Empty<NativeModifier>(), ApplyNative, m => m.Turn, m => m.Play);
    Check(transfer == default, "Already expired modifiers grant no new discount.");
}
int ApplyNative(NativeModifier modifier, int value) => modifier.Absolute ? modifier.Amount : value + modifier.Amount;

void SteamDeathEvidence()
{
    foreach (var domainFirst in new[] { false, true })
    {
        var episode = Episode();
        episode.ObserveDomain(domainFirst);
        Check(!episode.DeathConfirmed && !episode.Cancelled && !episode.TerminalRequested, "Domain observation alone is not death confirmation.");
        Check(episode.GatePositiveDamage(7, true, true) == 0, "Unconfirmed episode cannot grant its protected benefit.");
        episode.ConfirmDeath(prevented: true);
        Check(!episode.DeathConfirmed && !episode.Cancelled, "A veto does not enter the protected death episode.");
        episode.ConfirmDeath(prevented: false);
        Check(episode.DeathConfirmed && episode.Cancelled == domainFirst, "Actual confirmation resolves previously observed Domain.");
        Check(episode.CanApplyBenefit == !domainFirst, "Benefit requires confirmed, uncancelled death.");
        Check(episode.GatePositiveDamage(7, true, true) == (domainFirst ? 0 : 7),
            "Confirmed native benefit remains allowed without Domain; do not permanently suppress matched damage.");
        episode.ObserveDomain(true); episode.ObserveDomain(false);
        Check(episode.Cancelled && episode.TerminalRequested && !episode.CanApplyBenefit, "Cancellation stays consumed after Domain exits.");
        foreach (var value in new decimal[] { -2, 0, 7 })
        {
            Check(episode.GatePositiveDamage(value, true, true) == (value > 0 ? 0 : value), "Only positive matched opposing contribution suppressed.");
            Check(episode.GatePositiveDamage(value, false, true) == value, "Foreign contribution unchanged.");
            Check(episode.GatePositiveDamage(value, true, false) == value, "Different-side contribution unchanged.");
        }
    }
}

void SteamCommitAndIdentity()
{
    var combat = new Key("combat"); var monster = new Key("monster"); var power = new Key("power");
    var episode = new SteamEruptionDecision(combat, monster, power, 2, 3);
    Check(episode.Matches(combat, monster, power, 2, 3), "Exact episode identities match.");
    Check(!episode.Matches(new Key("combat"), monster, power, 2, 3), "Value-equal combat cannot borrow episode.");
    Check(!episode.Matches(combat, new Key("monster"), power, 2, 3), "Value-equal monster cannot borrow episode.");
    Check(!episode.Matches(combat, monster, new Key("power"), 2, 3), "Value-equal source cannot borrow episode.");
    Check(!episode.Matches(combat, monster, power, 3, 3) && !episode.Matches(combat, monster, power, 2, 4), "Generation/epoch isolate continuation.");
    episode.ConfirmDeath(false);
    var firstWrite = new Key("write");
    episode.RecordNativeWrite(firstWrite, "max-hp", monster, 100, 999999999);
    episode.ObserveDomain(true);
    // The synchronous native write has already committed, even when its event opened Domain.
    episode.RecordNativeWrite(new Key("write"), "current-hp", monster, 0, 999999999);
    Check(episode.Cancelled && episode.Writes.Count == 2, "Later cancellation does not discard committed writes.");
    Check(episode.Writes.Any(w => w.Part == "max-hp" && w.Before == 100 && w.After == 999999999), "Original committed values retained.");
    Check(episode.Writes.All(w => ReferenceEquals(w.Receiver, monster)), "Committed receiver identity retained.");
    Reject<InvalidOperationException>(() => episode.RecordNativeWrite(firstWrite, "max-hp", monster, 100, 999999999), "Same actual write cannot be credited twice.");
    Check(episode.Writes.Count == 2, "Duplicate rejection cannot corrupt prior receipts.");
}

void SteamTerminalGuards()
{
    foreach (var ancestor in new[] { false, true })
    foreach (var firstDeath in new[] { false, true })
    foreach (var inflight in new[] { false, true })
    foreach (var originalTail in new[] { false, true })
    {
        var episode = Episode();
        Check(!episode.TryBeginTerminal(false, false, false, false), "No terminal without confirmed/requested episode.");
        episode.ConfirmDeath(false); episode.RequestNaturalTerminal();
        var allowed = !ancestor && !firstDeath && (!inflight || originalTail);
        Check(episode.TryBeginTerminal(ancestor, firstDeath, inflight, originalTail) == allowed, "Terminal guards must respect ancestor and active scopes.");
        Check(episode.TerminalStarted == allowed, "Rejected admission must not mutate started flag.");
        if (!allowed) Check(episode.TryBeginTerminal(false, false, false, false), "After guards clear, still-pending request can begin once.");
        Check(!episode.TryBeginTerminal(false, false, false, true), "Started terminal cannot reenter even at original tail.");
        Reject<InvalidOperationException>(() => episode.RecordTerminalKill(false, true), "A corpse is not a positive-HP kill attempt.");
        episode.RecordTerminalKill(true, true);
        Check(episode.TerminalAttemptCount == 1 && episode.TerminalKillCommitted, "One actual terminal attempt recorded.");
        Reject<InvalidOperationException>(() => episode.RecordTerminalKill(true, true), "Duplicate terminal kill record rejected.");
    }
}

void SteamVetoAndRetirement()
{
    foreach (var cancelled in new[] { false, true })
    foreach (var alive in new[] { false, true })
    foreach (var closed in new[] { false, true })
    {
        var episode = Episode(); episode.ConfirmDeath(false);
        episode.ObserveDomain(cancelled); episode.RequestNaturalTerminal();
        Check(episode.TryBeginTerminal(false, false, false, false), "Settled terminal starts.");
        episode.RecordTerminalKill(true, false);
        Check(!episode.TerminalKillCommitted && episode.TerminalAttemptCount == 1, "Native veto is retained, not converted into death.");
        var released = !cancelled && alive && closed;
        Check(episode.FinishNativeMoveAfterVeto(alive, closed) == released, "Only uncancelled completed native move may release vetoed attempt.");
        if (released)
        {
            Check(!episode.TerminalRequested && !episode.TerminalStarted, "Release does not instantly retry.");
            episode.RequestNaturalTerminal();
            Check(episode.TryBeginTerminal(false, false, false, false), "A later genuine native move may request terminal again.");
            episode.RecordTerminalKill(true, true);
            Check(episode.TerminalAttemptCount == 2 && episode.TerminalKillCommitted, "Later attempt count retained, not retroactive retry of first.");
            Check(!episode.FinishNativeMoveAfterVeto(true, true), "Real committed death cannot reopen.");
        }
        else Check(episode.TerminalStarted, "Blocked release keeps consumed attempt.");
    }
    var external = Episode();
    Reject<InvalidOperationException>(() => external.ObserveExternalTerminalDeath(), "No external terminal consumption before actual death episode.");
    external.ConfirmDeath(false); external.ObserveExternalTerminalDeath();
    Check(external.TerminalDeathConfirmed && external.TerminalAttemptCount == 0, "External terminal is not a fabricated cleanup kill.");
    Check(!external.FinishNativeMoveAfterVeto(true, true), "External confirmed death cannot reopen.");
    Reject<InvalidOperationException>(() => external.MarkRetired(true), "Still-attached entity cannot claim retirement.");
    Check(!external.Retired, "Failed retirement leaves state intact.");
    external.MarkRetired(false);
    Check(external.Retired && !external.CanApplyBenefit, "Detached retirement is terminal for benefits.");
    Check(!external.TryBeginTerminal(false, false, false, true), "Retired episode cannot restart terminal.");
    Reject<InvalidOperationException>(() => external.ObserveExternalTerminalDeath(), "Retired episode cannot accept fresh terminal evidence.");
}

sealed record Modifier(int Amount, bool Absolute);
sealed record Key(string Value);

sealed record NativeModifier(int Amount, bool Absolute, bool Turn, bool Play);
