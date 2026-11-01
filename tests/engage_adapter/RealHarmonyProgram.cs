#if REAL_HARMONY
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

// Real upstream Harmony, synthetic native types. This does not load StS2 or test a network.
internal static class RealHarmonyProgram
{
    private static int assertions;
    private static readonly PlayerChoiceContext Choices = new();
    private static readonly Type Machine = typeof(MonsterModel).GetMethod(nameof(MonsterModel.PerformMove))!
        .GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
    private static readonly MethodInfo MoveNext = AccessTools.Method(Machine, "MoveNext");
    private sealed class Fixture
    {
        internal readonly CombatState State = new();
        internal readonly Creature Receiver, Enemy;
        internal readonly CardModel Card;
        internal Fixture()
        {
            Receiver = new() { CombatState = State };
            var player = new Player { Creature = Receiver }; Receiver.Player = player;
            Card = new() { Owner = player };
            Enemy = new() { CombatState = State, IsEnemy = true };
            Enemy.Monster = new() { Creature = Enemy };
            State.Members.AddRange([Receiver, Enemy]);
            CombatManager.Instance.Setup(State);
        }
        internal Task<EngageCmd.Result> Engage() => EngageCmd.Perform(Choices, Enemy, Card);
    }
    private static void Check(bool ok, string why)
    { assertions++; if (!ok) throw new Exception(why); }

    private static async Task NormalAndReentry()
    {
        var f = new Fixture(); EngageCmd.Result reentry = default;
        f.Enemy.Monster!.Body = async _ => { reentry = await f.Engage(); };
        await f.Enemy.Monster.PerformMove();
        Check(reentry is { Performed: false, Completed: false, Absorbed: 0 }, "Body entry consumes natural action before synchronous reentry");
        Check(f.Enemy.Monster.BodyCalls == 1 && EngageCmd.NaturalOpportunityEntryCount == 1,
            "Exactly one original body and natural opportunity");
        f = new();
        f.Enemy.Monster!.Body = _ => { f.Receiver.DamageBlockInternal(3m); return Task.CompletedTask; };
        var result = await f.Engage();
        Check(result is { Performed: true, Completed: true, Absorbed: 3 }, "Actual installed patches observe an ordinary Engage");
        Check(EngageCmd.NaturalOpportunityEntryCount == 1, "The early action has one real native entry");
    }

    private static async Task AwaitResume()
    {
        var f = new Fixture();
        var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        f.Enemy.Monster!.Body = _ => gate.Task;
        var pending = f.Engage();
        Check(!pending.IsCompleted && EngageCmd.NaturalOpportunityEntryCount == 1, "Initial real MoveNext recorded before suspension");
        f.State.RoundNumber++;
        gate.SetResult(); var result = await pending.WaitAsync(TimeSpan.FromSeconds(10));
        Check(result.Performed && !result.Completed, "A real entry remains a fact, but old-round rewards stop");
        Check(!EngageCmd.Consumed(f.Enemy), "Resumed MoveNext does not consume the new round");
        Check(f.Enemy.Monster.BodyCalls == 1, "Await resume did not run the action twice");
    }

    private static bool SkipPublicEntry(ref Task __result)
    { __result = Task.CompletedTask; return false; }

    // A genuine foreign Prefix must finish the generated builder when vetoing MoveNext,
    // otherwise the synthetic async Task would hang. Emit a typed by-ref field injection;
    // this also works with Release's struct state machine (no mutation of a boxed copy).
    private static MethodInfo MoveVeto()
    {
        var builder = Machine.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
            .Single(f => f.FieldType == typeof(AsyncTaskMethodBuilder));
        var assembly = AssemblyBuilder.DefineDynamicAssembly(new AssemblyName("EngageForeignVeto"), AssemblyBuilderAccess.Run);
        var type = assembly.DefineDynamicModule("Veto").DefineType("ForeignVeto", TypeAttributes.Public | TypeAttributes.Abstract | TypeAttributes.Sealed);
        var method = type.DefineMethod("Skip", MethodAttributes.Public | MethodAttributes.Static,
            typeof(bool), [typeof(AsyncTaskMethodBuilder).MakeByRefType()]);
        method.DefineParameter(1, ParameterAttributes.None, "___" + builder.Name);
        var il = method.GetILGenerator();
        il.Emit(OpCodes.Ldarg_0); il.Emit(OpCodes.Call, typeof(AsyncTaskMethodBuilder).GetMethod(nameof(AsyncTaskMethodBuilder.SetResult))!);
        il.Emit(OpCodes.Ldc_I4_0); il.Emit(OpCodes.Ret);
        return type.CreateType()!.GetMethod("Skip")!;
    }

    private static async Task Veto(bool publicEntry, bool late, bool natural)
    {
        var foreign = new Harmony("Volibear.Test.ForeignEngageVeto");
        var target = publicEntry ? typeof(MonsterModel).GetMethod(nameof(MonsterModel.PerformMove))! : MoveNext;
        var prefix = publicEntry ? AccessTools.Method(typeof(RealHarmonyProgram), nameof(SkipPublicEntry)) : MoveVeto();
        foreign.Patch(target, prefix: new HarmonyMethod(prefix) { priority = late ? Priority.Last : Priority.First });
        try
        {
            var f = new Fixture();
            if (natural)
            {
                await f.Enemy.Monster!.PerformMove().WaitAsync(TimeSpan.FromSeconds(10));
                Check(!EngageCmd.Consumed(f.Enemy), "A vetoed natural body creates no consumed action fact");
            }
            else
            {
                var result = await f.Engage().WaitAsync(TimeSpan.FromSeconds(10));
                Check(result is { Performed: false, Completed: false, Absorbed: 0 }, "Vetoed native body does not complete Engage");
                Check(EngageCmd.Consumed(f.Enemy), "Engage reservation remains committed after a veto");
            }
            Check(f.Enemy.Monster!.BodyCalls == 0, "The foreign patch really skipped the original body");
            Check(EngageCmd.NaturalOpportunityEntryCount == 0, "No natural action observation for skipped IL");
        }
        finally { foreign.UnpatchAll(foreign.Id); }
    }

    private static readonly Dictionary<string, Func<Task>> Cases = new()
    {
        ["normal-reentry"] = NormalAndReentry,
        ["await-resume"] = AwaitResume,
        ["early-veto"] = () => Veto(false, false, false),
        ["late-veto"] = () => Veto(false, true, false),
        ["public-veto"] = () => Veto(true, false, false),
        ["natural-late-veto"] = () => Veto(false, true, true),
    };

    private static async Task<int> Main(string[] args)
    {
        if (args.Length != 1 || !Cases.TryGetValue(args[0], out var run)) return 2;
        try
        {
            EngageCmd.Install(); await run();
            Console.WriteLine($"ENGAGE_HARMONY_PASS name={args[0]} assertions={assertions} harmony={typeof(Harmony).Assembly.GetName().Version} native-gameplay=NOT_RUN multiplayer-network=NOT_RUN");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
#endif
