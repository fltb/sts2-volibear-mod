using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;
using Volibear.Core;

static class Program
{
    static int checks;
    static void Need(bool condition, string message)
    { checks++; if (!condition) throw new Exception(message); }
    static HoverTip[] Tips(IEnumerable<IHoverTip> tips) => tips.Cast<HoverTip>().ToArray();
    static string[] Ids(IEnumerable<IHoverTip> tips) => tips.Select(tip => tip.Id).ToArray();

    static void Main(string[] args)
    {
        switch (args[0])
        {
            case "glossary":
                Need(MechanicGlossary.Entries.Count == 26, "All frozen custom concepts have explanations");
                Need(MechanicGlossary.Entries.Select(e => e.Key).Distinct().Count() == 26, "Stable unique ids");
                Need(!MechanicGlossary.Match(null).Any() && !MechanicGlossary.Match("").Any(), "Empty text is empty");
                Need(Ids(MechanicHoverTips.ForText("迎战。吸收＋吸收。净化消耗并净化。")).SequenceEqual(
                    ["VOLIBEAR-ENGAGE", "VOLIBEAR-ABSORPTION", "VOLIBEAR-PURIFY"]), "Repeated aliases do not duplicate tips");
                Need(Ids(MechanicHoverTips.ForText("领域1")).SequenceEqual(["VOLIBEAR-DOMAIN", "VOLIBEAR-SUPPRESSION"]), "Timing and filtering are both explained");
                var engage = Tips(MechanicHoverTips.ForText("迎战")).Single().Description;
                Need(engage == "令目标立即执行当前意图。", "Approved engage copy preserved exactly");
                Need(!engage.Contains("实际开始"), "Engineering explanations are not restored to player copy");
                var domain = Tips(MechanicHoverTips.ForText("领域1"));
                Need(domain[0].Description.Contains("下回合抽牌后") && domain[0].Description.Contains("对全体造成4雷伤"), "Approved duration and lightning effects visible");
                Need(domain[0].Description.Contains("禁用自身debuff") && domain[0].Description.Contains("每抽到状态或诅咒消耗并补抽1张牌"), "Approved self suppression and purification visible");
                Need(domain[1].Description.Contains("保留普通攻击、已有及直接获得的力量与格挡"), "Approved beneficial-effect boundary visible");
                var beast = Tips(MechanicHoverTips.ForText("兽化")).Single().Description;
                Need(beast.Contains("先消耗原牌") && beast.Contains("生成新的兽形牌"), "Exhaust and generation remain explicit");
                Need(beast.Contains("攻击生成裂骨之爪，其他牌生成风暴之躯"), "Approved replacement types visible");
                Need(!beast.Contains("保留原牌实体"), "Retired identity overlay is not advertised");
                Need(Ids(MechanicHoverTips.ForText("雷甲")).Contains("VOLIBEAR-THUNDER_ARMOR"), "Title-only armor mechanic explained");
                Need(Ids(MechanicHoverTips.ForText("各部署独立计次")).Contains("VOLIBEAR-DEPLOYMENT"), "Legacy matcher aliases remain compatible");
                Need(Ids(MechanicHoverTips.ForText("能力叠加")).SequenceEqual(["VOLIBEAR-DEPLOYMENT"]), "Approved stacking title resolves");
                Need(Ids(MechanicHoverTips.ForText("出牌次数")).SequenceEqual(["VOLIBEAR-ATTACK_HISTORY"]), "Approved history title resolves");
                Need(MechanicGlossary.EnemyEntries.Any(e => e.Monsters.Contains("TheInsatiable") && e.Description.Contains("暂停倒计时与拉动")), "Actual locked sandworm model covered");
                Need(MechanicGlossary.Localization()["VOLIBEAR-DISABLED.selfTitle"].Contains("已被领域禁用"), "Exact disabled phrase for self debuffs");
                break;
            case "compose":
                var attack = new TestCard();
                Need(Ids(attack.HoverTips).SequenceEqual(["NATIVE-BASE", "VOLIBEAR-ENGAGE"]), "Production card getter preserves base tips");
                Need(Ids(new TestCard("b01").HoverTips).SequenceEqual(["NATIVE-BASE"]), "Plain strike gets no unrelated mechanics");
                Need(Ids(new TestCard("b03").HoverTips).SequenceEqual(["NATIVE-BASE", "VOLIBEAR-LIGHTNING"]), "Lightning on an attack does not grant thunder-spell tag");
                Need(!Ids(MechanicHoverTips.ForText("普通伤害，获得格挡。")).Any(), "No generic-word false positives");
                Need(EngageCmd.Queries == 0, "Card library does not query combat or consume opportunities");
                break;
            case "forms":
                Need(Ids(MechanicHoverTips.ForText("裂骨之爪")).SequenceEqual(["VOLIBEAR-BEAST_FORM"]), "Native claw has its own form tip");
                Need(Ids(MechanicHoverTips.ForText("风暴之躯 雷伤")).SequenceEqual(["VOLIBEAR-LIGHTNING", "VOLIBEAR-BEAST_FORM"]), "Native body has lightning and form explanation");
                Need(!Ids(MechanicHoverTips.ForText("风暴之躯 雷伤")).Contains("VOLIBEAR-ENGAGE"), "New token has no material-card tip");
                Need(!Ids(MechanicHoverTips.ForText("领域", "领域")).Contains("VOLIBEAR-DOMAIN"), "Own-tip omission remains available");
                break;
            case "reload":
                VolibearLoc.Install();
                Need(VolibearLoc.Installed, "Production localization installer includes glossary");
                var table = LocManager.Instance.GetTable("static_hover_tips");
                table.Entries["FOREIGN.title"] = "其他模组";
                Need(Tips(MechanicHoverTips.ForText("迎战")).Single().Title == "迎战", "Native LocString resolves title");
                Need(LocManager.Instance.GetTable("static_hover_tips").Entries["FOREIGN.title"] == "其他模组", "Merge preserves third-party localization");
                LocManager.Instance.Reload();
                Need(Tips(MechanicHoverTips.ForText("领域")).Select(t => t.Title).SequenceEqual(["领域", "领域压制"]), "Language-table replacement receives glossary again");
                Need(LocManager.Instance.GetTable("static_hover_tips").Entries.Count == 96, "All custom concepts, no-icon mechanics and disabled notices resolve");
                break;
            case "live":
                var combat = new CombatState();
                var player = new Creature { Name = "发起者", CombatState = combat };
                var a = new Creature { Name = "敌人甲", IsEnemy = true, CombatState = combat };
                var b = new Creature { Name = "敌人乙", IsEnemy = true, CombatState = combat };
                var dead = new Creature { Name = "已死亡", IsEnemy = true, CombatState = combat, IsAlive = false };
                combat.Members.AddRange([player, a, b, dead]);
                CombatManager.Instance.Current = combat;
                var card = new TestCard { Owner = new Player { Creature = player } };
                Need(Tips(card.HoverTips).Last().Description.Contains("所有存活敌人本轮都尚未行动"), "Fresh shared opportunity state shown");
                EngageCmd.Used.Add(a); EngageCmd.Used.Add(dead);
                var stateTip = Tips(card.HoverTips).Last();
                Need(stateTip.Id == "VOLIBEAR-ENGAGE_STATE" && stateTip.Description.Contains("敌人甲"), "Spent enemy named from actual ledger");
                Need(!stateTip.Description.Contains("敌人乙") && !stateTip.Description.Contains("已死亡"), "Unspent and dead enemies omitted");
                Need(stateTip.Description == "这些敌人本轮已行动，无法再次迎战：敌人甲。", "Approved action advice names only spent enemy");
                Need(EngageCmd.Used.Count == 2, "Reading does not mutate the shared ledger");
                EngageCmd.Used.Clear();
                Need(Tips(card.HoverTips).Last().Description.Contains("所有存活敌人本轮都尚未行动"), "New-round ledger state refreshes without cache");
                combat.CurrentSide = CombatSide.Enemy;
                Need(!Ids(card.HoverTips).Contains("VOLIBEAR-ENGAGE_STATE"), "No player action advice during enemy side");
                combat.CurrentSide = CombatSide.Player;
                CombatManager.Instance.Current = new CombatState();
                Need(!Ids(card.HoverTips).Contains("VOLIBEAR-ENGAGE_STATE"), "No stale combat snapshot");
                CombatManager.Instance.Current = combat;
                player.IsAlive = false;
                Need(!Ids(card.HoverTips).Contains("VOLIBEAR-ENGAGE_STATE"), "Dead owner gets no live action advice");
                player.IsAlive = true; combat.Members.Remove(player);
                Need(!Ids(card.HoverTips).Contains("VOLIBEAR-ENGAGE_STATE"), "Detached owner gets no live action advice");
                combat.Members.Add(player); CombatManager.Instance.IsOverOrEnding = true;
                Need(!Ids(card.HoverTips).Contains("VOLIBEAR-ENGAGE_STATE"), "Ending battle gets no live action advice");
                break;
            default: throw new Exception("Unknown case");
        }
        Console.WriteLine($"MECHANIC_HINTS_PASS {args[0]} checks={checks} native-rendering=NOT_RUN");
    }
}
