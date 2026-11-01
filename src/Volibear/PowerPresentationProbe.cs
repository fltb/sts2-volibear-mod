using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;
using Volibear.Content;

namespace Volibear;

/// <summary>Native mutable tooltip/resource probe, NOT visual recognition or power-mechanic
/// acceptance. ApplyInternal supplies a real native owner and instance without invoking
/// deployment effects. It must never run in a normal session or alongside another probe.</summary>
internal static class PowerPresentationProbe
{
    private static bool started;
    internal static void Install()
    {
        if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_POWER_PRESENTATION") != "1") return;
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState combat)
    {
        if (started) return;
        started = true;
        CombatManager.Instance.TurnStarted -= Start;
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        try
        {
            if (string.IsNullOrWhiteSpace(token) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("A run token and real non-TestMode combat are required.");
            var owner = combat.Players.Single().Creature;
            var before = owner.Powers.ToArray();
            var rows = new List<object>();
            foreach (var canonical in Models())
            {
                bool fixedValue = canonical is NextEngageDiscount or BiteMarkPower or LingeringStormPower or ThunderAftershockPower or ImmovableBodyPower;
                var power = canonical.ToMutable();
                try
                {
                    // Native instance/owner registration only: deliberately NOT PowerCmd.Apply,
                    // which would deploy gameplay responders and require real card sources.
                    power.ApplyInternal(owner, fixedValue ? 1 : 2, silent: true);
                    Record(power);
                    if (!fixedValue) { power.SetAmount(5, silent: true); Record(power); }
                    if (power is DomainPower) { power.SetAmount(CardResolutionDuration.Permanent, silent: true); Record(power); }
                }
                finally { if (owner.Powers.Contains(power)) power.RemoveInternal(); }
            }
            if (!before.SequenceEqual(owner.Powers)) throw new InvalidOperationException("Probe left power instances behind.");
            GD.Print("[Volibear] POWER_PRESENTATION_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, acceptance = "native-tooltip/resource-not-visual-recognition",
                fixture = "native-ToMutable-ApplyInternal-SetAmount-HoverTips-RemoveInternal",
                testMode = false, models = 25, rows
            }));
            ((SceneTree)Engine.GetMainLoop()).Quit();

            void Record(PowerModel power)
            {
                var tip = power.HoverTips.OfType<HoverTip>().First();
                var icon = power.Icon;
                var big = power.BigIcon;
                if (icon is null || big is null) throw new InvalidOperationException("Missing native power texture");
                rows.Add(new { model = power.GetType().Name, mutable = power.IsMutable, amount = power.Amount,
                    displayAmount = power.DisplayAmount, title = tip.Title, description = tip.Description, smart = tip.IsSmart,
                    iconPath = power.PackedIconPath, bigIconPath = power.ResolvedBigIconPath,
                    width = icon.GetWidth(), height = icon.GetHeight(), bigWidth = big.GetWidth(), bigHeight = big.GetHeight() });
            }
        }
        catch (Exception exception)
        {
            GD.PrintErr("[Volibear] POWER_PRESENTATION_FAILED " + token + " " + exception);
            ((SceneTree)Engine.GetMainLoop()).Quit(1);
        }
    }
    private static IEnumerable<PowerModel> Models() =>
    [
        ModelDb.Power<NextAttackDiscount>(), ModelDb.Power<NextEngageDiscount>(),
        ModelDb.Power<NextAttackReplayPower>(), ModelDb.Power<NextAttackTrainingPower>(),
        ModelDb.Power<UnifyPower>(), ModelDb.Power<PrimalThunderPower>(), ModelDb.Power<ThunderGuardPower>(), ModelDb.Power<BiteMarkPower>(),
        ModelDb.Power<StormConductionPower>(), ModelDb.Power<StandingPower>(), ModelDb.Power<BattleScarsPower>(),
        ModelDb.Power<LingeringStormPower>(), ModelDb.Power<ThunderAftershockPower>(), ModelDb.Power<PreyStillStandsPower>(),
        ModelDb.Power<GrowingFuryPower>(), ModelDb.Power<WelcomeThunderPower>(), ModelDb.Power<ThunderArmorPower>(),
        ModelDb.Power<ImmovableBodyPower>(), ModelDb.Power<BattleBodyPower>(), ModelDb.Power<ThunderPoolPower>(),
        ModelDb.Power<BearSpiritPower>(), ModelDb.Power<WildernessPower>(), ModelDb.Power<StormChargePower>(),
        ModelDb.Power<DomainPower>(), ModelDb.Power<EndlessHuntPower>()
    ];
}
