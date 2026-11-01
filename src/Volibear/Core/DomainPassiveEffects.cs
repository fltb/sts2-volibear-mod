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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

/// <summary>Exact passive contribution callsites, rechecked at native precommit boundaries.
/// Direct benefits, existing values and source bookkeeping are never blanket-filtered.</summary>
public static class DomainPassiveEffects
{
    private const string HarmonyId = "Volibear.DomainPassiveEffects";
    private static readonly object InstallLock = new();
    private static bool _installed;
    private static int _generation;
    private static readonly AsyncLocal<Ticket?> Pending = new();
    private static ConditionalWeakTable<Task, Receipt> _tasks = new();
    private static readonly Dictionary<MethodBase, (Type Source, bool Strength, bool Async)> Sources = new();
    private static readonly Dictionary<MethodBase, int> Commands = new();

    internal sealed class Decision
    {
        internal int State { get; private set; } // 0 pending, 1 committed/allowed, 2 cancelled
        internal bool Cancelled => State == 2;
        internal bool Decide(bool cancel)
        {
            if (State == 0) State = cancel ? 2 : 1;
            return Cancelled;
        }
    }
    private sealed class Receipt(PowerModel source, Creature target, bool strength, decimal input, int generation)
    {
        internal readonly PowerModel Source = source;
        internal readonly Creature SourceOwner = source.Owner;
        internal readonly ICombatState? SourceCombat = source.Owner.CombatState;
        internal readonly Creature Target = target;
        internal readonly ICombatState? Combat = target.CombatState;
        internal readonly bool Strength = strength;
        internal readonly decimal Input = input;
        internal readonly int Generation = generation;
        internal readonly Decision Decision = new();
    }
    private sealed class Ticket(Receipt receipt) { internal readonly Receipt Receipt = receipt; internal bool Claimed; }
    private sealed record Frame(Receipt? Receipt, Task Native, int Generation);

