using System;
using BaseLib.Utils.NodeFactories;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Vfx;

namespace Volibear.Presentation;

/// <summary>
/// The game casts character trail scenes to NCardTrailVfx. BaseLib 3.4.7 does not register
/// that type, so this adapter supplies only its required native child contract. The game's
/// own NCardTrailVfx remains responsible for following cards, fading and cleanup.
/// </summary>
internal sealed class VolibearTrailFactory : NodeFactory<NCardTrailVfx>
{
    public VolibearTrailFactory() : base([new NodeInfo<Node2D>("Sprites", false)]) { }

    protected override void GenerateNode(Node target, INodeInfo required) =>
        throw new InvalidOperationException($"Volibear trail scene is missing {required.Path}");
}
