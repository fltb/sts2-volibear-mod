// Managed fixtures and Harmony emission only. Does not launch Godot or invoke
// ModEntry.Initialize, scene/content registration, or BaseLib's initializer.
BlockCardModifierTests.Run();
SummonBoundaryAdapterTests.Run();
LightningResponseAdapterTests.Run().GetAwaiter().GetResult();
SteamOrdinaryCooperationTests.Run();
PowerScalarMetadataTests.Run();
SteamAudioObservationTests.Run(SteamFullInstallChainTests.Run);
// The domain probe must observe the shared pipeline, not the retired private
// helper or only the canonical entry that Steam legitimately replaces.
Volibear.DomainContractProbe.Install();
var pipeline = HarmonyLib.AccessTools.Method(typeof(Volibear.Core.CardResolutionHooks),
    nameof(Volibear.Core.CardResolutionHooks.OrdinaryAttackPipelineV1));
var observerPatches = HarmonyLib.Harmony.GetPatchInfo(pipeline);
if (observerPatches is null ||
    observerPatches.Prefixes.Count(p => p.owner == "Volibear.DomainContractObserver") != 1 ||
    observerPatches.Postfixes.Count(p => p.owner == "Volibear.DomainContractObserver") != 1)
    throw new InvalidOperationException("Domain probe must observe the exact shared ordinary pipeline.");
new HarmonyLib.Harmony("Volibear.DomainContractObserver").UnpatchAll("Volibear.DomainContractObserver");
Console.WriteLine("STEAM_DOMAIN_PROBE_EMISSION_PASS shared-pipeline=true gameplay=NOT_RUN");
