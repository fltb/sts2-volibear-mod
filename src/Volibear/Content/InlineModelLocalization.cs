using System;
using System.Collections.Generic;
using System.Reflection;
using BaseLib.Abstracts;
using BaseLib.Patches.Localization;
using HarmonyLib;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>
/// BaseLib installs inline model strings at ModelDb.Init. Native language reloads
/// replace those tables afterwards; remerge our already-registered models without
/// constructing or registering any model a second time.
/// </summary>
internal static class InlineModelLocalization
{
    private static readonly FieldInfo Content = AccessTools.Field(typeof(ModelDb), "_contentById")
        ?? throw new MissingFieldException(typeof(ModelDb).FullName, "_contentById");
    private static readonly Dictionary<string, Dictionary<string, string>> Cached = new();
    private static int _modelCount = -1;
    [ThreadStatic] private static bool _merging;

    internal static void Merge(string tableName, LocTable table)
    {
        if (_merging) return;
        _merging = true;
        try
        {
            var models = Content.GetValue(null) as Dictionary<ModelId, AbstractModel>
                ?? throw new InvalidOperationException("Pinned ModelDb content dictionary unavailable.");
            if (_modelCount != models.Count)
            {
                Cached.Clear();
                foreach (var (id, model) in models)
                {
                    if (model.GetType().Assembly != typeof(InlineModelLocalization).Assembly ||
                        model is not ILocalizationProvider provider || provider.Localization is not { } strings)
                        continue;
                    var category = provider.LocTable ?? (model switch
                    {
                        CardModel => "cards",
                        PowerModel => "powers",
                        RelicModel => "relics",
                        CharacterModel => "characters",
                        _ => null
                    });
                    if (category is null) continue;
                    if (!Cached.TryGetValue(category, out var entries))
                        Cached.Add(category, entries = new Dictionary<string, string>());
                    foreach (var (key, value) in strings)
                        entries[id.Entry + "." + key] = SimpleLoc.TrySimplify(value);
                }
                _modelCount = models.Count;
            }
            if (Cached.TryGetValue(tableName, out var localized)) table.MergeWith(localized);
        }
        finally { _merging = false; }
    }
}
