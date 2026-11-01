using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace Volibear.Core;

/// <summary>
/// Card overlays follow the actual inheritance chain, including cards from other
/// mods and types loaded after initialization. Registration changes no card state;
/// every installed adapter still checks the exact converted card instance.
/// </summary>
internal sealed class BeastCardAdapterRegistry(Type root, Action<Type[]> install)
{
    private readonly HashSet<Type> registered = [];
    private readonly HashSet<(MethodInfo Method, string Handler, bool Postfix)> patched = [];

    internal void Ensure(Type type)
    {
        if (!root.IsAssignableFrom(type) || type.ContainsGenericParameters)
            throw new ArgumentException("Expected a closed native card type.", nameof(type));
        if (registered.Contains(type)) return;
        var missing = new Stack<Type>();
        for (var current = type; current is not null && root.IsAssignableFrom(current); current = current.BaseType)
            if (!registered.Contains(current)) missing.Push(current);
        var chain = missing.ToArray(); // Base before derived; includes intermediate mod bases.
        install(chain);
        // A failed installation must never certify an unadapted type. Successful
        // member patches are individually remembered so a retry cannot duplicate them.
        foreach (var current in chain) registered.Add(current);
    }

    internal void PatchOnce(MethodInfo method, string handler, bool postfix, Action patch)
    {
        var key = (method, handler, postfix);
        if (patched.Contains(key)) return;
        patch();
        patched.Add(key);
    }

    internal static IEnumerable<Type> LoadedCardTypes(Type root) => AppDomain.CurrentDomain.GetAssemblies()
        .SelectMany(LoadableTypes).Where(type => root.IsAssignableFrom(type) && !type.ContainsGenericParameters)
        .OrderBy(type => type.AssemblyQualifiedName, StringComparer.Ordinal);

    private static IEnumerable<Type> LoadableTypes(Assembly assembly)
    {
        try { return assembly.GetTypes(); }
        catch (ReflectionTypeLoadException error) { return error.Types.OfType<Type>(); }
        catch (NotSupportedException) { return []; }
    }

    internal static IEnumerable<MethodInfo> DeclaredOverrides(Type type, MethodInfo native) =>
        type.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
            .Where(method => !method.IsAbstract && (method.Equals(native) ||
                (method.IsVirtual && method.GetBaseDefinition().Equals(native.GetBaseDefinition()))));
}
