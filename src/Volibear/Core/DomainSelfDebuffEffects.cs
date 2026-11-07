using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

/// <summary>
/// Personal debuffs are muted independently of application provenance. Native powers,
/// amounts, counters and expiry remain present; only detrimental contributions are gated.
/// This also covers player-applied Knowledge Demon choices and restored combat state.
/// </summary>
public static class DomainSelfDebuffEffects
{
    public static bool IsSuppressed(PowerModel power) => power is not (ShriekPower or PlowPower) &&
        power.Owner is { IsPlayer: true } owner && power.GetTypeForAmount(power.Amount) == PowerType.Debuff &&
        DomainEnemyEffects.ProtectsPlayer(owner);

    private static MethodInfo Own(string name) => AccessTools.DeclaredMethod(typeof(DomainSelfDebuffEffects), name)
        ?? throw new MissingMethodException(name);
    private static MethodInfo Native(Type type, string name) => AccessTools.DeclaredMethod(type, name)
        ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo Machine(Type type, string name) => Native(
        Native(type, name).GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException("Expected native async method: " + type.Name + "." + name), "MoveNext");

    internal static void Install(Harmony harmony)
    {
        foreach (var name in new[] { nameof(Hook.ModifyEnergyGain), nameof(Hook.ModifyHandDraw),
            nameof(Hook.ModifyMaxEnergy), nameof(Hook.ShouldDraw), nameof(Hook.ModifyOrbValue),
            nameof(Hook.ModifyCardPlayCount), "ModifyDamageInternal" })
            harmony.Patch(Native(typeof(Hook), name), transpiler: new HarmonyMethod(Own(nameof(Dispatch))));

        // These exact callbacks contain only the recurring penalty. Their separate
        // removal/turn counters remain native. Mixed damage+expiry bodies are below.
        foreach (var (type, name) in new (Type, string)[] {
            (typeof(NeurosurgePower), nameof(NeurosurgePower.AfterSideTurnStart)),
            (typeof(WraithFormPower), nameof(WraithFormPower.AfterSideTurnStart)),
            (typeof(BiasedCognitionPower), nameof(BiasedCognitionPower.AfterSideTurnStart)),
            (typeof(ImbalancedPower), nameof(ImbalancedPower.AfterDamageGiven)),
            (typeof(SicEmPower), nameof(SicEmPower.AfterDamageGiven)) })
            harmony.Patch(Native(type, name), prefix: new HarmonyMethod(Own(nameof(Penalty))));

        foreach (var (type, name) in new (Type, string)[] {
            (typeof(PoisonPower), nameof(PoisonPower.AfterSideTurnStart)),
            (typeof(MagicBombPower), nameof(MagicBombPower.AfterSideTurnEnd)),
            (typeof(DisintegrationPower), nameof(DisintegrationPower.AfterSideTurnEndLate)),
            (typeof(DemisePower), nameof(DemisePower.AfterSideTurnEnd)),
            (typeof(StranglePower), nameof(StranglePower.AfterCardPlayed)) })
            harmony.Patch(Machine(type, name), transpiler: new HarmonyMethod(Own(nameof(DamageBody))));
        harmony.Patch(Machine(typeof(OblivionPower), nameof(OblivionPower.AfterCardPlayed)),
            transpiler: new HarmonyMethod(Own(nameof(OblivionBody))));
        harmony.Patch(Machine(typeof(TheGambitPower), nameof(TheGambitPower.AfterDamageReceived)),
            transpiler: new HarmonyMethod(Own(nameof(KillBody))));
        // Filtering the collection avoids JIT-inlining dependence on IsOwnerDoomed.
        harmony.Patch(Native(typeof(DoomPower), nameof(DoomPower.GetDoomedCreatures)),
            postfix: new HarmonyMethod(Own(nameof(Doomed))));
        harmony.Patch(Machine(typeof(DoomPower), nameof(DoomPower.BeforeSideTurnEnd)),
            transpiler: new HarmonyMethod(Own(nameof(DoomBody))));
        harmony.Patch(Native(typeof(ShrinkPower), nameof(ShrinkPower.AfterApplied)),
            postfix: new HarmonyMethod(Own(nameof(ShrinkApplied))));
        DomainDampenRestoration.Install(harmony);
        DomainConfusedCosts.Install(harmony);
    }

