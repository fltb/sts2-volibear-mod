using System;
using Godot;

namespace Volibear.Presentation;

/// <summary>Foot-anchored storm volume, drawn within the actor's visual layer, below native status UI.</summary>
internal static class DomainStormRing
{
    internal const float Radius = 300f;
    private const int Panels = 48, Bolts = 12;
    private static Vector2 Ground(float angle, float radius) => new(Mathf.Cos(angle) * radius, Mathf.Sin(angle) * radius * .24f - 5f);
    private static CanvasItemMaterial Light() => new() { BlendMode = CanvasItemMaterial.BlendModeEnum.Add, LightMode = CanvasItemMaterial.LightModeEnum.Unshaded };

    internal static void Populate(Node2D root)
    {
        // Never use negative global Z (behind the opaque room) or raise above health/status UI.
        root.ZIndex = 0;
        for (int i = 0; i < 6; i++)
            root.AddChild(new Line2D { Name = "LightningArc" + i, Antialiased = true,
                Width = i == 0 ? 58 : i == 1 ? 24 : 4,
                DefaultColor = i == 0 ? new Color(.04f, .38f, 1f, .16f) : i == 1 ? new Color(.04f, .55f, 1f, .48f) : new Color(.55f, .91f, 1f, .95f),
                Material = Light() });
        var wall = new Node2D { Name = "StormWall" };
        root.AddChild(wall);
        var light = Light();
        for (int i = 0; i < Panels; i++)
        {
            float a = i * Mathf.Tau / Panels, b = (i + 1) * Mathf.Tau / Panels;
            var p = Ground(a, Radius); var q = Ground(b, Radius);
            float height = 38f + 8f * Mathf.Sin(a * 3f);
            wall.AddChild(new Polygon2D { Name = "StormBand" + i, Material = light,
                Polygon = new[] { p, q, q - new Vector2(0, height), p - new Vector2(0, height) },
                VertexColors = new[] { new Color(.05f,.5f,1f,.08f), new Color(.05f,.5f,1f,.08f), new Color(.1f,.65f,1f,.28f), new Color(.1f,.65f,1f,.28f) } });
        }
        var bolts = new Node2D { Name = "StormBolts" };
        root.AddChild(bolts);
        for (int i = 0; i < Bolts; i++)
            bolts.AddChild(new Line2D { Name = "RisingBolt" + i, Width = 2.8f, Antialiased = true,
                DefaultColor = new Color(.35f, .8f, 1f, .9f), Material = light });
        Animate(root, Time.GetTicksMsec() / 1000f);
    }

    internal static void Animate(Node2D root, float time)
    {
        for (int arc = 0; arc < 6; arc++)
        {
            var points = new Vector2[arc < 2 ? 97 : 25];
            for (int p = 0; p < points.Length; p++)
            {
                float angle = p / (float)(points.Length - 1) * Mathf.Tau * (arc < 2 ? 1f : .28f)
                    + time * (arc % 2 == 0 ? .65f : -.8f) + arc * 1.7f;
                float jitter = arc < 2 ? 2f * Mathf.Sin(angle * 9f + time * 3f)
                    : 13f * Mathf.Sin(p * 17.1f + MathF.Floor(time * 14f) * 2.3f + arc);
                points[p] = Ground(angle, Radius + (arc - 2) * 5f + jitter);
                if (arc >= 2) points[p] -= new Vector2(0, (arc - 2) * 11f);
            }
            root.GetChild<Line2D>(arc).Points = points;
        }
        var bolts = root.GetNode<Node2D>("StormBolts");
        for (int i = 0; i < Bolts; i++)
        {
            float angle = i * Mathf.Tau / Bolts + time * .16f;
            var foot = Ground(angle, Radius + 5f);
            float height = 48f + 25f * (.5f + .5f * Mathf.Sin(time * 4f + i * 2.1f));
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
