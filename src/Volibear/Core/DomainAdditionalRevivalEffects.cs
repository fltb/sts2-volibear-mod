using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Volibear.Core;

/// <summary>Stock newborns and TestSubject's Adaptable phase only. Native death facts,
/// committed entities/HP and original cleanup remain native; never decides victory.</summary>
public static partial class DomainAdditionalRevivalEffects
{
    private sealed class Ticket(PowerModel source, ICombatState combat, long epoch)
    {
        internal readonly PowerModel Source = source;
        internal readonly Creature Owner = source.Owner;
        internal readonly ICombatState Combat = combat;
        internal readonly long Epoch = epoch;
        internal bool Confirmed, Cancelled, Committed, Finished, ManagerRemoved, PresentationFinished;
        internal int DeathDepth, CallbackDepth;
        internal Task? Cleanup;
        internal bool CleanupStarted;
        internal MonsterModel? Creating;
    }
    private sealed class DeathCall(Ticket ticket)
    {
        internal readonly Ticket Ticket = ticket;
        internal readonly Action<Creature> Died = owner =>
        {
            if (!ReferenceEquals(owner, ticket.Owner)) return;
            ticket.Confirmed = true;
            Observe(ticket);
        };
        internal bool Closed;
    }
    private sealed class MoveDepth { internal int Count; }
    private sealed class MoveCall(Creature owner, MoveDepth depth)
    {
        internal readonly Creature Owner = owner;
        internal readonly MoveDepth Depth = depth;
        internal bool Closed;
    }
    private static readonly ConditionalWeakTable<Creature, MoveDepth> Moves = new();
    private static readonly ConditionalWeakTable<PowerModel, Ticket> Sources = new();
    private static readonly ConditionalWeakTable<Creature, Ticket> Owners = new();
    private static readonly List<Ticket> Pending = [];
    private static long epoch;
    private static bool installed;
    private static readonly Func<AdaptablePower, bool> IsReviving = AccessTools.MethodDelegate<Func<AdaptablePower, bool>>(
        AccessTools.PropertyGetter(typeof(AdaptablePower), "IsReviving"));
    private static readonly Action<TestSubject, Color> SetColor = AccessTools.MethodDelegate<Action<TestSubject, Color>>(
        AccessTools.Method(typeof(TestSubject), "SetColor"));

