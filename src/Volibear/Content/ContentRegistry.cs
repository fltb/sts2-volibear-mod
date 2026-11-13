using System;
using System.Linq;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Localization;

namespace Volibear.Content;

/// <summary>BaseLib owns model/pool registration; this installs the Chinese table adapter.</summary>
public static class ContentRegistry
{
    public static bool Registered { get; private set; }

    public static void Register()
    {
        if (Registered) return;
        var getTable = AccessTools.Method(typeof(LocManager), nameof(LocManager.GetTable), [typeof(string)])
            ?? throw new MissingMethodException("LocManager.GetTable(string)");
        new Harmony("Volibear.Localization").Patch(getTable,
            postfix: new HarmonyMethod(typeof(VolibearLoc), nameof(VolibearLoc.AfterGetTable)));
        // Tables may not exist during ModInitializer. Merge on retrieval, not eagerly.
        // Do not install the old Ironclad visual or filesystem portrait Harmony bridges.
        // BaseLib constructors + Pool attributes are the single model registration path.
        Registered = true;
        var cards = VolibearCard.AllCardTypes.Count();
        GD.Print($"[Volibear] CONTENT_OK cards={cards} character={nameof(VolibearCharacter)} framework=BaseLib-{typeof(BaseLib.Abstracts.CustomCardModel).Assembly.GetName().Version}");
    }
}
