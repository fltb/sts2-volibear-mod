using System;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace Volibear.Presentation;

/// <summary>Native UI children refreshed by the native state tracker, never a frame poll.
/// Overlays do not replace icons, change their materials, or touch gameplay state.</summary>
internal static class PowerPresentationDisabledVisual
{
    private const string OverlayName = "VolibearDomainDisabled";

    // Pinned NPower permits an unbound multiplayer intent node; its public getter throws.
    private static readonly AccessTools.FieldRef<NPower, PowerModel?> BoundModel =
        AccessTools.FieldRefAccess<NPower, PowerModel?>("_model");
    private static readonly ConditionalWeakTable<NPower, PowerBinding> PowerBindings = new();

    internal static PowerModel? ReadBoundModel(NPower power) => BoundModel(power);

    internal static void ModelChanged(NPower power)
    {
        // Create() sets Model before Ready: defer construction, not the later binding.
        if (PowerBindings.TryGetValue(power, out var binding)) binding.Refresh(null);
    }

    internal static void Attach(NPower power) => PowerBindings.GetValue(power, CreatePowerBinding).Refresh(null);

    private static PowerBinding CreatePowerBinding(NPower power)
    {
        var overlay = new Control { Name = OverlayName, Visible = false, MouseFilter = Control.MouseFilterEnum.Ignore };
        power.AddChild(overlay);
        overlay.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        var veil = new ColorRect { Color = new Color(0.02f, 0.08f, 0.15f, 0.65f), MouseFilter = Control.MouseFilterEnum.Ignore };
        overlay.AddChild(veil);
        veil.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        // Two high-contrast diagonal strokes remain legible on every native icon.
        foreach (var angle in new[] { -Mathf.Pi / 4, Mathf.Pi / 4 })
        {
            var slash = new ColorRect { Color = new Color(0.45f, 0.9f, 1f),
                Size = new Vector2(34, 3), Position = new Vector2(16, 16),
                PivotOffset = new Vector2(17, 1.5f), Rotation = angle,
                MouseFilter = Control.MouseFilterEnum.Ignore };
            slash.Position -= slash.PivotOffset;
            overlay.AddChild(slash);
        }
        return new PowerBinding(power, overlay);
    }

    private sealed class PowerBinding
    {
        private readonly NPower power;
        private readonly Control overlay;
        private Action? unsubscribe;

        internal PowerBinding(NPower power, Control overlay)
        {
            this.power = power;
            this.overlay = overlay;
            overlay.TreeEntered += Enter;
            overlay.TreeExiting += Exit;
            if (overlay.IsInsideTree()) Enter();
        }

        private void Enter()
        {
            if (unsubscribe is not null) return;
            var tracker = CombatManager.Instance.StateTracker;
            tracker.CombatStateChanged += Refresh;
            unsubscribe = () => tracker.CombatStateChanged -= Refresh;
            Refresh(null);
        }

        private void Exit()
        {
            unsubscribe?.Invoke();
            unsubscribe = null;
            overlay.Visible = false;
        }

        internal void Refresh(CombatState? _) => overlay.Visible =
            overlay.IsInsideTree() && ReadBoundModel(power) is { } model &&
            PowerPresentationDisabled.IsSuppressed(model);
    }

    internal static void Attach(NCreature creature)
    {
        if (creature.Hitbox.HasNode(OverlayName)) return;
        var badge = new PanelContainer { Name = OverlayName, MouseFilter = Control.MouseFilterEnum.Stop,
            Position = new Vector2(0, -36), ZIndex = 5 };
        var style = new StyleBoxFlat { BgColor = new Color(0.025f, 0.1f, 0.2f, 0.94f),
            BorderColor = new Color(0.4f, 0.85f, 1f), BorderWidthLeft = 2, BorderWidthRight = 2,
            BorderWidthTop = 2, BorderWidthBottom = 2, ContentMarginLeft = 8, ContentMarginRight = 8,
            ContentMarginTop = 3, ContentMarginBottom = 3 };
        badge.AddThemeStyleboxOverride("panel", style);
        var label = new Label { MouseFilter = Control.MouseFilterEnum.Ignore };
        label.AddThemeColorOverride("font_color", new Color(0.65f, 0.93f, 1f));
        label.AddThemeFontSizeOverride("font_size", 18);
        badge.AddChild(label);
        creature.Hitbox.AddChild(badge);
        bool hovered = false;
        badge.MouseEntered += () => { hovered = true; creature.ShowHoverTips(creature.Entity.HoverTips); };
        badge.MouseExited += () => { hovered = false; creature.HideHoverTips(); };
        void Refresh(CombatState? _)
        {
            badge.Visible = PowerPresentationDisabled.IsCreatureSuppressed(creature.Entity);
            if (badge.Visible) label.Text = PowerPresentationDisabled.Text("badge").GetFormattedText();
            if (hovered)
            {
                if (badge.Visible) creature.ShowHoverTips(creature.Entity.HoverTips);
                else { hovered = false; creature.HideHoverTips(); }
            }
        }
        Refresh(null);
        CombatManager.Instance.StateTracker.CombatStateChanged += Refresh;
        creature.TreeExited += () => CombatManager.Instance.StateTracker.CombatStateChanged -= Refresh;
    }
}
