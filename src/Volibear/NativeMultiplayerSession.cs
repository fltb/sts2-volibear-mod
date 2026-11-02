using System;
using System.Collections;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Runs;
using Volibear.Content;

namespace Volibear;

/// <summary>Two actual native ENet peers. Only installed by the isolated acceptance runner.</summary>
internal sealed class NativeMultiplayerSession(bool host, ushort port, Func<string, Task> barrier)
{
    private object? service;
    private NativeLobbyProbeListener? listener;
    private bool nativeJoinLoop;
    internal readonly System.Collections.Generic.List<string> Calls = [];
    internal bool Host => host;
    internal ulong NetId => (ulong)NativeLobbyApi.Get(service!, "NetId")!;
    internal bool Connected => service is not null && (bool)NativeLobbyApi.Get(service, "IsConnected")!;
    internal int PeerCount => host && service is not null
        ? ((IEnumerable)NativeLobbyApi.Get(service, "ConnectedPeers")!).Cast<object>().Count()
        : Connected ? 1 : 0;
    internal static Type NativeType(string name) => typeof(RunManager).Assembly.GetType("MegaCrit.Sts2.Core." + name, true)!;

    internal void Pump()
    {
        if (listener?.Failure is { } failure) throw failure;
        if (service is not null && !nativeJoinLoop) NativeLobbyApi.Call(service, "Update");
    }

