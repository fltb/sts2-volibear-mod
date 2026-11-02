using System.Reflection;
using BaseLib.Utils;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using Volibear.Presentation;

static bool Invoke(string method, params object[] arguments) =>
    (bool)typeof(VolibearMerchantIntegration).GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, arguments)!;
static void Check(bool condition, string label)
{
    if (!condition) throw new Exception(label);
}

var vanilla = new NMerchantCharacter();
vanilla.Children.Add(new Node { SceneFilePath = "res://other/merchant.tscn" });
Check(Invoke("Ready", vanilla), "Other characters must keep native Ready");
Check(Invoke("PlayAnimation", vanilla, "die"), "Other characters must keep native animation");
Check(CustomAnimation.Calls == 0, "Other characters must not touch custom animation");
var empty = new NMerchantCharacter();
Check(Invoke("Ready", empty), "Malformed unrelated scenes must not be hidden");
var bear = new NMerchantCharacter();
bear.Children.Add(new Node { SceneFilePath = VolibearPresentation.MerchantScenePath });
Check(!Invoke("Ready", bear), "Converted Volibear must bypass Spine Ready");
Check(CustomAnimation.Names.SequenceEqual(new[] { "idle", "Idle", "relaxed_loop" }), "Ready must start relaxed animation");
Check(!Invoke("PlayAnimation", bear, "die"), "Volibear animation must bypass Spine");
Check(CustomAnimation.Names.SequenceEqual(new[] { "Die", "die" }), "Death aliases must match BaseLib");
Check(!Invoke("PlayAnimation", bear, "custom"), "Other animation requests must dispatch");
Check(CustomAnimation.Names.SequenceEqual(new[] { "custom" }), "Unknown animation names must be preserved");
CustomAnimation.HasAnimation = false;
try { Invoke("Ready", bear); throw new Exception("Broken Volibear animation must fail visibly"); }
catch (TargetInvocationException e) when (e.InnerException is InvalidOperationException) { }
Console.WriteLine("PASS: merchant scope, Ready, animation dispatch, and visible failures (stub logic test; not Godot execution)");

namespace Godot
{
    public class Node
    {
        public string SceneFilePath { get; set; } = "";
        public List<Node> Children { get; } = [];
        public int GetChildCount() => Children.Count;
        public Node GetChild(int index) => Children[index];
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Shops
{
    public class NMerchantCharacter : Node
    {
        public void _Ready() { }
        public void PlayAnimation(string anim, bool loop = false) { }
    }
}
namespace BaseLib.Utils
{
    public static class CustomAnimation
    {
        public static bool HasAnimation = true;
        public static int Calls;
        public static string[] Names = [];
        public static bool HasCustomAnimation(Node node) => HasAnimation;
        public static bool PlayCustomAnimation(Node node, params string[] names)
        { Calls++; Names = names; return HasAnimation; }
    }
}
namespace HarmonyLib
{
    public class Harmony
    {
        public Harmony(string id) { }
        public Harmony CreateClassProcessor(Type type) => this;
        public void Patch() { }
    }
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
    public class HarmonyPatch : Attribute
    {
        public HarmonyPatch() { }
        public HarmonyPatch(Type type, string method) { }
    }
    public class HarmonyPrefix : Attribute { }
}
namespace Volibear.Presentation
{
    internal static class VolibearPresentation
    {
        public const string MerchantScenePath = "res://VolibearArt/scenes/volibear_merchant.tscn";
    }
}
