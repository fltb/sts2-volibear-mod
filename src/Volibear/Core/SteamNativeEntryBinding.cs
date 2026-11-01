using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using HarmonyLib;

namespace Volibear.Core;

/// <summary>
/// Transfers provenance to one native async body. Public-entry prefixes run with the
/// ticket masked; the original wrapper arms it immediately before Builder.Start.
/// A prefix's recursive call, skipped original, postfix or delayed continuation cannot
/// take the caller's ticket. The native Task and all foreign patches remain intact.
/// </summary>
internal sealed class SteamNativeEntryBinding
{
    private sealed class Ticket(object? value)
    {
        private object? _value = value;
        internal object? Consume() => Interlocked.Exchange(ref _value, null);
    }

    internal sealed class Entry
    {
        internal readonly SteamNativeEntryBinding Channel;
        internal readonly Entry? Previous;
        private Ticket? _ticket;
        internal readonly long Generation;
        internal bool Closed;
        private Entry(SteamNativeEntryBinding channel, Ticket? ticket, Entry? previous)
        { Channel = channel; _ticket = ticket; Previous = previous; Generation = channel._generation; }
        internal object? Take()
        {
            if (Closed || Generation != Channel._generation) return null;
            var ticket = _ticket; _ticket = null;
            return ticket;
        }
        internal void Close() { Closed = true; _ticket = null; }
        internal static Entry Begin(SteamNativeEntryBinding channel)
        {
            var entry = new Entry(channel, channel._pending.Value, channel._entries.Value);
            channel._pending.Value = null;
            channel._entries.Value = entry;
            return entry;
        }
    }

    private sealed class DispatchScope(SteamNativeEntryBinding channel, Ticket? previous, long generation) : IDisposable
    {
        private bool _disposed;
        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            if (channel._generation == generation) channel._pending.Value = previous;
        }
    }

    private readonly AsyncLocal<Ticket?> _pending = new();
    private readonly AsyncLocal<Entry?> _entries = new();
    private readonly AsyncLocal<Ticket?> _body = new();
    private long _generation;
    private static readonly Dictionary<MethodBase, SteamNativeEntryBinding> Channels = new();
    private static readonly object RegistrationLock = new();

    internal IDisposable Dispatch(object? value)
    {
        var previous = _pending.Value;
        _pending.Value = value is null ? null : new Ticket(value);
        return new DispatchScope(this, previous, _generation);
    }

    internal object? Consume()
    {
        var ticket = _body.Value;
        _body.Value = null;
        return ticket?.Consume();
    }

    internal void Reset()
    { _generation++; _pending.Value = null; _entries.Value = null; _body.Value = null; }

    private static void Prefix(MethodBase __originalMethod, out Entry __state)
    { __state = Entry.Begin(Channels[__originalMethod]); }

    private static void Finalizer(Entry? __state)
    {
        if (__state is null) return;
        var channel = __state.Channel;
        __state.Close();
        if (ReferenceEquals(channel._entries.Value, __state))
        {
            channel._entries.Value = __state.Generation == channel._generation ? __state.Previous : null;
            channel._body.Value = null;
        }
    }

    private static void ArmNativeBody(MethodBase method)
    {
        var channel = Channels[method];
        channel._body.Value = channel._entries.Value?.Take() as Ticket;
    }

    private static IEnumerable<CodeInstruction> Wrapper(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var machine = __originalMethod.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Steam entry has no native async state machine: " + __originalMethod);
        var getMethod = typeof(MethodBase).GetMethod(nameof(MethodBase.GetMethodFromHandle), [typeof(RuntimeMethodHandle)])!;
        var arm = AccessTools.Method(typeof(SteamNativeEntryBinding), nameof(ArmNativeBody));
        int starts = 0;
        foreach (var instruction in instructions)
        {
            if (instruction.operand is MethodInfo method && method.Name == "Start" && method.IsGenericMethod &&
                method.GetGenericArguments().SequenceEqual([machine]) &&
                (method.DeclaringType == typeof(AsyncTaskMethodBuilder) ||
                 method.DeclaringType?.IsGenericType == true && method.DeclaringType.GetGenericTypeDefinition() == typeof(AsyncTaskMethodBuilder<>)))
            {
                var load = new CodeInstruction(OpCodes.Ldtoken, __originalMethod);
                load.labels.AddRange(instruction.labels); instruction.labels.Clear();
                load.blocks.AddRange(instruction.blocks); instruction.blocks.Clear();
                yield return load;
                yield return new(OpCodes.Call, getMethod);
                yield return new(OpCodes.Call, arm);
                starts++;
            }
            yield return instruction;
        }
        if (starts != 1) throw new InvalidOperationException("Steam entry Builder.Start shape changed: " + __originalMethod + "; count=" + starts);
    }

    internal void Install(Harmony harmony, MethodInfo method)
    {
        if (method.IsGenericMethod || method.DeclaringType?.IsGenericType == true)
            throw new NotSupportedException("Steam entry binding requires a closed non-generic public method.");
        lock (RegistrationLock)
        {
            if (Channels.TryGetValue(method, out var prior) && !ReferenceEquals(prior, this))
                throw new InvalidOperationException("Native Steam entry already has another provenance channel: " + method);
            Channels[method] = this;
            // Ordering is explicit and remains stable if a normal foreign prefix is added later.
            // A patch that deliberately runs before this isolation boundary must itself preserve
            // provenance; replacing/transpiling away the native body is not a native contribution.
            harmony.Patch(method,
                prefix: new HarmonyMethod(AccessTools.Method(typeof(SteamNativeEntryBinding), nameof(Prefix))) { priority = int.MaxValue },
                transpiler: new HarmonyMethod(AccessTools.Method(typeof(SteamNativeEntryBinding), nameof(Wrapper))) { priority = int.MinValue },
                finalizer: new HarmonyMethod(AccessTools.Method(typeof(SteamNativeEntryBinding), nameof(Finalizer))) { priority = int.MinValue });
        }
    }
}
