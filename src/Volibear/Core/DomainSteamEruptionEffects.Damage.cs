using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.ValueProps;

#if STS2_BETA
using AttackTarget = MegaCrit.Sts2.Core.Entities.Creatures.DamageTargetData;
#else
using AttackTarget = MegaCrit.Sts2.Core.Entities.Creatures.Creature;
#endif

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    internal static readonly MethodInfo NativeDamage = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
        [typeof(PlayerChoiceContext), typeof(IEnumerable<AttackTarget>), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)
#if STS2_BETA
            , typeof(CardPlay), typeof(ModifyDamageHookType)
#endif
            ]);
    // Last rewrite candidate is exposed to managed emission fixtures only. Reports
    // use the tracker so failed Harmony recomposition cannot publish this candidate.
    private static PatchCompatibilitySnapshot.CapabilityRecord? _damageBindingCapability;
    private static readonly PatchCapabilityTracker<PatchCompatibilitySnapshot.CapabilityRecord> DamageBindingCapabilities = new();
    internal static PatchCompatibilitySnapshot.CapabilityRecord DamageBindingCapability
    {
        get
        {
            var original = Async(AccessTools.Method(typeof(AttackCommand), nameof(AttackCommand.Execute)));
            return DamageBindingCapabilities.TryRead(original, Own(nameof(AttackMachine)), out var capability) ? capability :
                new("steam_explosion_damage_attribution", "unknown", original.FullDescription(),
                    "The attack adapter is absent or no capability assessment is confirmed for its currently committed Harmony patch chain.",
                    "Whether mid-hit Steam Eruption damage suppression is available cannot be confirmed.");
        }
    }

    private static async Task<AttackCommand> ExplodeAttack(AttackCommand command, PlayerChoiceContext? choice, WaterfallGiant monster)
    {
        var episode = CurrentEpisode(Flow.Explode, monster);
        if (episode is null) return await command.Execute(choice);
        if (!ReferenceEquals(command.Attacker, episode.Owner)) throw new InvalidOperationException("Steam attack owner mismatch.");
        Attacks.Remove(command); Attacks.Add(command, episode); episode.Commands.Add(command);
        if (!Allow(episode)) { PublishSteamCancellation(episode); Observed?.Invoke(episode.Owner, "explosion-not-started-cancelled"); return command; }
        return await command.Execute(choice);
    }
    private static bool CompleteStaleAttack(AttackCommand command, ref int state, ref AsyncTaskMethodBuilder<AttackCommand> builder)
    {
        if (state != -1 || !Attacks.TryGetValue(command, out var episode) || Allow(episode)) return false;
        PublishSteamCancellation(episode);
        state = -2; builder.SetResult(command); return true;
    }
    private static Task<IEnumerable<DamageResult>> DamageFromCommand(PlayerChoiceContext choice, IEnumerable<AttackTarget> targets,
        decimal amount, ValueProp props, Creature? dealer, CardModel? card,
#if STS2_BETA
        CardPlay? cardPlay, ModifyDamageHookType hookType,
#endif
        AttackCommand command)
    {
        var episode = CurrentEpisode(Flow.Attack, command);
        // This dispatcher is installed only while the exact native call remains.
        // Ordinary-segment completion is independently composed into its awaiter.
        // The ticket covers native dispatch only, never foreign before/after hooks.
        return DispatchNativeDamage(choice, targets, amount, props, dealer, card,
#if STS2_BETA
            cardPlay, hookType,
#endif
            command, episode);
    }
    private static Task<IEnumerable<DamageResult>> DispatchNativeDamage(PlayerChoiceContext choice, IEnumerable<AttackTarget> targets,
        decimal amount, ValueProp props, Creature? dealer, CardModel? card,
#if STS2_BETA
        CardPlay? cardPlay, ModifyDamageHookType hookType,
#endif
        AttackCommand command, Episode? episode)
    {
        using var binding = DamageHandoff.Dispatch(episode is null ? null : new DamageInvocation(episode, command));
        return CreatureCmd.Damage(choice, targets, amount, props, dealer, card
#if STS2_BETA
            , cardPlay, hookType
#endif
            );
    }
    private static DamageInvocation? CurrentDamage => ActiveFrame is { Flow: Flow.Damage, Closed: false } frame ? frame.Damage : null;
    private static decimal GateDamage(DamageInvocation? invocation, Creature receiver, decimal amount)
    {
        if (invocation is null || receiver.Side == invocation.Episode.Owner.Side || amount <= 0) return amount;
        var episode = invocation.Episode;
        // A known stale command is not an untagged ordinary attack.
        if (!IsCurrent(episode) || !ReferenceEquals(receiver.CombatState, episode.Combat)) return 0;
        _ = Allow(episode);
        var gated = episode.Decision.GatePositiveDamage(amount, sourceMatched: true, harmsOpposingSide: true);
        if (gated < amount) PublishSteamCancellation(episode);
        return gated;
    }
    private static void PublishSteamCancellation(Episode episode)
    {
        try
        {
            if (IsCurrent(episode) && episode.Decision.Cancelled)
                Volibear.Presentation.PowerPresentationDomain.Once(episode, episode.Owner, episode.Source, sourceCombat: episode.Combat);
        }
        catch { }
    }
    private static decimal BlockCommit(Creature receiver, decimal amount, ValueProp props)
    {
        var invocation = CurrentDamage;
        if (invocation is not null) invocation.TargetOrdinal++;
        var before = receiver.Block;
        var actual = receiver.DamageBlockInternal(GateDamage(invocation, receiver, amount), props);
        invocation?.Episode.Decision.RecordNativeWrite(new object(), "block:" + invocation.TargetOrdinal, receiver, before, receiver.Block);
        if (invocation is not null) Observed?.Invoke(invocation.Episode.Owner, "block-committed");
        return actual; // Preserve the native blockedDamage return and every already-consumed block point.
    }
    private static DamageResult HpCommit(Creature receiver, decimal amount, ValueProp props, string part)
    {
        var invocation = CurrentDamage;
        var before = receiver.CurrentHp;
        var committedAmount = GateDamage(invocation, receiver, amount);
        ObserveLethalWrite(receiver, receiver.IsAlive && committedAmount >= receiver.CurrentHp);
        var actual = receiver.LoseHpInternal(committedAmount, props);
        invocation?.Episode.Decision.RecordNativeWrite(new object(), part + ":" + invocation.TargetOrdinal, receiver, before, receiver.CurrentHp);
        if (invocation is not null) Observed?.Invoke(invocation.Episode.Owner, part + "-committed");
        return actual; // Do not change the caller's raw unblockedDamage or WasFullyBlocked calculation.
    }
