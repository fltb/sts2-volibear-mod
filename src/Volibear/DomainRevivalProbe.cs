using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Volibear.Core;

namespace Volibear;

/// <summary>Formal native enemy mechanism fixture, NOT normal card/whole enemy-turn acceptance.
/// Encounter and initial/death states are native. Explicitly labelled move callbacks exercise
/// cancellation reentry without inventing a replacement enemy executor or copying expected HP.</summary>
internal static class DomainRevivalProbe
{
    private static bool _started;
    public static void Install() => CombatManager.Instance.TurnStarted += Start;
    private static void Start(CombatState combat)
    {
        if (_started) return;
        _started = true; CombatManager.Instance.TurnStarted -= Start;
        _ = Run(combat);
    }
    private static object Snapshot(Creature creature, CombatState combat, PowerModel source) => new
    {
        hp = creature.CurrentHp, maxHp = creature.MaxHp, alive = creature.IsAlive,
        attached = ReferenceEquals(creature.CombatState, combat), listed = combat.ContainsCreature(creature),
        nodePresent = NCombatRoom.Instance?.GetCreatureNode(creature) is not null,
        sourcePresent = creature.Powers.Any(power => ReferenceEquals(power, source)),
        nextMove = creature.Monster?.MoveStateMachine is null ? null : creature.Monster.NextMove.Id,
    };
    private static async Task Run(CombatState combat)
    {
        Func<PowerModel, Creature, bool, Task>? callback = null;
        Action<Creature, string>? lifecycle = null;
        Action<PowerModel>? cleanup = null;
        Action<CombatState>? managerRemoved = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_VARIANT") ?? "";
            var pieces = variant.Split('-');
            if (string.IsNullOrEmpty(token) || pieces.Length != 2 ||
                !new[] { "reattach", "illusion" }.Contains(pieces[0]) ||
                !new[] { "off", "on", "late", "cached", "toggle" }.Contains(pieces[1]) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Invalid isolated revival fixture token/variant/TestMode.");
            var family = pieces[0]; var mode = pieces[1];
            var owner = combat.Players.Single();
            var context = new ThrowingPlayerChoiceContext();
            if (owner.Creature.GetPowerAmount<DomainPower>() != 0) throw new InvalidOperationException("Expected fresh no-domain fixture.");
            var setupMoves = new List<string>();
            if (family == "illusion")
            {
                if (combat.Encounter is not TheObscuraNormal) throw new InvalidOperationException("Requires TheObscuraNormal native encounter.");
                var obscura = combat.Enemies.Single(enemy => enemy.Monster is TheObscura);
                if (obscura.Monster!.NextMove.Id != "ILLUSION_MOVE") throw new InvalidOperationException("Expected natural first summon state.");
                setupMoves.Add(obscura.Monster.NextMove.Id);
                await obscura.Monster.PerformMove(); // Native initial summon, not direct fabricated Parafright/IllusionPower.
            }
            else if (combat.Encounter is not DecimillipedeElite) throw new InvalidOperationException("Requires DecimillipedeElite native encounter.");
            var target = family == "reattach" ? combat.Enemies.First(enemy => enemy.Monster is DecimillipedeSegmentFront)
                : combat.Enemies.Single(enemy => enemy.Monster is Parafright);
            PowerModel source = family == "reattach" ? target.GetPower<ReattachPower>()! : target.GetPower<IllusionPower>()!;
            if (source is null) throw new InvalidOperationException("Formal enemy did not deploy its actual native power.");
            var minion = target.GetPower<MinionPower>();
            var nativeType = target.Monster!.GetType().Name;
            var sourceType = source.GetType().Name;
            var initial = Snapshot(target, combat, source);
            var sourceAmount = source.Amount;
            var initialFatal = target.Powers.All(power => power.ShouldOwnerDeathTriggerFatal());
            bool? minionFatalBefore = minion?.ShouldOwnerDeathTriggerFatal();
            var died = 0; var sourceRemoved = 0; var afterRemoved = 0; var managerNotifications = 0; var callbackCount = 0; var nativeBodiesExecuted = 0;
            var trace = new List<string>();
            target.Died += creature => { if (ReferenceEquals(creature, target)) died++; };
            target.PowerRemoved += power => { if (ReferenceEquals(power, source)) sourceRemoved++; };
            lifecycle = (creature, phase) => { if (ReferenceEquals(creature, target)) trace.Add(phase); };
            cleanup = power => { if (ReferenceEquals(power, source)) afterRemoved++; };
            managerRemoved = _ => { if (target.Monster.MoveStateMachine is null) managerNotifications++; };
            DomainRevivalEffects.LifecycleObserved += lifecycle;
            DomainRevivalEffects.PowerDeathCleanupCompleted += cleanup;
            CombatManager.Instance.CreaturesChanged += managerRemoved;
            async Task Open() { await DomainPower.Open(context, owner.Creature, 3); }
            object? beforeCachedOpen = null;
            callback = async (power, creature, bodyRan) =>
            {
                if (!ReferenceEquals(power, source) || !ReferenceEquals(creature, target)) return;
                callbackCount++;
                if (bodyRan) nativeBodiesExecuted++;
                if (mode == "cached")
                {
                    beforeCachedOpen = Snapshot(target, combat, source);
                    await Open(); // Actual native AfterDeath has returned; Kill's cached removal is still false.
                }
            };
            DomainRevivalEffects.AfterDeathContribution += callback;
            if (mode is "on" or "toggle") await Open();
            var livePowerSurvivedOpen = target.Powers.Any(power => ReferenceEquals(power, source));
            var fatalWithInitialDomain = target.Powers.All(power => power.ShouldOwnerDeathTriggerFatal());
            if (mode == "toggle") await PowerCmd.Remove<DomainPower>(owner.Creature);
            await CreatureCmd.Kill(target);
            var deathDepthAfterKill = DomainRevivalEffects.DeathDepthFor(source);
            var afterDeath = Snapshot(target, combat, source);
            MoveState? capturedCallback = null;
            if (mode == "late")
            {
                capturedCallback = family == "reattach"
                    ? (MoveState)target.Monster.MoveStateMachine!.States["REATTACH_MOVE"] : target.Monster.NextMove;
                await Open();
            }
            var afterOpen = Snapshot(target, combat, source);
            var normalMoves = new List<string>();
            var control = mode is "off" or "toggle";
            if (control)
            {
                if (family == "reattach")
                {
                    normalMoves.Add(target.Monster.NextMove.Id);
                    await target.Monster.PerformMove();
                    target.PrepareForNextTurn(combat.Players.Select(player => player.Creature));
                }
                normalMoves.Add(target.Monster.NextMove.Id);
                await target.Monster.PerformMove();
            }
            else
            {
                await PowerCmd.Remove<DomainPower>(owner.Creature);
                await DomainRevivalEffects.AfterDomainOpened(owner.Creature); // Domain is OFF: idempotent no-op regression, not a rescue call.
                if (capturedCallback is not null)
                    await capturedCallback.PerformMove(combat.Players.Select(player => player.Creature));
            }
            var afterExitOrRevive = Snapshot(target, combat, source);
            bool? minionFatalAfter = minion?.ShouldOwnerDeathTriggerFatal();
            CombatManager.Instance.CreaturesChanged -= managerRemoved; managerRemoved = null;
            var measuredDied = died; var measuredRemoved = sourceRemoved; var measuredAfterRemoved = afterRemoved;
            var victories = 0; var endings = 0;
            CombatManager.Instance.CombatWon += _ => victories++;
            CombatManager.Instance.CombatEnded += _ => endings++;
            var explicitWinCheck = !control;
            var checkResult = false;
            if (explicitWinCheck)
            {
                await CreatureCmd.Kill(combat.Enemies.Where(enemy => enemy.IsAlive).ToArray());
                checkResult = await CombatManager.Instance.CheckWinCondition();
            }
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing release metadata.");
            var result = new
            {
                token, scenario = "domain-revival", variant, completed = true, testMode = false,
                gameVersion = release.Version.StartsWith("v", StringComparison.Ordinal) ? release.Version[1..] : release.Version,
                gameCommit = release.Commit,
                acceptance = "formal-native-revival-mechanism-not-normal-card-or-enemy-turn",
                discovery = "native encounter and native deployed power",
                fixtureApi = "CreatureCmd.Kill;MonsterModel.PerformMove;Creature.PrepareForNextTurn;DomainPower.Open;PowerCmd.Remove",
                encounter = combat.Encounter.GetType().Name, nativeType, sourceType, sourceAmount,
                setupMoves, initial, initialFatal, minionFatalBefore, livePowerSurvivedOpen, fatalWithInitialDomain,
                beforeCachedOpen, afterDeath, afterOpen, afterExitOrRevive, normalMoves,
                reentry = capturedCallback is not null ? "captured-native-callback-after-cancel" : "none",
                died = measuredDied, sourceRemoved = measuredRemoved, afterRemoved = measuredAfterRemoved,
                managerNotifications, callbackCount, nativeBodiesExecuted, deathDepthAfterKill, trace, minionFatalAfter,
                explicitWinCheck, checkResult, victories, endings, inProgress = CombatManager.Instance.IsInProgress,
            };
            GD.Print("[Volibear] DOMAIN_REVIVAL_RESULT " + JsonSerializer.Serialize(result));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit();
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_REVIVAL_PROBE_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            if (callback is not null) DomainRevivalEffects.AfterDeathContribution -= callback;
            if (lifecycle is not null) DomainRevivalEffects.LifecycleObserved -= lifecycle;
            if (cleanup is not null) DomainRevivalEffects.PowerDeathCleanupCompleted -= cleanup;
            if (managerRemoved is not null) CombatManager.Instance.CreaturesChanged -= managerRemoved;
        }
    }
}
