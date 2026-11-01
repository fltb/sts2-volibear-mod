using System.Text.Json;

namespace Volibear.Core;

/// <summary>
/// The manifest's minimum version cannot express the upper bound of our native adapters.
/// Check the installed release before registering content or installing any Harmony patch.
/// </summary>
public static class SupportedGameBuild
{
    public const string Version = "v0.107.1";
    public const string Commit = "59260271";

    public static void EnsureInstalled(string executablePath)
    {
        var directory = Path.GetDirectoryName(Path.GetFullPath(executablePath))
            ?? throw new InvalidOperationException("Volibear: cannot locate the installed game directory.");
        var release = Path.Combine(directory, "release_info.json");
        if (!File.Exists(release))
            throw new InvalidOperationException("Volibear: missing release_info.json beside the game executable; " +
                $"this build requires StS2 {Version} / {Commit}.");
        EnsureRelease(File.ReadAllText(release));
    }

    public static void EnsureRelease(string json)
    {
        try
        {
            // File.ReadAllText accepts BOM-prefixed UTF-8, and direct diagnostic callers may
            // pass the BOM as a character. Neither path changes the installed release file.
            using var document = JsonDocument.Parse(json.TrimStart('\uFEFF'));
            var root = document.RootElement;
            var version = StringProperty(root, "version");
            var commit = StringProperty(root, "commit");
            if (version != Version || commit != Commit)
                throw new InvalidOperationException($"Volibear: requires StS2 {Version} / {Commit}; " +
                    $"found {version ?? "missing version"} / {commit ?? "missing commit"}. " +
                    "Install a matching mod build before enabling it. No Volibear patches were installed.");
        }
        catch (JsonException error)
        {
            throw new InvalidOperationException("Volibear: invalid installed release_info.json; " +
                $"this build requires StS2 {Version} / {Commit}.", error);
        }
    }

    private static string? StringProperty(JsonElement root, string name) =>
        root.ValueKind == JsonValueKind.Object && root.TryGetProperty(name, out var value) &&
        value.ValueKind == JsonValueKind.String ? value.GetString() : null;
}
