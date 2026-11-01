using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Entities.Cards;

// Actual pinned native CardEnergyCost, but no game/combat/TestMode. Null owner is
// intentional: this test touches only the owner-independent constructor/metadata.
// It is NOT payment acceptance or a substitute for native F01.
var cost = new CardEnergyCost(null!, 0, true);
var canonical = typeof(CardEnergyCost).GetField("<Canonical>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic)!;
var costsX = typeof(CardEnergyCost).GetField("<CostsX>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic)!;
Check(cost.CostsX && cost.Canonical == 0, "native X metadata baseline");
Check(ReadX(cost), "JIT consumer sees native X baseline");
canonical.SetValue(cost, 1);
costsX.SetValue(cost, false);
Check(!cost.CostsX && !ReadX(cost) && cost.Canonical == 1, "native metadata and JIT consumer agree after same-object update");
CaptureIfX(cost, 9); // Non-X branch must not enter owner-dependent native X setter.
Check((int)canonical.GetValue(cost)! == 1 && !(bool)costsX.GetValue(cost)!, "raw and getter agree");
canonical.SetValue(cost, 0);
costsX.SetValue(cost, true);
Check(cost.CostsX && cost.Canonical == 0 && cost.CapturedXValue == 0, "reset restores metadata, never captured another X");
Console.WriteLine("BEAST_NATIVE_COST_METADATA_OK assertions=5; gameplay=NOT_RUN");

static void Check(bool condition, string name) { if (!condition) throw new Exception(name); }
[MethodImpl(MethodImplOptions.NoInlining)]
static bool ReadX(CardEnergyCost cost) => cost.CostsX;
[MethodImpl(MethodImplOptions.NoInlining)]
static void CaptureIfX(CardEnergyCost cost, int value)
{
    if (cost.CostsX) cost.CapturedXValue = value;
}
