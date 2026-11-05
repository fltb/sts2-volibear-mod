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
        new("ENGAGE", "迎战", "令目标立即执行当前意图。", "迎战"),
        new("DOMAIN", "领域", "展开指定轮数，每轮领域持续到下回合抽牌后。领域期间禁用敌方的特殊能力，禁用自身的负面状态，每抽到状态或诅咒消耗并补抽1张牌，每打出一张攻击牌对全体造成4雷伤。", "领域"),
        new("SUPPRESSION", "领域压制", "压制对敌人有利的特殊效果，例如复活、保护阶段、限伤、不可选和给玩家施加负面效果。保留普通攻击、已有及直接获得的力量与格挡。", "领域"),
        new("ABSORPTION", "吸收", "本次迎战中，发起者的格挡实际挡住的伤害总量。", "吸收"),
        new("LIGHTNING", "雷伤", "法术伤害，受雷势增幅。", "雷伤"),
        new("THUNDER_FORCE", "雷势", "每点使每段雷伤增加1。", "雷势"),
        new("THUNDER_SPELL", "雷法", "牌面自身直接造成雷伤的技能。", "雷法"),
        new("BEASTIFY", "兽化", "先消耗原牌，再生成新的兽形牌：攻击生成裂骨之爪，其他牌生成风暴之躯。", "兽化"),
        new("BEAST_FORM", "兽形", "裂骨之爪与风暴之躯的统称，分别称为爪形和躯形。继承原牌的升级，使用后消耗。", "兽形", "爪形", "躯形", "裂骨之爪", "风暴之躯"),
        new("BITE", "咬痕", "暴怒撕咬命中后留下的标记。", "咬痕"),
        new("RETALIATE", "反雷", "每承受一段敌人攻击后，对该攻击者造成指定的雷伤。", "反雷"),
        new("PREPARE", "蓄势", "指定牌下次打出时，每段攻击伤害增加指定值。", "蓄势"),
        new("TRAIN", "强化", "指定牌本战每段自身攻击与雷伤增加指定值。", "强化"),
        new("REPLAY", "重演", "额外结算完整牌效。", "重演"),
        new("DRAIN", "汲取", "按照实际造成的伤害恢复生命。", "汲取"),
        new("RETAIN_BLOCK", "留甲", "回合开始时，格挡不再移除，改为最多减少指定值。", "留甲"),
        new("UNBREAKABLE", "坚甲", "承受攻击后，格挡保持原值；超过格挡的伤害仍扣生命。", "坚甲"),
        new("PURIFY", "净化消耗", "先禁止所选状态或诅咒牌自身的效果，再消耗该牌。", "净化消耗", "净化"),
        new("RETRIEVE", "检索", "从抽牌堆选择符合条件的牌加入手牌。", "检索"),
        new("RECOVER", "回收", "从弃牌堆选择符合条件的牌加入手牌。", "回收"),
        new("DISCOUNT", "减费", "为指定牌降低费用。", "减费"),
        new("THUNDER_ARMOR", "雷甲", "每造成一次雷伤，获得指定数值的格挡。全体雷伤每段算一次。", "雷甲"),
        new("ORDINARY_SEGMENT", "普通攻击段", "多段攻击的每段伤害分别计算；同一段击中多个敌人仍算一段。", "每段普通攻击", "首次普通攻击段"),
        new("LIGHTNING_COUNT", "雷伤次数", "每段雷伤计一次，全体雷伤每段也计一次。本回合次数在下回合重新计算。", "雷霆余威", "累计2次雷伤", "每造成1次雷伤"),
        new("DEPLOYMENT", "能力叠加", "多次打出同一能力牌时，各自触发效果，分别计算次数。", "能力叠加", "每次部署", "各部署", "独立计次", "独立结算"),
        new("ATTACK_HISTORY", "出牌次数", "每打出一张攻击牌计一次，重演不额外计次。本回合次数在下回合重新计算。", "出牌次数", "第2张攻击", "第2张单体攻击", "每打出1张攻击"),
    };

    internal sealed record EnemyEntry(string Key, string Title, string Description, params string[] Monsters);
    internal static readonly EnemyEntry[] EnemyEntries =
    [
        new("SUMMON", "召唤", "召来新的敌人。领域期间无法召唤，已召来的敌人仍会战斗。",
            "Fabricator", "Ovicopter", "LivingFog", "TwoTailedRat", "Fogmog", "TheObscura"),
        new("HATCH", "孵化与变形", "死亡或进入新阶段时变为另一种形态。领域期间无法孵化、变形或复活。",
            "ToughEgg", "TestSubject"),
        new("FLEE", "胖地精逃跑", "离开战斗。领域期间无法逃跑。", "FatGremlin"),
        new("CARD_THEFT", "偷牌", "偷走你的卡牌，可能使你永久失去它。领域期间无法偷牌。", "ThievingHopper"),
        new("GOLD_THEFT", "偷金币", "偷走你的金币。领域期间无法偷取；击败敌人仍可取回已被偷走的金币。", "GremlinMerc"),
        new("STATUS_CARDS", "有害状态牌", "将状态牌加入你的牌堆。领域期间无法添加。",
            "MechaKnight", "TestSubject", "Aeonglass", "Chomper", "EyeWithTeeth", "HauntedShip", "LeafSlimeS", "LeafSlimeM",
            "TwigSlimeM", "SlimedBerserker", "Myte", "PhrogParasite", "Wriggler", "Vantom", "Noisebot", "SoulFysh"),
        new("SANDPIT", "沙坑与吞噬", "沙坑会将你拉向深处，倒计时归零时吞噬你。领域期间暂停倒计时与拉动，并禁用吞噬；领域结束后继续倒计时。", "TheInsatiable"),
        new("KNOWLEDGE", "知识限制", "选择承受持续伤害、减少抽牌、限制出牌或减少能量。领域期间这些负面效果暂不生效；领域结束后，尚未到期的效果恢复。", "KnowledgeDemon"),
        new("KNIGHTS", "骑士限制", "压制卡牌升级，并使卡牌获得虚无。领域期间恢复受压制的升级，并禁用此效果赋予的虚无；领域结束后，尚存的限制恢复。期间新获得的升级保留。", "MagiKnight", "SpectralKnight"),
    ];

    // These labels describe the actual gated contribution, never the entire Power.
    internal static readonly Entry[] SuppressedContributions =
    [
        new("ATTACK_BONUS", "攻击加成", "额外攻击伤害已被领域禁用。", "VigorPower"),
        new("BLOCK_RETENTION", "格挡保留", "回合间保留格挡的效果已被领域禁用。", "BurrowedPower"),
        new("MITIGATION", "减伤与限伤", "减伤与伤害上限已被领域禁用。", "FlutterPower", "SoarPower", "IntangiblePower", "SlipperyPower", "HardToKillPower", "HardenedShellPower"),
        new("ARTIFACT", "负面免疫", "抵挡负面状态的效果已被领域禁用。", "ArtifactPower"),
        new("RETALIATION", "伤害反击", "荆棘与反射伤害已被领域禁用。", "ThornsPower", "ReflectPower"),
        new("PASSIVE_STRENGTH", "被动力量增长", "被动获得力量的效果已被领域禁用。", "RitualPower", "SuckPower", "TerritorialPower", "HighVoltagePower", "EnragePower", "RavenousPower"),
        new("CRAB_RAGE", "死亡激怒", "死亡时获得力量与格挡的效果已被领域禁用。", "CrabRagePower"),
        new("PASSIVE_BLOCK", "被动格挡", "被动获得格挡的效果已被领域禁用。", "RampartPower", "PlatingPower", "CurlUpPower", "SkittishPower"),
        new("REVIVAL", "复活与保护", "复活、重新接合与死亡保护已被领域禁用。", "StockPower", "AdaptablePower", "ReattachPower", "IllusionPower"),
        new("STEAM", "蒸汽阶段", "蒸汽阶段与复活保护已被领域禁用。", "SteamEruptionPower"),
        new("DEATH_SUMMON", "死亡召唤", "死亡时召来敌人的效果已被领域禁用。", "InfestedPower", "SurprisePower"),
        new("GOLD_THEFT", "偷金币", "偷取金币已被领域禁用。", "ThieveryPower"),
        new("CARD_THEFT", "偷牌", "偷取卡牌已被领域禁用。", "SwipePower"),
        new("STATUS", "有害状态牌", "添加有害状态牌的效果已被领域禁用。", "WitheringPresencePower", "PainfulStabsPower", "PersonalHivePower"),
        new("GALVANIC", "状态牌附伤", "状态牌触发的额外伤害已被领域禁用。", "GalvanicPower"),
        new("VITAL_SPARK", "状态牌减伤", "状态牌降低你伤害的效果已被领域禁用。", "VitalSparkPower"),
        new("PAPER_CUTS", "生命上限损失", "降低生命上限的效果已被领域禁用。", "PaperCutsPower"),
    ];

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
        result.Add("VOLIBEAR-ENGAGE_STATE.empty", "所有存活敌人本轮都尚未行动。");
        result.Add("VOLIBEAR-ENGAGE_STATE.spent", "这些敌人本轮已行动，无法再次迎战：{Enemies}。");
        result.Add("VOLIBEAR-DISABLED.badge", "⊘ 已被领域禁用");
        result.Add("VOLIBEAR-DISABLED.description", "已被领域禁用");
        result.Add("VOLIBEAR-DISABLED.enemyTitle", "领域压制");
        result.Add("VOLIBEAR-DISABLED.enemyDescription", "该敌人的特殊机制已被领域禁用；普通攻击仍然有效。");
        result.Add("VOLIBEAR-DISABLED.selfTitle", "已被领域禁用");
        result.Add("VOLIBEAR-DISABLED.selfDescription", "负面状态暂不生效，受限能力恢复。状态仍会正常到期；领域结束后，尚未到期的状态恢复生效。");
        foreach (var entry in EnemyEntries)
        {
            result.Add("VOLIBEAR-ENEMY-" + entry.Key + ".title", entry.Title);
            result.Add("VOLIBEAR-ENEMY-" + entry.Key + ".description", entry.Description);
        }
        foreach (var entry in SuppressedContributions)
            result.Add("VOLIBEAR-CONTRIBUTION-" + entry.Key, entry.Description);
        return result;
    }
}
