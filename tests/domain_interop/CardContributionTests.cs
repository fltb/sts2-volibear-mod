using System.Reflection;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Afflictions;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

internal static class CardContributionTests
{
    private static int Checks;
    private static object? Invoke(string method, params object?[] args) => typeof(DomainCardContributions)
        .GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, args);
    private static void Check(bool value, string why) { Checks++; if (!value) throw new Exception(why); }
    private static decimal Cost(PowerModel power, CardModel card)
    {
        object?[] args = [power, card, 1m, 0m];
        _ = typeof(DomainCardContributions).GetMethod("CostContribution", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, args);
        return (decimal)args[3]!;
    }

    internal static void Run()
    {
        foreach (bool enemyFirst in new[] { false, true })
        {
            DomainCardContributions.Reset(); DomainEnemyEffects.Active = true;
            var combat = new CombatState();
            var player = new Creature { IsPlayer = true, CombatId = 1, CombatState = combat };
            var enemy = new Creature { IsEnemy = true, CombatId = 2, CombatState = combat };
            var teammate = new Creature { IsPlayer = true, CombatId = 3, CombatState = combat };
            combat.Creatures.AddRange([player, enemy, teammate]);
            var card = new CardModel(new Player(player)) { Affliction = new Entangled() };
            var context = new PlayerChoiceContext();
            var power = new TangledPower();
            Invoke("ApplyCommit", power, player, enemyFirst ? 2m : 3m, false, enemyFirst ? enemy : player, null, context);
            Check(Cost(power, card) == 1m, "Domain suppresses initial player or enemy sourced cost");
            Invoke("AmountCommit", power, 5, false, enemyFirst ? player : enemy, null, context);
            Check(Cost(power, card) == 1 && power.Amount == 5, "mixed debuff cost is muted without rewriting native amount");
            var audit = DomainCardContributions.Audit(power);
            Check(audit.State == "mixed" && audit.RetainedAmount == 3 && audit.UnsupportedReason == "", "mixed source is supported, with an explicit retained amount");
            DomainEnemyEffects.Active = false;
            Check(Cost(power, card) == 6, "ending Domain restores complete native cost without rewriting the power");
            DomainEnemyEffects.Active = true;
            power.OtherModOffset = 4;
            Check(Cost(power, card) == 1, "the debuff contribution including its adjusted magnitude is muted");
            DomainEnemyEffects.Active = false;
            Check(Cost(power, card) == 10, "foreign contribution adjustment returns with the native debuff");
            power.OtherModOffset = 0;
            DomainEnemyEffects.Active = true;
            combat.Creatures.Remove(enemy); enemy.CombatState = null;
            Check(Cost(power, card) == 1, "source departure does not end player protection");
            Invoke("AmountCommit", power, 6, false, null, null, context);
            Check(Cost(power, card) == 1 && power.Amount == 6, "unattributed stacks commit and remain suppressed");
            power.SetAmount(8, false);
            Check(Cost(power, card) == 1, "direct native amount writes remain suppressed");
            Invoke("AmountCommit", power, 7, false, null, null, context);
            Check(Cost(power, card) == 1 && power.Amount == 7, "native decrement retains lifetime while contribution stays muted");
            card.Affliction = null;
            Check(Cost(power, card) == 1, "non-entangled card never gains an invented discount");
            card.Affliction = new Entangled();
            power.SetAmount(-2, false);
            Check(Cost(power, card) == -1, "favorable native negative cost remains unchanged");
            DomainCardContributions.Reset(); power.SetAmount(4, false);
            Check(Cost(power, card) == 1, "existing untracked debuff is suppressed without provenance receipts");
            enemy.CombatState = combat; combat.Creatures.Add(enemy);
            Invoke("AmountCommit", power, 6, false, enemy, null, context);
            Check(Cost(power, card) == 1, "new enemy stacks retain temporary suppression");

            foreach (var pair in new (PowerModel Power, object Affliction)[]
                { (new HexPower(), new Hexed()), (new SmoggyPower(), new Smog()), (new RingingPower(), new Ringing()) })
            {
                card.Affliction = pair.Affliction;
                Invoke("ApplyCommit", pair.Power, player, 1m, false, enemy, null, context);
                bool Effect()
                {
                    if (pair.Power is HexPower)
                    {
                        var keywords = new HashSet<CardKeyword>();
                        _ = Invoke("KeywordsContribution", pair.Power, card, keywords);
                        return keywords.Contains(CardKeyword.Ethereal);
                    }
                    return !(bool)Invoke("PlayContribution", pair.Power, card, AutoPlayType.None)!;
                }
                Check(!Effect(), "enemy-only boolean restriction is suppressed");
                Invoke("AmountCommit", pair.Power, 2, false, player, null, context);
                Check(!Effect(), "player-sourced restriction is also suppressed");
                DomainEnemyEffects.Active = false;
                Check(Effect(), "mixed restriction resumes on Domain exit");
                DomainEnemyEffects.Active = true;
                Check(DomainCardContributions.Audit(pair.Power).UnsupportedReason == "", "idempotent mixed boolean contribution is supported");
            }
        }
        var ledger = new DomainCardContributionLedger(2, enemy: true);
        ledger.Change(2, 1, enemy: false);
        Check(ledger.Effective == 0, "a decay of enemy-only cost cannot create a negative discount");
        ledger.Change(1, 2, enemy: false); Check(ledger.Effective == 1, "new player contribution survives after decay");
        ledger.Change(2, 3, enemy: true); Check(ledger.Effective == 1, "new enemy contribution is excluded");
        Console.WriteLine($"DOMAIN_CARD_INTEROP_PASS checks={Checks} production-adapters=true native-gameplay=NOT_RUN");
    }
}
