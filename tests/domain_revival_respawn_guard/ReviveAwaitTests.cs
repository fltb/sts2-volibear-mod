using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models.Monsters;
using Volibear.Core;

internal static class ReviveAwaitTests
{
    internal static void Run()
    {
        var type = typeof(DomainAdditionalRevivalEffects);
        var body = AccessTools.Method(AccessTools.Method(typeof(TestSubject), "Revive").GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        var original = PatchProcessor.GetOriginalInstructions(body).ToList();
        var generic = AccessTools.Method(typeof(TaskAwaiter<decimal>), "GetResult");
        var ordinary = AccessTools.Method(typeof(TaskAwaiter), "GetResult");
        int at = original.FindIndex(c => c.Calls(generic));
        if (at < 0 || at + 1 >= original.Count || original[at + 1].opcode != OpCodes.Pop || original.Count(c => c.Calls(ordinary)) != 1)
            throw new Exception("Pinned Revive awaits changed");
        // Populate production body mapping and run the complete actual Harmony emitter.
        var harmony = new Harmony("Volibear.Tests.ReviveAwaitBoundaries");
        try
        {
            AccessTools.Method(type, "InstallPatches").Invoke(null, [harmony]);
            var rewrite = AccessTools.Method(type, "Rewrite");
            var blocked = AccessTools.Method(type, "Blocked");
            List<CodeInstruction> Emit(List<CodeInstruction> code) => ((IEnumerable<CodeInstruction>)rewrite.Invoke(null,
                [code, new DynamicMethod("ReviveAwait", typeof(void), Type.EmptyTypes).GetILGenerator(), body])!).ToList();
            var emitted = Emit(original.Select(c => new CodeInstruction(c)).ToList());
            int result = emitted.FindIndex(c => c.Calls(generic));
            if (emitted[result + 1].opcode != OpCodes.Pop || emitted[result + 2].opcode != OpCodes.Ldloc || !emitted[result + 3].Calls(blocked))
                throw new Exception("Revive cancellation must follow original generic result discard");
            foreach (var mutation in new[] { "discard", "missing-result", "extra-void" })
            {
                var copy = original.Select(c => new CodeInstruction(c)).ToList();
                if (mutation == "discard") copy[at + 1].opcode = OpCodes.Nop;
                if (mutation == "missing-result") copy[at].opcode = OpCodes.Nop;
                if (mutation == "missing-result") copy[at].operand = null;
                if (mutation == "extra-void") copy.Insert(at, new CodeInstruction(OpCodes.Call, ordinary));
                bool rejected = false;
                try { Emit(copy); }
                catch (InvalidOperationException) { rejected = true; }
                catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { rejected = true; }
                if (!rejected) throw new Exception("Revive accepted drift: " + mutation);
            }
            Console.WriteLine("REVIVE_AWAIT_GUARD_PASS generic-discard=true negatives=3 native-gameplay=NOT_RUN");
        }
        finally { harmony.UnpatchAll(harmony.Id); }
    }
}
