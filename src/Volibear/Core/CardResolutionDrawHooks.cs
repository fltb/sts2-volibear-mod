using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

public static partial class CardResolutionHooks
{
    private sealed class DrawRequest(PlayerChoiceContext choices, Player player, Func<CardModel, Task> observer)
    {
        internal readonly PlayerChoiceContext Choices = choices;
        internal readonly Player Player = player;
        internal readonly Func<CardModel, Task> Observer = observer;
        internal bool Claimed;
    }

    private sealed class DrawScope(DrawRequest request, long generation)
    {
        internal readonly DrawRequest Request = request;
        internal readonly long Generation = generation;
        internal bool Closed;
    }

    private sealed class DrawMoveFrame(DrawScope? scope, DrawScope? previous, Task native,
        Player player, bool fromHandDraw)
    {
        internal readonly Player Player = player;
        internal readonly bool FromHandDraw = fromHandDraw;
        internal readonly DrawScope? Scope = scope;
        internal readonly DrawScope? Previous = previous;
        internal readonly Task Native = native;
    }

    private static readonly AsyncLocal<DrawRequest?> PendingObservedDraw = new();
    private static readonly AsyncLocal<DrawScope?> CurrentDraw = new();
    private static ConditionalWeakTable<Task, DrawScope> _drawTasks = new();
    private static long _drawGeneration;

    /// <summary>
    /// Native draw with an awaited observer after each direct hand Add and before
    /// that card's draw hooks. Only this exact native invocation claims the observer;
    /// nested/replacement draws have no observer unless explicitly requested anew.
    /// This delegates all counts, hand limits, shuffle and draw prevention to native Draw.
    /// </summary>
    public static Task<IEnumerable<CardModel>> DrawObserved(PlayerChoiceContext context, decimal count,
        Player player, Func<CardModel, Task> observer)
    {
        ArgumentNullException.ThrowIfNull(observer);
        Install();
        var previous = PendingObservedDraw.Value;
        var request = new DrawRequest(context, player, observer);
        PendingObservedDraw.Value = request;
        try
        {
            var native = CardPileCmd.Draw(context, count, player, fromHandDraw: false);
            if (!request.Claimed)
                throw new InvalidOperationException("Observed draw did not enter its native state machine.");
            return native;
        }
        finally { PendingObservedDraw.Value = previous; }
    }

    private static IEnumerable<CodeInstruction> DrawMoveLifecycle(IEnumerable<CodeInstruction> instructions,
        ILGenerator generator, MethodBase original)
    {
        var fields = original.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        var builderType = typeof(AsyncTaskMethodBuilder<IEnumerable<CardModel>>);
        var builder = fields.Single(field => field.FieldType == builderType);
        var player = fields.Single(field => field.FieldType == typeof(Player) && field.Name == "player");
        var choices = fields.Single(field => field.FieldType == typeof(PlayerChoiceContext) && field.Name == "choiceContext");
        var state = fields.Single(field => field.FieldType == typeof(int) && field.Name == "<>1__state");
        var fromHandDraw = fields.Single(field => field.FieldType == typeof(bool) && field.Name == "fromHandDraw");
        var taskGetter = AccessTools.PropertyGetter(builderType, "Task");
        var setResult = Required(builderType, "SetResult", typeof(IEnumerable<CardModel>));
        var frame = generator.DeclareLocal(typeof(DrawMoveFrame));
        var code = instructions.ToList();
        if (code.Count(instruction => Equals(instruction.operand, setResult)) != 1)
            throw new InvalidOperationException("Expected one native Draw successful completion boundary.");
        if (!code.Any(instruction => instruction.opcode == OpCodes.Ret))
            throw new InvalidOperationException("Native draw state machine has no return boundary.");
        var patched = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, taskGetter),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, player),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, choices),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, fromHandDraw),
            new(OpCodes.Call, Required(typeof(CardResolutionHooks), nameof(EnterDrawMove),
                typeof(Task), typeof(Player), typeof(PlayerChoiceContext), typeof(int), typeof(bool))), new(OpCodes.Stloc, frame)
        };
        foreach (var instruction in code)
        {
            if (Equals(instruction.operand, setResult))
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                load.labels.AddRange(instruction.labels);
                load.blocks.AddRange(instruction.blocks);
                instruction.labels.Clear();
                instruction.blocks.Clear();
                patched.Add(load);
                patched.Add(new CodeInstruction(OpCodes.Call,
                    Required(typeof(CardResolutionHooks), nameof(CompleteDrawMove), typeof(DrawMoveFrame))));
            }
            if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                load.labels.AddRange(instruction.labels);
                load.blocks.AddRange(instruction.blocks);
                instruction.labels.Clear();
                instruction.blocks.Clear();
                patched.Add(load);
                patched.Add(new CodeInstruction(OpCodes.Ldarg_0));
                patched.Add(new CodeInstruction(OpCodes.Ldflda, builder));
                patched.Add(new CodeInstruction(OpCodes.Call, taskGetter));
                patched.Add(new CodeInstruction(OpCodes.Call,
                    Required(typeof(CardResolutionHooks), nameof(LeaveDrawMove), typeof(DrawMoveFrame), typeof(Task))));
            }
            patched.Add(instruction);
        }
        return patched;
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static DrawMoveFrame EnterDrawMove(Task native, Player player, PlayerChoiceContext choices,
        int nativeState, bool fromHandDraw)
    {
        var previous = CurrentDraw.Value;
        if (!_drawTasks.TryGetValue(native, out var scope) && nativeState == -1)
        {
            var pending = PendingObservedDraw.Value;
            if (pending is { Claimed: false } && ReferenceEquals(pending.Player, player) &&
                ReferenceEquals(pending.Choices, choices))
            {
                pending.Claimed = true;
                scope = new DrawScope(pending, _drawGeneration);
                _drawTasks.Add(native, scope);
            }
        }
        // Unobserved nested Draw MUST clear the inherited observer for its own body.
        CurrentDraw.Value = scope;
        return new DrawMoveFrame(scope, previous, native, player, fromHandDraw);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void CompleteDrawMove(DrawMoveFrame frame)
    {
        // Close BEFORE SetResult can synchronously resume the caller or next draw.
        if (frame.Scope is not { } scope) return;
        scope.Closed = true;
        _drawTasks.Remove(frame.Native);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void LeaveDrawMove(DrawMoveFrame frame, Task currentNative)
    {
        if (frame.Scope is { } scope)
        {
            if (!ReferenceEquals(frame.Native, currentNative))
            {
                _drawTasks.Remove(frame.Native);
                if (_drawTasks.TryGetValue(currentNative, out var existing))
                {
                    if (!ReferenceEquals(existing, scope))
                        throw new InvalidOperationException("Native Draw Task belongs to another observed request.");
                }
                else if (!scope.Closed && scope.Generation == _drawGeneration) _drawTasks.Add(currentNative, scope);
            }
            if (currentNative.IsCompleted)
            {
                scope.Closed = true;
                _drawTasks.Remove(currentNative);
            }
        }
        CurrentDraw.Value = frame.Previous;
    }

    private static void ResetObservedDraws()
    {
        _drawGeneration++;
        _drawTasks = new ConditionalWeakTable<Task, DrawScope>();
        PendingObservedDraw.Value = null;
        CurrentDraw.Value = null;
    }
}
