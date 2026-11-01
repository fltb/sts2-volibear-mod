using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;

namespace Volibear.Core;

/// <summary>Only the native Magi Dampen ledger+card pair. Native admission, ending/exception behavior and restitution remain native.</summary>
public static class DomainDampenTransactions
{
    private const string HarmonyId = "Volibear.DomainDampenTransactions";
    private static readonly object Sync = new();
    private static long _epoch, _nonce;
    private static bool _installed;
    private static long Epoch => Interlocked.Read(ref _epoch);
    private static long Nonce() => Interlocked.Increment(ref _nonce);
    private sealed class Outer(DampenLifetime life, MagiKnight source, Creature caster, ICombatState? combat)
    {
        public DampenLifetime Life { get; } = life;
        public MagiKnight Source { get; } = source;
        public Creature Caster { get; } = caster;
        public ICombatState? Combat { get; set; } = combat;
    }
    private sealed record Move(DampenLifetime Life, Outer Outer);
    private sealed record Request(Move Move, DampenPower Power, Creature Target, Creature Caster, CardModel? Card);
    private sealed record Apply(DampenLifetime Life, Request Request);
    private sealed class Invocation(Apply? apply, DampenPower power, Creature? applier, CardModel? card, string reason)
    {
        internal readonly Apply? Apply = apply;
        internal readonly DampenPower Power = power;
        internal readonly Creature? Applier = applier;
        internal readonly CardModel? Card = card;
        internal readonly string Reason = reason;
        internal readonly long Nonce = DomainDampenTransactions.Nonce();
        internal bool Closed, Reported;
    }
    private sealed class InvocationRequest(Apply apply)
    {
        internal readonly Apply Apply = apply;
        internal Invocation? Bound;
    }
    private static ConditionalWeakTable<Task, Outer> _outers = new();
    private static ConditionalWeakTable<Task, Move> _moves = new();
    private static ConditionalWeakTable<Task, Apply> _applies = new();
    private static readonly Dictionary<PowerModel, HashSet<Apply>> ActivePowers = new(ReferenceEqualityComparer.Instance);
    private static readonly AsyncLocal<DampenHandoff<Outer>?> PendingMove = new();
    private static readonly AsyncLocal<DampenHandoff<Request>?> PendingApply = new();
    private static readonly AsyncLocal<DampenHandoff<InvocationRequest>?> PendingInvocation = new();
    private static readonly MethodInfo NativeMagi = AccessTools.DeclaredMethod(typeof(MagiKnight), "DampenMove");
    private static readonly FieldInfo NativeAction = AccessTools.Field(typeof(MoveState), "_onPerform");
    private static bool Live(Outer value) => value.Life.Live(Epoch);
    private static bool Live(Move value) => value.Life.Live(Epoch) && Live(value.Outer);
    private static bool Live(Apply value) => value.Life.Live(Epoch) && Live(value.Request.Move);
    private static bool Stale(Outer value) => value.Life.Epoch != Epoch;
    private static bool Stale(Move value) => value.Life.Epoch != Epoch || Stale(value.Outer);
    private static bool Stale(Apply value) => value.Life.Epoch != Epoch || Stale(value.Request.Move) ||
        !ReferenceEquals(value.Request.Target.CombatState, value.Request.Move.Outer.Combat);
    private static bool Carry(Outer value) => !value.Life.Closed && !value.Life.Task.IsCompleted;
    private static bool Carry(Move value) => !value.Life.Closed && !value.Life.Task.IsCompleted && Carry(value.Outer);

