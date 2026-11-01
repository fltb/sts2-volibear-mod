using System;
using System.Collections.Generic;

namespace Volibear.Core;

/// <summary>Actual death provenance survives removal of its Steam power.</summary>
public sealed class SteamEruptionDecision
{
    public object Combat { get; }
    public object Monster { get; }
    public object Source { get; }
    public long Generation { get; }
    public long Epoch { get; }
    public bool DeathConfirmed { get; private set; }
    public bool DomainSeen { get; private set; }
    public bool Cancelled { get; private set; }
    public bool TerminalRequested { get; private set; }
    public bool TerminalStarted { get; private set; }
    public bool TerminalKillCommitted { get; private set; }
    public bool TerminalAttemptRecorded { get; private set; }
    public int TerminalAttemptCount { get; private set; }
    public bool TerminalDeathConfirmed { get; private set; }
    public bool Retired { get; private set; }
    public bool CanApplyBenefit => DeathConfirmed && !Cancelled && !TerminalStarted && !Retired;
    private readonly Dictionary<object, SteamWriteReceipt> _writes = new(ReferenceEqualityComparer.Instance);
    public IReadOnlyCollection<SteamWriteReceipt> Writes => _writes.Values;

    public SteamEruptionDecision(object combat, object monster, object source, long generation, long epoch)
    {
        Combat = combat ?? throw new ArgumentNullException(nameof(combat));
        Monster = monster ?? throw new ArgumentNullException(nameof(monster));
        Source = source ?? throw new ArgumentNullException(nameof(source));
        if (generation <= 0) throw new ArgumentOutOfRangeException(nameof(generation));
        Generation = generation; Epoch = epoch;
    }
    public bool Matches(object combat, object monster, object source, long generation, long epoch) =>
        ReferenceEquals(Combat, combat) && ReferenceEquals(Monster, monster) && ReferenceEquals(Source, source) &&
        Generation == generation && Epoch == epoch;
    public void ObserveDomain(bool active)
    {
        if (active && !Retired) DomainSeen = true;
        if (DeathConfirmed && DomainSeen) { Cancelled = true; TerminalRequested = true; }
    }
    public void ConfirmDeath(bool prevented)
    {
        if (prevented) return;
        DeathConfirmed = true;
        ObserveDomain(false);
    }
    public decimal GatePositiveDamage(decimal proposed, bool sourceMatched, bool harmsOpposingSide) =>
        sourceMatched && harmsOpposingSide && proposed > 0 && !CanApplyBenefit ? 0 : proposed;

    /// <summary>Observes a completed native write, even if its synchronous event opened Domain.
    /// Never rejects, refunds, or rewrites already committed HP/block because cancellation happened later.</summary>
    public void RecordNativeWrite(object writeIdentity, string part, object receiver, decimal before, decimal after)
    {
        if (!_writes.TryAdd(writeIdentity, new SteamWriteReceipt(part, receiver, before, after)))
            throw new InvalidOperationException("Duplicate native write receipt identity.");
    }
    public void RequestNaturalTerminal() { if (DeathConfirmed) TerminalRequested = true; }
    public bool TryBeginTerminal(bool ownAncestor, bool firstDeathRunning, bool moveOrDamageRunning, bool originalExplodeTail)
    {
        if (!TerminalRequested || TerminalStarted || Retired || ownAncestor || firstDeathRunning ||
            (moveOrDamageRunning && !originalExplodeTail)) return false;
        TerminalStarted = true;
        return true;
    }
    public void RecordTerminalKill(bool wasAliveBefore, bool isDeadAfter)
    {
        if (!TerminalStarted || !wasAliveBefore || TerminalAttemptRecorded)
            throw new InvalidOperationException("Not one genuine positive-HP terminal attempt.");
        TerminalAttemptRecorded = true; TerminalAttemptCount++;
        TerminalKillCommitted = isDeadAfter; // Preserve an independent native ShouldDie veto; never force/retry.
    }
    public void ObserveExternalTerminalDeath()
    {
        if (!DeathConfirmed || Retired) throw new InvalidOperationException("No live Steam death episode to consume.");
        TerminalRequested = true;
        TerminalStarted = true; TerminalDeathConfirmed = true;
    }
    /// <summary>Only a completed real native move may release a vetoed, uncancelled attempt.
    /// This never retries a cancelled cleanup and never releases a genuinely consumed death.</summary>
    public bool FinishNativeMoveAfterVeto(bool ownerAlive, bool scopesClosed)
    {
        if (!ownerAlive || !scopesClosed || !TerminalStarted || !TerminalAttemptRecorded || TerminalKillCommitted ||
            TerminalDeathConfirmed || Cancelled || Retired) return false;
        TerminalRequested = false; TerminalStarted = false; TerminalAttemptRecorded = false;
        return true;
    }
    public void MarkRetired(bool stillAttached)
    {
        if (stillAttached) throw new InvalidOperationException("Cannot claim retirement while still attached.");
        Retired = true;
    }
}

public sealed record SteamWriteReceipt(string Part, object Receiver, decimal Before, decimal After)
{
    public decimal Delta => After - Before;
}
