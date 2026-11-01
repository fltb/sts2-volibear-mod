// Command/dispatcher boundaries only. These declarations are not native-game evidence.
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Godot { internal static class GD { public static void Print(string message) { } } }
namespace MegaCrit.Sts2.Core.Combat
{
    public interface ICombatState { bool ContainsCreature(Creature creature); }
    public sealed class CombatState : ICombatState
    {
        public readonly List<Creature> Creatures = [];
        public bool ContainsCreature(Creature creature) => Creatures.Contains(creature);
    }
    public sealed class CombatManager { public void Reset(bool loading) { } }
}
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardKeyword { Ethereal }
    public enum AutoPlayType { None }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public bool IsPlayer { get; set; }
        public bool IsEnemy { get; set; }
        public uint? CombatId { get; set; }
        public ICombatState? CombatState { get; set; }
        public List<PowerModel> Powers { get; } = [];
    }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public class PlayerChoiceContext; }
namespace MegaCrit.Sts2.Core.Models
{
    public abstract class AbstractModel
    {
        public virtual bool TryModifyKeywordsInCombat(CardModel card, ISet<CardKeyword> keywords) => false;
        public virtual bool TryModifyEnergyCostInCombat(CardModel card, decimal original, out decimal modified)
        { modified = original; return false; }
        public virtual bool ShouldPlay(CardModel card, AutoPlayType autoPlayType) => true;
    }
    public sealed class Player(Creature creature) { public Creature Creature { get; } = creature; }
    public sealed class CardModel(Player owner)
    { public Player Owner { get; } = owner; public object? Affliction { get; set; } }
    public abstract class PowerModel : AbstractModel
    {
        public Creature Owner { get; private set; } = null!;
        public int Amount { get; private set; }
        public void ApplyInternal(Creature target, decimal amount, bool silent)
        { Owner = target; Amount = (int)amount; target.Powers.Add(this); }
        public void SetAmount(int amount, bool silent) => Amount = amount;
    }
}
namespace MegaCrit.Sts2.Core.Models.Afflictions
{ public sealed class Hexed; public sealed class Entangled; public sealed class Smog; public sealed class Ringing; }
namespace MegaCrit.Sts2.Core.Models.Powers
{
    public sealed class HexPower : PowerModel
    {
        public override bool TryModifyKeywordsInCombat(CardModel card, ISet<CardKeyword> keywords) =>
            card.Affliction is Afflictions.Hexed && keywords.Add(CardKeyword.Ethereal);
    }
    public sealed class TangledPower : PowerModel
    {
        public decimal OtherModOffset { get; set; }
        public override bool TryModifyEnergyCostInCombat(CardModel card, decimal original, out decimal modified)
        {
            bool applies = card.Affliction is Afflictions.Entangled;
            modified = original + (applies ? Amount + OtherModOffset : 0);
            return applies;
        }
    }
    public sealed class SmoggyPower : PowerModel
    { public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType) => card.Affliction is not Afflictions.Smog; }
    public sealed class RingingPower : PowerModel
    { public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType) => card.Affliction is not Afflictions.Ringing; }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class PowerCmd
    {
        public static async Task Apply(PlayerChoiceContext choiceContext, PowerModel power, Creature target,
            decimal amount, Creature? applier, CardModel? cardSource, bool silent)
        { await Task.Yield(); power.ApplyInternal(target, amount, silent); }
        public static async Task ModifyAmount(PlayerChoiceContext choiceContext, PowerModel power,
            decimal amount, Creature? applier, CardModel? cardSource, bool silent)
        { await Task.Yield(); power.SetAmount(power.Amount + (int)amount, silent); }
    }
}
namespace MegaCrit.Sts2.Core.Hooks
{
    public static class Hook
    {
        public static void ModifyKeywordsInCombat(ICombatState combat, CardModel card, ISet<CardKeyword> keywords) { }
        public static decimal ModifyEnergyCostInCombat(ICombatState combat, CardModel card, decimal amount) => amount;
        public static bool ShouldPlay(ICombatState combat, CardModel card, out AbstractModel? preventer, AutoPlayType type)
        { preventer = null; return true; }
    }
}
namespace Volibear.Core
{
    internal static class DomainEnemyEffects
    { internal static bool Active; internal static bool ActiveFor(ICombatState? state) => Active && state is not null; }
    internal static class DomainEnemyStatusContributions
    {
        internal static void AppliedTainted(PowerModel p, Creature t, decimal a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
        internal static void TaintedAmountChanged(PowerModel p, int a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
    }
    internal static class DomainPlayerDebuffContributions
    {
        internal static void Applied(PowerModel p, Creature t, decimal a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
        internal static void AmountChanged(PowerModel p, int a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
    }
    internal static class DomainPlayerStatContributions
    {
        internal static void Applied(PowerModel p, Creature t, decimal a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
        internal static void AmountChanged(PowerModel p, int a, Creature? s, CardModel? c, PlayerChoiceContext x) { }
    }
}
namespace Volibear.Presentation
{
    internal static class PowerPresentationDomainScalars
    { internal static bool IsCapturing => false; internal static void Capture(Creature c, PowerModel p) { } }
}
