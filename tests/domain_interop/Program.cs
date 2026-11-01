using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using Volibear.Core;

internal static class Program
{
    private static readonly SteamNativeEntryBinding Channel = new();
    private static readonly List<(string Name, object? Ticket)> Bodies = [];
    private static readonly List<Task> Returned = [];
    private static TaskCompletionSource Gate = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private static readonly Exception Sentinel = new InvalidOperationException("foreign-prefix-exception");
    private static string Mode = "";
    private static int Depth, Checks;
    private static Task? Descendant;
    private static readonly MethodInfo NativeMethod = typeof(Program).GetMethod(nameof(Native), BindingFlags.NonPublic | BindingFlags.Static)!;

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<int> Native(string name, bool delay = false)
    {
        Bodies.Add((name, Channel.Consume()));
        if (delay) await Gate.Task;
        if (name == "native-fault") throw Sentinel;
        return name.Length;
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task Phase()
    {
        Bodies.Add(("phase", Channel.Consume()));
        await Task.Yield();
    }

    private static bool ForeignPrefix(ref string name, ref Task<int> __result)
    {
        if (Depth != 0) return true;
        Depth++;
        try
        {
            if (Mode is "prefix-reentry" or "skip" or "throw" or "change-argument")
                _ = Native("foreign-child");
            if (Mode == "delayed-child") Descendant = DeferredChild();
            if (Mode == "skip") { __result = Task.FromResult(99); return false; }
            if (Mode == "throw") throw Sentinel;
            if (Mode == "change-argument") name = "changed-by-prefix";
            if (Mode == "reset") Channel.Reset();
            return true;
        }
        finally { Depth--; }
    }

    private static async Task DeferredChild()
    {
        await Gate.Task;
        Mode = "";
        _ = await Native("deferred-child");
    }

    private static void ForeignPostfix(Task<int> __result)
    {
        Returned.Add(__result);
        if (Mode != "postfix-reentry" || Depth != 0) return;
        Depth++;
        try { _ = Native("postfix-child"); }
        finally { Depth--; }
    }

    private static void Check(bool value, string why)
    { Checks++; if (!value) throw new InvalidOperationException(why); }

    private static async Task Run()
    {
        var own = new Harmony("Volibear.DomainInterop.NativeEntry");
        var foreign = new Harmony("ThirdParty.DamageModifiers");
        var phase = typeof(Program).GetMethod(nameof(Phase), BindingFlags.NonPublic | BindingFlags.Static)!;
        try
        {
            // Exercise both installation orders, including a later foreign prefix.
            foreach (bool foreignFirst in new[] { true, false })
            {
                void InstallForeign() => foreign.Patch(NativeMethod,
                    prefix: new HarmonyMethod(typeof(Program), nameof(ForeignPrefix)),
                    postfix: new HarmonyMethod(typeof(Program), nameof(ForeignPostfix)));
                if (foreignFirst) InstallForeign();
                Channel.Install(own, NativeMethod); Channel.Install(own, phase);
                if (!foreignFirst) InstallForeign();
                foreach (string mode in new[] { "", "prefix-reentry", "postfix-reentry", "change-argument", "skip", "throw", "reset", "delayed-child" })
                {
                    Channel.Reset(); Bodies.Clear(); Returned.Clear(); Mode = mode;
                    Gate = new(TaskCreationOptions.RunContinuationsAsynchronously);
                    var ticket = new object();
                    Task<int>? actual = null;
                    try
                    {
                        using (Channel.Dispatch(ticket)) actual = Native("primary", delay: true);
                        Check(mode != "throw", "foreign throw must survive");
                    }
                    catch (Exception error) when (ReferenceEquals(error, Sentinel))
                    { Check(mode == "throw", "only expected foreign exception"); }
                    if (actual is not null) Check(Returned.Any(task => ReferenceEquals(task, actual)), "return original native/foreign Task identity");
                    Gate.SetResult();
                    if (actual is not null) Check(await actual == (mode == "skip" ? 99 : mode == "change-argument" ? 17 : 7), "native/foreign result preserved");
                    if (Descendant is not null) { await Descendant; Descendant = null; }
                    var tagged = Bodies.Where(row => row.Ticket is not null).ToArray();
                    if (mode is "skip" or "throw" or "reset") Check(tagged.Length == 0, "cancelled or reset entry cannot donate ticket");
                    else Check(tagged.Length == 1 && ReferenceEquals(tagged[0].Ticket, ticket) &&
                        tagged[0].Name == (mode == "change-argument" ? "changed-by-prefix" : "primary"), "exact primary body owns one ticket");
                    Check(Bodies.Where(row => row.Name.Contains("child")).All(row => row.Ticket is null), "prefix/postfix/deferred children remain untagged");
                    Mode = "";
                    _ = await Native("later");
                    Check(Bodies[^1].Ticket is null, "later ordinary entry cannot reuse ticket");
                }
                Channel.Reset(); Bodies.Clear(); Mode = "";
                var phaseTicket = new object();
                using (Channel.Dispatch(phaseTicket)) await Phase();
                Check(ReferenceEquals(Bodies.Single().Ticket, phaseTicket), "non-generic Task builder is bound");
                using (Channel.Dispatch(new object()))
                {
                    try { await Native("native-fault"); throw new Exception("lost fault"); }
                    catch (Exception error) when (ReferenceEquals(error, Sentinel)) { Checks++; }
                }
                _ = await Native("after-fault");
                Check(Bodies[^1].Ticket is null, "native async fault cannot leak ticket");
                own.UnpatchAll(own.Id); foreign.UnpatchAll(foreign.Id);
            }
            Console.WriteLine($"DOMAIN_NATIVE_ENTRY_PASS checks={Checks} real-harmony=true native-gameplay=NOT_RUN");
        }
        finally { own.UnpatchAll(own.Id); foreign.UnpatchAll(foreign.Id); Channel.Reset(); }
    }

    private static void Main() { Run().GetAwaiter().GetResult(); CardContributionTests.Run(); }
}
