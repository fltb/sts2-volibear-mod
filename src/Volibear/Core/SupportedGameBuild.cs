using System;
using System.IO;
using System.Text.Json;

namespace Volibear.Core;

/// <summary>
/// The pinned release is the only build we have actually acceptance-tested, but the mod must not
/// demand a rebuild per game patch. The manifest's minimum version expresses the lower bound; a
/// structural self-check (registered by the mod entry) verifies that the native surface we use is
/// still present on an unknown/newer build. When it is, the mod loads with an unverified-build note
/// instead of refusing outright; when it is not, initialization stops before any patch is applied.
/// </summary>
public static class SupportedGameBuild
{
    public const string Version = "v0.107.1";
    public const string Commit = "59260271";

    /// <summary>Native-surface verifier for a build other than the pinned one. It must throw a
    /// descriptive <see cref="InvalidOperationException"/> when a required member is missing.</summary>
    public static Action? StructuralCheck { get; set; }

    /// <summary>Human-readable outcome of the last successful check, for the boot log.</summary>
    public static string LastCheckSummary { get; private set; } = "build=not-checked";

    public static void EnsureInstalled(string executablePath)
    {
        var directory = Path.GetDirectoryName(Path.GetFullPath(executablePath))
            ?? throw new InvalidOperationException("Volibear: cannot locate the installed game directory.");
        var release = Path.Combine(directory, "release_info.json");
        if (!File.Exists(release))
            throw new InvalidOperationException("Volibear: missing release_info.json beside the game executable; " +
                "cannot determine the installed game build.");
        EnsureRelease(File.ReadAllText(release));
    }

    public static void EnsureRelease(string json)
    {
        string? version, commit;
        try
        {
            // File.ReadAllText accepts BOM-prefixed UTF-8, and direct diagnostic callers may
            // pass the BOM as a character. Neither path changes the installed release file.
            using var document = JsonDocument.Parse(json.TrimStart('\uFEFF'));
            var root = document.RootElement;
            version = StringProperty(root, "version");
            commit = StringProperty(root, "commit");
        }
        catch (JsonException error)
        {
            throw new InvalidOperationException("Volibear: invalid installed release_info.json; " +
                "cannot determine the installed game build.", error);
        }
        if (version is null || commit is null)
            throw new InvalidOperationException("Volibear: release_info.json is missing version/commit; " +
                "cannot determine the installed game build.");
        if (version == Version && commit == Commit)
        {
            LastCheckSummary = $"build=verified target={Version}/{Commit}";
            return;
        }
        // Unknown build: only proceed when every native member the mod actually uses still exists.
        if (StructuralCheck is null)
            throw new InvalidOperationException($"Volibear: game build {version}/{commit} differs from the " +
                $"acceptance-tested {Version}/{Commit}, and no native compatibility self-check is registered. " +
                "No Volibear patches were installed.");
        try
        {
            StructuralCheck();
        }
        catch (InvalidOperationException error)
        {
            throw new InvalidOperationException($"Volibear: game build {version}/{commit} is missing native " +
                $"surface this mod needs ({error.Message}). No Volibear patches were installed.", error);
        }
        LastCheckSummary = $"build=unverified-compatible found={version}/{commit} tested={Version}/{Commit}";
    }

    private static string? StringProperty(JsonElement root, string name) =>
        root.ValueKind == JsonValueKind.Object && root.TryGetProperty(name, out var value) &&
        value.ValueKind == JsonValueKind.String ? value.GetString() : null;
}
