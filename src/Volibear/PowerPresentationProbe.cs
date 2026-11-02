using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using System.Reflection;
using System.Diagnostics;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;
using Volibear.Content;

namespace Volibear;

/// <summary>Native tooltip/resources plus original NPower placeholder lifecycle; not
/// screenshot recognition. The 25-model text section uses ApplyInternal only; the
/// isolated UI section uses real PowerCmd and Model setters after that section restores
/// its powers. Never run in a normal session or alongside another probe.</summary>
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
        _ = Run(combat);
    }
    private static async Task Run(CombatState combat)
    {
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        try
        {
            if (string.IsNullOrWhiteSpace(token) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("A run token and real non-TestMode combat are required.");
            await NativeAcceptanceRunHost.WaitForQuiet(combat, 1);
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
            await NativeAcceptanceRunHost.WaitForQuiet(combat, 1);
            var uiLifecycle = await UiLifecycle(combat);
            GD.Print("[Volibear] POWER_PRESENTATION_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, acceptance = "native-tooltip/resource-not-visual-recognition",
                fixture = "native-ToMutable-ApplyInternal-SetAmount-HoverTips-RemoveInternal",
                testMode = false, models = 25, rows, uiLifecycle
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit();
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
    private static async Task<object> UiLifecycle(CombatState combat)
    {
        const string scenePath = "res://scenes/combat/multiplayer_player_intent.tscn";
        const string overlayName = "VolibearDomainDisabled";
        var tree = (SceneTree)Engine.GetMainLoop();
        var owner = combat.Players.Single().Creature;
        var before = owner.Powers.ToArray();
        if (owner.GetPower<WeakPower>() is not null || owner.GetPower<StrengthPower>() is not null || owner.GetPower<DomainPower>() is not null)
            throw new InvalidOperationException("UI lifecycle needs fresh Weak/Strength/Domain slots");
        var stages = new List<object>();
        var clock = Stopwatch.StartNew();
        Node? source = null; Control? fixture = null; NPower? icon = null;
        WeakPower? weak = null; StrengthPower? strength = null; DomainPower? domain = null;
        var choices = new ThrowingPlayerChoiceContext();
        var modelField = typeof(NPower).GetField("_model", BindingFlags.NonPublic | BindingFlags.Instance)!;
        void Need(bool ok, string message) { if (!ok) throw new InvalidOperationException("NPower lifecycle: " + message); }
        async Task Until(Func<bool> condition)
        {
            while (!condition())
            {
                Need(clock.Elapsed.TotalSeconds < 30, "bounded native UI transition timed out");
                await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            }
        }
        Control Overlay() => icon!.GetNode<Control>(overlayName);
        void Record(string phase, PowerModel? expected, bool visible, bool inside, bool active, ulong? setterFrame = null)
        {
            var model = (PowerModel?)modelField.GetValue(icon);
            var overlays = icon!.GetChildren().OfType<Control>().Where(n => n.Name == overlayName).ToArray();
            var overlay = overlays.Single();
            bool? sameFrame = setterFrame.HasValue ? Engine.GetProcessFrames() == setterFrame.Value : null;
            stages.Add(new { phase, nodeId = icon.GetInstanceId(), boundModel = model?.GetType().Name,
                ready = icon.IsNodeReady(), insideTree = icon.IsInsideTree(), overlays = overlays.Length,
                children = overlay.GetChildCount(), visible = overlay.Visible, visibleInTree = overlay.IsVisibleInTree(),
                domain = DomainPower.IsActive(owner), immediate = setterFrame.HasValue, setterSameFrame = sameFrame });
            Need(ReferenceEquals(model, expected) && icon.IsInsideTree() == inside && (!inside || icon.IsNodeReady()) &&
                overlays.Length == 1 && overlay.GetChildCount() == 3 && overlay.Visible == visible &&
                overlay.IsVisibleInTree() == (visible && inside) && DomainPower.IsActive(owner) == active && sameFrame is not false, phase);
        }
        void Bind(string phase, PowerModel model, bool visible)
        {
            var frame = Engine.GetProcessFrames();
            icon!.Model = model; // Exactly the native intent handler's late/rebinding path.
            Record(phase, model, visible, true, DomainPower.IsActive(owner), frame);
        }
        try
        {
            // Extract the very node used by the native multiplayer intent scene BEFORE
            // its handler enters the tree; no network peer, fake node, or manual Ready.
            source = ResourceLoader.Load<PackedScene>(scenePath).Instantiate();
            icon = source.GetNode<NPower>("%PowerIntent");
            Need(modelField.GetValue(icon) is null && !icon.IsInsideTree(), "native placeholder must start unbound/off-tree");
            icon.GetParent().RemoveChild(icon);
            source.Free(); source = null;
            fixture = new Control { Name = "PowerPresentationLifecycleFixture", Position = new Vector2(1100, 100), MouseFilter = Control.MouseFilterEnum.Ignore };
            NCombatRoom.Instance!.AddChild(fixture);
            icon.Visible = true;
            fixture.AddChild(icon);
            await Until(() => icon.IsNodeReady());
            Record("unbound-ready", null, false, true, false);
            weak = await PowerCmd.Apply<WeakPower>(choices, owner, 2, owner, null);
            strength = await PowerCmd.Apply<StrengthPower>(choices, owner, 2, owner, null);
            Need(weak is not null && strength is not null, "real mutable powers applied");
            Bind("late-bound-off", weak!, false);
            domain = await DomainPower.Open(choices, owner, 5);
            await Until(() => Overlay().Visible);
            Record("domain-on", weak, true, true, true);
            Bind("rebound-ordinary", strength!, false);
            Bind("rebound-debuff", weak!, true);
            await PowerCmd.Remove(domain); domain = null;
            await Until(() => !Overlay().Visible);
            Record("domain-off", weak, false, true, false);
            fixture.RemoveChild(icon);
            Record("tree-detached", weak, false, false, false);
            fixture.AddChild(icon);
            await Until(() => icon.IsNodeReady());
            Record("tree-reattached", weak, false, true, false);
            domain = await DomainPower.Open(choices, owner, 5);
            await Until(() => Overlay().Visible);
            Record("domain-reentered", weak, true, true, true);
            icon.QueueFree();
            await Until(() => !GodotObject.IsInstanceValid(icon));
            // Exercise the tracker after release too; a stale subscription must surface
            // through the existing runtime-error gate rather than being swallowed.
            await PowerCmd.Remove(domain); domain = null;
            await PowerCmd.Remove(weak); weak = null;
            await PowerCmd.Remove(strength); strength = null;
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
            bool restored = before.SequenceEqual(owner.Powers);
            Need(restored && clock.Elapsed.TotalSeconds < 30, "fixture powers restored within budget");
            return new { fixture = "native-multiplayer-power-intent-extracted", sourceScene = scenePath,
                nodeType = typeof(NPower).FullName, stages, freed = !GodotObject.IsInstanceValid(icon), powersRestored = restored };
        }
        catch
        {
            GD.Print("[Volibear] POWER_UI_LIFECYCLE_PARTIAL " + JsonSerializer.Serialize(stages));
            throw;
        }
        finally
        {
            if (fixture is not null && GodotObject.IsInstanceValid(fixture)) fixture.Free();
            if (icon is not null && GodotObject.IsInstanceValid(icon)) icon.Free();
            if (source is not null && GodotObject.IsInstanceValid(source)) source.Free();
            if (domain is not null && owner.Powers.Contains(domain)) await PowerCmd.Remove(domain);
            if (weak is not null && owner.Powers.Contains(weak)) await PowerCmd.Remove(weak);
            if (strength is not null && owner.Powers.Contains(strength)) await PowerCmd.Remove(strength);
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
