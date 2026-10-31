using System.Collections.Generic;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes.Debug;
using MegaCrit.Sts2.Core.Rooms;

namespace Volibear;

// Explicitly enabled only by the isolated developer runner; never registered as normal content.
public sealed class DevelopmentBootstrap : IBootstrapSettings
{
    public CharacterModel Character => ModelDb.Character<Ironclad>();
    public RoomType RoomType => RoomType.Monster;
    public EncounterModel Encounter => ModelDb.Encounter<SlimesWeak>();
    public EventModel Event => throw new System.InvalidOperationException("Not an event scenario");
    public ActModel Act => System.Linq.Enumerable.First(ActModel.GetDefaultList());
    public int Ascension => 0;
    public bool SaveRunHistory => false;
    public string Seed => "VOLIBEARBASELINE";
    public bool DoPreloading => true;
    public bool BootstrapInMultiplayer => false;
    public List<ModifierModel> Modifiers => new();
    public string Language => "eng";
    public Task Setup(Player localPlayer) => Task.CompletedTask;

    public static void Install(bool installDriver = true)
    {
        if (installDriver)
            BaselineDriver.Install();
        if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ENGAGE") == "1")
        {
            var harmony = new Harmony("Volibear.EngagePrototype");
            harmony.CreateClassProcessor(typeof(EngagePrototype.SkipConsumedAction)).Patch();
            harmony.CreateClassProcessor(typeof(EngagePrototype.ObserveAbsorption)).Patch();
        }
        new Harmony("Volibear.DevelopmentBootstrap").Patch(
            AccessTools.Method(typeof(BootstrapSettingsUtil), nameof(BootstrapSettingsUtil.Get)),
            prefix: new HarmonyMethod(typeof(DevelopmentBootstrap), nameof(SelectSettings)));
    }

    private static bool SelectSettings(ref System.Type? __result)
    {
        __result = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CHARACTER") == "volibear"
            ? typeof(VolibearBootstrap)
            : typeof(DevelopmentBootstrap);
        return false;
    }
}
