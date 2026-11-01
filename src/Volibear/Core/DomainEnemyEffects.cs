using System;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

/// <summary>
/// Pinned 0.107.1 enemy-benefit slice, NOT complete Domain suppression.
/// Only scalar protections, Artifact's veto, pure retaliation, and living-enemy healing.
/// No whole-Power filtering, action cancellation, resurrection or generic Apply/Add patches.
/// </summary>
public static class DomainEnemyEffects
{
    private const string HarmonyId = "Volibear.DomainEnemyEffects";
    private static readonly object InstallLock = new();
    private static bool _installed;
    private sealed record ShellWindow(ICombatState Combat, Creature Owner, int Round);
    private static readonly ConditionalWeakTable<PowerModel, ShellWindow> SuppressedShells = new();

    /// <summary>Query the current encounter's live player domains; never cache an active flag.</summary>
    public static bool ActiveFor(ICombatState? combat)
    {
        if (combat is null || !CombatManager.Instance.IsInProgress ||
            CombatManager.Instance.IsOverOrEnding ||
            !ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(), combat)) return false;
        return combat.Players.Any(player => player.Creature is { } owner &&
            owner.IsPlayer && owner.IsAlive && ReferenceEquals(owner.CombatState, combat) &&
            combat.ContainsCreature(owner) && DomainPower.IsActive(owner));
    }

    /// <summary>Enemy benefit eligibility, excluding player pets, escaped and detached creatures.</summary>
    public static bool ActiveFor(Creature? creature) => creature is not null && creature.IsEnemy &&
        !creature.IsPlayer && creature.CombatState is { } combat &&
        combat.ContainsCreature(creature) && ActiveFor(combat);

    private static bool ProtectsTarget(PowerModel power, Creature? target) =>
        target is not null && ReferenceEquals(power.Owner, target) && ActiveFor(target);

    private sealed record PatchSpec(Type Owner, string Name, Type Result, Type[] Arguments,
                                    string Callback, bool Prefix = false, bool Static = false);

    /// <summary>
    /// Resolve every exact declared method before installing anything. A renamed/moved/changed
    /// signature fails initialization instead of silently losing protection coverage.
    /// Main ModEntry owns calling this; no test-only or implicit per-card installation.
    /// </summary>
    public static void Install()
    {
        lock (InstallLock)
        {
            if (_installed) return;
            Type[] damage = [typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)];
            Type[] cap = [typeof(Creature), typeof(ValueProp), typeof(Creature), typeof(CardModel)];
            Type[] received = [typeof(PlayerChoiceContext), typeof(Creature), typeof(DamageResult), typeof(ValueProp), typeof(Creature), typeof(CardModel)];
            PatchSpec[] specs =
            [
                new(typeof(VigorPower), "ModifyDamageAdditive", typeof(decimal), damage, nameof(NeutralEnemyAttackBonus)),
                new(typeof(SurroundedPower), "ModifyDamageMultiplicative", typeof(decimal), damage, nameof(NeutralBackAttackBonus)),
                new(typeof(BurrowedPower), "ShouldClearBlock", typeof(bool), [typeof(Creature)], nameof(AllowBlockClear)),
                new(typeof(FlutterPower), "ModifyDamageMultiplicative", typeof(decimal), damage, nameof(NeutralMultiplier)),
                new(typeof(SoarPower), "ModifyDamageMultiplicative", typeof(decimal), damage, nameof(NeutralMultiplier)),
                new(typeof(IntangiblePower), "ModifyHpLostAfterOsty", typeof(decimal), damage, nameof(NeutralHpLoss)),
                new(typeof(IntangiblePower), "ModifyDamageCap", typeof(decimal), cap, nameof(NeutralCap)),
                new(typeof(SlipperyPower), "ModifyHpLostAfterOsty", typeof(decimal), damage, nameof(NeutralHpLoss)),
                new(typeof(HardToKillPower), "ModifyDamageCap", typeof(decimal), cap, nameof(NeutralCap)),
                new(typeof(HardenedShellPower), "ModifyHpLostBeforeOstyLate", typeof(decimal), damage, nameof(NeutralShell)),
                new(typeof(HardenedShellPower), "BeforeSideTurnStart", typeof(Task),
                    [typeof(PlayerChoiceContext), typeof(CombatSide), typeof(System.Collections.Generic.IReadOnlyList<Creature>), typeof(ICombatState)],
                    nameof(ClearShellWindow)),
                new(typeof(ArtifactPower), "TryModifyPowerAmountReceived", typeof(bool),
                    [typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(decimal).MakeByRefType()],
                    nameof(AllowArtifactDebuff), Prefix: true),
                new(typeof(ThornsPower), "BeforeDamageReceived", typeof(Task),
                    [typeof(PlayerChoiceContext), typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)],
                    nameof(SuppressRetaliation), Prefix: true),
                new(typeof(ReflectPower), "AfterDamageReceived", typeof(Task), received,
                    nameof(SuppressRetaliation), Prefix: true),
                new(typeof(CreatureCmd), "Heal", typeof(Task), [typeof(Creature), typeof(decimal), typeof(bool)],
                    nameof(SuppressEnemyHeal), Prefix: true, Static: true),
            ];
            var resolved = specs.Select(spec => (Spec: spec, Method: Resolve(spec),
                Callback: typeof(DomainEnemyEffects).GetMethod(spec.Callback,
                    BindingFlags.Static | BindingFlags.NonPublic) ??
                    throw new MissingMethodException(typeof(DomainEnemyEffects).FullName, spec.Callback))).ToArray();
            var harmony = new Harmony(HarmonyId);
            try
            {
                foreach (var patch in resolved)
                {
                    var callback = new HarmonyMethod(patch.Callback);
                    harmony.Patch(patch.Method, prefix: patch.Spec.Prefix ? callback : null,
                        postfix: patch.Spec.Prefix ? null : callback);
                }
                _installed = true;
            }
            catch
            {
                // Remove only this installer's patches, never any other mod's patches.
                foreach (var patch in resolved)
                    harmony.Unpatch(patch.Method, HarmonyPatchType.All, HarmonyId);
                throw;
            }
        }
    }

    private static MethodInfo Resolve(PatchSpec spec)
    {
        var flags = BindingFlags.Public | BindingFlags.DeclaredOnly |
                    (spec.Static ? BindingFlags.Static : BindingFlags.Instance);
        var method = spec.Owner.GetMethod(spec.Name, flags, null, spec.Arguments, null);
        if (method is null || method.ReturnType != spec.Result || method.ContainsGenericParameters ||
            method.IsStatic != spec.Static || method.DeclaringType != spec.Owner)
            throw new MissingMethodException($"Domain suppression API drift: {spec.Owner.FullName}.{spec.Name}");
        return method;
    }

    // These exact native methods only compute scalar contributions. Other hooks continue to
    // run: notably Flutter's decrement/stun, Slippery's charge loss, and Intangible's expiry.
    private static void NeutralMultiplier(PowerModel __instance, Creature? __0, ref decimal __result)
    {
        if (ProtectsTarget(__instance, __0))
        {
            if (__result != 1m) Volibear.Presentation.PowerPresentationDomainScalars.Capture(__0, __instance);
            __result = 1m;
        }
    }

    private static void NeutralEnemyAttackBonus(PowerModel __instance, Creature? __3, ref decimal __result)
    {
        // Vigor's attack registration and AfterAttack consumption still run. Only
        // its positive additive contribution is suppressed; negative values survive.
        if (__result > 0m && ReferenceEquals(__instance.Owner, __3) && ActiveFor(__3))
        {
            Volibear.Presentation.PowerPresentationDomainScalars.Capture(__3, __instance);
            __result = 0m;
        }
    }

    private static void NeutralBackAttackBonus(PowerModel __instance, Creature? __0, Creature? __3, ref decimal __result)
    {
        // Facing/markers are combat facts and remain intact. This exact native
        // multiplier is the enemy benefit, even though its power lives on a player.
        if (__result > 1m && __0 is { IsPlayer: true } && ReferenceEquals(__instance.Owner, __0) &&
            __3 is not null && ReferenceEquals(__0.CombatState, __3.CombatState) && ActiveFor(__3))
        {
            Volibear.Presentation.PowerPresentationDomainScalars.Capture(__3, __instance);
            __result = 1m;
        }
    }

    private static void AllowBlockClear(PowerModel __instance, Creature __0, ref bool __result)
    {
        // Do not strip current/direct block on domain entry. Suppress only this
        // passive veto when the normal lifecycle actually requests block clearing.
        if (ProtectsTarget(__instance, __0))
        {
            if (!__result && __0.Block > 0) Volibear.Presentation.PowerPresentationDomainScalars.Capture(__0, __instance);
            __result = true;
        }
    }

    private static void NeutralHpLoss(PowerModel __instance, Creature? __0, decimal __1, ref decimal __result)
    {
        if (ProtectsTarget(__instance, __0))
        {
            if (__result != __1) Volibear.Presentation.PowerPresentationDomainScalars.Capture(__0, __instance);
            __result = __1;
        }
    }

    private static void NeutralCap(PowerModel __instance, Creature? __0, ref decimal __result)
    {
        if (ProtectsTarget(__instance, __0))
        {
            if (__result != decimal.MaxValue) Volibear.Presentation.PowerPresentationDomainScalars.CaptureCap(__0, __instance, __result);
            __result = decimal.MaxValue;
        }
    }

    private static void NeutralShell(PowerModel __instance, Creature? __0, decimal __1, ref decimal __result)
    {
        if (ProtectsTarget(__instance, __0))
        {
            if (__result != __1) Volibear.Presentation.PowerPresentationDomainScalars.Capture(__0, __instance);
            __result = __1;
            if (__1 > 0m)
            {
                var combat = __0!.CombatState!;
                SuppressedShells.Remove(__instance);
                SuppressedShells.Add(__instance, new ShellWindow(combat, __0, combat.RoundNumber));
            }
            return;
        }
        // Preserve native per-turn counters. ONLY a shell touched by this domain in the
        // current reset window may have overflowed its quota; unrelated vanilla stays exact.
        if (__0 is not null && ReferenceEquals(__instance.Owner, __0) && __0.IsEnemy &&
            !__0.IsPlayer && __1 > 0m && __result < 0m &&
            SuppressedShells.TryGetValue(__instance, out var window) &&
            ReferenceEquals(window.Owner, __0) && ReferenceEquals(window.Combat, __0.CombatState) &&
            window.Round == window.Combat.RoundNumber && window.Combat.ContainsCreature(__0) &&
            CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding &&
            ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(), window.Combat)) __result = 0m;
    }

    private static void ClearShellWindow(PowerModel __instance)
    {
        // Exact native BeforeSideTurnStart resets synchronously and returns CompletedTask.
        // Run it normally, then expire only our sidecar, including same-round side switches.
        SuppressedShells.Remove(__instance);
    }

    private static bool AllowArtifactDebuff(PowerModel __instance, PowerModel __0, Creature __1, decimal __2,
                                            ref decimal __4, ref bool __result)
    {
        if (!ProtectsTarget(__instance, __1)) return true;
        // false means this listener did not modify the amount: no Artifact consumption hook.
        // Leave visibility/type classification and all other listeners to the original engine.
        try
        {
            if (__2 != 0 && __0.IsVisible && __0.GetTypeForAmount(__2) == MegaCrit.Sts2.Core.Entities.Powers.PowerType.Debuff)
                Volibear.Presentation.PowerPresentationDomainScalars.Capture(__1, __instance);
        }
        catch { }
        __4 = __2;
        __result = false;
        return false;
    }

    private static bool SuppressRetaliation(PowerModel __instance, Creature __1, object[] __args, ref Task __result)
    {
        if (!ProtectsTarget(__instance, __1)) return true;
        // Only exact Thorns.BeforeDamageReceived / Reflect.AfterDamageReceived are installed.
        // They contain retaliation alone. Reflect.AfterSideTurnStart (expiry) is NOT patched.
        Volibear.Presentation.PowerPresentationDomain.RetaliationCancelled(__instance, __args);
        __result = Task.CompletedTask;
        return false;
    }

    private static bool SuppressEnemyHeal(Creature __0, decimal __1, ref Task __result)
    {
        // CreatureCmd.Heal lacks a source parameter. Gate the recipient benefit, never infer
        // enemy origin from CurrentSide: Engage also runs enemy actions in the player phase.
        // Dead-target heals are resurrection transactions and intentionally outside this slice.
        if (__1 <= 0m || !__0.IsAlive || !ActiveFor(__0)) return true;
        Volibear.Presentation.PowerPresentationDomain.Suppressed(__0, amount: __1);
        __result = Task.CompletedTask;
        return false;
    }
}
