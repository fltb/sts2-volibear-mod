using Godot;
using MegaCrit.Sts2.Core.Modding;
using Volibear.Content;

namespace Volibear;

[ModInitializer(nameof(Initialize))]
public static class ModEntry
{
    public static void Initialize()
    {
        DomainSteamNativeObservation.PrepareForTestScenario();
        Presentation.VolibearPresentation.RegisterSceneConversions();
        ContentRegistry.Register();
        Core.EngageCmd.Install();
        Core.CardResolutionHooks.Install();
        Core.DomainEnemyEffects.Install();
        Core.DomainHopperEffects.Install();
        Core.BeastForms.Install();
        Core.AttackHistory.Install();
        Core.TargetCosts.Install();
        Core.PersistentBlockHooks.Install();
        Core.DomainSummonEffects.Install();
        Core.DomainRevivalEffects.Install();
        Core.DomainPassiveEffects.Install();
        Core.DomainCardContributions.Install();
        Core.DomainDampenTransactions.Install();
        Core.DomainSteamEruptionEffects.Install();
        Core.DomainPlayerStatContributions.Install();
        Core.DomainPlayerDebuffContributions.StatCancellation = Core.DomainPlayerStatContributions.ShouldCancel;
        Core.DomainPlayerDebuffContributions.Install();
        Core.DomainEnemyStatusContributions.Install();
        Core.DomainEnemySpecialContributions.Install();
        Core.DomainAdditionalRevivalEffects.Install();
        Presentation.VolibearPresentationBridge.Install();
        Presentation.VolibearInspectPortraits.Install();
        var expectedDirectory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT");
        if (!string.IsNullOrEmpty(expectedDirectory))
        {
            var actual = System.IO.Path.GetFullPath(OS.GetUserDataDir());
            var expected = System.IO.Path.GetFullPath(expectedDirectory);
            if (actual != expected || MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized)
                throw new System.InvalidOperationException("Volibear test isolation assertion failed");
            GD.Print("[Volibear] ISOLATION_OK steam=false");
            var scenario = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO");
            if (scenario == "baseline")
                DevelopmentBootstrap.Install();
            else if (scenario == "save-load-contract")
                SaveLoadContractProbe.Install();
            else if (scenario == "save-load-catalog")
                SaveLoadCatalogProbe.Install();
            else if (scenario == "api")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                ApiProbe.Install();
            }
            else if (scenario == "content")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                ContentProbe.Install();
            }
            else if (scenario == "engage-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                EngageContractProbe.Install();
            }
            else if (scenario == "domain-hopper")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainHopperProbe.Install();
            }
            else if (scenario == "domain-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainContractProbe.Install();
            }
            else if (scenario == "beast-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                BeastContractProbe.Install();
            }
            else if (scenario == "domain-enemy-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainEnemyContractProbe.Install();
            }
            else if (scenario == "persistent-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PersistentContractProbe.Install();
            }
            else if (scenario == "catalog")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                CardCatalogProbe.Install();
            }
            else if (scenario == "enemy-catalog")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                EnemyCatalogProbe.Install();
            }
            else if (scenario == "domain-summon-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                var summonCase = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_SUMMON_CASE") ?? "";
                if (DomainSummonD17Probe.Variants.Contains(summonCase)) DomainSummonD17Probe.Install();
                else DomainSummonContractProbe.Install();
            }
            else if (scenario == "manual-play")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                ManualPlayProbe.Install();
            }
            else if (scenario == "relic-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                RelicContractProbe.Install();
            }
            else if (scenario == "domain-passive-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                var passiveCase = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE");
                if (passiveCase is "newapply-off" or "newapply-on" or "newapply-open" or "newapply-close" or "newapply-post")
                    NewStrengthPassiveProbe.Install();
                else if (passiveCase is "suck-off" or "suck-on")
                    SuckPassiveContractProbe.Install();
                else if (passiveCase is "plating-initial-off" or "plating-initial-on")
                    InitialPlatingContractProbe.Install();
                else if (passiveCase is "curlup-off" or "curlup-on" or "skittish-off" or "skittish-on")
                    CardPassiveContractProbe.Install();
                else PassiveContractProbe.Install();
            }
            else if (scenario == "card-face-acceptance")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                CardFaceAcceptanceProbe.Install();
            }
            else if (scenario == "card-lifecycle")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                CardLifecycleAcceptanceProbe.Install();
            }
            else if (scenario == "native-run")
            {
                // Exercise normal selection / save / Continue, with no development run fixture.
                NativeRunAcceptanceProbe.Install();
            }
            else if (scenario == "presentation-acceptance")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PresentationAcceptanceProbe.Install();
            }
            else if (scenario == "prepared-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PreparedContractProbe.Install();
            }
            else if (scenario == "prepared-choice")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PreparedChoiceProbe.Install();
            }
            else if (scenario == "audio-receipts")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                AudioReceiptProbe.Install();
            }
            else if (scenario == "primal-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PrimalContractProbe.Install();
            }
            else if (scenario == "coupon-contract")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                CouponContractProbe.Install();
            }
            else if (scenario == "domain-steam")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainSteamEruptionProbe.Install();
            }
            else if (scenario == "standing-extra-turn")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                StandingExtraTurnProbe.Install();
            }
            else if (scenario == "domain-dampen-transactions")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainDampenTransactionsProbe.Install();
            }
            else if (scenario == "domain-card-contributions")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainCardContributionsProbe.Install();
            }
            else if (scenario == "power-presentation")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                PowerPresentationProbe.Install();
            }
            else if (scenario == "domain-revival")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                DomainRevivalProbe.Install();
            }
            else if (scenario == "enemy-matrix-mvp")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                EnemyMatrixProbe.Install();
            }
            else if (scenario == "enemy-exploration")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                EnemyExplorationProbe.Install();
            }
        }
        GD.Print("[Volibear] LOAD_OK version=0.1.0 target=0.107.1 phase=development-candidate gameplay=partial");
    }
}
