using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using System.Threading.Tasks;

namespace Volibear.Core;

/// <summary>A read-only copy of one native damage result (including redirected damage).</summary>
public sealed record LightningHit(Creature Receiver, int HpLost, int Blocked, int Overkill);

/// <summary>
/// Explicit lightning identity, never inferred from ValueProp.Unpowered. Amount is a
/// single pre-await snapshot for every target. CountThisTurn already includes this batch.
/// Id is unique within this combat/owner, not a play ID or a target/hit counter.
/// </summary>
public sealed record LightningBatch(
    long Id, ICombatState Combat, Creature Owner, CardModel? Card,
    int RoundNumber, int PlayerTurnNumber, decimal BaseDamage, int StormCharge,
    decimal Amount, IReadOnlyList<Creature> Targets, IReadOnlyList<LightningHit> Results,
    int CountThisTurn)
{
    public int HpLost => Results.Sum(result => result.HpLost);
}

/// <summary>
/// Combat-scoped, player-scoped completion notifications. Use Subscribe once per
/// deployed instance and dispose when that instance is removed. All callbacks are
/// awaited serially; exceptions propagate (partly applied batches are never retried).
/// The native game executes these operations on its combat action thread.
/// </summary>
public static class LightningBatches
{
    internal sealed class OwnerScope
    {
        internal readonly LightningCounter Counter = new();
        internal readonly List<Subscription> Listeners = [];
    }

    internal sealed class Subscription(OwnerScope scope,
        Func<PlayerChoiceContext, LightningBatch, Task> callback) : IDisposable
    {
        internal bool Active { get; private set; } = true;
        internal Task Invoke(PlayerChoiceContext context, LightningBatch batch) => callback(context, batch);
        public void Dispose()
        {
            if (!Active) return;
            Active = false;
            scope.Listeners.Remove(this);
        }
    }

    private static readonly Dictionary<ICombatState, Dictionary<Creature, OwnerScope>> Scopes =
        new(ReferenceEqualityComparer.Instance);
    private static bool _installed;

    public static int GetTurnCount(Creature owner)
    {
        if (!CanUse(owner, out var combat)) return 0;
        return Scope(combat!, owner).Counter.Read(combat!.RoundNumber, Turn(owner));
    }

    /// <summary>Each deployment receives its own subscription; there is no shared first-use flag.</summary>
    public static IDisposable Subscribe(Creature owner,
        Func<PlayerChoiceContext, LightningBatch, Task> callback)
    {
        ArgumentNullException.ThrowIfNull(callback);
        if (!CanUse(owner, out var combat))
            throw new InvalidOperationException("Lightning subscriptions require a live player in combat.");
        var scope = Scope(combat!, owner);
        var subscription = new Subscription(scope, callback);
        scope.Listeners.Add(subscription);
        return subscription;
    }

    internal static int Turn(Creature owner) => owner.Player!.PlayerCombatState!.TurnNumber;

    internal static bool CanUse(Creature owner, out ICombatState? combat)
    {
        combat = owner.CombatState;
        return combat is not null && owner.IsAlive && owner.Player?.PlayerCombatState is not null &&
               combat.ContainsCreature(owner) && CombatManager.Instance.IsInProgress &&
               !CombatManager.Instance.IsEnding &&
               ReferenceEquals(CombatManager.Instance.DebugOnlyGetState(), combat);
    }

    internal static OwnerScope Scope(ICombatState combat, Creature owner)
    {
        InstallLifecycle();
        if (!Scopes.TryGetValue(combat, out var owners))
        {
            owners = new Dictionary<Creature, OwnerScope>(ReferenceEqualityComparer.Instance);
            Scopes.Add(combat, owners);
        }
        if (!owners.TryGetValue(owner, out var scope)) owners.Add(owner, scope = new OwnerScope());
        return scope;
    }

    internal static async Task Notify(PlayerChoiceContext context, OwnerScope scope, LightningBatch batch)
    {
        bool CanContinue()
        {
            if (scope.Counter.IsClosed || !CanUse(batch.Owner, out var combat) ||
                !ReferenceEquals(batch.Combat, combat) ||
                combat!.RoundNumber != batch.RoundNumber || Turn(batch.Owner) != batch.PlayerTurnNumber)
                return false;
            return true;
        }
        await LightningResponseDispatch.Run(scope.Listeners, CanContinue,
            listener => listener.Active, listener => listener.Invoke(context, batch));
    }

    /// <summary>Clears counters, pending tickets and deployed-instance callbacks, never power Amount.</summary>
    public static void ResetCombatState()
    {
        foreach (var owners in Scopes.Values)
        foreach (var scope in owners.Values)
        {
            scope.Counter.Close();
            foreach (var listener in scope.Listeners.ToArray()) listener.Dispose();
        }
        Scopes.Clear();
    }

    private static void InstallLifecycle()
    {
        if (_installed) return;
        // CombatEnded handles victory/loss. Reset(bool) has NO end event when a run
        // is abandoned, so its verified native entry also clears sidecar state.
        var reset = AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), [typeof(bool)])
            ?? throw new MissingMethodException("CombatManager.Reset(bool)");
        new Harmony("Volibear.Lightning.Lifecycle").Patch(reset,
            prefix: new HarmonyMethod(typeof(LightningBatches), nameof(BeforeManagerReset)));
        CombatManager.Instance.CombatEnded += _ => ResetCombatState();
        CombatManager.Instance.CombatSetUp += _ => ResetCombatState();
        _installed = true;
    }

    private static void BeforeManagerReset() => ResetCombatState();
}