#if STS2_BETA
    private static DamageResult PreBlockHp(Creature receiver, decimal amount, ValueProp props) => HpCommit(receiver, amount, props, "pre-block-hp");
#endif
    private static DamageResult PrimaryHp(Creature receiver, decimal amount, ValueProp props) => HpCommit(receiver, amount, props, "primary-hp");
    private static DamageResult OverflowHp(Creature receiver, decimal amount, ValueProp props) => HpCommit(receiver, amount, props, "overflow-hp");
    private static async Task ObserveBoundary(Task native, string point)
    {
        await native;
        if (CurrentDamage is not { } invocation || Boundary is null) return;
        // Probe-only observers open Domain at a labelled native hook-completion boundary.
        // Their injected wait is not represented as a naturally yielding game hook.
        foreach (Func<Creature, string, Task> observer in Boundary.GetInvocationList())
            await observer(invocation.Episode.Owner, point);
    }
    private static IEnumerable<CodeInstruction> AttackMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var subject = Subject(__originalMethod.DeclaringType!, Flow.Attack);
        var code = input.Select(instruction => new CodeInstruction(instruction)).ToList();
        // Run after ordinary extensions. If another adapter owns the awaited hit,
        // leave it intact: an ambient ticket around an unknown async wrapper would
        // misattribute damage emitted by its before-hit listeners to Steam.
        var exact = NativeCallCapability.CanBindExactCall(code, NativeDamage, out var reason);
        var body = exact ? Replace(code, NativeDamage, nameof(DamageFromCommand), subject: subject) : code;
        body = Scope(body, generator, __originalMethod, Flow.Attack);
        var result = EarlyEntry(body, generator, __originalMethod, subject, nameof(CompleteStaleAttack)).ToArray();
        var capability = new PatchCompatibilitySnapshot.CapabilityRecord("steam_explosion_damage_attribution", exact ? "available" : "unavailable",
            __originalMethod.FullDescription(), reason,
            exact ? "None. Exact mid-hit Steam Eruption damage suppression remains installed." :
                "Mid-hit positive damage suppression for Steam Eruption is unavailable for this attack dispatch. " +
                "Ordinary-segment Domain lightning and responders, pre-attack cancellation, and the remaining Steam lifecycle protections remain installed.");
        _damageBindingCapability = capability;
        DamageBindingCapabilities.Observe(__originalMethod, capability);
        return result;
    }
    private static IEnumerable<CodeInstruction> DamageMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var block = AccessTools.Method(typeof(Creature), nameof(Creature.DamageBlockInternal));
        var hp = AccessTools.Method(typeof(Creature), nameof(Creature.LoseHpInternal));
        var result = new List<CodeInstruction>(); var blocks = 0; var hps = 0;
        var beforeDamage = 0; var beforeOsty = 0; var afterOsty = 0; var afterHp = 0;
        foreach (var instruction in input)
        {
            string? point = null;
            if (instruction.Calls(block)) { instruction.opcode = OpCodes.Call; instruction.operand = Own(nameof(BlockCommit)); blocks++; }
            else if (instruction.Calls(hp))
            {
                hps++;
                instruction.opcode = OpCodes.Call;
#if STS2_BETA
                instruction.operand = Own(hps switch { 1 when blocks == 0 => nameof(PreBlockHp), 2 when blocks == 1 => nameof(PrimaryHp),
                    3 when blocks == 1 => nameof(OverflowHp), _ => throw new InvalidOperationException("Unexpected damage write order") });
#else
                instruction.operand = Own(hps == 1 ? nameof(PrimaryHp) : nameof(OverflowHp));
#endif
            }
            else if (instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.BeforeDamageReceived))))
            { point = "before-block"; beforeDamage++; }
            else if (instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.AfterModifyingHpLostBeforeOsty))))
            { point = "after-block-before-primary-modifiers"; beforeOsty++; }
            else if (instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.AfterModifyingHpLostAfterOsty))))
                point = ++afterOsty == 1 ? "before-primary-hp" : "before-overflow-hp";
            else if (instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.AfterCurrentHpChanged))))
            { point = "after-hp-hooks"; afterHp++; }
            result.Add(instruction);
            if (point is not null)
            { result.Add(new(OpCodes.Ldstr, point)); result.Add(new(OpCodes.Call, Own(nameof(ObserveBoundary)))); }
        }
        #if STS2_BETA
        const int hpSites = 3;
