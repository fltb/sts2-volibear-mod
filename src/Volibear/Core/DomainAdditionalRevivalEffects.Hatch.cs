using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;

namespace Volibear.Core;

public static partial class DomainAdditionalRevivalEffects
{
    private sealed class HatchTicket(ToughEgg egg, ICombatState combat, long generation)
    {
        internal readonly ToughEgg Egg = egg;
        internal readonly Creature Owner = egg.Creature;
        internal readonly ICombatState Combat = combat;
        internal readonly long Epoch = generation;
        internal bool Cancelled;
    }
    private sealed class HatchRequest(HatchTicket ticket)
    {
        internal readonly HatchTicket Ticket = ticket;
        internal bool Consumed;
    }
    private static readonly SummonLifetime<HatchTicket> HatchLifetimes = new();
    private static readonly List<HatchTicket> Hatching = [];
    private static readonly AsyncLocal<HatchRequest?> RequestedHatch = new();
    private static readonly Func<ToughEgg, Task> NativeHatch = AccessTools.MethodDelegate<Func<ToughEgg, Task>>(AccessTools.Method(typeof(ToughEgg), "Hatch"));
    private static Frame EnterHatch(Task task, int state, ToughEgg egg, BodyKind kind)
    {
        if (state != -1) return new(null, HatchLifetimes.Find(task, egg, (int)kind));
        HatchTicket? ticket = null;
        bool owns = kind == BodyKind.HatchMove;
        if (owns && egg.Creature.IsEnemy && !egg.Creature.IsPlayer && egg.Creature.CombatState is { } combat)
        {
            ticket = new(egg, combat, epoch); ticket.Cancelled = Domain(combat); Hatching.Add(ticket);
        }
        else if (!owns && RequestedHatch.Value is { Consumed: false } request && ReferenceEquals(request.Ticket.Egg, egg))
        { request.Consumed = true; ticket = request.Ticket; }
        // AfterAddedToRoom -> Hatch is initial population, deliberately untagged.
        return new(null, ticket is null ? null : HatchLifetimes.Begin(ticket, ticket.Epoch, owns, egg, (int)kind));
    }
    private static bool HatchBlocked(Frame frame)
    {
        if (frame.Hatch is { Closed: true }) return true;
        if (frame.Hatch?.Payload is not { } t) return false;
        if (t.Epoch != epoch || !ReferenceEquals(t.Combat, CombatManager.Instance.DebugOnlyGetState())) return true;
        if (Domain(t.Combat)) t.Cancelled = true;
        return t.Cancelled;
    }
    private static Task HatchCleanse(PowerModel? power, Frame frame)
    {
        // Removal of buffs remains an enemy cost. Negative Strength etc use the
        // native amount-sensitive classification, not only PowerModel.Type.
        if (power is not null && HatchBlocked(frame) && power.TypeForCurrentAmount == PowerType.Debuff)
        {
            PublishHatchCancellation(frame);
            return Task.CompletedTask;
        }
        return PowerCmd.Remove(power);
    }
    private static Task HatchFromMove(ToughEgg egg, Frame frame)
    {
        var previous = RequestedHatch.Value;
        RequestedHatch.Value = frame.Hatch?.Payload is { } t ? new(t) : null;
        try { return NativeHatch(egg); }
        finally { RequestedHatch.Value = previous; }
    }
    private static async Task HatchHp(Creature owner, decimal amount, Frame frame)
    {
        if (frame.Hatch is null) { await CreatureCmd.SetMaxAndCurrentHp(owner, amount); return; }
        // Same two native commands and order as SetMaxAndCurrentHp, with a fresh
        // gate between them. Preserve decreases; never manufacture a new HP value.
        if (!HatchBlocked(frame) || amount <= owner.MaxHp) await CreatureCmd.SetMaxHp(owner, amount);
        else PublishHatchCancellation(frame);
        if (!HatchBlocked(frame) || amount <= owner.CurrentHp) await CreatureCmd.SetCurrentHp(owner, amount);
        else PublishHatchCancellation(frame);
    }
    private static void PublishHatchCancellation(Frame frame)
    {
        try
        {
            if (frame.Hatch?.Payload is { Cancelled: true } t && t.Epoch == epoch)
                Volibear.Presentation.PowerPresentationDomain.Once(t, t.Owner, t.Egg, sourceCombat: t.Combat);
        }
        catch { }
    }
    private static void CancelOpenHatches(ICombatState combat)
    {
        foreach (var t in Hatching)
            if (t.Epoch == epoch && ReferenceEquals(t.Combat, combat)) t.Cancelled = true;
    }
}
