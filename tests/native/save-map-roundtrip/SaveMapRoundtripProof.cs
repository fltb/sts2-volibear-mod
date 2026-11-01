using System;
using System.Text.Json;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Runs;

static void Need(bool ok, string why) { if (!ok) throw new Exception(why); }
var info = JsonSerializationUtility.GetTypeInfo<SerializableMapPoint>();
foreach (var original in new[] { false, true })
{
    var source = new SerializableMapPoint { CanBeModified = original };
    var first = JsonSerializer.Serialize(source, info);
    using var firstJson = JsonDocument.Parse(first);
    Need(firstJson.RootElement.TryGetProperty("can_modify", out var flag) == original, "Native omission must exactly track false default");
    if (original) Need(flag.ValueKind == JsonValueKind.True, "True must be actual bool");
    var restored = JsonSerializer.Deserialize(first, info)!;
    Need(restored.CanBeModified, "Native ctor default is true after omitted false");
    var second = JsonSerializer.Serialize(restored, info);
    using var secondJson = JsonDocument.Parse(second);
    Need(secondJson.RootElement.GetProperty("can_modify").ValueKind == JsonValueKind.True, "Native rewrite must emit true");
    foreach (var property in firstJson.RootElement.EnumerateObject())
        Need(property.Value.GetRawText() == secondJson.RootElement.GetProperty(property.Name).GetRawText(), "Unrelated native property changed: " + property.Name);
    Console.WriteLine($"native-original={original} first={first} second={second}");
}
// Explicit false is preserved by deserialization but omitted on serialization; it is NOT the
// native fresh-checkpoint input produced above. Numeric 1 must not be treated as bool true.
Need(!JsonSerializer.Deserialize("{\"can_modify\":false}", info)!.CanBeModified, "Explicit false must not default to true");
bool numericRejected=false;
try { JsonSerializer.Deserialize("{\"can_modify\":1}", info); } catch (JsonException) { numericRejected=true; }
Need(numericRejected,"Native bool converter accepted numeric1");
Console.WriteLine("PASS actual pinned JsonSerializationUtility + SerializableMapPoint; no Godot game or save file used");
