using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.addons.mega_text;
using Volibear.Presentation;
static class Program
{
    static int checks;
    static void Need(bool ok, string message) { checks++; if (!ok) throw new Exception(message); }
    static void Main()
    {
        Need(AccessTools.DeclaredField(typeof(NPower), "_model").FieldType == typeof(PowerModel), "Pinned nullable model field");
        Need(AccessTools.DeclaredField(typeof(NPower), "_amountLabel").FieldType == typeof(MegaLabel), "Pinned actual amount label field");
        var field = AccessTools.DeclaredField(typeof(NPowerContainer), "_powerNodes");
        Need(field.IsInitOnly && field.FieldType == typeof(List<NPower>), "Native full node list remains readonly-owned");
        var layout = AccessTools.DeclaredMethod(typeof(NPowerContainer), "UpdatePositions");
        var original = PatchProcessor.GetOriginalInstructions(layout).ToArray();
        int loads = original.Count(i => i.opcode == OpCodes.Ldfld && Equals(i.operand, field));
        Need(loads >= 6, "Pinned layout reads full list for count, width, positions and centering");
        var hoverGetter = AccessTools.PropertyGetter(typeof(PowerModel), nameof(PowerModel.HoverTips));
        int before = Harmony.GetPatchInfo(hoverGetter)?.Owners.Count ?? 0;
        PowerStackVisual.Install(); PowerStackVisual.Install();
        Need((Harmony.GetPatchInfo(hoverGetter)?.Owners.Count ?? 0) == before, "Global model getter unpatched");
        foreach (var method in new MethodBase[] {
            layout, AccessTools.DeclaredMethod(typeof(NPowerContainer), nameof(NPowerContainer._EnterTree)),
            AccessTools.DeclaredMethod(typeof(NPower), nameof(NPower._Ready)),
            AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)),
            AccessTools.DeclaredMethod(typeof(NPower), "RefreshAmount"),
            AccessTools.DeclaredMethod(typeof(NPower), "OnHovered"),
            AccessTools.DeclaredMethod(typeof(NPower), "OnUnhovered"),
            AccessTools.DeclaredMethod(typeof(NCreature), nameof(NCreature.ShowHoverTips)) })
        {
            var info = Harmony.GetPatchInfo(method)!;
            Need(info.Owners.Count(o => o == "Volibear.PowerStackVisual") == 1, "Pinned UI entry installed once: " + method.Name);
        }
        var rewritten = PatchProcessor.GetCurrentInstructions(layout).ToArray();
        Need(!rewritten.Any(i => i.opcode == OpCodes.Ldfld && Equals(i.operand, field)), "All layout-only list reads projected");
        Need(PatchProcessor.GetOriginalInstructions(AccessTools.DeclaredMethod(typeof(NPowerContainer), "Remove"))
            .Any(i => i.opcode == OpCodes.Ldfld && Equals(i.operand, field)), "Native Remove still sees every model node");
        Console.WriteLine($"POWER_STACK_VISUAL_ABI_PASS checks={checks} native-layout-loads={loads} Godot-render=NOT_RUN");
    }
}
