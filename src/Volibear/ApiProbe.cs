using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using Godot;

namespace Volibear;

// Test-only reflection dump. Prints authoritative signatures of the game types this mod
// implements against, so card code is written from the installed assembly, not from guesses.
internal static class ApiProbe
{
    private static readonly Type[] Roots =
    {
        typeof(MegaCrit.Sts2.Core.Models.CardModel),
        typeof(MegaCrit.Sts2.Core.Models.CharacterModel),
        typeof(MegaCrit.Sts2.Core.Models.CardPoolModel),
        typeof(MegaCrit.Sts2.Core.Models.RelicModel),
        typeof(MegaCrit.Sts2.Core.Models.PowerModel),
        typeof(MegaCrit.Sts2.Core.Models.AbstractModel),
        typeof(MegaCrit.Sts2.Core.Localization.LocString),
        typeof(MegaCrit.Sts2.Core.Localization.LocManager),
        typeof(MegaCrit.Sts2.Core.Localization.LocTable),
    };

    public static void Install()
    {
        MegaCrit.Sts2.Core.Combat.CombatManager.Instance.TurnStarted += OnTurnStarted;
    }

    private static bool dumped;

    private static void OnTurnStarted(MegaCrit.Sts2.Core.Combat.CombatState state)
    {
        if (dumped) return;
        dumped = true;
        Dump();
    }

    public static void Dump()
    {
        var output = new StringBuilder();
        foreach (var type in Roots)
        {
            Section(output, $"### TYPE {type.FullName} abstract={type.IsAbstract}", () => AppendMembers(output, type));
        }

        Section(output, "### IRONCLAD FIELDS", () =>
        {
            var ironclad = MegaCrit.Sts2.Core.Models.ModelDb.Character<
                MegaCrit.Sts2.Core.Models.Characters.Ironclad>();
            for (var type = ironclad.GetType(); type is not null; type = type.BaseType)
                foreach (var field in type.GetFields(BindingFlags.NonPublic | BindingFlags.Public
                             | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                {
                    object? value;
                    try { value = field.GetValue(ironclad); } catch { continue; }
                    var rendered = value as string ?? (value is null ? "null" : value.GetType().Name);
                    output.AppendLine($"  field {type.Name}.{field.Name}={rendered}");
                }
        });

        Section(output, "### DYNAMIC VARS", () =>
        {
            var dynamicVars = typeof(MegaCrit.Sts2.Core.Models.CardModel).Assembly
                .GetTypes()
                .Where(t => t.Namespace == "MegaCrit.Sts2.Core.Localization.DynamicVars" && !t.IsEnum)
                .OrderBy(t => t.Name);
            foreach (var type in dynamicVars)
            {
                output.AppendLine($"### VAR {type.Name} : {type.BaseType?.Name}");
                AppendConstructors(output, type);
            }
        });

        Section(output, "### SAMPLE", () => AppendSampleCard(output));
        Section(output, "### IRONCLAD PATHS", () =>
        {
            var ironclad = MegaCrit.Sts2.Core.Models.ModelDb.Character<
                MegaCrit.Sts2.Core.Models.Characters.Ironclad>();
            foreach (var property in ironclad.GetType().GetProperties(
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            {
                if (property.PropertyType != typeof(string)) continue;
                object? value;
                try { value = property.GetValue(ironclad); } catch { continue; }
                if (value is string text && text.Length > 0)
                    output.AppendLine($"  path {property.Name}={text}");
            }
        });

        GD.Print("[Volibear] API_DUMP_BEGIN");
        foreach (var line in output.ToString().Split('\n'))
            GD.Print("[Volibear] API " + line.TrimEnd());
        GD.Print("[Volibear] API_DUMP_DONE");
    }

    private static void Section(StringBuilder output, string title, Action body)
    {
        output.AppendLine(title);
        try
        {
            body();
        }
        catch (Exception exception)
        {
            output.AppendLine($"  !! {exception.GetType().Name}: {exception.Message}");
        }
    }

    private static void AppendSampleCard(StringBuilder output)
    {
        var strike = MegaCrit.Sts2.Core.Models.ModelDb.Card<MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad>();
        output.AppendLine("### SAMPLE StrikeIronclad");
        output.AppendLine($"runtimeType={strike.GetType().FullName} base={strike.GetType().BaseType?.FullName}");
        foreach (var name in new[] { "PortraitPath", "FramePath", "EnergyIconPath", "PortraitPngPath",
                                     "CanonicalEnergyCost", "Type", "TargetType", "Keywords", "DynamicVars" })
        {
            var property = strike.GetType().GetProperty(name,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                ?? strike.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public);
            if (property is null) { output.AppendLine($"  {name}=<missing>"); continue; }
            object? value;
            try { value = property.GetValue(strike); }
            catch (Exception exception) { output.AppendLine($"  {name}=<throws {exception.GetType().Name}>"); continue; }
            output.AppendLine($"  {name}={Describe(value)}");
        }
    }

    private static string Describe(object? value)
    {
        if (value is null) return "null";
        if (value is string text) return text;
        if (value is System.Collections.IEnumerable items and not string)
            return "[" + string.Join(",", items.Cast<object?>().Select(Describe).Take(12)) + "]";
        return value.ToString() ?? "?";
    }

    private static void AppendMembers(StringBuilder output, Type type)
    {
        AppendConstructors(output, type);
        foreach (var property in type.GetProperties(BindingFlags.Public | BindingFlags.NonPublic
                     | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
                     .OrderBy(p => p.Name))
        {
            var accessor = property.GetMethod ?? property.SetMethod;
            if (accessor is null) continue;
            var access = accessor.IsPublic ? "public" : accessor.IsFamily ? "protected" : "private";
            var kind = property.GetMethod is { IsAbstract: true } ? "abstract" : property.GetMethod is { IsVirtual: true } ? "virtual" : "";
            output.AppendLine($"  prop {access} {kind} {property.PropertyType.Name} {property.Name}");
        }
        foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic
                     | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
                     .Where(m => !m.IsSpecialName).OrderBy(m => m.Name))
        {
            var access = method.IsPublic ? "public" : method.IsFamily ? "protected" : "private";
            var kind = method.IsAbstract ? "abstract" : method.IsVirtual ? "virtual" : "";
            var parms = string.Join(", ", method.GetParameters().Select(p => $"{p.ParameterType.Name} {p.Name}"));
            output.AppendLine($"  method {access} {kind} {method.ReturnType.Name} {method.Name}({parms})");
        }
    }

    private static void AppendConstructors(StringBuilder output, Type type)
    {
        foreach (var ctor in type.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            var access = ctor.IsPublic ? "public" : ctor.IsFamily ? "protected" : "private";
            var parms = string.Join(", ", ctor.GetParameters().Select(p => $"{p.ParameterType.Name} {p.Name}"));
            output.AppendLine($"  ctor {access} ({parms})");
        }
    }
}
