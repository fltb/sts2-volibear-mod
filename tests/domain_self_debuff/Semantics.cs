using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

internal static class Semantics
{
    private static bool active;
    private static int checks;
    private const BindingFlags F = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
    private static bool Protect(Creature creature, ref bool __result) { __result = active && creature.IsPlayer; return false; }
    private static void Need(bool value, string label) { checks++; if (!value) throw new Exception(label); }
    private static object? Call(Type owner, string name, params object?[] args) => AccessTools.Method(owner, name).Invoke(null, args);
    private static bool Upgrade(CardModel card) { AccessTools.Field(typeof(CardModel), "_currentUpgradeLevel").SetValue(card, card.CurrentUpgradeLevel + 1); return false; }
    private static bool Downgrade(CardModel card) { AccessTools.Field(typeof(CardModel), "_currentUpgradeLevel").SetValue(card, 0); return false; }
    public static void Run()
    {
        var fixture = new Harmony("Volibear.Tests.DebuffAvailabilityFixture");
        fixture.Patch(AccessTools.Method(typeof(DomainEnemyEffects), "ProtectsPlayer"), prefix: new HarmonyMethod(typeof(Semantics), nameof(Protect)));
        var player = (Player)RuntimeHelpers.GetUninitializedObject(typeof(Player));
        AccessTools.Field(typeof(Player), "_relics").SetValue(player, new List<RelicModel>());
        var creature = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
        AccessTools.Field(typeof(Creature), "<Player>k__BackingField").SetValue(creature, player);
        AccessTools.Field(typeof(Creature), "_powers").SetValue(creature, new List<PowerModel>());
        T Power<T>(int amount = 2) where T : PowerModel
        {
            var power = (T)RuntimeHelpers.GetUninitializedObject(typeof(T));
            typeof(AbstractModel).GetProperty("IsMutable", F)!.SetValue(power, true);
            typeof(PowerModel).GetProperty("Owner", F)!.SetValue(power, creature);
            AccessTools.Field(typeof(PowerModel), "_amount").SetValue(power, amount);
            return power;
        }
        var noDraw = Power<NoDrawPower>();
        var mindRot = Power<MindRotPower>();
        var waste = Power<WasteAwayPower>();
        var noEnergy = Power<NoEnergyGainPower>();
        var weak = Power<WeakPower>();
        var frail = Power<FrailPower>();
        var sloth = Power<SlothPower>();
        var card = (CardModel)RuntimeHelpers.GetUninitializedObject(typeof(Volibear.Content.Volibear_B01));
        typeof(AbstractModel).GetProperty("IsMutable", F)!.SetValue(card, true);
        typeof(CardModel).GetProperty("Owner", F)!.SetValue(card, player);
        try
        {
            foreach (bool domain in new[] { false, true, false })
            {
                active = domain;
                Need(DomainSelfDebuffEffects.IsSuppressed(mindRot) == domain, "existing power enters/exits suppression without source receipt");
                Need((decimal)Call(typeof(DomainSelfDebuffEffects), "DrawCount", mindRot, player, 5m)! == (domain ? 5m : 3m), "MindRot restores draw and resumes after exit");
                Need((decimal)Call(typeof(DomainSelfDebuffEffects), "MaxEnergy", waste, player, 3m)! == (domain ? 3m : 1m), "WasteAway restores max energy and resumes");
                Need((decimal)Call(typeof(DomainSelfDebuffEffects), "Energy", noEnergy, player, 2m)! == (domain ? 2m : 0m), "NoEnergy restores gain");
                Need((bool)Call(typeof(DomainSelfDebuffEffects), "DrawAllowed", noDraw, player, false)! == domain, "NoDraw restores draw capability");
                Need((decimal)Call(typeof(DomainPlayerDebuffContributions), "DamageMultiplier", weak, creature, 10m, ValueProp.Move, creature, card)! == (domain ? 1m : .75m), "Weak restores damage multiplier");
                Need((decimal)Call(typeof(DomainPlayerDebuffContributions), "BlockMultiplier", frail, creature, 10m, ValueProp.Move, card, null)! == (domain ? 1m : .75m), "Frail restores block multiplier");
                Need(mindRot.Amount == 2 && waste.Amount == 2 && weak.Amount == 2, "native amounts never overwritten");
            }
            active = true;
            var newDebuff = Power<DisintegrationPower>(7);
            Need(DomainSelfDebuffEffects.IsSuppressed(newDebuff), "new player-applied penalty suppressed");
            var damage = (Task<IEnumerable<DamageResult>>)Call(typeof(DomainSelfDebuffEffects), "Damage", null, creature, 7m, ValueProp.Unpowered, null, null, newDebuff)!;
            Need(!damage.GetAwaiter().GetResult().Any(), "Disintegration contribution suppressed before command");
            Need(DomainPlayerDebuffContributions.EffectiveAmount(Power<ChainsOfBindingPower>()) == 0, "preexisting Chains removes draw-affliction contribution");
            Need(DomainPlayerDebuffContributions.EffectiveAmount(Power<ConstrictPower>()) == 0, "preexisting Constrict removes damage contribution");
            Need(DomainPlayerDebuffContributions.ShouldCancel(weak, creature, 2, null, null, null!) == false, "new weak commits with native lifetime");
            var buff = Power<StrengthPower>(4);
            Need(!DomainSelfDebuffEffects.IsSuppressed(buff), "positive player buff retained");
            Need(!DomainSelfDebuffEffects.IsSuppressed(Power<ShriekPower>()), "monster-only Shriek is not falsely marked as suppressed on player");
            Need(!DomainSelfDebuffEffects.IsSuppressed(Power<PlowPower>()), "monster-only Plow is not falsely marked as suppressed on player");
            // Exercise the production loan ledger with deterministic card-command seams;
            // actual native command/scene behavior is covered by the isolated knights probe.
            fixture.Patch(typeof(CardCmd).GetMethods().Single(m => m.Name == nameof(CardCmd.Upgrade) && m.GetParameters()[0].ParameterType == typeof(CardModel)), prefix: new HarmonyMethod(typeof(Semantics), nameof(Upgrade)));
            fixture.Patch(AccessTools.Method(typeof(CardCmd), nameof(CardCmd.Downgrade)), prefix: new HarmonyMethod(typeof(Semantics), nameof(Downgrade)));
            var dampen = Power<DampenPower>();
            var dataType = typeof(DampenPower).GetNestedType("Data", F)!;
            var data = Activator.CreateInstance(dataType, true)!;
            AccessTools.Field(typeof(PowerModel), "_internalData").SetValue(dampen, data);
            var ledger = (Dictionary<CardModel, int>)dataType.GetField("downgradedCardsToOldUpgradeLevels")!.GetValue(data)!;
            ledger.Add(card, 1);
            DomainDampenRestoration.Refresh(dampen);
            Need(card.CurrentUpgradeLevel == 1 && ledger.Count == 1, "Dampen entry borrows native upgrade without erasing debt");
            DomainDampenRestoration.Refresh(dampen);
            Need(card.CurrentUpgradeLevel == 1, "multiple domains do not duplicate loan");
            active = false; DomainDampenRestoration.Refresh(dampen);
            Need(card.CurrentUpgradeLevel == 0 && ledger[card] == 1, "Dampen exit returns only loan and retains native debt");
            active = true; DomainDampenRestoration.Refresh(dampen);
            Call(typeof(DomainDampenRestoration), "Removing", dampen);
            dampen.AfterRemoved(creature).GetAwaiter().GetResult();
            Need(card.CurrentUpgradeLevel == 1, "native removal restores exactly once while domain active");
            active = false; DomainDampenRestoration.Refresh(dampen);
            Need(card.CurrentUpgradeLevel == 1, "after native removal domain exit preserves restored upgrade");
            Console.WriteLine("SELF_DEBUFF_SEMANTICS_PASS checks=" + checks);
        }
        finally { fixture.UnpatchAll(fixture.Id); active = false; }
    }
}