    public static void Install()
    {
        if (installed) return;
        var harmony = new Harmony("Volibear.DomainAdditionalRevivalEffects");
        try
        {
            InstallPatches(harmony);
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            installed = true;
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }
    public static void Reset() { epoch++; Pending.Clear(); Hatching.Clear(); }
    private static Ticket? Find(PowerModel power) => Sources.TryGetValue(power, out var t) ? t : null;
    private static Ticket? Find(Creature owner) => Owners.TryGetValue(owner, out var t) ? t : null;
    private static bool Current(Ticket t) => t.Epoch == epoch && ReferenceEquals(t.Combat, CombatManager.Instance.DebugOnlyGetState());
    // Do not query IsEnding here: the powers themselves contribute to its veto.
    private static bool Domain(ICombatState combat) => CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsAboutToLose &&
        ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) && combat.Players.Any(p =>
            p.Creature.IsAlive && ReferenceEquals(p.Creature.CombatState, combat) && combat.ContainsCreature(p.Creature) && p.Creature.GetPowerAmount<DomainPower>() > 0);
    private static Ticket Create(PowerModel source, ICombatState combat)
    {
        var t = new Ticket(source, combat, epoch);
        if (Find(t.Owner) is { } prior) Pending.Remove(prior);
        Sources.Remove(source); Sources.Add(source, t);
        Owners.Remove(t.Owner); Owners.Add(t.Owner, t);
        Pending.Add(t); return t;
    }
    private static void StockCommit(Ticket t)
    {
        if (t.Creating is not { } creating) return;
        // CreateCreature sets the actual creature before AddCreature raises listeners.
        // Observe physical membership, not a returned/provisional async Task.
        if (AccessTools.Field(typeof(MonsterModel), "_creature").GetValue(creating) is Creature child && t.Combat.ContainsCreature(child))
        { t.Committed = true; Pending.Remove(t); }
    }
    private static bool Observe(Ticket t)
    {
        StockCommit(t);
        if (t.Committed) return false;
        if (!Current(t)) return true;
        if (t.Confirmed && Domain(t.Combat)) t.Cancelled = true;
        return t.Cancelled;
    }
    private static void DeathPrefix(Creature creature, out DeathCall? __state)
    {
        __state = null;
        if (!creature.IsEnemy || creature.IsPlayer || creature.CombatState is not { } combat) return;
        PowerModel? source = creature.Monster switch
        {
            Axebot => creature.GetPower<StockPower>(),
            TestSubject => creature.GetPower<AdaptablePower>(),
            _ => null,
        };
        if (source is null) return;
        var old = Find(source);
        // Recursive prevention retries share their still-open native death; a
        // later actual death gets a fresh phase, never revives a cancelled ticket.
        var t = old is { Finished: false, Committed: false, DeathDepth: > 0 } && Current(old) ? old : Create(source, combat);
        t.DeathDepth++;
        __state = new DeathCall(t); creature.Died += __state.Died;
    }
    private static void CloseDeath(DeathCall call)
    {
        if (call.Closed) return;
        call.Closed = true; call.Ticket.Owner.Died -= call.Died; call.Ticket.DeathDepth--;
    }
    private static void DeathPostfix(DeathCall? __state, ref Task __result)
    { if (__state is not null) __result = FinishDeath(__result, __state); }
    private static Exception? DeathFinalizer(Exception? __exception, DeathCall? __state)
    { if (__exception is not null && __state is not null) CloseDeath(__state); return __exception; }
    private static async Task FinishDeath(Task original, DeathCall call)
    {
        try { await original; }
        finally { CloseDeath(call); }
        var t = call.Ticket;
        if (!Current(t) || t.DeathDepth != 0) return;
        if (!t.Confirmed) { Pending.Remove(t); t.Finished = true; return; }
        if (t.Source is StockPower || t.Committed) { Pending.Remove(t); t.Finished = true; return; }
        if (t.ManagerRemoved)
        {
            if (t.Cancelled) TerminalPresentation(t);
            Pending.Remove(t); t.Finished = true;
        }
        else await FinalizeWhenSafe(t);
    }
    private static void ManagerRemoved(Creature creature)
    { if (Find(creature) is { } t && Current(t)) t.ManagerRemoved = true; }
    private static void MovePrefix(MonsterModel __instance, out MoveCall? __state)
    {
        __state = null;
        if (__instance is not TestSubject) return;
        var depth = Moves.GetValue(__instance.Creature, _ => new()); depth.Count++;
        __state = new(__instance.Creature, depth);
    }
    private static void CloseMove(MoveCall call)
    { if (!call.Closed) { call.Closed = true; call.Depth.Count--; } }
    private static void MovePostfix(MoveCall? __state, ref Task __result)
    { if (__state is not null) __result = FinishMove(__result, __state); }
    private static Exception? MoveFinalizer(Exception? __exception, MoveCall? __state)
    { if (__exception is not null && __state is not null) CloseMove(__state); return __exception; }
    private static async Task FinishMove(Task original, MoveCall call)
    {
        try { await original; }
        finally { CloseMove(call); }
        // Death can happen inside a previously living monster's move. Resolve its
        // current corpse only here, after both outer waits and native move history.
        if (Find(call.Owner) is { } t) await FinalizeWhenSafe(t);
    }

