using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Core;

internal static class AdapterTests
{
    private static readonly Type Adapter = typeof(DomainHopperEffects);
    private static Type Nested(string name) => Adapter.GetNestedType(name, BindingFlags.NonPublic)!;
    private static object New(string name, params object?[] args) => Activator.CreateInstance(Nested(name), BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null, args, null)!;
    private static object? Call(string method, params object?[] args)
    {
        try { return AccessTools.Method(Adapter, method).Invoke(null, args); }
        catch (TargetInvocationException error) when (error.InnerException is { } inner) { System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(inner).Throw(); throw; }
    }
    private static void Field(object target, string name, object? value) => AccessTools.Field(target.GetType(), name).SetValue(target, value);
    private static object? Field(object target, string name) => (AccessTools.Field(target.GetType(), name) ?? AccessTools.Field(target.GetType(), "<" + name + ">k__BackingField")).GetValue(target);
    private static object Kind(string name) => Enum.Parse(Nested("Kind"), name);
    private static object Context(DomainHopperDecision decision, out CardModel master, out SwipePower swipe)
    {
        // Real native types are identity fixtures only; no game singleton, HP, pile or Add simulator.
        master = (CardModel)RuntimeHelpers.GetUninitializedObject(typeof(StrikeIronclad));
        var card = (CardModel)RuntimeHelpers.GetUninitializedObject(typeof(StrikeIronclad));
        swipe = (SwipePower)RuntimeHelpers.GetUninitializedObject(typeof(SwipePower));
        var root = RuntimeHelpers.GetUninitializedObject(Nested("Root"));
        var theft = RuntimeHelpers.GetUninitializedObject(Nested("Theft"));
        Field(theft, "Root", root); Field(theft, "Card", card); Field(theft, "Master", master);
        Field(theft, "Decision", decision); Field(theft, "Swipe", swipe);
        var dictType = AccessTools.Field(Nested("Root"), "Cards").FieldType;
        var cards = Activator.CreateInstance(dictType)!;
        dictType.GetMethod("Add")!.Invoke(cards, [card, theft]); Field(root, "Cards", cards);
        return New("Context", root, theft);
    }
    private static object Frame(object? context, string kind)
    {
        object? binding = null;
        if (context is not null)
        {
            var life = AccessTools.Field(Adapter, "Lifetimes").GetValue(null)!;
            binding = AccessTools.Method(life.GetType(), "Begin").Invoke(life, [context, 0L, false, null, -1]);
        }
        return New("Frame", binding, Kind(kind));
    }
    internal static int Run()
    {
        int count = 0;
        void Check(bool condition, string rule) { count++; if (!condition) throw new Exception(rule); }
        var cancelled = new DomainHopperDecision(); cancelled.AdmitCombat(true, false); cancelled.CombatCompleted(); cancelled.AdmitMaster(true, true);
        var context = Context(cancelled, out var master, out var swipe);
        var frame = Frame(context, "MasterMany");
        Call("MasterState", master, frame); // Would invoke invalid native object if cancellation guard were absent.
        Check(!master.HasBeenRemovedFromState, "cancelled M leaves native removed flag false");
        var history = new PlayerMapPointHistoryEntry();
        Call("LootStolen", history, 1, Frame(context, "Steal"));
        Check(history.StolenLoot == 0, "actual cancelled adapter suppresses MarkLootStolen");
        var skipped = (Task)Call("Apply", null, swipe, null, 1m, null, null, false, Frame(context, "Root"))!;
        Check(skipped.IsCompletedSuccessfully, "cancelled Swipe mount skipped without touching native owner");
        Call("LootStolen", history, 2, Frame(null, "Steal"));
        Check(history.StolenLoot == 2, "unowned history call remains native");
        var committed = new DomainHopperDecision(); committed.AdmitCombat(true, false); committed.CombatCompleted(); committed.AdmitMaster(true, false); committed.MasterCommitted();
        var committedContext = Context(committed, out _, out _);
        DomainHopperEffects.Reset();
        Call("LootStolen", history, 3, Frame(committedContext, "Steal"));
        Check(history.StolenLoot == 5, "committed original loot survives epoch invalidation");

        var subject = new object(); var nativeTask = new TaskCompletionSource().Task; object? entered = null;
        Func<Task> native = () => { entered = Call("Enter", Task.CompletedTask, -1, subject, (int)Kind("Steal")); return nativeTask; };
        var returned = Call("Forward", Kind("Steal"), subject, context, native);
        Check(ReferenceEquals(returned, nativeTask), "exact original Task returned through source handoff");
        Check(ReferenceEquals(Call("Payload", entered), context), "exact initial source claims only its explicit ticket");
        var firstBinding = Field(entered!, "Binding");
        Call("Forward", Kind("Steal"), subject, context, native);
        Check(!ReferenceEquals(firstBinding, Field(entered!, "Binding")), "same cached initial Task does not merge distinct invocations");
        object? unknown = null;
        Call("Forward", Kind("Steal"), subject, context, (Func<Task>)(() => {
            unknown = Call("Enter", nativeTask, 0, subject, (int)Kind("Steal")); return nativeTask;
        }));
        Check(Call("Payload", unknown) is null, "unknown resume cannot borrow matching pending source");
        object? mismatch = null;
        Call("Forward", Kind("Steal"), subject, context, (Func<Task>)(() => {
            mismatch = Call("Enter", Task.CompletedTask, -1, new object(), (int)Kind("Steal"));
            unknown = Call("Enter", Task.CompletedTask, -1, subject, (int)Kind("Steal")); return nativeTask;
        }));
        Check(Call("Payload", mismatch) is null && Call("Payload", unknown) is null, "mismatched first entry masks ancestor ticket for nested call");
        var error = new InvalidOperationException("original synchronous native failure"); Exception? caught = null;
        try { Call("Forward", Kind("Steal"), subject, context, (Func<Task>)(() => throw error)); } catch (Exception actual) { caught = actual; }
        Check(ReferenceEquals(caught, error), "synchronous source exception preserved");
        unknown = Call("Enter", Task.CompletedTask, -1, subject, (int)Kind("Steal"));
        Check(Call("Payload", unknown) is null, "handoff cleared after exception");
        Call("Close", entered);
        bool rejected = false; try { Call("MasterState", master, entered); } catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "closed known source cannot fall through as ordinary native call");
        Console.WriteLine($"HOPPER_ACTUAL_ADAPTER_PASS checks={count} native-world=NOT_RUN");
        return count;
    }
}
