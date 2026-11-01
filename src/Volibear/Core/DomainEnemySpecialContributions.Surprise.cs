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
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;

namespace Volibear.Core;

public static partial class DomainEnemySpecialContributions
{
    private sealed class SurpriseReceipt(ICombatState combat)
    {
        internal readonly ICombatState Combat = combat;
        internal bool Cancelled;
    }
    private static ConditionalWeakTable<SurprisePower, SurpriseReceipt> surprises = new();
    private static int specialGeneration;
    private static bool SurpriseGate(SurpriseReceipt receipt, int generation)
    {
        if (generation != specialGeneration) return true;
        receipt.Cancelled |= DomainEnemyEffects.ActiveFor(receipt.Combat);
        return receipt.Cancelled;
    }
    private static bool DeathContribution(SurprisePower __instance, PlayerChoiceContext choiceContext, Creature target, bool wasRemovalPrevented, ref Task __result)
    {
        if (wasRemovalPrevented || !ReferenceEquals(__instance.Owner, target) || !target.IsEnemy || target.IsPlayer ||
            target.CombatState is not { } combat || !combat.ContainsCreature(target)) return true;
        var receipt = new SurpriseReceipt(combat);
        surprises.Remove(__instance); surprises.Add(__instance, receipt);
        __result = SurpriseDeath(__instance, choiceContext, receipt, specialGeneration);
        return false;
    }
    private static async Task SurpriseDeath(SurprisePower power, PlayerChoiceContext context, SurpriseReceipt receipt, int generation)
    {
        // Each Add commits synchronously before its first await (native CreateCreature/AddCreature).
        // A late domain cancels only the next child. Already committed children are never removed.
        if (!SurpriseGate(receipt, generation)) await CreatureCmd.Add<SneakyGremlin>(receipt.Combat, "sneaky");
        else if (generation == specialGeneration) Volibear.Presentation.PowerPresentationDomain.Once(receipt, power.Owner, power, sourceCombat: receipt.Combat);
        if (generation != specialGeneration) return;
        Creature? fat = null;
        if (!SurpriseGate(receipt, generation)) fat = await CreatureCmd.Add<FatGremlin>(receipt.Combat, "fat");
        else if (generation == specialGeneration) Volibear.Presentation.PowerPresentationDomain.Once(receipt, power.Owner, power, sourceCombat: receipt.Combat);
        if (generation != specialGeneration) return;
        int total = 0;
        foreach (var theft in power.Owner.GetPowerInstances<ThieveryPower>())
        {
            int amount = theft.DynamicVars.Gold.IntValue;
            total += amount;
            if (fat is not null)
            {
                var heist = (HeistPower)ModelDb.Power<HeistPower>().ToMutable();
                heist.Target = theft.Target;
                await PowerCmd.Apply(context, heist, fat, amount, power.Owner, null);
                if (generation != specialGeneration) return;
            }
            else if (amount > 0)
            {
                // The carrier never existed. Settle the same stolen-back reward and history
                // as Heist.BeforeDeath, without inventing a creature or killing a placeholder.
                var player = theft.Target?.Player ?? throw new InvalidOperationException("Native theft has no player reward target");
                if (receipt.Combat.RunState.CurrentRoom is CombatRoom room)
                    room.AddExtraReward(player, new GoldReward(amount, player, wasGoldStolenBack: true));
                receipt.Combat.RunState.CurrentMapPointHistoryEntry?.GetEntry(player.NetId).MarkLootReturned(amount);
            }
        }
        if (total > 0 && receipt.Combat.Encounter is GremlinMercNormal encounter) encounter.MarkGoldStolen();
    }
    private static bool EndingContribution(AbstractModel model)
    {
        if (model is SurprisePower power && surprises.TryGetValue(power, out var receipt) && receipt.Cancelled &&
            ReferenceEquals(receipt.Combat, power.Owner.CombatState) && power.Owner.IsDead) return false;
        return model.ShouldStopCombatFromEnding();
    }
    private static void ResetSpecial() { specialGeneration++; surprises = new(); }
    private static MethodInfo SpecialHandler(string name) => typeof(DomainEnemySpecialContributions).GetMethod(name,
        BindingFlags.NonPublic | BindingFlags.Static) ?? throw new MissingMethodException(name);
    private static IEnumerable<CodeInstruction> RewriteSurprise(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        if (__originalMethod.Name != nameof(Hook.ShouldStopCombatFromEnding)) throw new InvalidOperationException("Unknown ending-vote dispatcher");
        var native = Method(typeof(AbstractModel), nameof(AbstractModel.ShouldStopCombatFromEnding));
        int count = 0;
        var output = new List<CodeInstruction>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.Calls(native))
            {
                count++; instruction.opcode = OpCodes.Call;
                instruction.operand = SpecialHandler(nameof(EndingContribution));
            }
            output.Add(instruction);
        }
        if (count != 1) throw new InvalidOperationException("Surprise dispatcher native call count changed: " + __originalMethod);
        return output;
    }
    private static void InstallSurprise(Harmony harmony)
    {
        var death = Method(typeof(SurprisePower), nameof(SurprisePower.AfterDeath), typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float));
        // Concrete asynchronous callback, reached by the existing native/revival dispatcher.
        // Do not compete for its AbstractModel.AfterDeath callsite.
        harmony.Patch(death, prefix: new HarmonyMethod(SpecialHandler(nameof(DeathContribution))));
        var sites = new[] { Method(typeof(Hook), nameof(Hook.ShouldStopCombatFromEnding), typeof(ICombatState)) };
        foreach (var site in sites)
        {
            _ = RewriteSurprise(PatchProcessor.GetOriginalInstructions(site), site).ToArray();
            harmony.Patch(site, transpiler: new HarmonyMethod(SpecialHandler(nameof(RewriteSurprise))));
        }
        harmony.Patch(Method(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool)), prefix: new HarmonyMethod(SpecialHandler(nameof(ResetSpecial))));
    }
}
