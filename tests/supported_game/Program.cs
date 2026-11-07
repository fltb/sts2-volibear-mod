using Volibear.Core;

var checkedCases = 0;
const string Valid = "{\"version\":\"v0.107.1\",\"commit\":\"59260271\",\"branch\":\"v0.107.1\"}";
const string Newer = "{\"version\":\"v0.108.0\",\"commit\":\"deadbeef\",\"branch\":\"v0.108.0\"}";
SupportedGameBuild.EnsureRelease(Valid);
if (!SupportedGameBuild.LastCheckSummary.Contains("build=verified")) throw new Exception("Pinned build not recorded as verified");
SupportedGameBuild.EnsureRelease("\uFEFF" + Valid);
checkedCases += 2;

// Unknown build without a registered structural check must stop before patching.
Reject(() => SupportedGameBuild.EnsureRelease(Newer), "no native compatibility self-check");
checkedCases++;
// Unknown build whose native surface is missing must be refused with the failing member named.
SupportedGameBuild.StructuralCheck = () => throw new InvalidOperationException("Hook.ModifyHandDraw");
Reject(() => SupportedGameBuild.EnsureRelease(Newer), "Hook.ModifyHandDraw");
checkedCases++;
// Unknown build whose whole native surface exists may load, but only as unverified.
SupportedGameBuild.StructuralCheck = () => { };
SupportedGameBuild.EnsureRelease(Newer);
if (!SupportedGameBuild.LastCheckSummary.Contains("build=unverified-compatible")) throw new Exception("Unverified build not reported");
checkedCases++;

foreach (var invalid in new[]
{
    "{}", "[]", "null", "{", "{\"version\":123}",
    "{\"version\":\"v0.108.0\"}",
    "{\"version\":\"v0.107.1\"}"
})
{
    Reject(() => SupportedGameBuild.EnsureRelease(invalid), "cannot determine");
    checkedCases++;
}

var directory = Path.Combine(Path.GetTempPath(), "volibear-version-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(directory);
try
{
    var executable = Path.Combine(directory, "SlayTheSpire2");
    Reject(() => SupportedGameBuild.EnsureInstalled(executable), "missing release_info.json");
    checkedCases++;
    var release = Path.Combine(directory, "release_info.json");
    File.WriteAllText(release, Valid);
    SupportedGameBuild.EnsureInstalled(executable);
    if (File.ReadAllText(release) != Valid) throw new Exception("Release file was changed");
    checkedCases++;
}
finally { Directory.Delete(directory, recursive: true); }
Console.WriteLine($"SUPPORTED_GAME_PASS cases={checkedCases} native-gameplay=NOT_RUN");

static void Reject(Action action, string expected)
{
    try { action(); }
    catch (InvalidOperationException error) when (error.Message.Contains("Volibear:") &&
                                                error.Message.Contains(expected, StringComparison.Ordinal)) { return; }
    throw new Exception("Unsupported or unreadable release accepted; expected: " + expected);
}
