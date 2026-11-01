using System;
using System.Collections.Generic;

namespace Volibear.Core;

/// <summary>
/// Rebase only modifiers which existed when the material became a form. Their native
/// objects retain expiry/cleanup ownership. Later absolute modifiers refer to the form,
/// not the material (Set(1) after conversion must cost 1).
/// </summary>
internal sealed class BeastCostLedger<T> where T : class
{
    private readonly HashSet<T> inherited;
    internal int MaterialBase { get; }
    internal int FormBase { get; set; } = 1;

    internal BeastCostLedger(int materialBase, IEnumerable<T> existing)
    {
        MaterialBase = Math.Max(0, materialBase);
        inherited = new HashSet<T>(existing, ReferenceEqualityComparer.Instance);
    }

    internal bool IsInherited(T modifier) => inherited.Contains(modifier);

    internal int Evaluate(IEnumerable<T> live, Func<T, int, int> apply)
    {
        var added = new List<T>();
        var oldCost = MaterialBase;
        foreach (var modifier in live)
        {
            if (inherited.Contains(modifier)) oldCost = apply(modifier, oldCost);
            else added.Add(modifier);
        }
        // Preserve a discount, not an old card's surcharge or absolute base.
        var value = Math.Max(0, FormBase - Math.Max(0, MaterialBase - oldCost));
        foreach (var modifier in added) value = apply(modifier, value);
        return Math.Max(0, value);
    }

    internal BeastCostLedger<T> CloneFor(IReadOnlyList<T> source, IReadOnlyList<T> clones)
    {
        if (source.Count != clones.Count)
            throw new InvalidOperationException("Native cost clone changed modifier count.");
        var selected = new List<T>();
        for (var i = 0; i < source.Count; i++)
            if (inherited.Contains(source[i])) selected.Add(clones[i]);
        return new BeastCostLedger<T>(MaterialBase, selected) { FormBase = FormBase };
    }
}
