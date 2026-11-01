using System.Reflection;
using Volibear;

public interface IProbeLobby
{
    void PlayerConnected(ulong player);
    void BeginRun(string seed, List<string> acts, IReadOnlyList<string> modifiers);
    void LocalPlayerDisconnected(string reason);
    void RemotePlayerDisconnected(ulong player);
    Task<bool> ShouldAllowRunToBegin();
}
public interface IUnknownLobby { void UnreviewedApi(); }
public interface IBadBeginLobby { int BeginRun(); }
public sealed class NativeShape(int value, string label = "default")
{
    public int Value { get; } = value;
    public string Label = label;
    public string Call(int amount, string suffix = "optional") => amount + ":" + suffix;
    public int Nullable(int? value) => value ?? -1;
    public string Ambiguous(IComparable arg) => "first";
    public string Ambiguous(object arg) => "second";
    public string Generic<T>(T arg) => "not a non-generic contract";
    public void Throw(Exception error) => throw error;
}
internal static class Program
{
    private static int assertions;
    private static void Check(bool ok) { assertions++; if (!ok) throw new Exception("Assertion " + assertions); }
    private static void Throws<T>(Action action) where T : Exception
    { assertions++; try { action(); } catch (T) { return; } throw new Exception("Expected " + typeof(T).Name); }
    private static async Task<int> Main()
    {
        var shape = (NativeShape)NativeLobbyApi.New(typeof(NativeShape), 7);
        Check(shape.Value == 7 && shape.Label == "default");
        Check((int)NativeLobbyApi.Get(shape, "Value")! == 7);
        Check((string)NativeLobbyApi.Get(shape, "Label")! == "default");
        Check((string)NativeLobbyApi.Call(shape, "Call", 3)! == "3:optional");
        Check((int)NativeLobbyApi.Call(shape, "Nullable", [null])! == -1);
        Throws<MissingMethodException>(() => NativeLobbyApi.Call(shape, "Call", "wrong argument"));
        Throws<MissingMethodException>(() => NativeLobbyApi.Call(shape, "Call", [null]));
        Throws<MissingMemberException>(() => NativeLobbyApi.Get(shape, "Absent"));
        Throws<MissingMethodException>(() => NativeLobbyApi.Call(shape, "Absent"));
        Throws<AmbiguousMatchException>(() => NativeLobbyApi.Call(shape, "Ambiguous", "both"));
        Throws<MissingMethodException>(() => NativeLobbyApi.Call(shape, "Generic", 1));
        var original = new InvalidOperationException("native failure");
        try { NativeLobbyApi.Call(shape, "Throw", original); throw new Exception("Not propagated"); }
        catch (InvalidOperationException error) { Check(ReferenceEquals(error, original)); }
        var listener = NativeLobbyProbeListener.Create(typeof(IProbeLobby));
        var contract = (IProbeLobby)listener;
        contract.PlayerConnected(1);
        Check(listener.Failure is null && !listener.Began.Task.IsCompleted);
        Check(await contract.ShouldAllowRunToBegin());
        contract.BeginRun("seed", ["act"], Array.Empty<string>());
        Check((string)(await listener.Began.Task)[0]! == "seed");
        contract.BeginRun("again", [], []);
        Check(listener.Failure is not null);
        listener = NativeLobbyProbeListener.Create(typeof(IProbeLobby)); contract = (IProbeLobby)listener;
        contract.RemotePlayerDisconnected(2);
        Check(listener.Failure is not null && listener.Began.Task.IsFaulted);
        listener = NativeLobbyProbeListener.Create(typeof(IProbeLobby)); contract = (IProbeLobby)listener;
        listener.AllowDisconnect = true; contract.LocalPlayerDisconnected("expected disconnect");
        Check(listener.Failure is null);
        Throws<MissingMethodException>(() => NativeLobbyProbeListener.Create(typeof(IUnknownLobby)));
        Throws<MissingMethodException>(() => NativeLobbyProbeListener.Create(typeof(IBadBeginLobby)));
        Console.WriteLine($"NATIVE_LOBBY_BINDING_PASS assertions={assertions} native-network=NOT_RUN");
        return 0;
    }
}
