using System.Linq;
using Godot;

namespace Volibear.Content;

/// <summary>BaseLib owns model/pool registration; the game loads localization tables from the mod PCK.</summary>
public static class ContentRegistry
{
    public static bool Registered { get; private set; }

    public static void Register()
    {
        if (Registered) return;
        VolibearLoc.Register();
        Registered = true;
        var cards = VolibearCard.AllCardTypes.Count();
        GD.Print($"[Volibear] CONTENT_OK cards={cards} character={nameof(VolibearCharacter)} framework=BaseLib-{typeof(BaseLib.Abstracts.CustomCardModel).Assembly.GetName().Version}");
    }
}
