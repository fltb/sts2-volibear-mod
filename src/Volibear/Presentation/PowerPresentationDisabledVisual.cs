using System;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace Volibear.Presentation;

/// <summary>Native UI children refreshed by the native state tracker, never a frame poll.
/// Overlays do not replace models, change their materials, or touch gameplay state.
/// A disabled entry is marked by the packed suppression rune only: no persistent words.</summary>
internal static class PowerPresentationDisabledVisual
{
    private const string OverlayName = "VolibearDomainDisabled";
    internal const string SuppressionIconPath = "res://VolibearArt/vfx/icons/128/domain_suppress.png";
    private const float CreatureIconSize = 56f;

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

    private static TextureRect Rune() => new()
    {
        Name = "SuppressionRune",
        Texture = ResourceLoader.Load<Texture2D>(SuppressionIconPath),
        ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
        StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
        MouseFilter = Control.MouseFilterEnum.Ignore,
    };

    private static PowerBinding CreatePowerBinding(NPower power)
    {
        var overlay = new Control { Name = OverlayName, Visible = false, MouseFilter = Control.MouseFilterEnum.Ignore };
        power.AddChild(overlay);
        overlay.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        // Dim the native effect icon and cover it with the same suppression rune used
        // for the creature marker: one icon, no text, on every disabled entry.
        var veil = new ColorRect { Color = new Color(0.02f, 0.08f, 0.15f, 0.55f), MouseFilter = Control.MouseFilterEnum.Ignore };
        overlay.AddChild(veil);
        veil.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
        var rune = Rune();
        overlay.AddChild(rune);
        rune.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
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
        // Icon-only marker: no label, no words. It is aligned onto the creature's
        // intent row so the rune covers the intent icons the domain suppresses.
        var badge = new Control { Name = OverlayName, Visible = false, MouseFilter = Control.MouseFilterEnum.Stop, ZIndex = 5,
            Size = new Vector2(CreatureIconSize, CreatureIconSize) };
        var rune = Rune();
        rune.Size = new Vector2(CreatureIconSize, CreatureIconSize);
        badge.AddChild(rune);
        creature.Hitbox.AddChild(badge);
        bool hovered = false;
        badge.MouseEntered += () => { hovered = true; creature.ShowHoverTips(creature.Entity.HoverTips); };
        badge.MouseExited += () => { hovered = false; creature.HideHoverTips(); };
        void Refresh(CombatState? _)
        {
            badge.Visible = PowerPresentationDisabled.IsCreatureSuppressed(creature.Entity);
            badge.Position = BadgePosition(creature);
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

    private static Vector2 BadgePosition(NCreature creature)
    {
        var intents = creature.IntentContainer;
        if (intents is { } target && target.IsInsideTree() && creature.Hitbox.IsInsideTree())
        {
            // Convert the native intent row centre into the hitbox-local space the
            // badge lives in; the rune then covers the intent icons on every creature.
            Rect2 row = target.GetGlobalRect();
            // NIntent stacks its icon above the value label; bias the rune onto the
            // icon row so the marker covers the intent glyph rather than the number.
            Vector2 centre = row.Position + new Vector2(row.Size.X / 2f, 20f);
            Vector2 local = creature.Hitbox.GetGlobalTransform().AffineInverse() * centre;
            return local - new Vector2(CreatureIconSize / 2f, CreatureIconSize / 2f);
        }
        return new Vector2((creature.Hitbox.Size.X - CreatureIconSize) / 2f, -68f);
    }
}
