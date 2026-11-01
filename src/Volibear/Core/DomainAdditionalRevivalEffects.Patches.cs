using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
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

public static partial class DomainAdditionalRevivalEffects
{
    private enum BodyKind { Stock, TriggerDead, Respawn, Revive, HatchMove, Hatch }
    private sealed record Invocation(Ticket Ticket, BodyKind Kind);
    private sealed record Frame(SummonLifetime<Invocation>.Binding? Binding, SummonLifetime<HatchTicket>.Binding? Hatch = null);
    private static readonly SummonLifetime<Invocation> Lifetimes = new();
    private static readonly Dictionary<MethodBase, BodyKind> Bodies = [];
    private static MethodInfo Local(string name) => AccessTools.Method(typeof(DomainAdditionalRevivalEffects), name)
        ?? throw new MissingMethodException(name);
    private static MethodInfo Native(Type type, string name, params Type[] args) => AccessTools.Method(type, name, args)
        ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo Body(MethodInfo method) => AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Native additional revival async body missing: " + method), "MoveNext");
    internal static void InstallPatches(Harmony harmony)
    {
        void Prefix(Type type, string name, string patch, params Type[] args) => harmony.Patch(Native(type, name, args), prefix: new HarmonyMethod(Local(patch)));
        Prefix(typeof(StockPower), nameof(StockPower.ShouldStopCombatFromEnding), nameof(StopEnding));
        Prefix(typeof(AdaptablePower), nameof(AdaptablePower.ShouldStopCombatFromEnding), nameof(StopEnding));
        Prefix(typeof(AdaptablePower), nameof(AdaptablePower.ShouldAllowHitting), nameof(AllowHitting), typeof(Creature));
        foreach (var type in new[] { typeof(AdaptablePower), typeof(PainfulStabsPower) })
        {
            Prefix(type, nameof(AdaptablePower.ShouldCreatureBeRemovedFromCombatAfterDeath), nameof(RemovalVote), typeof(Creature));
            Prefix(type, nameof(AdaptablePower.ShouldPowerBeRemovedAfterOwnerDeath), nameof(RemovePower));
        }
        harmony.Patch(Native(typeof(CreatureCmd), "KillWithoutCheckingWinCondition", typeof(Creature), typeof(bool), typeof(int)),
            prefix: new HarmonyMethod(Local(nameof(DeathPrefix))), postfix: new HarmonyMethod(Local(nameof(DeathPostfix))),
            finalizer: new HarmonyMethod(Local(nameof(DeathFinalizer))));
        harmony.Patch(Native(typeof(CombatManager), nameof(CombatManager.RemoveCreature), typeof(Creature)), postfix: new HarmonyMethod(Local(nameof(ManagerRemoved))));
        harmony.Patch(Native(typeof(MonsterModel), nameof(MonsterModel.PerformMove)),
            prefix: new HarmonyMethod(Local(nameof(MovePrefix))), postfix: new HarmonyMethod(Local(nameof(MovePostfix))),
            finalizer: new HarmonyMethod(Local(nameof(MoveFinalizer))));
        Prefix(typeof(CombatManager), nameof(CombatManager.Reset), nameof(Reset), typeof(bool));
        InstallDispatch(harmony);
        Bodies.Clear();
        Bodies.Add(Body(Native(typeof(StockPower), nameof(StockPower.AfterDeath), typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float))), BodyKind.Stock);
        Bodies.Add(Body(Native(typeof(TestSubject), nameof(TestSubject.TriggerDeadState))), BodyKind.TriggerDead);
        Bodies.Add(Body(Native(typeof(TestSubject), "RespawnMove", typeof(IReadOnlyList<Creature>))), BodyKind.Respawn);
        Bodies.Add(Body(Native(typeof(TestSubject), "Revive", typeof(int))), BodyKind.Revive);
        Bodies.Add(Body(Native(typeof(ToughEgg), "HatchMove", typeof(IReadOnlyList<Creature>))), BodyKind.HatchMove);
        Bodies.Add(Body(Native(typeof(ToughEgg), "Hatch")), BodyKind.Hatch);
        foreach (var body in Bodies.Keys) harmony.Patch(body, transpiler: new HarmonyMethod(Local(nameof(Rewrite))));
    }
    private static Frame Enter(Task task, int state, object source, int kind)
    {
        if (source is ToughEgg egg) return EnterHatch(task, state, egg, (BodyKind)kind);
        if (state != -1) return new(Lifetimes.Find(task, source, kind));
        var t = source is PowerModel power ? Find(power) : source is TestSubject subject ? Find(subject.Creature) : null;
        if (t is null) return new(null); // Untagged callbacks remain native, never borrow an ambient parent.
        t.CallbackDepth++;
        return new(Lifetimes.Begin(new(t, (BodyKind)kind), t.Epoch, true, source, kind));
    }
    private static void Close(Frame frame)
    {
        Lifetimes.Close(frame.Binding, invocation => invocation.Ticket.CallbackDepth--);
        HatchLifetimes.Close(frame.Hatch, ticket => Hatching.Remove(ticket));
    }
    private static void Leave(Frame frame, ref AsyncTaskMethodBuilder builder, int state)
    {
        Lifetimes.VerifyReturn(frame.Binding, ref builder, state);
        HatchLifetimes.VerifyReturn(frame.Hatch, ref builder, state);
    }
    private static ISummonRegistration? Registration(Frame frame) => (ISummonRegistration?)frame.Binding ?? frame.Hatch;
    private static bool Blocked(Frame frame)
    {
        if (frame.Binding is { Closed: true }) return true;
        if (frame.Binding?.Payload is not { } invocation) return false;
        bool blocked = Observe(invocation.Ticket);
        if (blocked && Current(invocation.Ticket) && invocation.Ticket.Cancelled)
            Volibear.Presentation.PowerPresentationDomain.Once(invocation.Ticket, invocation.Ticket.Owner, invocation.Ticket.Source, sourceCombat: invocation.Ticket.Combat);
        return blocked;
    }
    private static void QueueDead(MonsterModel monster, MoveState state, bool force, Frame frame)
    {
        if (Blocked(frame))
        {
            if (frame.Binding?.Payload?.Ticket is { } t && Current(t) && t.Source is AdaptablePower adaptable) adaptable.DoRevive();
            return;
        }
        monster.SetMoveImmediate(state, force);
    }
    private static Task<Creature> StockAdd(MonsterModel monster, ICombatState combat, CombatSide side, string? slot, Frame frame)
    {
        var t = frame.Binding?.Payload?.Ticket;
        if (t is null) return CreatureCmd.Add(monster, combat, side, slot);
        t.Creating = monster;
        try { return CreatureCmd.Add(monster, combat, side, slot); }
        finally { StockCommit(t); }
    }
    private static Task ReviveHeal(Creature owner, decimal amount, bool animation, Frame frame)
    {
        if (Blocked(frame)) return Task.CompletedTask;
        var task = CreatureCmd.Heal(owner, amount, animation);
        if (frame.Binding?.Payload?.Ticket is { } t && ReferenceEquals(owner, t.Owner) && owner.IsAlive)
        { t.Committed = true; Pending.Remove(t); }
        return task;
    }
    private static void Require(bool value, string message)
    { if (!value) throw new InvalidOperationException("Additional revival native shape: " + message); }
    private static int Unique(List<CodeInstruction> code, Func<MethodInfo, bool> predicate)
    {
        var matches = code.Select((instruction, index) => (instruction, index))
            .Where(pair => pair.instruction.operand is MethodInfo method && predicate(method)).Select(pair => pair.index).ToArray();
        Require(matches.Length == 1, "expected one call anchor, found " + matches.Length);
        return matches[0];
    }
    private static bool LoadReceiver(CodeInstruction i) => i.opcode == OpCodes.Ldloc || i.opcode == OpCodes.Ldloc_S ||
        i.opcode == OpCodes.Ldloc_0 || i.opcode == OpCodes.Ldloc_1 || i.opcode == OpCodes.Ldloc_2 || i.opcode == OpCodes.Ldloc_3 || i.opcode == OpCodes.Ldarg_0;
    private static void Transfer(CodeInstruction from, CodeInstruction to)
    { to.labels.AddRange(from.labels); from.labels.Clear(); to.blocks.AddRange(from.blocks); from.blocks.Clear(); }
    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var kind = Bodies[__originalMethod]; var machine = __originalMethod.DeclaringType!;
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        var state = AccessTools.Field(machine, "<>1__state"); var builder = AccessTools.Field(machine, "<>t__builder");
        var source = AccessTools.Field(machine, "<>4__this");
        Require(state?.FieldType == typeof(int) && builder?.FieldType == typeof(AsyncTaskMethodBuilder) &&
            source?.FieldType == (kind == BodyKind.Stock ? typeof(StockPower) : kind is BodyKind.Hatch or BodyKind.HatchMove ? typeof(ToughEgg) : typeof(TestSubject)), "machine fields");
        static MethodInfo[] Awaits(IEnumerable<CodeInstruction> stream) => stream.Where(i => i.operand is MethodInfo m &&
            m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name.StartsWith("Await", StringComparison.Ordinal)).Select(i => (MethodInfo)i.operand).ToArray();
        var pristine = Awaits(PatchProcessor.GetOriginalInstructions(__originalMethod)); var incoming = Awaits(code);
        Require(pristine.Length > 0 && incoming.Length == pristine.Length && pristine.All(m => incoming.Count(x => x == m) == pristine.Count(x => x == m)), "complete await inventory");
        int success = Unique(code, m => m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == nameof(AsyncTaskMethodBuilder.SetResult));
        Unique(code, m => m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == nameof(AsyncTaskMethodBuilder.SetException));
        int end = code.FindLastIndex(i => i.blocks.Any(b => b.blockType == ExceptionBlockType.EndExceptionBlock));
        Require(end >= 0 && end + 3 < success && code[end + 1].opcode == OpCodes.Ldarg_0 && code[end + 2].LoadsConstant(-2) &&
            code[end + 3].opcode == OpCodes.Stfld && Equals(code[end + 3].operand, state), "successful epilogue");
        if (kind is not BodyKind.HatchMove and not BodyKind.Hatch)
            Require(!code.Any(i => i.blocks.Any(b => b.blockType == ExceptionBlockType.BeginFinallyBlock)), "unexpected native finally");
        var complete = generator.DefineLabel(); code[end + 1].labels.Add(complete);
        var frame = generator.DeclareLocal(typeof(Frame)); var guards = new HashSet<int>();
        var replacements = new Dictionary<int, MethodInfo>();
        if (kind == BodyKind.Stock)
        {
            int wait = code.FindIndex(i => i.opcode == OpCodes.Ldfld && i.operand is FieldInfo f && f.Name == "deathAnimLength");
            Require(wait > 0 && code[wait - 1].opcode == OpCodes.Ldarg_0, "stock delay entry"); guards.Add(wait - 1);
            guards.Add(Unique(code, m => m.DeclaringType == typeof(ModelDb) && m.Name == nameof(ModelDb.Monster) && m.IsGenericMethod && m.GetGenericArguments().SequenceEqual(new[] { typeof(Axebot) })));
            replacements.Add(Unique(code, m => m == Native(typeof(CreatureCmd), nameof(CreatureCmd.Add), typeof(MonsterModel), typeof(ICombatState), typeof(CombatSide), typeof(string))), Local(nameof(StockAdd)));
        }
        else if (kind == BodyKind.TriggerDead)
        {
            replacements.Add(Unique(code, m => m == Native(typeof(MonsterModel), nameof(MonsterModel.SetMoveImmediate), typeof(MoveState), typeof(bool))), Local(nameof(QueueDead)));
            // No whole TriggerDeadState skip: music, TestSubjectKills and DeadTrigger are facts.
        }
        else if (kind == BodyKind.HatchMove)
        {
            replacements.Add(Unique(code, m => m == Native(typeof(PowerCmd), nameof(PowerCmd.Remove), typeof(PowerModel))), Local(nameof(HatchCleanse)));
            replacements.Add(Unique(code, m => m == Native(typeof(ToughEgg), "Hatch")), Local(nameof(HatchFromMove)));
            // HatchPower removal, IsHatched, _hatched, animation and state advance stay native.
        }
        else if (kind == BodyKind.Hatch)
            replacements.Add(Unique(code, m => m == Native(typeof(CreatureCmd), nameof(CreatureCmd.SetMaxAndCurrentHp), typeof(Creature), typeof(decimal))), Local(nameof(HatchHp)));
        else
        {
            if (kind == BodyKind.Respawn)
            {
                int increment = code.FindIndex(i => i.operand is MethodInfo m && m.DeclaringType == typeof(TestSubject) && m.Name == "get_Respawns");
                Require(increment >= 2 && LoadReceiver(code[increment - 2]) && (LoadReceiver(code[increment - 1]) || code[increment - 1].opcode == OpCodes.Dup), "respawn counter entry");
                guards.Add(increment - 2);
            }
            else
            {
                int assertion = Unique(code, m => m.Name == nameof(AbstractModel.AssertMutable));
                Require(assertion > 0 && LoadReceiver(code[assertion - 1]), "revive initial assertion"); guards.Add(assertion - 1);
                replacements.Add(Unique(code, m => m == Native(typeof(CreatureCmd), nameof(CreatureCmd.Heal), typeof(Creature), typeof(decimal), typeof(bool))), Local(nameof(ReviveHeal)));
            }
            var results = code.Select((instruction, index) => (instruction, index)).Where(p => p.instruction.operand is MethodInfo m &&
                m.DeclaringType == typeof(TaskAwaiter) && m.Name == nameof(TaskAwaiter.GetResult)).Select(p => p.index + 1).ToArray();
            Require(results.Length >= (kind == BodyKind.Respawn ? 3 : 2), "native post-await boundaries");
            foreach (var index in results) guards.Add(index); // Original GetResult always executes first.
        }
        var output = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, AccessTools.PropertyGetter(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.Task))),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, source), new(OpCodes.Ldc_I4, (int)kind),
            new(OpCodes.Call, Local(nameof(Enter))), new(OpCodes.Stloc, frame),
        };
        for (int index = 0; index < code.Count; index++)
        {
            var instruction = code[index];
            if (guards.Contains(index))
            {
                var next = generator.DefineLabel(); var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.AddRange([load, new(OpCodes.Call, Local(nameof(Blocked))), new(OpCodes.Brfalse, next), new(OpCodes.Leave, complete)]);
                instruction.labels.Add(next);
            }
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(AsyncTaskMethodBuilder) && method.Name.StartsWith("Await", StringComparison.Ordinal))
            {
                var args = method.GetGenericArguments();
                Require(method.Name == "AwaitUnsafeOnCompleted" && args.Length == 2 && args[1] == machine, "exact unsafe await registration");
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load); output.Add(load); output.Add(new(OpCodes.Call, Local(nameof(Registration))));
                instruction.opcode = OpCodes.Call; instruction.operand = AccessTools.Method(typeof(SummonRegistration), nameof(SummonRegistration.Await)).MakeGenericMethod(args);
            }
            else if (instruction.operand is MethodInfo terminal && terminal.DeclaringType == typeof(AsyncTaskMethodBuilder) && terminal.Name is "SetResult" or "SetException")
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load); output.Add(load); output.Add(new(OpCodes.Call, Local(nameof(Close))));
            }
            else if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.AddRange([load, new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Call, Local(nameof(Leave)))]);
            }
            else if (replacements.TryGetValue(index, out var replacement))
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load); output.Add(load);
                instruction.opcode = OpCodes.Call; instruction.operand = replacement;
            }
            output.Add(instruction);
        }
        return output;
    }
}
