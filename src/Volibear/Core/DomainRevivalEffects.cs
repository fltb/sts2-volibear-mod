using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Volibear.Core;

/// <summary>Only Reattach/Illusion. No Steam, Adaptable, Stock, or generic move bypass.
/// Installation and evidence are separate; never checks/ends combat inside Domain.Open.</summary>
public static class DomainRevivalEffects
{
    private sealed class Ticket(PowerModel source, ICombatState combat, long epoch)
    {
        internal readonly PowerModel Source = source;
        internal readonly Creature Owner = source.Owner;
        internal readonly ICombatState Combat = combat;
        internal readonly long Epoch = epoch;
        internal readonly RevivalDecision Decision = new();
        internal int DeathDepth;
        internal int CallbackDepth;
        internal bool NativeRemoval;
        internal bool NativeCleanupFinished;
        internal bool NodeRetired;
        internal bool ManagerRetired;
        internal bool Finished;
        internal Task? Cleanup;
        internal bool CleanupStarted;
    }
    private sealed class DeathFrame(Creature creature, Task native, DeathFrame? previous, Ticket[] tickets)
    {
        internal readonly Creature Creature = creature;
        internal Task Native = native;
        internal readonly DeathFrame? Previous = previous;
        internal readonly Ticket[] Tickets = tickets;
        internal bool Closed;
    }
    private sealed record MoveFrame(DeathFrame? Active, DeathFrame? Previous, Task Native);
    private static readonly AsyncLocal<DeathFrame?> Current = new();
    private static ConditionalWeakTable<Task, DeathFrame> _tasks = new();
    private static readonly ConditionalWeakTable<PowerModel, Ticket> Tickets = new();
    private static readonly ConditionalWeakTable<DecimillipedeSegment, Ticket> ReattachMoves = new();
    private static readonly List<Ticket> Active = [];
    private static long _epoch;
    private static bool _installed;
    private static readonly MethodInfo ReattachPending = AccessTools.PropertyGetter(typeof(ReattachPower), "IsReviving");
    private static readonly MethodInfo OtherSegmentsDead = AccessTools.Method(typeof(ReattachPower), "AreAllOtherSegmentsDead");
    internal static event Func<PowerModel, Creature, bool, Task>? AfterDeathContribution;
    public static event Action<Creature, string>? LifecycleObserved;
    public static event Action<PowerModel>? PowerDeathCleanupCompleted;

    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony("Volibear.DomainRevivalEffects");
        try
        {
            InstallPatches(harmony);
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            _installed = true;
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }

