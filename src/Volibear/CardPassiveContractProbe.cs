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
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>Native encounter + real Strike card lifecycle controls. No source callbacks called directly.</summary>
internal static class CardPassiveContractProbe
{
    private static bool _started;
    private static Creature? _owner, _target;
    private static CombatState? _combat;
    private static string _family = "";
    private static readonly List<object> Attempts = [];
    private static readonly Harmony Observer = new("Volibear.CardPassiveContractObserver");
    public static void Install()
    {
        var gain = typeof(CreatureCmd).GetMethods().Single(m => m.Name == "GainBlock" && m.GetParameters()[1].ParameterType == typeof(decimal));
        var machine = gain.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
        Observer.Patch(AccessTools.Method(machine, "MoveNext"), transpiler: new HarmonyMethod(typeof(CardPassiveContractProbe), nameof(ObserveBlockCall)));
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    private static IEnumerable<CodeInstruction> ObserveBlockCall(IEnumerable<CodeInstruction> instructions)
    {
        int count = 0;
        var code = instructions.Select(c => new CodeInstruction(c)).ToArray();
        foreach (var instruction in code)
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(Hook) && method.Name == "BeforeBlockGained")
            {
                var wrapper = typeof(CardPassiveContractProbe).GetMethod(nameof(BeforeBlock), BindingFlags.NonPublic | BindingFlags.Static)!;
                if (!method.GetParameters().Select(p => p.ParameterType).SequenceEqual(wrapper.GetParameters().Select(p => p.ParameterType)))
                    throw new InvalidOperationException("Native before-block observation signature changed");
                instruction.opcode = OpCodes.Call; instruction.operand = wrapper; count++;
            }
        if (count != 1) throw new InvalidOperationException("Missing exact native before-block observation callsite");
        return code;
    }
    private static async Task BeforeBlock(ICombatState state, Creature target, decimal amount, ValueProp props, CardModel? card)
    {
        await Hook.BeforeBlockGained(state, target, amount, props, card);
        if (ReferenceEquals(target, _target) && props == ValueProp.Unpowered && card is null && amount == (_family == "curlup" ? 14m : 6m))
            Attempts.Add(new { amount, props = (int)props, cardSource = (string?)null, before = Snapshot() });
    }
    private static string Id(Creature creature) => creature.CombatId?.ToString() ?? throw new InvalidOperationException("Missing native identity");
    private static object Snapshot() => new
    {
        ownerId = Id(_owner!), targetId = Id(_target!), hp = _target!.CurrentHp, block = _target.Block,
        strength = _target.GetPowerAmount<StrengthPower>(), curlup = _target.GetPowerAmount<CurlUpPower>(),
        skittish = _target.GetPowerAmount<SkittishPower>(), curled = (_target.Monster as LouseProgenitor)?.Curled,
        latch = _target.GetPower<SkittishPower>()?.HasGainedBlockThisTurn,
        domain = _owner!.GetPowerAmount<DomainPower>(), playerHp = _owner.CurrentHp,
        round = _combat!.RoundNumber, side = _combat.CurrentSide.ToString(),
        targetAttached = _combat.ContainsCreature(_target), inProgress = CombatManager.Instance.IsInProgress
    };
    private static void OnTurnStarted(CombatState state)
    {
        if (_started) return;
        _started = true; _ = Run(state);
    }
    private static async Task NextTurn(CombatState state, Player player)
    {
        if (player.Creature.Block > 0) await NativeCompat.LoseBlock(player.Creature, player.Creature.Block);
        await CreatureCmd.GainBlock(player.Creature, 100m, ValueProp.Unpowered, null);
        int round = state.RoundNumber;
        PlayerCmd.EndTurn(player, canBackOut: false);
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (state.RoundNumber <= round || state.CurrentSide != CombatSide.Player || player.PlayerCombatState!.Phase != PlayerTurnPhase.Play)
        {
            if (timer.Elapsed > TimeSpan.FromSeconds(40)) throw new TimeoutException("Native card-passive end turn stalled");
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
            if (string.IsNullOrWhiteSpace(token) || parts.Length != 2 || parts[0] is not ("curlup" or "skittish") || parts[1] is not ("off" or "on") ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("Unsupported native card-passive fixture");
            _family = parts[0]; bool domain = parts[1] == "on";
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing release metadata");
            if (release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit) throw new InvalidOperationException("Wrong pinned release");
            var player = state.Players.Single(); var choices = new ThrowingPlayerChoiceContext();
            _combat = state; _owner = player.Creature;
            _target = _family == "curlup" ? state.Enemies.Single(e => e.Monster is LouseProgenitor)
                : state.Enemies.Single(e => e.Monster is PhantasmalGardener && e.SlotName == "first");
            if (_owner.CurrentHp != 80 || _owner.Block != 0 || _owner.GetPowerAmount<DomainPower>() != 0 || state.RoundNumber != 1 || player.PlayerCombatState!.TurnNumber != 1 ||
                _target.Block != 0 || _target.GetPowerAmount<StrengthPower>() != 0 ||
                (_family == "curlup" ? state.Enemies.Count != 1 || _target.GetPowerAmount<CurlUpPower>() != 14 || ((LouseProgenitor)_target.Monster!).Curled
                    : state.Enemies.Count != 4 || state.Enemies.Any(e => e.Monster is not PhantasmalGardener || e.GetPowerAmount<SkittishPower>() != 6 || e.GetPower<SkittishPower>()!.HasGainedBlockThisTurn)))
                throw new InvalidOperationException("Expected native ascension-zero encounter powers and fresh first turn");
            foreach (var enemy in state.Enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 1000m);
            if (domain) await DomainPower.Open(choices, _owner, 5);
            var directBefore = Snapshot();
            var directStrength = await PowerCmd.Apply<StrengthPower>(choices, _target, 4m, _target, null);
            int? directStrengthResult = directStrength?.Amount;
            var directBlockResult = await CreatureCmd.GainBlock(_target, 7m, ValueProp.Unpowered, null);
            var directAfter = Snapshot();
            await NativeCompat.LoseBlock(_target, _target.Block); // Explicit native fixture cleanup, not domain rollback.
            var beforeCards = Snapshot();
            Attempts.Clear();
            var cards = new Dictionary<CardModel, string>(ReferenceEqualityComparer.Instance);
            var batches = new List<object>();
            using var subscription = LightningBatches.Subscribe(_owner, (context, batch) =>
            {
                if (batch.Card is null || !cards.TryGetValue(batch.Card, out var cardRef)) throw new InvalidOperationException("Unbound native card/lightning identity");
                batches.Add(new { cardRef, baseDamage = batch.BaseDamage, amount = batch.Amount, count = batch.CountThisTurn,
                    targetIds = batch.Targets.Select(Id).ToArray(),
                    hits = batch.Results.Select(r => new { targetId = Id(r.Receiver), hpLost = r.HpLost, blocked = r.Blocked, overkill = r.Overkill }).ToArray() });
                return Task.CompletedTask;
            });
            async Task Play(string id)
            {
                var card = state.CreateCard<StrikeIronclad>(player); cards.Add(card, id);
                await CardPileCmd.Add(card, player.PlayerCombatState.Hand);
                await CardCmd.AutoPlay(choices, card, _target);
            }
            int historyStart = CombatManager.Instance.History.Entries.Count();
            await Play("strike-1");
            var firstCard = Snapshot();
            int attemptsAfterFirst = Attempts.Count;
            if (_target.Block > 0) await NativeCompat.LoseBlock(_target, _target.Block);
            var beforeSecond = Snapshot();
            await Play("strike-2");
            var secondCard = Snapshot();
            int attemptsAfterSecond = Attempts.Count;
            await NextTurn(state, player);
            var nextTurn = Snapshot();
            var rosterAfterTurn = state.Enemies.Select(e => new { id = Id(e), type = e.Monster!.GetType().Name,
                slot = e.SlotName, hp = e.CurrentHp, strength = e.GetPowerAmount<StrengthPower>(),
                enlarge = (e.Monster as PhantasmalGardener)?.EnlargeTriggers }).ToArray();
            if (_family == "curlup") await NextTurn(state, player); // Actual WEB -> CURL_AND_GROW; its direct block/Strength must remain.
            else await Play("strike-3"); // New player turn: native Skittish latch must have reset and trigger again.
            var final = Snapshot();
            var entries = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            var blockHistory = entries.OfType<BlockGainedEntry>().Where(e => ReferenceEquals(e.Receiver, _target))
                .Select(e => new { targetId = Id(e.Receiver), amount = e.Amount, props = (int)e.Props }).ToArray();
            var powerHistory = entries.OfType<PowerReceivedEntry>().Where(e => ReferenceEquals(e.Power.Owner, _target))
                .Select(e => new { targetId = Id(e.Power.Owner), power = e.Power.GetType().Name, amount = e.Amount,
                    applierId = e.Applier is null ? null : Id(e.Applier) }).ToArray();
            var moves = entries.OfType<MonsterPerformedMoveEntry>().Select(e => new
                { sourceId = Id(e.Monster.Creature), type = e.Monster.GetType().Name, slot = e.Monster.Creature.SlotName, move = e.Move.Id }).ToArray();
            GD.Print("[Volibear] DOMAIN_CARD_PASSIVE_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-passive-contract", variant,
                acceptance = "native-encounter-card-autoplay-contract-not-natural-input", testMode = false,
                version = release.Version, commit = release.Commit, targetType = _target.Monster!.GetType().Name,
                fixture = _family == "curlup" ? "LouseProgenitorNormal" : "PhantasmalGardenersElite",
                api = "native-encounter-powers+CardCmd.AutoPlay<StrikeIronclad>+PlayerCmd.EndTurn",
                directBefore, directAfter, directStrengthInput = 4, directBlockInput = 7, directStrengthResult, directBlockResult,
                beforeCards, firstCard, beforeSecond, secondCard, nextTurn, final,
                attempts = Attempts.ToArray(), attemptsAfterFirst, attemptsAfterSecond, blockHistory, powerHistory,
                moves, rosterAfterTurn, batches = batches.ToArray(), cardCount = cards.Count
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_CARD_PASSIVE_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            _owner = null; _target = null; _combat = null;
            Observer.UnpatchAll(Observer.Id);
            CombatManager.Instance.TurnStarted -= OnTurnStarted;
        }
    }
}
