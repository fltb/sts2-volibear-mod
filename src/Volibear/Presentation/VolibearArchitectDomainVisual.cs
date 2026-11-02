using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace Volibear.Presentation;

/// <summary>Event-room lifetime without relying on Godot callbacks for a dynamically loaded Mod class.</summary>
internal sealed partial class VolibearArchitectDomainVisual : Node2D
{
    private Node2D body = null!;
    private AnimatedSprite2D sprite = null!;
    private Vector2 originalScale;
    private SceneTree? tree;
    internal bool Entered { get; private set; }

    internal static void Enter(NCreature creature)
    {
        if (creature.Visuals.GetNodeOrNull<VolibearArchitectDomainVisual>("VolibearArchitectDomain") is not null) return;
        var view = new VolibearArchitectDomainVisual { Name = "VolibearArchitectDomain" };
        view.body = creature.Visuals.GetNode<Node2D>("Visuals");
        view.sprite = view.body.GetNode<AnimatedSprite2D>("AnimatedSprite2D");
        view.originalScale = view.body.Scale;
        DomainStormRing.Populate(view);
        view.TreeEntered += view.Attach;
        view.TreeExiting += view.Detach;
        creature.Visuals.AddChild(view);
        creature.Visuals.MoveChild(view, 0);
        view.body.Scale = view.originalScale * 1.22f;
        view.sprite.Material = new ShaderMaterial { Shader = new Shader { Code = VolibearPresentationBridge.ArchitectSpiritShader } };
        VolibearPresentation.SetIdle(creature.Visuals, "domain_idle");
        VolibearPresentation.Play(creature.Visuals, "domain_enter");
        view.Entered = true;
    }
    private void Tick() => DomainStormRing.Animate(this, Time.GetTicksMsec() / 1000f);
    private void Attach()
    {
        Detach();
        tree = GetTree();
        tree.ProcessFrame += Tick;
    }
    private void Detach()
    {
        // The native victory screen detaches the event-room visuals. That ends rendering,
        // not the character's final domain state. Keep the treatment until this view is freed;
        // if the room is reattached, resume animation without applying scale a second time.
        if (tree is not null && GodotObject.IsInstanceValid(tree)) tree.ProcessFrame -= Tick;
        tree = null;
    }
}
