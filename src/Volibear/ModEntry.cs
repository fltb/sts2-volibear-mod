using Godot;
using MegaCrit.Sts2.Core.Modding;
using Volibear.Content;

namespace Volibear;

[ModInitializer(nameof(Initialize))]
public static class ModEntry
{
    public static void Initialize()
    {
        ContentRegistry.Register();
        var expectedDirectory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT");
        if (!string.IsNullOrEmpty(expectedDirectory))
        {
            var actual = System.IO.Path.GetFullPath(OS.GetUserDataDir());
            var expected = System.IO.Path.GetFullPath(expectedDirectory);
            if (actual != expected || MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized)
                throw new System.InvalidOperationException("Volibear test isolation assertion failed");
            GD.Print("[Volibear] ISOLATION_OK steam=false");
            var scenario = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO");
            if (scenario == "baseline")
                DevelopmentBootstrap.Install();
            else if (scenario == "api")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                ApiProbe.Install();
            }
            else if (scenario == "content")
            {
                DevelopmentBootstrap.Install(installDriver: false);
                ContentProbe.Install();
            }
        }
        GD.Print("[Volibear] LOAD_OK version=0.1.0 target=0.107.1 phase=M0-probe gameplay=not-implemented");
    }
}
