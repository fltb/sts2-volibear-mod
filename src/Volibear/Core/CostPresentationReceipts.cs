using System;
using System.Threading;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

namespace Volibear.Core;

public sealed record CommittedCostPresentation(long Id, ICombatState Combat, Creature Owner,
    CardModel Card, int Before, int After, string Cause);

/// <summary>Optional presentation after a real per-card modifier write or successful native
/// payment. No UI references, cost replacement, Task proxy, or grant-as-consumption claim.</summary>
public static class CostPresentationReceipts
{
    public sealed record Snapshot(ICombatState Combat, Creature Owner, CardModel Card, int LocalCost);
    private static long sequence;
    public static event Action<CommittedCostPresentation>? Committed;
    public static Snapshot? Capture(CardModel card)
    {
        try
        {
            if (card.IsCanonical || card.Owner?.Character is not VolibearCharacter || card.EnergyCost.CostsX ||
                card.Owner.Creature.CombatState is not { } combat) return null;
            int cost=card.EnergyCost.GetWithModifiers(CostModifiers.Local);
            return cost>=0 ? new(combat,card.Owner.Creature,card,cost) : null;
        }
        catch { return null; }
    }
    public static void LocalReductionCommitted(Snapshot? snapshot)
    {
        try { if(snapshot is not null) Publish(snapshot,Math.Max(0,snapshot.Card.EnergyCost.GetWithModifiers(CostModifiers.Local)),"local-card-modifier"); }
        catch { /* Cosmetic receipt cannot fail the committed modifier. */ }
    }
    public static void ObserveNativePayment(Snapshot? snapshot,Task<(int,int)> original)
    {
        if(snapshot is null)return;
        void Completed()
        {
            try
            {
                if(!original.IsCompletedSuccessfully)return;
                var (energy,stars)=original.Result;
                // Do not mislabel alternate star payment as a discount. Local coupons were
                // already reported at their real write; here compare actual paid energy to local cost.
                if(stars==0)Publish(snapshot,energy,"resolved-native-payment");
            }
            catch { /* Never changes the original completion or caller continuation. */ }
        }
        try
        {
            if(original.IsCompleted)Completed();
            else original.GetAwaiter().OnCompleted(Completed);
        }
        catch { /* Best effort subscriber, no Task substitution. */ }
    }
    private static void Publish(Snapshot snapshot,int after,string cause)
    {
        if(after<0 || after>=snapshot.LocalCost || !snapshot.Owner.IsAlive ||
            !ReferenceEquals(snapshot.Owner.CombatState,snapshot.Combat) ||
            !ReferenceEquals(snapshot.Card.Owner?.Creature,snapshot.Owner) ||
            !ReferenceEquals(snapshot.Combat,CombatManager.Instance.DebugOnlyGetState()) ||
            !CombatManager.Instance.IsInProgress || CombatManager.Instance.IsOverOrEnding)return;
        var receipt=new CommittedCostPresentation(Interlocked.Increment(ref sequence),snapshot.Combat,
            snapshot.Owner,snapshot.Card,snapshot.LocalCost,after,cause);
        foreach(Action<CommittedCostPresentation> callback in Committed?.GetInvocationList()??[])
            try { callback(receipt); } catch { /* Optional presentation only. */ }
    }
}
