using System.Reflection;
using HarmonyLib;
using Volibear.Core;
var tests = 0;
void Need(bool condition) { if (!condition) throw new Exception("revival decision check " + tests); tests++; }
foreach (var seen in new[] { false, true })
foreach (var confirmed in new[] { false, true })
foreach (var atCommit in new[] { false, true })
{
    var decision = new RevivalDecision();
    decision.ObserveDomain(seen);
    Need(!decision.CancelIfRequired(false)); // A death attempt alone consumes nothing.
    decision.Confirm(!confirmed);
    var expected = confirmed && (seen || atCommit);
    Need(decision.CancelIfRequired(atCommit) == expected);
    Need(decision.CancelIfRequired(false) == expected); // Exiting cannot replay cancellation.
    Need(decision.Cancelled == expected);
    if (confirmed && !seen && !atCommit)
    {
        decision.Commit(); Need(decision.Committed);
        Need(!decision.CancelIfRequired(true)); // Committed HP is not rolled back.
    }
    else
    {
        try { decision.Commit(); throw new Exception("invalid benefit committed"); }
        catch (InvalidOperationException) { tests++; }
    }
}
var pending = new RevivalDecision(); pending.Confirm(false); Need(!pending.CancelIfRequired(false));
Need(pending.CancelIfRequired(true)); Need(pending.CancelIfRequired(false));
Console.WriteLine("REVIVAL_DECISION_PASS checks=" + tests);
var sourceChecks = 0;
var sourceA = new EqualIdentity(7); var sourceB = new EqualIdentity(7);
var ownerA = new EqualIdentity(9); var ownerB = new EqualIdentity(9);
foreach (var cancelled in new[] { false, true })
foreach (var sameEpoch in new[] { false, true })
foreach (var sourceMatches in new[] { false, true })
foreach (var capturedOwnerMatches in new[] { false, true })
foreach (var targetMatches in new[] { false, true })
{
    // Distinct records compare equal by value: only actual source/owner identity counts.
    var actual = RevivalDecision.OwnsCancelledPreservation(sourceA, sourceMatches ? sourceA : sourceB,
        ownerA, capturedOwnerMatches ? ownerA : ownerB, targetMatches ? ownerA : ownerB, cancelled, sameEpoch);
    Need(actual == (cancelled && sameEpoch && sourceMatches && capturedOwnerMatches && targetMatches));
    sourceChecks++;
}
Console.WriteLine("REVIVAL_SOURCE_IDENTITY_PASS checks=" + sourceChecks);
var callbackChecks = 0;
foreach (var state in new[] { -2, -1, 0, 1 })
foreach (var owned in new[] { false, true })
foreach (var allowed in new[] { false, true })
{
    Need(RevivalDecision.SkipUnstartedCallback(state, owned, allowed) == (state == -1 && owned && !allowed));
    callbackChecks++;
}
Console.WriteLine("REVIVAL_CALLBACK_DECISION_PASS checks=" + callbackChecks);
var harmony = new Harmony("Volibear.RevivalStage.EmissionOnly");
try
{
    DomainRevivalEffects.InstallPatches(harmony);
    Need(harmony.GetPatchedMethods().Count() == 12);
    var preservation = AccessTools.Method(typeof(DomainRevivalEffects), "RemoveCancelledPreservation");
    Need(preservation.GetParameters()[0].Name == "__instance" &&
        preservation.GetParameters()[0].ParameterType == typeof(MegaCrit.Sts2.Core.Models.Powers.IllusionPower));
    Need(PatchProcessor.GetOriginalInstructions(preservation).Count(instruction => instruction.Calls(
        AccessTools.Method(typeof(RevivalDecision), nameof(RevivalDecision.OwnsCancelledPreservation)))) == 1);
    var kill = AccessTools.Method(typeof(MegaCrit.Sts2.Core.Commands.CreatureCmd), "KillWithoutCheckingWinCondition");
    var machine = kill.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()!.StateMachineType;
    var current = PatchProcessor.GetCurrentInstructions(AccessTools.Method(machine, "MoveNext"));
    Need(current.Count(instruction => instruction.Calls(AccessTools.Method(typeof(MegaCrit.Sts2.Core.Hooks.Hook), "AfterDeath"))) == 2);
    Need(current.Count(instruction => instruction.Calls(AccessTools.Method(typeof(MegaCrit.Sts2.Core.Hooks.Hook), "ShouldCreatureBeRemovedFromCombatAfterDeath"))) == 1);
    var completionSignals = current.Select((instruction, index) => (instruction, index)).Where(pair =>
        pair.instruction.operand is MethodInfo method && method.DeclaringType == typeof(System.Runtime.CompilerServices.AsyncTaskMethodBuilder) &&
        (method.Name is "SetResult" or "SetException")).ToArray();
    Need(completionSignals.Length == 2);
    foreach (var signal in completionSignals)
        Need(signal.index > 0 && current[signal.index - 1].Calls(AccessTools.Method(typeof(DomainRevivalEffects), "BeforeDeathCompletion")));
    var revive = AccessTools.Method(typeof(MegaCrit.Sts2.Core.Models.Powers.IllusionPower), "ReviveMove");
    var reviveMachine = revive.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()!.StateMachineType;
    var reviveCode = PatchProcessor.GetCurrentInstructions(AccessTools.Method(reviveMachine, "MoveNext"));
    var firstCall = reviveCode.First(instruction => instruction.operand is MethodInfo);
    Need(firstCall.Calls(AccessTools.Method(typeof(DomainRevivalEffects), "CompleteCancelledRevive")));
    var earlyCompletion = PatchProcessor.GetOriginalInstructions(AccessTools.Method(typeof(DomainRevivalEffects), "CompleteCancelledRevive"));
    Need(earlyCompletion.Count(instruction => instruction.Calls(AccessTools.Method(typeof(System.Runtime.CompilerServices.AsyncTaskMethodBuilder), "SetResult"))) == 1);
    Need(earlyCompletion.Count(instruction => instruction.Calls(AccessTools.Method(typeof(DomainRevivalEffects), "AllowBenefit"))) == 1);
    var reattachMove = AccessTools.Method(typeof(MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment), "ReattachMove");
    var reattachMachine = reattachMove.GetCustomAttribute<System.Runtime.CompilerServices.AsyncStateMachineAttribute>()!.StateMachineType;
    var reattachCode = PatchProcessor.GetCurrentInstructions(AccessTools.Method(reattachMachine, "MoveNext"));
    Need(reattachCode.First(instruction => instruction.operand is MethodInfo).Calls(
        AccessTools.Method(typeof(DomainRevivalEffects), "CompleteCancelledReattach")));
    var reattachGuard = PatchProcessor.GetOriginalInstructions(AccessTools.Method(typeof(DomainRevivalEffects), "CompleteCancelledReattach"));
    Need(reattachGuard.Count(instruction => instruction.Calls(AccessTools.Method(typeof(System.Runtime.CompilerServices.AsyncTaskMethodBuilder), "SetResult"))) == 1);
    Need(reattachGuard.All(instruction => instruction.operand is not MethodInfo method || !method.Name.StartsWith("GetPower", StringComparison.Ordinal)));
    Need(reattachGuard.Any(instruction => instruction.operand is FieldInfo field && field.Name == "ReattachMoves"));
    Console.WriteLine("REVIVAL_CALLBACK_BOUNDARIES_PASS early-native-revive-guards=2 pre-signal-death-close=2 no-reattach-power-lookup=true");
    foreach (var name in new[] { "DeathDispatch", "RemovalVotes", "ReattachCaller" })
    {
        var transpiler = AccessTools.Method(typeof(DomainRevivalEffects), name);
        try
        {
            transpiler.Invoke(null, new object[] { Array.Empty<CodeInstruction>() });
            throw new Exception("Missing native callsite accepted: " + name);
        }
        catch (TargetInvocationException error) when (error.InnerException is InvalidOperationException) { tests++; }
    }
    Console.WriteLine("REVIVAL_NATIVE_IL_EMISSION_PASS patches=12 missing-callsite-rejections=3 (no game methods executed)");
}
finally { harmony.UnpatchAll(harmony.Id); }
sealed record EqualIdentity(int Value);
