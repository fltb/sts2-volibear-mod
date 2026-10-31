using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models.Cards;

namespace Volibear;

// Test-only extension of one exact Strike instance; not shipped card content.
// Wrapping its OnPlay task keeps the enemy action inside OnPlayWrapper's await.
[HarmonyPatch(typeof(StrikeIronclad), "OnPlay")]
internal static class EngageCardProbe
{
    internal static StrikeIronclad? Selected;
    internal static CombatState? State;
    internal static EngagePrototype.Result? First, Duplicate;
    internal static readonly List<string> Order = new();
    internal static int Responses, BlockBeforeResponse, BlockAfterResponse, FollowupDamage;

    private static void Postfix(StrikeIronclad __instance, CardPlay cardPlay, ref Task __result)
    {
        if (!ReferenceEquals(__instance, Selected)) return;
        __result = Continue(__result, __instance, cardPlay);
    }

    private static async Task Continue(Task original, StrikeIronclad card, CardPlay play)
    {
        await original;
        Order.Add("pre-effect-finished");
        async Task Respond(EngagePrototype.Result result)
        {
            Order.Add("enemy-action-finished");
            Responses++;
            BlockBeforeResponse = card.Owner.Creature.Block;
            await MegaCrit.Sts2.Core.Commands.CreatureCmd.GainBlock(card.Owner.Creature,
                result.Absorbed, MegaCrit.Sts2.Core.ValueProps.ValueProp.Unpowered, null);
            BlockAfterResponse = card.Owner.Creature.Block;
            Order.Add("completion-response");
        }
        First = await EngagePrototype.Perform(State!, play.Target!, card.Owner.Creature, Respond);
        Duplicate = await EngagePrototype.Perform(State!, play.Target!, card.Owner.Creature, Respond);
        Order.Add("duplicate-rejected");
        if (!First.Value.Completed || card.Owner.Creature.IsDead || CombatManager.Instance.IsEnding) return;
        int hp = play.Target!.CurrentHp;
        await MegaCrit.Sts2.Core.Commands.DamageCmd.Attack(1m).FromCard(card).Targeting(play.Target)
            .Execute(new MegaCrit.Sts2.Core.GameActions.Multiplayer.ThrowingPlayerChoiceContext());
        FollowupDamage = hp - play.Target.CurrentHp;
        Order.Add("remaining-card-effect");
    }
}
