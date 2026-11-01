using System.Reflection;
using System.Reflection.Emit;
using Volibear.Core;

// Real production type discovery, inheritance traversal and registration are run
// here. The callback records selected methods; no Harmony/game acceptance is claimed.
internal static class AdapterRegistrationTests
{
    internal static void Run()
    {
        var checks = 0;
        void Check(bool value, string message)
        {
            checks++;
            if (!value) throw new Exception(message);
        }

        var foreignBase = ForeignType("ForeignBase", typeof(AdapterCard), title: true, turnEnd: true);
        var foreignCard = ForeignType("ForeignCard", foreignBase, description: true, overload: true);
        Check(foreignBase.Assembly != typeof(AdapterCard).Assembly, "Fixture must be in another assembly.");
        var discovered = BeastCardAdapterRegistry.LoadedCardTypes(typeof(AdapterCard)).ToArray();
        Check(discovered.Contains(foreignBase) && discovered.Contains(foreignCard), "Warm discovery must include third-party cards.");
        Check(!discovered.Contains(typeof(GenericCard<>)), "Open generic types cannot be patched.");

        var registered = new List<Type>();
        var patched = new List<MethodInfo>();
        var registry = Create(registered, patched);
        registry.Ensure(foreignCard);
        Check(registered.SequenceEqual(new[] { typeof(AdapterCard), foreignBase, foreignCard }), "Register complete foreign inheritance chain base-first.");
        Check(patched.Contains(foreignBase.GetMethod("get_Title")!), "Foreign inherited title override must be adapted.");
        Check(patched.Contains(foreignBase.GetMethod(nameof(AdapterCard.OnTurnEndInHand))!), "Foreign in-hand action override must be adapted.");
        Check(patched.Contains(foreignCard.GetMethod("get_Description")!), "Concrete foreign description override must be adapted.");
        Check(!patched.Contains(foreignCard.GetMethod(nameof(AdapterCard.OnTurnEndInHand), [typeof(int)])!), "Unrelated same-name overload must remain untouched.");
        var initialCount = patched.Count;
        registry.Ensure(foreignCard);
        registry.Ensure(foreignBase);
        Check(registered.Count == 3 && patched.Count == initialCount, "Repeated conversion cannot install duplicate prefixes.");

        // Appears after the initializer's assembly snapshot, as a delayed mod load.
        var late = ForeignType("LateForeignCard", foreignBase, description: true);
        Check(!discovered.Contains(late), "Late fixture must be absent from the initial snapshot.");
        registry.Ensure(late);
        Check(registered.Last() == late && registered.Count == 4, "First conversion must adapt a late-loaded type.");
        Check(patched.Contains(late.GetMethod("get_Description")!), "Late override must be selected before conversion.");
        Check(patched.Count == initialCount + 1, "Late registration must reuse inherited patches.");

        // Client installation order must not change the set of adapted native members.
        var peerPatches = new List<MethodInfo>();
        var peer = Create([], peerPatches);
        peer.Ensure(late);
        peer.Ensure(foreignCard);
        Check(peerPatches.ToHashSet().SetEquals(patched), "Different peer discovery orders must adapt the same members.");
        Check(peerPatches.Count == patched.Count, "Different peer order cannot duplicate shared ancestors.");

        var rejected = false;
        try { registry.Ensure(typeof(string)); } catch (ArgumentException) { rejected = true; }
        Check(rejected, "Non-card types must be rejected.");
        rejected = false;
        try { registry.Ensure(typeof(GenericCard<>)); } catch (ArgumentException) { rejected = true; }
        Check(rejected, "Unbound generic card type must be rejected.");
        registry.Ensure(typeof(GenericCard<int>));
        Check(registered.Contains(typeof(GenericCard<int>)), "Concrete generic card type must be accepted.");

        var attempts = 0;
        var succeeded = 0;
        BeastCardAdapterRegistry? retry = null;
        var member = typeof(AdapterCard).GetProperty(nameof(AdapterCard.Title))!.GetMethod!;
        retry = new BeastCardAdapterRegistry(typeof(AdapterCard), _ =>
        {
            attempts++;
            retry!.PatchOnce(member, "overlay", false, () => succeeded++);
            if (attempts == 1) throw new InvalidOperationException("Simulated failed remaining adapter.");
        });
        try { retry.Ensure(foreignCard); } catch (InvalidOperationException) { }
        retry.Ensure(foreignCard);
        retry.Ensure(foreignCard);
        Check(attempts == 2, "Failed type installation must not certify the type or retry after success.");
        Check(succeeded == 1, "Retry must not duplicate already successful member patches.");
        var patchAttempts = 0;
        var otherMember = typeof(AdapterCard).GetProperty(nameof(AdapterCard.Description))!.GetMethod!;
        try { retry.PatchOnce(otherMember, "overlay", false, () => { patchAttempts++; throw new Exception(); }); }
        catch (Exception) { }
        retry.PatchOnce(otherMember, "overlay", false, () => patchAttempts++);
        Check(patchAttempts == 2, "Failed member patch must remain retryable.");
        retry.PatchOnce(otherMember, "overlay", true, () => patchAttempts++);
        Check(patchAttempts == 3, "A postfix and prefix are separate adapters.");

        Console.WriteLine($"BEAST_ADAPTERS_OK assertions={checks}; harmony-gameplay=NOT_RUN");
    }