    private static void ShrinkApplied(ShrinkPower __instance)
    {
        if (IsSuppressed(__instance)) Scale(__instance.Owner, 1f);
    }
    private static void Scale(Creature owner, float scale) =>
        MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom.Instance?.GetCreatureNode(owner)?.ScaleTo(scale, 0.25);
    public static void RefreshScales(Creature domainOwner)
    {
        if (domainOwner.CombatState is not { } combat) return;
        foreach (var player in combat.Players)
            if (player.Creature.GetPower<ShrinkPower>() is { } shrink)
                Scale(player.Creature, IsSuppressed(shrink) ? 1f : 0.5f);
    }

    private static bool Penalty(PowerModel __instance, ref Task __result)
    {
        if (!IsSuppressed(__instance)) return true;
        __result = Task.CompletedTask;
        return false;
    }

    private static IEnumerable<CodeInstruction> Dispatch(IEnumerable<CodeInstruction> input)
    {
        int count = 0;
        foreach (var old in input)
        {
            var code = new CodeInstruction(old);
            if (code.operand is MethodInfo method && method.DeclaringType == typeof(AbstractModel))
            {
                string? wrapper = method.Name switch {
                    nameof(AbstractModel.ModifyEnergyGain) => nameof(Energy),
                    nameof(AbstractModel.ModifyHandDraw) => nameof(DrawCount),
                    nameof(AbstractModel.ModifyMaxEnergy) => nameof(MaxEnergy),
                    nameof(AbstractModel.ShouldDraw) => nameof(DrawAllowed),
                    nameof(AbstractModel.ModifyOrbValue) => nameof(OrbValue),
                    nameof(AbstractModel.ModifyCardPlayCount) => nameof(PlayCount),
                    nameof(AbstractModel.ModifyDamageAdditive) => nameof(DamageAdditive),
                    _ => null };
                if (wrapper is not null) { code.opcode = OpCodes.Call; code.operand = Own(wrapper); count++; }
            }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Self debuff dispatch callsite drift: " + count);
    }
    private static bool Muted(AbstractModel model) => model is PowerModel power && IsSuppressed(power);
    internal static decimal RestoreMissingFocus(DomainPower domain, OrbModel orb, decimal amount)
    {
        var owner = orb.Owner.Creature;
        if (owner.GetPower<FocusPower>() is not null || !DomainEnemyEffects.ProtectsPlayer(owner) ||
            domain.Owner.CombatState is not { } combat ||
            !ReferenceEquals(combat.Players.FirstOrDefault(p => DomainPower.IsActive(p.Creature))?.Creature.GetPower<DomainPower>(), domain)) return amount;
        return amount + owner.Powers.OfType<TemporaryFocusPower>().Where(p => p.Type == PowerType.Debuff).Sum(p => Math.Max(0, p.Amount));
    }
    private static decimal OrbValue(AbstractModel model, OrbModel orb, decimal amount)
    {
        if (model is FocusPower focus && ReferenceEquals(focus.Owner.Player, orb.Owner) && DomainEnemyEffects.ProtectsPlayer(focus.Owner))
        {
            int debt = focus.Owner.Powers.OfType<TemporaryFocusPower>().Where(p => p.Type == PowerType.Debuff).Sum(p => Math.Max(0, p.Amount));
            return Math.Max(0m, amount + Math.Max(0, focus.Amount + debt));
        }
        return Muted(model) ? amount : model.ModifyOrbValue(orb, amount);
    }
    private static int PlayCount(AbstractModel model, CardModel card, Creature? target, int count) => Muted(model) ? count : model.ModifyCardPlayCount(card, target, count);
    private static decimal Energy(AbstractModel model, Player player, decimal amount) => Muted(model) ? amount : model.ModifyEnergyGain(player, amount);
    private static decimal DrawCount(AbstractModel model, Player player, decimal amount) => Muted(model) ? amount : model.ModifyHandDraw(player, amount);
    private static decimal MaxEnergy(AbstractModel model, Player player, decimal amount) => Muted(model) ? amount : model.ModifyMaxEnergy(player, amount);
    private static bool DrawAllowed(AbstractModel model, Player player, bool fromHandDraw) => Muted(model) || model.ShouldDraw(player, fromHandDraw);
    private static decimal DamageAdditive(AbstractModel model, Creature? target, decimal amount, ValueProp props, Creature? dealer, CardModel? card
#if STS2_BETA
        , CardPlay? play
#endif
        ) =>
        model is not StrengthPower && Muted(model) ? 0m : model.ModifyDamageAdditive(target, amount, props, dealer, card
#if STS2_BETA
            , play
#endif
            );

    private static MethodInfo DamageMethod => AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
        [typeof(PlayerChoiceContext), typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]);
    private static IEnumerable<CodeInstruction> DamageBody(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) =>
        InjectSource(input, __originalMethod, DamageMethod, Own(nameof(Damage)));
    private static IEnumerable<CodeInstruction> OblivionBody(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) =>
        InjectSource(input, __originalMethod, typeof(PowerCmd).GetMethods().Single(m => m.Name == nameof(PowerCmd.Apply) &&
            m.IsGenericMethodDefinition && m.GetParameters().Length == 6 && m.GetParameters()[1].ParameterType == typeof(Creature))
            .MakeGenericMethod(typeof(DoomPower)), Own(nameof(ApplyDoom)));
    private static Task<DoomPower?> ApplyDoom(PlayerChoiceContext choices, Creature target, decimal amount,
        Creature? applier, CardModel? card, bool silent, PowerModel source) => IsSuppressed(source)
            ? Task.FromResult<DoomPower?>(null) : PowerCmd.Apply<DoomPower>(choices, target, amount, applier, card, silent);
    private static IEnumerable<CodeInstruction> KillBody(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) =>
        InjectSource(input, __originalMethod, AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Kill),
            [typeof(Creature), typeof(bool)]), Own(nameof(Kill)));
    private static IEnumerable<CodeInstruction> InjectSource(IEnumerable<CodeInstruction> input, MethodBase method, MethodInfo native, MethodInfo replacement)
    {
        var source = AccessTools.Field(method.DeclaringType, "<>4__this");
        if (source is null || !typeof(PowerModel).IsAssignableFrom(source.FieldType)) throw new InvalidOperationException("Debuff source field drift");
        int count = 0;
        foreach (var old in input)
        {
            var code = new CodeInstruction(old);
            if (code.Calls(native))
            {
                var load = new CodeInstruction(OpCodes.Ldarg_0);
                load.labels.AddRange(code.labels); code.labels.Clear();
                if (code.blocks.Count != 0) throw new InvalidOperationException("Debuff call exception boundary drift");
                yield return load;
                yield return new CodeInstruction(OpCodes.Ldfld, source);
                code.opcode = OpCodes.Call; code.operand = replacement; count++;
            }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Debuff exact contribution drift: " + method + ": " + count);
    }
    private static Task<IEnumerable<DamageResult>> Damage(PlayerChoiceContext choices, Creature target, decimal amount,
        ValueProp props, Creature? dealer, CardModel? card, PowerModel source) => IsSuppressed(source)
            ? Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>())
            : CreatureCmd.Damage(choices, target, amount, props, dealer, card
#if STS2_BETA
                , null
#endif
                );
    private static Task Kill(Creature target, bool force, PowerModel source) => IsSuppressed(source)
        ? Task.CompletedTask : CreatureCmd.Kill(target, force);
    private static void Doomed(ref IReadOnlyList<Creature> __result) => __result = __result
        .Where(c => c.GetPower<DoomPower>() is not { } power || !IsSuppressed(power)).ToArray();
