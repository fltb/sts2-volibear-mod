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
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

internal sealed record PowerAudioReceipt(long Transaction, ICombatState Combat, Creature Owner,
    PowerModel Power, CardModel? CardSource, Creature? Applier, string Cue);

/// <summary>Exact native MoveNext frame observation. Builder Task is read again on exit
/// because the first suspension can replace its original promise. Completion closes the
/// frame BEFORE SetResult/SetException can execute a caller continuation. No gameplay Task
/// is wrapped/replaced/awaited, and nested commands never inherit an outer source ticket.</summary>
internal static partial class PowerAudioReceipts
{
    private sealed class Ticket(PowerModel power, Creature? owner, CardModel? card, Creature? applier, bool silent)
    {
        internal readonly long Id = Interlocked.Increment(ref sequence);
        internal readonly PowerModel Power = power;
        internal readonly Creature? Owner = owner;
        internal readonly ICombatState? Combat = owner?.CombatState;
        internal readonly CardModel? Card = card;
        internal readonly Creature? Applier = applier;
        internal readonly bool Silent = silent;
        internal readonly AudioCommitGate Gate = new();
        internal bool Invalid;
        internal bool PresentationCommitted;
    }
    private sealed class Frame(Ticket? ticket, Frame? previous)
    {
        internal readonly Ticket? Ticket = ticket;
        internal readonly Frame? Previous = previous;
        internal bool Closed;
        internal bool AtCommit;
    }
    private static readonly AsyncLocal<Frame?> Current = new();
    private static readonly ConditionalWeakTable<Task, Ticket> Tickets = new();
    private static long sequence;
    private static bool installed;

