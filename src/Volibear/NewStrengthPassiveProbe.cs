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

/// <summary>New Strength transaction fixture. No same-type nested creation before commit.</summary>
internal static class NewStrengthPassiveProbe
{
    private static bool _started, _armed;
    private static string _mode = "";
    private static Creature? _owner, _target;
    private static CombatState? _combat;
    private static PowerModel? _candidate;
    private static object? _candidateBefore;
    private static readonly List<object> Events = [], PostHooks = [], Gates = [];
    private static readonly Harmony Observer = new("Volibear.NewStrengthPassiveProbe");
    public static void Install()
    {
        foreach (var method in new[] { typeof(PowerCmd).GetMethods().Single(m => m.Name == "Apply" && !m.IsGenericMethod), typeof(PowerCmd).GetMethod("ModifyAmount")! })
        {
            var machine = method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
            Observer.Patch(AccessTools.Method(machine, "MoveNext"), transpiler: new HarmonyMethod(typeof(NewStrengthPassiveProbe), nameof(ObserveCalls)));
        }
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static IEnumerable<CodeInstruction> ObserveCalls(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var code = instructions.Select(c => new CodeInstruction(c)).ToArray(); int hooks = 0, applied = 0;
        foreach (var c in code)
        {
            if (c.operand is not MethodInfo method) continue;
            string? wrapper = method.DeclaringType == typeof(Hook) ? method.Name switch
            {
                "BeforePowerAmountChanged" => nameof(BeforePower), "AfterPowerAmountChanged" => nameof(AfterPower), _ => null
            } : null;
            if (wrapper is not null)
            {
                var replacement = typeof(NewStrengthPassiveProbe).GetMethod(wrapper, BindingFlags.Static | BindingFlags.NonPublic)!;
                if (!method.GetParameters().Select(p => p.ParameterType).SequenceEqual(replacement.GetParameters().Select(p => p.ParameterType)))
                    throw new InvalidOperationException("Native power observation signature changed");
                c.opcode = OpCodes.Call; c.operand = replacement; hooks++;
            }
            else if (method.DeclaringType == typeof(PowerModel) && method.Name == "AfterApplied")
            {
                c.opcode = OpCodes.Call; c.operand = typeof(NewStrengthPassiveProbe).GetMethod(nameof(AfterApplied), BindingFlags.Static | BindingFlags.NonPublic)!;
                applied++;
            }
        }
        bool newApply = __originalMethod.DeclaringType!.Name.StartsWith("<Apply>", StringComparison.Ordinal);
        if (hooks != 2 || applied != (newApply ? 1 : 0)) throw new InvalidOperationException("Native transaction observation anchors changed");
        return code;
    }
    private static string Id(Creature c) => c.CombatId?.ToString() ?? throw new InvalidOperationException("Missing native ID");
    private static object CreatureState(Creature c) => new { id = Id(c), hp = c.CurrentHp, block = c.Block,
        strength = c.GetPowerAmount<StrengthPower>(), strengthInstances = c.Powers.Count(p => p is StrengthPower) };
    private static object CandidateState() => new { observed = _candidate is not null, amount = _candidate?.Amount,
        ownerId = _candidate?.Owner is { } owner ? Id(owner) : null,
        applierId = _candidate?.Applier is { } applier ? Id(applier) : null,
        attached = _candidate is not null && _target!.Powers.Any(p => ReferenceEquals(p, _candidate)),
        currentIdentity = _candidate is not null && ReferenceEquals(_target!.GetPower<StrengthPower>(), _candidate) };
    private static object Snapshot() => new { ownerId = Id(_owner!), target = CreatureState(_target!),
        ritual = _target!.GetPowerAmount<RitualPower>(), domain = _owner!.GetPowerAmount<DomainPower>(),
        playerHp = _owner.CurrentHp, round = _combat!.RoundNumber, side = _combat.CurrentSide.ToString(),
        targetAttached = _combat.ContainsCreature(_target), inProgress = CombatManager.Instance.IsInProgress };
    private static void DisplayChanged() => Events.Add(new { kind = "display", delta = (int?)null, candidate = CandidateState() });
    private static void PowerApplied(PowerModel power)
    { if (ReferenceEquals(power, _candidate)) Events.Add(new { kind = "applied", delta = (int?)null, candidate = CandidateState() }); }
    private static void PowerIncreased(PowerModel power, int delta, bool silent)
    { if (ReferenceEquals(power, _candidate)) Events.Add(new { kind = "increased", delta = (int?)delta, candidate = CandidateState() }); }
    private static async Task BeforePower(ICombatState state, PowerModel power, decimal amount, Creature target, Creature? applier, CardModel? card)
    {
        await Hook.BeforePowerAmountChanged(state, power, amount, target, applier, card);
        if (_armed && ReferenceEquals(target, _target) && power is StrengthPower && amount == 3m && _candidate is null)
        {
            if (target.GetPower<StrengthPower>() is not null || power.Owner is not null || power.Amount != 0)
                throw new InvalidOperationException("New-Apply fixture unexpectedly has an existing/attached Strength");
            _candidate = power; _candidateBefore = CandidateState(); power.DisplayAmountChanged += DisplayChanged;
            await Gate("before");
        }
    }
    private static async Task AfterApplied(PowerModel power, Creature? applier, CardModel? card)
    {
        await power.AfterApplied(applier, card);
        if (ReferenceEquals(power, _candidate)) PostHooks.Add(new { kind = "AfterApplied", amount = power.Amount, candidate = CandidateState() });
    }
    private static async Task AfterPower(ICombatState state, PlayerChoiceContext choices, PowerModel power, decimal amount, Creature? applier, CardModel? card)
    {
        await Hook.AfterPowerAmountChanged(state, choices, power, amount, applier, card);
        if (ReferenceEquals(power, _candidate))
        {
            PostHooks.Add(new { kind = "AfterPowerAmountChanged", amount, candidate = CandidateState() });
            if (amount == 3m) await Gate("after");
        }
    }
    private static async Task Gate(string stage)
    {
        if (!_armed || stage != (_mode == "post" ? "after" : "before")) return;
        _armed = false;
        var before = Snapshot(); var candidateBefore = CandidateState();
        var tree = (SceneTree)Engine.GetMainLoop();
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        var afterYield = Snapshot();
        var choices = new ThrowingPlayerChoiceContext();
        if (_mode is "open" or "post") await DomainPower.Open(choices, _owner!, 5);
        else if (_mode == "close") await PowerCmd.Remove<DomainPower>(_owner!);
        var afterToggle = Snapshot();
        var block = await CreatureCmd.GainBlock(_target!, 3m, ValueProp.Unpowered, null);
        int? nestedStrength = null;
        // Same-type nesting is only permitted AFTER native ApplyInternal/history/posthooks committed.
        if (_mode == "post") nestedStrength = (await PowerCmd.Apply<StrengthPower>(choices, _target!, 2m, _target, null))?.Amount;
        Gates.Add(new { stage, before, candidateBefore, afterYield, afterToggle, afterNested = Snapshot(),
            candidateAfterNested = CandidateState(), nestedBlockInput = 3, nestedBlockResult = block,
            nestedStrengthInput = _mode == "post" ? 2 : 0, nestedStrengthResult = nestedStrength });
    }
    private static void OnTurnStarted(CombatState state) { if (!_started) { _started = true; _ = Run(state); } }
    private static async Task NextTurn(CombatState state, Player player)
    {
        if (player.Creature.Block > 0) await NativeCompat.LoseBlock(player.Creature, player.Creature.Block);
        await CreatureCmd.GainBlock(player.Creature, 100m, ValueProp.Unpowered, null);
        int round = state.RoundNumber; PlayerCmd.EndTurn(player, canBackOut: false);
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (state.RoundNumber <= round || state.CurrentSide != CombatSide.Player || player.PlayerCombatState!.Phase != PlayerTurnPhase.Play)
        {
            if (timer.Elapsed > TimeSpan.FromSeconds(40)) throw new TimeoutException("Native new-Apply turn stalled");
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE") ?? "";
            var parts = variant.Split('-');
            if (string.IsNullOrWhiteSpace(token) || parts.Length != 2 || parts[0] != "newapply" || parts[1] is not ("off" or "on" or "open" or "close" or "post") ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("Unsupported new-Apply fixture");
            _mode = parts[1];
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No version metadata");
            if (release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit) throw new InvalidOperationException("Wrong pinned version");
            var player = state.Players.Single(); _owner = player.Creature; _combat = state;
            _target = state.Enemies.Single(e => e.Monster is LeafSlimeS);
            var control = state.Enemies.Single(e => e.Monster is TwigSlimeS);
            if (state.Enemies.Count != 3 || state.RoundNumber != 1 || _owner.CurrentHp != 80 || _owner.Block != 0 ||
                _owner.GetPowerAmount<DomainPower>() != 0 || _target.Powers.Count != 0 || control.Powers.Count != 0)
                throw new InvalidOperationException("Expected fresh actual SlimesWeak/no-Strength fixture");
            foreach (var enemy in state.Enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 1000m);
            _target.PowerApplied += PowerApplied; _target.PowerIncreased += PowerIncreased;
            var choices = new ThrowingPlayerChoiceContext();
            if (_mode is "on" or "close") await DomainPower.Open(choices, _owner, 5);
            var initial = Snapshot(); var controlBefore = CreatureState(control);
            int? controlStrengthResult = (await PowerCmd.Apply<StrengthPower>(choices, control, 4m, control, null))?.Amount;
            var controlBlockResult = await CreatureCmd.GainBlock(control, 7m, ValueProp.Unpowered, null);
            var controlAfter = CreatureState(control);
            await PowerCmd.Apply<RitualPower>(choices, _target, 3m, _target, null);
            await NextTurn(state, player);
            var firstTurn = Snapshot(); bool candidateAfterFirst = _candidate is not null;
            _armed = true; int historyStart = CombatManager.Instance.History.Entries.Count();
            await NextTurn(state, player);
            var final = Snapshot(); var candidateFinal = CandidateState();
            var entries = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            var powerHistory = entries.OfType<PowerReceivedEntry>().Where(e => ReferenceEquals(e.Power, _candidate) || ReferenceEquals(e.Power.Owner, _target))
                .Select(e => new { power = e.Power.GetType().Name, amount = e.Amount, targetId = e.Power.Owner is { } owner ? Id(owner) : null, applierId = e.Applier is null ? null : Id(e.Applier) }).ToArray();
            var blockHistory = entries.OfType<BlockGainedEntry>().Where(e => ReferenceEquals(e.Receiver, _target))
                .Select(e => new { targetId = Id(e.Receiver), amount = e.Amount, props = (int)e.Props }).ToArray();
            var moves = entries.OfType<MonsterPerformedMoveEntry>().Select(e => new { sourceId = Id(e.Monster.Creature), type = e.Monster.GetType().Name, move = e.Move.Id }).ToArray();
            GD.Print("[Volibear] DOMAIN_NEW_APPLY_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-passive-contract", variant,
                acceptance = "controlled-native-new-apply-await-not-natural-input", testMode = false, version = release.Version, commit = release.Commit,
                fixture = "SlimesWeak+Ritual3+separate-TwigSlimeS-direct-controls", targetType = "LeafSlimeS", controlType = "TwigSlimeS",
                initial, controlBefore, controlAfter, controlStrengthInput = 4, controlBlockInput = 7, controlStrengthResult, controlBlockResult,
                firstTurn, candidateAfterFirst, candidateBefore = _candidateBefore, candidateFinal, final,
                events = Events.ToArray(), postHooks = PostHooks.ToArray(), gates = Gates.ToArray(), armedAfter = _armed,
                powerHistory, blockHistory, moves
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_NEW_APPLY_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally
        {
            if (_candidate is not null) _candidate.DisplayAmountChanged -= DisplayChanged;
            if (_target is not null) { _target.PowerApplied -= PowerApplied; _target.PowerIncreased -= PowerIncreased; }
            _armed = false; _candidate = null; _owner = null; _target = null; _combat = null;
            Observer.UnpatchAll(Observer.Id); CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