    public sealed record PairObservation(DampenPower Power, CardModel Card, Creature? Source, ICombatState? Combat,
        long InvocationNonce, long ApplyNonce, long MoveNonce, long OuterNonce, int BeforeLevel, int AfterLevel,
        int LedgerBefore, int LedgerAfter, bool DomainAtAdmission, bool Suppressed, string Provenance,
        IReadOnlyList<KeyValuePair<CardModel, int>> Ledger);
    // A probe may explicitly inject a boundary transition here; production has no subscribers.
    public static event Action<PairObservation>? PairObserved;

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task PerformFromMagi(MoveState move, IEnumerable<Creature> targets, MonsterModel source,
        ICombatState nativeSavedCombat, ref AsyncTaskMethodBuilder builder, ref Outer? bound)
    {
        if (source is not MagiKnight magi || move.Id != "DAMPEN_MOVE" || !source.Creature.IsEnemy || source.Creature.IsPlayer ||
            NativeAction.GetValue(move) is not Delegate action || action.Method != NativeMagi || !ReferenceEquals(action.Target, magi))
            return move.PerformMove(targets);
        var frame = bound;
        if (frame is null || !ReferenceEquals(frame.Source, magi) || !Carry(frame)) return move.PerformMove(targets);
        frame.Combat = nativeSavedCombat; // Only the native saved field supplies combat authority, never the target.
        lock (Sync) Rebind(_outers, frame, frame.Life, builder.Task);
        var previous = PendingMove.Value;
        PendingMove.Value = new(frame);
        try { return move.PerformMove(targets); }
        catch { frame.Life.Close(); throw; }
        finally { PendingMove.Value = previous; }
    }
    private static Outer? EnterOuter(int state, ref AsyncTaskMethodBuilder builder, MonsterModel source)
    {
        if (source is not MagiKnight magi) return null;
        lock (Sync)
        {
            if (state != -1) { _outers.TryGetValue(builder.Task, out var existing); return existing; }
            var frame = new Outer(new(builder.Task, Epoch, Nonce()), magi, magi.Creature, null);
            if (_outers.TryGetValue(builder.Task, out var duplicate)) { duplicate.Life.Conflict(); frame.Life.Conflict(); }
            else _outers.Add(builder.Task, frame);
            return frame;
        }
    }
    private static Move? EnterMove(int state, ref AsyncTaskMethodBuilder builder, MagiKnight source)
    {
        if (state != -1) { lock (Sync) { _moves.TryGetValue(builder.Task, out var existing); return existing; } }
        var ticket = PendingMove.Value;
        var outer = ticket?.Claim(ReferenceEquals(ticket.Value.Source, source) && Carry(ticket.Value));
        if (outer is null) return null;
        var task = builder.Task;
        var frame = new Move(new(task, outer.Life.Epoch, Nonce()), outer);
        lock (Sync) { if (_moves.TryGetValue(task, out var old)) { old.Life.Conflict(); frame.Life.Conflict(); } else _moves.Add(task, frame); }
        return frame;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task ApplyFromMagi(PlayerChoiceContext context, PowerModel power, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, MagiKnight source, Move? move)
    {
        Request? request = power is DampenPower dampen && move is not null && Carry(move) && move.Outer.Combat is not null &&
            ReferenceEquals(source, move.Outer.Source) && ReferenceEquals(applier, move.Outer.Caster) && card is null && target.IsPlayer
            ? new(move, dampen, target, applier!, card) : null;
        var previous = PendingApply.Value;
        PendingApply.Value = request is null ? null : new(request);
        try { return PowerCmd.Apply(context, power, target, amount, applier, card, silent); }
        finally { PendingApply.Value = previous; }
    }
    private static Apply? EnterApply(int state, ref AsyncTaskMethodBuilder builder, PowerModel power, Creature target, Creature? applier, CardModel? card)
    {
        if (state != -1)
        {
            lock (Sync) { if (power is not DampenPower) return null; _applies.TryGetValue(builder.Task, out var existing); return existing; }
        }
        var ticket = PendingApply.Value;
        var request = ticket?.Claim(ReferenceEquals(ticket.Value.Power, power) && ReferenceEquals(ticket.Value.Target, target) &&
            ReferenceEquals(ticket.Value.Caster, applier) && ReferenceEquals(ticket.Value.Card, card) && Carry(ticket.Value.Move));
        if (request is null)
        {
            // A nested/untracked call using an already in-flight power is not a second authority.
            lock (Sync) if (ActivePowers.TryGetValue(power, out var occupied)) foreach (var old in occupied) old.Life.Conflict();
            return null;
        }
        var task = builder.Task;
        var frame = new Apply(new(task, request.Move.Life.Epoch, Nonce()), request);
        lock (Sync)
        {
            if (!Stale(frame))
            {
                if (!ActivePowers.TryGetValue(power, out var slot)) ActivePowers.Add(power, slot = new());
                if (slot.Count != 0) { frame.Life.Conflict(); foreach (var old in slot) old.Life.Conflict(); }
                slot.Add(frame);
            }
            if (_applies.TryGetValue(task, out var duplicate)) { duplicate.Life.Conflict(); frame.Life.Conflict(); }
            else _applies.Add(task, frame);
        }
        return frame;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Task AfterAppliedFromTask(PowerModel power, Creature? applier, CardModel? card, Apply? frame)
    {
        // A precisely identified obsolete Dampen callback must not even enumerate the reused player's NEW AllCards.
        if (power is DampenPower && frame is not null && ReferenceEquals(frame.Request.Power, power) && Stale(frame)) return Task.CompletedTask;
        var previous = PendingInvocation.Value;
        var request = frame is not null && power is DampenPower && ReferenceEquals(frame.Request.Power, power)
            ? new InvocationRequest(frame) : null;
        PendingInvocation.Value = request is null ? null : new(request);
        try { return power.AfterApplied(applier, card); }
        finally
        {
            if (request?.Bound is { } invocation) invocation.Closed = true;
            PendingInvocation.Value = previous;
        }
    }
    private static Invocation BeginInvocation(DampenPower power, Creature? applier, CardModel? card)
    {
        var ticket = PendingInvocation.Value;
        var request = ticket?.Claim(ReferenceEquals(ticket.Value.Apply.Request.Power, power) &&
            ReferenceEquals(ticket.Value.Apply.Request.Caster, applier) && ReferenceEquals(ticket.Value.Apply.Request.Card, card));
        if (request is null)
        {
            if (ticket is not null) ticket.Value.Apply.Life.Conflict();
            lock (Sync) if (ActivePowers.TryGetValue(power, out var occupied)) foreach (var active in occupied) active.Life.Conflict();
        }
        var invocation = new Invocation(request?.Apply, power, applier, card,
            request is not null ? "native-magi" : applier?.IsPlayer == true ? "player" : "untracked-or-reentrant");
        if (request is not null) request.Bound = invocation;
        return invocation;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void CommitPair(Dictionary<CardModel, int> ledger, CardModel card, int oldLevel, Invocation invocation)
    {
        var apply = invocation.Apply;
        // Reset inside an already admitted card callback never rolls that card back, but rejects every later pair.
        if (apply is not null && Stale(apply)) return;
        bool source = !invocation.Closed && apply is not null && Live(apply) &&
            ReferenceEquals(invocation.Power, apply.Request.Power) && ReferenceEquals(invocation.Power.Owner, apply.Request.Target) &&
            ReferenceEquals(invocation.Applier, apply.Request.Caster) && invocation.Card is null &&
            ReferenceEquals(card.Owner.Creature, apply.Request.Target) &&
            ReferenceEquals(apply.Request.Target.CombatState, apply.Request.Move.Outer.Combat);
        string provenance = source ? "native-magi" : invocation.Reason == "player" ? "player" : "unsupported";
        if (provenance == "unsupported" && !invocation.Reported)
        { invocation.Reported = true; GD.Print("[Volibear] DOMAIN_DAMPEN_SOURCE_UNSUPPORTED exact active invocation not proven; native pair retained"); }
        bool domain = source && DomainEnemyEffects.ActiveFor(apply!.Request.Move.Outer.Combat);
        int before = card.CurrentUpgradeLevel, count = ledger.Count;
        if (!domain) { ledger.Add(card, oldLevel); CardCmd.Downgrade(card); }
        else Volibear.Presentation.PowerPresentationDomain.Suppressed(apply!.Request.Caster, invocation.Power, card);
        PairObserved?.Invoke(new(invocation.Power, card, apply?.Request.Caster, apply?.Request.Move.Outer.Combat,
            invocation.Nonce, apply?.Life.Nonce ?? 0, apply?.Request.Move.Life.Nonce ?? 0, apply?.Request.Move.Outer.Life.Nonce ?? 0,
            before, card.CurrentUpgradeLevel, count, ledger.Count, domain, domain, provenance, ledger.ToArray()));
    }
    // These run BEFORE the original builder.SetResult/SetException, not from a completion continuation.
    private static void Remove<T>(ConditionalWeakTable<Task, T> table, Task task, T frame) where T : class
    { if (table.TryGetValue(task, out var found) && ReferenceEquals(found, frame)) table.Remove(task); }
    private static void CloseOuter(Outer? frame)
    { if (frame is null) return; lock (Sync) { frame.Life.Close(); Remove(_outers, frame.Life.Task, frame); } }
    private static void CloseMove(Move? frame)
    { if (frame is null) return; lock (Sync) { frame.Life.Close(); Remove(_moves, frame.Life.Task, frame); } }
    private static void CloseApply(Apply? frame)
    {
        if (frame is null) return;
        lock (Sync)
        {
            frame.Life.Close(); Remove(_applies, frame.Life.Task, frame);
            if (ActivePowers.TryGetValue(frame.Request.Power, out var slot))
            { slot.Remove(frame); if (slot.Count == 0) ActivePowers.Remove(frame.Request.Power); }
        }
    }
    private static void Rebind<T>(ConditionalWeakTable<Task, T> table, T frame, DampenLifetime life, Task actual) where T : class
    {
        if (life.Closed || ReferenceEquals(life.Task, actual)) return;
        Remove(table, life.Task, frame);
        life.Rebind(actual);
        if (table.TryGetValue(actual, out var other)) { if (!ReferenceEquals(other, frame)) life.Conflict(); }
        else table.Add(actual, frame);
    }
    private struct RegistrationAwaiter<TAwaiter>(TAwaiter native, object frame) : ICriticalNotifyCompletion where TAwaiter : ICriticalNotifyCompletion
    {
        private TAwaiter _native = native;
        private readonly object _frame = frame;
        private void Bind(Action continuation)
        {
            // .NET's builder supplies its actual Task-derived state-machine box as the action target.
            if (continuation.Target is not Task actual) throw new InvalidOperationException("Pinned CLR state-machine continuation target drifted");
            lock (Sync)
            {
                switch (_frame)
                {
                    case Outer outer: Rebind(_outers, outer, outer.Life, actual); break;
                    case Move move: Rebind(_moves, move, move.Life, actual); break;
                    case Apply apply: Rebind(_applies, apply, apply.Life, actual); break;
                    default: throw new InvalidOperationException("Unknown Dampen registration receipt");
                }
            }
        }
        public void OnCompleted(Action continuation) { Bind(continuation); _native.OnCompleted(continuation); }
        public void UnsafeOnCompleted(Action continuation) { Bind(continuation); _native.UnsafeOnCompleted(continuation); }
    }
    private static void AwaitBound<TAwaiter, TMachine>(ref AsyncTaskMethodBuilder builder, ref TAwaiter awaiter, ref TMachine machine, object? frame)
        where TAwaiter : ICriticalNotifyCompletion where TMachine : IAsyncStateMachine
    {
        if (frame is null) { builder.AwaitUnsafeOnCompleted(ref awaiter, ref machine); return; }
        var registration = new RegistrationAwaiter<TAwaiter>(awaiter, frame);
        builder.AwaitUnsafeOnCompleted(ref registration, ref machine);
    }
    // Test-only observer; null in production. It can deterministically hold the first-ret registration window.
    internal static Action<string, object, Task>? BeforeReturnBinding = null;
    // Read the actual suspended-box builder before EVERY MoveNext ret. Never authorize a child through ambient lookup on resume.
    private static void ReturnOuter(ref AsyncTaskMethodBuilder builder, Outer? frame)
    { if (frame is not null) lock (Sync) Rebind(_outers, frame, frame.Life, builder.Task); }
    private static void ReturnMove(ref AsyncTaskMethodBuilder builder, Move? frame)
    { if (frame is not null) { var actual = builder.Task; BeforeReturnBinding?.Invoke("Move", frame, actual); lock (Sync) Rebind(_moves, frame, frame.Life, actual); } }
    private static void ReturnApply(ref AsyncTaskMethodBuilder builder, Apply? frame)
    { if (frame is not null) lock (Sync) Rebind(_applies, frame, frame.Life, builder.Task); }
    public static object Audit()
    {
        lock (Sync) return new { epoch = Epoch, outer = _outers.Count(), moves = _moves.Count(), applies = _applies.Count(), powerSlots = ActivePowers.Count };
    }
    public static void Reset()
    {
        lock (Sync) { Interlocked.Increment(ref _epoch); ActivePowers.Clear(); }
        // Keep weak original-task tombstones until completion: Reset does not cancel default native waits.
        // Discard only strong current-power indexing, never erase a known stale task into 'untracked'.
    }

    private enum Site { Outer, Move, Apply, Pair }
    private static Dictionary<MethodBase, Site> Sites = new();
    public sealed record IlSite(string Method, string Kind, int SourceCalls, int SuccessCloses, int FailureCloses, int EntryBindings, int ReturnBindings, int AwaitRegistrations, string PatchType);
    private static MethodInfo Handler(string name) => AccessTools.DeclaredMethod(typeof(DomainDampenTransactions), name) ?? throw new MissingMethodException(name);
    private static MethodInfo Method(Type type, string name, params Type[] args) => AccessTools.DeclaredMethod(type, name, args) ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo Machine(MethodInfo method) => AccessTools.DeclaredMethod(method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Native async state machine missing: " + method), "MoveNext");
    private static FieldInfo Field(Type type, string name, Type expected)
    { var field = AccessTools.Field(type, name); if (field is null || field.FieldType != expected) throw new InvalidOperationException("Native field changed: " + name); return field; }
    private static int Unique(IReadOnlyList<CodeInstruction> code, MethodInfo method)
    { var found = code.Select((x, i) => (x, i)).Where(p => p.x.Calls(method)).ToArray(); if (found.Length != 1) throw new InvalidOperationException("Expected one exact native call: " + method); return found[0].i; }
    private static void MoveLabels(CodeInstruction from, CodeInstruction to)
    { if (from.blocks.Count != 0) throw new InvalidOperationException("Unsupported exception boundary at anchor"); to.labels.AddRange(from.labels); from.labels.Clear(); }
    private static List<CodeInstruction> Load(FieldInfo field, bool address = false) => [new(OpCodes.Ldarg_0), new(address ? OpCodes.Ldflda : OpCodes.Ldfld, field)];
    private static void ReplaceCall(List<CodeInstruction> code, MethodInfo original, string handler, IEnumerable<CodeInstruction> extra)
    {
        int index = Unique(code, original); var inserted = extra.ToList();
        if (inserted.Count != 0) { MoveLabels(code[index], inserted[0]); code.InsertRange(index, inserted); index += inserted.Count; }
        code[index].opcode = OpCodes.Call; code[index].operand = Handler(handler);
    }
    private static void CloseAnchors(List<CodeInstruction> code, LocalBuilder frame, string close)
    {
        foreach (var target in new[] { Method(typeof(AsyncTaskMethodBuilder), "SetResult"), Method(typeof(AsyncTaskMethodBuilder), "SetException", typeof(Exception)) })
        {
            int i = Unique(code, target); var load = new CodeInstruction(OpCodes.Ldloc, frame);
            MoveLabels(code[i], load); code.InsertRange(i, new[] { load, new CodeInstruction(OpCodes.Call, Handler(close)) });
        }
    }
    private static void FrameAnchors(List<CodeInstruction> code, FieldInfo state, FieldInfo builder, FieldInfo source,
        LocalBuilder frame, string enter, string leave, params FieldInfo[] rest)
    {
        int registrations = 0;
        for (int i = code.Count - 1; i >= 0; i--)
        {
            if (code[i].operand is not MethodInfo call || call.DeclaringType != typeof(AsyncTaskMethodBuilder) || !call.Name.StartsWith("Await")) continue;
            if (call.Name != "AwaitUnsafeOnCompleted" || !call.IsGenericMethod) throw new InvalidOperationException("Native await registration drifted");
            var args = call.GetGenericArguments(); var awaiter = args[0];
            if (awaiter != typeof(TaskAwaiter) && (!awaiter.IsGenericType || awaiter.GetGenericTypeDefinition() != typeof(TaskAwaiter<>)))
                throw new InvalidOperationException("Only pinned native TaskAwaiter registrations are supported");
            var load = new CodeInstruction(OpCodes.Ldloc, frame); MoveLabels(code[i], load); code.Insert(i, load);
            code[i + 1].opcode = OpCodes.Call; code[i + 1].operand = Handler(nameof(AwaitBound)).MakeGenericMethod(args); registrations++;
        }
        if (registrations == 0) throw new InvalidOperationException("Native MoveNext lost await registrations");
        if (!code.Any(c => c.opcode == OpCodes.Ret)) throw new InvalidOperationException("Native MoveNext lost its ret anchor");
        for (int i = code.Count - 1; i >= 0; i--)
        {
            if (code[i].opcode != OpCodes.Ret) continue;
            var last = Load(builder, true); last.Add(new(OpCodes.Ldloc, frame)); last.Add(new(OpCodes.Call, Handler(leave)));
            MoveLabels(code[i], last[0]); code.InsertRange(i, last);
        }
        var first = Load(state); first.AddRange(Load(builder, true)); first.AddRange(Load(source));
        foreach (var field in rest) first.AddRange(Load(field));
        first.Add(new(OpCodes.Call, Handler(enter))); first.Add(new(OpCodes.Stloc, frame)); code.InsertRange(0, first);
    }
    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var code = input.Select(c => new CodeInstruction(c)).ToList();
        var kind = Sites[__originalMethod];
        if (kind == Site.Pair)
        {
            if (code.Count < 3 || code[^1].opcode != OpCodes.Ret ||
                !code[^2].Calls(AccessTools.PropertyGetter(typeof(Task), nameof(Task.CompletedTask))) ||
                !code[^3].Calls(AccessTools.Method(typeof(PowerModel), "Flash")))
                throw new InvalidOperationException("Native Dampen no longer has its synchronous Flash/CompletedTask tail");
            var add = Method(typeof(Dictionary<CardModel, int>), "Add", typeof(CardModel), typeof(int));
            var downgrade = Method(typeof(CardCmd), "Downgrade", typeof(CardModel));
            int i = Unique(code, add), d = Unique(code, downgrade);
            if (i < 6 || d != i + 2 || code[i - 6].opcode != OpCodes.Ldarg_0 ||
                code[i - 5].operand is not MethodInfo getter || getter.Name != "GetInternalData" || getter.DeclaringType != typeof(PowerModel) ||
                code[i - 4].opcode != OpCodes.Ldfld || code[i - 4].operand is not FieldInfo field ||
                field.Name != "downgradedCardsToOldUpgradeLevels" || field.FieldType != typeof(Dictionary<CardModel, int>) ||
                field.DeclaringType?.DeclaringType != typeof(DampenPower) || !getter.GetGenericArguments().SequenceEqual(new[] { field.DeclaringType }) ||
                code[i + 1].opcode != OpCodes.Ldloc_2 || code[i - 3].opcode != OpCodes.Ldloc_2 ||
                code[i - 2].opcode != OpCodes.Ldloc_2 || !code[i - 1].Calls(AccessTools.PropertyGetter(typeof(CardModel), "CurrentUpgradeLevel")) ||
                code[i + 1].labels.Count != 0 || code[d].labels.Count != 0 || code[i + 1].blocks.Count != 0 || code[d].blocks.Count != 0 ||
                __originalMethod.GetMethodBody()!.LocalVariables[2].LocalType != typeof(CardModel))
                throw new InvalidOperationException("Native Dampen ledger/downgrade pair changed");
            var token = generator.DeclareLocal(typeof(Invocation));
            code.RemoveRange(i + 1, 2);
            var load = new CodeInstruction(OpCodes.Ldloc, token); MoveLabels(code[i], load); code.Insert(i, load);
            code[i + 1].opcode = OpCodes.Call; code[i + 1].operand = Handler(nameof(CommitPair));
            code.InsertRange(0, new CodeInstruction[] { new(OpCodes.Ldarg_0), new(OpCodes.Ldarg_1), new(OpCodes.Ldarg_2),
                new(OpCodes.Call, Handler(nameof(BeginInvocation))), new(OpCodes.Stloc, token) });
            return code;
        }
        var sm = __originalMethod.DeclaringType!;
        var builder = Field(sm, "<>t__builder", typeof(AsyncTaskMethodBuilder));
        var state = Field(sm, "<>1__state", typeof(int));
        if (kind == Site.Outer)
        {
            var source = Field(sm, "<>4__this", typeof(MonsterModel)); var combat = Field(sm, "<combatState>5__2", typeof(ICombatState));
            var frame = generator.DeclareLocal(typeof(Outer));
            var extra = Load(source); extra.AddRange(Load(combat)); extra.AddRange(Load(builder, true)); extra.Add(new(OpCodes.Ldloca, frame));
            ReplaceCall(code, Method(typeof(MoveState), "PerformMove", typeof(IEnumerable<Creature>)), nameof(PerformFromMagi), extra);
            CloseAnchors(code, frame, nameof(CloseOuter));
            FrameAnchors(code, state, builder, source, frame, nameof(EnterOuter), nameof(ReturnOuter));
        }
        else if (kind == Site.Move)
        {
            var source = Field(sm, "<>4__this", typeof(MagiKnight)); var frame = generator.DeclareLocal(typeof(Move));
            var extra = Load(source); extra.Add(new(OpCodes.Ldloc, frame));
            ReplaceCall(code, NativeApply(), nameof(ApplyFromMagi), extra);
            CloseAnchors(code, frame, nameof(CloseMove));
            FrameAnchors(code, state, builder, source, frame, nameof(EnterMove), nameof(ReturnMove));
        }
        else
        {
            var power = Field(sm, "power", typeof(PowerModel)); var frame = generator.DeclareLocal(typeof(Apply));
            ReplaceCall(code, Method(typeof(PowerModel), "AfterApplied", typeof(Creature), typeof(CardModel)), nameof(AfterAppliedFromTask), new[] { new CodeInstruction(OpCodes.Ldloc, frame) });
            CloseAnchors(code, frame, nameof(CloseApply));
            FrameAnchors(code, state, builder, power, frame, nameof(EnterApply), nameof(ReturnApply),
                Field(sm, "target", typeof(Creature)), Field(sm, "applier", typeof(Creature)), Field(sm, "cardSource", typeof(CardModel)));
        }
        return code;
    }
    private static MethodInfo NativeApply() => Method(typeof(PowerCmd), "Apply", typeof(PlayerChoiceContext), typeof(PowerModel),
        typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool));
    public static IReadOnlyList<IlSite> VerifyNativeIl()
    {
        var prepared = new Dictionary<MethodBase, Site>();
        prepared.Add(Machine(Method(typeof(MonsterModel), "PerformMove")), Site.Outer);
        prepared.Add(Machine(NativeMagi), Site.Move);
        prepared.Add(Machine(NativeApply()), Site.Apply);
        var after = Method(typeof(DampenPower), "AfterApplied", typeof(Creature), typeof(CardModel));
        if (after.GetCustomAttribute<AsyncStateMachineAttribute>() is not null) throw new InvalidOperationException("Dampen became async");
        prepared.Add(after, Site.Pair);
        _ = Method(typeof(CombatManager), "Reset", typeof(bool));
        Sites = prepared; // Publish only a complete target map, never a transient cleared map.
        var result = new List<IlSite>();
        foreach (var (method, kind) in Sites)
        {
            var code = PatchProcessor.GetOriginalInstructions(method, out var generator);
            var emitted = Rewrite(code, generator, method).ToArray();
            bool AwaiterField(CodeInstruction c) => c.operand is FieldInfo f && (f.FieldType == typeof(TaskAwaiter) ||
                (f.FieldType.IsGenericType && f.FieldType.GetGenericTypeDefinition() == typeof(TaskAwaiter<>)));
            if (!code.Where(c => c.operand is MethodInfo m && m.Name == "GetResult").Select(c => (c.opcode, c.operand))
                    .SequenceEqual(emitted.Where(c => c.operand is MethodInfo m && m.Name == "GetResult").Select(c => (c.opcode, c.operand))) ||
                !code.Where(AwaiterField).Select(c => (c.opcode, c.operand)).SequenceEqual(emitted.Where(AwaiterField).Select(c => (c.opcode, c.operand))))
                throw new InvalidOperationException("Original stored native awaiter/GetResult instructions changed");
            int registrations = code.Count(c => c.operand is MethodInfo m && m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == "AwaitUnsafeOnCompleted");
            if (emitted.Count(c => c.operand is MethodInfo m && m.IsGenericMethod && m.GetGenericMethodDefinition() == Handler(nameof(AwaitBound))) != registrations)
                throw new InvalidOperationException("Native registration bridge count differs");
            result.Add(new(method.DeclaringType!.FullName + "." + method.Name, kind.ToString(), 1, kind == Site.Pair ? 0 : 1,
                kind == Site.Pair ? 0 : 1, 1, kind == Site.Pair ? 0 : code.Count(c => c.opcode == OpCodes.Ret),
                code.Count(c => c.operand is MethodInfo m && m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == "AwaitUnsafeOnCompleted"), "Transpiler"));
        }
        result.Add(new(typeof(CombatManager).FullName + ".Reset(System.Boolean)", "Reset", 0, 0, 0, 0, 0, 0, "Prefix"));
        return result;
    }
    public sealed record PatchTarget(string Method, string PatchType, string[] PrefixOwners, string[] TranspilerOwners);
    public static IReadOnlyList<PatchTarget> InstalledPatchTargets()
    {
        var reset = Method(typeof(CombatManager), "Reset", typeof(bool));
        var expected = Sites.Keys.Append(reset).ToHashSet();
        var actual = Harmony.GetAllPatchedMethods().Where(m => Harmony.GetPatchInfo(m)!.Owners.Contains(HarmonyId)).ToHashSet();
        if (!actual.SetEquals(expected)) throw new InvalidOperationException("Dampen exact five native patch targets differ");
        return expected.Select(method =>
        {
            var info = Harmony.GetPatchInfo(method)!; bool isReset = method == reset;
            if (info.Prefixes.Count(p => p.owner == HarmonyId) != (isReset ? 1 : 0) ||
                info.Transpilers.Count(p => p.owner == HarmonyId) != (isReset ? 0 : 1) ||
                info.Postfixes.Any(p => p.owner == HarmonyId) || info.Finalizers.Any(p => p.owner == HarmonyId))
                throw new InvalidOperationException("Dampen patch kind/owner mismatch");
            return new PatchTarget(method.DeclaringType!.FullName + "." + method.Name + (isReset ? "(System.Boolean)" : ""),
                isReset ? "Prefix" : "Transpiler", info.Prefixes.Select(p => p.owner).ToArray(), info.Transpilers.Select(p => p.owner).ToArray());
        }).ToArray();
    }
    internal static Action<Exception>? InstallFailureObserved = null;
    public static void Install()
    {
        lock (Sync)
        {
            if (_installed) return;
            VerifyNativeIl(); var harmony = new Harmony(HarmonyId);
            try
            {
                foreach (var method in Sites.Keys) harmony.Patch(method, transpiler: new HarmonyMethod(Handler(nameof(Rewrite)))
                { priority = Priority.Last, after = ["Volibear.DomainPassiveEffects", "Volibear.DomainCardContributions", "Volibear.DomainRevivalEffects"] });
                harmony.Patch(Method(typeof(CombatManager), "Reset", typeof(bool)), prefix: new HarmonyMethod(Handler(nameof(Reset))));
                _installed = true;
            }
            catch (Exception error)
            {
                try { InstallFailureObserved?.Invoke(error); } catch (Exception observer) { error.Data["DampenInstallObserverFailure"] = observer; }
                try { harmony.UnpatchAll(HarmonyId); } catch (Exception cleanup) { error.Data["DampenRollbackFailure"] = cleanup; }
                Reset(); throw;
            }
        }
    }
}
