using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>
/// Actual native encounters/moves/death, controlled mechanism probe, NOT complete enemy coverage.
/// No replaced delegates, direct adapter/helper calls, TestMode or pretend damage/intent execution.
/// Expected values live in the external evidence gate; all receipts here are raw observations.
/// </summary>
internal static class DomainSummonContractProbe
{
    private static bool _started;
    private static Creature? _parent;
    private static Creature? _owner;
    private static CombatState? _combat;
    private static readonly Harmony Observer = new("Volibear.DomainSummonContractObserver");
    private static readonly List<object> CallbackReceipts = [];

    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(ObserveInfestedCallback)).Patch();
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static void OnTurnStarted(CombatState state)
    {
        if (_started) return;
        _started = true;
        _ = Run(state);
    }
    private static string Id(Creature creature) => creature.CombatId?.ToString() ??
        throw new InvalidOperationException("Missing actual combat identity");

    private static object Enemy(Creature enemy) => new
    {
        id = Id(enemy), type = enemy.Monster!.GetType().Name, slot = enemy.SlotName,
        hp = enemy.CurrentHp, maxHp = enemy.MaxHp, block = enemy.Block,
        minion = enemy.GetPowerAmount<MinionPower>(), infested = enemy.GetPowerAmount<InfestedPower>(),
        hatch = enemy.GetPowerAmount<HatchPower>(), nextMove = enemy.Monster.NextMove.Id,
        startStunned = enemy.Monster is Wriggler wriggler ? (bool?)wriggler.StartStunned : null
    };
    private static object Snapshot(CombatState state, Creature parent, Creature owner) => new
    {
        parentId = Id(parent), playerId = Id(owner), parentHp = parent.CurrentHp, parentMaxHp = parent.MaxHp,
        parentAttached = state.ContainsCreature(parent), parentInfested = parent.GetPowerAmount<InfestedPower>(),
        playerHp = owner.CurrentHp, playerBlock = owner.Block, domain = owner.GetPowerAmount<DomainPower>(),
        inProgress = CombatManager.Instance.IsInProgress, isEnding = CombatManager.Instance.IsEnding,
        round = state.RoundNumber, side = state.CurrentSide.ToString(),
        enemies = state.Enemies.Select(Enemy).ToArray()
    };
    private static object[] DamageSince(int start) => CombatManager.Instance.History.Entries.Skip(start)
        .OfType<DamageReceivedEntry>().Select(entry => (object)new
        {
            sourceId = entry.Dealer is null ? null : Id(entry.Dealer), receiverId = Id(entry.Receiver),
            hpLost = entry.Result.UnblockedDamage, blocked = entry.Result.BlockedDamage,
            overkill = entry.Result.OverkillDamage, cardSource = entry.CardSource?.GetType().Name
        }).ToArray();
    private static object[] MovesSince(int start) => CombatManager.Instance.History.Entries.Skip(start)
        .OfType<MonsterPerformedMoveEntry>().Select(entry => (object)new
        {
            sourceId = Id(entry.Monster.Creature), move = entry.Move.Id,
            targets = entry.Targets?.Select(Id).ToArray()
        }).ToArray();

    private static async Task Run(CombatState state)
    {
        Action<Creature>? died = null;
        Action<CombatRoom>? won = null;
        Action<CombatRoom>? ended = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_SUMMON_CASE") ?? "";
            var variants = new[] { "fabricator-off", "fabricator-on", "ovicopter-off", "ovicopter-on",
                "infested-off", "infested-on", "infested-expire" };
            if (string.IsNullOrWhiteSpace(token) || !variants.Contains(variant) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Invalid isolated native summon probe token/case/TestMode");
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No release metadata");
            if (release.Version != "v0.107.1" || release.Commit != "59260271") throw new InvalidOperationException("Wrong pinned version");
            var player = state.Players.Single();
            var owner = player.Creature;
            var parent = state.Enemies.Single();
            var encounter = state.Encounter ?? throw new InvalidOperationException("Missing actual encounter");
            var family = variant.Split('-')[0];
            var expectedType = family == "fabricator" ? typeof(Fabricator) : family == "ovicopter" ? typeof(Ovicopter) : typeof(PhrogParasite);
            var expectedEncounter = family == "fabricator" ? "FabricatorNormal" : family == "ovicopter" ? "OvicopterNormal" : "PhrogParasiteElite";
            if (parent.Monster!.GetType() != expectedType || encounter.GetType().Name != expectedEncounter ||
                state.RoundNumber != 1 || state.CurrentSide != CombatSide.Player || player.PlayerCombatState!.TurnNumber != 1 ||
                owner.CurrentHp != 80 || owner.Block != 0 || owner.GetPowerAmount<DomainPower>() != 0 || parent.Block != 0 ||
                parent.GetPowerAmount<InfestedPower>() != (family == "infested" ? 4 : 0))
                throw new InvalidOperationException("Wrong untouched native encounter/bootstrap fixture");
            _parent = parent; _owner = owner; _combat = state;
            CallbackReceipts.Clear();
            // Fixed lethal input is independent of randomized native initial HP, via an ordinary native fixture command.
            await CreatureCmd.SetMaxAndCurrentHp(parent, 100m);
            var choices = new ThrowingPlayerChoiceContext();
            if (!variant.EndsWith("-off", StringComparison.Ordinal)) await DomainPower.Open(choices, owner, 2);
            var before = Snapshot(state, parent, owner);
            int historyStart = CombatManager.Instance.History.Entries.Count();
            object data;
            if (family != "infested")
            {
                var model = parent.Monster;
                var machine = model.MoveStateMachine ?? throw new InvalidOperationException("No actual move machine");
                string requested = family == "fabricator" ? "FABRICATING_STRIKE_MOVE" : "LAY_EGGS_MOVE";
                var initialMove = model.NextMove.Id;
                if (family == "fabricator")
                    model.SetMoveImmediate((MoveState)machine.States[requested], forceTransition: true);
                else if (model.NextMove.Id != requested)
                    throw new InvalidOperationException("Ovicopter did not begin with its actual native LayEggs move");
                var selected = model.NextMove.Id;
                var stateLogBefore = machine.StateLog.Select(s => s.Id).ToArray();
                var performingBefore = model.IsPerformingMove;
                await model.PerformMove().WaitAsync(TimeSpan.FromSeconds(35));
                var afterMove = Snapshot(state, parent, owner);
                var moves = MovesSince(historyStart);
                var damage = DamageSince(historyStart);
                var performingAfter = model.IsPerformingMove;
                // The native executor normally rolls after completion; call its real roll, not an assigned next intent.
                model.RollMove(state.PlayerCreatures);
                data = new
                {
                    api = "MonsterModel.PerformMove+MonsterModel.RollMove", initialMove, selected,
                    setup = family == "fabricator" ? "forced-existing-legal-reachable-FABRICATING_STRIKE_MOVE" : "native-initial-LAY_EGGS_MOVE",
                    performingBefore, performingAfter, stateLogBefore,
                    stateLogAfter = machine.StateLog.Select(s => s.Id).ToArray(), nextMove = model.NextMove.Id,
                    before, after = afterMove, moves, damage
                };
            }
            else
            {
                int wonCount = 0, endedCount = 0;
                won = _ => wonCount++;
                ended = _ => endedCount++;
                CombatManager.Instance.CombatWon += won;
                CombatManager.Instance.CombatEnded += ended;
                Task? removal = null;
                var diedReceipts = new List<object>();
                died = target =>
                {
                    var domainBefore = owner.GetPowerAmount<DomainPower>();
                    if (variant == "infested-expire") removal = PowerCmd.Remove<DomainPower>(owner);
                    // RemoveInternal runs before native Remove's first await. Observe, never assume, the actual amount.
                    diedReceipts.Add(new
                    {
                        targetId = Id(target), sameParent = ReferenceEquals(target, parent), hp = target.CurrentHp,
                        domainBefore, domainAfter = owner.GetPowerAmount<DomainPower>(),
                        removedByFixture = removal is not null
                    });
                };
                parent.Died += died;
                var results = (await CreatureCmd.Damage(choices, parent, 100m,
                    ValueProp.Unblockable | ValueProp.Unpowered, owner, null).WaitAsync(TimeSpan.FromSeconds(35)))
                    .Select(r => new { receiverId = Id(r.Receiver), hpLost = r.UnblockedDamage,
                        blocked = r.BlockedDamage, overkill = r.OverkillDamage }).ToArray();
                if (removal is not null) await removal.WaitAsync(TimeSpan.FromSeconds(10));
                var after = Snapshot(state, parent, owner);
                var damage = DamageSince(historyStart);
                var moves = MovesSince(historyStart);
                var winResult = await CombatManager.Instance.CheckWinCondition().WaitAsync(TimeSpan.FromSeconds(35));
                data = new
                {
                    api = "CreatureCmd.Damage+native-Kill/AfterDeath+CombatManager.CheckWinCondition",
                    setup = variant == "infested-expire" ? "controlled-native-Died-domain-removal-not-natural-draw-expiry" : "native-PhrogParasite-InfestedPower",
                    input = new { amount = 100, props = 6, sourceId = Id(owner), targetId = Id(parent) },
                    before, after, results, damage, moves, diedReceipts,
                    callbackReceipts = CallbackReceipts.ToArray(), winResult, wonCount, endedCount,
                    finalInProgress = CombatManager.Instance.IsInProgress,
                    finalEnemies = state.Enemies.Select(Enemy).ToArray()
                };
            }
            GD.Print("[Volibear] DOMAIN_SUMMON_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-summon-contract", variant,
                acceptance = "native-mechanism-probe-not-complete-enemy-coverage",
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                version = release.Version, commit = release.Commit, encounter = encounter.GetType().Name,
                parentType = parent.Monster!.GetType().Name, fixtureHp = 100, fixtureApi = "CreatureCmd.SetMaxAndCurrentHp",
                data
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_SUMMON_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            if (_parent is not null && died is not null) _parent.Died -= died;
            if (won is not null) CombatManager.Instance.CombatWon -= won;
            if (ended is not null) CombatManager.Instance.CombatEnded -= ended;
            _parent = null; _owner = null; _combat = null;
            Observer.UnpatchAll(Observer.Id);
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }

    // Read-only receipt from the actual native dispatcher call. Never invokes the handler,
    // swaps its Task, alters arguments, or synthesizes a phase. A missing receipt FAILS the gate.
    [HarmonyPatch(typeof(InfestedPower), nameof(InfestedPower.AfterDeath),
        [typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float)])]
    private static class ObserveInfestedCallback
    {
        private static void Postfix(InfestedPower __instance, Creature __1, bool __2, Task __result)
        {
            if (_parent is null || _owner is null || _combat is null || !ReferenceEquals(__instance.Owner, _parent)) return;
            CallbackReceipts.Add(new
            {
                ownerId = Id(__instance.Owner), targetId = Id(__1), prevented = __2,
                ownerHp = __instance.Owner.CurrentHp, attached = _combat.ContainsCreature(__instance.Owner),
                infested = __instance.Amount, domain = _owner.GetPowerAmount<DomainPower>(),
                // This normal public getter naturally queries all native ending votes, while Infested is still attached.
                isEnding = CombatManager.Instance.IsEnding,
                taskCompleted = __result.IsCompletedSuccessfully
            });
        }
    }
}
