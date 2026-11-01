using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

namespace Volibear.Content;

// Recheck after awaited damage/response commands: they may have ended combat or
// removed the player's combat state before a later effect resumes.
internal static partial class DirectEffects
{
    internal static bool Live(CardModel card) => card.Owner.Creature.IsAlive &&
        card.Owner.Creature.CombatState is not null && CombatManager.Instance.IsInProgress &&
        !CombatManager.Instance.IsOverOrEnding;

    internal static Task<EngageCmd.Result> Engage(PlayerChoiceContext context, CardModel card, Creature? target) =>
        Live(card) && target is not null ? EngageCmd.Perform(context, target, card)
            : Task.FromResult(new EngageCmd.Result(false, 0m, false));
}
