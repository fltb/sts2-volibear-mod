using Godot;
using MegaCrit.Sts2.Core.Modding;

namespace Volibear;

[ModInitializer(nameof(Initialize))]
public static class ModEntry
{
    public static void Initialize()
    {
        var expectedDirectory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT");
        if (!string.IsNullOrEmpty(expectedDirectory))
        {
            var actual = System.IO.Path.GetFullPath(OS.GetUserDataDir());
            var expected = System.IO.Path.GetFullPath(expectedDirectory);
            if (actual != expected || MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized)
                throw new System.InvalidOperationException("Volibear test isolation assertion failed");
            GD.Print("[Volibear] ISOLATION_OK steam=false");
            if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "baseline")
                DevelopmentBootstrap.Install();
        }
        GD.Print("[Volibear] LOAD_OK version=0.1.0 target=0.107.1 phase=M0-probe gameplay=not-implemented");
    }
}
