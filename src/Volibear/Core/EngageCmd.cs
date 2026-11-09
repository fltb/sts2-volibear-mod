using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace Volibear.Core;

public interface IEngageResponder
{
    Task AfterEngageCompleted(EngageCmd.Completion completion);
}

/// <summary>Consumes the real enemy action, preserving the engine's damage and move state machine.</summary>
public static class EngageCmd
{
    public readonly record struct Result(bool Performed, decimal Absorbed, bool Completed, decimal Taken = 0);
    public sealed record Completion(PlayerChoiceContext Choices, ICombatState Combat, Creature Receiver,
        Creature Enemy, CardModel Card, decimal Absorbed, decimal Taken = 0);
    private sealed class Window
    {
        internal Creature Receiver = null!;
        internal Creature Enemy = null!;
        internal ICombatState Combat = null!;
        internal long Generation;
        internal int Round;
        internal bool ActionStarted;
        internal decimal Absorbed;
        internal decimal HpBefore;
    }
    private static readonly AsyncLocal<Window?> Active = new();
    private static readonly EngageOpportunityLedger Opportunities = new();
    private static bool installed;
    internal static int EarlyOpportunityEntryCount => Opportunities.EarlyEntryCount;
    internal static int NaturalOpportunityEntryCount => Opportunities.NaturalEntryCount;

    public static void Install()
    {
        if (installed) return;
        var h = new Harmony("Volibear.Engage");
        h.CreateClassProcessor(typeof(ObserveAbsorption)).Patch();
        h.CreateClassProcessor(typeof(ObserveActionStart)).Patch();
        h.CreateClassProcessor(typeof(SkipConsumedAction)).Patch();
        h.CreateClassProcessor(typeof(SkipConsumedIntent)).Patch();
        h.CreateClassProcessor(typeof(AbandonCombat)).Patch();
        CombatManager.Instance.CombatSetUp += _ => Reset();
        CombatManager.Instance.CombatEnded += _ => Reset();
        installed = true;
    }

    private static void Reset()
    {
        Opportunities.Reset();
        Active.Value = null;
    }

    private static void EnsureCombat(ICombatState state) => Opportunities.EnsureCombat(state);

    private static bool EarlyConsumed(Creature enemy)
    {
        var state = CombatManager.Instance.DebugOnlyGetState();
        return state is not null && Opportunities.EarlyConsumed(state, enemy.CombatState, enemy, state.RoundNumber);
    }

    public static bool Consumed(Creature enemy)
    {
        var state = CombatManager.Instance.DebugOnlyGetState();
        return state is not null && Opportunities.Consumed(state, enemy.CombatState, enemy, state.RoundNumber);
    }

    public static async Task<Result> Perform(PlayerChoiceContext choices, Creature target, CardModel card)
    {
        var receiver = card.Owner?.Creature ?? throw new InvalidOperationException("Engage card has no owner");
        var state = receiver.CombatState ?? throw new InvalidOperationException("Engage requires live combat");
        if (state.CurrentSide != CombatSide.Player)
            throw new InvalidOperationException("Engage requires the player phase");
        if (!ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())) return new(false, 0, false);
        EnsureCombat(state);
        if (receiver.IsDead || target.IsDead || target.Monster is null || !target.IsEnemy ||
            !ReferenceEquals(target.CombatState, state) || !state.ContainsCreature(target) ||
            Consumed(target) || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding)
            return new(false, 0, false);

        // Reserve before any await. Never make a partly executed action eligible for a retry.
        if (!Opportunities.TryReserve(state, target.CombatState, target, state.RoundNumber))
            return new(false, 0, false);
        var previous = Active.Value;
        var window = new Window { Receiver = receiver, Enemy = target, Combat = state,
            Generation = Opportunities.Generation, Round = state.RoundNumber, HpBefore = receiver.CurrentHp };
        try
        {
            var node = target.GetCreatureNode();
            if (node is not null) await node.PerformIntent();
            if (!Live(window) || receiver.IsDead || target.IsDead || !state.ContainsCreature(target) ||
                !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) return new(false, 0, false);
            // Intent rendering is not the enemy action. Other mods may run effects there;
            // only observe absorption while the real move is being invoked.
            Active.Value = window;
            await target.Monster.PerformMove(); // This method already advances OnMovePerformed.
        }
        finally { Active.Value = previous is not null && Live(previous) ? previous : null; }

