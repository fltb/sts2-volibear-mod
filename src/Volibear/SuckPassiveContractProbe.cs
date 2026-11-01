using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;
namespace Volibear;

/// <summary>Actual FossilStalker LATCH blocked control, then native LASH two-hit Suck contribution.</summary>
internal static class SuckPassiveContractProbe
{
    private static bool _started, _collect;
    private static Creature? _owner, _target;
    private static CombatState? _combat;
    private static StrengthPower? _strength;
    private static readonly List<object> Attacks = [], Events = [], PostHooks = [];
    private static readonly Harmony Observer = new("Volibear.SuckPassiveContractProbe");
    public static void Install()
    {
        var source = typeof(SuckPower).GetMethod("AfterAttack")!;
        var machine = source.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
        foreach (var (name, type) in new[] { ("<>1__state", typeof(int)), ("<>4__this", typeof(SuckPower)), ("command", typeof(AttackCommand)) })
            if (machine.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.FieldType != type)
                throw new InvalidOperationException("Native Suck state observation shape changed: " + name);
        var sourceMove = AccessTools.Method(machine, "MoveNext");
        Observer.Patch(sourceMove, prefix: new HarmonyMethod(typeof(SuckPassiveContractProbe), nameof(ObserveSource)));
        var modify = typeof(PowerCmd).GetMethod("ModifyAmount")!;
        Observer.Patch(AccessTools.Method(modify.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext"),
            transpiler: new HarmonyMethod(typeof(SuckPassiveContractProbe), nameof(ObservePostCall)));
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static void ObserveSource(object __instance)
    {
        var t = __instance.GetType(); var flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        if ((int)t.GetField("<>1__state", flags)!.GetValue(__instance)! != -1 || !_collect) return;
        var source = (SuckPower)t.GetField("<>4__this", flags)!.GetValue(__instance)!;
        var command = (AttackCommand)t.GetField("command", flags)!.GetValue(__instance)!;
        if (!ReferenceEquals(source.Owner, _target) || !ReferenceEquals(command.Attacker, _target)) return;
        // Copy scalar results BEFORE native Suck's pet de-duplication. Never change Results or native counters.
        Attacks.Add(new { before = Snapshot(), sourceAmount = source.Amount, attackerId = Id(command.Attacker!),
            targetSide = command.TargetSide.ToString(), props = (int)command.DamageProps,
            hits = command.Results.Select(hit => hit.Select(r => new { receiverId = Id(r.Receiver),
                unblocked = r.UnblockedDamage, blocked = r.BlockedDamage, overkill = r.OverkillDamage,
                total = r.TotalDamage, fullyBlocked = r.WasFullyBlocked, killed = r.WasTargetKilled }).ToArray()).ToArray() });
    }
    private static IEnumerable<CodeInstruction> ObservePostCall(IEnumerable<CodeInstruction> instructions)
    {
        var code = instructions.Select(c => new CodeInstruction(c)).ToArray(); int count = 0;
        foreach (var c in code)
            if (c.operand is MethodInfo m && m.DeclaringType == typeof(Hook) && m.Name == "AfterPowerAmountChanged")
            {
                var replacement = typeof(SuckPassiveContractProbe).GetMethod(nameof(AfterPower), BindingFlags.NonPublic | BindingFlags.Static)!;
                if (!m.GetParameters().Select(p => p.ParameterType).SequenceEqual(replacement.GetParameters().Select(p => p.ParameterType)))
                    throw new InvalidOperationException("Suck observation signature changed");
                c.opcode = OpCodes.Call; c.operand = replacement; count++;
            }
        if (count != 1) throw new InvalidOperationException("Missing native ModifyAmount posthook");
        return code;
    }
    private static async Task AfterPower(ICombatState state, PlayerChoiceContext choices, PowerModel power, decimal amount, Creature? applier, CardModel? card)
    {
        await Hook.AfterPowerAmountChanged(state, choices, power, amount, applier, card);
        if (_collect && ReferenceEquals(power, _strength)) PostHooks.Add(new { amount, strength = power.Amount, sameIdentity = ReferenceEquals(_target!.GetPower<StrengthPower>(), power) });
    }
    private static string Id(Creature c) => c.CombatId?.ToString() ?? throw new InvalidOperationException("Missing native ID");
    private static object Snapshot() => new { ownerId = Id(_owner!), targetId = Id(_target!), hp = _target!.CurrentHp,
        block = _target.Block, strength = _target.GetPowerAmount<StrengthPower>(), strengthInstances = _target.Powers.Count(p => p is StrengthPower),
        suck = _target.GetPowerAmount<SuckPower>(), domain = _owner!.GetPowerAmount<DomainPower>(), playerHp = _owner.CurrentHp, playerBlock = _owner.Block,
        round = _combat!.RoundNumber, side = _combat.CurrentSide.ToString(), targetAttached = _combat.ContainsCreature(_target), inProgress = CombatManager.Instance.IsInProgress };
    private static void DisplayChanged() { if (_collect) Events.Add(new { kind = "display", delta = (int?)null, strength = _strength!.Amount }); }
    private static void PowerIncreased(PowerModel power, int delta, bool silent)
    { if (_collect && ReferenceEquals(power, _strength)) Events.Add(new { kind = "increased", delta = (int?)delta, strength = power.Amount }); }
    private static void PowerApplied(PowerModel power)
    { if (_collect && power is StrengthPower) Events.Add(new { kind = "applied", delta = (int?)null, strength = power.Amount }); }
    private static void OnTurnStarted(CombatState state) { if (!_started) { _started = true; _ = Run(state); } }
    private static async Task<object> NextTurn(CombatState state, Player player, decimal block)
    {
        if (player.Creature.Block > 0) await CreatureCmd.LoseBlock(player.Creature, player.Creature.Block);
        if (block > 0) await CreatureCmd.GainBlock(player.Creature, block, ValueProp.Unpowered, null);
        var before = Snapshot(); int round = state.RoundNumber; PlayerCmd.EndTurn(player, canBackOut: false);
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (state.RoundNumber <= round || state.CurrentSide != CombatSide.Player || player.PlayerCombatState!.Phase != PlayerTurnPhase.Play)
        {
            if (timer.Elapsed > TimeSpan.FromSeconds(40)) throw new TimeoutException("Native Suck turn stalled");
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
        return before;
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE") ?? "";
            if (string.IsNullOrWhiteSpace(token) || variant is not ("suck-off" or "suck-on") || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Unsupported Suck fixture");
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing native release");
            if (release.Version != "v0.107.1" || release.Commit != "59260271") throw new InvalidOperationException("Wrong native release");
            var player = state.Players.Single(); _owner = player.Creature; _combat = state;
            _target = state.Enemies.Single(e => e.Monster is FossilStalker);
            if (state.Enemies.Count != 1 || state.RoundNumber != 1 || _owner.CurrentHp != 80 || _owner.Block != 0 || _owner.GetPowerAmount<DomainPower>() != 0 ||
                _target.Block != 0 || _target.GetPowerAmount<StrengthPower>() != 0 || _target.GetPowerAmount<SuckPower>() != 3)
                throw new InvalidOperationException("Expected fresh native FossilStalker/Suck3 fixture");
            await CreatureCmd.SetMaxAndCurrentHp(_target, 1000m);
            var choices = new ThrowingPlayerChoiceContext();
            if (variant == "suck-on") await DomainPower.Open(choices, _owner, 5);
            var directBefore = Snapshot();
            var controlStrength = await PowerCmd.Apply<StrengthPower>(choices, _target, 4m, _target, null);
            int? controlStrengthResult = controlStrength?.Amount;
            var controlBlockResult = await CreatureCmd.GainBlock(_target, 7m, ValueProp.Unpowered, null);
            var directAfter = Snapshot();
            _strength = _target.GetPower<StrengthPower>() ?? throw new InvalidOperationException("Direct Strength missing");
            _strength.DisplayAmountChanged += DisplayChanged; _target.PowerIncreased += PowerIncreased; _target.PowerApplied += PowerApplied;
            _collect = true; int historyStart = CombatManager.Instance.History.Entries.Count();
            var initialMove = _target.Monster!.NextMove.Id;
            var blockedStart = await NextTurn(state, player, 16m); // Native first LATCH12 + existing Strength4: fully blocked.
            var blockedEnd = Snapshot(); int eventsAfterBlocked = Events.Count, hooksAfterBlocked = PostHooks.Count;
            var machine = _target.Monster!.MoveStateMachine ?? throw new InvalidOperationException("No native move machine");
            _target.Monster.SetMoveImmediate((MoveState)machine.States["LASH_MOVE"], forceTransition: true);
            var selectedMove = _target.Monster.NextMove.Id; // Existing reachable native state/delegate, never a synthesized damage move.
            var lashStart = await NextTurn(state, player, 0m);
            var final = Snapshot();
            var entries = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            var powerHistory = entries.OfType<PowerReceivedEntry>().Where(e => ReferenceEquals(e.Power.Owner, _target))
                .Select(e => new { power = e.Power.GetType().Name, amount = e.Amount, targetId = Id(e.Power.Owner), applierId = e.Applier is null ? null : Id(e.Applier) }).ToArray();
            var moves = entries.OfType<MonsterPerformedMoveEntry>().Select(e => new { sourceId = Id(e.Monster.Creature), type = e.Monster.GetType().Name, move = e.Move.Id }).ToArray();
            GD.Print("[Volibear] DOMAIN_SUCK_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-passive-contract", variant,
                acceptance = "native-encounter-endturn-controlled-existing-move-not-natural-input", testMode = false, version = release.Version, commit = release.Commit,
                fixture = "FossilStalkerNormal", targetType = "FossilStalker", directBefore, directAfter,
                controlStrengthInput = 4, controlBlockInput = 7, controlStrengthResult, controlBlockResult,
                initialMove, selectedMove, selectionApi = "MonsterModel.SetMoveImmediate(existing-native-LASH_MOVE)",
                blockedStart, blockedEnd, eventsAfterBlocked, hooksAfterBlocked, lashStart, final,
                attacks = Attacks.ToArray(), events = Events.ToArray(), postHooks = PostHooks.ToArray(), powerHistory, moves,
                sameStrengthIdentity = ReferenceEquals(_strength, _target.GetPower<StrengthPower>())
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_SUCK_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally
        {
            _collect = false;
            if (_strength is not null) _strength.DisplayAmountChanged -= DisplayChanged;
            if (_target is not null) { _target.PowerIncreased -= PowerIncreased; _target.PowerApplied -= PowerApplied; }
            _strength = null; _owner = null; _target = null; _combat = null;
            Observer.UnpatchAll(Observer.Id); CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
