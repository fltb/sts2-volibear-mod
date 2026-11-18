using System;
using System.Collections.Generic;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Vfx;

namespace Volibear.Presentation;

/// <summary>
/// Lifecycle compatibility only: convert our trail scene without replacing BaseLib's
/// process-wide NodeFactory&lt;NCardTrailVfx&gt; slot, which other character mods can own.
/// The native trail still handles following cards, fading and cleanup; animation is unchanged.
/// </summary>
internal static class VolibearTrailFactory
{
    private static bool installed;

    internal static void Install()
    {
        if (installed) return;
        var instantiate = typeof(PackedScene).GetMethod(nameof(PackedScene.Instantiate),
            genericParameterCount: 0, [typeof(PackedScene.GenEditState)])
            ?? throw new MissingMethodException(typeof(PackedScene).FullName, nameof(PackedScene.Instantiate));
        new Harmony("Volibear.TrailCompatibility").Patch(instantiate,
            postfix: new HarmonyMethod(typeof(VolibearTrailFactory), nameof(ConvertOwnedScene))
            { after = ["BaseLib"] });
        installed = true;
    }

    private static void ConvertOwnedScene(PackedScene __instance, ref Node __result)
    {
        if (!string.Equals(__instance.ResourcePath, VolibearPresentation.TrailScenePath, StringComparison.Ordinal) ||
            __result is NCardTrailVfx) return;

        // Validate before creating a replacement or detaching anything. A failed conversion
        // must never hand the caller a partially dismantled scene.
        if (__result is not Node2D source || source.GetNodeOrNull("Sprites") is not Node2D)
            throw new InvalidOperationException("Volibear trail scene requires a Node2D root and Sprites child.");

        var ownership = new List<(Node Node, Node? Owner)>();
        CollectOwnership(source, ownership);
        var children = source.GetChildren(includeInternal: true);
        var ordinaryChildren = new HashSet<Node>(source.GetChildren());
        var target = new NCardTrailVfx
        {
            Name = source.Name,
            SceneFilePath = source.SceneFilePath,
            ProcessMode = source.ProcessMode,
            ProcessPriority = source.ProcessPriority,
            ProcessPhysicsPriority = source.ProcessPhysicsPriority,
            Visible = source.Visible,
            Modulate = source.Modulate,
            SelfModulate = source.SelfModulate,
            ShowBehindParent = source.ShowBehindParent,
            TopLevel = source.TopLevel,
            ZIndex = source.ZIndex,
            ZAsRelative = source.ZAsRelative,
            YSortEnabled = source.YSortEnabled,
            TextureFilter = source.TextureFilter,
            TextureRepeat = source.TextureRepeat,
            Material = source.Material,
            UseParentMaterial = source.UseParentMaterial,
            ClipChildren = source.ClipChildren,
            LightMask = source.LightMask,
            VisibilityLayer = source.VisibilityLayer,
            Transform = source.Transform
        };

        // Sprites guarantees at least one ordinary child. Keep both internal groups and
        // their ordering, including nodes another postfix attached to this owned scene.
        foreach (var (node, owner) in ownership)
            if (ReferenceEquals(owner, source)) node.Owner = null;
        var passedOrdinaryChild = false;
        foreach (var child in children)
        {
            var ordinary = ordinaryChildren.Contains(child);
            var mode = ordinary ? Node.InternalMode.Disabled : passedOrdinaryChild
                ? Node.InternalMode.Back : Node.InternalMode.Front;
            passedOrdinaryChild |= ordinary;
            source.RemoveChild(child);
            target.AddChild(child, @internal: mode);
        }
        foreach (var (node, owner) in ownership)
            node.Owner = ReferenceEquals(owner, source) ? target : owner;

        // Keep root metadata/groups used by cooperating presentation mods. Children are
        // the original instances, so their scripts, resources and connections are retained.
        foreach (var key in source.GetMetaList()) target.SetMeta(key, source.GetMeta(key));
        foreach (var group in source.GetGroups()) target.AddToGroup(group);
        source.QueueFree();
        __result = target;
    }

    private static void CollectOwnership(Node parent, List<(Node Node, Node? Owner)> ownership)
    {
        foreach (var child in parent.GetChildren(includeInternal: true))
        {
            ownership.Add((child, child.Owner));
            CollectOwnership(child, ownership);
        }
    }
}
