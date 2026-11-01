using Volibear.Core;

var checkedCases = 0;
const string Valid = "{\"version\":\"v0.107.1\",\"commit\":\"59260271\",\"branch\":\"v0.107.1\"}";
SupportedGameBuild.EnsureRelease(Valid);
SupportedGameBuild.EnsureRelease("\uFEFF" + Valid);
checkedCases += 2;
foreach (var invalid in new[]
{
    "{}", "[]", "null", "{", "{\"version\":123}",
    "{\"version\":\"v0.108.0\",\"commit\":\"59260271\"}",
    "{\"version\":\"v0.107.1\",\"commit\":\"other\"}",
    "{\"version\":\"v0.107.1\"}"
})
{
    Reject(() => SupportedGameBuild.EnsureRelease(invalid));
    checkedCases++;
}
var directory = Path.Combine(Path.GetTempPath(), "volibear-version-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(directory);
try
{
    var executable = Path.Combine(directory, "SlayTheSpire2");
    Reject(() => SupportedGameBuild.EnsureInstalled(executable));
    checkedCases++;
    var release = Path.Combine(directory, "release_info.json");
    File.WriteAllText(release, Valid);
    SupportedGameBuild.EnsureInstalled(executable);
    if (File.ReadAllText(release) != Valid) throw new Exception("Release file was changed");
    checkedCases++;
}
finally { Directory.Delete(directory, recursive: true); }
Console.WriteLine($"SUPPORTED_GAME_PASS cases={checkedCases} native-gameplay=NOT_RUN");

static void Reject(Action action)
{
    try { action(); }
    catch (InvalidOperationException error) when (error.Message.Contains("Volibear:") &&
                                                error.Message.Contains("v0.107.1")) { return; }
    throw new Exception("Unsupported or unreadable release accepted");
}
