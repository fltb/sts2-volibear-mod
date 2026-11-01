using System.Collections;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

var assembly = typeof(Volibear.Presentation.AudioCommitGate).Assembly;
var host = typeof(DomainPower).Assembly;
const BindingFlags flags = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
Type T(string name) => assembly.GetType(name) ?? host.GetType(name, throwOnError: true)!;
object? Call(Type t, string name, params object?[] args) => t.GetMethod(name, flags)!.Invoke(null, args);
int checks = 0;
void Check(bool condition, string label) { checks++; if (!condition) throw new Exception(label); }
var gateType = T("Volibear.Presentation.AudioCommitGate");
object Gate() => Activator.CreateInstance(gateType, nonPublic: true)!;
bool Commit(object gate, params bool[] facts) => (bool)gateType.GetMethod("TryCommit", flags)!.Invoke(gate, facts.Cast<object>().ToArray())!;
foreach (int mask in Enumerable.Range(0, 32))
{
    var facts = Enumerable.Range(0, 5).Select(bit => (mask & (1 << bit)) != 0).ToArray();
    var gate = Gate();
    bool expected = facts[0] && facts[1] && facts[2] && facts[3] && !facts[4];
    Check(Commit(gate, facts) == expected, "positive/member/source/silent truth table");
    Check(Commit(gate, true, true, true, true, false) == !expected, "rejected preliminary event does not consume transaction");
    Check(!Commit(gate, true, true, true, true, false), "same exact transaction cannot emit twice");
}
Check(Commit(Gate(), true, true, true, true, false) && Commit(Gate(), true, true, true, true, false), "distinct transactions are not time-deduplicated");
var cardPolicy = T("Volibear.Core.CardReceiptPolicy");
foreach (string effect in new[] { "card_purify", "card_retrieve", "card_draw", "card_exhaust", "unknown" })
foreach (string from in new[] { "Draw", "Hand", "Discard", "Play", "Exhaust", "Deck", "None", "unknown" })
foreach (string to in new[] { "Draw", "Hand", "Discard", "Exhaust", "None" })
foreach (int mask in Enumerable.Range(0, 8))
{
    bool owner = (mask & 1) != 0, combat = (mask & 2) != 0, live = (mask & 4) != 0;
    bool expected = owner && combat && live && ((effect == "card_purify" && new[] { "Draw", "Hand", "Discard", "Play" }.Contains(from) && to == "Exhaust") ||
        (effect == "card_retrieve" && new[] { "Draw", "Discard" }.Contains(from) && to == "Hand"));
    Check((bool)Call(cardPolicy, "Allows", effect, from, to, owner, combat, live)! == expected, "card receipt refuses generic/failed/wrong-source moves");
}
int notified = 0;
Action<int> listeners = _ => throw new InvalidOperationException("cosmetic failure");
listeners += value => notified = value;
cardPolicy.GetMethod("Notify", flags)!.MakeGenericMethod(typeof(int)).Invoke(null, [listeners, 7]);
Check(notified == 7, "throwing subscriber cannot block following synchronous observers");
var audio = T("Volibear.Presentation.PowerAudioReceipts");
foreach (var row in new[] { ("StandingPower", "armor_retain"), ("ImmovableBodyPower", "armor_iron"),
    ("NextAttackDiscount", "cost_reduce"),
    ("NextEngageDiscount", "cost_reduce"), ("EndlessHuntPower", "cost_reduce") })
{
    var type = host.GetType("Volibear.Core." + row.Item1) ?? host.GetType("Volibear.Content." + row.Item1)!;
    Check((string?)Call(audio, "Cue", RuntimeHelpers.GetUninitializedObject(type)) == row.Item2, "exact approved positive power cue: " + row.Item1);
}
foreach (var type in new[] { typeof(WeakPower), typeof(VulnerablePower), T("Volibear.Content.VolibearChargeStrengthPower"), T("Volibear.Core.StormChargePower"), T("Volibear.Core.ThunderArmorPower") })
    Check(Call(audio, "Cue", RuntimeHelpers.GetUninitializedObject(type)) is null, "unapproved/duplicate power family rejected: " + type.Name);
var nativePower = (StrengthPower)RuntimeHelpers.GetUninitializedObject(typeof(StrengthPower));
Check((string?)Call(audio, "Cue", nativePower) == "strength", "native positive Strength routes once at its own command");
Task Promise() => new TaskCompletionSource().Task;
object Enter(Task task, int state) => Call(audio, "Enter", task, state, nativePower, null, null, null, false)!;
object? Ticket(object frame) => frame.GetType().GetField("Ticket", flags)!.GetValue(frame);
object? Current() { var local = audio.GetField("Current", flags)!.GetValue(null)!; return local.GetType().GetProperty("Value")!.GetValue(local); }
var initial = Promise(); var actual = Promise();
var first = Enter(initial, -1); var ticket = Ticket(first);
Check(ticket is not null, "initial real frame receives its own ticket");
Call(audio, "Leave", first, actual, 0);
Check(Current() is null, "suspension closes ambient frame");
var resumed = Enter(actual, 0);
Check(ReferenceEquals(Ticket(resumed), ticket), "resumed frame binds to reread actual builder promise");
var unknown = Enter(Promise(), 0);
Check(Ticket(unknown) is null, "unknown resume never borrows outer source");
Call(audio, "Close", unknown);
var nested = Enter(Promise(), -1);
Check(Ticket(nested) is not null && !ReferenceEquals(Ticket(nested), ticket), "nested actual command gets independent ticket");
Call(audio, "Close", nested);
Call(audio, "Close", resumed);
Check(Current() is null, "completion closes before caller continuation");
var collision = Enter(initial, -1);
Check(Ticket(collision) is null, "ambiguous builder identity fails closed");
Call(audio, "Close", collision);
var invalidated = Enter(actual, 0);
Check(Ticket(invalidated) is null, "colliding ticket cannot resume attributed");
Call(audio, "Close", invalidated);

