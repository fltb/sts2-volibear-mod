using System;
using System.Collections.Generic;
using System.Linq;

namespace Volibear.Content;

/// <summary>Presentation-only glossary. Matching visible words never grants a gameplay capability.</summary>
internal static class MechanicGlossary
{
    internal sealed record Entry(string Key, string Title, string Description, params string[] Words);

    internal static IReadOnlyList<Entry> Entries { get; } = new Entry[]
    {
        new("ENGAGE", "迎战", "按牌面顺序，令目标立即执行本轮尚未使用的真实行动。每名敌人每轮只有一次机会，全队共享；正常敌方阶段跳过已迎战的行动。保留敌人原本的攻击目标，不会让发起者替队友承伤。目标提前死亡或已经行动时不再执行；行动实际开始、发起者存活且战斗继续，才触发迎战完成收益。", "迎战"),
        new("DOMAIN", "领域", "展开或延长指定轮数。领域1持续到你的下一次正常起手抽牌结束，抽完才扣1轮；永久领域持续本战。你每次实际打出的攻击牌，在领域内首次普通攻击段后，对全体附加4＋当前雷势的雷伤，多段与重演共用一次机会。你实际抽到状态或诅咒时，净化消耗并补抽1张。敌方特殊效果的压制对全队生效；任一存活持有者仍有领域，压制就继续，多人领域不使压制翻倍。", "领域"),
        new("SUPPRESSION", "领域压制", "压制对敌人有利的特殊效果，例如复活、保护阶段、限伤、不可选和给玩家施加负面效果。保留普通攻击、已有及直接获得的力量与格挡。敌人自身的不利效果、状态到期和必要清理正常执行；混合效果分别处理。已取消的一次性效果不会在领域结束后补发。", "领域"),
        new("ABSORPTION", "吸收", "本次迎战中，发起者的格挡实际挡住的伤害总量。按每个伤害段累计；完全格挡也计算，坚甲未减少格挡仍照计。队友挡住的伤害不计入你的吸收。", "吸收"),
        new("LIGHTNING", "雷伤", "非普通攻击伤害。加上当前雷势及明确适用的增幅，不受普通攻击的力量、虚弱与易伤加成。仍经过格挡、减免和死亡结算。每段完整雷伤计1次，全体同一段也只计1次；不会递归触发普通攻击响应。", "雷伤"),
        new("THUNDER_FORCE", "雷势", "每点使每段雷伤增加1，持续本战，不自动消耗。一批全体雷伤使用同一份雷势数值；响应中新获得的雷势从下一批生效。", "雷势"),
        new("THUNDER_SPELL", "雷法", "牌面自身直接造成雷伤的技能。普通攻击附带雷伤仍是攻击；领域附雷不会把一张牌变成雷法。风暴之躯属于雷法。", "雷法"),
        new("BEASTIFY", "兽化", "先消耗原牌，再在原牌所在牌堆生成新的兽形牌：攻击生成裂骨之爪，其他牌生成风暴之躯。原牌正常触发消耗响应；新牌继承升级、临时减费与保留，使用后消耗。已有兽形不重复转换。永久牌组保持原牌。", "兽化"),
        new("BEAST_FORM", "兽形", "裂骨之爪与风暴之躯的统称。爪形为攻击，躯形为直接造成雷伤的技能；继承材料升级，使用后消耗。", "兽形", "爪形", "躯形", "裂骨之爪", "风暴之躯"),
        new("BITE", "咬痕", "暴怒撕咬命中后留下的标记，按发起玩家与敌人实体分别记录，持续本战。完全格挡仍可留下标记。追加伤害读取本次出牌前的标记，同次重演不会借用本牌刚施加的标记。", "咬痕"),
        new("RETALIATE", "反雷", "本轮每承受一段敌人攻击后，对该攻击者造成牌面指定的雷伤。完全格挡也触发；多段攻击逐段响应。", "反雷"),
        new("PREPARE", "蓄势", "指定牌下次打出时，每段固定普通攻击伤害增加指定值；该次完整出牌结算后清除。不会增加雷伤。", "蓄势"),
        new("TRAIN", "强化", "指定牌本战每段自身普通攻击与原生雷伤增加指定值。不是角色雷势，也不会提高其他牌的伤害。", "强化"),
        new("REPLAY", "重演", "额外结算完整牌效，沿用原目标、已支付的X和出牌前记录。不再次付费，不另算一次打出；与原牌共用领域附雷机会。", "重演"),
        new("DRAIN", "汲取", "按照该段伤害实际造成的生命损失恢复生命。被格挡或被减免的部分不计入恢复量。", "汲取"),
        new("RETAIN_BLOCK", "留甲", "回合开始时，格挡变为当前格挡减去指定值，最低0。重复获得时取较小的损耗。此更新不是获得格挡。", "留甲"),
        new("UNBREAKABLE", "坚甲", "承受攻击后，格挡保持原值；超过格挡的伤害仍扣生命。不会改变回合开始的清除格挡或留甲规则。", "坚甲"),
        new("PURIFY", "净化消耗", "先禁止所选状态或诅咒牌自身的效果，再消耗该牌。其他遗物与能力的消耗响应仍会触发。领域的实际抽牌净化会补抽1张；普通净化按牌面执行。", "净化消耗", "净化"),
        new("RETRIEVE", "检索", "从抽牌堆选择符合条件的牌加入手牌，受手牌上限约束。检索不是抽牌，不触发领域的抽牌净化。", "检索"),
        new("RECOVER", "回收", "从弃牌堆选择符合条件的牌加入手牌，受手牌上限约束。回收不是抽牌，不触发领域的抽牌净化。", "回收"),
        new("DISCOUNT", "减费", "按牌面为指定牌或下一张符合条件的牌降低费用，最低0。同类待用减费取最大值；实际打出时消费。X费牌仍按原生X费规则支付。", "减费"),
    };

    internal static IEnumerable<Entry> Match(string? text, string? omitTitle = null)
    {
        if (string.IsNullOrEmpty(text)) yield break;
        foreach (var entry in Entries)
            if (entry.Title != omitTitle && entry.Words.Any(word => text.Contains(word, StringComparison.Ordinal)))
                yield return entry;
    }

    internal static Dictionary<string, string> Localization()
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var entry in Entries)
        {
            result.Add("VOLIBEAR-" + entry.Key + ".title", entry.Title);
            result.Add("VOLIBEAR-" + entry.Key + ".description", entry.Description);
        }
        result.Add("VOLIBEAR-ENGAGE_STATE.title", "本轮迎战信息");
        result.Add("VOLIBEAR-ENGAGE_STATE.empty", "当前没有存活敌人用过本轮行动。行动机会由全队共享。");
        result.Add("VOLIBEAR-ENGAGE_STATE.spent", "本轮行动机会已用：{Enemies}。这些敌人本轮不能再次迎战；卡牌的其他效果仍按牌面结算。");
        return result;
    }
}