    private static BeastCardAdapterRegistry Create(List<Type> registered, List<MethodInfo> patched)
    {
        var native = new[]
        {
            typeof(AdapterCard).GetProperty(nameof(AdapterCard.Title))!.GetMethod!,
            typeof(AdapterCard).GetProperty(nameof(AdapterCard.Description))!.GetMethod!,
            typeof(AdapterCard).GetMethod(nameof(AdapterCard.OnTurnEndInHand))!
        };
        BeastCardAdapterRegistry? registry = null;
        registry = new BeastCardAdapterRegistry(typeof(AdapterCard), types =>
        {
            registered.AddRange(types);
            foreach (var method in native)
            foreach (var type in types)
            foreach (var member in BeastCardAdapterRegistry.DeclaredOverrides(type, method))
                registry!.PatchOnce(member, "overlay", false, () => patched.Add(member));
        });
        return registry;
    }

    private static Type ForeignType(string name, Type parent, bool title = false, bool description = false,
        bool turnEnd = false, bool overload = false)
    {
        var module = AssemblyBuilder.DefineDynamicAssembly(new AssemblyName(name), AssemblyBuilderAccess.Run)
            .DefineDynamicModule(name);
        var type = module.DefineType(name, TypeAttributes.Public, parent);
        type.DefineDefaultConstructor(MethodAttributes.Public);
        foreach (var property in new[] { (nameof(AdapterCard.Title), title), (nameof(AdapterCard.Description), description) })
        {
            if (!property.Item2) continue;
            var original = parent.GetProperty(property.Item1)!.GetMethod!;
            var getter = type.DefineMethod(original.Name, MethodAttributes.Public | MethodAttributes.Virtual |
                MethodAttributes.SpecialName | MethodAttributes.HideBySig, typeof(string), Type.EmptyTypes);
            var il = getter.GetILGenerator();
            il.Emit(OpCodes.Ldstr, name); il.Emit(OpCodes.Ret);
            type.DefineMethodOverride(getter, original);
            type.DefineProperty(property.Item1, PropertyAttributes.None, typeof(string), null).SetGetMethod(getter);
        }
        if (turnEnd)
        {
            var original = parent.GetMethod(nameof(AdapterCard.OnTurnEndInHand))!;
            var method = type.DefineMethod(original.Name, MethodAttributes.Public | MethodAttributes.Virtual |
                MethodAttributes.HideBySig, typeof(void), Type.EmptyTypes);
            method.GetILGenerator().Emit(OpCodes.Ret);
            type.DefineMethodOverride(method, original);
        }
        if (overload)
        {
            var method = type.DefineMethod(nameof(AdapterCard.OnTurnEndInHand), MethodAttributes.Public,
                typeof(void), [typeof(int)]);
            method.GetILGenerator().Emit(OpCodes.Ret);
        }
        return type.CreateType()!;
    }
}

public class AdapterCard
{
    public virtual string Title => "Original title";
    public virtual string Description => "Original rules";
    public virtual void OnTurnEndInHand() { }
}
public class GenericCard<T> : AdapterCard { }
