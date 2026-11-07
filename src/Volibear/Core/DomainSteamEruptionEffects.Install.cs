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
        void Patch(MethodInfo original, string transpiler) => harmony.Patch(original, transpiler: new HarmonyMethod(Own(transpiler)));
        var steps = new (string Label, Action Run)[]
        {
            ("damage-handoff", () => DamageHandoff.Install(harmony, NativeDamage)),
            ("phase-handoff", () => PhaseHandoff.Install(harmony, AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState)))),
            ("death-machine", () => Patch(Async(AccessTools.Method(typeof(CreatureCmd), "KillWithoutCheckingWinCondition")), nameof(DeathMachine))),
            ("public-kill", () => Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Kill), [typeof(IReadOnlyCollection<Creature>), typeof(bool)])), nameof(PublicKill))),
            ("removal-contributions", () => Patch(AccessTools.Method(typeof(Hook), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath)), nameof(RemovalContributions))),
            ("steam-death", () => Patch(Async(AccessTools.Method(typeof(SteamEruptionPower), nameof(SteamEruptionPower.AfterDeath))), nameof(SteamDeathCallback))),
            ("phase-machine", () => Patch(Async(AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState))), nameof(PhaseMachine))),
            ("about-machine", () => Patch(Async(AccessTools.Method(typeof(WaterfallGiant), "AboutToBlowMove")), nameof(AboutMachine))),
            ("explode-machine", () => Patch(Async(AccessTools.Method(typeof(WaterfallGiant), "ExplodeMove")), nameof(ExplodeMachine))),
            ("attack-machine", () => harmony.Patch(Async(AccessTools.Method(typeof(AttackCommand), nameof(AttackCommand.Execute))),
                transpiler: new HarmonyMethod(Own(nameof(AttackMachine))) { after = [CardResolutionHooks.OrdinaryAttackOwnerV1] })),
            ("damage-machine", () => Patch(Async(NativeDamage), nameof(DamageMachine))),
            ("set-hp-machine", () => Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.SetCurrentHp))), nameof(SetHpMachine))),
            ("set-max-hp-machine", () => Patch(Async(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.SetMaxHp))), nameof(SetMaxHpMachine))),
            ("move-tail", () => Patch(Async(AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.PerformMove))), nameof(MoveTail))),
            ("ending-vote", () => harmony.Patch(AccessTools.Method(typeof(SteamEruptionPower), nameof(SteamEruptionPower.ShouldStopCombatFromEnding)), prefix: new HarmonyMethod(Own(nameof(EndingVote))))),
            ("reset", () => harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)]), prefix: new HarmonyMethod(Own(nameof(Reset))))),
        };
        foreach (var step in steps)
        {
            try { step.Run(); }
            catch (Exception error) { throw new InvalidOperationException("Steam patch failed: " + step.Label, error); }
        }
    }
}
