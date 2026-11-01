using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Localization;

namespace Volibear.Content;

/// <summary>
/// Localization tables for the mod. They are merged into the game's own tables so the card,
/// relic and character text resolves exactly like content shipped inside a pck. Keys use the
/// model database's own entry names, which is why the character key carries its full id.
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
                ["VOLIBEAR_B02.description"] = "获得{Block}格挡。",
                ["VOLIBEAR_B03.title"] = "霆爪",
                ["VOLIBEAR_B03.description"] = "造成{Damage}伤害。对全体造成{Lightning}雷伤。",
                ["VOLIBEAR_B04.title"] = "挺身迎战",
                ["VOLIBEAR_B04.description"] = "获得{Block}格挡。造成{Damage}伤害。迎战。",
            },
            ["characters"] = new()
            {
                ["VOLIBEAR_CHARACTER.title"] = "沃利贝尔",
                ["VOLIBEAR_CHARACTER.description"] = "不灭狂雷。以雷霆与兽性碾碎敌人。",
                ["VOLIBEAR_CHARACTER.titleObject"] = "沃利贝尔",
                ["VOLIBEAR_CHARACTER.pronounSubject"] = "他",
                ["VOLIBEAR_CHARACTER.pronounObject"] = "他",
                ["VOLIBEAR_CHARACTER.pronounPossessive"] = "他的",
                ["VOLIBEAR_CHARACTER.possessiveAdjective"] = "他的",
                ["VOLIBEAR_CHARACTER.cardsModifierTitle"] = "不灭狂雷",
                ["VOLIBEAR_CHARACTER.cardsModifierDescription"] = "沃利贝尔的卡牌会出现在奖励和商店中。",
                ["VOLIBEAR_CHARACTER.eventDeathPrevention"] = "雷霆拒绝了死亡。",
                ["VOLIBEAR_CHARACTER.aromaPrinciple"] = "风暴只服从自己的意志",
                ["VOLIBEAR_CHARACTER.goldMonologue"] = "这些金属，终将被雷霆熔铸。",
                ["VOLIBEAR_CHARACTER.banter.alive.endTurnPing"] = "风暴不会等待。",
                ["VOLIBEAR_CHARACTER.banter.dead.endTurnPing"] = "雷声尚未消散……",
            },
            ["relics"] = new()
            {
                ["HUNTERS_HEART.title"] = "不灭狂雷",
                ["HUNTERS_HEART.description"] = "每回合首次完成迎战后，抽1张牌。",
                ["HUNTERS_HEART.flavor"] = "雷霆不会熄灭。",
                ["VOLIBEAR_HUNTERS_HEART.title"] = "不灭狂雷",
                ["VOLIBEAR_HUNTERS_HEART.description"] = "每回合首次完成迎战后，抽1张牌。",
                ["VOLIBEAR_HUNTERS_HEART.flavor"] = "雷霆不会熄灭。",
                ["SEA_GLASS.VOLIBEAR_CHARACTER.title"] = "风暴海玻璃",
            },
            // BaseLib adds these lines to TheArchitect's actual dialogue set.
            // Every line uses the repeat suffix so both first and later victories
            // have a valid character-specific conversation in the native finale.
            ["ancients"] = new()
            {
                ["THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-0r.ancient"] = "你的风暴，已经震动了这里的根基。",
                ["THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-1r.char"] = "石墙会崩塌。雷霆不会。",
                ["THE_ARCHITECT.talk.VOLIBEAR_CHARACTER.0-2r.ancient"] = "那就让我看看，这场风暴还能持续多久。",
            },
            ["powers"] = new(),
            ["static_hover_tips"] = MechanicGlossary.Localization(),
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
        if (Tables.TryGetValue(name, out var entries) && entries.Count > 0)
            __result.MergeWith(entries);
        InlineModelLocalization.Merge(name, __result);
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
            merged += entries.Count;
        }
        installed = true;
        GD.Print($"[Volibear] LOC_OK entries={merged}");
    }
}
