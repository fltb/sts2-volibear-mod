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
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    private enum Flow { Death, Phase, About, Explode, Attack, Damage, SetHp, SetMaxHp, NativeMove }
    private sealed class Episode(WaterfallGiant monster, SteamEruptionPower source, ICombatState combat, long generation, long epoch)
    {
        internal readonly ConditionalWeakTable<Creature, OwnerDeathLease> OwnerRegistry = ActiveFrame?.OwnerRegistry ?? OwnerDeaths;
        internal readonly WaterfallGiant Monster = monster;
        internal readonly Creature Owner = monster.Creature;
        internal readonly SteamEruptionPower Source = source;
        internal readonly ICombatState Combat = combat;
        internal readonly SteamEruptionDecision Decision = new(combat, monster, source, generation, epoch);
        internal int DeathDepth, PhaseDepth, MoveDepth, AttackDepth, DamageDepth;
        internal int InitialDeaths, TerminalDeaths;
        internal bool NativeRemoval, NativeDeathCleanup, NodeRemoved, ManagerRemoved, SourceRemovalStarted;
        internal Task? SourceRemoval;
        internal bool CleanupStarted;
        internal Task? Cleanup;
        internal readonly List<AttackCommand> Commands = [];
    }
    private sealed class DamageInvocation(Episode episode, AttackCommand command)
    {
        internal readonly Episode Episode = episode;
        internal readonly AttackCommand Command = command;
        internal int TargetOrdinal;
    }
    private sealed class Frame(Task native, Flow flow, object? subject, Episode? episode, Frame? previous)
    {
        internal readonly long Epoch = previous?.Epoch ?? Origin.Value?.Epoch ?? _epoch;
        internal readonly ConditionalWeakTable<Creature, OwnerDeathLease> OwnerRegistry = previous?.OwnerRegistry ?? Origin.Value?.OwnerRegistry ?? OwnerDeaths;
        internal Task Native = native;
        internal readonly Flow Flow = flow;
        internal readonly object? Subject = subject;
        internal readonly Episode? Episode = episode;
        internal readonly Frame? Previous = previous;
        internal DamageInvocation? Damage;
        internal bool TerminalDeath, Closed, DeathConfirmed;
        internal OwnerDeathLease? DeathLease;
        internal long DeathAttempt;
        internal bool NativeRemoval, FirstMoveReturned;
        internal readonly List<HpObservation> HpObservations = [];
    }
    private sealed class OwnerDeathLease { internal int Active, HpCommandsActive; internal long Serial, LastConfirmed; internal bool UnconfirmedHold; }
    private sealed record Step(Frame Frame, Frame? Previous, Task Native, Frame? PreviousOrigin);
    private sealed record CleanupLease(Episode Episode, CleanupLease? Previous);
    private static readonly AsyncLocal<Frame?> Current = new();
    private static readonly AsyncLocal<CleanupLease?> CleanupOwner = new();
    private static readonly AsyncLocal<SteamSingleUseBinding<Episode>?> PendingPhase = new();
    private static readonly AsyncLocal<SteamSingleUseBinding<DamageInvocation>?> PendingDamage = new();
    private sealed class PendingBindings { internal readonly List<WeakReference<Frame>> Items = []; }
    private static readonly object NullSubject = new();
    private static readonly ConditionalWeakTable<object, PendingBindings> Unreturned = new();
    private static Frame? UnreturnedBinding(object? subject, Flow flow)
    {
        if (!Unreturned.TryGetValue(subject ?? NullSubject, out var bucket)) return null;
        var live = bucket.Items.Select(item => item.TryGetTarget(out var value) ? value : null)
            .Where(frame => frame is not null && !frame.Closed && !frame.FirstMoveReturned && frame.Flow == flow).ToArray();
        return live.Length == 1 ? live[0] : null; // Never borrow one of several ambiguous generations.
    }
    // Reset clears ambient tagging, not the origin of an executing native MoveNext.
    // Otherwise a synchronous post-Reset child could silently become a fresh root.
    private static readonly AsyncLocal<Frame?> Origin = new();
    private static Frame? ActiveFrame => Current.Value ?? Origin.Value;
    private static readonly ConditionalWeakTable<Task, Frame> Frames = new();
    private static readonly ConditionalWeakTable<Task, Frame> DeathRoots = new();
    private static readonly ConditionalWeakTable<WaterfallGiant, Episode> Latest = new();
    private static readonly ConditionalWeakTable<AttackCommand, Episode> Attacks = new();
    private static ConditionalWeakTable<Creature, OwnerDeathLease> OwnerDeaths = new();
    private static void PublishConfirmed(Episode episode)
    {
        if (!episode.Decision.DeathConfirmed || episode.Decision.Epoch != _epoch) return;
        var previous = LatestFor(episode.Monster);
        if (previous is not null && previous.Decision.Generation >= episode.Decision.Generation) return;
        Latest.Remove(episode.Monster); Latest.Add(episode.Monster, episode); Episodes.Add(episode);
    }
    private static bool HasProtectedCommit(Episode episode) => episode.Decision.Writes.Any(write =>
        write.Part == "protected-current-hp" && write.After > 0);
    private static bool OwnerScopesClosed(Episode episode) => IsCurrent(episode) &&
        (!OwnerDeaths.TryGetValue(episode.Owner, out var lease) || lease.Active == 0 && lease.HpCommandsActive == 0);
    private static bool DeathBlocksDrain(Episode episode, bool nativeTail) => OwnerDeaths.TryGetValue(episode.Owner, out var lease) &&
        (lease.Active > 0 || lease.HpCommandsActive > 0 || !nativeTail && lease.UnconfirmedHold);
    private static readonly List<Episode> Episodes = [];
    private static long _epoch, _generation;
    private static bool _installed;
    internal static event Action<Creature, string>? Observed;
    internal static event Func<Creature, string, Task>? Boundary;

    private static Episode? LatestFor(WaterfallGiant monster) => Latest.TryGetValue(monster, out var episode) ? episode : null;
    private static bool IsCurrent(Episode episode) => episode.Decision.Epoch == _epoch && ReferenceEquals(LatestFor(episode.Monster), episode);
    private static bool RawDomain(Episode episode) => CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsAboutToLose &&
        ReferenceEquals(episode.Combat, CombatManager.Instance.DebugOnlyGetState()) && episode.Combat.Players.Any(player =>
            player.Creature.IsAlive && ReferenceEquals(player.Creature.CombatState, episode.Combat) &&
            episode.Combat.ContainsCreature(player.Creature) && player.Creature.GetPowerAmount<DomainPower>() > 0);
    private static bool Allow(Episode episode)
    {
        if (!IsCurrent(episode)) return false;
        episode.Decision.ObserveDomain(RawDomain(episode));
        return episode.Decision.CanApplyBenefit;
    }
    private static bool HasAncestor(Episode episode)
    {
        for (var frame = ActiveFrame; frame is not null; frame = frame.Previous)
            if (!frame.Closed && ReferenceEquals(frame.Episode, episode)) return true;
        return OwnCleanup(episode);
    }
    private static bool OwnCleanup(Episode episode)
    {
        for (var lease = CleanupOwner.Value; lease is not null; lease = lease.Previous)
            if (ReferenceEquals(lease.Episode, episode)) return true;
        return false;
    }
    private static Episode? CurrentEpisode(Flow kind, object subject) => ActiveFrame is { } frame &&
        !frame.Closed && frame.Flow == kind && ReferenceEquals(frame.Subject, subject) ? frame.Episode : null;
    private static void Count(Frame frame, int delta)
    {
        if (frame.Episode is not { } episode) return;
        switch (frame.Flow)
        {
            case Flow.Death: if (!frame.TerminalDeath) episode.DeathDepth += delta; break;
            case Flow.Phase: episode.PhaseDepth += delta; break;
            case Flow.About: case Flow.Explode: episode.MoveDepth += delta; break;
            case Flow.Attack: episode.AttackDepth += delta; break;
            case Flow.Damage: episode.DamageDepth += delta; break;
        }
    }
    private static Step Enter(Task native, object? subject, int state, Flow flow)
    {
        var previous = Current.Value; var previousOrigin = Origin.Value;
        if (!Frames.TryGetValue(native, out var frame) && state != -1)
        {
            // Await registration can synchronously resume the boxed machine before
            // its first MoveNext returns and rereads the actual builder Task.
            var binding = previous is { Closed: false } && previous.Flow == flow && ReferenceEquals(previous.Subject, subject)
                ? previous : UnreturnedBinding(subject, flow);
            if (binding is null || !Frames.TryGetValue(binding.Native, out var provisional) || !ReferenceEquals(provisional, binding))
                throw new InvalidOperationException("Unowned or ambiguous resumed Steam native scope.");
            frame = binding; Frames.Remove(frame.Native); Frames.Add(native, frame); frame.Native = native;
            if (flow == Flow.Death && !DeathRoots.TryGetValue(native, out _)) DeathRoots.Add(native, frame);
        }
        if (frame is null)
        {
            var contextEpoch = previous?.Epoch ?? Origin.Value?.Epoch ?? _epoch;
            // An old continuation may finish, but cannot dispatch new native work under
            // the authority of a creature/model now owned by a fresh combat episode.
            var subjectMonster = subject as WaterfallGiant ?? (subject as Creature)?.Monster as WaterfallGiant;
            if (contextEpoch != _epoch && subjectMonster is not null && LatestFor(subjectMonster) is { } currentOwner && IsCurrent(currentOwner))
                throw new InvalidOperationException("Stale Steam child cannot enter a new epoch owner.");
            Episode? episode = null;
            DamageInvocation? damage = null;
            var terminal = false;
            if (state == -1)
            {
                if (flow == Flow.Death && subject is Creature creature && creature.IsEnemy && creature.Monster is WaterfallGiant giant && creature.CombatState is { } combat)
                {
                    var own = CleanupOwner.Value?.Episode;
                    if (own is not null && ReferenceEquals(own.Owner, creature)) { episode = own; terminal = true; }
                    else if (creature.GetPower<SteamEruptionPower>() is { } steam)
                    {
                        episode = new Episode(giant, steam, combat, ++_generation, contextEpoch);
                        episode.Decision.ObserveDomain(RawDomain(episode));
                        // A pending attempt must not replace the still-owned confirmed phase.
                        // Publish only after the native Died signal, never on mere Kill entry.
                    }
                    else if (LatestFor(giant) is { } pending && IsCurrent(pending) && HasProtectedCommit(pending) &&
                        pending.Decision.DeathConfirmed && !pending.Decision.Retired && ReferenceEquals(pending.Combat, combat))
                    { episode = pending; terminal = true; } // A real external death can consume the power-less protected phase too.
                }
                else if (flow == Flow.Phase)
                {
                    episode = PendingPhase.Value?.Consume(); PendingPhase.Value = null;
                    if (episode is not null && !ReferenceEquals(subject, episode.Monster)) throw new InvalidOperationException("Steam phase provenance mismatch.");
                }
                else if ((flow is Flow.About or Flow.Explode) && subject is WaterfallGiant monster) episode = LatestFor(monster);
                else if (flow == Flow.Attack && subject is AttackCommand command) Attacks.TryGetValue(command, out episode);
                else if (flow == Flow.Damage)
                {
                    damage = PendingDamage.Value?.Consume(); PendingDamage.Value = null;
                    episode = damage?.Episode;
                    if (episode is not null && !ReferenceEquals(subject, episode.Owner)) throw new InvalidOperationException("Steam damage dealer provenance mismatch.");
                }
            }
            if (episode?.Decision is { } boundDecision && boundDecision.Epoch != contextEpoch)
                throw new InvalidOperationException("Steam child binding crossed its continuation epoch.");
            frame = new Frame(native, flow, subject, episode, previous) { Damage = damage, TerminalDeath = terminal };
            if (flow == Flow.Death && subject is Creature deathOwner && deathOwner.Monster is WaterfallGiant)
            {
                frame.DeathLease = frame.OwnerRegistry.GetValue(deathOwner, _ => new OwnerDeathLease());
                frame.DeathAttempt = ++frame.DeathLease.Serial; frame.DeathLease.Active++;
            }
            var bucket = Unreturned.GetValue(subject ?? NullSubject, _ => new PendingBindings());
            bucket.Items.RemoveAll(item => !item.TryGetTarget(out var prior) || prior.Closed || prior.FirstMoveReturned);
            bucket.Items.Add(new(frame));
            Frames.Add(native, frame); Count(frame, 1);
            if (flow == Flow.Death) DeathRoots.Add(native, frame);
        }
        Current.Value = frame; // Untagged calls intentionally mask a tagged parent's scope.
        Origin.Value = frame;
        return new Step(frame, previous, native, previousOrigin);
    }
    private static void Close(Frame frame, bool success)
    {
        if (frame.Closed) return;
        frame.Closed = true; Count(frame, -1);
        foreach (var observation in frame.HpObservations)
        {
            observation.Lease.HpCommandsActive--;
            if (observation.Owner.IsDead && observation.Lease.LastConfirmed <= observation.ConfirmedBefore)
                observation.Lease.UnconfirmedHold = true; // A failed/aborted command is not a confirmed native death.
        }
        if (frame.DeathLease is { } lease)
        {
            lease.Active--;
            if ((!success || !frame.DeathConfirmed) && frame.DeathAttempt > lease.LastConfirmed) lease.UnconfirmedHold = true;
        }
        if (success && frame.DeathConfirmed && frame.Flow == Flow.Death && frame.Episode is { } episode && frame.NativeRemoval && !frame.TerminalDeath)
        { episode.NativeDeathCleanup = true; episode.NodeRemoved = true; episode.ManagerRemoved = true; }
        Frames.Remove(frame.Native);
    }
    private static void BeforeSignal(Step step, bool success) { Close(step.Frame, success); Current.Value = step.Previous; Origin.Value = step.PreviousOrigin; }
    private static void Leave(Step step, Task native)
    {
        step.Frame.FirstMoveReturned = true;
        if (!step.Frame.Closed && !ReferenceEquals(step.Native, native))
        {
            Frames.Remove(step.Native);
            if (!Frames.TryGetValue(native, out _)) Frames.Add(native, step.Frame);
            step.Frame.Native = native;
            if (step.Frame.Flow == Flow.Death && !DeathRoots.TryGetValue(native, out _)) DeathRoots.Add(native, step.Frame);
        }
        if (native.IsCompleted) Close(step.Frame, native.IsCompletedSuccessfully);
        Current.Value = step.Previous; Origin.Value = step.PreviousOrigin;
    }
    public static void Reset()
    {
        _epoch++; OwnerDeaths = new(); Current.Value = null; CleanupOwner.Value = null; PendingPhase.Value = null; PendingDamage.Value = null;
        Episodes.Clear(); // Weak task bindings survive reset so old awaiters can finish without borrowing a new generation.
        // Epoch checks reject their future benefits; no strong global list retains old episodes.
    }
    private static MethodInfo Own(string name) => AccessTools.Method(typeof(DomainSteamEruptionEffects), name);
    private static MethodInfo Async(MethodInfo method) => AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Missing native state machine: " + method), "MoveNext");
    private static FieldInfo Field(Type type, Func<FieldInfo, bool> predicate)
    {
        var fields = type.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Where(predicate).ToArray();
        return fields.Length == 1 ? fields[0] : throw new InvalidOperationException("Native field shape drift: " + type + " count=" + fields.Length);
    }
    private static FieldInfo Subject(Type machine, Flow flow) => flow switch
    {
        Flow.Death or Flow.SetHp or Flow.SetMaxHp => Field(machine, field => field.FieldType == typeof(Creature) && field.Name == "creature"),
        Flow.Damage => Field(machine, field => field.FieldType == typeof(Creature) && field.Name == "dealer"),
        Flow.Attack => Field(machine, field => field.FieldType == typeof(AttackCommand)),
        Flow.NativeMove => Field(machine, field => field.FieldType == typeof(MonsterModel)),
        _ => Field(machine, field => field.FieldType == typeof(WaterfallGiant)),
    };
    private static void Metadata(CodeInstruction from, CodeInstruction to)
    { to.labels.AddRange(from.labels); from.labels.Clear(); to.blocks.AddRange(from.blocks); from.blocks.Clear(); }
    private static IEnumerable<CodeInstruction> Scope(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase original, Flow flow)
    {
        var machine = original.DeclaringType!;
        var subject = Subject(machine, flow);
        var state = Field(machine, field => field.FieldType == typeof(int) && field.Name.Contains("__state", StringComparison.Ordinal));
        var builder = Field(machine, field => field.FieldType == typeof(AsyncTaskMethodBuilder) ||
            field.FieldType.IsGenericType && field.FieldType.GetGenericTypeDefinition() == typeof(AsyncTaskMethodBuilder<>));
        var task = AccessTools.PropertyGetter(builder.FieldType, "Task");
        var local = generator.DeclareLocal(typeof(Step));
        var result = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, task),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, subject), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state),
            new(OpCodes.Ldc_I4, (int)flow), new(OpCodes.Call, Own(nameof(Enter))), new(OpCodes.Stloc, local),
        };
        var signals = 0;
        foreach (var instruction in input)
        {
            if (instruction.operand is MethodInfo method && method.DeclaringType == builder.FieldType && (method.Name is "SetResult" or "SetException"))
            {
                var before = new CodeInstruction(OpCodes.Ldloc, local); Metadata(instruction, before); result.Add(before);
                result.Add(new(method.Name == "SetResult" ? OpCodes.Ldc_I4_1 : OpCodes.Ldc_I4_0));
                result.Add(new(OpCodes.Call, Own(nameof(BeforeSignal)))); signals++;
            }
            if (instruction.opcode == OpCodes.Ret)
            {
                var before = new CodeInstruction(OpCodes.Ldloc, local); Metadata(instruction, before); result.Add(before);
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldflda, builder)); result.Add(new(OpCodes.Call, task));
                result.Add(new(OpCodes.Call, Own(nameof(Leave))));
            }
            result.Add(instruction);
        }
        if (signals != 2) throw new InvalidOperationException("Native completion signal shape drift: " + original);
        return result;
    }
    private static IEnumerable<CodeInstruction> Replace(IEnumerable<CodeInstruction> input, MethodInfo native, string adapter, int expected = 1, FieldInfo? subject = null)
    {
        var result = new List<CodeInstruction>(); var count = 0;
        foreach (var instruction in input)
        {
            if (instruction.Calls(native))
            {
                if (subject is not null)
                {
                    var load = new CodeInstruction(OpCodes.Ldarg_0); Metadata(instruction, load); result.Add(load);
                    result.Add(new(OpCodes.Ldfld, subject));
                }
                instruction.opcode = OpCodes.Call; instruction.operand = Own(adapter); count++;
            }
            result.Add(instruction);
        }
        if (count != expected) throw new InvalidOperationException($"Native call shape drift {native}: {count}, expected {expected}");
        return result;
    }
}
