using System.Text.Json;
using HarmonyLib;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Modding;

namespace Volibear.Content;

internal static class VolibearLoc
{
    private static readonly Dictionary<string, Dictionary<string, string>> GlossarySources = new();
    private static bool Chinese => LocManager.Instance.Language is "zhs" or "zht";
    internal static string SentenceSeparator => Chinese ? "" : " ";
    internal static string ListSeparator => Chinese ? "、" : ", ";

    // Match the same mechanic hints in every language, including translated card titles.
    // Displayed titles and descriptions are always resolved by the native localization tables.
    internal static string GlossarySource(string table, string id)
    {
        if (!GlossarySources.TryGetValue(table, out var source))
        {
            var path = $"res://Volibear/localization/zhs/{table}.json";
            source = JsonSerializer.Deserialize<Dictionary<string, string>>(Godot.FileAccess.GetFileAsString(path))
                ?? throw new InvalidDataException(path);
            GlossarySources.Add(table, source);
        }
        return source.GetValueOrDefault(id + ".title") + "\n" + source.GetValueOrDefault(id + ".description");
    }

    internal static void Register()
    {
        // The mod initializer runs before the game constructs its localization manager.
        new Harmony("Volibear.Localization").Patch(AccessTools.Method(typeof(LocManager), nameof(LocManager.Initialize)),
            postfix: new HarmonyMethod(typeof(VolibearLoc), nameof(BindModMenu)));
        if (LocManager.Instance is not null) BindModMenu();
    }

    private static void BindModMenu()
    {
        var manager = LocManager.Instance;
        manager.SubscribeToLocaleChange(UpdateModMenu);
        UpdateModMenu();
    }

    private static void UpdateModMenu()
    {
        // The mod list reads the in-memory manifest directly. The manifest on disk also
        // supplies the default metadata when this mod is disabled.
        var manifest = ModManager.GetLoadedMods().FirstOrDefault(mod => mod.manifest?.id == "Volibear")?.manifest;
        if (manifest is null || !LocString.Exists("characters", "VOLIBEAR_MOD.title")) return;
        manifest.name = new LocString("characters", "VOLIBEAR_MOD.title").GetFormattedText();
        manifest.description = new LocString("characters", "VOLIBEAR_MOD.description").GetFormattedText();
    }
}
