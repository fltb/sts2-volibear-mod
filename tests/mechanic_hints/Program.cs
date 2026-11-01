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
                Need(MechanicGlossary.Entries.Count == 21, "All frozen custom concepts have explanations");
                Need(MechanicGlossary.Entries.Select(e => e.Key).Distinct().Count() == 21, "Stable unique ids");
                Need(!MechanicGlossary.Match(null).Any() && !MechanicGlossary.Match("").Any(), "Empty text is empty");
                Need(Ids(MechanicHoverTips.ForText("迎战。吸收＋吸收。净化消耗并净化。")).SequenceEqual(
                    ["VOLIBEAR-ENGAGE", "VOLIBEAR-ABSORPTION", "VOLIBEAR-PURIFY"]), "Repeated aliases do not duplicate tips");
                Need(Ids(MechanicHoverTips.ForText("领域1")).SequenceEqual(["VOLIBEAR-DOMAIN", "VOLIBEAR-SUPPRESSION"]), "Timing and filtering are both explained");
                var engage = Tips(MechanicHoverTips.ForText("迎战")).Single().Description;
                Need(engage.Contains("全队共享") && engage.Contains("保留敌人原本的攻击目标"), "Multiplayer target rules visible");
                Need(engage.Contains("行动实际开始") && engage.Contains("发起者存活且战斗继续"), "Completion conditions visible");
                var domain = Tips(MechanicHoverTips.ForText("领域1"));
                Need(domain[0].Description.Contains("下一次正常起手抽牌结束") && domain[0].Description.Contains("4＋当前雷势"), "Draw boundary and attachment visible");
                Need(domain[0].Description.Contains("多段与重演共用一次") && domain[0].Description.Contains("你实际抽到"), "Personal benefit boundary visible");
                Need(domain[1].Description.Contains("敌人自身的不利效果") && domain[1].Description.Contains("不会在领域结束后补发"), "Beneficial-only suppression visible");
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
                Need(Ids(MechanicHoverTips.ForBeast(true)).SequenceEqual(["VOLIBEAR-BEAST_FORM"]), "Converted claw shows only current form");
                Need(Ids(MechanicHoverTips.ForBeast(false)).SequenceEqual(["VOLIBEAR-LIGHTNING", "VOLIBEAR-BEAST_FORM"]), "Converted body has lightning and form explanation");
                Need(!Ids(MechanicHoverTips.ForBeast(false)).Contains("VOLIBEAR-ENGAGE"), "Original foreign-card effect cannot leak into converted tip");
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
                Need(LocManager.Instance.GetTable("static_hover_tips").Entries.Count == 45, "All 21 title/body pairs and three state entries resolve");
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
                Need(Tips(card.HoverTips).Last().Description.Contains("当前没有存活敌人"), "Fresh shared opportunity state shown");
                EngageCmd.Used.Add(a); EngageCmd.Used.Add(dead);
                var stateTip = Tips(card.HoverTips).Last();
                Need(stateTip.Id == "VOLIBEAR-ENGAGE_STATE" && stateTip.Description.Contains("敌人甲"), "Spent enemy named from actual ledger");
                Need(!stateTip.Description.Contains("敌人乙") && !stateTip.Description.Contains("已死亡"), "Unspent and dead enemies omitted");
                Need(stateTip.Description.Contains("其他效果仍按牌面结算"), "Hint does not claim card is unplayable");
                Need(EngageCmd.Used.Count == 2, "Reading does not mutate the shared ledger");
                EngageCmd.Used.Clear();
                Need(Tips(card.HoverTips).Last().Description.Contains("当前没有存活敌人"), "New-round ledger state refreshes without cache");
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
