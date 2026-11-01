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
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using Volibear.Core;

namespace Volibear;

/// <summary>Explicitly instrumented native fixture; not ordinary input and never invokes a private power/move callback.</summary>
internal static class DomainDampenTransactionsProbe
{
    private const string Id = "Volibear.DomainDampenTransactionsProbe";
    private static readonly HashSet<string> Cases = ["off", "on", "enter-await", "exit-await", "enter-pair", "exit-pair", "departure"];
    public static string Case => System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DAMPEN_CASE") ?? "";
    public static EncounterModel Encounter => ModelDb.Encounter<KnightsElite>();
    private static bool _installed, _started, _waitUsed, _pairUsed;
    private static CombatState _state = null!;
    private static Creature _owner = null!, _source = null!;
    private static DampenPower? _sourcePower;
    private static string _phase = "setup";
    private static readonly List<object> Boundaries = [];
    private static readonly List<Task> SwitchTasks = [];
    private static readonly ThrowingPlayerChoiceContext Choices = new();
    private static bool Domain => DomainEnemyEffects.ActiveFor(_state);
    private static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
    private static uint CardId(CardModel card) => NetCombatCardDb.Instance.TryGetCardId(card, out var id) ? id : throw new InvalidOperationException("native card ID absent");
    private static uint CreatureId(Creature creature) => creature.CombatId ?? throw new InvalidOperationException("native creature ID absent");
    private static Task SetDomain(bool on) => on ? DomainPower.Open(Choices, _owner, 5) : PowerCmd.Remove<DomainPower>(_owner);
    private static object Data(DampenPower power)
    {
        var data = AccessTools.Field(typeof(PowerModel), "_internalData").GetValue(power)!;
        Require(data.GetType().DeclaringType == typeof(DampenPower), "Dampen internal data layout drifted"); return data;
    }
    private static Dictionary<CardModel, int> Ledger(DampenPower power) => (Dictionary<CardModel, int>)AccessTools.Field(Data(power).GetType(), "downgradedCardsToOldUpgradeLevels").GetValue(Data(power))!;
    private static HashSet<Creature> Casters(DampenPower power) => (HashSet<Creature>)AccessTools.Field(Data(power).GetType(), "casters").GetValue(Data(power))!;
    public static void Install()
    {
        Require(System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "domain-dampen-transactions" && Cases.Contains(Case), "explicit isolated Dampen fixture required");
        if (_installed) return;
        DomainDampenTransactions.Install(); InstallBoundaryPatches();
        CombatManager.Instance.TurnStarted += OnTurn; _installed = true;
    }
    private static MethodInfo MoveNext(MethodInfo method) => AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
    internal static void InstallBoundaryPatches()
    {
        var harmony = new Harmony(Id);
        var apply = AccessTools.Method(typeof(PowerCmd), "Apply", [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)]);
        try
        {
            harmony.Patch(MoveNext(apply), transpiler: new HarmonyMethod(typeof(DomainDampenTransactionsProbe), nameof(WaitBoundary))
                { priority = Priority.Last, after = ["Volibear.DomainDampenTransactions"] });
            harmony.Patch(MoveNext(AccessTools.Method(typeof(MonsterModel), "PerformMove")), transpiler: new HarmonyMethod(typeof(DomainDampenTransactionsProbe), nameof(WaitBoundary))
                { priority = Priority.Last, after = ["Volibear.DomainDampenTransactions", "Volibear.DomainRevivalEffects"] });
        }
        catch { harmony.UnpatchAll(Id); throw; }
    }
    private static IEnumerable<CodeInstruction> WaitBoundary(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var code = input.Select(c => new CodeInstruction(c)).ToList();
        bool apply = __originalMethod.DeclaringType!.DeclaringType == typeof(PowerCmd);
        var wait = AccessTools.Method(typeof(Cmd), nameof(Cmd.CustomScaledWait));
        var indices = code.Select((c, i) => (c, i)).Where(p => p.c.Calls(wait)).Select(p => p.i).ToArray();
        // Revival may have replaced the outer LAST wait; this intentionally instruments only the original FIRST wait.
        Require(apply ? indices.Length == 1 : indices.Length is 1 or 2, "native wait boundary changed");
        int index = indices[0];
        var field = AccessTools.Field(__originalMethod.DeclaringType, apply ? "power" : "<>4__this");
        Require(field.FieldType == (apply ? typeof(PowerModel) : typeof(MonsterModel)), "native wait owner drifted");
        code.InsertRange(index + 1, new CodeInstruction[] { new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, field),
            new(OpCodes.Call, AccessTools.Method(typeof(DomainDampenTransactionsProbe), apply ? nameof(PowerWait) : nameof(OuterWait))) });
        return code;
    }
    private static Task PowerWait(Task native, PowerModel power) => _phase == "source" && !_waitUsed &&
        ReferenceEquals(power, _sourcePower) && Case is "enter-await" or "exit-await" ? ChangeAfterWait(native) : native;
    private static async Task ChangeAfterWait(Task native)
    {
        _waitUsed = true; bool before = Domain; await native;
        await SetDomain(Case == "enter-await");
        Boundaries.Add(new { kind = "instrumented-native-power-wait-continuation", before, after = Domain, originalWaitCompleted = native.IsCompletedSuccessfully });
    }
    private static Task OuterWait(Task native, MonsterModel source) => _phase == "source" && !_waitUsed && Case == "departure" &&
        ReferenceEquals(source, _source.Monster) ? DepartAfterWait(native) : native;
    private static async Task DepartAfterWait(Task native)
    {
        _waitUsed = true; bool attachedBefore = _state.ContainsCreature(_source); await native;
        // Keep the native visual node for the still-running native dialogue; membership really leaves the combat.
        await CreatureCmd.Escape(_source, removeCreatureNode: false); await SetDomain(true);
        Boundaries.Add(new { kind = "instrumented-native-outer-wait-departure", attachedBefore,
            attachedAfter = _state.ContainsCreature(_source), sourceCombatNull = _source.CombatState is null,
            originalWaitCompleted = native.IsCompletedSuccessfully, after = Domain });
    }
    private static void OnTurn(CombatState state) { if (_started) return; _started = true; _ = Run(state); }
    private static async Task Until(Func<bool> ready)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew(); var tree = (SceneTree)Engine.GetMainLoop();
        while (!ready()) { if (watch.Elapsed > TimeSpan.FromSeconds(60)) throw new TimeoutException("Dampen fixture wait"); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame); }
    }
    private static async Task Run(CombatState state)
    {
        Action<PowerModel>? applied = null;
        Action<DomainDampenTransactions.PairObservation>? observed = null;
        var subscriptions = new List<(CardModel card, Action callback)>();
        try
        {
            _state = state; var player = state.Players.Single(); _owner = player.Creature;
            _source = state.Enemies.Single(e => e.Monster is MagiKnight);
            string token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            Require(!string.IsNullOrWhiteSpace(token) && !MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn && release.Version == "v0.107.1" && release.Commit == "59260271", "wrong pinned native fixture");
            Require(state.RoundNumber == 1 && player.PlayerCombatState!.TurnNumber == 1 && _owner.CurrentHp == 80 && _owner.Block == 0 && !Domain &&
                ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState()) && state.Enemies.Any(e => e.Monster is SpectralKnight), "untouched KnightsElite fixture required");
            await Until(() => player.PlayerCombatState!.Phase == PlayerTurnPhase.Play);
            Require(!player.PlayerCombatState!.AllCards.Any(c => c.IsUpgraded), "unexpected upgraded baseline combat card");
            var paths = ModelDb.Card<StrikeIronclad>().RunAssetPaths.Concat(ModelDb.Card<DefendIronclad>().RunAssetPaths).Distinct().Except(PreloadManager.Cache.GetLoadedCacheAssets());
            Require(await NAssetLoader.Instance.LoadInTheBackground(PreloadManager.Cache.CreateSession("Dampen native fixtures", paths)), "fixture asset preload");
            var cards = new CardModel[] { state.CreateCard<StrikeIronclad>(player), state.CreateCard<DefendIronclad>(player) };
            await CardPileCmd.Add(cards[0], player.PlayerCombatState.Hand); await CardPileCmd.Add(cards[1], player.PlayerCombatState.DrawPile);
            foreach (var card in cards) CardCmd.Upgrade(card);
            var refs = new Dictionary<object, string>(ReferenceEqualityComparer.Instance);
            string? Ref(object? value) { if (value is null) return null; if (!refs.TryGetValue(value, out var id)) refs.Add(value, id = "r" + (refs.Count + 1)); return id; }
            var sourceId = CreatureId(_source); var ownerId = CreatureId(_owner); var sourceRef = Ref(_source); var combatRef = Ref(state);
            var initialRoster = state.Enemies.Select(c => new { id = CreatureId(c), reference = Ref(c), type = c.Monster!.GetType().Name }).ToArray();
            object Card(CardModel c) => new { id = CardId(c), reference = Ref(c), type = c.GetType().Name, level = c.CurrentUpgradeLevel,
                value = c is StrikeIronclad ? c.DynamicVars.Damage.BaseValue : c.DynamicVars.Block.BaseValue,
                cost = c.EnergyCost.GetWithModifiers(CostModifiers.Local), pile = c.Pile!.Type.ToString(), owner = Ref(c.Owner.Creature) };
            object[] Entries(DampenPower p) => Ledger(p).Select(e => (object)new { card = Ref(e.Key), id = CardId(e.Key), oldLevel = e.Value }).ToArray();
            var steps = new List<object>(); var pairs = new List<object>(); var events = new List<object>(); var received = new List<object>();
            var moves = new List<object>(); var rawSources = new List<object>();
            void Snapshot(string name, DampenPower? p = null)
            {
                p ??= _sourcePower;
                steps.Add(new { name, phase = _phase, domain = Domain, ending = CombatManager.Instance.IsEnding,
                    sourceAttached = state.ContainsCreature(_source), sourceCombat = Ref(_source.CombatState), combat = combatRef,
                    power = Ref(p), present = p is not null && _owner.Powers.Contains(p), amount = p?.Amount,
                    applier = Ref(p?.Applier), casters = p is null ? Array.Empty<string?>() : Casters(p).Select(c => Ref(c)).OrderBy(x => x).ToArray(),
                    ledger = p is null ? Array.Empty<object>() : Entries(p), cards = cards.Select(Card).ToArray() });
            }
            applied = p =>
            {
                if (p is not DampenPower dampen) return;
                if (_phase == "source") _sourcePower = dampen;
                received.Add(new { phase = _phase, power = Ref(p), target = Ref(p.Owner), applier = Ref(p.Applier), amount = p.Amount, domain = Domain });
            };
            _owner.PowerApplied += applied;
            foreach (var card in cards)
            {
                int previous = card.CurrentUpgradeLevel;
                Action callback = () =>
                {
                    events.Add(new { phase = _phase, card = Ref(card), id = CardId(card), before = previous, after = card.CurrentUpgradeLevel, domain = Domain }); previous = card.CurrentUpgradeLevel;
                    if (_phase == "source" && Case == "enter-pair" && !_pairUsed && card.CurrentUpgradeLevel == 0)
                    {
                        _pairUsed = true; bool before = Domain; var task = SetDomain(true); SwitchTasks.Add(task);
                        Require(Domain, "native Domain.Open did not commit synchronously in real Upgraded event");
                        Boundaries.Add(new { kind = "native-card-Upgraded-event", card = Ref(card), before, after = Domain });
                    }
                };
                card.Upgraded += callback; subscriptions.Add((card, callback));
            }
            observed = row =>
            {
                pairs.Add(new { phase = _phase, power = Ref(row.Power), card = Ref(row.Card), id = CardId(row.Card), source = Ref(row.Source), combat = Ref(row.Combat),
                    invocationNonce = row.InvocationNonce, applyNonce = row.ApplyNonce, moveNonce = row.MoveNonce, outerNonce = row.OuterNonce,
                    before = row.BeforeLevel, after = row.AfterLevel, ledgerBefore = row.LedgerBefore, ledgerAfter = row.LedgerAfter,
                    sourceDomainAtAdmission = row.DomainAtAdmission, domainAfter = Domain, suppressed = row.Suppressed, provenance = row.Provenance,
                    sourceAttached = row.Source is not null && state.ContainsCreature(row.Source), nativeLedger = Entries(row.Power),
                    sameNativeLedger = row.Ledger.Count == Ledger(row.Power).Count && row.Ledger.All(e => Ledger(row.Power).TryGetValue(e.Key, out int level) && level == e.Value) });
                if (_phase == "source" && Case == "exit-pair" && !_pairUsed)
                {
                    _pairUsed = true; bool before = Domain; var task = SetDomain(false); SwitchTasks.Add(task);
                    Require(!Domain, "native Domain.Remove did not commit synchronously at probe-only pair boundary");
                    Boundaries.Add(new { kind = "instrumented-post-pair", card = Ref(row.Card), before, after = Domain });
                }
            };
            DomainDampenTransactions.PairObserved += observed;
            async Task NativeMove(Creature creature)
            {
                uint id = CreatureId(creature); rawSources.Add(new { reference = Ref(creature), id, type = creature.Monster!.GetType().Name });
                int before = CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>().Count();
                creature.Monster!.SetMoveImmediate((MoveState)creature.Monster.MoveStateMachine!.States["DAMPEN_MOVE"], forceTransition: true);
                await creature.Monster.PerformMove();
                var entries = CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>().Skip(before).ToArray();
                Require(entries.Length == 1 && ReferenceEquals(entries[0].Monster, creature.Monster) && entries[0].Move.Id == "DAMPEN_MOVE", "actual move history missing");
                moves.Add(new { source = Ref(creature), id, type = creature.Monster.GetType().Name, move = entries[0].Move.Id });
            }
            Snapshot("baseline");
            if (Case is "on" or "exit-await" or "exit-pair") await SetDomain(true);
            _phase = "source"; await NativeMove(_source); await Task.WhenAll(SwitchTasks);
            Require(_sourcePower is not null, "native power application absent"); Snapshot("source");
            _phase = "no-replay"; await SetDomain(false); Snapshot("off-no-replay");
            Creature? second = null;
            if (Case != "departure")
            {
                second = await CreatureCmd.Add<MagiKnight>(state); await NativeMove(second); Snapshot("joined");
            }
            await SetDomain(true); _phase = "independent";
            var independent = cards.FirstOrDefault(c => c.CurrentUpgradeLevel > 0 && !Ledger(_sourcePower!).ContainsKey(c));
            if (independent is not null) CardCmd.Downgrade(independent);
            Snapshot("independent");
            _phase = "restoration";
            if (second is not null) { await CreatureCmd.Kill(_source, force: true); Snapshot("first-death"); await CreatureCmd.Kill(second, force: true); }
            else await PowerCmd.Remove(_sourcePower!); // Escape deliberately does not fabricate native death cleanup.
            Snapshot("restored");
            _phase = "player"; var control = (DampenPower)ModelDb.Power<DampenPower>().ToMutable();
            await PowerCmd.Apply(Choices, control, _owner, 1m, _owner, null); Snapshot("player-control", control);
            await PowerCmd.Remove(control); Snapshot("player-restored", control);
            GD.Print("[Volibear] DOMAIN_DAMPEN_TRANSACTIONS_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-dampen-transactions", variant = Case,
                acceptance = "native-source-ledger-card-pairs-not-power-admission-or-ordinary-input", testMode = false,
                version = release.Version, commit = release.Commit, encounter = (state.Encounter ?? throw new InvalidOperationException("actual combat encounter missing")).GetType().Name,
                sourceId, ownerId, sourceRef, ownerRef = Ref(_owner), combatRef, nativeMoveCalls = moves.Count, directPowerCallbackCalls = 0,
                initialCards = cards.Select(c => new { id = CardId(c), reference = Ref(c), type = c.GetType().Name }).ToArray(),
                independentCard = Ref(independent), cleanupKind = second is null ? "native-remove-after-escape" : "native-last-caster-death",
                ilSites = DomainDampenTransactions.VerifyNativeIl(), initialRoster, rawSources, moves, received,
                nativeReceived = CombatManager.Instance.History.Entries.OfType<PowerReceivedEntry>().Where(e => e.Power is DampenPower)
                    .Select(e => new { power = Ref(e.Power), type = e.Power.GetType().Name, amount = e.Amount, applier = Ref(e.Applier), target = Ref(e.Power.Owner) }).ToArray(),
                pairs, cardEvents = events, boundaries = Boundaries, steps,
                lifetimeAfter = DomainDampenTransactions.Audit(), patchTargets = DomainDampenTransactions.InstalledPatchTargets(),
                admissionSuppression = false, artifactSuppression = false, endingRepair = false, exceptionRollback = false, escapeRestitutionRepair = false
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_DAMPEN_TRANSACTIONS_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally
        {
            if (applied is not null) _owner.PowerApplied -= applied;
            if (observed is not null) DomainDampenTransactions.PairObserved -= observed;
            foreach (var (card, callback) in subscriptions) card.Upgraded -= callback;
            CombatManager.Instance.TurnStarted -= OnTurn; new Harmony(Id).UnpatchAll(Id);
        }
    }
}
