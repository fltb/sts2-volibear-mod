// Managed fixtures and Harmony emission only. Does not launch Godot or invoke
// ModEntry.Initialize, scene/content registration, or BaseLib's initializer.
BlockCardModifierTests.Run();
SummonBoundaryAdapterTests.Run();
LightningResponseAdapterTests.Run().GetAwaiter().GetResult();
SteamOrdinaryCooperationTests.Run();
PowerScalarMetadataTests.Run();
SteamAudioObservationTests.Run(SteamFullInstallChainTests.Run);
// The domain probe observes the completion entered by the live native awaiter
// consumer as well as managed pipeline probes.
Volibear.DomainContractProbe.Install();
var pipeline = HarmonyLib.AccessTools.Method(typeof(Volibear.Core.CardResolutionHooks),
    nameof(Volibear.Core.CardResolutionHooks.CompleteOrdinaryAttack));
var observerPatches = HarmonyLib.Harmony.GetPatchInfo(pipeline);
if (observerPatches is null ||
    observerPatches.Prefixes.Count(p => p.owner == "Volibear.DomainContractObserver") != 1 ||
    observerPatches.Postfixes.Count(p => p.owner == "Volibear.DomainContractObserver") != 1)
    throw new InvalidOperationException("Domain probe must observe the exact shared ordinary pipeline.");
new HarmonyLib.Harmony("Volibear.DomainContractObserver").UnpatchAll("Volibear.DomainContractObserver");
Console.WriteLine("STEAM_DOMAIN_PROBE_EMISSION_PASS shared-pipeline=true gameplay=NOT_RUN");
