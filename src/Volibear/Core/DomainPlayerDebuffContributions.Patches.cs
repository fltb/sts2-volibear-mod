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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

public static partial class DomainPlayerDebuffContributions
{
    public static void Install()
    {
        if (installed) return;
        var harmony = new Harmony(HarmonyId);
        try
        {
            harmony.Patch(AccessTools.Method(typeof(Hook), "ModifyDamageInternal"),
                transpiler: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(DamageDispatch)));
            harmony.Patch(AccessTools.Method(typeof(Hook), nameof(Hook.ModifyBlock)),
                transpiler: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(BlockDispatch)));
            harmony.Patch(Machine(typeof(ConstrictPower), nameof(ConstrictPower.AfterSideTurnEnd)),
                transpiler: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(ConstrictContribution)));
            harmony.Patch(Machine(typeof(ChainsOfBindingPower), nameof(ChainsOfBindingPower.AfterCardDrawn)),
                transpiler: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(ChainsDrawContribution)));
            // This nontrivial concrete method is invoked virtually through the native
            // ShouldPlay dispatcher (and its existing DomainCardContributions wrapper).
            harmony.Patch(AccessTools.Method(typeof(ChainsOfBindingPower), nameof(ChainsOfBindingPower.ShouldPlay)),
                postfix: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(ChainsPlayContribution)));
            InstallNullSource(harmony);
            InstallCommitGates(harmony);
            harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]),
                prefix: new HarmonyMethod(typeof(DomainPlayerDebuffContributions), nameof(Reset)));
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            installed = true;
        }
        catch { harmony.UnpatchAll(HarmonyId); Reset(); throw; }
    }

    private static MethodInfo Own(string name) => AccessTools.Method(typeof(DomainPlayerDebuffContributions), name)
        ?? throw new MissingMethodException(nameof(DomainPlayerDebuffContributions), name);
    private static MethodInfo Machine(Type owner, string name)
    {
        var native = AccessTools.Method(owner, name) ?? throw new MissingMethodException(owner.FullName, name);
        var machine = native.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Expected native debuff state machine: " + native);
        return AccessTools.Method(machine, "MoveNext");
    }
    private static IEnumerable<CodeInstruction> Replace(IEnumerable<CodeInstruction> input, MethodInfo original,
        MethodInfo replacement, int expected)
    {
        int count = 0;
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        foreach (var instruction in code)
            if (instruction.Calls(original))
            {
                instruction.opcode = OpCodes.Call;
                instruction.operand = replacement;
                count++;
            }
        if (count != expected) throw new InvalidOperationException($"Debuff native callsite drift: {original}: {count}/{expected}");
        return code;
    }

    private static IEnumerable<CodeInstruction> DamageDispatch(IEnumerable<CodeInstruction> input) => Replace(input,
        AccessTools.Method(typeof(AbstractModel), nameof(AbstractModel.ModifyDamageMultiplicative)), Own(nameof(DamageMultiplier)), 1);
    private static IEnumerable<CodeInstruction> BlockDispatch(IEnumerable<CodeInstruction> input) => Replace(input,
        AccessTools.Method(typeof(AbstractModel), nameof(AbstractModel.ModifyBlockMultiplicative)), Own(nameof(BlockMultiplier)), 1);

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static decimal DamageMultiplier(AbstractModel model, Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? card)
    {
        if (model is PowerModel power && power is WeakPower or VulnerablePower or ShrinkPower && Suppressed(power)) return 1m;
        return model.ModifyDamageMultiplicative(target, amount, props, dealer, card);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static decimal BlockMultiplier(AbstractModel model, Creature target, decimal amount, ValueProp props,
        CardModel? card, CardPlay? play) => model is FrailPower frail && Suppressed(frail) ? 1m :
        model.ModifyBlockMultiplicative(target, amount, props, card, play);

    private static IEnumerable<CodeInstruction> ChainsDrawContribution(IEnumerable<CodeInstruction> input) => Replace(input,
        AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Amount)), Own(nameof(EffectiveAmount)), 2);
    private static void ChainsPlayContribution(ChainsOfBindingPower __instance, ref bool __result)
    {
        if (Suppressed(__instance)) __result = true;
    }

    private static IEnumerable<CodeInstruction> ConstrictContribution(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var native = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            [typeof(PlayerChoiceContext), typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]);
        var source = AccessTools.Field(__originalMethod.DeclaringType, "<>4__this");
        if (source?.FieldType != typeof(ConstrictPower)) throw new InvalidOperationException("Constrict source changed.");
        var output = new List<CodeInstruction>(); int count = 0;
        foreach (var old in input)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.Calls(native))
            {
                var load = new CodeInstruction(OpCodes.Ldarg_0);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                if (instruction.blocks.Count != 0) throw new InvalidOperationException("Unexpected Constrict EH boundary.");
                output.Add(load); output.Add(new CodeInstruction(OpCodes.Ldfld, source));
                instruction.opcode = OpCodes.Call; instruction.operand = Own(nameof(ConstrictDamage)); count++;
            }
            output.Add(instruction);
        }
        if (count != 1) throw new InvalidOperationException("Constrict damage callsite changed.");
        return output;
    }
    private static Task<IEnumerable<DamageResult>> ConstrictDamage(PlayerChoiceContext choices, Creature target,
        decimal amount, ValueProp props, Creature? dealer, CardModel? card, ConstrictPower source)
    {
        int effective = EffectiveAmount(source);
        if (Suppressed(source)) return Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>());
        // Only this exact native contribution reads the retained amount; Amount itself,
        // death-triggered removal and every unrelated damage command are untouched.
        return CreatureCmd.Damage(choices, target, effective, props, dealer, card);
    }
}