// Emit actual pinned native IL with current production passive/revival/summon adapters.
// No engine/gameplay or audio playback occurs in this test process.
var passive = T("Volibear.Core.DomainPassiveEffects");
var revival = T("Volibear.Core.DomainRevivalEffects");
var summon = T("Volibear.Core.DomainSummonEffects");
var contributions = T("Volibear.Core.DomainCardContributions");
var contributionsId = (string)contributions.GetField("HarmonyId", flags)!.GetValue(null)!;
Call(passive, "Prepare");
var bodies = ((IEnumerable<MethodInfo>)Call(audio, "NativeBodies")!).ToArray();
var harmony = new Harmony("Volibear.AudioReceipts.CombinedEmissionTest");
var audioHarmony = new Harmony("Volibear.Presentation.PowerAudioReceipts");
var passiveHarmony = new Harmony("Volibear.DomainPassiveEffects");
void Audio()
{
    foreach (var body in bodies) audioHarmony.Patch(body, transpiler: new HarmonyMethod(audio.GetMethod("CommandBody", flags)!));
}
void Other()
{
    foreach (var pair in new[] { ("Sources", "SourceCalls"), ("Commands", "CommandBody") })
        foreach (DictionaryEntry row in (IDictionary)passive.GetField(pair.Item1, flags)!.GetValue(null)!)
            passiveHarmony.Patch((MethodBase)row.Key, transpiler: new HarmonyMethod(passive.GetMethod(pair.Item2, flags)!));
    Call(contributions, "Install");
    Call(revival, "InstallPatches", harmony);
    if (summon.GetMethod("InstallPatches", flags) is not null) Call(summon, "InstallPatches", harmony);
    else Call(summon, "Install");
}
try
{
    foreach (bool audioFirst in new[] { false, true })
    {
        if (audioFirst) { Audio(); Other(); } else { Other(); Audio(); }
        foreach (var body in bodies)
        {
            var code = PatchProcessor.GetCurrentInstructions(body).ToList();
            var close = audio.GetMethod("Close", flags)!;
            var completions = code.Select((c, i) => (c, i)).Where(p => p.c.operand is MethodInfo m &&
                m.DeclaringType?.Name.StartsWith("AsyncTaskMethodBuilder") == true && m.Name is "SetResult" or "SetException").ToArray();
            Check(completions.Length == 2, "both actual completion paths retained");
            Check(completions.All(p => code[p.i - 1].Calls(close)), "close immediately before native result/exception signal");
            Check(code.Any(c => c.Calls(audio.GetMethod("Leave", flags)!)), "actual builder reread at return");
            var wrappers = code.Select((c, i) => (c, i)).Where(p => p.c.operand is MethodInfo m &&
                m.DeclaringType == contributions && m.Name is "ApplyCommit" or "AmountCommit").ToArray();
            Check(wrappers.Length == 1, "b03 provenance wrapper preserved exactly once");
            Check(code.FindIndex(c => c.Calls(audio.GetMethod("BeginCommit", flags)!)) < wrappers[0].i &&
                code[wrappers[0].i + 2].Calls(audio.GetMethod("EndCommit", flags)!), "audio window surrounds wrapper without replacing it");
            Check(!code.Any(c => c.operand is MethodInfo m && m.DeclaringType == typeof(MegaCrit.Sts2.Core.Models.PowerModel) &&
                m.Name is "ApplyInternal" or "SetAmount"), "no bypass of b03 commit wrapper");
            var il = new DynamicMethod("MissingResult", typeof(void), Type.EmptyTypes).GetILGenerator();
            var mutated = PatchProcessor.GetOriginalInstructions(body, il).Where(c => c.operand is not MethodInfo m || m.Name != "SetResult").ToList();
            try { _ = ((IEnumerable<CodeInstruction>)Call(audio, "CommandBody", mutated, il, body)!).ToArray(); Check(false, "missing completion must reject"); }
            catch (TargetInvocationException error) { Check(error.InnerException is InvalidOperationException, "missing completion mutation refused"); }
        }
        harmony.UnpatchAll(contributionsId);
        contributions.GetField("_installed", flags)!.SetValue(null, false);
        audioHarmony.UnpatchAll(audioHarmony.Id);
        passiveHarmony.UnpatchAll(passiveHarmony.Id);
        harmony.UnpatchAll(harmony.Id);
    }
}
finally
{
    harmony.UnpatchAll(contributionsId);
    audioHarmony.UnpatchAll(audioHarmony.Id);
    passiveHarmony.UnpatchAll(passiveHarmony.Id);
    harmony.UnpatchAll(harmony.Id);
    if (summon.GetField("HarmonyId", flags)?.GetValue(null) is string id) harmony.UnpatchAll(id);
}
Console.WriteLine($"AUDIO_RECEIPT_RULES_AND_COMBINED_NATIVE_EMISSION_OK checks={checks}; gameplay=NOT_RUN; playback=NOT_RUN; listening=NOT_RUN");
