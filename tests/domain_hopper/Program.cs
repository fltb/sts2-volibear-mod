using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

internal static class Program
{
    private static int checks;
    private static void Check(bool value, string rule)
    { checks++; if (!value) throw new Exception(rule); }
    private static void Decisions()
    {
        var beforeC = new DomainHopperDecision();
        Check(!beforeC.AdmitCombat(true, true), "domain before C denies new theft");
        Check(beforeC.State == DomainHopperDecision.Phase.Cancelled, "denial committed");
        Check(!beforeC.AdmitMaster(true, false), "domain exit cannot revive denied C");
        var stale = new DomainHopperDecision();
        Check(!stale.AdmitCombat(false, false), "stale source cannot remove C");
        var between = new DomainHopperDecision();
        Check(between.AdmitCombat(true, false), "domain off allows C");
        between.CombatCompleted();
        Check(!between.AdmitMaster(true, true), "domain during original wait denies M");
        Check(!between.FinishCommitted, "C-only loss cannot create return/mount obligation");
        Check(!between.AdmitMaster(true, false), "residual cancellation sticky");
        var postHook = new DomainHopperDecision();
        Check(postHook.AdmitCombat(true, false), "second C allowed"); postHook.CombatCompleted();
        Check(postHook.AdmitMaster(true, false), "entry to Steal allowed");
        Check(!postHook.AdmitMaster(true, true), "domain during BeforeCardRemoved denies physical M mutation");
        Check(!postHook.FinishCommitted, "posthook cancellation cannot mark loot or mount Swipe");
        var committed = new DomainHopperDecision();
        Check(committed.AdmitCombat(true, false), "third C allowed"); committed.CombatCompleted();
        Check(committed.AdmitMaster(true, false), "M entry allowed");
        Check(committed.AdmitMaster(true, false), "physical M gate independently allows");
        committed.MasterCommitted();
        Check(committed.FinishCommitted, "physical M establishes original cleanup obligation");
        Check(!postHook.FinishCommitted, "independent card remains cancelled");
        var invalid = new DomainHopperDecision();
        bool threw = false; try { invalid.MasterCommitted(); } catch (InvalidOperationException) { threw = true; }
        Check(threw, "master commit without C must fail");
        var reset = new DomainHopperDecision(); reset.AdmitCombat(true, false); reset.CombatCompleted();
        Check(!reset.AdmitMaster(false, false), "old source cannot begin cross-reset M loss");
    }
    private static void NativeEmission()
    {
        var root = DomainHopperEffects.Body(AccessTools.Method(typeof(ThievingHopper), "ThieveryMove"));
        var before = PatchProcessor.GetOriginalInstructions(root);
        var originalAttack = before.Where(i => i.operand is MethodInfo m && m.DeclaringType?.Name == "AttackCommand" && m.Name == "Execute").Select(i => i.operand).ToArray();
        Check(originalAttack.Length == 1, "one native original attack");
        var emptyBefore = CardPileCmd.RemoveFromDeck(Array.Empty<CardModel>(), false);
        emptyBefore.GetAwaiter().GetResult();
        Check(emptyBefore.IsCompletedSuccessfully, "unowned native empty control succeeds");
        var harmony = new Harmony("Volibear.Tests.Hopper");
        try
        {
            DomainHopperEffects.InstallPatches(harmony); // Real pinned native bodies, no world launch.
            var missingOne = before.Select(i => new CodeInstruction(i)).ToList();
            var registrations = missingOne.Where(i => i.operand is MethodInfo m && m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name.StartsWith("Await", StringComparison.Ordinal)).ToArray();
            Check(registrations.Length > 1, "negative fixture retains other original registrations");
            registrations[0].opcode = OpCodes.Nop; registrations[0].operand = null;
            bool rejectedMissingOne = false;
            try
            {
                var generator = new DynamicMethod("HopperMissingOne", typeof(void), Type.EmptyTypes).GetILGenerator();
                var rewritten = (IEnumerable<CodeInstruction>)AccessTools.Method(typeof(DomainHopperEffects), "Rewrite").Invoke(null, [missingOne, generator, root])!;
                _ = rewritten.ToArray();
            }
            catch (TargetInvocationException error) when (error.InnerException is InvalidOperationException inner && inner.Message.Contains("registration count/type multiset"))
            { rejectedMissingOne = true; }
            Check(rejectedMissingOne, "missing just one original await rejects before emission despite remaining registrations");
            var emptyAfter = CardPileCmd.RemoveFromDeck(Array.Empty<CardModel>(), false);
            emptyAfter.GetAwaiter().GetResult();
            Check(emptyAfter.IsCompletedSuccessfully, "actual patched unowned native body still succeeds");
            var invalid = CardPileCmd.RemoveFromDeck((IReadOnlyList<CardModel>)null!, false);
            bool originalFailure = false;
            try { invalid.GetAwaiter().GetResult(); } catch (NullReferenceException) { originalFailure = true; }
            Check(originalFailure && invalid.IsFaulted, "actual patched unowned native failure is not swallowed");
            var after = PatchProcessor.GetCurrentInstructions(root);
            Check(after.Count(i => Equals(i.operand, originalAttack[0])) == 1, "actual attack preserved exactly once");
            foreach (var name in new[] { "RemoveCombat", "Enqueue", "Steal", "Apply" })
                Check(after.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(DomainHopperEffects) && m.Name == name) == 1, "exact root edge " + name);
            Check(Harmony.GetPatchInfo(AccessTools.Method(typeof(SwipePower), "BeforeDeath"))?.Owners.Contains(harmony.Id) != true, "existing return untouched");
            foreach (var method in typeof(PowerCmd).GetMethods().Where(m => m.Name == "Apply"))
                Check(Harmony.GetPatchInfo(method)?.Owners.Contains(harmony.Id) != true, "no global Apply veto");
            var bulk = DomainHopperEffects.Body(AccessTools.Method(typeof(CardPileCmd), "RemoveFromDeck", [typeof(IReadOnlyList<CardModel>), typeof(bool)]));
            var patched = PatchProcessor.GetCurrentInstructions(bulk);
            int hook = patched.FindIndex(i => i.operand is MethodInfo m && m.Name == "BeforeCardRemoved");
            int gate = patched.FindIndex(i => i.operand is MethodInfo m && m.DeclaringType == typeof(DomainHopperEffects) && m.Name == "MasterPile");
            Check(hook >= 0 && gate > hook, "physical gate follows native hook");
            Check(patched.Skip(hook).Take(gate - hook).Any(i => i.operand is MethodInfo m && m.Name == "GetResult"), "native hook GetResult is preserved before gate");
        }
        finally { harmony.UnpatchAll(harmony.Id); }
    }
    private static int Main()
    {
        try { Decisions(); NativeEmission(); AdapterTests.Run(); Console.WriteLine($"HOPPER_DECISION_NATIVE_IL_PASS checks={checks} gameplay=NOT_RUN"); return 0; }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
