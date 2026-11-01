using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>Identity only, scoped to the original native Scry selection await.
/// Presentation observes the actual screen push; entering this scope is not an opened event.</summary>
public sealed class ScryPresentationScope : IDisposable
{
    private static readonly AsyncLocal<ScryPresentationScope?> Current = new();
    private readonly ScryPresentationScope? previous;
    private bool disposed;

    public static ScryPresentationScope? CurrentScry => Current.Value;
    public PlayerChoiceContext Context { get; }
    public CardModel Source { get; }
    public IReadOnlyList<CardModel> Looked { get; }

    public ScryPresentationScope(PlayerChoiceContext context, CardModel source, IEnumerable<CardModel> looked)
    {
        Context = context;
        Source = source;
        Looked = Array.AsReadOnly(looked.ToArray());
        previous = Current.Value;
        Current.Value = this;
    }

    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        if (ReferenceEquals(Current.Value, this)) Current.Value = previous;
    }
}
