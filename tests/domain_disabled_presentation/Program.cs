using System.Reflection;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Content;
using Volibear.Core;
using Volibear.Presentation;

static class Program
{
    static int checks;
    static void Need(bool ok, string message) { checks++; if (!ok) throw new Exception(message); }
    static void Set(object target, string field, object? value)
    {
        for (Type? t = target.GetType(); t is not null; t = t.BaseType)
            if (t.GetField(field, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is { } f)
            { f.SetValue(target, value); return; }
        throw new MissingFieldException(field);
    }
    static void InitLoc()
    {
        var manager = (LocManager)RuntimeHelpers.GetUninitializedObject(typeof(LocManager));
        AccessTools.Method(typeof(LocManager), "LoadLocFormatters").Invoke(manager, null);
        var tables = VolibearLoc.Tables.ToDictionary(p => p.Key, p => new LocTable(p.Key, new Dictionary<string,string>(p.Value), null!));
        tables["powers"] = new("powers", new() {
            ["TEST.title"] = "测试状态", ["TEST.description"] = "原始效果" }, null!);
        Set(manager, "_tables", tables);
        AccessTools.Field(typeof(LocManager), "<Instance>k__BackingField").SetValue(null, manager);
    }
    static T Power<T>(Creature owner) where T : PowerModel, new()
    {
        var power = new T();
        Set(power, "<Id>k__BackingField", new ModelId("powers", "TEST"));
        Set(power, "<IsMutable>k__BackingField", true);
        Set(power, "_owner", owner);
        return power;
    }
    static Creature MakeCreature(MonsterModel? monster = null)
    {
        var result = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        Set(result, "_powers", new List<PowerModel>());
        Set(result, "<Monster>k__BackingField", monster);
        return result;
    }
    static bool NoIcon(ref Texture2D __result) { __result = null!; return false; }
    static bool NoEnergyPool(ref string __result) { __result = "energy"; return false; }
    static void Main()
    {
        InitLoc();
        // Icon IO only is bypassed: no engine process or resource loading in this suite.
        var fixture = new Harmony("Volibear.Tests.DisabledIcons");
        fixture.Patch(AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.Icon)), prefix: new(typeof(Program), nameof(NoIcon)));
        // Cosmetic energy sprite prefix normally needs the whole registered ModelDb.
        fixture.Patch(AccessTools.Method(typeof(MegaCrit.Sts2.Core.Helpers.EnergyIconHelper), "GetPrefix", [typeof(AbstractModel)]), prefix: new(typeof(Program), nameof(NoEnergyPool)));
        PowerPresentationDisabled.Install();
        PowerPresentationDisabled.Install();
        foreach (var method in new MethodBase[] {
            AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.HoverTips)),
            AccessTools.PropertyGetter(typeof(Creature), nameof(Creature.HoverTips)),
            AccessTools.DeclaredMethod(typeof(NPower), nameof(NPower._Ready)),
            AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)),
            AccessTools.DeclaredMethod(typeof(NCreature), nameof(NCreature._Ready)) })
            Need(Harmony.GetPatchInfo(method)!.Postfixes.Count(p => p.owner == "Volibear.PowerPresentationDisabled") == 1, "Native entry installed exactly once: " + method);
        Need(!PowerPresentationDisabled.IsSuppressed(new WeakPower()), "Canonical never reads mutable Owner");
        var player = MakeCreature();
        var weak = Power<WeakPower>(player);
        // Native NPower has engine-backed static StringNames: inspect its exact ABI here;
        // executable tree/unbound/late/rebind/exit paths live in disabled_visual_lifecycle.
        var modelField = AccessTools.DeclaredField(typeof(NPower), "_model");
        Need(modelField is { IsPrivate: true } && modelField.FieldType == typeof(PowerModel),
            "Pinned NPower nullable backing-field ABI matches the read-only visual adapter");
        Need(PatchProcessor.GetOriginalInstructions(AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)))
            .Any(i => i.opcode == System.Reflection.Emit.OpCodes.Stfld && Equals(i.operand, modelField)),
            "Pinned Model setter commits the same field observed by the immediate postfix");
        var original = new HoverTip(new LocString("powers", "TEST.title"), "original") { Id = weak.Id.ToString() };
        Need(PowerPresentationDisabled.PowerTips(weak, [original]).Cast<HoverTip>().Single().Description == "original", "Inactive projection preserves native text");
        DomainSelfDebuffEffects.Muted.Add(weak);
        Need(weak.HoverTips.Cast<HoverTip>().First().Description.Contains("已被领域禁用"), "Actual patched native PowerModel.HoverTips entry annotates self debuff");
        var disabled = PowerPresentationDisabled.PowerTips(weak, [original]).Cast<HoverTip>().Single();
        Need(disabled.Description.Contains("已被领域禁用") && disabled.Description.StartsWith("original"), "Self debuff visible native tip annotated without replacement loss");
        Need(disabled.Id == original.Id, "Native tip identity preserved");
        Need(PowerPresentationDisabled.PowerTips(weak, []).Cast<HoverTip>().Single().Description.Contains("已被领域禁用"), "Hidden power exposed without icon");
        DomainSelfDebuffEffects.Muted.Clear();
        Need(PowerPresentationDisabled.PowerTips(weak, [original]).Cast<HoverTip>().Single().Description == "original", "Exit restores native description on next query");
        var enemy = MakeCreature(new TheInsatiable());
        var thorns = Power<ThornsPower>(enemy);
        var strength = Power<StrengthPower>(enemy);
        var vulnerable = Power<VulnerablePower>(enemy);
        DomainEnemyEffects.Active.Add(enemy);
        Need(PowerPresentationDisabled.IsSuppressed(thorns), "Known beneficial contribution disabled");
        Need(!PowerPresentationDisabled.IsSuppressed(strength) && !PowerPresentationDisabled.IsSuppressed(vulnerable), "Direct stats and enemy debuffs retained");
        var tips = PowerPresentationDisabled.CreatureTips(enemy, []).Cast<HoverTip>().ToArray();
        Need(tips.Any(t => t.Id == "VOLIBEAR-ENEMY-SANDPIT" && t.Description.Contains("已被领域禁用")), "No-icon sandworm count/movement/kill reachable from creature hover");
        Need(tips.Any(t => t.Id == "VOLIBEAR-DISABLED-ENEMY"), "General action-body suppression visible");
        DomainEnemyEffects.Active.Clear();
        tips = PowerPresentationDisabled.CreatureTips(enemy, []).Cast<HoverTip>().ToArray();
        Need(tips.Length == 1 && !tips[0].Description.Contains("已被领域禁用"), "Inactive creature keeps explanation without false disabled claim");
        foreach (var entry in MechanicGlossary.EnemyEntries)
        foreach (var name in entry.Monsters)
            Need(typeof(MonsterModel).Assembly.GetType("MegaCrit.Sts2.Core.Models.Monsters." + name) is not null, "No guessed monster names: " + name);
        var ordinary = MakeCreature();
        DomainEnemyEffects.Active.Add(ordinary);
        Need(!PowerPresentationDisabled.IsCreatureSuppressed(ordinary) && !PowerPresentationDisabled.CreatureTips(ordinary, []).Any(), "No blanket badge or false claim for ordinary/unsupported enemy");
        var hopper = MakeCreature(new ThievingHopper());
        DomainEnemyEffects.Active.Add(hopper);
        var hopperTips = PowerPresentationDisabled.CreatureTips(hopper, []).ToArray();
        Need(hopperTips.Any(t => t.Id == "VOLIBEAR-ENEMY-CARD_THEFT") && !hopperTips.Any(t => t.Id == "VOLIBEAR-ENEMY-FLEE"), "Hopper theft does not falsely claim escape cancellation");
        Need(!PowerPresentationDisabled.IsSuppressed(Power<EscapeArtistPower>(hopper)), "Unsupported escape Power remains visibly enabled");
        foreach (var name in PowerPresentationDisabled.EnemyPowers)
            Need(typeof(PowerModel).Assembly.GetType("MegaCrit.Sts2.Core.Models.Powers." + name) is not null, "Supported contribution uses real pinned native Power: " + name);
        Need(MechanicGlossary.SuppressedContributions.Single(e => e.Words.Contains("PlatingPower")).Description.Contains("被动"), "Mixed power annotation names only suppressed contribution");
        var knowledge = MakeCreature(new KnowledgeDemon());
        DomainEnemyEffects.Active.Add(knowledge);
        Need(PowerPresentationDisabled.CreatureTips(knowledge, []).Cast<HoverTip>().Any(t => t.Id == "VOLIBEAR-ENEMY-KNOWLEDGE" && t.Description.Contains("减少抽牌") && !t.Description.Contains("虚无")), "Knowledge Demon choices are not knight penalties");
        foreach (var monster in new MonsterModel[] { new MagiKnight(), new SpectralKnight() })
        {
            var knight = MakeCreature(monster);
            DomainEnemyEffects.Active.Add(knight);
            Need(PowerPresentationDisabled.CreatureTips(knight, []).Cast<HoverTip>().Any(t => t.Id == "VOLIBEAR-ENEMY-KNIGHTS" && t.Description.Contains("升级") && t.Description.Contains("虚无") && t.Description.Contains("已被领域禁用")), "Native knights expose their own disabled upgrade/ethereal mechanism");
        }
        Console.WriteLine($"DOMAIN_DISABLED_PRESENTATION_PASS checks={checks} native-entry-patches=5 gameplay-predicates=TEST-DOUBLES Godot-render=NOT_RUN");
    }
}
