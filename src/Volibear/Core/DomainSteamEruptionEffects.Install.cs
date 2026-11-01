using System;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    public const string HarmonyId = "Volibear.DomainSteamEruptionEffects";
    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony(HarmonyId);
        try
        {
            InstallPatches(harmony);
            _installed = true;
        }
        catch
        {
            harmony.UnpatchAll(HarmonyId);
            throw;
        }
    }
    internal static void InstallPatches(Harmony harmony)
    {
        DamageHandoff.Install(harmony, NativeDamage);
        PhaseHandoff.Install(harmony, AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState)));
        void Patch(MethodInfo original, string transpiler) => harmony.Patch(original, transpiler: new HarmonyMethod(Own(transpiler)));
        Patch(Async(AccessTools.Method(typeof(CreatureCmd), "KillWithoutCheckingWinCondition")), nameof(DeathMachine));
        Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Kill), [typeof(IReadOnlyCollection<Creature>), typeof(bool)])), nameof(PublicKill));
        Patch(AccessTools.Method(typeof(Hook), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath)), nameof(RemovalContributions));
        Patch(Async(AccessTools.Method(typeof(SteamEruptionPower), nameof(SteamEruptionPower.AfterDeath))), nameof(SteamDeathCallback));
        Patch(Async(AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState))), nameof(PhaseMachine));
        Patch(Async(AccessTools.Method(typeof(WaterfallGiant), "AboutToBlowMove")), nameof(AboutMachine));
        Patch(Async(AccessTools.Method(typeof(WaterfallGiant), "ExplodeMove")), nameof(ExplodeMachine));
        harmony.Patch(Async(AccessTools.Method(typeof(AttackCommand), nameof(AttackCommand.Execute))),
            transpiler: new HarmonyMethod(Own(nameof(AttackMachine))) { after = [CardResolutionHooks.OrdinaryAttackOwnerV1] });
        Patch(Async(NativeDamage), nameof(DamageMachine));
        Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.SetCurrentHp))), nameof(SetHpMachine));
        Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.SetMaxHp))), nameof(SetMaxHpMachine));
        Patch(Async(AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.PerformMove))), nameof(MoveTail));
        harmony.Patch(AccessTools.Method(typeof(SteamEruptionPower), nameof(SteamEruptionPower.ShouldStopCombatFromEnding)), prefix: new HarmonyMethod(Own(nameof(EndingVote))));
        harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]), prefix: new HarmonyMethod(Own(nameof(Reset))));
    }
}