    internal async Task Until(Func<bool> condition, string stage, int timeoutSeconds = 90)
    {
        var clock = Stopwatch.StartNew();
        while (!condition())
        {
            if (clock.Elapsed.TotalSeconds > timeoutSeconds) throw new TimeoutException(stage);
            Pump();
            var tree = (SceneTree)Engine.GetMainLoop();
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
        if (listener?.Failure is { } failure) throw failure;
    }

    internal async Task<object?> Await(object? result, string stage)
    {
        if (result is not Task task) throw new InvalidOperationException(stage + " must return a native Task");
        // Native scene loads include cold Common/character GPU preloads (measured
        // over 200s even in singleplayer). Keep network handshakes at 90s; only
        // actual run scene-loading Tasks receive the bounded loading budget.
        int timeout = stage is "native StartNewMultiplayerRun" or "native saved multiplayer load" ? 360 : 90;
        await Until(() => task.IsCompleted, stage, timeout);
        await task;
        return task.GetType().GetProperty("Result")?.GetValue(task);
    }

    private object Call(object owner, string method, params object?[] args)
    {
        Calls.Add(owner.GetType().Name + "." + method);
        return NativeLobbyApi.Call(owner, method, args)!;
    }

    private void StartHost()
    {
        service = NativeLobbyApi.New(NativeType("Multiplayer.NetHostGameService"));
        if (Call(service, "StartENetHost", port, 1) is { } error)
            throw new InvalidOperationException("Native ENet listen failed: " + error);
    }

    private async Task<object> Join()
    {
        var type = NativeType("Multiplayer.Game.JoinFlow");
        var flow = NativeLobbyApi.New(type);
        var initializer = NativeLobbyApi.New(NativeType("Multiplayer.Connection.ENetClientConnectionInitializer"), 2UL, "127.0.0.1", port);
        // In pinned 0.107.1 Begin creates NetService before its first await and
        // starts NetServiceUpdateLoop using this real SceneTree. A null tree or
        // reading NetService before Begin would make the client unable to join.
        nativeJoinLoop = true;
        try
        {
            var pending = Call(flow, "Begin", initializer, (SceneTree)Engine.GetMainLoop());
            service = NativeLobbyApi.Get(flow, "NetService") ?? throw new InvalidOperationException("JoinFlow did not create its native service");
            return await Await(pending, "native JoinFlow.Begin") ?? throw new InvalidOperationException("Native join returned no result");
        }
        finally { nativeJoinLoop = false; }
    }

    internal async Task<RunState> Start(string seed)
    {
        listener = NativeLobbyProbeListener.Create(NativeType("Multiplayer.Game.Lobby.IStartRunLobbyListener"));
        object lobby;
        if (host)
        {
            StartHost();
            lobby = NativeLobbyApi.New(NativeType("Multiplayer.Game.Lobby.StartRunLobby"), GameMode.Standard, service, listener, 2);
            var unlocks = Call(SaveManager.Instance, "GenerateUnlockStateFromProgress");
            Call(lobby, "AddLocalHostPlayer", unlocks, 0);
            Call(lobby, "SetLocalCharacter", ModelDb.Character<VolibearCharacter>());
            Call(lobby, "SetSeed", seed);
            await barrier("new-listening");
        }
        else
        {
            await barrier("new-listening");
            var join = await Join();
            var message = NativeLobbyApi.Get(join, "joinResponse") ?? throw new InvalidOperationException("Expected native new-run lobby join response");
            lobby = NativeLobbyApi.New(NativeType("Multiplayer.Game.Lobby.StartRunLobby"), GameMode.Standard, service, listener, 2);
            Call(lobby, "InitializeFromMessage", message);
            Call(lobby, "SetLocalCharacter", ModelDb.Character<VolibearCharacter>());
        }
        await Until(() => ((IEnumerable)NativeLobbyApi.Get(lobby, "Players")!).Cast<object>().Count() == 2, "both native lobby players");
        await barrier("new-lobby-joined");
        Call(lobby, "SetReady", true);
        await Until(() => listener.Began.Task.IsCompleted, "native lobby BeginRun");
        var begin = await listener.Began.Task;
        if (begin.Length != 3 || begin[0] is not string nativeSeed || nativeSeed != seed)
            throw new InvalidOperationException("Unexpected native BeginRun payload");
        // Native selection screens detach their lobby handlers before RunLobby
        // is installed. Keep the connected service and input synchronizer alive.
        Call(lobby, "CleanUp", false);
        return (RunState)(await Await(Call(NGame.Instance!, "StartNewMultiplayerRun", lobby, true, begin[1], begin[2], seed, 0),
            "native StartNewMultiplayerRun") ?? throw new InvalidOperationException("Native new run missing"));
    }

    internal async Task<RunState> Load(SerializableRun? checkpoint)
    {
        listener = NativeLobbyProbeListener.Create(NativeType("Multiplayer.Game.Lobby.ILoadRunLobbyListener"));
        object lobby;
        if (host)
        {
            if (checkpoint is null) throw new InvalidOperationException("Host native checkpoint missing");
            StartHost();
            lobby = NativeLobbyApi.New(NativeType("Multiplayer.Game.Lobby.LoadRunLobby"), service, listener, checkpoint);
            Call(lobby, "AddLocalHostPlayer");
            await barrier("load-listening");
        }
        else
        {
            await barrier("load-listening");
            var join = await Join();
            var message = NativeLobbyApi.Get(join, "loadJoinResponse") ?? throw new InvalidOperationException("Expected native saved-run lobby join response");
            lobby = NativeLobbyApi.New(NativeType("Multiplayer.Game.Lobby.LoadRunLobby"), service, listener, message);
        }
        await Until(() => ((IEnumerable)NativeLobbyApi.Get(lobby, "ConnectedPlayerIds")!).Cast<object>().Count() == 2, "original player identities in saved-run lobby");
        await barrier("load-lobby-joined");
        Call(lobby, "SetReady", true);
        await Until(() => listener.Began.Task.IsCompleted, "native saved lobby BeginRun");
        await listener.Began.Task;
        var save = (SerializableRun)NativeLobbyApi.Get(lobby, "Run")!;
        Call(lobby, "CleanUp", false);
        var run = RunState.FromSerializable(save);
        Calls.Add("RunState.FromSerializable");
        await Await(Call(RunManager.Instance, "SetUpSavedMultiplayer", run, lobby), "native saved multiplayer setup");
        await Await(Call(NGame.Instance!, "LoadRun", run, save.PreFinishedRoom), "native saved multiplayer load");
        return run;
    }

    internal object Receipt()
    {
        if (!Connected || NetId != (host ? 1UL : 2UL) || PeerCount != 1
            || !ReferenceEquals(NativeLobbyApi.Get(RunManager.Instance, "NetService"), service))
            throw new InvalidOperationException("Native two-peer run is not connected");
        var transport = NativeLobbyApi.Get(service!, host ? "NetHost" : "NetClient")!;
        if (transport.GetType().Name != (host ? "ENetHost" : "ENetClient"))
            throw new InvalidOperationException("Acceptance requires the game's actual ENet transport");
        var checksum = NativeLobbyApi.Get(RunManager.Instance, "ChecksumTracker")!;
        var replay = NativeLobbyApi.Get(RunManager.Instance, "CombatReplayWriter")!;
        if (NativeLobbyApi.Get(checksum, "IsEnabled") is not true || NativeLobbyApi.Get(replay, "IsEnabled") is not true)
            throw new InvalidOperationException("Native checksum/replay mechanisms must remain enabled");
        return new { netId = NetId, peerCount = PeerCount, service = service!.GetType().Name,
            transport = transport.GetType().Name, nativeChecksums = true, nativeReplay = true };
    }

    internal void DisconnectClient()
    {
        if (host) throw new InvalidOperationException("Only the client is intentionally disconnected");
        if (listener is not null) listener.AllowDisconnect = true;
        var quit = Enum.Parse(NativeType("Entities.Multiplayer.NetError"), "Quit");
        // Orderly native quit sends the game's Disconnection packet before
        // closing ENet. Immediate transport teardown leaves host membership stale.
        Call(service!, "Disconnect", quit, false);
    }

    internal void AllowDisconnect() { if (listener is not null) listener.AllowDisconnect = true; }
}
