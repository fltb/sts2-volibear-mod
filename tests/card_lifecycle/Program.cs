using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using Volibear.Content;
using Volibear.Core;

// The real B04 OnPlay and shared lifecycle guard are linked above. Only engine
// boundaries are test doubles; this checks command sequencing, not native gameplay.
var checks = 0;
void Check(bool value, string message)
{
    checks++;
    if (!value) throw new Exception(message);
}

Volibear_B04 NewCard()
{
    BoundaryTrace.Events.Clear();
    CreatureCmd.AfterBlock = null;
    DamageCmd.AfterAttack = null;
    DamageCmd.RejectCalls = false;
    EngageCmd.RejectCalls = false;
    CombatManager.Instance.IsInProgress = true;
    CombatManager.Instance.IsOverOrEnding = false;
    return new Volibear_B04 { Owner = new() { Creature = new() { IsAlive = true, CombatState = new() } } };
}

var context = new PlayerChoiceContext();
var play = new CardPlay { Target = new Creature() };
var live = NewCard();
await live.Play(context, play);
Check(BoundaryTrace.Events.SequenceEqual(new[] { "block:8", "attack:6", "engage" }), "live B04 preserves block/attack/automatic engage order");

foreach (var terminal in new[] { "state-removed", "ending", "not-in-progress", "owner-dead" })
{
    var card = NewCard();
    var resumed = false;
    CreatureCmd.AfterBlock = async () =>
    {
        await Task.Yield(); // Block responses can finish combat before B04 resumes.
        switch (terminal)
        {
            case "state-removed": card.Owner.Creature.CombatState = null; break;
            case "ending": CombatManager.Instance.IsOverOrEnding = true; break;
            case "not-in-progress": CombatManager.Instance.IsInProgress = false; break;
            case "owner-dead": card.Owner.Creature.IsAlive = false; break;
        }
        DamageCmd.RejectCalls = true;
        EngageCmd.RejectCalls = true;
        resumed = true;
    };
    await card.Play(context, play);
    Check(resumed, terminal + ": block really yielded before terminal transition");
    Check(BoundaryTrace.Events.SequenceEqual(new[] { "block:8" }), terminal + ": no attack or engage after awaited block termination");
}

var lostTarget = NewCard();
var removedTarget = new Creature();
CreatureCmd.AfterBlock = async () =>
{
    await Task.Yield();
    removedTarget.IsHittable = false;
    DamageCmd.RejectCalls = true;
};
await lostTarget.Play(context, new CardPlay { Target = removedTarget });
Check(!BoundaryTrace.Events.Any(e => e.StartsWith("attack:")), "B04 skips ordinary attack when block responses make the target unhittable");

foreach (var terminal in new[] { "state-removed", "ending", "not-in-progress", "owner-dead" })
{
    var card = NewCard();
    var resumed = false;
    DamageCmd.AfterAttack = async () =>
    {
        await Task.Yield(); // End while the actual B04 is awaiting its attack command.
        switch (terminal)
        {
            case "state-removed": card.Owner.Creature.CombatState = null; break;
            case "ending": CombatManager.Instance.IsOverOrEnding = true; break;
            case "not-in-progress": CombatManager.Instance.IsInProgress = false; break;
            case "owner-dead": card.Owner.Creature.IsAlive = false; break;
        }
        EngageCmd.RejectCalls = true; // A terminal boundary must not be entered.
        resumed = true;
    };
    await card.Play(context, play);
    Check(resumed, terminal + ": attack really yielded before terminal transition");
    Check(BoundaryTrace.Events.SequenceEqual(new[] { "block:8", "attack:6" }), terminal + ": no engage call after awaited termination");
}

var noTarget = NewCard();
await noTarget.Play(context, new CardPlay());
Check(BoundaryTrace.Events.SequenceEqual(new[] { "block:8" }), "missing target keeps block and skips targeted effects");
var nextCombat = NewCard();
await nextCombat.Play(context, play);
Check(BoundaryTrace.Events.Last() == "engage", "later live combat can engage normally");
Console.WriteLine($"CARD_LIFECYCLE_UNIT_OK checks={checks} engine=STUBBED native-gameplay=NOT_RUN");
