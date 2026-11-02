using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes.Debug;
using MegaCrit.Sts2.Core.Rooms;

namespace Volibear;

/// <summary>
/// Development bootstrap that starts a real run as Volibear, so the probe plays cards that came
/// from the character's own starting deck instead of synthetic test cards.
/// </summary>
public sealed class VolibearBootstrap : IBootstrapSettings
{
    public CharacterModel Character => ModelDb.Character<Content.VolibearCharacter>();
    private static string? Scenario => Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO");
    private static string? SummonCase => Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_SUMMON_CASE");
    private static string? PassiveCase => Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_PASSIVE_CASE");
    private static string? RevivalCase => Environment.GetEnvironmentVariable("VOLIBEAR_TEST_VARIANT");
    public RoomType RoomType => Scenario == "domain-suppression" ? DomainSuppressionAcceptanceProbe.Encounter.RoomType
        : Scenario == "domain-steam" ? RoomType.Boss : Scenario == "domain-card-contributions"
        ? DomainCardContributionsProbe.Family switch { "hex" => RoomType.Elite, "ringing" => RoomType.Boss, _ => RoomType.Monster }
        : Scenario == "domain-dampen-transactions" || (Scenario == "domain-summon-contract" &&
        SummonCase?.StartsWith("infested-", StringComparison.Ordinal) == true) ||
        (Scenario == "domain-passive-contract" && PassiveCase is "skittish-off" or "skittish-on") ||
        (Scenario == "domain-revival" && RevivalCase?.StartsWith("reattach-", StringComparison.Ordinal) == true)
            ? RoomType.Elite : RoomType.Monster;
    public EncounterModel Encounter
    {
        get
        {
            if (Scenario == "persistent-contract" &&
                Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PERSISTENT_CASE") is
                    "PP-R02-no-consumption" or "PP-U02-instances" or "PP-U02-domain-order")
                return ModelDb.Encounter<ChompersNormal>();
            if (Scenario == "card-face-acceptance" &&
                System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_CASE") is "R09-base-summon" or "R09-upgrade-summon")
                return ModelDb.Encounter<OvicopterNormal>();
            if (Scenario == "domain-suppression") return DomainSuppressionAcceptanceProbe.Encounter;
            if (Scenario == "domain-hopper") return ModelDb.Encounter<ThievingHopperWeak>();
            if (Scenario == "domain-steam") return ModelDb.Encounter<WaterfallGiantBoss>();
            if (Scenario == "domain-dampen-transactions") return DomainDampenTransactionsProbe.Encounter;
            if (Scenario == "domain-card-contributions") return DomainCardContributionsProbe.Encounter;
            if (Scenario == "domain-revival")
                return RevivalCase?.StartsWith("reattach-", StringComparison.Ordinal) == true
                    ? ModelDb.Encounter<DecimillipedeElite>() : ModelDb.Encounter<TheObscuraNormal>();
            if (Scenario == "domain-passive-contract")
                return PassiveCase switch
                {
                    "curlup-off" or "curlup-on" => ModelDb.Encounter<LouseProgenitorNormal>(),
                    "skittish-off" or "skittish-on" => ModelDb.Encounter<PhantasmalGardenersElite>(),
                    "suck-off" or "suck-on" => ModelDb.Encounter<FossilStalkerNormal>(),
                    "plating-initial-off" or "plating-initial-on" => ModelDb.Encounter<FrogKnightNormal>(),
                    _ => ModelDb.Encounter<SlimesWeak>()
                };
            if (Scenario == "domain-summon-contract")
                return SummonCase switch
                {
                    string name when name.StartsWith("fabricator-", StringComparison.Ordinal) => ModelDb.Encounter<FabricatorNormal>(),
                    string name when name.StartsWith("ovicopter-", StringComparison.Ordinal) => ModelDb.Encounter<OvicopterNormal>(),
                    string name when name.StartsWith("infested-", StringComparison.Ordinal) => ModelDb.Encounter<PhrogParasiteElite>(),
                    _ => throw new System.InvalidOperationException("Unknown domain summon encounter case")
                };
            return ModelDb.Encounter<SlimesWeak>();
        }
    }
    public EventModel Event => throw new System.InvalidOperationException("Not an event scenario");
    public ActModel Act => System.Linq.Enumerable.First(ActModel.GetDefaultList());
    public int Ascension => 0;
    public bool SaveRunHistory => false;
    public string Seed => "VOLIBEARTEST";
    public bool DoPreloading => true;
    public bool BootstrapInMultiplayer => false;
    public List<ModifierModel> Modifiers => new();
    public string Language => "zhs";
    public Task Setup(Player localPlayer)
    {
        // Only this isolated developer profile opts out of tutorial overlays.
        var expected = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT");
        if (string.IsNullOrEmpty(expected) ||
            !string.Equals(System.IO.Path.GetFullPath(expected), System.IO.Path.GetFullPath(Godot.OS.GetUserDataDir()), StringComparison.OrdinalIgnoreCase) ||
            MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized)
            throw new InvalidOperationException("Acceptance bootstrap requires its own offline data root.");
        var saves = MegaCrit.Sts2.Core.Saves.SaveManager.Instance;
        saves.SetFtuesEnabled(false);
        if (Environment.GetEnvironmentVariable("VOLIBEAR_TEST_FAST_MODE") == "Fast")
            saves.PrefsSave.FastMode = MegaCrit.Sts2.Core.Settings.FastModeType.Fast;
        Godot.GD.Print("[Volibear] ACCEPTANCE_SPEED " + saves.PrefsSave.FastMode + " isolated=true");
        return Task.CompletedTask;
    }
}
