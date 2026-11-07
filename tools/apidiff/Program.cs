// Dumps the public/protected native surface used by Volibear so two game channels can be diffed.
using System.Reflection;
using System.Text.Json;

var asm = Assembly.LoadFrom(Environment.GetEnvironmentVariable("VOLIBEAR_API_ASSEMBLY")!);
const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
string Vis(MethodBase m) => m.IsPublic ? "public" : m.IsFamily || m.IsFamilyOrAssembly ? "protected" : "internal";
var surface = new SortedDictionary<string, SortedDictionary<string, string>>(StringComparer.Ordinal);
foreach (var type in asm.GetTypes().Where(t => t.IsPublic || t.IsNestedPublic || t.IsNestedFamily).OrderBy(t => t.FullName, StringComparer.Ordinal))
{
    var members = new SortedDictionary<string, string>(StringComparer.Ordinal);
    foreach (var m in type.GetMethods(Flags).Where(m => m.IsPublic || m.IsFamily || m.IsFamilyOrAssembly || m.IsAssembly).OrderBy(m => m.Name, StringComparer.Ordinal))
        members["M:" + m.Name + "(" + string.Join(",", m.GetParameters().Select(p => p.ParameterType.Name)) + ")"] = Vis(m) + ":" + m.ReturnType.Name;
    foreach (var p in type.GetProperties(Flags).OrderBy(p => p.Name, StringComparer.Ordinal))
        members["P:" + p.Name] = (p.GetMethod is { } g ? Vis(g) : "?") + ":" + p.PropertyType.Name;
    foreach (var f in type.GetFields(Flags).OrderBy(f => f.Name, StringComparer.Ordinal))
        members["F:" + f.Name] = (f.IsPublic ? "public" : f.IsFamily ? "protected" : "internal") + ":" + f.FieldType.Name;
    if (members.Count > 0) surface[type.FullName!] = members;
}
Console.WriteLine(JsonSerializer.Serialize(surface, new JsonSerializerOptions { WriteIndented = false }));
