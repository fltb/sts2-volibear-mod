using System.Reflection;
using System.Runtime.InteropServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using Volibear.Presentation;

public partial class Program : Node
{
    private static int assertions;
    private static readonly MethodInfo Instantiate = typeof(PackedScene).GetMethod(
        nameof(PackedScene.Instantiate), genericParameterCount: 0, [typeof(PackedScene.GenEditState)])!;
    private const string ForeignPath = "res://ForeignCharacter/trail.tscn";
    private static readonly Dictionary<Type, Func<Node, Node>> ForeignFactories = new();
    private static readonly Dictionary<string, Type> ForeignScenes = new();
    private static Node? observedSource;
    private static Node? foreignResult;
    private static Node? suppliedNative;
    private static bool supplyNative;
    private static bool decorate;

    [DllImport("libdl.so.2")]
    private static extern IntPtr dlopen(string fileName, int flags);

    public override async void _Ready()
    {
        try
        {
            var order = OS.GetCmdlineUserArgs().Single();
            Require(order is "foreign-first" or "volibear-first", "known registration order");
            // BaseLib.Initialize does the same Linux preload before using Harmony. This
            // standalone Godot fixture has no BaseLib/game assembly to perform it for us.
            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux) && dlopen("libgcc_s.so.1", 2 | 256) == IntPtr.Zero)
                throw new InvalidOperationException("Unable to prepare libgcc for Harmony in Godot.");
            // Fixture for BaseLib's registry-backed Instantiate postfix. Its global registry
            // is deliberately owned by a different consumer; production must never replace it.
            new Harmony("BaseLib").Patch(Instantiate,
                postfix: new HarmonyMethod(typeof(Program), nameof(FrameworkPostfix)));
            if (order == "foreign-first") RegisterForeign();
            VolibearTrailFactory.Install();
            VolibearTrailFactory.Install();
            if (order == "volibear-first") RegisterForeign();

            var patches = Harmony.GetPatchInfo(Instantiate)!;
            Require(patches.Postfixes.Count(p => p.owner == "Volibear.TrailCompatibility") == 1,
                "repeated installation registers one postfix");
            Require(patches.Postfixes.Single(p => p.owner == "Volibear.TrailCompatibility").after.Contains("BaseLib"),
                "conversion explicitly follows framework conversion");
            Require(ForeignFactories.Count == 1 && ForeignFactories[typeof(NCardTrailVfx)] == ConvertForeign,
                "foreign type factory survives both registration orders");
            Require(ForeignScenes.Count == 1 && ForeignScenes.ContainsKey(ForeignPath),
                "foreign scene registrations are untouched");

