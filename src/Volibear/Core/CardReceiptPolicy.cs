namespace Volibear.Core;

/// <summary>Receipt eligibility only, never a rule that moves a card.</summary>
internal static class CardReceiptPolicy
{
    internal static void Notify<T>(System.Action<T>? listeners, T receipt)
    {
        if (listeners is null) return;
        foreach (System.Action<T> listener in listeners.GetInvocationList())
        {
            try { listener(receipt); }
            catch { /* A failed cosmetic observer cannot interrupt the next observer or gameplay. */ }
        }
    }

    internal static bool Allows(string effect, string from, string to, bool sameOwner, bool sameCombat, bool live)
    {
        if (!sameOwner || !sameCombat || !live) return false;
        return effect switch
        {
            "card_purify" => from is "Draw" or "Hand" or "Discard" or "Play" && to == "Exhaust",
            "card_retrieve" => from is "Draw" or "Discard" && to == "Hand",
            _ => false
        };
    }
}
