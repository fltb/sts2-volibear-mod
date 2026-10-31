using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Localization;

namespace Volibear.Content;

/// <summary>
/// Localization tables for the mod. They are merged into the game's own tables so the card,
/// relic and character text resolves exactly like content shipped inside a pck.
/// </summary>
public static class VolibearLoc
{
    public static readonly IReadOnlyDictionary<string, Dictionary<string, string>> Tables =
        new Dictionary<string, Dictionary<string, string>>
        {
            ["cards"] = new()
            {
                ["VOLIBEAR_B01.title"] = "打击",
                ["VOLIBEAR_B01.description"] = "造成{Damage}伤害。",
                ["VOLIBEAR_B02.title"] = "防御",
                ["VOLIBEAR_B02.description"] = "获得{Block}点格挡。",
                ["VOLIBEAR_B03.title"] = "霆爪",
                ["VOLIBEAR_B03.description"] = "造成{Damage}伤害。对所有敌人造成{Lightning}点雷伤。",
                ["VOLIBEAR_B04.title"] = "挺身迎战",
                ["VOLIBEAR_B04.description"] = "获得{Block}点格挡。造成{Damage}伤害。迎战。",
            },
            ["characters"] = new()
            {
                ["VOLIBEAR.title"] = "沃利贝尔",
                ["VOLIBEAR.description"] = "不灭狂雷。以雷霆与兽性碾碎敌人。",
                ["VOLIBEAR.pronoun_subject"] = "他",
                ["VOLIBEAR.pronoun_object"] = "他",
                ["VOLIBEAR.pronoun_possessive"] = "他的",
                ["VOLIBEAR.possessive_adjective"] = "他的",
                ["VOLIBEAR.cards_modifier_title"] = "不灭狂雷",
                ["VOLIBEAR.cards_modifier_description"] = "沃利贝尔的卡牌与机制。",
                ["VOLIBEAR.event_death_prevention"] = "{0}的雷霆拒绝了死亡。",
            },
            ["relics"] = new()
            {
                ["VOLIBEAR_HUNTERS_HEART.title"] = "不灭狂雷",
                ["VOLIBEAR_HUNTERS_HEART.description"] = "每场战斗首次迎战时，抽一张牌。",
                ["VOLIBEAR_HUNTERS_HEART.flavor"] = "雷霆不会熄灭。",
            },
            ["powers"] = new(),
        };

    private static bool installed;

    public static bool Installed => installed;

    /// <summary>
    /// Harmony postfix: every table the game hands out gets our entries merged first, so a table
    /// reload or language switch cannot leave the mod's text unresolved.
    /// </summary>
    public static void AfterGetTable(string name, ref LocTable __result)
    {
        if (__result is null) return;
        if (!Tables.TryGetValue(name, out var entries) || entries.Count == 0) return;
        __result.MergeWith(entries);
        installed = true;
    }

    public static void Install()
    {
        var manager = LocManager.Instance;
        if (manager is null)
        {
            GD.PrintErr("[Volibear] LOC_ERROR manager unavailable");
            return;
        }
        var merged = 0;
        var tables = new List<object>();
        foreach (var (tableName, entries) in Tables)
        {
            if (entries.Count == 0) continue;
            var table = manager.GetTable(tableName);
            if (table is null)
            {
                GD.PrintErr($"[Volibear] LOC_ERROR missing table {tableName}");
                continue;
            }
            table.MergeWith(entries);
            tables.Add(entries.ContainsKey("VOLIBEAR_B01.title") && table.HasEntry("VOLIBEAR_B01.title"));
            merged += entries.Count;
        }
        installed = true;
        GD.Print($"[Volibear] LOC_OK entries={merged} probe={tables[0]}");
    }
}
