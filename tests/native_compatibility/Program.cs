using Volibear.Core;

var candidatePath = Environment.GetEnvironmentVariable("ModDll")
    ?? throw new InvalidOperationException("Set ModDll to the compiled Volibear DLL for this game channel.");
var candidate = System.Reflection.Assembly.LoadFrom(Path.GetFullPath(candidatePath));
void VerifyCandidate() => NativeCompatibility.Verify(candidate);
// Run in a separate process: assemblies with the same identity must not share a load context.
if (args.Contains("--expect-legacy-pbe-rejection"))
{
    try { VerifyCandidate(); }
    catch (InvalidOperationException error)
    {
        foreach (var reason in new[] { "SilentPlayerChoiceContext", "PossessContext", "TenderContext", "get_GameActionType", "DomainPower.AfterDeath" })
            if (!error.Message.Contains(reason, StringComparison.Ordinal))
                throw new Exception("Missing compatibility diagnostic: " + reason, error);
        Console.WriteLine("LEGACY_PBE_REJECTED choiceContexts=3 deathOverride=1");
        return;
    }
    throw new Exception("Legacy DLL unexpectedly accepted on the new PBE.");
}
var checks = 0;
const string Pinned = "{\"version\":\"v0.107.1\",\"commit\":\"59260271\"}";
const string Newer = "{\"version\":\"v0.108.0\",\"commit\":\"deadbeef\"}";

// The pinned release must never consult the structural check.
SupportedGameBuild.StructuralCheck = () => throw new Exception("structural check ran on the pinned release");
SupportedGameBuild.EnsureRelease(Pinned);
if (!SupportedGameBuild.LastCheckSummary.Contains("build=verified")) throw new Exception("pinned build not verified");
checks++;

// The curated native surface must resolve completely against the installed game assemblies.
VerifyCandidate();
checks++;

// An unknown build passes only through the structural verifier and is reported unverified.
SupportedGameBuild.StructuralCheck = VerifyCandidate;
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
