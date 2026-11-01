using System.Globalization;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;

internal static class BoundaryTrace { internal static readonly List<string> Events = []; }

namespace BaseLib.Utils.Attributes
{
    [AttributeUsage(AttributeTargets.Class)]
    public sealed class CustomIDAttribute : Attribute { public CustomIDAttribute(string id) { } }
}
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardType { Attack, Skill }
    public enum CardRarity { Basic }
    public enum TargetType { AnyEnemy, Self }
    public enum CardTag { Strike, Defend }
    public sealed class CardPlay { public Creature? Target { get; init; } }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public bool IsAlive { get; set; }
        public bool IsHittable { get; set; } = true;
        public object? CombatState { get; set; }
    }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public sealed class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public bool IsInProgress { get; set; }
        public bool IsOverOrEnding { get; set; }
    }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.ValueProps { public enum ValueProp { Move } }
namespace MegaCrit.Sts2.Core.Models
{
    public sealed class Player { public Creature Creature { get; set; } = new(); }
    public class CardModel { public Player Owner { get; set; } = new(); }
}
namespace MegaCrit.Sts2.Core.Localization.DynamicVars
{
    public class DynamicVar(string name, decimal value)
    {
        public string Name { get; } = name;
        public decimal BaseValue { get; } = value;
    }
    public sealed class DamageVar : DynamicVar { public DamageVar(decimal amount, ValueProp props) : base("Damage", amount) { } }
    public sealed class BlockVar : DynamicVar { public BlockVar(decimal amount, ValueProp props) : base("Block", amount) { } }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class CreatureCmd
    {
        public static Func<Task>? AfterBlock;
        public static async Task GainBlock(Creature creature, decimal amount, ValueProp props, CardPlay play, bool unused)
        {
            BoundaryTrace.Events.Add("block:" + amount.ToString(CultureInfo.InvariantCulture));
            if (AfterBlock is not null) await AfterBlock();
        }
    }
    public static class DamageCmd
    {
        public static Func<Task>? AfterAttack;
        public static bool RejectCalls;
        public static AttackCommand Attack(decimal amount) => new(amount);
        public sealed class AttackCommand(decimal amount)
        {
            public AttackCommand FromCard(CardModel card) => this;
            public AttackCommand Targeting(Creature creature) => this;
            public async Task Execute(PlayerChoiceContext context)
            {
                if (RejectCalls) throw new InvalidOperationException("B04 entered a terminal attack boundary");
                BoundaryTrace.Events.Add("attack:" + amount.ToString(CultureInfo.InvariantCulture));
                if (AfterAttack is not null) await AfterAttack();
            }
        }
    }
}
namespace Volibear.Core
{
    public static class EngageCmd
    {
        public readonly record struct Result(bool Performed, decimal Absorbed, bool Completed);
        public static bool RejectCalls;
        public static Task<Result> Perform(PlayerChoiceContext context, Creature target, CardModel card)
        {
            if (RejectCalls) throw new InvalidOperationException("B04 entered a terminal engage boundary");
            BoundaryTrace.Events.Add("engage");
            return Task.FromResult(new Result(true, 0m, true));
        }
    }
}
namespace Volibear.Content
{
    public abstract class VolibearCard : CardModel
    {
        protected VolibearCard(int cost, CardType type, CardRarity rarity, TargetType target, string key) { }
        protected static ValueProp Move => ValueProp.Move;
        protected virtual HashSet<CardTag> CanonicalTags => [];
        protected abstract IEnumerable<DynamicVar> CanonicalVars { get; }
        protected abstract Task OnPlay(PlayerChoiceContext context, CardPlay play);
        protected abstract void OnUpgrade();
        protected T Var<T>(string name) where T : DynamicVar => (T)CanonicalVars.Single(v => v.Name == name);
        protected decimal Value(string name) => CanonicalVars.Single(v => v.Name == name).BaseValue;
        protected void UpgradeVar(string name, decimal delta) { }
        public Task Play(PlayerChoiceContext context, CardPlay play) => OnPlay(context, play);
    }
    public static class LightningCmd
    {
        public static Task DealAllEnemies(PlayerChoiceContext context, decimal amount, CardModel card) => Task.CompletedTask;
    }
}