#if STS2_BETA
    // PBE made this predicate private; reflect it instead of pinning a now-inaccessible call.
    private static readonly Func<DoomPower, bool> IsOwnerDoomedNative =
        (Func<DoomPower, bool>)AccessTools.Method(typeof(DoomPower), "IsOwnerDoomed")!
            .CreateDelegate(typeof(Func<DoomPower, bool>));
    private static bool IsDoomed(DoomPower power) => !IsSuppressed(power) && IsOwnerDoomedNative(power);
    private static readonly MethodInfo DoomPredicate = AccessTools.Method(typeof(DoomPower), "IsOwnerDoomed")!;
#else
    private static bool IsDoomed(DoomPower power) => !IsSuppressed(power) && power.IsOwnerDoomed();
    private static readonly MethodInfo DoomPredicate = Native(typeof(DoomPower), nameof(DoomPower.IsOwnerDoomed));
#endif
    private static IEnumerable<CodeInstruction> DoomBody(IEnumerable<CodeInstruction> input)
    {
        int count = 0;
        foreach (var old in input)
        {
            var code = new CodeInstruction(old);
            if (code.Calls(DoomPredicate))
            { code.opcode = OpCodes.Call; code.operand = Own(nameof(IsDoomed)); count++; }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Doom predicate callsite drift");
    }
}
