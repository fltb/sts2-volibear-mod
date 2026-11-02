using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Presentation;

static class Program
{
    static int checks;
    static void Need(bool value, string label) { checks++; if(!value) throw new Exception(label); }
    static void ModelChanged(NPower __instance) => PowerPresentationDisabledVisual.ModelChanged(__instance);
    static Control Overlay(NPower node) => node.Children.Single(c => c.Name == "VolibearDomainDisabled");
    static void Main()
    {
        // Same native setter-postfix boundary; real Harmony, tree/events are the doubles.
        new Harmony("Volibear.Tests.DisabledVisualLifecycle").Patch(
            AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)),
            postfix: new(typeof(Program), nameof(ModelChanged)));
        var tracker = CombatManager.Instance.StateTracker;
        var node = new NPower(); node.Enter();
        PowerPresentationDisabledVisual.Attach(node);
        var overlay = Overlay(node);
        Need(!overlay.Visible && node.GetterReads == 0, "Unbound Ready never invokes Model getter");
        Need(tracker.Subscribers == 1, "Unbound node retains a refresh subscription");
        PowerPresentationDisabledVisual.Attach(node);
        Need(node.Children.Count == 1 && tracker.Subscribers == 1, "Repeated attach is idempotent");
        tracker.Notify();
        Need(!overlay.Visible && node.GetterReads == 0, "State change is safe while still unbound");
        var suppressed = new PowerModel { Suppressed = true };
        node.Model = suppressed;
        Need(overlay.Visible, "Late setter immediately reveals suppression without combat event");
        var ordinary = new PowerModel();
        node.Model = ordinary;
        Need(!overlay.Visible, "Reused intent hides stale suppression immediately");
        ordinary.Suppressed = true; tracker.Notify();
        Need(overlay.Visible, "Current bound model follows combat state");
        node.Exit();
        Need(tracker.Subscribers == 0 && !overlay.Visible, "Exit removes subscription and hides overlay");
        int evaluations = PowerPresentationDisabled.Evaluations;
        tracker.Notify();
        Need(PowerPresentationDisabled.Evaluations == evaluations, "No stale callbacks after exit");
        node.Model = suppressed;
        Need(!overlay.Visible, "Off-tree setter does not revive overlay");
        var replacement = new Tracker(); CombatManager.Instance.StateTracker = replacement;
        node.Enter();
        Need(replacement.Subscribers == 1 && tracker.Subscribers == 0 && overlay.Visible,
             "Reentry resubscribes once to current tracker without another Ready");
        node.Exit();
        Need(replacement.Subscribers == 0, "Second exit releases current tracker");
        var early = new NPower { Model = suppressed };
        Need(early.Children.Count == 0, "Pre-Ready setter never constructs UI prematurely");
        early.Enter(); PowerPresentationDisabledVisual.Attach(early);
        Need(Overlay(early).Visible && replacement.Subscribers == 1, "Bound-before-Ready path remains visible");
        early.Model = new PowerModel { IsCanonical = true, Suppressed = true };
        Need(!Overlay(early).Visible, "Canonical read-only projection remains undisabled");
        early.Exit();
        Need(replacement.Subscribers == 0 && early.GetterReads == 0 && node.GetterReads == 0,
             "All lifecycle paths avoid getter and release callbacks");
        Console.WriteLine($"PASS disabled visual lifecycle {checks} checks");
    }
}
