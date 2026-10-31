using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using Godot;

namespace Volibear;

/// <summary>Diagnostic: shows where a card instance lives so the probe can play a real hand card.</summary>
internal static class ProbeDiag
{
    public static void DumpPiles(object state, object player)
    {
        DumpObject("state", state);
        DumpObject("player", player);
        if (state.GetType().GetProperty("Players")?.GetValue(state) is IEnumerable players)
            foreach (var entry in players.Cast<object>().Take(1)) DumpObject("player0", entry);
    }

    private static void DumpObject(string label, object target)
    {
        GD.Print($"[Volibear] DIAG {label}={target.GetType().FullName}");
        foreach (var property in target.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            object? value;
            try { value = property.GetValue(target); } catch { value = "<throws>"; }
            var rendered = value is IEnumerable items and not string
                ? "[" + string.Join(",", items.Cast<object?>().Take(10).Select(Describe)) + "]"
                : Describe(value);
            GD.Print($"[Volibear] DIAG   {property.Name}:{property.PropertyType.Name}={rendered}");
        }
    }

    private static string Describe(object? value) =>
        value switch
        {
            null => "null",
            MegaCrit.Sts2.Core.Models.CardModel card => $"{card.GetType().Name}({card.Id.Entry})",
            MegaCrit.Sts2.Core.Entities.Cards.CardPile pile => $"Pile({pile.GetType().Name})",
            _ => value.ToString() ?? "?",
        };
}
