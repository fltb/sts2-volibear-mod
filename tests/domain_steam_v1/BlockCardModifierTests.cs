using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

internal static class BlockCardModifierTests
{
    internal static void Run()
    {
        const BindingFlags flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
        var checks = 0;
        void Need(bool condition, string message) { checks++; if (!condition) throw new InvalidOperationException(message); }
        // Native identity fixtures only: run actual modifier bodies, not a combat/world simulation.
        var target = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        var foreign = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        T Power<T>(int amount) where T : PowerModel
        {
            var p = (T)RuntimeHelpers.GetUninitializedObject(typeof(T));
            typeof(AbstractModel).GetProperty("IsMutable", flags)!.SetValue(p, true);
            typeof(PowerModel).GetProperty("Owner", flags)!.SetValue(p, target);
            typeof(PowerModel).GetField("_amount", flags)!.SetValue(p, amount);
            return p;
        }
        var dexterity = Power<DexterityPower>(3);
        var frail = Power<FrailPower>(1);
        foreach (var (type, baseBlock, upgradedBlock) in new[]
        {
            (typeof(Volibear_B02), 5m, 8m), (typeof(Volibear_B04), 10m, 13m)
        })
        {
            var card = (CardModel)RuntimeHelpers.GetUninitializedObject(type);
            typeof(AbstractModel).GetProperty("IsMutable", flags)!.SetValue(card, true);
            for (var face = 0; face < 2; face++)
            {
                if (face == 1) type.GetMethod("OnUpgrade", flags)!.Invoke(card, null);
                var block = card.DynamicVars.Block;
                Need(block.BaseValue == (face == 0 ? baseBlock : upgradedBlock), type.Name + " independent printed block");
                Need(block.Props == ValueProp.Move, type.Name + " powered card block metadata");
                Need(dexterity.ModifyBlockAdditive(target, block.BaseValue, block.Props, null, null) == 3m, "actual native Dexterity applies");
                Need(frail.ModifyBlockMultiplicative(target, block.BaseValue, block.Props, null, null) == .75m, "actual native Frail applies");
                Need(dexterity.ModifyBlockAdditive(foreign, block.BaseValue, block.Props, null, null) == 0m, "no foreign Dexterity");
            }
            var onPlay = type.GetMethod("OnPlay", flags)!;
            var body = onPlay.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType.GetMethod("MoveNext", flags)!;
            var instructions = PatchProcessor.GetOriginalInstructions(body).ToArray();
            var move = typeof(VolibearCard).GetMethod("get_Move", flags)!;
            Need(instructions.Count(i => i.Calls(move)) == 1, type.Name + " actual OnPlay passes Move to native block command");
        }
        Need(dexterity.ModifyBlockAdditive(target, 5m, (ValueProp)0, null, null) == 0m, "native zero-props regression reproduces lost Dexterity");
        Need(frail.ModifyBlockMultiplicative(target, 5m, (ValueProp)0, null, null) == 1m, "native zero-props regression reproduces lost Frail");
        Need(dexterity.ModifyBlockAdditive(target, 5m, ValueProp.Move | ValueProp.Unpowered, null, null) == 0m, "explicit unpowered remains exempt");
        Console.WriteLine($"BLOCK_CARD_NATIVE_MODIFIERS_PASS checks={checks} actual-metadata-upgrade-native-modifiers=true native-gameplay=NOT_RUN");
    }
}
