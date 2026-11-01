using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Content;
using Volibear.Core;

namespace Volibear.Presentation;

internal static partial class PowerAudioReceipts
{
    private static bool TracksPresentation(PowerModel power, CardModel? card) =>
        power is VulnerablePower or WeakPower or DexterityPower or PrimalThunderPower or UnifyPower || card?.Type == CardType.Power;

    private static void InstallPresentationCommits(Harmony harmony)
    {
        PowerPresentationDomainScalars.Install(harmony);
        harmony.Patch(AccessTools.Method(typeof(PowerModel), nameof(PowerModel.SetAmount)),
            transpiler: new(typeof(PowerAudioReceipts), nameof(AmountCommitBody)));
        harmony.Patch(AccessTools.Method(typeof(Creature), nameof(Creature.ApplyPowerInternal)),
            transpiler: new(typeof(PowerAudioReceipts), nameof(DeploymentCommitBody)));
    }

    // Observe the exact clamped native delta immediately after its field write, BEFORE
    // DisplayAmountChanged can execute nested work. Initial SetAmount is not deployment:
    // the instance must already be in Powers, otherwise the Add boundary below owns it.
    private static IEnumerable<CodeInstruction> AmountCommitBody(IEnumerable<CodeInstruction> instructions)
    {
        var field = AccessTools.Field(typeof(PowerModel), "_amount");
        var code = instructions.ToList();
        int difference = code.FindIndex(c => c.opcode == OpCodes.Sub);
        if (difference < 1 || difference + 1 >= code.Count || !code[difference - 1].LoadsField(field) ||
            code[difference + 1].opcode != OpCodes.Stloc_0 ||
            AccessTools.Method(typeof(PowerModel), nameof(PowerModel.SetAmount)).GetMethodBody()!.LocalVariables[0].LocalType != typeof(int))
            throw new InvalidOperationException("Power clamped delta local drift");
        int matches = 0;
        foreach (var instruction in code)
        {
            yield return instruction;
            if (instruction.opcode != OpCodes.Stfld || !Equals(instruction.operand, field)) continue;
            matches++;
            yield return new(OpCodes.Ldarg_0);
            yield return new(OpCodes.Ldloc_0); // Pinned native num = clamped amount - old amount.
            yield return new(OpCodes.Ldc_I4_0);
            yield return new(OpCodes.Call, Handler(nameof(PresentationCommitted)));
        }
        if (matches != 1) throw new InvalidOperationException("Power amount presentation commit drift");
    }

    // List insertion is the successful deployment, before native PowerApplied listeners.
    private static IEnumerable<CodeInstruction> DeploymentCommitBody(IEnumerable<CodeInstruction> instructions)
    {
        var add = AccessTools.Method(typeof(List<PowerModel>), nameof(List<PowerModel>.Add));
        int matches = 0;
        foreach (var instruction in instructions)
        {
            yield return instruction;
            if (!instruction.Calls(add)) continue;
            matches++;
            yield return new(OpCodes.Ldarg_1);
            yield return new(OpCodes.Ldarg_1);
            yield return new(OpCodes.Callvirt, AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Amount)));
            yield return new(OpCodes.Ldc_I4_1);
            yield return new(OpCodes.Call, Handler(nameof(PresentationCommitted)));
        }
        if (matches != 1) throw new InvalidOperationException("Power deployment presentation commit drift");
    }

    private static void PresentationCommitted(PowerModel power, int delta, bool deployed)
    {
        try
        {
            if (Current.Value is not { Closed: false, AtCommit: true, Ticket: { Invalid: false, PresentationCommitted: false } ticket } ||
                delta <= 0 || ticket.Owner is not { } recipient || !ReferenceEquals(ticket.Power, power) ||
                !ReferenceEquals(power.Owner, recipient) || !ReferenceEquals(ticket.Combat, recipient.CombatState) ||
                !recipient.Powers.Contains(power)) return;
            ticket.PresentationCommitted = true;
            // Own-stat receipts belong to the recipient. Enemy debuffs require the exact
            // command's player applier, never the power's historical Applier property.
            var owner = recipient.Player?.Character is VolibearCharacter ? recipient : ticket.Applier;
            if (owner?.Player?.Character is not VolibearCharacter || !ReferenceEquals(owner.CombatState, recipient.CombatState)) return;
            void Publish(string kind) => GameplayPresentationReceipts.Publish(kind, owner, power, ticket.Card, recipient, delta);
            if (recipient.IsEnemy && !recipient.IsPlayer && ReferenceEquals(ticket.Applier, owner))
            {
                if (power is VulnerablePower) Publish("vulnerable_applied");
                if (power is WeakPower) Publish("weakness_applied");
            }
            if (!ReferenceEquals(recipient, owner)) return;
            if (deployed && power is (PreparedPower or PersistentPower or EndlessHuntPower or BearSpiritPower or WildernessPower) &&
                ticket.Card?.Type == CardType.Power && ReferenceEquals(ticket.Card.Owner.Creature, owner))
                Publish("power_instance_deployed");
            if (power is PrimalThunderPower or UnifyPower) Publish("thunder_modifier_changed");
            if (power is DexterityPower) Publish("dexterity_changed");
        }
        catch { /* Cosmetic observers cannot fail the native mutation. */ }
    }
}
