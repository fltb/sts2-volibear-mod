using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear;

/// <summary>Small source-level bridges for the two game channels. Production behavior is unchanged;
/// only signatures that moved between the stable and PBE branches are wrapped here.</summary>
internal static class NativeCompat
{
#if STS2_BETA
    /// <summary>PBE <c>AttackCommand.FromCard</c> carries the originating card play; mod attack
    /// segments pass null where the native queue only needs the card for attribution.</summary>
    public static AttackCommand BridgeFromCard(this AttackCommand command, CardModel card) =>
        command.FromCard(card, null);
#endif

    internal static readonly Type[] AfterDeathParameters =
        [typeof(PlayerChoiceContext), typeof(Creature),
#if STS2_BETA
         typeof(CardModel),
#endif
         typeof(bool), typeof(float)];

    internal static readonly Type[] KillWithoutWinParameters =
        [typeof(Creature),
#if STS2_BETA
         typeof(CardModel),
#endif
         typeof(bool), typeof(int)];

    // Development probes keep their original call shapes; these bridges absorb the channel split.
    internal static Task LoseBlock(Creature target, decimal amount)
    {
#if STS2_BETA
        return CreatureCmd.LoseBlock(new ThrowingPlayerChoiceContext(), target, amount, null);
#else
        return CreatureCmd.LoseBlock(target, amount);
#endif
    }

    internal static Task<IEnumerable<DamageResult>> Damage(PlayerChoiceContext context, Creature target, decimal amount,
        ValueProp props, Creature? dealer, CardModel? card)
    {
#if STS2_BETA
        return CreatureCmd.Damage(context, target, amount, props, dealer, card, null);
#else
        return CreatureCmd.Damage(context, target, amount, props, dealer, card);
#endif
    }

    internal static Task<IEnumerable<DamageResult>> Damage(PlayerChoiceContext context, IEnumerable<Creature> targets, decimal amount,
        ValueProp props, Creature? dealer, CardModel? card)
    {
#if STS2_BETA
        return CreatureCmd.Damage(context, targets, amount, props, dealer, card, null);
#else
        return CreatureCmd.Damage(context, targets, amount, props, dealer, card);
#endif
    }

    internal static bool IsDebugEncounter(EncounterModel encounter)
    {
#if STS2_BETA
        // PBE dropped the flag; debug content is identified by its canonical id prefix.
        return encounter.Id.ToString().Contains("debug", StringComparison.OrdinalIgnoreCase);
#else
        return encounter.IsDebugEncounter;
#endif
    }
}
