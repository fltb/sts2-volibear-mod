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
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;
namespace Volibear;

/// <summary>Initial native side-start dispatcher fixture, installed BEFORE combat starts.
/// The dispatcher still invokes and awaits its exact original virtual callback with its native choice context.</summary>
internal static class InitialPlatingContractProbe
{
    private static bool _seen, _complete, _started;
    private static Creature? _owner, _target;
    private static CombatState? _combat;
    private static PlatingPower? _source;
    private static object? _before, _afterSource, _afterControls;
    private static string[] _participants = [];
    private static int _historyStart, _callbackRound;
    private static string? _callbackSide;
    private static decimal _controlBlockResult;
    private static int? _controlStrengthResult;
    private static readonly Harmony Observer = new("Volibear.InitialPlatingContractProbe");
    public static void Install()
    {
        var method = typeof(Hook).GetMethod("BeforeSideTurnStart")!;
        var machine = method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
        Observer.Patch(AccessTools.Method(machine, "MoveNext"), transpiler: new HarmonyMethod(typeof(InitialPlatingContractProbe), nameof(DispatchCall)));
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static IEnumerable<CodeInstruction> DispatchCall(IEnumerable<CodeInstruction> instructions)
    {
        var code = instructions.Select(c => new CodeInstruction(c)).ToArray(); int count = 0;
        foreach (var c in code)
            if (c.operand is MethodInfo m && m.DeclaringType == typeof(AbstractModel) && m.Name == "BeforeSideTurnStart")
            {
                var replacement = typeof(InitialPlatingContractProbe).GetMethod(nameof(Dispatch), BindingFlags.Static | BindingFlags.NonPublic)!;
                if (m.ReturnType != typeof(Task) || !m.GetParameters().Select(p => p.ParameterType).Prepend(typeof(AbstractModel))
                    .SequenceEqual(replacement.GetParameters().Select(p => p.ParameterType))) throw new InvalidOperationException("Native initial-side dispatcher changed");
                c.opcode = OpCodes.Call; c.operand = replacement; count++;
            }
        if (count != 1) throw new InvalidOperationException("Missing exact original native BeforeSideTurnStart dispatch");
        return code;
    }
    private static string Id(Creature c) => c.CombatId?.ToString() ?? throw new InvalidOperationException("Missing native ID");
    private static object Snapshot() => new { ownerId = Id(_owner!), targetId = Id(_target!), hp = _target!.CurrentHp, block = _target.Block,
        strength = _target.GetPowerAmount<StrengthPower>(), strengthInstances = _target.Powers.Count(p => p is StrengthPower),
        plating = _target.GetPowerAmount<PlatingPower>(), domain = _owner!.GetPowerAmount<DomainPower>(), playerHp = _owner.CurrentHp,
        round = _combat!.RoundNumber, side = _combat.CurrentSide.ToString(), targetAttached = _combat.ContainsCreature(_target),
        inProgress = CombatManager.Instance.IsInProgress, sameSourceIdentity = ReferenceEquals(_target.GetPower<PlatingPower>(), _source) };
    private static async Task Dispatch(AbstractModel model, PlayerChoiceContext context, CombatSide side, IReadOnlyList<Creature> participants, ICombatState state)
    {
        if (_seen || model is not PlatingPower plating || plating.Owner.Monster is not FrogKnight || state.RoundNumber != 1 || side != CombatSide.Player)
        {
            await model.BeforeSideTurnStart(context, side, participants, state);
            return;
        }
        _seen = true;
        try
        {
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE") ?? "";
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var release = ReleaseInfoManager.Instance.ReleaseInfo;
            if (string.IsNullOrWhiteSpace(token) || release is null || release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit ||
                variant is not ("plating-initial-off" or "plating-initial-on") || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Unsupported initial Plating fixture/token/version");
            _combat = (CombatState)state; _owner = state.Players.Single().Creature; _target = plating.Owner; _source = plating;
            if (state.Enemies.Count != 1 || plating.Amount != 15 || _target.Block != 0 || _target.GetPower<StrengthPower>() is not null ||
                _owner.CurrentHp != 80 || _owner.Block != 0 || _owner.GetPowerAmount<DomainPower>() != 0 ||
                participants.Count != 1 || !ReferenceEquals(participants[0], _owner))
                throw new InvalidOperationException("Expected first native player-side FrogKnight Plating15 callback");
            await CreatureCmd.SetMaxAndCurrentHp(_target, 1000m);
            if (variant == "plating-initial-on") await DomainPower.Open(context, _owner, 5);
            _participants = participants.Select(Id).ToArray(); _callbackRound = state.RoundNumber; _callbackSide = side.ToString(); _before = Snapshot();
            _historyStart = CombatManager.Instance.History.Entries.Count();
            // Forward the ORIGINAL native dispatcher invocation. No out-of-band callback invocation, skip, or fake task result.
            await model.BeforeSideTurnStart(context, side, participants, state);
            _afterSource = Snapshot();
            _controlBlockResult = await CreatureCmd.GainBlock(_target, 7m, ValueProp.Unpowered, null);
            _controlStrengthResult = (await PowerCmd.Apply<StrengthPower>(context, _target, 4m, _target, null))?.Amount;
            _afterControls = Snapshot(); _complete = true;
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_INITIAL_PLATING_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
            throw;
        }
    }
    private static void OnTurnStarted(CombatState state) { if (!_started) { _started = true; _ = Finish(state); } }
    private static async Task Finish(CombatState state)
    {
        try
        {
            var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE") ?? "";
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No release metadata");
            if (string.IsNullOrWhiteSpace(token) || release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit ||
                !_seen || !_complete || !ReferenceEquals(state, _combat) || state.RoundNumber != 1 || state.CurrentSide != CombatSide.Player)
                throw new InvalidOperationException("Initial native side-start receipt missing/stale/wrong release");
            var entries = CombatManager.Instance.History.Entries.Skip(_historyStart).ToArray();
            var blocks = entries.OfType<BlockGainedEntry>().Where(e => ReferenceEquals(e.Receiver, _target))
                .Select(e => new { targetId = Id(e.Receiver), amount = e.Amount, props = (int)e.Props }).ToArray();
            var powers = entries.OfType<PowerReceivedEntry>().Where(e => ReferenceEquals(e.Power.Owner, _target))
                .Select(e => new { targetId = Id(e.Power.Owner), power = e.Power.GetType().Name, amount = e.Amount,
                    applierId = e.Applier is null ? null : Id(e.Applier) }).ToArray();
            GD.Print("[Volibear] DOMAIN_INITIAL_PLATING_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-passive-contract", variant,
                acceptance = "native-first-side-dispatch-controlled-domain-fixture", testMode = false, version = release.Version, commit = release.Commit,
                fixture = "FrogKnightNormal", targetType = "FrogKnight", callback = "PlatingPower.BeforeSideTurnStart",
                callbackRound = _callbackRound, callbackSide = _callbackSide, participants = _participants,
                before = _before, afterSource = _afterSource, afterControls = _afterControls, final = Snapshot(),
                controlBlockInput = 7, controlStrengthInput = 4, controlBlockResult = _controlBlockResult, controlStrengthResult = _controlStrengthResult,
                blockHistory = blocks, powerHistory = powers, nativeMoveCount = entries.OfType<MonsterPerformedMoveEntry>().Count(),
                callbackObserved = _seen, callbackCompleted = _complete
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); tree.Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_INITIAL_PLATING_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally
        {
            _owner = null; _target = null; _source = null; _combat = null;
            Observer.UnpatchAll(Observer.Id); CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