    /// <summary>Await from DomainPower.AfterApplied. In-flight native death/callbacks
    /// are only marked here; they retire after their own original continuations.</summary>
    public static async Task AfterDomainOpened(Creature player)
    {
        if (!player.IsPlayer || player.CombatState is not { } combat || !Domain(combat)) return;
        CancelOpenHatches(combat);
        foreach (var owner in combat.Enemies.ToArray())
        {
            if (owner.IsAlive || owner.Monster is not TestSubject || owner.GetPower<AdaptablePower>() is not { } power) continue;
            // A concrete pending native phase can predate this Domain opening.
            if (Find(power) is null && IsReviving(power)) Create(power, combat).Confirmed = true;
        }
        foreach (var t in Pending.ToArray())
        {
            if (!Current(t) || !ReferenceEquals(t.Combat, combat) || !t.Confirmed) continue;
            if (t.Source is AdaptablePower && t.Owner.IsAlive) continue;
            Observe(t);
            if (t.Cancelled) await FinalizeWhenSafe(t);
        }
    }
    private static bool StopEnding(PowerModel __instance, ref bool __result)
    {
        if (!__instance.Owner.IsEnemy || __instance.Owner.IsPlayer) return true;
        if (Find(__instance) is { } t && Observe(t) || __instance.Owner.CombatState is { } combat && Domain(combat))
        { __result = false; return false; }
        return true;
    }
    private static bool RemovalVote(PowerModel __instance, Creature creature, ref bool __result)
    {
        if (ReferenceEquals(__instance.Owner, creature) && creature.Monster is TestSubject && Find(creature) is { } t && Observe(t))
        { __result = true; return false; }
        return true;
    }
    private static bool RemovePower(PowerModel __instance, ref bool __result)
    {
        if (__instance.Owner.Monster is TestSubject && Find(__instance.Owner) is { } t && Observe(t))
        { __result = true; return false; }
        return true;
    }
    private static bool AllowHitting(AdaptablePower __instance, Creature creature, ref bool __result)
    {
        if (ReferenceEquals(__instance.Owner, creature) &&
            (Find(__instance) is { } t && Observe(t) || creature.CombatState is { } combat && Domain(combat)))
        { __result = true; return false; }
        return true;
    }
    private static void TerminalPresentation(Ticket t)
    {
        if (t.PresentationFinished || t.Owner.Monster is not TestSubject subject) return;
        t.PresentationFinished = true;
        if (t.Source is AdaptablePower adaptable) adaptable.DoRevive();
        // TriggerDeadState's TestSubjectKills increment/music/death animation were
        // never skipped. Finish the terminal presentation without replaying AfterDeath.
        SetColor(subject, Colors.White);
        NRunMusicController.Instance?.UpdateMusicParameter("test_subject_progress", 5f);
    }
    private static Task FinalizeWhenSafe(Ticket t)
    {
        if (!Current(t) || !ReferenceEquals(Find(t.Owner), t) || !t.Cancelled || !t.Confirmed || t.Committed || t.Finished || t.Owner.IsAlive ||
            t.Source is not AdaptablePower || t.DeathDepth != 0 || t.CallbackDepth != 0 ||
            Moves.TryGetValue(t.Owner, out var move) && move.Count != 0 || t.Owner.Monster?.IsPerformingMove == true)
            return Task.CompletedTask;
        if (!Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(t.Combat, t.Owner)) return Task.CompletedTask;
        if (t.CleanupStarted) return t.Cleanup ?? Task.CompletedTask;
        t.CleanupStarted = true; return t.Cleanup = Retire(t);
    }
    private static async Task Retire(Ticket t)
    {
        var owner = t.Owner;
        var allies = t.Combat.GetTeammatesOf(owner).Where(c => c.IsAlive).ToArray();
        var primary = owner.IsPrimaryEnemy;
        TerminalPresentation(t);
        var node = NCombatRoom.Instance?.GetCreatureNode(owner);
        // A retained TestSubject may still be playing AnimDie(false). StartDeathAnim
        // refuses a second animation while that task runs; wait for its native tail
        // before requesting the terminal animation, otherwise the node never frees.
        if (node?.DeathAnimationTask is { IsCompleted: false } animation) await animation;
        if (!Current(t) || !ReferenceEquals(Find(owner), t) || owner.IsAlive ||
            !Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(t.Combat, owner))
        { t.CleanupStarted = false; t.Cleanup = null; return; }
        if (node is not null && ReferenceEquals(NCombatRoom.Instance?.GetCreatureNode(owner), node))
        { node.StartDeathAnim(true); NCombatRoom.Instance?.RemoveCreatureNode(node); }
        if (!t.ManagerRemoved) { CombatManager.Instance.RemoveCreature(owner); t.ManagerRemoved = true; }
        if (t.Combat.ContainsCreature(owner)) t.Combat.RemoveCreature(owner);
        foreach (var power in owner.RemoveAllPowersAfterDeath()) await power.AfterRemoved(owner);
        t.Finished = true; Pending.Remove(t);
        // Same secondary-enemy cleanup as native terminal death. No re-kill of the
        // already-dead owner, no HP write, no synthetic death, no CheckWinCondition.
        if (primary && allies.Length > 0 && allies.All(c => c.IsSecondaryEnemy)) await CreatureCmd.Kill(allies);
    }
}
