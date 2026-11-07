using Volibear.Core;

var checks = 0;
const string Pinned = "{\"version\":\"v0.107.1\",\"commit\":\"59260271\"}";
const string Newer = "{\"version\":\"v0.108.0\",\"commit\":\"deadbeef\"}";

// The pinned release must never consult the structural check.
SupportedGameBuild.StructuralCheck = () => throw new Exception("structural check ran on the pinned release");
SupportedGameBuild.EnsureRelease(Pinned);
if (!SupportedGameBuild.LastCheckSummary.Contains("build=verified")) throw new Exception("pinned build not verified");
checks++;

// The curated native surface must resolve completely against the installed game assemblies.
NativeCompatibility.Verify();
checks++;

// An unknown build passes only through the structural verifier and is reported unverified.
SupportedGameBuild.StructuralCheck = NativeCompatibility.Verify;
SupportedGameBuild.EnsureRelease(Newer);
if (!SupportedGameBuild.LastCheckSummary.Contains("build=unverified-compatible"))
    throw new Exception("unknown build not reported as unverified: " + SupportedGameBuild.LastCheckSummary);
checks++;

// A missing native member is named and blocks initialization.
SupportedGameBuild.StructuralCheck = () => throw new InvalidOperationException("Hook.ModifyHandDraw");
try
{
    SupportedGameBuild.EnsureRelease(Newer);
    throw new Exception("missing native surface was accepted");
}
catch (InvalidOperationException error) when (error.Message.Contains("Hook.ModifyHandDraw") &&
                                              error.Message.Contains("No Volibear patches were installed"))
{
    checks++;
}

Console.WriteLine($"NATIVE_COMPATIBILITY_PASS checks={checks}");