            decorate = true;
            using var ownScene = Scene(VolibearPresentation.TrailScenePath);
            var converted = ownScene.Instantiate();
            var original = (Node2D)observedSource!;
            Require(converted is NCardTrailVfx, "owned scene returns native-compatible trail");
            var trail = (NCardTrailVfx)converted;
            Require(original.IsQueuedForDeletion() && original.GetChildCount(true) == 0,
                "only emptied original root is queued for deletion");
            Require(trail.Name == original.Name && trail.SceneFilePath == original.SceneFilePath,
                "root identity properties retained");
            Require(trail.Transform.IsEqualApprox(original.Transform), "full Node2D transform retained");
            Require(trail.Visible == original.Visible && trail.Modulate == original.Modulate &&
                trail.SelfModulate == original.SelfModulate && trail.ShowBehindParent == original.ShowBehindParent &&
                trail.TopLevel == original.TopLevel && trail.ZIndex == original.ZIndex &&
                trail.ZAsRelative == original.ZAsRelative && trail.YSortEnabled == original.YSortEnabled,
                "CanvasItem drawing state retained");
            Require(trail.TextureFilter == original.TextureFilter && trail.TextureRepeat == original.TextureRepeat &&
                ReferenceEquals(trail.Material, original.Material) && trail.UseParentMaterial == original.UseParentMaterial &&
                trail.ClipChildren == original.ClipChildren && trail.LightMask == original.LightMask &&
                trail.VisibilityLayer == original.VisibilityLayer, "CanvasItem resource and layer state retained");
            Require(trail.ProcessMode == original.ProcessMode && trail.ProcessPriority == original.ProcessPriority &&
                trail.ProcessPhysicsPriority == original.ProcessPhysicsPriority, "process configuration retained");
            Require(trail.GetMeta("foreign_marker").AsString() == "retained" && trail.IsInGroup("foreign-group"),
                "cooperating root metadata and group retained");
            Require(trail.GetChildren(true).Select(n => n.Name.ToString()).SequenceEqual(
                new[] { "InternalFront", "Sprites", "Extra", "InternalBack" }), "all root children retain order");
            Require(trail.GetChildren().Select(n => n.Name.ToString()).SequenceEqual(new[] { "Sprites", "Extra" }),
                "internal children stay internal");
            var sprites = trail.GetNode<Node2D>("Sprites");
            Require(ReferenceEquals(sprites, beforeSprites), "Sprites is the original instance");
            Require(ReferenceEquals(sprites.Owner, trail), "root-owned child follows replacement root");
            Require(ReferenceEquals(sprites.GetNode("RootOwned").Owner, trail), "root-owned descendant follows replacement root");
            Require(ReferenceEquals(sprites.GetNode("NestedOwned").Owner, sprites), "nested ownership remains nested");
            Require(sprites.GetNode("Unowned").Owner is null, "unowned descendant remains unowned");
            Require(ReferenceEquals(trail.GetNode("%Sprites"), sprites), "unique-name lookup follows new owner");
            AddChild(trail);
            Require(trail.ReadyWithSprites, "replacement enters real scene tree with child contract intact");
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            Require(!GodotObject.IsInstanceValid(original), "queued original root is freed by Godot");
            Require(GodotObject.IsInstanceValid(sprites), "moved children outlive original root");
            trail.QueueFree();

            decorate = false;
            using var foreignScene = Scene(ForeignPath);
            var foreign = foreignScene.Instantiate();
            Require(ReferenceEquals(foreign, foreignResult) && foreign.GetMeta("foreign_result").AsBool(),
                "foreign factory result is not replaced");
            Require(ForeignFactories[typeof(NCardTrailVfx)] == ConvertForeign && ForeignScenes.Count == 1,
                "instantiation never overwrites foreign registries");
            foreign.Free();

            foreach (var path in new[] { "res://Other/volibear_trail.tscn", "res://VolibearArt/scenes/volibear_trail.tscn.other" })
            {
                using var unrelated = Scene(path, valid: false);
                var node = unrelated.Instantiate();
                Require(ReferenceEquals(node, observedSource) && node is not NCardTrailVfx && !node.IsQueuedForDeletion(),
                    "foreign scene without Sprites is returned untouched: " + path);
                node.Free();
            }

            supplyNative = true;
            var alreadyNative = ownScene.Instantiate();
            Require(ReferenceEquals(alreadyNative, suppliedNative) && !alreadyNative.IsQueuedForDeletion(),
                "already-native owned result is preserved");
            alreadyNative.Free();
            supplyNative = false;

