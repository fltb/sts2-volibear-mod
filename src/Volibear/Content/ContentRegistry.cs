using System;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Modding;

namespace Volibear.Content;

/// <summary>
/// Puts every Volibear model into its pool. The model database discovers model types from the
/// loaded mod assemblies itself; constructing or injecting them here would create duplicates.
/// </summary>
public static class ContentRegistry
{
    public static bool Registered { get; private set; }

    public static void Register()
    {
        if (Registered) return;
        Registered = true;
        try
        {
            // The localization manager is constructed during game startup; merge our tables as
            // soon as it exists instead of racing it from the mod initializer.
            try
            {
                var getTable = HarmonyLib.AccessTools.Method(
                    typeof(MegaCrit.Sts2.Core.Localization.LocManager),
                    nameof(MegaCrit.Sts2.Core.Localization.LocManager.GetTable),
                    [typeof(string)]);
                if (getTable is null)
                {
                    GD.PrintErr("[Volibear] LOC_PATCH_ERROR GetTable not found");
                }
                else
                {
                    new HarmonyLib.Harmony("Volibear.Localization").Patch(getTable,
                        postfix: new HarmonyLib.HarmonyMethod(typeof(VolibearLoc), nameof(VolibearLoc.AfterGetTable)));
                    VolibearLoc.Install();
                }
            }
            catch (Exception exception)
            {
                GD.PrintErr($"[Volibear] LOC_PATCH_ERROR {exception}");
            }
            var cards = VolibearCard.AllCardTypes.ToArray();
            foreach (var cardType in cards)
                ModHelper.AddModelToPool(typeof(VolibearCardPool), cardType);
            ModHelper.AddModelToPool(typeof(VolibearRelicPool), typeof(HuntersHeart));
            GD.Print($"[Volibear] CONTENT_OK cards={cards.Length} character={typeof(VolibearCharacter).Name}");
        }
        catch (Exception exception)
        {
            GD.PrintErr($"[Volibear] CONTENT_ERROR {exception}");
            throw;
        }
    }
}
