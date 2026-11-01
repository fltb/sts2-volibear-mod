using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models.Monsters;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    // Observation only. Never attaches Steam provenance to the damage frame, changes
    // its amount/result, or manufactures a death. Covers native post-HP awaits before Kill.
    private sealed record HpObservation(Creature Owner, OwnerDeathLease Lease, long ConfirmedBefore);
    private static void ObserveLethalWrite(Creature owner, bool lethal)
    {
        if (!lethal || ActiveFrame is not { Closed: false } frame || frame.Flow is not (Flow.Damage or Flow.SetHp or Flow.SetMaxHp) ||
            owner.Monster is not WaterfallGiant monster || LatestFor(monster) is not { } episode ||
            !IsCurrent(episode) || episode.Decision.Retired || !episode.Decision.DeathConfirmed || !HasProtectedCommit(episode) ||
            !ReferenceEquals(owner, episode.Owner) || !ReferenceEquals(owner.CombatState, episode.Combat)) return;
        if (frame.Epoch != episode.Decision.Epoch)
            throw new InvalidOperationException("Stale HP command cannot acquire a new epoch owner lease.");
        if (frame.HpObservations.Any(item => ReferenceEquals(item.Owner, owner))) return;
        var lease = frame.OwnerRegistry.GetValue(owner, _ => new OwnerDeathLease());
        lease.HpCommandsActive++;
        frame.HpObservations.Add(new(owner, lease, lease.LastConfirmed));
    }
    private static bool LethalSetHp(Creature owner, decimal amount) => owner.IsAlive && Math.Min(amount, owner.MaxHp) < 1m;
    private static void ObserveSetHp(Creature owner, decimal amount)
    {
        ObserveLethalWrite(owner, LethalSetHp(owner, amount));
        owner.SetCurrentHpInternal(amount); // Exact original argument and actual native write.
    }
    private static void ObserveSetMaxHp(Creature owner, decimal amount)
    {
        // SetMaxHpInternal synchronously raises MaxHpChanged and clamps current HP,
        // whose change event can reenter Domain before SetMaxHp reaches its native Kill.
        ObserveLethalWrite(owner, owner.IsAlive && amount < 1m);
        owner.SetMaxHpInternal(amount);
    }
    private static IEnumerable<CodeInstruction> SetMaxHpMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod) =>
        Scope(Replace(input, AccessTools.Method(typeof(Creature), nameof(Creature.SetMaxHpInternal)), nameof(ObserveSetMaxHp)), generator, __originalMethod, Flow.SetMaxHp);
    private static IEnumerable<CodeInstruction> SetHpMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod) =>
        Scope(Replace(input, AccessTools.Method(typeof(Creature), nameof(Creature.SetCurrentHpInternal)), nameof(ObserveSetHp)), generator, __originalMethod, Flow.SetHp);
}
