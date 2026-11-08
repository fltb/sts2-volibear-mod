using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Saves;
using Volibear.Core;
using Volibear.Presentation;
using GDictionary = Godot.Collections.Dictionary;

namespace Volibear;

internal static partial class AudioReceiptProbe
{
    private sealed record SoundState(StepRow Row, Node Root, string Event, string Cue, HashSet<ulong> Before);
    private static MethodInfo Method(Type type, string name) => AccessTools.Method(type, name) ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo Handler(string name) => Method(typeof(AudioReceiptProbe), name);
    private static void InstallObservers(Harmony harmony)
    {
        harmony.Patch(Method(typeof(PowerAudioReceipts), "Capture"), postfix: new(Handler(nameof(PowerCaptured))));
        harmony.Patch(Method(typeof(PowerAudioReceipts), "Enter"), postfix: new(Handler(nameof(FrameEntered))));
        harmony.Patch(Method(typeof(CardPresentationReceipts), "Publish"), transpiler: new(Handler(nameof(ObserveCardNotify))));
        var owner = BridgeType.GetNestedType("OwnerScope", BindingFlags.NonPublic)!;
        foreach (var name in new[] { "PowerAudio", "CardAudio" })
            harmony.Patch(Method(owner, name), transpiler: new(Handler(nameof(ObserveSoundCall))));
    }
    private static void Guard(Action observe)
    {
        try { observe(); }
        catch (Exception error) { Errors.Add(error.GetType().Name + ":" + error.Message); }
    }
    private static long Sequence() => Interlocked.Increment(ref sequence);
    private static void PowerCaptured(PowerModel power, int delta, bool silent, PowerAudioReceipt? __result)
    {
        if (Active is not { } row || __result is not { } receipt) return;
        Guard(() => row.receipts.Add(new { sequence = Sequence(), kind = "power", id = receipt.Transaction,
            cue = "sfx." + receipt.Cue, powerRef = Id(receipt.Power), power = power.GetType().Name,
            delta, amount = power.Amount, silent, sourceRef = Id(receipt.CardSource),
            sameOwner = ReferenceEquals(receipt.Owner, Owner), sameCombat = ReferenceEquals(receipt.Combat, Combat),
            sameApplier = ReferenceEquals(receipt.Applier, Owner), registered = receipt.Owner.Powers.Contains(power) }));
    }
    private static void CardCaptured(CommittedCardPresentation receipt)
    {
        if (Active is not { } row) return;
        Guard(() => row.receipts.Add(new { sequence = Sequence(), kind = "card", id = receipt.Id,
            cue = "sfx." + receipt.Effect, cardRef = Id(receipt.Card), sourceRef = Id(receipt.Source),
            source = receipt.Source.GetType().Name, from = receipt.From.ToString(), pile = receipt.Card.Pile?.Type.ToString(),
            sameOwner = ReferenceEquals(receipt.Owner, Owner), sameCombat = ReferenceEquals(receipt.Combat, Combat),
            replacementPile = row.id == "purify" ? Replacement?.Pile?.Type.ToString() : null }));
    }
    private static void FrameEntered(int state, PowerModel power, object __result)
    {
        if (Active is not { } row || state != -1) return;
        Guard(() =>
        {
            var ticket = __result.GetType().GetField("Ticket", Flags)!.GetValue(__result);
            object? Get(string name) => ticket?.GetType().GetField(name, Flags)!.GetValue(ticket);
            row.frames.Add(new { power = power.GetType().Name, powerRef = Id(power),
                ticket = Get("Id"), silent = Get("Silent"), sourceRef = Id(Get("Card")),
                sameOwner = ticket is not null && ReferenceEquals(Get("Owner"), Owner) });
        });
    }
    private static SoundState? BeforeSound(VolibearEffects effects, string eventId, string cueId)
    {
        if (Active is not { } row) return null;
        SoundState? result = null;
        Guard(() =>
        {
            var root = (Node)typeof(VolibearEffects).GetField("_root", Flags)!.GetValue(effects)!;
            result = new(row, root, eventId, cueId, root.GetChildren().OfType<AudioStreamPlayer>().Select(p => p.GetInstanceId()).ToHashSet());
        });
        return result;
    }
    private static void AfterSound(SoundState? state, bool accepted)
    {
        if (state is null) return;
        Guard(() =>
        {
            var players = state.Root.GetChildren().OfType<AudioStreamPlayer>().Where(p => !state.Before.Contains(p.GetInstanceId())).ToArray();
            var gains = (GDictionary)Method(typeof(VolibearEffects), "ReadGameVolume").Invoke(null, null)!;
            var settings = SaveManager.Instance.SettingsSave;
            bool focused = DisplayServer.GetName() == "headless" || DisplayServer.WindowIsFocused();
            var voices = state.Root.Get("_voices").AsGodotDictionary();
            var mix = state.Root.Get("_mix").AsGodotDictionary();
            var nodes = new List<object>();
            foreach (var player in players)
            {
                var record = voices.Values.Select(v => v.AsGodotDictionary()).Single(r => r["node"].AsGodotObject().GetInstanceId() == player.GetInstanceId());
                var cue = record["cue"].AsGodotDictionary();
                nodes.Add(new { nodeId = player.GetInstanceId(), playing = player.Playing, inTree = player.IsInsideTree(),
                    streamType = player.Stream?.GetClass().ToString(), length = player.Stream?.GetLength(),
                    bus = player.Bus.ToString(), busMuted = AudioServer.IsBusMute(AudioServer.GetBusIndex(player.Bus)),
                    busVolumeDb = AudioServer.GetBusVolumeDb(AudioServer.GetBusIndex(player.Bus)),
                    volumeLinear = player.VolumeLinear, file = cue["file"].AsString(),
                    cue = cue["id"].AsString(), category = cue["bus"].AsString(), authoredDb = cue["gain_db"].AsDouble(),
                    mixDb = mix["sfx_bus"].AsDouble(), headroomDb = mix["headroom_db"].AsDouble(),
                    voiceDivisor = Math.Max(1, voices.Count) });
            }
            state.Row.dispatches.Add(new { sequence = Sequence(), eventId = state.Event, cue = state.Cue, accepted,
                master = settings.VolumeMaster, sfx = settings.VolumeSfx, ambience = settings.VolumeAmbience,
                focused, muteInBackground = SaveManager.Instance.PrefsSave.MuteInBackground,
                effectiveSfx = gains["Sfx"].AsDouble(), nodes });
        });
    }
    private static IEnumerable<CodeInstruction> ObserveCardNotify(IEnumerable<CodeInstruction> instructions)
    {
        int count = 0;
        foreach (var original in instructions)
        {
            var code = new CodeInstruction(original);
            if (code.operand is MethodInfo method && method.DeclaringType == typeof(CardReceiptPolicy) && method.Name == "Notify")
            {
                if (code.blocks.Count != 0) throw new InvalidOperationException("Unexpected receipt notification EH boundary");
                var duplicate = new CodeInstruction(OpCodes.Dup); duplicate.labels.AddRange(code.labels); code.labels.Clear();
                yield return duplicate; yield return new(OpCodes.Call, Handler(nameof(CardCaptured))); count++;
            }
            yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Expected exactly one real card receipt notification");
    }
    private static IEnumerable<CodeInstruction> ObserveSoundCall(IEnumerable<CodeInstruction> instructions, ILGenerator generator)
    {
        var play = Method(typeof(VolibearEffects), nameof(VolibearEffects.PlaySound));
        var types = new[] { typeof(VolibearEffects) }.Concat(play.GetParameters().Select(p => p.ParameterType)).ToArray();
        var args = types.Select(generator.DeclareLocal).ToArray();
        var observation = generator.DeclareLocal(typeof(SoundState));
        var returned = generator.DeclareLocal(typeof(bool)); int count = 0;
        foreach (var original in instructions)
        {
            var code = new CodeInstruction(original);
            if (code.Calls(play))
            {
                if (code.blocks.Count != 0) throw new InvalidOperationException("Unexpected sound dispatch EH boundary");
                for (int i = args.Length - 1; i >= 0; i--)
                {
                    var store = new CodeInstruction(OpCodes.Stloc, args[i]);
                    if (i == args.Length - 1) { store.labels.AddRange(code.labels); code.labels.Clear(); }
                    yield return store;
                }
                for (int i = 0; i < 3; i++) yield return new(OpCodes.Ldloc, args[i]);
                yield return new(OpCodes.Call, Handler(nameof(BeforeSound))); yield return new(OpCodes.Stloc, observation);
                foreach (var arg in args) yield return new(OpCodes.Ldloc, arg);
                yield return code; // Original PlaySound call and arguments remain intact.
                yield return new(OpCodes.Stloc, returned); yield return new(OpCodes.Ldloc, observation);
                yield return new(OpCodes.Ldloc, returned); yield return new(OpCodes.Call, Handler(nameof(AfterSound)));
                yield return new(OpCodes.Ldloc, returned); count++;
            }
            else yield return code;
        }
        if (count != 1) throw new InvalidOperationException("Expected exactly one original semantic PlaySound call");
    }
    private static object[] InspectRuntimeBoundaries()
    {
        var bodies = (IEnumerable<MethodInfo>)Method(typeof(PowerAudioReceipts), "NativeBodies").Invoke(null, null)!;
        return bodies.Select(body =>
        {
            var code = PatchProcessor.GetCurrentInstructions(body).ToList();
            var signal = code.Select((c, i) => (c, i)).Where(p => p.c.operand is MethodInfo m &&
                m.DeclaringType?.Name.StartsWith("AsyncTaskMethodBuilder") == true && m.Name is "SetResult" or "SetException").ToArray();
            int boundaries = code.Count(c => c.operand is MethodInfo m &&
                ((m.DeclaringType == typeof(PowerModel) && m.Name is "ApplyInternal" or "SetAmount") ||
                 (m.DeclaringType == typeof(DomainCardContributions) && m.Name is "ApplyCommit" or "AmountCommit")));
            bool closed = signal.Length == 2 && signal.All(p => code[p.i - 1].Calls(Method(typeof(PowerAudioReceipts), "Close")));
            int asyncAudio = code.Count(c => c.operand is MethodInfo m && m.DeclaringType == typeof(PowerAudioReceipts) && typeof(Task).IsAssignableFrom(m.ReturnType));
            var entry = typeof(PowerCmd).GetMethods(BindingFlags.Static | BindingFlags.Public).Single(m =>
                m.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()?.StateMachineType == body.DeclaringType);
            var patches = Harmony.GetPatchInfo(entry);
            int audioEntryPatches = patches is null ? 0 : patches.Prefixes.Concat(patches.Postfixes).Concat(patches.Transpilers).Concat(patches.Finalizers)
                .Count(p => p.owner.StartsWith("Volibear.Presentation.PowerAudioReceipts") || p.owner.StartsWith("Volibear.AudioReceiptProbe"));
            if (!closed || boundaries != 1 || asyncAudio != 0 || audioEntryPatches != 0) throw new InvalidOperationException($"Native mechanics/audio boundary changed: closed={closed} boundaries={boundaries} asyncAudio={asyncAudio} patches={audioEntryPatches}");
            return (object)new { method = body.DeclaringType!.Name.Contains("ModifyAmount") ? "ModifyAmount" : "Apply",
                nativeSignals = signal.Length, closeBeforeSignals = closed, mutationBoundaries = boundaries,
                audioCallsReturningTask = asyncAudio, audioEntryPatches };
        }).ToArray();
    }
}
