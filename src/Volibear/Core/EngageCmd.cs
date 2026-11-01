using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
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
    public readonly record struct Result(bool Performed, decimal Absorbed, bool Completed);
    public sealed record Completion(PlayerChoiceContext Choices, ICombatState Combat, Creature Receiver,
        Creature Enemy, CardModel Card, decimal Absorbed);
    private sealed class Window
    {
        internal Creature Receiver = null!;
        internal ICombatState Combat = null!;
        internal long Generation;
        internal decimal Absorbed;
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
        var window = new Window { Receiver = receiver, Combat = state, Generation = Opportunities.Generation };
        Active.Value = window;
        try
        {
            var node = target.GetCreatureNode();
            if (node is not null) await node.PerformIntent();
            if (!Live(window) || receiver.IsDead || target.IsDead || !state.ContainsCreature(target) ||
                !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) return new(false, 0, false);
            await target.Monster.PerformMove(); // This method already advances OnMovePerformed.
        }
        finally { Active.Value = previous is not null && Live(previous) ? previous : null; }

        var completed = Live(window) && !receiver.IsDead && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding;
        if (completed)
        {
            var completion = new Completion(choices, state, receiver, target, card, window.Absorbed);
            // Snapshot each source once; responses may add/remove powers or draw more cards.
            var responders = receiver.Player!.Relics.Cast<object>().Concat(receiver.Powers)
                .OfType<IEngageResponder>().ToArray();
            foreach (var responder in responders)
            {
                if (!Live(window) || receiver.IsDead || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) break;
                await responder.AfterEngageCompleted(completion);
            }
        }
        return new(true, window.Absorbed, completed);
    }

    public static async Task<IReadOnlyList<Result>> PerformAll(PlayerChoiceContext choices, CardModel card)
    {
        var state = card.Owner?.Creature.CombatState ?? throw new InvalidOperationException("No combat");
        var targets = state.Enemies.ToArray(); // Stable engine ordering; new summons are not added mid-card.
        var results = new List<Result>();
        foreach (var target in targets)
        {
            if (!ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState()) ||
                card.Owner!.Creature.IsDead || !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsEnding) break;
            results.Add(await Perform(choices, target, card));
        }
        return results;
    }

    private static bool Live(Window window) => Opportunities.IsCurrent(window.Combat, window.Generation) &&
        ReferenceEquals(window.Combat, CombatManager.Instance.DebugOnlyGetState()) &&
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
        private static void Prefix(object __instance)
        {
            // Observe the real initial state-machine entry, including callers whose
            // tiny async entry stub was inlined before mod initialization.
            if ((int)State.GetValue(__instance)! != -1 || Owner.GetValue(__instance) is not MonsterModel monster ||
                monster.Creature.CombatState is not { } state ||
                !ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState())) return;
            EnsureCombat(state);
            Opportunities.ObserveActionStart(state, monster.Creature.CombatState, monster.Creature, state.RoundNumber);
        }
    }

    [HarmonyPatch(typeof(Creature), nameof(Creature.TakeTurn))]
    private static class SkipConsumedAction
    {
        private static bool Prefix(Creature __instance, ref Task __result)
        {
            if (!EarlyConsumed(__instance)) return true;
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
