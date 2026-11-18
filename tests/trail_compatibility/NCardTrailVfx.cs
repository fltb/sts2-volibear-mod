using Godot;

namespace MegaCrit.Sts2.Core.Nodes.Vfx;

// Only the game type is doubled. PackedScene, Node2D, ownership, deletion and
// the scene tree below are real Godot 4.5.1 objects, and Harmony is the real library.
public partial class NCardTrailVfx : Node2D
{
    public bool ReadyWithSprites { get; private set; }
    public override void _Ready() => ReadyWithSprites = GetNodeOrNull("Sprites") is Node2D;
}
