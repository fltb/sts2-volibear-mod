using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;

namespace Volibear.Core;

/// <summary>
/// Counts the damage write points inside a native async state machine without running it.
/// A transpiler only sees its own rewrite input, so the same question has to be answered
/// once before Harmony is asked to install anything: whether this build still contains the
/// inline HP/block writes the Steam adapter gates, or has moved them elsewhere.
/// The measurement is read-only and reports exact counts so an unavailable capability can
/// quote evidence instead of a guess.
/// </summary>
internal readonly record struct NativeWriteShape(int Blocks, int Hp, int BeforeDamage, int BeforeOsty, int AfterOsty, int AfterHp)
{
    /// <summary>False only when the method definitively writes neither block nor HP inline.</summary>
    internal bool HasInlineWrites => Blocks > 0 || Hp > 0;

    /// <summary>
    /// The 0.114 layout: block and HP writes are gone from CreatureCmd.Damage while the
    /// before-damage and after-HP hooks remain, i.e. the writes moved to another method.
    /// Narrow on purpose, so an unexpected body falls through to the loud shape assertion.
    /// </summary>
    internal bool IsWriteRelocated => Blocks == 0 && Hp == 0 && BeforeDamage == 1 && AfterHp == 1;

    internal string Describe() => $"{Blocks}/{Hp}/{BeforeDamage}/{BeforeOsty}/{AfterOsty}/{AfterHp}";

    private static readonly Dictionary<ushort, OpCode> OpCodesByValue = BuildOpCodeTable();

    private static Dictionary<ushort, OpCode> BuildOpCodeTable()
    {
        var table = new Dictionary<ushort, OpCode>();
        foreach (var field in typeof(OpCodes).GetFields(BindingFlags.Public | BindingFlags.Static))
            if (field.GetValue(null) is OpCode opcode) table[(ushort)opcode.Value] = opcode;
        return table;
    }

    /// <summary>Counts calls to the native write primitives and the five damage hooks.</summary>
    internal static NativeWriteShape Measure(MethodBase moveNext)
    {
        ArgumentNullException.ThrowIfNull(moveNext);
        var body = moveNext.GetMethodBody() ?? throw new InvalidOperationException("Native state machine has no body: " + moveNext.FullDescription());
        var il = body.GetILAsByteArray() ?? throw new InvalidOperationException("Native state machine has no IL: " + moveNext.FullDescription());
        var module = moveNext.Module;
        var blocks = 0; var hp = 0; var beforeDamage = 0; var beforeOsty = 0; var afterOsty = 0; var afterHp = 0;
        var position = 0;
        while (position < il.Length)
        {
            var value = il[position];
            if (value == 0xFE)
            {
                if (position + 1 >= il.Length) break;
                value = 0;
                var two = (ushort)(0xFE00 | il[position + 1]);
                if (!OpCodesByValue.TryGetValue(two, out var wide)) throw new InvalidOperationException($"Unknown two-byte opcode 0x{two:X4} in {moveNext.FullDescription()}");
                position += 2;
                position += OperandSize(wide, il, position);
                continue;
            }
            if (!OpCodesByValue.TryGetValue(value, out var opcode)) throw new InvalidOperationException($"Unknown opcode 0x{value:X2} in {moveNext.FullDescription()}");
            position++;
            if (opcode.OperandType is OperandType.InlineMethod)
            {
                if (position + 4 > il.Length) break;
                var token = BitConverter.ToInt32(il, position);
                if (opcode == OpCodes.Call || opcode == OpCodes.Callvirt) Count(Resolve(module, token, moveNext));
                position += 4;
                continue;
            }
            position += OperandSize(opcode, il, position);
        }
        return new(blocks, hp, beforeDamage, beforeOsty, afterOsty, afterHp);

        void Count(MethodBase? method)
        {
            if (method is null) return;
            var declaring = method.DeclaringType;
            if (declaring == typeof(Creature))
            {
                if (method.Name == nameof(Creature.DamageBlockInternal)) blocks++;
                else if (method.Name == nameof(Creature.LoseHpInternal)) hp++;
                return;
            }
            if (declaring != typeof(Hook)) return;
            switch (method.Name)
            {
                case nameof(Hook.BeforeDamageReceived): beforeDamage++; break;
                case nameof(Hook.AfterModifyingHpLostBeforeOsty): beforeOsty++; break;
                case nameof(Hook.AfterModifyingHpLostAfterOsty): afterOsty++; break;
                case nameof(Hook.AfterCurrentHpChanged): afterHp++; break;
            }
        }
    }

    private static MethodBase? Resolve(Module module, int token, MethodBase caller)
    {
        try
        {
            return module.ResolveMethod(token,
                caller.DeclaringType?.GetGenericArguments(),
                caller.IsGenericMethod ? caller.GetGenericArguments() : null);
        }
        catch (Exception)
        {
            // An unresolvable token is not evidence of absence; callers treat null as noise.
            return null;
        }
    }

    private static int OperandSize(OpCode opcode, byte[] il, int position) => opcode.OperandType switch
    {
        OperandType.InlineNone => 0,
        OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar => 1,
        OperandType.InlineVar => 2,
        OperandType.InlineBrTarget or OperandType.InlineField or OperandType.InlineI or OperandType.InlineMethod
            or OperandType.InlineSig or OperandType.InlineString or OperandType.InlineTok or OperandType.InlineType
            or OperandType.ShortInlineR => 4,
        OperandType.InlineI8 or OperandType.InlineR => 8,
        OperandType.InlineSwitch => position + 4 <= il.Length ? 4 + 4 * BitConverter.ToInt32(il, position) : 0,
        _ => throw new InvalidOperationException($"Unsupported operand type {opcode.OperandType}."),
    };
}
