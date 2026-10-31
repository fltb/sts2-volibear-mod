// integration_source_uncompiled. Loads actual V5 alpha atlas assets.
using System;
using System.Collections.Generic;
using System.Text.Json;
using Godot;

namespace VolibearMod.ArtV5;

public partial class VolibearVfxPlayer : Node2D
{
    private sealed record Effect(SpriteFrames Frames, bool Loop, string Anchor, Vector2 Pivot, int Z,
        bool HasSegment, Vector2 SegmentSource, Vector2 SegmentTarget);
    private static readonly HashSet<string> TargetAnchors = new(StringComparer.Ordinal)
    {
        "target_contact", "target_ground", "target_status", "resolved_enemy_group",
        "selected_card", "owner_to_selected_card", "converted_attack_card", "converted_other_card",
        "draw_pile_to_hand", "source_pile_to_hand", "card_to_discard_pile", "exhausted_card",
        "card_cost_anchor", "played_card"
    };
    private readonly Dictionary<string, Effect> _effects = new(StringComparer.Ordinal);
    private readonly Dictionary<ulong, AnimatedSprite2D> _active = [];
    private readonly Dictionary<string, ulong> _loops = new(StringComparer.Ordinal);
    private ulong _next;

    public void LoadManifest(string path = "res://VolibearArt/vfx/manifest.json")
    {
        using var f = Godot.FileAccess.Open(path, Godot.FileAccess.ModeFlags.Read)
            ?? throw new InvalidOperationException($"Missing VFX manifest: {path}");
        using var d = JsonDocument.Parse(f.GetAsText());
        string folder = path[..(path.LastIndexOf('/') + 1)];
        foreach (var item in d.RootElement.GetProperty("effects").EnumerateArray())
        {
            string id = item.GetProperty("id").GetString()!;
            string image = item.GetProperty("atlas").GetProperty("image").GetString()!;
            var texture = GD.Load<Texture2D>(folder + image)
                ?? throw new InvalidOperationException($"Missing VFX texture: {image}");
            var frames = new SpriteFrames(); frames.RemoveAnimation("default");
            frames.AddAnimation(id);
            frames.SetAnimationSpeed(id, item.TryGetProperty("fps", out var fps) ? fps.GetDouble() : d.RootElement.GetProperty("fps").GetDouble());
            bool loop = item.GetProperty("loop").GetBoolean();
            frames.SetAnimationLoop(id, loop);
            foreach (var frame in item.GetProperty("frames").EnumerateArray())
            {
                var r = frame.GetProperty("rect");
                frames.AddFrame(id, new AtlasTexture {Atlas = texture,
                    Region = new Rect2(r[0].GetSingle(),r[1].GetSingle(),r[2].GetSingle(),r[3].GetSingle()), FilterClip = true});
            }
            var p = item.GetProperty("pivot_px");
            string anchor=item.GetProperty("anchor").GetString()!;
            Vector2 segmentSource=Vector2.Zero, segmentTarget=Vector2.Zero;
            bool hasSegment=item.TryGetProperty("segment_anchors_px",out var endpoints);
            if(hasSegment)
            {
                var s=endpoints.GetProperty("source"); var t=endpoints.GetProperty("target");
                segmentSource=new Vector2(s[0].GetSingle(),s[1].GetSingle());
                segmentTarget=new Vector2(t[0].GetSingle(),t[1].GetSingle());
                if(segmentSource.DistanceSquaredTo(segmentTarget)<0.000001f)
                    throw new InvalidOperationException($"Coincident authored VFX endpoints: {id}");
            }
            Vector2 pivot=new(p[0].GetSingle(),p[1].GetSingle());
            // Feral transfer includes a card frame: preserve its aspect ratio and
            // anchor the authored arrival point to the selected card's portrait.
            // source_anchor_px remains a local incoming-path hint, not a world tether.
            if(anchor=="owner_to_selected_card" && item.TryGetProperty("target_anchor_px",out var arrival))
                pivot=new Vector2(arrival[0].GetSingle(),arrival[1].GetSingle());
            _effects.Add(id, new(frames, loop, anchor, pivot,item.GetProperty("layer_z").GetInt32(),
                hasSegment,segmentSource,segmentTarget));
        }
    }

    /// <summary>Global positions come from the committed gameplay target, not mouse prediction.</summary>
    public ulong Spawn(string id, Vector2 sourceGlobal, Vector2 targetGlobal)
    {
        if (!_effects.TryGetValue(id, out var e)) return 0;
        if (e.Loop && _loops.TryGetValue(id, out var existing) && _active.ContainsKey(existing)) return existing;
        Vector2 a = ToLocal(sourceGlobal), b = ToLocal(targetGlobal);
        var sprite = new AnimatedSprite2D {SpriteFrames = e.Frames, Centered = false,
            Offset = -e.Pivot, ZIndex = e.Z, Position = a};
        if (e.HasSegment)
        {
            // Map each effect's own endpoints. Lifesteal is authored right-to-left.
            var authored=e.SegmentTarget-e.SegmentSource; var vector=b-a;
            if(vector.LengthSquared()<0.000001f) {sprite.Free();return 0;}
            var u=authored.Normalized(); var v=new Vector2(-u.Y,u.X);
            var worldU=vector.Normalized(); var worldV=new Vector2(-worldU.Y,worldU.X);
            float stretch=vector.Length()/authored.Length();
            sprite.Offset=-e.SegmentSource;
            sprite.Transform=new Transform2D(worldU*stretch*u.X+worldV*v.X,
                worldU*stretch*u.Y+worldV*v.Y,a);
        }
        else if (TargetAnchors.Contains(e.Anchor)) sprite.Position = b;
        AddChild(sprite);
        ulong token = ++_next; _active[token] = sprite;
        if (e.Loop) _loops[id] = token;
        if (!e.Loop) sprite.AnimationFinished += () => Stop(token);
        sprite.Play(id);
        return token;
    }

    public void Stop(ulong token)
    {
        if (!_active.Remove(token, out var sprite) || !GodotObject.IsInstanceValid(sprite)) return;
        string? loopId = null;
        foreach (var pair in _loops) if (pair.Value == token) {loopId=pair.Key;break;}
        if(loopId!=null) _loops.Remove(loopId);
        sprite.Stop(); sprite.QueueFree();
    }

    public void StopLoop(string id)
    {
        if(_loops.TryGetValue(id,out var token)) Stop(token);
    }

    public void StopAllOwned()
    {
        foreach (var sprite in _active.Values)
            if (GodotObject.IsInstanceValid(sprite)) {sprite.Stop(); sprite.QueueFree();}
        _active.Clear(); _loops.Clear();
    }
    public override void _ExitTree() => StopAllOwned();
}
