using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Content;
using Volibear.Core;
using Volibear.Presentation;

namespace Volibear;

/// <summary>Developer-only real native UI projection matrix, plus two paid U34 plays.
/// No synthetic input. Matrix powers use native ApplyInternal only (no gameplay hooks);
/// the separate armor check goes through paid PlayCardAction and actual lightning.</summary>
internal static class PowerStackUiProbe
{
    private static readonly FieldInfo ModelField = typeof(NPower).GetField("_model", BindingFlags.NonPublic | BindingFlags.Instance)!;
    private static SceneTree Tree => (SceneTree)Engine.GetMainLoop();
    private static async Task Frame() => await Tree.ToSignal(Tree, SceneTree.SignalName.ProcessFrame);
    private static void Need(bool ok, string message) { if (!ok) throw new InvalidOperationException("Power stack UI: " + message); }
    private static IEnumerable<Node> Descendants(Node root)
    {
        foreach (var child in root.GetChildren())
        {
            yield return child;
            foreach (var descendant in Descendants(child)) yield return descendant;
        }
    }
    internal static async Task<object> Run(CombatState combat, IEnumerable<PowerModel> models)
    {
        var player = combat.Players.Single();
        var owner = player.Creature;
        var before = owner.Powers.ToArray();
        var view = NCombatRoom.Instance!.GetCreatureNode(owner)!;
        var container = Descendants(view).OfType<NPowerContainer>().Single();
        var samples = new List<object>();
        var payments = new List<object>();
        var introduced = new List<PowerModel>();
        var choices = new ThrowingPlayerChoiceContext();
        string directory = Path.GetFullPath(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_POWER_STACK_OUTPUT")
            ?? throw new InvalidOperationException("Power stack screenshot output missing"));
        Directory.CreateDirectory(directory);
        NPower[] Nodes(Type type) => container.GetChildren().OfType<NPower>()
            .Where(n => !n.IsQueuedForDeletion() && ModelField.GetValue(n) is PowerModel p && p.GetType() == type).ToArray();
        object Record(string phase, Type type)
        {
            var powers = owner.Powers.Where(p => p.GetType() == type).ToArray();
            var nodes = Nodes(type);
            var visible = nodes.Where(n => n.Visible && n.IsVisibleInTree()).ToArray();
            Need(visible.Length == (powers.Length > 0 ? 1 : 0), phase + " must have exactly one visible icon per remaining type");
            Need(nodes.Length == powers.Length, phase + " must retain one underlying native node/model per instance");
            var tips = visible.Length == 0 ? Array.Empty<HoverTip>() : PowerStackVisual.DisplayedTips(visible[0]).OfType<HoverTip>().ToArray();
            var row = new { phase, model = type.Name, amounts = powers.Select(p => p.Amount).ToArray(),
                nodeCount = nodes.Length, visibleCount = visible.Length,
                label = visible.Length == 0 ? "" : visible[0].GetNode("%AmountLabel").Get("text").AsString(),
                visibleNode = visible.Length == 0 ? 0UL : visible[0].GetInstanceId(),
                tips = tips.Select(t => t.Description).ToArray(), tipTitles = tips.Select(t => t.Title).ToArray() };
            samples.Add(row);
            return row;
        }
        async Task Capture(string name, PowerModel power)
        {
            // Let native gain/remove floating text and the turn banner finish; do not
            // suppress or edit VFX just to make the evidence screenshot look cleaner.
            await Tree.ToSignal(Tree.CreateTimer(3.0), SceneTreeTimer.SignalName.Timeout);
            // Same native rendering outlet as pointer hover, without injecting input.
            view.ShowHoverTips(power.HoverTips);
            await Frame();
            await Tree.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var image = Tree.Root.GetTexture().GetImage();
            Need(image.SavePng(Path.Combine(directory, name + ".png")) == Error.Ok, "screenshot write");
            view.HideHoverTips();
        }
        async Task Play(CardModel card)
        {
            await CardPileCmd.Add(card, PileType.Hand);
            var energyBefore = player.PlayerCombatState!.Energy;
            var action = new PlayCardAction(card, card.TargetType == TargetType.AnyEnemy ? combat.Enemies.First(e => e.IsHittable) : null);
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
            var clock = Stopwatch.StartNew();
            while (!action.CompletionTask.IsCompleted)
            {
                Need(clock.Elapsed.TotalSeconds < 30, "paid action bounded timeout");
                await Frame();
            }
            await action.CompletionTask;
            if (action.Exception is not null) throw new InvalidOperationException("Power stack paid action fault", action.Exception);
            Need(action.State.ToString() == "Finished", "action finished");
            payments.Add(new { model = card.GetType().Name, upgraded = card.IsUpgraded, before = energyBefore,
                after = player.PlayerCombatState.Energy, state = action.State.ToString(), type = action.GetType().Name });
            await Frame();
        }
        try
        {
            Need(!owner.Powers.OfType<ThunderArmorPower>().Any(), "fresh armor slot");
            await PlayerCmd.SetEnergy(10, player);
            var baseArmor = combat.CreateCard<Volibear_U34>(player);
            var plusArmor = combat.CreateCard<Volibear_U34>(player);
            CardCmd.Upgrade(plusArmor);
            await Play(baseArmor);
            Record("armor-paid-base", typeof(ThunderArmorPower));
            await Play(plusArmor);
            var armor = owner.Powers.OfType<ThunderArmorPower>().ToArray();
            introduced.AddRange(armor);
            Need(armor.Select(p => p.Amount).SequenceEqual(new[] { 3, 4 }), "two paid armor instances retained");
            Record("armor-paid-mixed", typeof(ThunderArmorPower));
            await Capture("armor-mixed", armor[0]);
            int blockBefore = owner.Block;
            int lightningBefore = LightningBatches.GetTurnCount(owner);
            int historyBefore = CombatManager.Instance.History.Entries.Count();
            await Play(combat.CreateCard<Volibear_C24>(player));
            var blockGains = CombatManager.Instance.History.Entries.Skip(historyBefore).OfType<BlockGainedEntry>()
                .Where(entry => ReferenceEquals(entry.Receiver, owner)).Select(entry => entry.Amount).ToArray();
            Need(blockGains.SequenceEqual(new[] { 3, 4 }), "two independent native block gains retained");
            int blockAfter = owner.Block;
            int lightningAfter = LightningBatches.GetTurnCount(owner);
            Need(blockAfter - blockBefore == 7 && lightningAfter - lightningBefore == 1, "mixed armor grants 3+4 on one actual lightning batch");
            Record("armor-after-lightning", typeof(ThunderArmorPower));
            await PowerCmd.Remove(armor[0]);
            await Frame();
            Record("armor-representative-removed", typeof(ThunderArmorPower));
            var parent = container.GetParent();
            int index = container.GetIndex();
            parent.RemoveChild(container);
            parent.AddChild(container);
            parent.MoveChild(container, index);
            await Frame();
            Record("armor-tree-reentered", typeof(ThunderArmorPower));
            await PowerCmd.ModifyAmount(choices, armor[1], 1, owner, null);
            await Frame();
            Record("armor-amount-changed", typeof(ThunderArmorPower));
            await PowerCmd.Remove(armor[1]);
            await Frame();
            Record("armor-last-removed", typeof(ThunderArmorPower));
            introduced.Clear();

            foreach (var canonical in models)
            {
                var active = new List<PowerModel>();
                bool flag = canonical is NextEngageDiscount or BiteMarkPower or ImmovableBodyPower;
                bool fixedResponse = canonical is ThunderAftershockPower or LingeringStormPower;
                try
                {
                    var power = canonical.ToMutable();
                    power.ApplyInternal(owner, flag || fixedResponse ? 1 : 2, silent: true);
                    active.Add(power); introduced.Add(power);
                    await Frame();
                    Record("matrix-single", canonical.GetType());
                    if (canonical.InstanceType == PowerInstanceType.Instanced)
                    {
                        var second = canonical.ToMutable();
                        second.ApplyInternal(owner, fixedResponse ? 1 : 5, silent: true);
                        active.Add(second); introduced.Add(second);
                    }
                    else if (!flag) power.SetAmount(5, silent: true);
                    await Frame();
                    Record("matrix-updated", canonical.GetType());
                    if (power is StormConductionPower) await Capture("multiple-lightning", power);
                    if (power is ImmovableBodyPower) await Capture("nonstacking", power);
                    if (power is DomainPower)
                    {
                        power.SetAmount(CardResolutionDuration.Permanent, silent: true);
                        await Frame();
                        Record("domain-permanent", canonical.GetType());
                        await Capture("domain-permanent", power);
                    }
                }
                finally
                {
                    foreach (var power in active) if (owner.Powers.Contains(power)) power.RemoveInternal();
                    introduced.Clear();
                }
                await Frame();
                Record("matrix-cleared", canonical.GetType());
            }
            Need(before.SequenceEqual(owner.Powers), "all fixture powers restored");
            return new { fixture = "native-container-matrix-and-paid-armor", samples, payments,
                blockBefore, blockAfter, blockGains, lightningBefore, lightningAfter, powersRestored = true,
                captures = new[] { "armor-mixed.png", "multiple-lightning.png", "nonstacking.png", "domain-permanent.png" } };
        }
        catch
        {
            GD.Print("[Volibear] POWER_STACK_UI_PARTIAL " + System.Text.Json.JsonSerializer.Serialize(samples));
            throw;
        }
        finally
        {
            view.HideHoverTips();
            foreach (var power in introduced) if (owner.Powers.Contains(power)) await PowerCmd.Remove(power);
        }
    }
}
