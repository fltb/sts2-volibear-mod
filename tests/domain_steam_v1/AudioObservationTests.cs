using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear;
using Volibear.Core;

// Real production methods and native-reference Harmony emission, not a Godot run.
// The injected callback runs the existing full-chain suite once, while early audio
// observers are installed. It must not call ModEntry.Initialize or launch a game.
internal static class SteamAudioObservationTests
{
    internal static void Run(Action installChain)
    {
        ArgumentNullException.ThrowIfNull(installChain);
        const string id = "Volibear.SteamProbe.NativeObservation";
        const BindingFlags flags = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        var observer = typeof(DomainSteamNativeObservation);
        var owner = new Harmony(id);
        var foreign = new Harmony("Volibear.Tests.SteamAudioObservation.ForeignFixture");
        var steamHarmony = new Harmony(DomainSteamEruptionEffects.HarmonyId);
        // Never adopt/unpatch an existing session or another test's owned patches.
        if (owner.GetPatchedMethods().Any() || foreign.GetPatchedMethods().Any() || steamHarmony.GetPatchedMethods().Any() ||
            observer.GetField("Active", flags)!.GetValue(null) is not null)
            throw new InvalidOperationException("Audio emission fixture requires a fresh inactive observer/Steam patch scope.");
        var environment = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO");
        var dataRoot = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT");
        var checks = 0;
        void Need(bool condition, string message) { checks++; if (!condition) throw new Exception(message); }
        MethodInfo Own(string name) => AccessTools.Method(observer, name);
        void AudioShape()
        {
            foreach (var (type, name, before, after) in new[]
            {
                (typeof(NCreature), "StopSfxLoop", "StopBefore", "StopAfter"),
                (typeof(NRunMusicController), "UpdateMusicParameter", "", "MusicAfter"),
                (typeof(SfxCmd), "SetParam", "", "AmbientAfter"),
            })
            {
                var info = Harmony.GetPatchInfo(AccessTools.Method(type, name))!;
                var prefixes = info.Prefixes.Where(p => p.owner == id).ToArray();
                var postfixes = info.Postfixes.Where(p => p.owner == id).ToArray();
                Need(prefixes.Length == (before == "" ? 0 : 1) && (before == "" || prefixes[0].PatchMethod == Own(before)), "exact native audio prefix ownership");
                Need(postfixes.Length == 1 && postfixes[0].PatchMethod == Own(after), "exact native audio postfix ownership");
            }
            Need(observer.GetField("Active", flags)!.GetValue(null) is null, "early preparation cannot activate observations");
        }
        try
        {
            foreach (var scenario in new string?[] { null, "baseline", "domain-revival" })
            {
                Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", scenario);
                DomainSteamNativeObservation.PrepareForTestScenario();
                Need(!owner.GetPatchedMethods().Any(), "ordinary/other startup must not enable Steam observation");
            }
            Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", "domain-steam");
            Environment.SetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT", null);
            DomainSteamNativeObservation.PrepareForTestScenario();
            Need(!owner.GetPatchedMethods().Any(), "scenario without test-root configuration must not enable early observation");
            // This sentinel exercises only the environment selection branch. No directory
            // is created or certified isolated; actual native isolation remains runner-owned.
            Environment.SetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT", "managed-emission-fixture-not-a-game-run");
            DomainSteamNativeObservation.PrepareForTestScenario();
            DomainSteamNativeObservation.PrepareForTestScenario();
            Need(owner.GetPatchedMethods().Count() == 3, "early phase installs only three non-conflicting audio methods");
            AudioShape();
            var startup = PatchProcessor.GetOriginalInstructions(AccessTools.Method(typeof(ModEntry), "Initialize")).ToArray();
            Need(startup.First(c => c.operand is MethodInfo).Calls(Own("PrepareForTestScenario")), "preparation precedes real main installation/registration");
            installChain();
            AudioShape();
            DomainSteamNativeObservation.InstallPatches(owner);
            Need(owner.GetPatchedMethods().Count() == 9, "remaining six observer methods retain their later installation");
            DomainSteamNativeObservation.PrepareForTestScenario();
            AudioShape();
            try
            {
                DomainSteamEruptionEffects.InstallPatches(steamHarmony);
                var effects = typeof(DomainSteamEruptionEffects);
                MethodInfo Effect(string name) => AccessTools.Method(effects, name);
                MethodInfo Machine(string name) => AccessTools.Method(AccessTools.Method(typeof(WaterfallGiant), name).GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
                var phase = PatchProcessor.GetCurrentInstructions(Machine("TriggerAboutToBlowState")).ToList();
                foreach (var (helper, value) in new[] { ("PhaseMusic", 2f), ("PhaseAmbient", 3f) })
                {
                    var matches = phase.Select((code, index) => (code, index)).Where(x => x.code.Calls(Effect(helper))).ToArray();
                    Need(matches.Length == 1 && matches[0].index > 0 && phase[matches[0].index - 1].opcode == OpCodes.Ldc_R4 && (float)phase[matches[0].index - 1].operand == value, "phase preserves actual original native parameter: " + helper);
                }
                Need(PatchProcessor.GetOriginalInstructions(Effect("PhaseMusic")).Count(c => c.Calls(AccessTools.Method(typeof(NRunMusicController), "UpdateMusicParameter"))) == 1, "core music gate retains actual native API call");
                Need(PatchProcessor.GetOriginalInstructions(Effect("PhaseAmbient")).Count(c => c.Calls(AccessTools.Method(typeof(SfxCmd), "SetParam"))) == 1, "core ambient gate retains actual native API call");
                Need(PatchProcessor.GetCurrentInstructions(Machine("ExplodeMove")).Count(c => c.Calls(AccessTools.Method(typeof(WaterfallGiant), "StopAmbientSfx"))) == 1, "core explode retains real native ambient-stop call");
            }
            finally { steamHarmony.UnpatchAll(steamHarmony.Id); }
            var music = AccessTools.Method(typeof(NRunMusicController), "UpdateMusicParameter");
            owner.Patch(music, postfix: new HarmonyMethod(Own("MusicAfter")));
            try { DomainSteamNativeObservation.PrepareForTestScenario(); throw new Exception("duplicate audio handler accepted"); }
            catch (InvalidOperationException error) { Need(error.Message.Contains("owner/handler shape drift"), "duplicates explicitly rejected rather than silently deduplicated"); }
            owner.UnpatchAll(id);
            DomainSteamNativeObservation.PrepareForTestScenario();
            AudioShape();
            Need(owner.GetPatchedMethods().Count() == 3, "real patch metadata, not a stale installed boolean, governs reprepare");
            foreign.Patch(music, prefix: new HarmonyMethod(typeof(ForeignAudioFixture), nameof(ForeignAudioFixture.Prefix)));
            DomainSteamNativeObservation.PrepareForTestScenario();
            AudioShape();
            // Only an empty subscription list and this fixture's Harmony owner are used
            // by Dispose. No fake node or native room lifecycle is executed here.
            var disposable = (DomainSteamNativeObservation)RuntimeHelpers.GetUninitializedObject(observer);
            observer.GetField("_harmony", flags)!.SetValue(disposable, owner);
            var subscriptions = observer.GetField("_subscriptions", flags)!;
            subscriptions.SetValue(disposable, Activator.CreateInstance(subscriptions.FieldType));
            disposable.Dispose();
            Need(!owner.GetPatchedMethods().Any() && Harmony.GetPatchInfo(music)!.Owners.Contains(foreign.Id), "actual Dispose removes only observer owner, preserving foreign audio hooks");
            Console.WriteLine($"STEAM_EARLY_AUDIO_OBSERVER_EMISSION_PASS checks={checks} main-installers=21 expected-sequences=UNCHANGED core-calls=STATICALLY-PRESERVED pre-JIT-cause=NOT_PROVEN native-gameplay=NOT_RUN");
        }
        finally
        {
            // Environment restoration must survive a patch-cleanup failure as well.
            try { owner.UnpatchAll(id); }
            finally
            {
                try { foreign.UnpatchAll(foreign.Id); }
                finally
                {
                    Environment.SetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO", environment);
                    Environment.SetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT", dataRoot);
                }
            }
        }
    }
    private static class ForeignAudioFixture { public static void Prefix() { } }
}