    internal static void Install()
    {
        if (installed) return;
        var h = new Harmony("Volibear.Presentation.PowerAudioReceipts");
        try
        {
            foreach (var method in NativeBodies())
                h.Patch(method, transpiler: new(typeof(PowerAudioReceipts), nameof(CommandBody)));
            InstallPresentationCommits(h);
            installed = true;
        }
        catch { h.UnpatchAll(h.Id); throw; }
    }
    private static IEnumerable<MethodInfo> NativeBodies()
    {
        var apply = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Apply),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)])!;
        var modify = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)])!;
        return new[] { apply, modify }.Select(m => AccessTools.Method(m.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Native power command lost its state machine"), "MoveNext"));
    }
    private static Frame? AliveParent(Frame? frame)
    { while (frame?.Closed == true) frame = frame.Previous; return frame; }
    private static Frame Enter(Task native, int state, PowerModel power, Creature? target, CardModel? card, Creature? applier, bool silent)
    {
        Ticket? ticket = null;
        try
        {
            if (state == -1 && (Cue(power) is not null || TracksPresentation(power, card)))
            {
                ticket = new(power, target ?? (power.IsMutable ? power.Owner : null), card, applier, silent);
                var bound = Tickets.GetValue(native, _ => ticket);
                if (!ReferenceEquals(bound, ticket)) { bound.Invalid = true; ticket.Invalid = true; ticket = null; }
            }
            else if (state >= 0) Tickets.TryGetValue(native, out ticket);
            if (ticket?.Invalid == true) ticket = null;
        }
        catch { ticket = null; }
        // Even unknown/resumed-unbound commands hide any outer ticket.
        var frame = new Frame(ticket, AliveParent(Current.Value));
        Current.Value = frame;
        return frame;
    }
    private static void BeginCommit(Frame frame) => frame.AtCommit = true;
    private static void EndCommit(Frame frame) => frame.AtCommit = false;
    private static void Close(Frame frame)
    {
        frame.AtCommit = false;
        frame.Closed = true;
        if (ReferenceEquals(Current.Value, frame)) Current.Value = AliveParent(frame.Previous);
    }
    private static void Leave(Frame frame, Task actual, int state)
    {
        try
        {
            if (state >= 0 && frame.Ticket is { } ticket)
            {
                var bound = Tickets.GetValue(actual, _ => ticket); // Actual post-suspension builder task.
                if (!ReferenceEquals(bound, ticket)) { bound.Invalid = true; ticket.Invalid = true; }
            }
        }
        catch { /* Unknown continuation means no cue, not borrowed attribution. */ }
        finally { Close(frame); }
    }
    internal static PowerAudioReceipt? Applied(PowerModel power) => Capture(power, power.Amount, false);
    internal static PowerAudioReceipt? Increased(PowerModel power, int change, bool silent) => Capture(power, change, silent);
    private static PowerAudioReceipt? Capture(PowerModel power, int delta, bool silent)
    {
        try
        {
            var frame = Current.Value;
            var ticket = frame is { Closed: false, AtCommit: true } ? frame.Ticket : null;
            if (ticket is not { Invalid: false, Owner: { } owner } || Cue(power) is not { } cue || owner.CombatState is not { } combat ||
                !ReferenceEquals(ticket.Combat, combat) || !owner.IsAlive || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsOverOrEnding) return null;
            if (!ticket.Gate.TryCommit(ReferenceEquals(ticket.Power, power) && ReferenceEquals(owner, power.Owner),
                owner.Powers.Contains(power), delta > 0, power.Amount > 0, silent || ticket.Silent)) return null;
            return new(ticket.Id, combat, owner, power, ticket.Card, ticket.Applier, cue);
        }
        catch { return null; }
    }
    private static string? Cue(PowerModel power) => power switch
    {
        StandingPower => "armor_retain", ImmovableBodyPower => "armor_iron",
        PendingCostPower or EndlessHuntPower => "cost_reduce", StrengthPower => "strength", _ => null
    };
    private static MethodInfo Handler(string name) => AccessTools.Method(typeof(PowerAudioReceipts), name);
    private static FieldInfo Field(Type type, string name, Type expected)
    {
        var field = AccessTools.Field(type, name);
        if (field is null || field.FieldType != expected) throw new InvalidOperationException("Native power frame field drift: " + name);
        return field;
    }
    [HarmonyPriority(Priority.Last)]
    [HarmonyAfter("Volibear.DomainPassiveEffects")]
    [HarmonyBefore("Volibear.DomainCardContributions")]
    private static IEnumerable<CodeInstruction> CommandBody(IEnumerable<CodeInstruction> instructions, ILGenerator generator, MethodBase __originalMethod)
    {
        var sm = __originalMethod.DeclaringType!;
        var code = instructions.Select(c => new CodeInstruction(c)).ToList();
        var builder = AccessTools.Field(sm, "<>t__builder") ?? throw new MissingFieldException("builder");
        var builderType = builder.FieldType;
        bool applying = builderType == typeof(AsyncTaskMethodBuilder);
        if (!applying && builderType != typeof(AsyncTaskMethodBuilder<int>)) throw new InvalidOperationException("Native power builder drift");
        var getTask = AccessTools.PropertyGetter(builderType, "Task");
        var state = Field(sm, "<>1__state", typeof(int));
        var power = Field(sm, "power", typeof(PowerModel));
        var card = Field(sm, "cardSource", typeof(CardModel));
        var applier = Field(sm, "applier", typeof(Creature));
        var silent = Field(sm, "silent", typeof(bool));
        var target = applying ? Field(sm, "target", typeof(Creature)) : null;
        bool Completion(CodeInstruction c) => c.operand is MethodInfo m && m.DeclaringType == builderType && m.Name is "SetResult" or "SetException";
        if (code.Count(c => Completion(c) && ((MethodInfo)c.operand).Name == "SetResult") != 1 ||
            code.Count(c => Completion(c) && ((MethodInfo)c.operand).Name == "SetException") != 1 || !code.Any(c => c.opcode == OpCodes.Ret))
            throw new InvalidOperationException("Native completion boundaries drifted");
        var commit = applying ? AccessTools.Method(typeof(PowerModel), nameof(PowerModel.ApplyInternal))
            : AccessTools.Method(typeof(PowerModel), nameof(PowerModel.SetAmount));
        if (code.Count(c => c.Calls(commit)) != 1) throw new InvalidOperationException("Native power mutation boundary drifted");
        var frame = generator.DeclareLocal(typeof(Frame));
        var result = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, getTask),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, power)
        };
        if (target is null) result.Add(new(OpCodes.Ldnull));
        else result.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, target)]);
        result.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, card), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, applier),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, silent), new(OpCodes.Call, Handler(nameof(Enter))), new(OpCodes.Stloc, frame)]);
        foreach (var instruction in code)
        {
            if (instruction.Calls(commit))
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                if (instruction.blocks.Count != 0) throw new InvalidOperationException("Unexpected commit EH boundary");
                result.AddRange([load, new(OpCodes.Call, Handler(nameof(BeginCommit))), instruction,
                    new(OpCodes.Ldloc, frame), new(OpCodes.Call, Handler(nameof(EndCommit)))]);
                continue;
            }
            if (Completion(instruction) || instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                if (instruction.blocks.Count != 0) throw new InvalidOperationException("Unexpected completion EH boundary");
                result.Add(load);
                if (instruction.opcode == OpCodes.Ret)
                    result.AddRange([new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, getTask),
                        new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Call, Handler(nameof(Leave)))]);
                else result.Add(new(OpCodes.Call, Handler(nameof(Close))));
            }
            result.Add(instruction);
        }
        return result;
    }
}
