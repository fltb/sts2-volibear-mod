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
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;

namespace Volibear.Core;

public static partial class DomainSummonEffects
{
    // These four native callers discard the Add result. Replacing only that call
    // keeps LivingFog's following attack, rat counters and HasSummoned facts.
    private static void RewriteAdditionalBirth(List<CodeInstruction> code, LocalBuilder frame, int kind)
    {
        Type child = kind switch
        {
            6 => typeof(GasBomb), 7 => typeof(TwoTailedRat),
            8 => typeof(EyeWithTeeth), 9 => typeof(Parafright),
            _ => throw new InvalidOperationException("Unknown finite summon source.")
        };
        var native = typeof(CreatureCmd).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(m => m.Name == nameof(CreatureCmd.Add) && m.IsGenericMethodDefinition &&
                m.GetParameters().Select(p => p.ParameterType).SequenceEqual([typeof(ICombatState), typeof(string)]))
            .MakeGenericMethod(child);
        int add = Unique(code, native);
        int result = code.Select((instruction, index) => (instruction, index)).Single(x =>
            x.instruction.operand is MethodInfo method && method.DeclaringType == typeof(TaskAwaiter<Creature>) &&
            method.Name == "GetResult").index;
        Require(add < result && result + 1 < code.Count && code[result + 1].opcode == OpCodes.Pop,
            "Additional summon caller no longer discards its child result.");
        var load = new CodeInstruction(OpCodes.Ldloc, frame);
        Transfer(code[add], load);
        code.Insert(add, load);
        code[add + 1].opcode = OpCodes.Call;
        code[add + 1].operand = Handler(nameof(AdditionalBirth)).MakeGenericMethod(child);
    }

    private static Task<Creature> AdditionalBirth<T>(ICombatState combat, string? slot, Frame frame) where T : MonsterModel
    {
        // The shared actual-task registration supplies sticky cancellation and
        // generation retirement. Native Add commits membership before its first
        // await: once forwarded, its child and native initialization stay intact.
        if (CancelAtGate(frame, "AdditionalBirth.pre-create"))
            return Task.FromResult<Creature>(null!); // Verified discarded by all four callers above.
        return CreatureCmd.Add<T>(combat, slot);
    }
}
