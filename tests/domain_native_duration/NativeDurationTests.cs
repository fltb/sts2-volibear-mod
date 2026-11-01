using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

// Native SetAmount and production Domain getters; only minimal owner/event metadata.
// No constructor/engine/combat/probe shortcut or claim of permanent-domain gameplay.
var power = (DomainPower)RuntimeHelpers.GetUninitializedObject(typeof(DomainPower));
var owner = (Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
const BindingFlags flags = BindingFlags.Instance | BindingFlags.NonPublic;
typeof(AbstractModel).GetField("<IsMutable>k__BackingField", flags)!.SetValue(power, true);
typeof(PowerModel).GetField("_owner", flags)!.SetValue(power, owner);
int checks = 0;
void Check(bool condition, string label) { checks++; if (!condition) throw new Exception(label); }
Check(CardResolutionDuration.Permanent == 999_999_999, "reserved sentinel fits actual native ceiling");
power.SetAmount(int.MaxValue, silent: true);
Check(power.Amount == 999_999_999 && power.Amount != int.MaxValue, "native SetAmount really clamps obsolete sentinel");
Check(power.IsPermanent && power.DisplayAmount == 0, "clamped stored value now selects production permanent display");
power.SetAmount(5, silent: true);
Check(!power.IsPermanent && power.DisplayAmount == 5, "finite duration remains finite");
power.SetAmount(CardResolutionDuration.Permanent, silent: true);
Check(power.Amount == CardResolutionDuration.Permanent && power.IsPermanent && power.DisplayAmount == 0,
    "legal permanent sentinel survives native setter without loss");
Check(CardResolutionDuration.Extend(CardResolutionDuration.Permanent, 3) == CardResolutionDuration.Permanent, "finite reapplication preserves permanent duration");
Check(CardResolutionDuration.Extend(2, 3) == 5, "ordinary finite stacking unchanged");
foreach (var pair in new[] { (999_999_998, 1), (0, 999_999_999), (0, 1_000_000_000), (0, 0), (0, -1) })
{
    try { CardResolutionDuration.Extend(pair.Item1, pair.Item2); throw new Exception("invalid finite boundary accepted"); }
    catch (ArgumentOutOfRangeException) { checks++; }
}
Console.WriteLine($"NATIVE_DOMAIN_DURATION_METADATA_OK checks={checks}; nativeSetAmount=EXECUTED; gameplay=NOT_RUN");