    private static MethodInfo Required(Type owner, string name, params Type[] args) =>
        owner.GetMethod(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static,
            null, args, null) ?? throw new MissingMethodException(owner.FullName, name);
    private static MethodInfo Handler(string name) => typeof(DomainPassiveEffects).GetMethod(name,
        BindingFlags.NonPublic | BindingFlags.Static) ?? throw new MissingMethodException(name);
    private static MethodInfo MoveNext(MethodInfo native) => Required(native.GetCustomAttribute<AsyncStateMachineAttribute>()?
        .StateMachineType ?? throw new InvalidOperationException("Missing actual async state machine: " + native), "MoveNext");
    private static MethodInfo BlockNative() => Required(typeof(CreatureCmd), nameof(CreatureCmd.GainBlock),
        typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(CardPlay), typeof(bool));
    private static MethodInfo StrengthNative() => typeof(PowerCmd).GetMethods().Single(m => m.Name == nameof(PowerCmd.Apply) &&
        m.IsGenericMethodDefinition && m.GetParameters().Length == 6 && m.GetParameters()[1].ParameterType == typeof(Creature))
        .MakeGenericMethod(typeof(StrengthPower));
    private static MethodInfo ApplyNative() => Required(typeof(PowerCmd), nameof(PowerCmd.Apply), typeof(PlayerChoiceContext),
        typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool));
    private static MethodInfo ModifyNative() => Required(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount), typeof(PlayerChoiceContext),
        typeof(PowerModel), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool));

    public static void Install()
    {
        lock (InstallLock)
        {
            if (_installed) return;
            Prepare();
            var nativeReset = Required(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool));
            Require(nativeReset.ReturnType == typeof(void) && !nativeReset.IsStatic && nativeReset.DeclaringType == typeof(CombatManager),
                "Native CombatManager.Reset(bool) signature changed");
            var harmony = new Harmony(HarmonyId);
            try
            {
                foreach (var method in Sources.Keys) harmony.Patch(method, transpiler: new HarmonyMethod(Handler(nameof(SourceCalls))));
                foreach (var method in Commands.Keys) harmony.Patch(method, transpiler: new HarmonyMethod(Handler(nameof(CommandBody))));
                harmony.Patch(nativeReset, prefix: new HarmonyMethod(Handler(nameof(BeforeNativeReset))));
                CombatManager.Instance.CombatSetUp += OnCombatSetUp;
                CombatManager.Instance.CombatEnded += OnCombatEnded;
                _installed = true;
            }
            catch
            {
                foreach (var method in Sources.Keys.Concat(Commands.Keys).Append(nativeReset)) harmony.Unpatch(method, HarmonyPatchType.All, HarmonyId);
                Reset();
                throw;
            }
        }
    }
    private static void Prepare()
    {
            Sources.Clear(); Commands.Clear();
            foreach (var (source, name, strength, async, args) in new (Type, string, bool, bool, Type[])[]
            {
                (typeof(RitualPower), "AfterSideTurnEnd", true, true, [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(IEnumerable<Creature>)]),
                (typeof(SuckPower), "AfterAttack", true, true, [typeof(PlayerChoiceContext), typeof(AttackCommand)]),
                (typeof(TerritorialPower), "AfterSideTurnEnd", true, true, [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(IEnumerable<Creature>)]),
                (typeof(HighVoltagePower), "AfterSideTurnEnd", true, true, [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(IEnumerable<Creature>)]),
                (typeof(EnragePower), "AfterCardPlayed", true, true, [typeof(PlayerChoiceContext), typeof(CardPlay)]),
                (typeof(RavenousPower), "AfterDeath", true, true, [typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float)]),
                // CrabRage has TWO independent positive contributions in one native body.
                // SourceCalls wraps both while its one-shot source removal remains native.
                (typeof(CrabRagePower), "AfterDeath", true, true, [typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float)]),
                (typeof(RampartPower), "AfterSideTurnStart", false, true, [typeof(CombatSide), typeof(IReadOnlyList<Creature>), typeof(ICombatState)]),
                (typeof(PlatingPower), "BeforeSideTurnStart", false, false, [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(IReadOnlyList<Creature>), typeof(ICombatState)]),
                (typeof(PlatingPower), "BeforeSideTurnEndEarly", false, true, [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(IEnumerable<Creature>)]),
                (typeof(CurlUpPower), "AfterCardPlayed", false, true, [typeof(PlayerChoiceContext), typeof(CardPlay)]),
                (typeof(SkittishPower), "AfterAttack", false, true, [typeof(PlayerChoiceContext), typeof(AttackCommand)])
            })
            {
                var method = Required(source, name, args);
                Require(method.DeclaringType == source && method.ReturnType == typeof(Task) && !method.IsStatic && !method.IsGenericMethod,
                    "Native passive source signature changed: " + method);
                Sources.Add(async ? MoveNext(method) : method, (source, strength, async));
            }
            Commands.Add(MoveNext(BlockNative()), 0);
            Commands.Add(MoveNext(ApplyNative()), 1);
            Commands.Add(MoveNext(ModifyNative()), 2);
            // Validate source/commit IL before patching any method. No partial installation on drift.
            foreach (var method in Sources.Keys) DryRun(method, source: true);
            foreach (var method in Commands.Keys) DryRun(method, source: false);
    }
    // Run before native Reset cancels its own combat token: abandon/menu/quit need not emit CombatEnded.
    // Only our receipt generation is invalidated. Native cancellation, creature reset and cleanup remain native.
    private static void BeforeNativeReset() => Reset();
    private static void OnCombatSetUp(CombatState _) => Reset();
    private static void OnCombatEnded(CombatRoom _) => Reset();
    public static void Reset()
    {
        Interlocked.Increment(ref _generation);
        _tasks = new ConditionalWeakTable<Task, Receipt>();
        Pending.Value = null;
    }
    private static void DryRun(MethodBase method, bool source)
    {
        var gen = new DynamicMethod("PassiveValidate", typeof(void), Type.EmptyTypes, typeof(DomainPassiveEffects).Module, true).GetILGenerator();
        var code = PatchProcessor.GetOriginalInstructions(method, gen);
        _ = (source ? SourceCalls(code, method) : CommandBody(code, gen, method)).ToArray();
    }

    private static Task<decimal> PassiveBlock(Creature target, decimal amount, ValueProp props, CardPlay? card, bool fast, PowerModel source)
    {
        var receipt = new Receipt(source, target, false, amount, _generation);
        return WithTicket(receipt, () => CreatureCmd.GainBlock(target, amount, props, card, fast));
    }
    private static Task<decimal> PassiveBlockVar(Creature target, BlockVar amount, CardPlay? card, bool fast, PowerModel source)
    {
        var receipt = new Receipt(source, target, false, amount.BaseValue, _generation);
        // Keep the exact original overload and its metadata reads; only the inner
        // native numeric GainBlock transaction claims this one-shot receipt.
        return WithTicket(receipt, () => CreatureCmd.GainBlock(target, amount, card, fast));
    }
    private static Task<StrengthPower?> PassiveStrength(PlayerChoiceContext context, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, PowerModel source)
    {
        var receipt = new Receipt(source, target, true, amount, _generation);
        return StrengthResult(WithTicket(receipt, () => PowerCmd.Apply<StrengthPower>(context, target, amount, applier, card, silent)), receipt);
    }
    private static async Task<StrengthPower?> StrengthResult(Task<StrengthPower?> native, Receipt receipt)
    {
        var actual = await native;
        // Only exact unused-result source awaits reach this wrapper. Never fabricate a spawn/null Creature.
        return receipt.Decision.Cancelled ? null : actual;
    }
    private static Task<T> WithTicket<T>(Receipt receipt, Func<Task<T>> invoke)
    {
        var previous = Pending.Value;
        Pending.Value = new Ticket(receipt);
        try { return invoke(); }
        finally { Pending.Value = previous; }
    }
    private static Task<int> ForwardStack(PlayerChoiceContext context, PowerModel power, decimal offset,
        Creature? applier, CardModel? card, bool silent, Frame frame) =>
        frame.Receipt is { } receipt && receipt.Generation == _generation
            ? WithTicket(receipt, () => PowerCmd.ModifyAmount(context, power, offset, applier, card, silent))
            : PowerCmd.ModifyAmount(context, power, offset, applier, card, silent);

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Frame Enter(Task native, int nativeState, Creature? target, PowerModel? power, bool strength)
    {
        _tasks.TryGetValue(native, out var receipt);
        if (receipt is null && nativeState == -1 && Pending.Value is { Claimed: false } ticket)
        {
            var candidate = ticket.Receipt;
            if (candidate.Generation == _generation && candidate.Strength == strength &&
                ReferenceEquals(candidate.Target, target) && (!strength || power is StrengthPower))
            {
                ticket.Claimed = true; // The exact first native operation claims it, never its nested hook effects.
                receipt = candidate;
                _tasks.Add(native, receipt);
            }
        }
        return new Frame(receipt, native, _generation);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void Leave(Frame frame, Task actualNative, int nativeState)
    {
        if (frame.Generation != _generation || frame.Receipt is not { } receipt) return;
        if (!ReferenceEquals(frame.Native, actualNative))
        {
            _tasks.Remove(frame.Native);
            if (_tasks.TryGetValue(actualNative, out var bound))
            {
                if (!ReferenceEquals(bound, receipt)) throw new InvalidOperationException("Native passive task identity collision");
            }
            else _tasks.Add(actualNative, receipt);
        }
        if (nativeState == -2 || actualNative.IsCompleted) _tasks.Remove(actualNative);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool CancelAtCommit(Frame frame, Creature target, PowerModel? power, decimal contribution)
    {
        var receipt = frame.Receipt;
        if (receipt is null || receipt.Generation != _generation || frame.Generation != _generation ||
            !ReferenceEquals(receipt.Target, target) || !ReferenceEquals(receipt.Source.Owner, receipt.SourceOwner) ||
            !ReferenceEquals(receipt.Combat, target.CombatState) || !ReferenceEquals(receipt.SourceCombat, receipt.Combat) ||
            receipt.Input <= 0 || contribution <= 0 ||
            (receipt.Strength ? power is not StrengthPower || receipt.Source is not
                (RitualPower or SuckPower or TerritorialPower or HighVoltagePower or EnragePower or RavenousPower or CrabRagePower)
                : power is not null || receipt.Source is not
                (PlatingPower or CurlUpPower or SkittishPower or CrabRagePower or RampartPower))) return false;
        if (receipt.Source is RampartPower)
        {
            // Rampart is the sole cross-owner callsite: living-shield passive block
            // to a native TurretOperator teammate, never player/pet or another combat.
            if (receipt.Strength || !receipt.SourceOwner.IsEnemy || receipt.SourceOwner.IsPlayer ||
                target.Monster is not TurretOperator || !target.IsEnemy || target.IsPlayer ||
                !ReferenceEquals(receipt.SourceOwner.CombatState, receipt.Combat)) return false;
        }
        else if (!ReferenceEquals(receipt.SourceOwner, target)) return false;
        return receipt.Decision.Decide(DomainEnemyEffects.ActiveFor(target));
    }

    private static IEnumerable<CodeInstruction> SourceCalls(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var (source, strength, async) = Sources[__originalMethod];
        var code = instructions.Select(c => new CodeInstruction(c)).ToList();
        var native = strength ? StrengthNative() : BlockNative();
        int index = UniqueCall(code, native);
        if (strength)
        {
            // C# await Task<StrengthPower> must discard GetResult. Reject any source that consumes it.
            var discard = code.Select((c, i) => (c, i)).Where(x => x.c.operand is MethodInfo m && m.Name == "GetResult" &&
                m.DeclaringType == typeof(TaskAwaiter<StrengthPower>)).Select(x => x.i).Single();
            Require(code[discard + 1].opcode == OpCodes.Pop, "Strength source now consumes its result");
        }
        var load = new List<CodeInstruction> { new(OpCodes.Ldarg_0) };
        if (async) load.Add(new(OpCodes.Ldfld, Field(__originalMethod.DeclaringType!, "<>4__this", source)));
        TransferLabels(code[index], load[0]);
        code.InsertRange(index, load);
        code[index + load.Count].opcode = OpCodes.Call;
        code[index + load.Count].operand = Handler(strength ? nameof(PassiveStrength) : nameof(PassiveBlock));
        if (source == typeof(CrabRagePower))
        {
            var nativeBlock = Required(typeof(CreatureCmd), nameof(CreatureCmd.GainBlock),
                typeof(Creature), typeof(BlockVar), typeof(CardPlay), typeof(bool));
            int block = UniqueCall(code, nativeBlock);
            var sourceLoad = new List<CodeInstruction>
            {
                new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, Field(__originalMethod.DeclaringType!, "<>4__this", source))
            };
            TransferLabels(code[block], sourceLoad[0]);
            code.InsertRange(block, sourceLoad);
            code[block + sourceLoad.Count].opcode = OpCodes.Call;
            code[block + sourceLoad.Count].operand = Handler(nameof(PassiveBlockVar));
        }
        return code;
    }

    private static IEnumerable<CodeInstruction> CommandBody(IEnumerable<CodeInstruction> instructions, ILGenerator generator, MethodBase __originalMethod)
    {
        int kind = Commands[__originalMethod]; // 0 block, 1 new strength, 2 stacked strength
        var sm = __originalMethod.DeclaringType!;
        var code = instructions.Select(c => new CodeInstruction(c)).ToList();
        var builderType = kind == 0 ? typeof(AsyncTaskMethodBuilder<decimal>) : kind == 1 ? typeof(AsyncTaskMethodBuilder) : typeof(AsyncTaskMethodBuilder<int>);
        var builder = Field(sm, "<>t__builder", builderType);
        var state = Field(sm, "<>1__state", typeof(int));
        var power = kind == 0 ? null : Field(sm, "power", typeof(PowerModel));
        var target = kind == 0 ? Field(sm, "creature", typeof(Creature)) : kind == 1 ? Field(sm, "target", typeof(Creature)) : null;
        var commitTarget = target ?? Field(sm, "<owner>5__2", typeof(Creature));
        var amount = Field(sm, kind == 2 ? "<modifiedOffset>5__4" : "<modifiedAmount>5__3", typeof(decimal));
        var getTask = AccessTools.PropertyGetter(builderType, "Task");
        var frame = generator.DeclareLocal(typeof(Frame));
        var setResult = Required(builderType, "SetResult", kind == 1 ? Type.EmptyTypes : [kind == 0 ? typeof(decimal) : typeof(int)]);
        int finish = UniqueCall(code, setResult);
        if (kind != 1)
        {
            Require(code[finish - 1].opcode == OpCodes.Ldloc_1, "Native result local changed");
            Require(__originalMethod.GetMethodBody()!.LocalVariables[1].LocalType == (kind == 0 ? typeof(decimal) : typeof(int)), "Native result type changed");
        }
        int endException = code.FindLastIndex(c => c.blocks.Any(b => b.blockType == ExceptionBlockType.EndExceptionBlock));
        Require(endException >= 0 && endException < finish, "Missing native completion epilogue");
        int epilogue = endException + 1;
        Require(code[epilogue].opcode == OpCodes.Ldarg_0 && code[epilogue + 1].LoadsConstant(-2) &&
            code[epilogue + 2].opcode == OpCodes.Stfld && Equals(code[epilogue + 2].operand, state), "Native successful completion changed");
        var complete = generator.DefineLabel();
        code[epilogue].labels.Add(complete);
        int anchor;
        if (kind == 0)
        {
            int sfx = code.Select((c, i) => (c, i)).Single(x => x.c.opcode == OpCodes.Ldstr && Equals(x.c.operand, "event:/sfx/block_gain")).i;
            anchor = sfx - 5;
            Require(code[anchor].opcode == OpCodes.Ldarg_0 && Equals(code[anchor + 1].operand, amount) &&
                code[anchor + 2].opcode == OpCodes.Ldsfld && code[anchor + 3].operand is MethodInfo cmp && cmp.Name == "op_GreaterThan" &&
                (code[anchor + 4].opcode == OpCodes.Brfalse || code[anchor + 4].opcode == OpCodes.Brfalse_S) &&
                code[anchor - 1].operand is MethodInfo awaited && awaited.Name == "GetResult", "Block precommit/await anchor changed");
            Require(UniqueCall(code, Required(typeof(Creature), "GainBlockInternal", typeof(decimal))) > sfx, "Block mutation boundary changed");
        }
        else if (kind == 1)
        {
            int apply = UniqueCall(code, Required(typeof(PowerModel), "ApplyInternal", typeof(Creature), typeof(decimal), typeof(bool)));
            anchor = apply - 13;
            Require(code[anchor].opcode == OpCodes.Ldarg_0 && Equals(code[anchor + 1].operand, target) &&
                code[anchor + 2].operand is MethodInfo can && can.Name == "get_CanReceivePowers" &&
                code[anchor - 1].operand is MethodInfo awaited && awaited.Name == "GetResult", "New power precommit/await anchor changed");
        }
        else
        {
            int history = UniqueNamedCall(code, "PowerReceived");
            anchor = history - 10;
            Require(code[anchor].operand is MethodInfo instance && instance.DeclaringType == typeof(CombatManager) && instance.Name == "get_Instance" &&
                code[anchor + 1].operand is MethodInfo h && h.Name == "get_History" &&
                code[anchor - 1].opcode == OpCodes.Stfld && Equals(code[anchor - 1].operand, amount), "Stacked power prehistory anchor changed");
            Require(UniqueCall(code, Required(typeof(PowerModel), "SetAmount", typeof(int), typeof(bool))) > history, "Stack mutation/history order changed");
        }
        var allow = generator.DefineLabel();
        var guard = new List<CodeInstruction> { new(OpCodes.Ldloc, frame), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, commitTarget) };
        if (power is null) guard.Add(new(OpCodes.Ldnull));
        else { guard.Add(new(OpCodes.Ldarg_0)); guard.Add(new(OpCodes.Ldfld, power)); }
        guard.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, amount), new(OpCodes.Call, Handler(nameof(CancelAtCommit))), new(OpCodes.Brfalse, allow)]);
        if (kind == 0) guard.AddRange([new(OpCodes.Ldsfld, typeof(decimal).GetField(nameof(decimal.Zero))!), new(OpCodes.Stloc_1)]);
        if (kind == 2) guard.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, power!), new(OpCodes.Callvirt, AccessTools.PropertyGetter(typeof(PowerModel), "Amount")), new(OpCodes.Stloc_1)]);
        guard.Add(new(OpCodes.Leave, complete));
        TransferLabels(code[anchor], guard[0]);
        code[anchor].labels.Add(allow);
        code.InsertRange(anchor, guard);
        if (kind == 1)
        {
            // Exact native new-apply -> existing-instance fallback is a transfer of the SAME receipt,
            // not inheritance by arbitrary nested hooks. Other nested native calls remain unowned.
            int forward = UniqueCall(code, ModifyNative());
            var load = new CodeInstruction(OpCodes.Ldloc, frame);
            TransferLabels(code[forward], load);
            code.Insert(forward, load);
            code[forward + 1].opcode = OpCodes.Call;
            code[forward + 1].operand = Handler(nameof(ForwardStack));
        }
        var entry = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, getTask),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state)
        };
        if (target is not null) entry.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, target)]);
        else entry.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, power!), new(OpCodes.Callvirt, AccessTools.PropertyGetter(typeof(PowerModel), "Owner"))]);
        if (power is null) entry.Add(new(OpCodes.Ldnull));
        else entry.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, power)]);
        entry.AddRange([new(kind == 0 ? OpCodes.Ldc_I4_0 : OpCodes.Ldc_I4_1), new(OpCodes.Call, Handler(nameof(Enter))), new(OpCodes.Stloc, frame)]);
        foreach (var instruction in code)
        {
            if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                TransferLabels(instruction, load);
                entry.AddRange([load, new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, getTask),
                    new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Call, Handler(nameof(Leave)))]);
            }
            entry.Add(instruction);
        }
        return entry;
    }
    private static FieldInfo Field(Type owner, string name, Type type)
    {
        var field = owner.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
        Require(field is not null && field.FieldType == type, "Native state field changed: " + owner + "." + name);
        return field!;
    }
    private static int UniqueCall(List<CodeInstruction> code, MethodInfo method) =>
        code.Select((c, i) => (c, i)).Where(x => (x.c.opcode == OpCodes.Call || x.c.opcode == OpCodes.Callvirt) && Equals(x.c.operand, method))
            .Select(x => x.i).Single();
    private static int UniqueNamedCall(List<CodeInstruction> code, string name) => code.Select((c, i) => (c, i))
        .Where(x => x.c.operand is MethodInfo m && m.Name == name).Select(x => x.i).Single();
    private static void TransferLabels(CodeInstruction from, CodeInstruction to)
    {
        Require(from.blocks.Count == 0, "Unexpected EH boundary at passive insertion");
        to.labels.AddRange(from.labels); from.labels.Clear();
    }
    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