            using var invalid = Scene(VolibearPresentation.TrailScenePath, valid: false);
            bool rejected = false;
            try { invalid.Instantiate().Free(); }
            catch (InvalidOperationException e) { rejected = e.Message.Contains("Sprites"); }
            Require(rejected, "invalid owned scene reports contract failure");
            Require(observedSource is { } bad && GodotObject.IsInstanceValid(bad) && !bad.IsQueuedForDeletion() &&
                bad.GetChildCount() == 1 && bad.GetNodeOrNull("Wrong") is Node2D,
                "contract validation leaves invalid source intact");
            observedSource!.Free();
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            GD.Print($"TRAIL_COMPATIBILITY_PASS order={order} assertions={assertions} godot=REAL harmony=REAL game-type=DOUBLE native-gameplay=NOT_RUN");
            GetTree().Quit();
        }
        catch (Exception error)
        {
            GD.PrintErr(error.ToString());
            GetTree().Quit(1);
        }
    }

    private static void Require(bool condition, string name)
    {
        if (!condition) throw new InvalidOperationException(name);
        assertions++;
    }

    private static void RegisterForeign()
    {
        ForeignFactories.Add(typeof(NCardTrailVfx), ConvertForeign);
        ForeignScenes.Add(ForeignPath, typeof(NCardTrailVfx));
    }

    private static Node ConvertForeign(Node source)
    {
        var target = new NCardTrailVfx { Name = "ForeignNativeTrail" };
        var sprites = source.GetNode("Sprites");
        sprites.Owner = null;
        source.RemoveChild(sprites);
        target.AddChild(sprites);
        target.SetMeta("foreign_result", true);
        source.QueueFree();
        foreignResult = target;
        return target;
    }

    private static Node? beforeSprites;
    private static void FrameworkPostfix(PackedScene __instance, ref Node __result)
    {
        observedSource = __result;
        if (ForeignScenes.TryGetValue(__instance.ResourcePath, out var type))
            __result = ForeignFactories[type](__result);
        if (__instance.ResourcePath != VolibearPresentation.TrailScenePath) return;
        if (supplyNative)
        {
            var target = new NCardTrailVfx { Name = "AlreadyNative" };
            __result.QueueFree();
            __result = target;
            suppliedNative = target;
        }
        else if (decorate)
        {
            var sprites = __result.GetNode("Sprites");
            beforeSprites = sprites;
            var nested = new Node { Name = "NestedOwned" };
            sprites.AddChild(nested);
            nested.Owner = sprites;
            sprites.AddChild(new Node { Name = "Unowned" });
            __result.AddChild(new Node { Name = "InternalFront" }, @internal: Node.InternalMode.Front);
            __result.AddChild(new Node { Name = "InternalBack" }, @internal: Node.InternalMode.Back);
            __result.SetMeta("foreign_marker", "retained");
            __result.AddToGroup("foreign-group");
        }
    }

    private static PackedScene Scene(string path, bool valid = true)
    {
        var source = new Node2D
        {
            Name = "OwnedTrail", Position = new(12, -7), Rotation = .4f, Scale = new(2, 3), Skew = .1f,
            Visible = false, Modulate = new(.2f, .3f, .4f, .5f), SelfModulate = new(.6f, .7f, .8f, .9f),
            ShowBehindParent = true, TopLevel = true, ZIndex = 4, ZAsRelative = false, YSortEnabled = true,
            TextureFilter = CanvasItem.TextureFilterEnum.Nearest, TextureRepeat = CanvasItem.TextureRepeatEnum.Enabled,
            Material = new CanvasItemMaterial(), UseParentMaterial = true, ClipChildren = CanvasItem.ClipChildrenMode.Only,
            LightMask = 3, VisibilityLayer = 7, ProcessMode = ProcessModeEnum.Always,
            ProcessPriority = 12, ProcessPhysicsPriority = 13
        };
        var sprites = new Node2D { Name = valid ? "Sprites" : "Wrong" };
        source.AddChild(sprites);
        sprites.Owner = source;
        sprites.UniqueNameInOwner = true;
        if (valid)
        {
            var nested = new Node { Name = "RootOwned" };
            sprites.AddChild(nested);
            nested.Owner = source;
            var extra = new Node { Name = "Extra" };
            source.AddChild(extra);
            extra.Owner = source;
        }
        var scene = new PackedScene();
        Require(scene.Pack(source) == Error.Ok, "fixture scene packs successfully");
        scene.TakeOverPath(path);
        source.Free();
        return scene;
    }
}
