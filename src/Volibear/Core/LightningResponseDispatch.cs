using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Volibear.Core;

/// <summary>Serial response dispatch only; world authority remains with the caller.</summary>
internal static class LightningResponseDispatch
{
    internal static async Task Run<T>(IEnumerable<T> listeners, Func<bool> canContinue,
        Func<T, bool> active, Func<T, Task> invoke)
    {
        // One snapshot per dispatch. Additions wait for the next batch, but removal
        // remains observable via active immediately before each invocation.
        foreach (var listener in listeners.ToArray())
        {
            if (!canContinue()) break;
            if (active(listener)) await invoke(listener);
        }
    }
}
