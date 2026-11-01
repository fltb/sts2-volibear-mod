using System;
using System.Linq;
using System.Reflection;
using System.Runtime.ExceptionServices;
using System.Threading.Tasks;

namespace Volibear;

/// <summary>
/// Acceptance-only binding to the game's own 0.107.1 lobby APIs, checked against
/// the complete pinned reference listed in docs/MULTIPLAYER_ACCEPTANCE.md.
/// Match public signatures, reject ambiguous/unknown shapes, and record the actual
/// methods used. This is not a network transport or a production compatibility shim.
/// </summary>
internal static class NativeLobbyApi
{
    internal static object? Get(object owner, string name)
    {
        var type = owner.GetType();
        if (type.GetProperty(name, BindingFlags.Public | BindingFlags.Instance) is { } property)
            return property.GetValue(owner);
        if (type.GetField(name, BindingFlags.Public | BindingFlags.Instance) is { } field)
            return field.GetValue(owner);
        throw new MissingMemberException(type.FullName, name);
    }

    private static bool Matches(MethodBase method, object?[] arguments)
    {
        var parameters = method.GetParameters();
        return arguments.Length <= parameters.Length && parameters.Skip(arguments.Length).All(p => p.IsOptional)
            && arguments.Select((arg, i) => arg is null
                ? !parameters[i].ParameterType.IsValueType || Nullable.GetUnderlyingType(parameters[i].ParameterType) is not null
                : parameters[i].ParameterType.IsInstanceOfType(arg)).All(match => match);
    }

    private static object?[] Arguments(MethodBase method, object?[] arguments) =>
        arguments.Concat(method.GetParameters().Skip(arguments.Length).Select(p => p.DefaultValue)).ToArray();

    private static T One<T>(T[] methods, string label) where T : MethodBase => methods.Length switch
    {
        1 => methods[0],
        0 => throw new MissingMethodException(label),
        _ => throw new AmbiguousMatchException(label)
    };

    internal static object New(Type type, params object?[] arguments)
    {
        var constructor = One(type.GetConstructors().Where(m => Matches(m, arguments)).ToArray(), type.FullName + ".ctor");
        return Unwrap(() => constructor.Invoke(Arguments(constructor, arguments)))!;
    }

    internal static object? Call(object owner, string name, params object?[] arguments)
    {
        var method = One(owner.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Where(m => m.Name == name && !m.ContainsGenericParameters && Matches(m, arguments)).ToArray(),
            owner.GetType().FullName + "." + name);
        return Unwrap(() => method.Invoke(owner, Arguments(method, arguments)));
    }

    private static object? Unwrap(Func<object?> invoke)
    {
        try { return invoke(); }
        catch (TargetInvocationException error) when (error.InnerException is not null)
        { ExceptionDispatchInfo.Capture(error.InnerException).Throw(); throw; }
    }
}

/// <summary>Public non-sealed base required by DispatchProxy's generated assembly.</summary>
public class NativeLobbyProbeListener : DispatchProxy
{
    internal readonly TaskCompletionSource<object?[]> Began = new();
    internal Exception? Failure;
    internal bool AllowDisconnect;

    internal static NativeLobbyProbeListener Create(Type contract)
    {
        if (!contract.IsInterface) throw new ArgumentException("Native lobby listener must be an interface");
        foreach (var method in contract.GetMethods()) Validate(method);
        return (NativeLobbyProbeListener)DispatchProxy.Create(contract, typeof(NativeLobbyProbeListener));
    }

    private static void Validate(MethodInfo method)
    {
        bool recognized = method.Name switch
        {
            "BeginRun" => method.ReturnType == typeof(void) && method.GetParameters().Length is 0 or 3,
            "ShouldAllowRunToBegin" => method.ReturnType == typeof(Task<bool>) && method.GetParameters().Length == 0,
            "PlayerConnected" or "PlayerChanged" or "AscensionChanged" or "SeedChanged" or "ModifiersChanged"
                or "MaxAscensionChanged" or "RemotePlayerDisconnected" or "LocalPlayerDisconnected"
                or "PlayerReadyChanged" => method.ReturnType == typeof(void),
            _ => false
        };
        if (!recognized) throw new MissingMethodException("Unknown native lobby callback: " + method);
    }

    protected override object? Invoke(MethodInfo? targetMethod, object?[]? args)
    {
        var method = targetMethod ?? throw new MissingMethodException("Missing lobby callback");
        Validate(method);
        switch (method.Name)
        {
            case "BeginRun":
                if (!Began.TrySetResult(args ?? []))
                    Failure = new InvalidOperationException("Native lobby began twice");
                break;
            case "ShouldAllowRunToBegin": return Task.FromResult(true);
            case "LocalPlayerDisconnected":
            case "RemotePlayerDisconnected":
                if (!AllowDisconnect)
                {
                    Failure = new InvalidOperationException("Unexpected native lobby disconnect: " +
                        string.Join(";", (args ?? []).Select(value => value?.ToString())));
                    Began.TrySetException(Failure);
                }
                break;
        }
        return null;
    }
}
