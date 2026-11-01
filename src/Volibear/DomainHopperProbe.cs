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
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Core;

namespace Volibear;

/// <summary>Isolated controlled native Hopper moves, not ordinary input/scheduler acceptance.
/// Fixture wrappers only await original native operations and open Domain at named boundaries.
/// No production gate, theft, return, reward or cleanup callback is called directly.</summary>
internal static class DomainHopperProbe
{
    internal static readonly string[] Variants = ["off", "on", "c-wait-open", "master-hook-open", "master-committed-open", "off-death", "mounted-domain-death", "escape"];
    private static readonly Harmony Observer = new("Volibear.DomainHopperProbe");
    private static readonly ThrowingPlayerChoiceContext Choices = new();
    private static readonly Dictionary<object, string> References = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Windows = [], Snapshots = [], DeathCallbacks = [];
    private static bool started, armed, windowUsed;
    private static string variant = "";
    private static CombatState combat = null!;
    private static Player player = null!;
    private static Creature hopper = null!, guard = null!;
    private static CardModel c = null!, m = null!;
    private static List<CardModel>? nativeList;
    private static SwipePower? capturedSwipe;
    private static readonly FieldInfo Registry = AccessTools.Field(typeof(RunState), "_allCards");
    private static readonly FieldInfo RewardCard = AccessTools.Field(typeof(SpecialCardReward), "_card");
    private static string Ref(object? value)
    {
        if (value is null) return "null";
        if (!References.TryGetValue(value, out var id)) References.Add(value, id = "r" + (References.Count + 1));
        return id;
    }
    private static string Id(Creature creature) => creature.CombatId?.ToString() ?? throw new InvalidOperationException("Missing native creature ID");
    private static void Require(bool valid, string message) { if (!valid) throw new InvalidOperationException(message); }
    public static void Install()
    {
        Require(System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "domain-hopper", "Explicit Hopper scenario required");
        InstallObservers(Observer);
        CombatManager.Instance.TurnStarted += OnTurn;
    }
    internal static void InstallObservers(Harmony observer)
    {
        observer.Patch(Body(AccessTools.Method(typeof(ThievingHopper), "ThieveryMove")),
            transpiler: new HarmonyMethod(typeof(DomainHopperProbe), nameof(RootWait)) { priority = Priority.Last });
        observer.Patch(Body(AccessTools.Method(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromDeck), [typeof(IReadOnlyList<CardModel>), typeof(bool)])),
            transpiler: new HarmonyMethod(typeof(DomainHopperProbe), nameof(MasterHook)) { priority = Priority.Last });
        observer.Patch(AccessTools.Method(typeof(SwipePower), nameof(SwipePower.Steal)),
            postfix: new HarmonyMethod(typeof(DomainHopperProbe), nameof(AfterSteal)));
        observer.Patch(AccessTools.Method(typeof(SwipePower), nameof(SwipePower.BeforeDeath)),
            postfix: new HarmonyMethod(typeof(DomainHopperProbe), nameof(ObserveDeath)));
    }
    private static void ObserveDeath(SwipePower __instance, Creature target, Task __result)
    {
        if (!ReferenceEquals(target, hopper) || !ReferenceEquals(__instance.Owner, hopper)) return;
        DeathCallbacks.Add(new { swipeRef = Ref(__instance), targetRef = Ref(target), stolenRef = Ref(__instance.StolenCard),
            masterRef = Ref(__instance.StolenCard?.DeckVersion), nativeCompleted = __result.IsCompletedSuccessfully,
            hopperHp = hopper.CurrentHp, domain = player.Creature.GetPowerAmount<DomainPower>() });
    }
    private static MethodInfo Body(MethodInfo method) => AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
    private static IEnumerable<CodeInstruction> RootWait(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var listField = __originalMethod.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Single(f => f.FieldType == typeof(List<CardModel>) && f.Name.StartsWith("<cardsToSteal>", StringComparison.Ordinal));
        int count = 0;
        foreach (var original in input)
        {
            var instruction = new CodeInstruction(original);
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(Cmd) && method.Name == nameof(Cmd.Wait))
            {
                Require(method.GetParameters().Select(p => p.ParameterType).SequenceEqual([typeof(float), typeof(bool)]), "Hopper wait signature changed");
                var load = new CodeInstruction(OpCodes.Ldarg_0);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                load.blocks.AddRange(instruction.blocks); instruction.blocks.Clear();
                yield return load; yield return new(OpCodes.Ldfld, listField);
                instruction.opcode = OpCodes.Call; instruction.operand = AccessTools.Method(typeof(DomainHopperProbe), nameof(Wait)); count++;
            }
            yield return instruction;
        }
        Require(count == 1, "Hopper unique native 0.6 wait anchor changed");
    }
    private static IEnumerable<CodeInstruction> MasterHook(IEnumerable<CodeInstruction> input)
    {
        int count = 0;
        foreach (var original in input)
        {
            var instruction = new CodeInstruction(original);
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(Hook) && method.Name == nameof(Hook.BeforeCardRemoved))
            {
                Require(method.GetParameters().Select(p => p.ParameterType).SequenceEqual([typeof(IRunState), typeof(CardModel)]), "BeforeCardRemoved signature changed");
                instruction.opcode = OpCodes.Call; instruction.operand = AccessTools.Method(typeof(DomainHopperProbe), nameof(BeforeRemoved)); count++;
            }
            yield return instruction;
        }
        Require(count == 1, "Native master hook anchor missing");
    }
    private static async Task Wait(float seconds, bool ignoreCombatEnd, List<CardModel> cards)
    {
        var native = Cmd.Wait(seconds, ignoreCombatEnd);
        if (armed)
        {
            Require(seconds == 0.6f, "Wrong native theft wait"); nativeList = cards;
            if (variant == "c-wait-open")
            {
                Require(!native.IsCompleted, "Native theft wait was not pending");
                await Open("native-C-completed-0.6wait-pending", native);
            }
        }
        await native;
    }
    private static async Task BeforeRemoved(IRunState run, CardModel card)
    {
        var native = Hook.BeforeCardRemoved(run, card);
        await native; // Preserve native hook completion/exception BEFORE the controlled domain input.
        if (armed && ReferenceEquals(card, m) && variant == "master-hook-open")
            await Open("native-BeforeCardRemoved-completed-before-M-pile", native);
    }
    private static void AfterSteal(SwipePower __instance, CardModel card, ref Task __result)
    {
        if (!armed || !ReferenceEquals(card, c)) return;
        capturedSwipe = __instance;
        if (variant == "master-committed-open") __result = AfterCommitted(__result);
    }
    private static async Task AfterCommitted(Task native)
    {
        await native;
        Require(m.Pile is null && m.HasBeenRemovedFromState, "Expected original master commit before domain input");
        await Open("native-Steal-completed-before-Swipe-mount", native);
    }
    private static async Task Open(string point, Task? native = null)
    {
        Require(!windowUsed, "Domain input boundary repeated"); windowUsed = true;
        var before = Snapshot(); bool? pending = native is null ? null : !native.IsCompleted;
        await DomainPower.Open(Choices, player.Creature, 5);
        Windows.Add(new { point, nativePending = pending, before, after = Snapshot() });
    }
    private static object Snapshot()
    {
        var room = player.RunState.CurrentRoom as CombatRoom ?? throw new InvalidOperationException("Hopper fixture requires native CombatRoom");
        var rewards = room.ExtraRewards.TryGetValue(player, out var rows) ? rows : [];
        var swipes = hopper.Powers.OfType<SwipePower>().ToArray();
        return new {
            cRef = Ref(c), mRef = Ref(m), cMasterRef = Ref(c.DeckVersion), cOwnerRef = Ref(c.Owner), mOwnerRef = Ref(m.Owner),
            cModel = c.GetType().Name, mModel = m.GetType().Name, cUpgrade = c.IsUpgraded, mUpgrade = m.IsUpgraded,
            cPile = c.Pile?.Type.ToString() ?? "None", mPile = m.Pile?.Type.ToString() ?? "None",
            cRemoved = c.HasBeenRemovedFromState, mRemoved = m.HasBeenRemovedFromState,
            masterInDeck = player.Deck.Cards.Count(card => ReferenceEquals(card, m)),
            registryOccurrences = ((IEnumerable<CardModel>)Registry.GetValue(player.RunState)!).Count(card => ReferenceEquals(card, m)),
            rewardMasterRefs = rewards.OfType<SpecialCardReward>().Select(reward => Ref(RewardCard.GetValue(reward))).ToArray(),
            loot = player.RunState.CurrentMapPointHistoryEntry?.GetEntry(player.NetId).StolenLoot,
            cardsRemovedHistory = player.RunState.CurrentMapPointHistoryEntry?.GetEntry(player.NetId).CardsRemoved.Count,
            listRefs = nativeList?.Select(Ref).ToArray() ?? [],
            swipes = swipes.Select(s => new { swipeRef = Ref(s), stolenRef = Ref(s.StolenCard), targetRef = Ref(s.Target), ownerRef = Ref(s.Owner) }).ToArray(),
            capturedSwipeRef = Ref(capturedSwipe), capturedStolenRef = Ref(capturedSwipe?.StolenCard),
            playerHp = player.Creature.CurrentHp, playerBlock = player.Creature.Block, domain = player.Creature.GetPowerAmount<DomainPower>(),
            hopperHp = hopper.CurrentHp, hopperAttached = combat.ContainsCreature(hopper), guardAttached = combat.ContainsCreature(guard)
        };
    }
    private static void Record(string point) => Snapshots.Add(new { point, state = Snapshot() });
    private static void OnTurn(CombatState state) { if (!started) { started = true; _ = Run(state); } }
    private static async Task Run(CombatState state)
    {
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            variant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_HOPPER_CASE") ?? "";
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            Require(!string.IsNullOrWhiteSpace(token) && Variants.Contains(variant) && !MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn && release.Version == "v0.107.1" && release.Commit == "59260271", "Invalid Hopper token/case/release");
            combat = state; player = state.Players.Single(); hopper = state.Enemies.Single();
            Require(state.Encounter is ThievingHopperWeak && hopper.Monster is ThievingHopper && state.RunState.AscensionLevel == 0 && state.RoundNumber == 1 && state.CurrentSide == CombatSide.Player && player.Creature.CurrentHp == 80 && player.Creature.Block == 0, "Expected fresh native Hopper encounter");
            Require(hopper.Monster!.NextMove.Id == "THIEVERY_MOVE", "Native initial move must not be forced");
            var eligible = CardPile.GetCards(player, PileType.Draw, PileType.Discard).Where(card => card.DeckVersion is not null).ToArray();
            Require(eligible.Length > 0, "No native combat/master card pair"); c = eligible[0]; m = c.DeckVersion!;
            guard = await CreatureCmd.Add<ThievingHopper>(state); // Keeps death/escape reward state inspectable.
            foreach (var other in eligible.Skip(1)) await CardPileCmd.Add(other, player.PlayerCombatState!.Hand);
            Require(CardPile.GetCards(player, PileType.Draw, PileType.Discard).Where(card => card.DeckVersion is not null).SequenceEqual([c]), "Deterministic native selection fixture failed");
            Require(!ReferenceEquals(c, m) && ReferenceEquals(c.Owner, player) && ReferenceEquals(m.Owner, player), "Native combat/master identity mismatch");
            Record("baseline");
            if (variant == "on") await Open("before-native-ThieveryMove");
            int historyStart = CombatManager.Instance.History.Entries.Count(); armed = true;
            await hopper.Monster!.PerformMove().WaitAsync(TimeSpan.FromSeconds(45));
            armed = false; Record("after-theft");
            if (variant == "mounted-domain-death") await Open("after-native-Swipe-mounted-before-death");
            if (variant is "off-death" or "mounted-domain-death")
            {
                await CreatureCmd.Kill(hopper, force: false).WaitAsync(TimeSpan.FromSeconds(45)); Record("after-death");
            }
            if (variant == "escape")
            {
                foreach (var expected in new[] { "FLUTTER_MOVE", "HAT_TRICK_MOVE", "NAB_MOVE", "ESCAPE_MOVE" })
                {
                    hopper.Monster!.RollMove(state.PlayerCreatures);
                    Require(hopper.Monster!.NextMove.Id == expected, "Native Hopper follow-up state drift");
                    await hopper.Monster!.PerformMove().WaitAsync(TimeSpan.FromSeconds(45));
                }
                Record("after-escape");
            }
            var history = CombatManager.Instance.History.Entries.Skip(historyStart).ToArray();
            GD.Print("[Volibear] DOMAIN_HOPPER_RESULT " + JsonSerializer.Serialize(new {
                schema = 1, token, scenario = "domain-hopper", variant, completed = true, version = release.Version, commit = release.Commit,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn, encounter = state.Encounter!.GetType().Name, ascension = state.RunState.AscensionLevel,
                acceptance = "controlled-native-moves-and-domain-windows-not-ordinary-input",
                playerRef = Ref(player), ownerRef = Ref(player.Creature), hopperRef = Ref(hopper), playerId = Id(player.Creature), hopperId = Id(hopper),
                snapshots = Snapshots, windows = Windows, deathCallbacks = DeathCallbacks,
                damage = history.OfType<DamageReceivedEntry>().Select(e => new { sourceId = e.Dealer is null ? null : Id(e.Dealer), receiverId = Id(e.Receiver), hpLost = e.Result.UnblockedDamage, blocked = e.Result.BlockedDamage, overkill = e.Result.OverkillDamage }).ToArray(),
                moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => new { sourceId = Id(e.Monster.Creature), move = e.Move.Id }).ToArray()
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_HOPPER_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { armed = false; Observer.UnpatchAll(Observer.Id); CombatManager.Instance.TurnStarted -= OnTurn; }
    }
}
