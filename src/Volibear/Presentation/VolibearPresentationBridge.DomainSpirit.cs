using System;
using Godot;

namespace Volibear.Presentation;

public static partial class VolibearPresentationBridge
{
    internal static string ArchitectSpiritShader => OwnerScope.SpiritShader;
    internal static void EnterArchitectDomain(MegaCrit.Sts2.Core.Entities.Creatures.Creature creature)
    {
        var node = MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom.Instance?.GetCreatureNode(creature);
        if (node is null || !GodotObject.IsInstanceValid(node))
            throw new InvalidOperationException("Architect domain entry requires the actual character view");
        VolibearArchitectDomainVisual.Enter(node);
    }
    internal static VolibearArchitectDomainVisual? ArchitectDomainVisual(MegaCrit.Sts2.Core.Entities.Creatures.Creature creature) =>
        MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom.Instance?.GetCreatureNode(creature)?.Visuals
            .GetNodeOrNull<VolibearArchitectDomainVisual>("VolibearArchitectDomain");

    private sealed partial class OwnerScope
    {
        private Node2D? _spiritVisuals;
        private AnimatedSprite2D? _spiritSprite;
        private Vector2 _spiritScale;
        private Material? _spiritMaterial;
        private Node2D? _stormRing;

        private void UpdateSpiritForm(bool active)
        {
            var visuals = Valid(_node) && Valid(_node.Visuals)
                ? _node.Visuals.GetNodeOrNull<Node2D>("Visuals") : null;
            if (!active || !Valid(visuals) || (_spiritVisuals is not null && _spiritVisuals != visuals))
                ReleaseSpiritForm();
            if (!active || !Valid(visuals) || _spiritVisuals is not null) return;
            var sprite = visuals!.GetNodeOrNull<AnimatedSprite2D>("AnimatedSprite2D");
            if (!Valid(sprite)) return;
            _spiritVisuals = visuals;
            _spiritSprite = sprite;
            _spiritScale = visuals.Scale;
            _spiritMaterial = sprite!.Material;
            visuals.Scale = _spiritScale * 1.22f;
            sprite.Material = new ShaderMaterial { Shader = new Shader { Code = SpiritShader } };
            _stormRing = new Node2D { Name = "VolibearDomainLightningRing" };
            DomainStormRing.Populate(_stormRing);
            _node.Visuals.AddChild(_stormRing);
            _node.Visuals.MoveChild(_stormRing, 0);
        }

        private void TickSpiritForm()
        {
            if (!_domain) return;
            UpdateSpiritForm(true);
            if (Valid(_stormRing)) DomainStormRing.Animate(_stormRing!, Time.GetTicksMsec() / 1000f);
        }

        private void ReleaseSpiritForm()
        {
            if (Valid(_spiritVisuals)) _spiritVisuals!.Scale = _spiritScale;
            if (Valid(_spiritSprite)) _spiritSprite!.Material = _spiritMaterial;
            if (Valid(_stormRing)) _stormRing!.QueueFree();
            _spiritVisuals = null;
            _spiritSprite = null;
            _spiritMaterial = null;
            _stormRing = null;
        }

        internal const string SpiritShader = """
            shader_type canvas_item;
            render_mode unshaded;
            varying vec4 vertex_tint;
            void vertex() { vertex_tint = COLOR; }
            void fragment() {
                vec4 tex = texture(TEXTURE, UV);
                float light = dot(tex.rgb, vec3(0.299, 0.587, 0.114));
                vec3 blue = mix(vec3(0.035, 0.22, 0.60), vec3(0.55, 0.91, 1.0), light);
                float pulse = 0.5 + 0.5 * sin(TIME * 3.0 + UV.y * 8.0);
                blue += vec3(0.02, 0.09, 0.14) * pulse;
                COLOR = vec4(blue, tex.a * 0.72) * vertex_tint;
            }
            """;
    }
}
