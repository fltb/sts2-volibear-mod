using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Content;

/// <summary>
/// Native lightning damage. It is not an attack: no strength, vulnerable or weak scaling,
/// it is blockable, and one batch is one settlement however many targets it touches.
/// </summary>
public static class LightningCmd
{
    public static async Task<int> DealAllEnemies(PlayerChoiceContext choiceContext, decimal amount,
                                                 CardModel? card, ICombatState? state = null)
    {
        if (amount <= 0) return 0;
        var combat = state ?? CombatManager.Instance.DebugOnlyGetState();
        if (combat is null) return 0;
        return await Deal(choiceContext, combat.Enemies, amount, card);
    }

    public static async Task<int> Deal(PlayerChoiceContext choiceContext, IEnumerable<Creature> targets,
                                       decimal amount, CardModel? card)
    {
        var living = targets.Where(target => target.IsAlive).ToList();
        if (amount <= 0 || living.Count == 0) return 0;
        var owner = card?.Owner?.Creature;
        var results = await CreatureCmd.Damage(choiceContext, living, amount, ValueProp.Unpowered,
                                               owner, card);
        var dealt = 0;
        foreach (var result in results) dealt += (int)result.UnblockedDamage;
        return dealt;
    }
}
