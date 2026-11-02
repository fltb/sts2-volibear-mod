using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using Volibear.Content;
using Volibear.Presentation;

internal static class Program
{
    private static int checks, recorded, nativeFinishes, entered, shown;
    private static readonly List<Creature> killed = [];
    private static readonly SerializableRun snapshot = new();
    private static SerializableRun? displayed;
    private static void Need(bool ok, string why) { checks++; if (!ok) throw new Exception(why); }
    private static T Empty<T>() => (T)RuntimeHelpers.GetUninitializedObject(typeof(T));
    private static void Field(object o, string name, object? value) => AccessTools.Field(o.GetType(), name).SetValue(o, value);
    private static object? Call(string name, params object[] args) => AccessTools.Method(typeof(VolibearArchitectEnding), name).Invoke(null, args);
    private static bool Record(bool isVictory, ref SerializableRun __result) { Need(isVictory, "native record stays victory"); recorded++; __result = snapshot; return false; }
    private static bool NativeFinish(ref Task __result) { nativeFinishes++; __result = Task.CompletedTask; return false; }
    private static bool Enter(Creature creature) { entered++; Need(creature.IsAlive, "domain entry preserves living character"); return false; }
    private static bool Show(SerializableRun snapshot) { shown++; displayed = snapshot; return false; }
    private static bool Wait(ref Task __result) { __result = Task.CompletedTask; return false; }
    private static bool Kill(Creature creature, bool force, ref Task __result) { Need(force, "other players retain forced kill"); killed.Add(creature); Field(creature, "_currentHp", 0); __result = Task.CompletedTask; return false; }
    private static bool Event(ref EventModel __result) { __result = Empty<TheArchitect>(); return false; }
    private static (RunManager Manager, RunState State, Creature Bear, Creature Other) Fixture(bool bear = true)
    {
        Player Player(CharacterModel character)
        {
            var p = Empty<Player>(); var c = Empty<Creature>();
            Field(p, "<Character>k__BackingField", character); Field(p, "<Creature>k__BackingField", c);
            Field(c, "<Player>k__BackingField", p); Field(c, "_currentHp", 37); return p;
        }
        var p0 = Player(bear ? Empty<VolibearCharacter>() : Empty<Ironclad>());
        var p1 = Player(Empty<Ironclad>());
        var state = Empty<RunState>();
        Field(state, "_players", new List<Player> { p0, p1 });
        Field(state, "_currentRooms", new List<AbstractRoom> { Empty<EventRoom>() });
        var manager = Empty<RunManager>(); Field(manager, "<State>k__BackingField", state);
        return (manager, state, p0.Creature, p1.Creature);
    }
    public static void Main()
    {
        var fixture = new Harmony("Volibear.Tests.ArchitectEnding");
        var own = typeof(VolibearArchitectEnding);
        void Prefix(MethodInfo target, string method) => fixture.Patch(target, prefix: new(typeof(Program), method));
        try
        {
            var native = VolibearArchitectEnding.NativeBody();
            var original = PatchProcessor.GetOriginalInstructions(native).ToArray();
            VolibearArchitectEnding.Install();
            var current = PatchProcessor.GetCurrentInstructions(native).ToArray();
            Need(current.Count(c => c.Calls(AccessTools.Method(own, "RecordVictory"))) == 1, "one exact victory record call replacement");
            Need(current.Count(c => c.Calls(AccessTools.Method(own, "FinishVictory"))) == 1, "one exact victory finish call replacement");
            Need(current.Count(c => c.Calls(AccessTools.Method(typeof(TheArchitect), nameof(TheArchitect.TriggerVictory)))) == 1, "native victory trigger retained");
            Need(original.Length == current.Length, "no async state-machine instructions removed");
            Need(new Harmony("Volibear.ArchitectEnding").GetPatchedMethods().Count() == 2, "only victory body and terminal predicate patched");
            foreach (var bad in new[] { Array.Empty<CodeInstruction>(), original.Concat(original).ToArray(), original.Reverse().ToArray() })
            {
                bool rejected = false;
                try { VolibearArchitectEnding.Rewrite(bad).ToArray(); } catch (InvalidOperationException) { rejected = true; }
                Need(rejected, "changed native anchors/order rejected");
            }
            Prefix(AccessTools.Method(typeof(RunManager), nameof(RunManager.OnEnded)), nameof(Record));
            Prefix(AccessTools.Method(typeof(RunManager), "GuaranteeKillAllPlayers"), nameof(NativeFinish));
            Prefix(AccessTools.Method(own, "EnterDomain"), nameof(Enter));
            Prefix(AccessTools.Method(own, "ShowVictory"), nameof(Show));
            Prefix(AccessTools.PropertyGetter(typeof(EventRoom), nameof(EventRoom.LocalMutableEvent)), nameof(Event));
            Prefix(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Kill), [typeof(Creature), typeof(bool)]), nameof(Kill));
            foreach (var method in typeof(Cmd).GetMethods().Where(m => m.Name is "Wait" or "CustomScaledWait")) Prefix(method, nameof(Wait));
            var mixed = Fixture();
            Need(!mixed.State.IsGameOver, "living run starts active");
            var returned = Call("RecordVictory", mixed.Manager, true);
            ((Task)Call("FinishVictory", mixed.Manager)!).GetAwaiter().GetResult();
            Need(recorded == 1 && ReferenceEquals(returned, snapshot) && ReferenceEquals(displayed, snapshot), "single native victory snapshot reaches stock screen unchanged");
            Need(entered == 1 && shown == 1 && nativeFinishes == 0, "only bear branch replaces terminal kill sequence");
            Need(mixed.Bear.CurrentHp == 37 && mixed.Bear.IsAlive && !killed.Contains(mixed.Bear), "no bear HP mutation or death command");
            Need(killed.SequenceEqual(new[] { mixed.Other }) && mixed.Other.IsDead, "other multiplayer character retains native forced death");
            Need(mixed.State.IsGameOver && VolibearArchitectEnding.IsDomainVictory(mixed.State), "completed living victory remains terminal for network and exit");
            ((Task)Call("FinishVictory", mixed.Manager)!).GetAwaiter().GetResult();
            Need(shown == 1 && entered == 1 && nativeFinishes == 0, "duplicate completion cannot kill bear or duplicate screen");
            var ordinary = Fixture(false);
            Call("RecordVictory", ordinary.Manager, true); ((Task)Call("FinishVictory", ordinary.Manager)!).GetAwaiter().GetResult();
            Need(nativeFinishes == 1 && !ordinary.State.IsGameOver && entered == 1, "other characters use original complete native sequence");
            var stale = Fixture(); Call("RecordVictory", stale.Manager, true);
            Field(stale.Manager, "<State>k__BackingField", Fixture().State);
            ((Task)Call("FinishVictory", stale.Manager)!).GetAwaiter().GetResult();
            Need(nativeFinishes == 2 && !stale.State.IsGameOver, "old run receipt never authorizes new run");
            var abandoned = Fixture(); Field(abandoned.Manager, "<IsAbandoned>k__BackingField", true);
            Call("RecordVictory", abandoned.Manager, true); ((Task)Call("FinishVictory", abandoned.Manager)!).GetAwaiter().GetResult();
            Need(nativeFinishes == 3 && entered == 1, "abandonment remains native");
            Console.WriteLine($"ARCHITECT_ENDING_PASS checks={checks} native-sites=2 gameplay=NOT_RUN");
        }
        finally { fixture.UnpatchAll(fixture.Id); new Harmony("Volibear.ArchitectEnding").UnpatchAll("Volibear.ArchitectEnding"); }
    }
}