    // Also called by the isolated emission gate; it never executes a game method.
    internal static void InstallPatches(Harmony harmony)
    {
        ValidateHealTiming();
        void Transpile(MethodInfo method, string name) => harmony.Patch(method,
            transpiler: new HarmonyMethod(typeof(DomainRevivalEffects), name));
        Transpile(MoveNext(AccessTools.Method(typeof(CreatureCmd), "KillWithoutCheckingWinCondition")), nameof(DeathMachine));
        Transpile(MoveNext(AccessTools.Method(typeof(Hook), nameof(Hook.AfterDeath))), nameof(DeathDispatch));
        Transpile(AccessTools.Method(typeof(Hook), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath)), nameof(RemovalVotes));
        Transpile(MoveNext(AccessTools.Method(typeof(IllusionPower), nameof(IllusionPower.AfterDeath))), nameof(IllusionQueue));
        Transpile(MoveNext(AccessTools.Method(typeof(IllusionPower), "ReviveMove")), nameof(IllusionReviveMachine));
        Transpile(MoveNext(AccessTools.Method(typeof(ReattachPower), nameof(ReattachPower.DoReattach))), nameof(HealCommit));
        Transpile(MoveNext(AccessTools.Method(typeof(DecimillipedeSegment), "ReattachMove")), nameof(ReattachMachine));
        Transpile(MoveNext(AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.PerformMove))), nameof(MoveTail));
        harmony.Patch(AccessTools.Method(typeof(ReattachPower), nameof(ReattachPower.ShouldPowerBeRemovedAfterOwnerDeath)),
            prefix: new HarmonyMethod(typeof(DomainRevivalEffects), nameof(RemoveCancelledSource)));
        harmony.Patch(AccessTools.Method(typeof(IllusionPower), nameof(IllusionPower.ShouldPowerBeRemovedOnDeath)),
            prefix: new HarmonyMethod(typeof(DomainRevivalEffects), nameof(RemoveCancelledPreservation)));
        harmony.Patch(AccessTools.Method(typeof(ReattachPower), nameof(ReattachPower.ShouldOwnerDeathTriggerFatal)),
            prefix: new HarmonyMethod(typeof(DomainRevivalEffects), nameof(FatalVote)));
        harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]),
            prefix: new HarmonyMethod(typeof(DomainRevivalEffects), nameof(Reset)));
    }

    private static void ValidateHealTiming()
    {
        var code = PatchProcessor.GetOriginalInstructions(MoveNext(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Heal))));
        bool Commit(CodeInstruction instruction) => instruction.operand is MethodInfo method &&
            method.DeclaringType == typeof(Creature) && method.Name == "HealInternal";
        var commit = code.FindIndex(Commit);
        var firstAwait = code.FindIndex(instruction => instruction.operand is MethodInfo method &&
            (method.Name is "AwaitOnCompleted" or "AwaitUnsafeOnCompleted"));
        if (commit < 0 || firstAwait < 0 || commit >= firstAwait || code.Count(Commit) != 1)
            throw new InvalidOperationException("Native Heal HP commit/await ordering drifted.");
    }
    private static MethodInfo MoveNext(MethodInfo method) => AccessTools.Method(
        method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Pinned async state machine absent: " + method), "MoveNext");
    private static MethodInfo Method(string name) => AccessTools.Method(typeof(DomainRevivalEffects), name);
    private static bool Supported(PowerModel power) => power is ReattachPower or IllusionPower;
    private static bool RawDomain(ICombatState combat) => CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsAboutToLose &&
        ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) && combat.Players.Any(player =>
            player.Creature.IsAlive && ReferenceEquals(player.Creature.CombatState, combat) && combat.ContainsCreature(player.Creature) &&
            player.Creature.GetPowerAmount<DomainPower>() > 0);
    private static bool Pending(PowerModel power) => power switch
    {
        IllusionPower illusion => illusion.IsReviving,
        ReattachPower reattach => (bool)ReattachPending.Invoke(reattach, null)!,
        _ => false,
    };
    private static Ticket NewTicket(PowerModel source, ICombatState combat)
    {
        Tickets.Remove(source);
        var ticket = new Ticket(source, combat, _epoch);
        Tickets.Add(source, ticket); Active.Add(ticket);
        if (source is ReattachPower && ticket.Owner.Monster is DecimillipedeSegment segment)
        { ReattachMoves.Remove(segment); ReattachMoves.Add(segment, ticket); }
        return ticket;
    }
    private static Ticket? Find(PowerModel source) => Tickets.TryGetValue(source, out var ticket) ? ticket : null;
    private static Ticket? CancelledOwner(Creature owner) => Active.FirstOrDefault(ticket =>
        ReferenceEquals(ticket.Owner, owner) && ticket.Epoch == _epoch && ticket.Decision.Cancelled);

    /// <summary>Await from DomainPower.AfterApplied after its own initialization.
    /// No CheckWinCondition. An ancestor native callback must never await itself.</summary>
    public static async Task AfterDomainOpened(Creature player)
    {
        var combat = player.CombatState;
        if (combat is null || !player.IsPlayer || !RawDomain(combat)) return;
        foreach (var enemy in combat.Enemies.ToArray())
        {
            if (!enemy.IsEnemy || enemy.IsPlayer || enemy.IsAlive) continue;
            foreach (var source in enemy.Powers.Where(Supported).ToArray())
            {
                var ticket = Find(source);
                if (ticket is null || ticket.Epoch != _epoch)
                {
                    if (!Pending(source)) continue;
                    ticket = NewTicket(source, combat);
                    ticket.Decision.Confirm(false);
                }
                ticket.Decision.CancelIfRequired(true);
            }
        }
        foreach (var ticket in Active.ToArray())
            if (ticket.Decision.Cancelled) await FinalizeWhenSafe(ticket);
    }

    private static MoveFrame EnterDeath(Task native, Creature creature, int state)
    {
        var previous = Current.Value;
        if (!_tasks.TryGetValue(native, out var frame) && state == -1 && creature.CombatState is { } combat && creature.IsEnemy && !creature.IsPlayer)
        {
            var tickets = creature.Powers.Where(Supported).Select(source =>
            {
                var old = Find(source);
                var ticket = old is { Finished: false } && old.Epoch == _epoch && !old.Decision.Committed
                    ? old : NewTicket(source, combat);
                ticket.DeathDepth++;
                ticket.Decision.ObserveDomain(RawDomain(combat));
                return ticket;
            }).ToArray();
            frame = new DeathFrame(creature, native, previous, tickets);
            _tasks.Add(native, frame);
        }
        Current.Value = frame;
        return new MoveFrame(frame, previous, native);
    }
    private static void LeaveDeath(MoveFrame move, Task native, int state)
    {
        var frame = move.Active;
        if (frame is not null)
        {
            if (!frame.Closed && !ReferenceEquals(move.Native, native))
            {
                _tasks.Remove(move.Native);
                if (!_tasks.TryGetValue(native, out _)) _tasks.Add(native, frame);
                frame.Native = native;
            }
            if (native.IsCompleted) CloseDeath(frame, native.IsCompletedSuccessfully);
        }
        Current.Value = move.Previous;
    }
    private static void CloseDeath(DeathFrame frame, bool success)
    {
        if (frame.Closed) return;
        frame.Closed = true;
        foreach (var ticket in frame.Tickets)
        {
            ticket.DeathDepth--;
            if (success && ticket.NativeRemoval)
            { ticket.NativeCleanupFinished = true; ticket.ManagerRetired = true; ticket.NodeRetired = true; ticket.Finished = true; }
        }
        _tasks.Remove(frame.Native);
    }
    private static void BeforeDeathCompletion(MoveFrame move, bool success)
    {
        // Builder signals may run the caller inline. Release before signalling,
        // never await an ancestor Task or launch teardown from this boundary.
        if (move.Active is { } frame) CloseDeath(frame, success);
        Current.Value = move.Previous;
    }
    internal static int DeathDepthFor(PowerModel source) => Find(source)?.DeathDepth ?? 0;
    private static void ConfirmDeathBeforeVote(Creature creature)
    {
        if (Current.Value is { } frame && ReferenceEquals(frame.Creature, creature))
            foreach (var ticket in frame.Tickets)
            {
                ticket.Decision.Confirm(false);
                ticket.Decision.CancelIfRequired(RawDomain(ticket.Combat));
            }
    }
    private static bool RecordNativeRemoval(bool remove, Creature creature)
    {
        if (Current.Value is { } current && ReferenceEquals(current.Creature, creature))
            foreach (var ticket in current.Tickets) { ticket.NativeRemoval = remove; if (remove) ticket.NodeRetired = true; }
        return remove;
    }
    private static bool RemovalVote(AbstractModel source, Creature creature)
    {
        if (source is PowerModel power && Supported(power) && ReferenceEquals(power.Owner, creature) &&
            Find(power) is { } ticket && (ticket.Decision.Cancelled || ticket.Epoch != _epoch)) return true;
        return source.ShouldCreatureBeRemovedFromCombatAfterDeath(creature);
    }
    private static bool RepairRemoval(ref bool cached, Creature creature)
    {
        var ticket = CancelledOwner(creature);
        if (!cached && ticket is not null && creature.IsDead && Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(ticket.Combat, creature))
        {
            cached = true;
            LifecycleObserved?.Invoke(creature, "cached-removal-repaired");
            foreach (var match in Active.Where(t => ReferenceEquals(t.Owner, creature) && t.Epoch == _epoch)) match.NativeRemoval = true;
            RetireNode(ticket);
        }
        return cached;
    }
    private static async Task DispatchDeath(AbstractModel source, PlayerChoiceContext context, Creature creature,
#if STS2_BETA
        CardModel? cardSource,
#endif
        bool prevented, float length)
    {
        Task ForwardDeath() => source.AfterDeath(context, creature,
#if STS2_BETA
            cardSource,
#endif
            prevented, length);
        if (source is not PowerModel power || !Supported(power) || !ReferenceEquals(power.Owner, creature) || prevented)
        { await ForwardDeath(); return; }
        var ticket = Find(power);
        if (ticket is null) { await ForwardDeath(); return; }
        ticket.CallbackDepth++;
        try
        {
            var cancel = ticket.Epoch != _epoch || ticket.Decision.CancelIfRequired(RawDomain(ticket.Combat));
            var executeNative = !cancel || (power is ReattachPower reattach && creature.IsDead &&
                creature.CombatState is not null && (bool)OtherSegmentsDead.Invoke(reattach, null)!);
            if (executeNative) await ForwardDeath();
            else if (ticket.Epoch == _epoch && ticket.Decision.Cancelled)
                Volibear.Presentation.PowerPresentationDomain.Once(ticket, ticket.Owner, source, sourceCombat: ticket.Combat);
            if (AfterDeathContribution is { } observers)
                foreach (Func<PowerModel, Creature, bool, Task> observer in observers.GetInvocationList()) await observer(power, creature, executeNative);
        }
        finally { ticket.CallbackDepth--; }
        await FinalizeWhenSafe(ticket);
    }
    private static bool AllowBenefit(PowerModel source)
    {
        var ticket = Find(source);
        if (ticket is null) return true;
        if (ticket.Epoch != _epoch) return false;
        if (ticket.Decision.Cancelled)
        {
            Volibear.Presentation.PowerPresentationDomain.Once(ticket, ticket.Owner, source, sourceCombat: ticket.Combat);
            return false;
        }
        if (ticket.Decision.Committed || source.Owner.IsAlive) return true;
        bool cancelled = ticket.Decision.CancelIfRequired(RawDomain(ticket.Combat));
        if (cancelled) Volibear.Presentation.PowerPresentationDomain.Once(ticket, ticket.Owner, source, sourceCombat: ticket.Combat);
        return !cancelled;
    }
    private static void QueueIllusion(MonsterModel monster, MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState state,
        bool force, IllusionPower source)
    {
        if (AllowBenefit(source)) monster.SetMoveImmediate(state, force);
    }
    private static bool CompleteCancelledRevive(IllusionPower source, ref int state, ref AsyncTaskMethodBuilder builder)
    {
        // A resumed callback must still consume its awaiter and preserve committed work.
        if (state != -1 || AllowBenefit(source)) return false;
        state = -2;
        builder.SetResult();
        return true;
    }
    private static bool CompleteCancelledReattach(DecimillipedeSegment segment, ref int state, ref AsyncTaskMethodBuilder builder)
    {
        // This map survives power removal and reset. A live new death replaces its
        // binding; stale source continuations cannot borrow a different ticket.
        if (state != -1 || !ReattachMoves.TryGetValue(segment, out var ticket)) return false;
        var allowed = ReferenceEquals(ticket.Owner, segment.Creature) && ReferenceEquals(ticket.Owner.Monster, segment) &&
            ReferenceEquals(ticket.Source.Owner, ticket.Owner) && ReferenceEquals(Find(ticket.Source), ticket) && AllowBenefit(ticket.Source);
        if (!RevivalDecision.SkipUnstartedCallback(state, true, allowed)) return false;
        state = -2;
        builder.SetResult();
        return true;
    }
    private static async Task GuardHeal(Creature creature, decimal amount, bool animation, PowerModel source)
    {
        var ticket = Find(source);
        if (!AllowBenefit(source)) { if (ticket is not null) await FinalizeWhenSafe(ticket); return; }
        var native = CreatureCmd.Heal(creature, amount, animation);
        // Pinned native Heal commits HP before its first await. The emission test
        // additionally checks this timing; already committed resurrection is not undone.
        if (ticket is not null && creature.IsAlive && !ticket.Decision.Committed) ticket.Decision.Commit();
        await native;
    }
    private static async Task Reattach(ReattachPower source)
    {
        var ticket = Find(source);
        if (!AllowBenefit(source)) { if (ticket is not null) await FinalizeWhenSafe(ticket); return; }
        if (ticket is not null) ticket.CallbackDepth++;
        try { await source.DoReattach(); }
        finally { if (ticket is not null) ticket.CallbackDepth--; }
        if (ticket is not null) await FinalizeWhenSafe(ticket);
    }
    private static async Task FinishMoveWait(float fast, float slow, bool ignoreEnd, CancellationToken cancellation, MonsterModel monster)
    {
        await Cmd.CustomScaledWait(fast, slow, ignoreEnd, cancellation);
        foreach (var ticket in Active.Where(t => ReferenceEquals(t.Owner, monster.Creature)).ToArray())
            await FinalizeWhenSafe(ticket);
    }
    private static void RetireNode(Ticket ticket)
    {
        if (ticket.NodeRetired) return;
        ticket.NodeRetired = true;
        var node = NCombatRoom.Instance?.GetCreatureNode(ticket.Owner);
        if (node is not null) { node.StartDeathAnim(true); NCombatRoom.Instance?.RemoveCreatureNode(node); }
    }
    private static Task FinalizeWhenSafe(Ticket ticket)
    {
        if (ticket.Epoch != _epoch || !ticket.Decision.Cancelled || ticket.Finished || ticket.Owner.IsAlive ||
            ticket.DeathDepth != 0 || ticket.CallbackDepth != 0 || ticket.Owner.Monster?.IsPerformingMove == true) return Task.CompletedTask;
        if (ticket.Owner.CombatState is not null && !Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(ticket.Combat, ticket.Owner))
            return Task.CompletedTask; // Preserve unrelated native retention votes; these are not an A/B adapter.
        var peer = Active.FirstOrDefault(other => !ReferenceEquals(other, ticket) && other.Epoch == ticket.Epoch &&
            ReferenceEquals(other.Owner, ticket.Owner) && ReferenceEquals(other.Combat, ticket.Combat) &&
            (other.CleanupStarted || other.NativeCleanupFinished));
        if (peer is not null) return peer.Cleanup ?? Task.CompletedTask;
        if (ticket.CleanupStarted) return ticket.Cleanup ?? Task.CompletedTask;
        ticket.CleanupStarted = true; // Set before async invocation: native callbacks may reenter synchronously.
        return ticket.Cleanup = RetireDead(ticket);
    }
    private static async Task RetireDead(Ticket ticket)
    {
        var owner = ticket.Owner;
        var teammates = ticket.Combat.GetTeammatesOf(owner).Where(c => c.IsAlive).ToArray();
        var primary = owner.IsPrimaryEnemy;
        RetireNode(ticket);
        if (!ticket.ManagerRetired) { ticket.ManagerRetired = true; CombatManager.Instance.RemoveCreature(owner); }
        if (ticket.Combat.ContainsCreature(owner)) ticket.Combat.RemoveCreature(owner);
        foreach (var removed in owner.RemoveAllPowersAfterDeath()) await AfterRemoved(removed, owner);
        foreach (var sameOwner in Active.Where(other => ReferenceEquals(other.Owner, owner) &&
            ReferenceEquals(other.Combat, ticket.Combat) && other.Epoch == ticket.Epoch))
        { sameOwner.Finished = true; sameOwner.ManagerRetired = true; sameOwner.NodeRetired = true; }
        LifecycleObserved?.Invoke(owner, "late-corpse-retired");
        if (primary && teammates.Length > 0 && teammates.All(c => c.IsSecondaryEnemy)) await CreatureCmd.Kill(teammates);
        // Intentionally NO CheckWinCondition: native ActionExecutor/turn boundary owns teardown.
    }
    private static async Task AfterRemoved(PowerModel power, Creature owner)
    {
        await power.AfterRemoved(owner);
        PowerDeathCleanupCompleted?.Invoke(power);
    }
    private static bool RemoveCancelledSource(ReattachPower __instance, ref bool __result)
    {
        if (Find(__instance)?.Decision.Cancelled != true) return true;
        __result = true; return false;
    }
    private static bool RemoveCancelledPreservation(IllusionPower __instance, PowerModel power, ref bool __result)
    {
        var ticket = Find(__instance);
        // Native Illusion votes globally. A target's tombstone does not own another
        // living Illusion's vote, even when both sources are in the same combat.
        if (!RevivalDecision.OwnsCancelledPreservation(__instance, ticket?.Source, __instance.Owner,
            ticket?.Owner, power.Owner, ticket?.Decision.Cancelled == true, ticket?.Epoch == _epoch)) return true;
        __result = true; return false;
    }
    private static bool FatalVote(ReattachPower __instance, ref bool __result)
    {
        if (Find(__instance)?.Decision.Cancelled == true || (__instance.Owner.IsEnemy && __instance.Owner.CombatState is { } combat && RawDomain(combat)))
        { __result = true; return false; }
        return true;
    }
    public static void Reset()
    {
        _epoch++; Current.Value = null; _tasks = new(); Active.Clear();
        // Weak source tombstones intentionally remain, rejecting old continuations.
    }

    private static FieldInfo Field(Type machine, Type fieldType, string? name = null)
    {
        var found = machine.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Where(f => f.FieldType == fieldType && (name is null || f.Name.Contains(name, StringComparison.Ordinal))).ToArray();
        if (found.Length != 1) throw new InvalidOperationException($"Pinned field drift: {machine.Name}/{fieldType.Name}/{name}: {found.Length}");
        return found[0];
    }
    private static void MoveMetadata(CodeInstruction from, CodeInstruction to)
    { to.labels.AddRange(from.labels); from.labels.Clear(); to.blocks.AddRange(from.blocks); from.blocks.Clear(); }
    private static IEnumerable<CodeInstruction> Replace(IEnumerable<CodeInstruction> input, MethodInfo from, string to, int expected = 1,
        FieldInfo? source = null)
    {
        var result = new List<CodeInstruction>(); var count = 0;
        foreach (var instruction in input)
        {
            if (instruction.Calls(from))
            {
                if (source is not null)
                {
                    var load = new CodeInstruction(OpCodes.Ldarg_0); MoveMetadata(instruction, load);
                    result.Add(load); result.Add(new CodeInstruction(OpCodes.Ldfld, source));
                }
                instruction.opcode = OpCodes.Call; instruction.operand = Method(to); count++;
            }
            result.Add(instruction);
        }
        if (count != expected) throw new InvalidOperationException($"Pinned callsite drift {from}: {count}, expected {expected}");
        return result;
    }
    private static IEnumerable<CodeInstruction> DeathMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var machine = __originalMethod.DeclaringType!;
        var creature = Field(machine, typeof(Creature));
        var builder = Field(machine, typeof(AsyncTaskMethodBuilder));
        var state = Field(machine, typeof(int), "__state");
        var removal = Field(machine, typeof(bool), "shouldRemoveFromCombat");
        var task = AccessTools.PropertyGetter(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.Task));
        var removalVote = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath));
        var code = Replace(input, AccessTools.Method(typeof(PowerModel), nameof(PowerModel.AfterRemoved)), nameof(AfterRemoved)).ToList();
        var local = generator.DeclareLocal(typeof(MoveFrame));
        var result = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, task),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, creature), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state),
            new(OpCodes.Call, Method(nameof(EnterDeath))), new(OpCodes.Stloc, local),
        };
        var repairs = 0; var votes = 0; var signals = 0;
        var setResult = AccessTools.Method(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetResult));
        var setException = AccessTools.Method(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetException));
        foreach (var instruction in code)
        {
            if (instruction.Calls(removalVote))
            {
                // Leave both original arguments on the stack, and preserve the native
                // Hook call anchor for independent death-transaction adapters.
                var before = new CodeInstruction(OpCodes.Ldarg_0); MoveMetadata(instruction, before);
                result.Add(before); result.Add(new(OpCodes.Ldfld, creature));
                result.Add(new(OpCodes.Call, Method(nameof(ConfirmDeathBeforeVote))));
                result.Add(instruction);
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, creature));
                result.Add(new(OpCodes.Call, Method(nameof(RecordNativeRemoval))));
                votes++; continue;
            }
            if (instruction.opcode == OpCodes.Ldfld && Equals(instruction.operand, removal))
            {
                instruction.opcode = OpCodes.Ldflda; result.Add(instruction);
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, creature));
                result.Add(new(OpCodes.Call, Method(nameof(RepairRemoval)))); repairs++; continue;
            }
            if (instruction.Calls(setResult) || instruction.Calls(setException))
            {
                var before = new CodeInstruction(OpCodes.Ldloc, local); MoveMetadata(instruction, before);
                result.Add(before);
                result.Add(new(instruction.Calls(setResult) ? OpCodes.Ldc_I4_1 : OpCodes.Ldc_I4_0));
                result.Add(new(OpCodes.Call, Method(nameof(BeforeDeathCompletion))));
                signals++;
            }
            if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, local); MoveMetadata(instruction, load); result.Add(load);
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldflda, builder)); result.Add(new(OpCodes.Call, task));
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, state)); result.Add(new(OpCodes.Call, Method(nameof(LeaveDeath))));
            }
            result.Add(instruction);
        }
        if (votes != 1 || repairs != 3 || signals != 2) throw new InvalidOperationException($"Native death shape drifted: votes={votes}, reads={repairs}, signals={signals}; expected 1/3/2.");
        return result;
    }
    private static IEnumerable<CodeInstruction> DeathDispatch(IEnumerable<CodeInstruction> input) => Replace(input,
        AccessTools.Method(typeof(AbstractModel), nameof(AbstractModel.AfterDeath)), nameof(DispatchDeath));
    private static IEnumerable<CodeInstruction> RemovalVotes(IEnumerable<CodeInstruction> input) => Replace(input,
        AccessTools.Method(typeof(AbstractModel), nameof(AbstractModel.ShouldCreatureBeRemovedFromCombatAfterDeath)), nameof(RemovalVote));
    private static IEnumerable<CodeInstruction> IllusionQueue(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) => Replace(input,
        AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.SetMoveImmediate)), nameof(QueueIllusion),
        source: Field(__originalMethod.DeclaringType!, typeof(IllusionPower)));
    private static IEnumerable<CodeInstruction> IllusionReviveMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod) =>
        CallbackEntry(HealCommit(input, __originalMethod), generator, __originalMethod, typeof(IllusionPower), nameof(CompleteCancelledRevive));
    private static IEnumerable<CodeInstruction> ReattachMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod) =>
        CallbackEntry(ReattachCaller(input), generator, __originalMethod, typeof(DecimillipedeSegment), nameof(CompleteCancelledReattach));
    private static IEnumerable<CodeInstruction> CallbackEntry(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase original, Type sourceType, string guard)
    {
        var machine = original.DeclaringType!;
        var source = Field(machine, sourceType);
        var state = Field(machine, typeof(int), "__state");
        var builder = Field(machine, typeof(AsyncTaskMethodBuilder));
        var runNative = generator.DefineLabel();
        var boundary = new CodeInstruction(OpCodes.Nop); boundary.labels.Add(runNative);
        var result = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, source),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, state),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder),
            new(OpCodes.Call, Method(guard)),
            new(OpCodes.Brfalse, runNative), new(OpCodes.Ret), boundary,
        };
        result.AddRange(input);
        return result;
    }
    private static IEnumerable<CodeInstruction> HealCommit(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) => Replace(input,
        AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Heal)), nameof(GuardHeal),
        source: Field(__originalMethod.DeclaringType!, __originalMethod.DeclaringType!.DeclaringType!));
    private static void RestoreAliveTexture(DecimillipedeSegment segment, Godot.Texture2D texture)
    {
        if (CancelledOwner(segment.Creature) is null)
            AccessTools.Method(typeof(DecimillipedeSegment), "ChangePhobiaModeTexture").Invoke(segment, [texture]);
    }
    private static IEnumerable<CodeInstruction> ReattachCaller(IEnumerable<CodeInstruction> input) => Replace(Replace(input,
        AccessTools.Method(typeof(ReattachPower), nameof(ReattachPower.DoReattach)), nameof(Reattach)),
        AccessTools.Method(typeof(DecimillipedeSegment), "ChangePhobiaModeTexture"), nameof(RestoreAliveTexture));
    private static IEnumerable<CodeInstruction> MoveTail(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var source = Field(__originalMethod.DeclaringType!, typeof(MonsterModel));
        var code = input.ToList();
        var waits = code.Select((instruction, i) => (instruction, i)).Where(pair =>
            pair.instruction.Calls(AccessTools.Method(typeof(Cmd), nameof(Cmd.CustomScaledWait)))).ToArray();
        if (waits.Length != 2) throw new InvalidOperationException("Native monster move wait boundaries drifted.");
        var last = waits[1].i;
        var head = code.Take(last).ToList();
        var tail = Replace(code.Skip(last), AccessTools.Method(typeof(Cmd), nameof(Cmd.CustomScaledWait)), nameof(FinishMoveWait), source: source);
        head.AddRange(tail); return head;
    }
}
