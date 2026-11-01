using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

// Read native IL and run our transformation as data only. No detours are installed,
// no game launched and no native card/payment methods executed.
internal static class NativeCallsiteChecks
{
    internal static int Run()
    {
        var checks = 0;
        AccessTools.Method(typeof(TargetCosts), "VerifyNativePaymentTiming").Invoke(null, null);
        checks++;
        var action = AccessTools.Method(typeof(PlayCardAction), "ExecuteAction");
        var actionMove = AccessTools.Method(action.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        var actionCode = PatchProcessor.GetOriginalInstructions(actionMove);
        var adapter = AccessTools.Method(typeof(TargetCosts), "ResolvedTargetCallsites");
        var rewritten = ((IEnumerable<CodeInstruction>)adapter.Invoke(null, [actionCode, actionMove])!).ToList();
        foreach (var name in new[] { "CanPlayResolved", "SpendResolved" })
        {
            if (rewritten.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(TargetCosts) && m.Name == name) != 1)
                throw new Exception("Expected exactly one native target adapter: " + name);
            checks++;
        }
        try { adapter.Invoke(null, [new List<CodeInstruction>(), actionMove]); throw new Exception("Payment drift did not fail closed."); }
        catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { checks++; }
        var wrapper = AccessTools.Method(typeof(CardModel), nameof(CardModel.OnPlayWrapper));
        var wrapperMove = AccessTools.Method(wrapper.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        var historyAdapter = AccessTools.Method(typeof(AttackHistory), "HookCallsites");
        var historyCode = ((IEnumerable<CodeInstruction>)historyAdapter.Invoke(null, [PatchProcessor.GetOriginalInstructions(wrapperMove)])!).ToList();
        foreach (var name in new[] { "BeforeNativeHooks", "AfterNativeHooks" })
        {
            if (historyCode.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(AttackHistory) && m.Name == name) != 1)
                throw new Exception("Expected one native history hook adapter: " + name);
            checks++;
        }
        try { historyAdapter.Invoke(null, [new List<CodeInstruction>()]); throw new Exception("History drift did not fail closed."); }
        catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { checks++; }
        // Check the crucial payment timing assumption on the actual pinned binary:
        // the cost is computed once, before the first await continuation registration.
        var spend = AccessTools.Method(typeof(CardModel), nameof(CardModel.SpendResources));
        var spendMove = AccessTools.Method(spend.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        var spendCode = PatchProcessor.GetOriginalInstructions(spendMove);
        var read = spendCode.FindIndex(i => i.operand is MethodInfo m && m.DeclaringType == typeof(CardEnergyCost) && m.Name == "GetAmountToSpend");
        var awaits = spendCode.FindIndex(i => i.operand is MethodInfo m && m.Name is "AwaitUnsafeOnCompleted" or "AwaitOnCompleted");
        if (read < 0 || awaits < 0 || read >= awaits || spendCode.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(CardEnergyCost) && m.Name == "GetAmountToSpend") != 1)
            throw new Exception("Native SpendResources cost-read timing drifted.");
        checks++;
        return checks;
    }
}
