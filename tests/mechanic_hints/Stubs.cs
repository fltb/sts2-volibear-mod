// Localization, native hover rendering and combat boundaries only. Production glossary,
// card getter, localization merging and live-state projection are compiled unchanged.
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;

namespace Godot { public static class GD { public static void Print(string _) { } public static void PrintErr(string _) { } } }
namespace BaseLib.Utils { [AttributeUsage(AttributeTargets.Class)] public sealed class PoolAttribute(Type _) : Attribute { } }
namespace BaseLib.Abstracts
{
    public abstract class CustomCardModel(int cost, CardType type, CardRarity rarity, TargetType target, bool show)
        : MegaCrit.Sts2.Core.Models.CardModel
    { public virtual string CustomPortraitPath => ""; }
}
namespace MegaCrit.Sts2.Core.ValueProps { public enum ValueProp { Unpowered, Move } }
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardType { Attack, Skill }
    public enum CardRarity { Basic }
    public enum TargetType { Self, AnyEnemy, AllEnemies, AllAllies, RandomEnemy }
}
namespace MegaCrit.Sts2.Core.Localization.DynamicVars
{
    public class DynamicVar { public decimal BaseValue { get; set; } public void UpgradeValueBy(decimal value) => BaseValue += value; }
}
namespace MegaCrit.Sts2.Core.Localization
{
    public sealed class LocTable
    {
        internal Dictionary<string, string> Entries { get; } = [];
        public void MergeWith(Dictionary<string, string> entries)
        { foreach (var (key, value) in entries) Entries[key] = value; }
    }
    public sealed class LocManager
    {
        public static LocManager Instance { get; } = new();
        private readonly Dictionary<string, LocTable> tables = [];
        public LocTable GetTable(string name)
        {
            if (!tables.TryGetValue(name, out var table)) tables[name] = table = new();
            Volibear.Content.VolibearLoc.AfterGetTable(name, ref table);
            return table;
        }
        internal void Reload() => tables.Clear();
    }
    public sealed class LocString(string table, string key)
    {
        private readonly Dictionary<string, object> values = [];
        public void Add(string name, object value) => values[name] = value;
        public string GetRawText() => LocManager.Instance.GetTable(table).Entries[key];
        public string GetFormattedText()
        {
            var text = GetRawText();
            foreach (var (name, value) in values) text = text.Replace("{" + name + "}", value.ToString());
            return text;
        }
    }
}
namespace MegaCrit.Sts2.Core.HoverTips
{
    public interface IHoverTip { string Id { get; } }
    public readonly record struct HoverTip(LocString TitleLoc, LocString DescriptionLoc) : IHoverTip
    {
        public string Id { get; init; } = "";
        public string Title => TitleLoc.GetFormattedText();
        public string Description => DescriptionLoc.GetFormattedText();
    }
}
namespace MegaCrit.Sts2.Core.Models
{
    public abstract class CardModel
    {
        public Player? Owner { get; set; }
        public bool IsCanonical { get; set; }
        public bool IsUpgraded { get; set; }
        public virtual string PortraitPath => "";
        public virtual string BetaPortraitPath => "";
        public LocString TitleLocString => new("cards", "VOLIBEAR_B01.title");
        public virtual LocString Description => new("cards", "VOLIBEAR_B04.description");
        protected virtual IEnumerable<DynamicVar> CanonicalVars => [];
        public Dictionary<string, DynamicVar> DynamicVars { get; } = [];
        // Represent a pre-existing native/base tip; the mod must append, not erase it.
        protected virtual IEnumerable<IHoverTip> ExtraHoverTips =>
            [new HoverTip(new("cards", "VOLIBEAR_B02.title"), new("cards", "VOLIBEAR_B02.description")) { Id = "NATIVE-BASE" }];
        public IEnumerable<IHoverTip> HoverTips => ExtraHoverTips;
    }
    public sealed class Player { public required Creature Creature { get; init; } }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public string Name { get; set; } = "";
        public bool IsAlive { get; set; } = true;
        public bool IsEnemy { get; set; }
        public MegaCrit.Sts2.Core.Combat.ICombatState? CombatState { get; set; }
    }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public enum CombatSide { Player, Enemy }
    public interface ICombatState
    {
        CombatSide CurrentSide { get; }
        IEnumerable<Creature> Enemies { get; }
        bool ContainsCreature(Creature creature);
    }
    public sealed class CombatState : ICombatState
    {
        public CombatSide CurrentSide { get; set; } = CombatSide.Player;
        public List<Creature> Members { get; } = [];
        public IEnumerable<Creature> Enemies => Members.Where(c => c.IsEnemy);
        public bool ContainsCreature(Creature creature) => Members.Contains(creature);
    }
    public sealed class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public bool IsInProgress { get; set; } = true;
        public bool IsOverOrEnding { get; set; }
        public ICombatState? Current { get; set; }
        public ICombatState? DebugOnlyGetState() => Current;
    }
}
namespace Volibear.Core
{
    public static class EngageCmd
    {
        internal static readonly HashSet<Creature> Used = [];
        internal static int Queries;
        public static bool Consumed(Creature enemy) { Queries++; return Used.Contains(enemy); }
    }
}
namespace Volibear.Content
{
    public sealed class VolibearCardPool { }
    internal static class InlineModelLocalization { internal static void Merge(string _, LocTable __) { } }
    internal sealed class TestCard(string key = "b04") : VolibearCard(1, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy, key)
    { public override LocString Description => new("cards", "VOLIBEAR_" + Key.ToUpperInvariant() + ".description"); }
}
