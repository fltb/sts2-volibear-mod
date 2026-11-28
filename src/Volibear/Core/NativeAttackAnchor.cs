using System;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

namespace Volibear.Core;

/// <summary>
/// 0.114 split <c>AttackCommand.Execute</c> into a thin wrapper (attacker animation state and
/// post-hit death cleanup) and <c>ExecuteInternal</c>, which owns the hit loop and therefore the
/// single native multi-target Damage call. Adapters that bind that call must follow the body that
/// actually contains it; stable and earlier PBE keep the call in <c>Execute</c>.
/// Pinning the wrong body is a hard failure, not a silent fallback.
/// </summary>
internal static class NativeAttackAnchor
{
    internal static MethodInfo Method() =>
        AccessTools.Method(typeof(AttackCommand), "ExecuteInternal", [typeof(PlayerChoiceContext)])
        ?? AccessTools.Method(typeof(AttackCommand), nameof(AttackCommand.Execute), [typeof(PlayerChoiceContext)])
        ?? throw new MissingMethodException(typeof(AttackCommand).FullName, "ExecuteInternal/Execute");

    internal static MethodInfo MoveNext()
    {
        var method = Method();
        var machine = method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException($"{method} has no async state machine.");
        return AccessTools.Method(machine, "MoveNext") ?? throw new MissingMethodException(machine.Name, "MoveNext");
    }
}