#else
        const int hpSites = 2;
#endif
        if (blocks != 1 || hps != hpSites || beforeDamage != 1 || beforeOsty != 1 || afterOsty != 2 || afterHp != 1)
            throw new InvalidOperationException($"Steam native damage shape drift {blocks}/{hps}/{beforeDamage}/{beforeOsty}/{afterOsty}/{afterHp}, expected 1/{hpSites}/1/1/2/1.");
        return Scope(result, generator, __originalMethod, Flow.Damage);
    }
    private static IEnumerable<CodeInstruction> EarlyEntry(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase original, FieldInfo subject, string guard)
    {
        var machine = original.DeclaringType!;
        var state = Field(machine, field => field.FieldType == typeof(int) && field.Name.Contains("__state", StringComparison.Ordinal));
        var builder = Field(machine, field => field.FieldType == typeof(AsyncTaskMethodBuilder) ||
            field.FieldType.IsGenericType && field.FieldType.GetGenericTypeDefinition() == typeof(AsyncTaskMethodBuilder<>));
        var run = generator.DefineLabel(); var boundary = new CodeInstruction(OpCodes.Nop); boundary.labels.Add(run);
        var result = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, subject), new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, state),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, Own(guard)),
            new(OpCodes.Brfalse, run), new(OpCodes.Ret), boundary,
        };
        result.AddRange(input); return result;
    }
}
