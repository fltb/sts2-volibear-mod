using System;
using System.Collections.Generic;
using System.IO;
using Godot;

namespace Volibear.Content;

/// <summary>
/// Art is loaded from the mod folder at runtime instead of being packed into a res:// bundle.
/// Godot can create textures and audio streams directly from files, so the mod needs neither a
/// Godot toolchain nor a PCK to show Volibear's own artwork.
/// </summary>
public static class VolibearAssets
{
    private static readonly Dictionary<string, Texture2D> Textures = new(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, AudioStream> Streams = new(StringComparer.OrdinalIgnoreCase);

    /// <summary>Directory that holds the deployed mod assembly; art sits beside it.</summary>
    public static string Root { get; } = Path.GetDirectoryName(typeof(VolibearAssets).Assembly.Location)
                                         ?? AppContext.BaseDirectory;

    public static string ArtRoot => Path.Combine(Root, "assets");

    public static bool Exists(string relative) => File.Exists(Path.Combine(ArtRoot, relative));

    /// <summary>Loads a PNG once and keeps the texture for the process lifetime.</summary>
    public static Texture2D? Texture(string relative)
    {
        if (Textures.TryGetValue(relative, out var cached)) return cached;
        var path = Path.Combine(ArtRoot, relative);
        if (!File.Exists(path)) return null;
        var image = new Image();
        var error = image.Load(path);
        if (error != Error.Ok)
        {
            GD.PrintErr($"[Volibear] ASSET_ERROR image {relative} {error}");
            return null;
        }
        var texture = ImageTexture.CreateFromImage(image);
        Textures[relative] = texture;
        return texture;
    }

    public static AudioStream? Ogg(string relative)
    {
        if (Streams.TryGetValue(relative, out var cached)) return cached;
        var path = Path.Combine(ArtRoot, relative);
        if (!File.Exists(path)) return null;
        var stream = AudioStreamOggVorbis.LoadFromFile(path);
        if (stream is null)
        {
            GD.PrintErr($"[Volibear] ASSET_ERROR audio {relative}");
            return null;
        }
        Streams[relative] = stream;
        return stream;
    }

    public static string ReadText(string relative)
    {
        var path = Path.Combine(ArtRoot, relative);
        return File.Exists(path) ? File.ReadAllText(path) : string.Empty;
    }

    internal static int CachedTextures => Textures.Count;
}
