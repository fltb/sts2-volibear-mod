using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;

namespace Volibear.Core;

public static partial class DomainEnemyStatusContributions
{
    private sealed record WitherContribution(ICombatState Combat, Creature Receiver, int Generation, decimal Damage);
    private static ConditionalWeakTable<CardModel, WitherContribution> _witherContributions = new();

    private static void InstallWitherContributions(Harmony harmony)
    {
        harmony.Patch(MoveNext(Required(typeof(Aeonglass), "IncreasingIntensityMove")),
            transpiler: Handler(nameof(WitherMoveContributions)));
        harmony.Patch(Required(typeof(Aeonglass), nameof(Aeonglass.MatchWitherToUpgradeCount)),
            transpiler: Handler(nameof(WitherMatchContributions)));
        // This is the real clone primitive used by native combat clones. Copy only
        // our finite status receipts, not arbitrary fields or a generic lineage graph.
        harmony.Patch(Required(typeof(AbstractModel), nameof(AbstractModel.MutableClone)),
            postfix: Handler(nameof(CopyStatusReceipts)));
    }

    private static IEnumerable<CodeInstruction> WitherMoveContributions(IEnumerable<CodeInstruction> instructions,
        MethodBase __originalMethod)
    {
        var source = __originalMethod.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Single(field => field.Name == "<>4__this" && field.FieldType == typeof(Aeonglass));
        var upgrade = Required(typeof(Wither), nameof(Wither.FakeUpgrade));
        var counter = AccessTools.PropertySetter(typeof(Aeonglass), nameof(Aeonglass.WitherUpgradeCount))!;
        int upgrades = 0, counters = 0;
        foreach (var instruction in instructions)
        {
            if (instruction.Calls(upgrade))
            {
                upgrades++;
                var load = new CodeInstruction(OpCodes.Ldarg_0);
                load.labels.AddRange(instruction.labels); load.blocks.AddRange(instruction.blocks);
                yield return load;
                yield return new CodeInstruction(OpCodes.Ldfld, source);
                yield return new CodeInstruction(OpCodes.Call, Required(typeof(DomainEnemyStatusContributions), nameof(EnemyWitherUpgrade)));
            }
            else if (instruction.Calls(counter))
            {
                counters++;
                instruction.opcode = OpCodes.Call;
                instruction.operand = Required(typeof(DomainEnemyStatusContributions), nameof(SetWitherUpgradeCount));
                yield return instruction;
            }
            else yield return instruction;
        }
        if (upgrades != 1 || counters != 1)
            throw new InvalidOperationException($"Aeonglass Wither move drift: upgrade={upgrades}, counter={counters}");
    }

    private static IEnumerable<CodeInstruction> WitherMatchContributions(IEnumerable<CodeInstruction> instructions)
    {
        var upgrade = Required(typeof(Wither), nameof(Wither.FakeUpgrade));
        int matched = 0;
        foreach (var instruction in instructions)
        {
            if (!instruction.Calls(upgrade)) { yield return instruction; continue; }
            matched++;
            var load = new CodeInstruction(OpCodes.Ldarg_0);
            load.labels.AddRange(instruction.labels); load.blocks.AddRange(instruction.blocks);
            yield return load;
            yield return new CodeInstruction(OpCodes.Call, Required(typeof(DomainEnemyStatusContributions), nameof(EnemyWitherUpgrade)));
        }
        if (matched != 1) throw new InvalidOperationException($"Aeonglass Wither matching drift: {matched}");
    }

    private static void SetWitherUpgradeCount(Aeonglass source, int value)
    {
        // Single-player contract. A canceled hostile upgrade is consumed now; it
        // must not be banked and applied to future Withers after domain expires.
        if (value > source.WitherUpgradeCount && source.Creature.IsEnemy &&
            source.Creature.CombatState?.Players.Any(player => DomainPower.IsActive(player.Creature)) == true) return;
        source.WitherUpgradeCount = value;
    }

    private static void EnemyWitherUpgrade(Wither card, Aeonglass source)
    {
        // Tooltip Withers have no owner/combat; keep their native informational path.
        var receiver = card.Owner?.Creature;
        if (receiver is null || !EnemySource(source, receiver, out _)) { card.FakeUpgrade(); return; }
        if (DomainPower.IsActive(receiver) || BeastForms.IsConverted(card)) return;
        decimal before = card.DynamicVars.Damage.BaseValue;
        card.FakeUpgrade();
        decimal added = card.DynamicVars.Damage.BaseValue - before;
        if (added <= 0m) return;
        var combat = receiver.CombatState!;
        decimal prior = _witherContributions.TryGetValue(card, out var old) && old.Generation == _generation &&
            ReferenceEquals(old.Combat, combat) && ReferenceEquals(old.Receiver, receiver) ? old.Damage : 0m;
        _witherContributions.Remove(card);
        _witherContributions.Add(card, new WitherContribution(combat, receiver, _generation, prior + added));
    }

    private static decimal WitherDamageWithoutEnemyContribution(CardModel card, Creature receiver, decimal original)
    {
        if (card is not Wither || BeastForms.IsConverted(card) || !DomainPower.IsActive(receiver) ||
            !_witherContributions.TryGetValue(card, out var contribution) || contribution.Generation != _generation ||
            !ReferenceEquals(contribution.Combat, receiver.CombatState) || !ReferenceEquals(contribution.Receiver, receiver))
            return original;
        // A player-created Wither keeps its own damage; only the observed enemy
        // FakeUpgrade increments are removed while domain is active.
        return Math.Max(0m, original - contribution.Damage);
    }

    private static void CopyStatusReceipts(AbstractModel __instance, AbstractModel __result)
    {
        if (__instance is not CardModel original || __result is not CardModel clone) return;
        if (_origins.TryGetValue(original, out var origin) && origin.Generation == _generation)
        { _origins.Remove(clone); _origins.Add(clone, origin); }
        if (_witherContributions.TryGetValue(original, out var contribution) && contribution.Generation == _generation)
        { _witherContributions.Remove(clone); _witherContributions.Add(clone, contribution); }
    }
}
