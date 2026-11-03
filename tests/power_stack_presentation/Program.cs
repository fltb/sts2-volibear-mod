using System.Reflection;
using System.Runtime.CompilerServices;
using BaseLib.Abstracts;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Content;
using Volibear.Core;
using Volibear.Presentation;

internal static class Program
{
    private static int checks, ownerReads, hoverReads;
    private static readonly HashSet<PowerModel> Hidden = new(ReferenceEqualityComparer.Instance);
    private static void Need(bool value, string label) { checks++; if (!value) throw new Exception(label); }
    private static bool OwnerRead() { ownerReads++; throw new Exception("Projection read public Owner getter"); }
    private static bool HoverRead() { hoverReads++; throw new Exception("Projection recursed through HoverTips"); }
    private static bool Visible(PowerModel __instance, ref bool __result)
    {
        if (!Hidden.Contains(__instance)) return true;
        __result = false; return false;
    }
    private static Creature Owner()
    {
        var owner = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        AccessTools.Field(typeof(Creature), "_powers").SetValue(owner, new List<PowerModel>());
        return owner;
    }
    private static List<PowerModel> Powers(Creature owner) => (List<PowerModel>)AccessTools.Field(typeof(Creature), "_powers").GetValue(owner);
    private static PowerModel Make(Type type, int amount, Creature? owner, string id = "STACK_TEST", bool mutable = true)
    {
        var power = (PowerModel)RuntimeHelpers.GetUninitializedObject(type);
        AccessTools.Property(typeof(AbstractModel), "IsMutable").SetValue(power, mutable);
        AccessTools.Field(typeof(AbstractModel), "<Id>k__BackingField").SetValue(power, new ModelId("powers", id));
        AccessTools.Field(typeof(PowerModel), "_owner").SetValue(power, owner);
        AccessTools.Field(typeof(PowerModel), "_amount").SetValue(power, amount);
        if (owner is not null) Powers(owner).Add(power);
        return power;
    }
    private static PowerStackProjection Describe(PowerModel power)
    {
        Need(PowerStackPresentation.TryDescribe(power, out var result), power.GetType().Name + " supported");
        return result;
    }
    public static void Main()
    {
        var harmony = new Harmony("Volibear.Tests.PowerStackProjection");
        harmony.Patch(AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Owner)), prefix: new(typeof(Program), nameof(OwnerRead)));
        harmony.Patch(AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.HoverTips)), prefix: new(typeof(Program), nameof(HoverRead)));
        harmony.Patch(AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.IsVisible)), prefix: new(typeof(Program), nameof(Visible)));
        try
        {
            (Type Type, string One, string Two)[] rules = [
                (typeof(NextAttackDiscount), "3", "4"), (typeof(NextEngageDiscount), "", ""),
                (typeof(NextAttackReplayPower), "3", "7"), (typeof(NextAttackTrainingPower), "3", "7"),
                (typeof(UnifyPower), "3", "7"), (typeof(PrimalThunderPower), "3", "7"),
                (typeof(ThunderGuardPower), "1", "2"), (typeof(BiteMarkPower), "", ""),
                (typeof(StormConductionPower), "1", "2"), (typeof(StandingPower), "3", "3"),
                (typeof(BattleScarsPower), "1", "2"), (typeof(LingeringStormPower), "1", "2"),
                (typeof(ThunderAftershockPower), "1", "2"), (typeof(PreyStillStandsPower), "1", "2"),
                (typeof(GrowingFuryPower), "1", "2"), (typeof(WelcomeThunderPower), "3", "4"),
                (typeof(ThunderArmorPower), "3", "7"), (typeof(ImmovableBodyPower), "", ""),
                (typeof(BattleBodyPower), "3", "7"), (typeof(ThunderPoolPower), "1", "2"),
                (typeof(BearSpiritPower), "1", "2"), (typeof(WildernessPower), "1", "2"),
                (typeof(StormChargePower), "3", "7"), (typeof(DomainPower), "3", "4"),
                (typeof(EndlessHuntPower), "3", "7"), (typeof(VolibearChargeStrengthPower), "3", "7")
            ];
            var concrete = typeof(DomainPower).Assembly.GetTypes().Where(t => !t.IsAbstract && typeof(PowerModel).IsAssignableFrom(t)).ToHashSet();
            Need(concrete.SetEquals(rules.Select(r => r.Type)), "every concrete custom power has an explicit rule");
            foreach (var (type, one, two) in rules)
            {
                var owner = Owner(); var a = Make(type, 3, owner);
                var single = Describe(a);
                Need(single.AmountText == one && single.Members.Count == 1 && ReferenceEquals(single.Members[0], a), type.Name + " single label");
                Need(single.Description.Length > 5 && !single.Description.Contains('{'), type.Name + " full resolved single description");
                if (type == typeof(DomainPower))
                {
                    AccessTools.Field(typeof(PowerModel), "_amount").SetValue(a, 4);
                    Need(Describe(a).AmountText == "4" && Describe(a).Members.Count == 1, "domain uses its one native duration, not a fabricated second domain");
                    AccessTools.Field(typeof(PowerModel), "_amount").SetValue(a, CardResolutionDuration.Permanent);
                    Need(Describe(a).AmountText == "本战" && Describe(a).Description.StartsWith("领域持续本战。"), "permanent domain marked explicitly");
                    Console.WriteLine("STACK_RULE DomainPower single=3 changed=4 permanent=本战");
                    continue;
                }
                var b = Make(type, 4, owner); var before = owner.Powers.ToArray();
                var pair = Describe(a); var fromSecond = Describe(b);
                Need(pair.AmountText == two && pair.Members.Count == 2 && fromSecond.AmountText == two && fromSecond.Description == pair.Description, type.Name + " stable aggregate from either member");
                Need(a.Amount == 3 && b.Amount == 4 && before.SequenceEqual(owner.Powers), type.Name + " never changes amount/membership/order");
                Need(pair.Description.Length > 5 && !pair.Description.Contains('{') && !pair.Description.Contains("实例") && !pair.Description.Contains("已被领域禁用"), type.Name + " readable standalone description, badge left to UI");
                if (one == "1")
                {
                    var text = ((CustomPowerModel)a).Localization.Single(v => v.Item1 == "smartDescription").Item2;
                    Need(single.Description == "共1份。" + text.Replace("{Amount}", "3"), type.Name + " single copy has one concise count and the complete effect");
                    Need(pair.Description.StartsWith("共2份，分别触发。") && pair.Description.Contains(text.Replace("{Amount}", "3")) && pair.Description.Contains(text.Replace("{Amount}", "4")), type.Name + " separate complete effects, conditions and lifetime");
                }
                Console.WriteLine($"STACK_RULE {type.Name} single={one} pair={two}");
            }
            {
                var owner = Owner(); var a = Make(typeof(WelcomeThunderPower), 2, owner); var b = Make(typeof(WelcomeThunderPower), 5, owner);
                var result = Describe(a);
                Need(result.AmountText == "5" && result.Description.StartsWith("共2份，分别触发。"), "welcome thunder displays maximum, not sum or count");
                Need(result.Description.Contains("1份：每回合首次完成迎战后，本回合下一张攻击减费2。") &&
                    result.Description.Contains("1份：每回合首次完成迎战后，本回合下一张攻击减费5。") &&
                    result.Description.EndsWith("减费不相加，取最高值。"), "welcome thunder preserves both independent first-trigger allowances and distinct values");
                Need(a.Amount == 2 && b.Amount == 5 && owner.Powers.Count == 2, "welcome thunder projection preserves both responders");
            }
            {
                var owner = Owner(); var a = Make(typeof(ThunderArmorPower), 3, owner); var b = Make(typeof(ThunderArmorPower), 4, owner);
                var result = Describe(a);
                Need(result.AmountText == "7" && result.Description.StartsWith("每造成一次雷伤，获得合计7基础格挡") && result.Description.Contains("分2次获得（3、4）"), "thunder armor is seven, never an original three with a vague seven appended");
                try { ((IList<PowerModel>)result.Members)[0] = b; throw new Exception("Mutable projection collection"); }
                catch (NotSupportedException) { checks++; }
                Powers(owner).Remove(a);
                Need(!PowerStackPresentation.TryDescribe(a, out _), "removed native instance is not a representative");
                Need(Describe(b).AmountText == "4" && result.Members.Count == 2, "fresh projection reflects removal without mutating prior snapshot");
                Make(typeof(ThunderArmorPower), 2, owner);
                Need(Describe(b).AmountText == "6", "reapplication observed without cached totals");
            }
            {
                var owner = Owner(); var a = Make(typeof(ThunderArmorPower), 3, owner); var hidden = Make(typeof(ThunderArmorPower), 4, owner);
                Hidden.Add(hidden);
                Make(typeof(ThunderArmorPower), 9, owner, "OTHER");
                Make(typeof(StormChargePower), 9, owner);
                Make(typeof(ThunderArmorPower), 9, owner, mutable: false);
                var foreign = Make(typeof(ThunderArmorPower), 9, Owner()); Powers(owner).Add(foreign);
                Powers(owner).Add(a);
                Need(Describe(a).AmountText == "3" && Describe(a).Members.Count == 1, "owner/type/id/visibility/mutability/reference uniqueness isolate groups");
                Need(!PowerStackPresentation.TryDescribe(hidden, out _), "hidden current power omitted");
                Need(!PowerStackPresentation.TryDescribe(Make(typeof(ThunderArmorPower), 3, null), out _), "unbound early return");
                Need(!PowerStackPresentation.TryDescribe(Make(typeof(ThunderArmorPower), 3, null, mutable: false), out _), "canonical early return");
                Need(!PowerStackPresentation.TryDescribe(Make(typeof(StrengthPower), 3, owner), out _), "foreign/native power remains outside custom projection");
            }
            {
                var owner = Owner(); var a = Make(typeof(ThunderArmorPower), 999999999, owner);
                Make(typeof(ThunderArmorPower), 999999999, owner); Make(typeof(ThunderArmorPower), 999999999, owner);
                Need(Describe(a).AmountText == "2999999997", "sum uses long, does not clamp or overflow actual members");
                var domain = Make(typeof(DomainPower), 2, owner);
                AccessTools.Field(typeof(PowerModel), "_amount").SetValue(domain, CardResolutionDuration.Permanent);
                var result = Describe(domain);
                Need(result.AmountText == "本战" && result.Description.StartsWith("领域持续本战。") && !result.Description.Contains("剩余"), "permanent domain omits meaningless counter and keeps full lifetime text");
                var tempOwner = Owner(); var temp = Make(typeof(VolibearChargeStrengthPower), -3, tempOwner);
                Need(Describe(temp).AmountText == "-3" && Describe(temp).Description == "本回合失去3力量，回合结束时恢复3力量。", "temporary strength negative reversal remains correct");
            }
            Need(ownerReads == 0 && hoverReads == 0, "no Owner getter or HoverTips recursion on any path");
            Console.WriteLine($"POWER_STACK_PRESENTATION_PASS models=26 checks={checks} readonly=true native-model-fixtures=true gameplay=NOT_RUN");
        }
        finally { harmony.UnpatchAll(harmony.Id); Hidden.Clear(); }
    }
}
