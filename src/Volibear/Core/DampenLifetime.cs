using System;
using System.Threading;
using System.Threading.Tasks;

namespace Volibear.Core;

// Pure lifetime primitives: an original builder task, never a replacement task.
internal sealed class DampenLifetime(Task task, long epoch, long nonce)
{
    private int _closed, _conflict;
    internal Task Task { get; private set; } = task;
    internal bool Closed => Volatile.Read(ref _closed) != 0;
    internal void Rebind(Task actualTask) { if (!Closed) Task = actualTask; }
    internal long Epoch { get; } = epoch;
    internal long Nonce { get; } = nonce;
    internal bool Live(long currentEpoch) => Epoch == currentEpoch && Volatile.Read(ref _closed) == 0 &&
        Volatile.Read(ref _conflict) == 0 && !Task.IsCompleted;
    internal void Close() => Interlocked.Exchange(ref _closed, 1);
    internal void Conflict() => Interlocked.Exchange(ref _conflict, 1);
}

internal sealed class DampenHandoff<T>(T value) where T : class
{
    private int _claimed;
    internal T Value { get; } = value;
    internal bool Fresh => Volatile.Read(ref _claimed) == 0;
    // Even a mismatching first entry burns the ticket: a later nested call must not inherit it.
    internal T? Claim(bool exactMatch)
    {
        bool first = Interlocked.CompareExchange(ref _claimed, 1, 0) == 0;
        return first && exactMatch ? Value : null;
    }
}
