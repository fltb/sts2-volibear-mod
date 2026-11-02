// Small tree/event fixture; production overlay code is linked unchanged.
using System.Runtime.CompilerServices;
namespace Godot
{
    public readonly record struct Vector2(float X, float Y)
    {
        public static Vector2 operator -(Vector2 a, Vector2 b) => new(a.X-b.X,a.Y-b.Y);
    }
    public readonly record struct Color(float R, float G, float B, float A = 1);
    public static class Mathf { public const float Pi = MathF.PI; }
    public class Control
    {
        public enum MouseFilterEnum { Ignore, Stop }
        public enum LayoutPreset { FullRect }
        public string Name { get; set; } = "";
        public bool Visible { get; set; } = true;
        public MouseFilterEnum MouseFilter { get; set; }
        public Vector2 Size { get; set; }
        public Vector2 Position { get; set; }
        public Vector2 PivotOffset { get; set; }
        public float Rotation { get; set; }
        public int ZIndex { get; set; }
        public readonly List<Control> Children = [];
        private bool inside;
        public event Action? TreeEntered;
        public event Action? TreeExiting;
        public event Action? TreeExited;
        public event Action? MouseEntered;
        public event Action? MouseExited;
        public bool IsInsideTree() => inside;
        public bool HasNode(string name) => Children.Any(n => n.Name == name);
        public void AddChild(Control child) { Children.Add(child); if(inside) child.Enter(); }
        public void SetAnchorsAndOffsetsPreset(LayoutPreset _) { }
        public void Enter() { inside=true; TreeEntered?.Invoke(); foreach(var c in Children) c.Enter(); }
        public void Exit() { foreach(var c in Children) c.Exit(); TreeExiting?.Invoke(); inside=false; TreeExited?.Invoke(); }
    }
    public class ColorRect : Control { public Color Color { get; set; } }
    public class PanelContainer : Control { public void AddThemeStyleboxOverride(string key, StyleBoxFlat value) { } }
    public class Label : Control
    {
        public string Text { get; set; } = "";
        public void AddThemeColorOverride(string key, Color value) { }
        public void AddThemeFontSizeOverride(string key, int value) { }
    }
    public class StyleBoxFlat
    {
        public Color BgColor, BorderColor;
        public int BorderWidthLeft, BorderWidthRight, BorderWidthTop, BorderWidthBottom;
        public int ContentMarginLeft, ContentMarginRight, ContentMarginTop, ContentMarginBottom;
    }
}
namespace MegaCrit.Sts2.Core.Models
{
    public class PowerModel { public bool Suppressed; public bool IsCanonical; }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public class CombatState { }
    public class Tracker
    {
        public event Action<CombatState>? CombatStateChanged;
        public int Subscribers => CombatStateChanged?.GetInvocationList().Length ?? 0;
        public void Notify() => CombatStateChanged?.Invoke(new());
    }
    public class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public Tracker StateTracker { get; set; } = new();
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Combat
{
    using MegaCrit.Sts2.Core.Models;
    public class NPower : Godot.Control
    {
        private PowerModel? _model;
        public int GetterReads;
        public PowerModel Model
        {
            get { GetterReads++; return _model ?? throw new InvalidOperationException("Model was accessed before it was set."); }
            [MethodImpl(MethodImplOptions.NoInlining)]
            set { _model = value; }
        }
    }
    public class NCreature : Godot.Control
    {
        public Godot.Control Hitbox { get; } = new();
        public Entity Entity { get; } = new();
        public void ShowHoverTips(object value) { }
        public void HideHoverTips() { }
    }
    public class Entity { public object HoverTips { get; } = new(); }
}
namespace Volibear.Presentation
{
    internal static class PowerPresentationDisabled
    {
        internal static int Evaluations;
        internal static bool IsSuppressed(MegaCrit.Sts2.Core.Models.PowerModel power)
        { Evaluations++; return !power.IsCanonical && power.Suppressed; }
        internal static bool IsCreatureSuppressed(object entity) => false;
        internal static TextValue Text(string key) => new();
        internal sealed class TextValue { public string GetFormattedText() => "disabled"; }
    }
}