        // A completed Task is not proof of an action: a cooperating patch can skip the
        // native method. Keep the reservation (prefixes may have committed effects), but
        // never manufacture completion rewards for a native body that did not start.
        if (!window.ActionStarted) return new(false, 0, false);
        var completed = Live(window) && !receiver.IsDead && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding;
        // "Taken" is every point this engage cost the receiver: absorbed block plus real HP loss.
        var taken = window.Absorbed + Math.Max(0m, window.HpBefore - receiver.CurrentHp);
        if (completed)
        {
            var completion = new Completion(choices, state, receiver, target, card, window.Absorbed, taken);
            // Snapshot each source once; responses may add/remove powers or draw more cards.
            var responders = receiver.Player!.Relics.Cast<object>().Concat(receiver.Powers)
                .OfType<IEngageResponder>().ToArray();
            foreach (var responder in responders)
            {
                if (!Live(window) || receiver.IsDead || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) break;
                await responder.AfterEngageCompleted(completion);
            }
        }
        return new(true, window.Absorbed, completed, taken);
    }

    public static async Task<IReadOnlyList<Result>> PerformAll(PlayerChoiceContext choices, CardModel card)
    {
        var state = card.Owner?.Creature.CombatState ?? throw new InvalidOperationException("No combat");
        if (!ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())) return Array.Empty<Result>();
        EnsureCombat(state);
        var generation = Opportunities.Generation;
        var round = state.RoundNumber;
        var targets = state.Enemies.ToArray(); // Stable engine ordering; new summons are not added mid-card.
        var results = new List<Result>();
        foreach (var target in targets)
        {
            if (!Opportunities.IsCurrent(state, generation) || state.RoundNumber != round ||
                state.CurrentSide != CombatSide.Player ||
                !ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState()) ||
                card.Owner!.Creature.IsDead || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) break;
            results.Add(await Perform(choices, target, card));
        }
        return results;
    }

    private static bool Live(Window window) => Opportunities.IsCurrent(window.Combat, window.Generation) &&
        ReferenceEquals(window.Combat, CombatManager.Instance.DebugOnlyGetState()) &&
        window.Combat.CurrentSide == CombatSide.Player &&
        window.Combat.RoundNumber == window.Round &&
        ReferenceEquals(window.Receiver.CombatState, window.Combat);

    [HarmonyPatch(typeof(CombatManager), nameof(CombatManager.Reset), new[] { typeof(bool) })]
    private static class AbandonCombat
    {
        private static void Prefix() => Reset();
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.DamageBlockInternal))]
    private static class ObserveAbsorption
    {
        private static void Postfix(Creature __instance, decimal __result)
        {
            if (Active.Value is { } window && Live(window) && ReferenceEquals(window.Receiver, __instance))
                window.Absorbed += __result;
        }
    }

    [HarmonyPatch]
    private static class ObserveActionStart
    {
        private static readonly Type Machine = AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.PerformMove))
            .GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Pinned native PerformMove state machine missing.");
        private static readonly FieldInfo State = AccessTools.Field(Machine, "<>1__state")
            ?? throw new MissingFieldException(Machine.FullName, "<>1__state");
        private static readonly FieldInfo Owner = AccessTools.Field(Machine, "<>4__this")
            ?? throw new MissingFieldException(Machine.FullName, "<>4__this");
        private static MethodBase TargetMethod() => AccessTools.Method(Machine, "MoveNext");
        private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
        {
            // Observe inside the actual body: any foreign Prefix veto skips this too.
            // Read the two fields directly for both class and struct state machines;
            // no boxed copy, original instruction replacement, or patch-order assumption.
            yield return new CodeInstruction(OpCodes.Ldarg_0);
            yield return new CodeInstruction(OpCodes.Ldfld, State);
            yield return new CodeInstruction(OpCodes.Ldarg_0);
            yield return new CodeInstruction(OpCodes.Ldfld, Owner);
            yield return new CodeInstruction(OpCodes.Call, AccessTools.Method(typeof(ObserveActionStart), nameof(BodyEntered)));
            foreach (var instruction in instructions) yield return instruction;
        }

        private static void BodyEntered(int machineState, MonsterModel monster)
        {
            // Initial body entry precedes every synchronous effect/reentry. Resuming an
            // await does not spend another opportunity or move the fact to another round.
            if (machineState != -1 ||
                monster.Creature.CombatState is not { } state ||
                !ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())) return;
            EnsureCombat(state);
            Opportunities.ObserveActionStart(state, monster.Creature.CombatState, monster.Creature, state.RoundNumber);
            if (Active.Value is { } window && Live(window) && ReferenceEquals(window.Enemy, monster.Creature))
                window.ActionStarted = true;
        }
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.TakeTurn))]
    private static class SkipConsumedAction
    {
        private static bool Prefix(Creature __instance, ref Task __result)
        {
            if (__instance.CombatState?.CurrentSide != CombatSide.Enemy || !EarlyConsumed(__instance)) return true;
            __result = Task.CompletedTask;
            return false;
        }
    }

    [HarmonyPatch(typeof(NCreature), nameof(NCreature.PerformIntent))]
    private static class SkipConsumedIntent
    {
        private static bool Prefix(NCreature __instance, ref Task __result)
        {
            var creature = __instance.Entity;
            if (creature.CombatState?.CurrentSide != CombatSide.Enemy || !EarlyConsumed(creature)) return true;
            __result = Task.CompletedTask;
            return false;
        }
    }
}
