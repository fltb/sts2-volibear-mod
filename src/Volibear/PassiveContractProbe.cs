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
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>Controlled native-await mechanism fixture, NOT natural input/full enemy coverage.
/// Native end turns dispatch actual powers. Hook wrappers await the original hooks, then execute
/// explicit native fixture commands; no production adapter calls or fake powers/results.</summary>
internal static class PassiveContractProbe
{
    private static bool _started, _armed;
    private static string _family = "", _mode = "";
    private static Creature? _owner, _target;
    private static CombatState? _combat;
    private static readonly List<object> Receipts = [];
    private static readonly Harmony Observer = new("Volibear.PassiveContractObserver");
    private static readonly Dictionary<string, string> Hooks = new()
    {
        ["BeforeBlockGained"] = nameof(BeforeBlock), ["AfterBlockGained"] = nameof(AfterBlock),
        ["BeforePowerAmountChanged"] = nameof(BeforePower), ["AfterPowerAmountChanged"] = nameof(AfterPower)
    };
    public static void Install()
    {
        var native = new[]
        {
            typeof(CreatureCmd).GetMethods().Single(m => m.Name == "GainBlock" && m.GetParameters()[1].ParameterType == typeof(decimal)),
            typeof(PowerCmd).GetMethods().Single(m => m.Name == "Apply" && !m.IsGenericMethod),
            typeof(PowerCmd).GetMethod("ModifyAmount")!
        };
        foreach (var method in native)
        {
            var machine = method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
            Observer.Patch(AccessTools.Method(machine, "MoveNext"), transpiler: new HarmonyMethod(typeof(PassiveContractProbe), nameof(HookCalls)));
        }
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static IEnumerable<CodeInstruction> HookCalls(IEnumerable<CodeInstruction> instructions)
    {
        var code = instructions.Select(c => new CodeInstruction(c)).ToArray();
        int count = 0;
        foreach (var instruction in code)
        {
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(Hook) && Hooks.TryGetValue(method.Name, out var replacement))
            {
                var wrapper = typeof(PassiveContractProbe).GetMethod(replacement, BindingFlags.NonPublic | BindingFlags.Static)!;
                if (!method.GetParameters().Select(p => p.ParameterType).SequenceEqual(wrapper.GetParameters().Select(p => p.ParameterType)))
                    throw new InvalidOperationException("Native hook signature changed: " + method);
                instruction.opcode = OpCodes.Call; instruction.operand = wrapper; count++;
            }
        }
        if (count != 2) throw new InvalidOperationException("Expected exactly native before/after hooks in command body");
        return code;
    }
    private static void OnTurnStarted(CombatState state)
    {
        if (_started) return;
        _started = true; _ = Run(state);
    }
    private static string Id(Creature creature) => creature.CombatId?.ToString() ?? throw new InvalidOperationException("No combat ID");
    private static object Snapshot() => new
    {
        ownerId = Id(_owner!), targetId = Id(_target!), hp = _target!.CurrentHp,
        block = _target.Block, strength = _target.GetPowerAmount<StrengthPower>(),
        ritual = _target.GetPowerAmount<RitualPower>(), plating = _target.GetPowerAmount<PlatingPower>(),
        domain = _owner!.GetPowerAmount<DomainPower>(), playerHp = _owner.CurrentHp,
        round = _combat!.RoundNumber, side = _combat.CurrentSide.ToString(),
        targetAttached = _combat.ContainsCreature(_target), inProgress = CombatManager.Instance.IsInProgress
    };
    private static async Task BeforeBlock(ICombatState state, Creature target, decimal amount, ValueProp props, CardModel? card)
    {
        await Hook.BeforeBlockGained(state, target, amount, props, card);
        if (_family == "plating") await Gate("before", target, amount);
    }
    private static async Task AfterBlock(ICombatState state, Creature target, decimal amount, ValueProp props, CardModel? card)
    {
        await Hook.AfterBlockGained(state, target, amount, props, card);
        if (_family == "plating") await Gate("after", target, amount);
    }
    private static async Task BeforePower(ICombatState state, PowerModel power, decimal amount, Creature target, Creature? applier, CardModel? card)
    {
        await Hook.BeforePowerAmountChanged(state, power, amount, target, applier, card);
        if (_family == "ritual" && power is StrengthPower) await Gate("before", target, amount);
    }
    private static async Task AfterPower(ICombatState state, PlayerChoiceContext choices, PowerModel power, decimal amount, Creature? applier, CardModel? card)
    {
        await Hook.AfterPowerAmountChanged(state, choices, power, amount, applier, card);
        if (_family == "ritual" && power is StrengthPower) await Gate("after", power.Owner, amount);
    }
    private static async Task Gate(string stage, Creature target, decimal amount)
    {
        var expectedStage = _mode == "post" ? "after" : "before";
        if (!_armed || stage != expectedStage || !ReferenceEquals(target, _target) || amount != (_family == "ritual" ? 3m : 4m)) return;
        _armed = false;
        var before = Snapshot();
        var tree = (SceneTree)Engine.GetMainLoop();
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame); // Real suspension: exercise actual builder/task rebinding.
        var afterYield = Snapshot();
        var choices = new ThrowingPlayerChoiceContext();
        if (_mode is "open" or "post") await DomainPower.Open(choices, _owner!, 5);
        else if (_mode == "close") await PowerCmd.Remove<DomainPower>(_owner!);
        var afterToggle = Snapshot();
        // These are intentionally untagged native operations nested inside the owned contribution's await.
        var block = await CreatureCmd.GainBlock(target, 3m, ValueProp.Unpowered, null);
        var strength = await PowerCmd.Apply<StrengthPower>(choices, target, 2m, target, null);
        var strengthResult = strength?.Amount;
        Receipts.Add(new { stage, amount, before, afterYield, afterToggle, afterNested = Snapshot(),
            nestedBlockInput = 3, nestedStrengthInput = 2, nestedBlockResult = block, nestedStrengthResult = strengthResult });
    }
    private static async Task NextTurn(CombatState state, MegaCrit.Sts2.Core.Entities.Players.Player player)
    {
        if (player.Creature.Block > 0) await CreatureCmd.LoseBlock(player.Creature, player.Creature.Block);
        await CreatureCmd.GainBlock(player.Creature, 100m, ValueProp.Unpowered, null);
        int round = state.RoundNumber;
        PlayerCmd.EndTurn(player, canBackOut: false);
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (state.RoundNumber <= round || state.CurrentSide != CombatSide.Player || player.PlayerCombatState!.Phase != PlayerTurnPhase.Play)
        {
            if (timer.Elapsed > TimeSpan.FromSeconds(40)) throw new TimeoutException("Actual passive native turn did not finish");
            var tree = (SceneTree)Engine.GetMainLoop();
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE") ?? "";
            var parts = variant.Split('-');
            if (string.IsNullOrWhiteSpace(token) || parts.Length != 2 || parts[0] is not ("ritual" or "plating") ||
                parts[1] is not ("off" or "on" or "open" or "close" or "post") || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Unsupported passive probe variant/token/TestMode");
            _family = parts[0]; _mode = parts[1];
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No native version metadata");
            if (release.Version != "v0.107.1" || release.Commit != "59260271") throw new InvalidOperationException("Wrong pinned release");
            var player = state.Players.Single();
            _owner = player.Creature; _target = state.Enemies.Single(e => e.Monster is LeafSlimeS); _combat = state;
            if (_owner.CurrentHp != 80 || _owner.Block != 0 || state.RoundNumber != 1 || player.PlayerCombatState!.TurnNumber != 1 ||
                _owner.GetPowerAmount<DomainPower>() != 0 || _target.Block != 0 || _target.Powers.Count != 0)
                throw new InvalidOperationException("Expected fresh native SlimesWeak mechanism fixture");
            await CreatureCmd.SetMaxAndCurrentHp(_target, 1000m);
            var choices = new ThrowingPlayerChoiceContext();
            if (_mode is "on" or "close") await DomainPower.Open(choices, _owner, 5);
            var directBefore = Snapshot();
            var directStrength = await PowerCmd.Apply<StrengthPower>(choices, _target, 4m, _target, null);
            int? directStrengthResult = directStrength?.Amount;
            var directBlockResult = await CreatureCmd.GainBlock(_target, 7m, ValueProp.Unpowered, null);
            var directAfter = Snapshot();
            if (_family == "ritual") await PowerCmd.Apply<RitualPower>(choices, _target, 3m, _target, null);
            else await PowerCmd.Apply<PlatingPower>(choices, _target, 5m, _target, null);
            await NextTurn(state, player); // Actual first Ritual skip / first Plating contribution.
            var firstTurn = Snapshot();
            Receipts.Clear(); _armed = true;
            int historyStart = CombatManager.Instance.History.Entries.Count();
            await NextTurn(state, player); // Actual second source contribution, with controlled await fixture.
            var secondTurn = Snapshot();
            var history = CombatManager.Instance.History.Entries.Skip(historyStart).OfType<MonsterPerformedMoveEntry>()
                .Select(e => new { sourceId = Id(e.Monster.Creature), type = e.Monster.GetType().Name, move = e.Move.Id }).ToArray();
            var blockHistory = CombatManager.Instance.History.Entries.Skip(historyStart).OfType<BlockGainedEntry>()
                .Where(e => ReferenceEquals(e.Receiver, _target))
                .Select(e => new { targetId = Id(e.Receiver), amount = e.Amount, props = (int)e.Props }).ToArray();
            var powerHistory = CombatManager.Instance.History.Entries.Skip(historyStart).OfType<PowerReceivedEntry>()
                .Where(e => ReferenceEquals(e.Power.Owner, _target))
                .Select(e => new { targetId = Id(e.Power.Owner), power = e.Power.GetType().Name, amount = e.Amount,
                    applierId = e.Applier is null ? null : Id(e.Applier) }).ToArray();
            GD.Print("[Volibear] DOMAIN_PASSIVE_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-passive-contract", variant,
                acceptance = "controlled-native-await-mechanism-not-full-enemy-coverage", testMode = false,
                version = release.Version, commit = release.Commit,
                targetType = _target.Monster!.GetType().Name, fixture = "native-SlimesWeak+native-fixture-powers",
                api = "PowerCmd+CreatureCmd+PlayerCmd.EndTurn+actual-command-MoveNext-await-boundary",
                directBefore, directAfter, directStrengthInput = 4, directBlockInput = 7,
                directStrengthResult, directBlockResult, firstTurn, secondTurn, receipts = Receipts.ToArray(), history, blockHistory, powerHistory,
                armedAfter = _armed
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_PASSIVE_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            _armed = false; _owner = null; _target = null; _combat = null;
            Observer.UnpatchAll(Observer.Id);
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
