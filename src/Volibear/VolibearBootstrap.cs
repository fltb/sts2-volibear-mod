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
    public RoomType RoomType => RoomType.Monster;
    public EncounterModel Encounter => ModelDb.Encounter<SlimesWeak>();
    public EventModel Event => throw new System.InvalidOperationException("Not an event scenario");
    public ActModel Act => System.Linq.Enumerable.First(ActModel.GetDefaultList());
    public int Ascension => 0;
    public bool SaveRunHistory => false;
    public string Seed => "VOLIBEARTEST";
    public bool DoPreloading => true;
    public bool BootstrapInMultiplayer => false;
    public List<ModifierModel> Modifiers => new();
    public string Language => "eng";
    public Task Setup(Player localPlayer) => Task.CompletedTask;
}
