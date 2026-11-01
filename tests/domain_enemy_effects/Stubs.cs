// Isolated API doubles: these are NOT a game simulator and do not implement native rules.
// Production callbacks are linked unchanged. Real Harmony/game integration is a separate gate.
using System.Reflection;

namespace HarmonyLib
{
    public enum HarmonyPatchType { All }
    public sealed class HarmonyMethod(MethodInfo method) { public MethodInfo Method = method; }
    public sealed class Harmony(string id)
    {
        public sealed record Applied(string Id, MethodInfo Target, HarmonyMethod? Prefix, HarmonyMethod? Postfix);
        public static List<Applied> Patches = [];
        public static int FailAt;
        public static int Calls;
        public void Patch(MethodInfo target, HarmonyMethod? prefix = null, HarmonyMethod? postfix = null)
        {
            Calls++;
            if (FailAt == Calls) throw new InvalidOperationException("Injected installation failure");
            Patches.Add(new(id, target, prefix, postfix));
        }
        public void Unpatch(MethodInfo target, HarmonyPatchType type, string harmonyID) =>
            Patches.RemoveAll(patch => patch.Id == harmonyID && patch.Target == target);
    }
}
namespace MegaCrit.Sts2.Core.Combat
{
    using MegaCrit.Sts2.Core.Entities.Creatures;
    public enum CombatSide { Player, Enemy }
    public sealed class TestPlayer { public Creature Creature = null!; }
    public interface ICombatState
    {
        IReadOnlyList<TestPlayer> Players { get; }
        int RoundNumber { get; set; }
        bool ContainsCreature(Creature creature);
    }
    public sealed class TestCombat : ICombatState
    {
        public List<TestPlayer> PlayerList = [];
        public HashSet<Creature> Creatures = [];
        public IReadOnlyList<TestPlayer> Players => PlayerList;
        public int RoundNumber { get; set; } = 1;
        public bool ContainsCreature(Creature creature) => Creatures.Contains(creature);
    }
    public sealed class CombatManager
    {
        public static CombatManager Instance = new();
        public bool IsInProgress = true;
        public bool IsOverOrEnding;
        public ICombatState? Current;
        public ICombatState? DebugOnlyGetState() => Current;
    }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    using MegaCrit.Sts2.Core.Combat;
    public sealed class Creature
    {
        public bool IsEnemy;
        public bool IsPlayer;
        public bool IsAlive = true;
        public bool Domain;
        public ICombatState? CombatState;
    }
    public sealed class DamageResult { }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.ValueProps { public enum ValueProp { None, Unpowered } }
namespace MegaCrit.Sts2.Core.Models
{
    using MegaCrit.Sts2.Core.Entities.Creatures;
    public class CardModel { }
    public class PowerModel { public Creature Owner = null!; }
}
namespace MegaCrit.Sts2.Core.Models.Powers
{
    using MegaCrit.Sts2.Core.Combat;
    using MegaCrit.Sts2.Core.Entities.Creatures;
    using MegaCrit.Sts2.Core.GameActions.Multiplayer;
    using MegaCrit.Sts2.Core.ValueProps;
    // Only signatures are modeled, not proprietary implementations or bookkeeping behavior.
    public sealed class FlutterPower : PowerModel
    {
        public decimal ModifyDamageMultiplicative(Creature? a, decimal b, ValueProp c, Creature? d, CardModel? e) => 0.5m;
        public Task AfterDamageReceived(PlayerChoiceContext a, Creature b, DamageResult c, ValueProp d, Creature? e, CardModel? f) => Task.CompletedTask;
    }
    public sealed class SoarPower : PowerModel
    { public decimal ModifyDamageMultiplicative(Creature? a, decimal b, ValueProp c, Creature? d, CardModel? e) => 0.5m; }
    public sealed class IntangiblePower : PowerModel
    {
        public decimal ModifyHpLostAfterOsty(Creature a, decimal b, ValueProp c, Creature? d, CardModel? e) => 1m;
        public decimal ModifyDamageCap(Creature? a, ValueProp b, Creature? c, CardModel? d) => 1m;
        public Task AfterSideTurnEnd(PlayerChoiceContext a, CombatSide b, IEnumerable<Creature> c) => Task.CompletedTask;
    }
    public sealed class SlipperyPower : PowerModel
    {
        public decimal ModifyHpLostAfterOsty(Creature a, decimal b, ValueProp c, Creature? d, CardModel? e) => 1m;
        public Task AfterDamageReceived(PlayerChoiceContext a, Creature b, DamageResult c, ValueProp d, Creature? e, CardModel? f) => Task.CompletedTask;
    }
    public sealed class HardToKillPower : PowerModel
    { public decimal ModifyDamageCap(Creature? a, ValueProp b, Creature? c, CardModel? d) => 1m; }
    public sealed class HardenedShellPower : PowerModel
    {
        public decimal ModifyHpLostBeforeOstyLate(Creature a, decimal b, ValueProp c, Creature? d, CardModel? e) => 1m;
        public Task BeforeSideTurnStart(PlayerChoiceContext a, CombatSide b, IReadOnlyList<Creature> c, ICombatState d) => Task.CompletedTask;
        public Task AfterDamageReceived(PlayerChoiceContext a, Creature b, DamageResult c, ValueProp d, Creature? e, CardModel? f) => Task.CompletedTask;
    }
    public sealed class ArtifactPower : PowerModel
    {
        public bool TryModifyPowerAmountReceived(PowerModel a, Creature b, decimal c, Creature? d, out decimal e) { e = 0; return true; }
        public Task AfterModifyingPowerAmountReceived(PowerModel a) => Task.CompletedTask;
    }
    public sealed class ThornsPower : PowerModel
    { public Task BeforeDamageReceived(PlayerChoiceContext a, Creature b, decimal c, ValueProp d, Creature? e, CardModel? f) => Task.CompletedTask; }
    public sealed class ReflectPower : PowerModel
    {
        public Task AfterDamageReceived(PlayerChoiceContext a, Creature b, DamageResult c, ValueProp d, Creature? e, CardModel? f) => Task.CompletedTask;
        public Task AfterSideTurnStart(CombatSide a, IReadOnlyList<Creature> b, ICombatState c) => Task.CompletedTask;
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    using MegaCrit.Sts2.Core.Entities.Creatures;
    public static class CreatureCmd
    { public static Task Heal(Creature creature, decimal amount, bool playAnim = true) => Task.CompletedTask; }
}
namespace Volibear.Core
{
    using MegaCrit.Sts2.Core.Entities.Creatures;
    public static class DomainPower { public static bool IsActive(Creature owner) => owner.Domain && owner.IsAlive; }
}
