using System;
using Godot;

namespace Volibear.Presentation;

/// <summary>Foot-anchored storm volume, drawn within the actor's visual layer, below native status UI.
/// The painted lightning-field texture replaces the thin procedural ellipse: layered electric bands,
/// jagged arcs and rising spikes give the domain real thickness instead of a single thin circle.</summary>
internal static class DomainStormRing
{
    internal const float Radius = 300f;
    internal const string AuraPath = "res://VolibearArt/ui/images/domain_storm_aura.png";
    private const int Bolts = 12;
    private static Vector2 Ground(float angle, float radius) => new(Mathf.Cos(angle) * radius, Mathf.Sin(angle) * radius * .24f - 5f);
    private static CanvasItemMaterial Light() => new() { BlendMode = CanvasItemMaterial.BlendModeEnum.Add, LightMode = CanvasItemMaterial.LightModeEnum.Unshaded };

    internal static void Populate(Node2D root)
    {
        // Never use negative global Z (behind the opaque room) or raise above health/status UI.
        root.ZIndex = 0;
        var texture = GD.Load<Texture2D>(AuraPath);
        if (texture is not null)
        {
            var aura = new Sprite2D { Name = "StormAura", Texture = texture, Centered = true, Material = Light() };
            root.AddChild(aura);
            var inner = new Sprite2D { Name = "StormAuraInner", Texture = texture, Centered = true, Material = Light(),
                Modulate = new Color(.75f, .92f, 1f, .55f) };
            root.AddChild(inner);
        }
        // A few procedural spikes keep the field alive between painted keyframes.
        var bolts = new Node2D { Name = "StormBolts" };
        root.AddChild(bolts);
        var light = Light();
        for (int i = 0; i < Bolts; i++)
            bolts.AddChild(new Line2D { Name = "RisingBolt" + i, Width = 3.2f, Antialiased = true,
                DefaultColor = new Color(.42f, .86f, 1f, .92f), Material = light });
        Animate(root, Time.GetTicksMsec() / 1000f);
    }

    internal static void Animate(Node2D root, float time)
    {
        float breathe = 1f + .025f * Mathf.Sin(time * 1.1f);
        if (root.GetNodeOrNull<Sprite2D>("StormAura") is { Texture: { } texture } aura)
        {
            // The painted band is sized to the pinned 600 x 144 foot ellipse, then breathes.
            float scale = 620f / texture.GetWidth();
            aura.Position = new Vector2(0, -30f);
            aura.Scale = new Vector2(scale * breathe, scale * (2f - breathe));
            aura.Modulate = new Color(1f, 1f, 1f, .86f + .14f * (.5f + .5f * Mathf.Sin(time * 2.6f)));
        }
        if (root.GetNodeOrNull<Sprite2D>("StormAuraInner") is { Texture: { } innerTexture } inner)
        {
            float scale = 470f / innerTexture.GetWidth();
            inner.Position = new Vector2(0, -22f);
            inner.Scale = new Vector2(scale * (2f - breathe), scale * breathe);
            inner.Rotation = .015f * Mathf.Sin(time * .7f);
            inner.Modulate = new Color(.8f, .95f, 1f, .38f + .12f * (.5f + .5f * Mathf.Sin(time * 1.9f + 1.2f)));
        }
        var bolts = root.GetNodeOrNull<Node2D>("StormBolts");
        if (bolts is null) return;
        for (int i = 0; i < Bolts; i++)
        {
            float angle = i * Mathf.Tau / Bolts + time * .16f;
            var foot = Ground(angle, Radius + 5f);
            float height = 46f + 28f * (.5f + .5f * Mathf.Sin(time * 4f + i * 2.1f));
            var points = new Vector2[7];
            for (int p = 0; p < points.Length; p++)
            {
                float f = p / 6f;
                points[p] = foot + new Vector2(p == 0 ? 0 : 12f * Mathf.Sin(p * 13f + i + MathF.Floor(time * 12f)), -height * f);
            }
            bolts.GetChild<Line2D>(i).Points = points;
        }
    }
}
