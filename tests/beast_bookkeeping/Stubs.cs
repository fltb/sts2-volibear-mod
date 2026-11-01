// Native/BaseLib command boundaries only. Production conversion, tokens, fee transfer,
// selection and coupon methods are compiled unchanged into this executable.
// This does not execute the proprietary game, Harmony, multiplayer transport or UI.
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;

namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardType { Attack, Skill, Power, Status, Curse }
    public enum CardRarity { Token }
    public enum TargetType { AnyEnemy, AllEnemies }
    public enum CardKeyword { Exhaust, Retain, Unplayable, Ethereal }
    public enum KeywordSources { Local }
    public enum PileType { None, Deck, Draw, Hand, Discard, Exhaust, Play }
    public enum CardPilePosition { None, Bottom, Top, Random }
    public enum LocalCostType { Absolute, Relative }
    [System.Flags] public enum LocalCostModifierExpiration { None = 0, EndOfTurn = 1, WhenPlayed = 2, EndOfCombat = 4 }
    [System.Flags] public enum CostModifiers { None = 0, Local = 1, Global = 2, All = 3 }
    public class LocalCostModifier(int amount, LocalCostType type, LocalCostModifierExpiration expiration, bool reduceOnly)
    {
        public int Amount { get; set; } = amount;
        public LocalCostType Type { get; } = type;
        public LocalCostModifierExpiration Expiration { get; } = expiration;
        public bool IsReduceOnly { get; } = reduceOnly;
        public int Modify(int cost)
        {
            var next = Type == LocalCostType.Absolute ? Amount : cost + Amount;
            return IsReduceOnly ? System.Math.Min(cost, next) : next;
        }
    }
    public sealed class CardEnergyCost(CardModel card, int cost, bool x = false)
    {
        private readonly List<LocalCostModifier> _localModifiers = [];
        private int basis = cost;
        public int Canonical { get; } = cost;
        public bool CostsX { get; } = x;
        public int GetWithModifiers(CostModifiers modes)
        {
            if (CostsX || basis < 0) return basis;
            var value = modes.HasFlag(CostModifiers.Local) ? _localModifiers.Aggregate(basis, (v, m) => m.Modify(v)) : basis;
            return System.Math.Max(0, value);
        }
        private void Put(int amount, LocalCostType type, LocalCostModifierExpiration expiry, bool reduceOnly)
        {
            if (type == LocalCostType.Relative && amount == 0) return;
            _localModifiers.Add(new LocalCostModifier(amount, type, expiry, reduceOnly));
        }
        public void SetUntilPlayed(int value, bool reduceOnly = false) => Put(value, LocalCostType.Absolute, LocalCostModifierExpiration.WhenPlayed, reduceOnly);
        public void SetThisTurn(int value, bool reduceOnly = false) => Put(value, LocalCostType.Absolute, LocalCostModifierExpiration.EndOfTurn, reduceOnly);
        public void SetThisTurnOrUntilPlayed(int value, bool reduceOnly = false) => Put(value, LocalCostType.Absolute, LocalCostModifierExpiration.EndOfTurn | LocalCostModifierExpiration.WhenPlayed, reduceOnly);
        public void SetThisCombat(int value, bool reduceOnly = false) => Put(value, LocalCostType.Absolute, LocalCostModifierExpiration.EndOfCombat, reduceOnly);
        public void AddUntilPlayed(int value, bool reduceOnly = false) => Put(value, LocalCostType.Relative, LocalCostModifierExpiration.WhenPlayed, reduceOnly);
        public void AddThisTurn(int value, bool reduceOnly = false) => Put(value, LocalCostType.Relative, LocalCostModifierExpiration.EndOfTurn, reduceOnly);
        public void AddThisTurnOrUntilPlayed(int value, bool reduceOnly = false) => Put(value, LocalCostType.Relative, LocalCostModifierExpiration.EndOfTurn | LocalCostModifierExpiration.WhenPlayed, reduceOnly);
        public void AddThisCombat(int value, bool reduceOnly = false) => Put(value, LocalCostType.Relative, LocalCostModifierExpiration.EndOfCombat, reduceOnly);
        public void SetCustomBaseCost(int value) => basis = value;
        public bool EndOfTurnCleanup() => _localModifiers.RemoveAll(m => m.Expiration.HasFlag(LocalCostModifierExpiration.EndOfTurn)) > 0;
        public bool AfterCardPlayedCleanup() => _localModifiers.RemoveAll(m => m.Expiration.HasFlag(LocalCostModifierExpiration.WhenPlayed)) > 0;
        public CardEnergyCost Clone(CardModel owner)
        {
            var copy = new CardEnergyCost(owner, Canonical, CostsX) { basis = basis };
            copy._localModifiers.AddRange(_localModifiers.Select(m => new LocalCostModifier(m.Amount, m.Type, m.Expiration, m.IsReduceOnly)));
            return copy;
        }
    }
    public sealed class CardPile(PileType type)
    {
        public static int MaxCardsInHand => 10;
        public PileType Type { get; } = type;
        public List<CardModel> Cards { get; } = [];
        public bool IsCombatPile => Type is not PileType.None and not PileType.Deck;
    }
    public static class PileTypeExtensions
    {
        public static CardPile GetPile(this PileType type, Player owner) => owner.Piles[type];
    }
    public struct CardPileAddResult { public bool success; public CardModel cardAdded; }
    public sealed class CardPlay { public required CardModel Card; public Creature? Target; public int PlayIndex; public int PlayCount = 1; }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public sealed class Player
    {
        public Player(CombatState combat)
        {
            Creature = new Creature { CombatState = combat, Player = this };
            foreach (var type in System.Enum.GetValues<PileType>()) Piles[type] = new CardPile(type);
        }
        public Creature Creature { get; }
        public object? PlayerCombatState { get; set; } = new();
        public Dictionary<PileType, CardPile> Piles { get; } = [];
        public int HandLimit { get; set; } = 10;
    }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature { public bool IsAlive = true; public bool IsHittable = true; public ICombatState? CombatState; public Player? Player; public int Block; }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public enum CombatSide { Player, Enemy }
    public interface ICombatState { T CreateCard<T>(Player owner) where T : CardModel; void RemoveCard(CardModel card); }
    public sealed class CombatState : ICombatState
    {
        public readonly List<CardModel> Registered = [];
        public T CreateCard<T>(Player owner) where T : CardModel
        {
            var card = System.Activator.CreateInstance<T>(); card.Owner = owner; card.State = this;
            Registered.Add(card); Harness.Events.Add("create"); return card;
        }
        public void RemoveCard(CardModel card) => Registered.Remove(card);
    }
    public sealed class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public bool IsInProgress = true;
        public bool IsOverOrEnding;
        public HistoryLog History { get; } = new();
    }
    public sealed class HistoryLog { public List<object> Entries { get; } = []; }
}
namespace MegaCrit.Sts2.Core.Combat.History.Entries
{ public sealed class CardExhaustedEntry(CardModel card) { public CardModel Card { get; } = card; } }
namespace MegaCrit.Sts2.Core.Models
{
    public class CardModel
    {
        public CardModel(int cost = 1, CardType type = CardType.Skill)
        { Type = type; EnergyCost = new CardEnergyCost(this, cost); }
        public CardType Type { get; protected set; }
        public TargetType TargetType { get; protected set; }
        public CardRarity Rarity { get; protected set; }
        public Player Owner { get; set; } = null!;
        public ICombatState? State { get; set; }
        public ICombatState? CombatState => State;
        public CardPile? Pile { get; set; }
        public CardModel? DeckVersion { get; set; }
        public CardModel? CloneOf { get; set; }
        public object? Enchantment { get; set; }
        public object? Affliction { get; set; }
        public CardEnergyCost EnergyCost { get; set; }
        public bool IsUpgraded { get; private set; }
        private bool HasSingleTurnRetain { get; set; }
        public bool ShouldRetainThisTurn => HasSingleTurnRetain || Keywords.Contains(CardKeyword.Retain);
        public HashSet<CardKeyword> LocalKeywords { get; } = [];
        public virtual IEnumerable<CardKeyword> CanonicalKeywords => [];
        public IReadOnlySet<CardKeyword> Keywords => LocalKeywords.Union(CanonicalKeywords).ToHashSet();
        public virtual bool CanBeGeneratedInCombat => true;
        public virtual bool CanBeGeneratedByModifiers => true;
        public virtual bool GainsBlock => false;
        public FakeId Id { get; } = new();
        private DynamicVarSet? vars;
        public DynamicVarSet DynamicVars => vars ??= new DynamicVarSet(CanonicalVars);
        protected virtual IEnumerable<DynamicVar> CanonicalVars => [];
        protected virtual void OnUpgrade() { }
        protected virtual Task OnPlay(PlayerChoiceContext context, CardPlay play) => Task.CompletedTask;
        public void UpgradeInternal() { if (!IsUpgraded) { IsUpgraded = true; OnUpgrade(); } }
        public void AssertMutable() { }
        public IReadOnlySet<CardKeyword> GetKeywordsWithSources(KeywordSources source) => LocalKeywords;
        public void GiveSingleTurnRetain() => HasSingleTurnRetain = true;
        public void EndOfTurnCleanup() { HasSingleTurnRetain = false; EnergyCost.EndOfTurnCleanup(); }
        public void InvokeEnergyCostChanged() { }
        public Task TestPlay(PlayerChoiceContext context, CardPlay play) => OnPlay(context, play);
    }
    public sealed class FakeId { public string Entry => "TEST"; }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.ValueProps { public enum ValueProp { Move } }
namespace MegaCrit.Sts2.Core.Localization { public sealed class LocString(string table, string key) { } }
namespace MegaCrit.Sts2.Core.HoverTips { public interface IHoverTip { } }
namespace MegaCrit.Sts2.Core.Localization.DynamicVars
{
    public class DynamicVar(string name, decimal value) { public string Name = name; public decimal BaseValue = value; }
    public sealed class DamageVar(decimal value, MegaCrit.Sts2.Core.ValueProps.ValueProp prop) : DynamicVar("Damage", value);
    public sealed class BlockVar(decimal value, MegaCrit.Sts2.Core.ValueProps.ValueProp prop) : DynamicVar("Block", value);
    public sealed class DynamicVarSet(IEnumerable<DynamicVar> vars) : Dictionary<string, DynamicVar>(vars.ToDictionary(v => v.Name));
}
namespace MegaCrit.Sts2.Core.CardSelection
{
    public sealed class CardSelectorPrefs(MegaCrit.Sts2.Core.Localization.LocString prompt, int min, int max = 1) { }
}
namespace MegaCrit.Sts2.Core.Rooms { public sealed class CombatRoom { } }
namespace BaseLib.Utils.Attributes
{
    [System.AttributeUsage(System.AttributeTargets.Class)] public sealed class CustomIDAttribute(string id) : System.Attribute { }
}
namespace BaseLib.Patches.Hooks
{
    public static class MaxHandSizePatch { public static int GetMaxHandSize(Player owner, int original) => owner.HandLimit; }
}
namespace BaseLib.Abstracts
{
    public interface ICustomModel { }
    public class CardModifier
    {
        private static readonly Dictionary<CardModel, List<CardModifier>> modifiers = new(System.Collections.Generic.ReferenceEqualityComparer.Instance);
        public CardModel? Owner { get; private set; }
        public static IEnumerable<CardModifier> Modifiers(CardModel card) => modifiers.GetValueOrDefault(card) ?? [];
        public static T AddModifier<T>(CardModel card, decimal amount) where T : CardModifier, new()
        {
            if (!modifiers.TryGetValue(card, out var list)) modifiers[card] = list = [];
            var value = new T { Owner = card }; list.Add(value); return value;
        }
        public static void RemoveModifier(CardModel card, CardModifier modifier) => modifiers.GetValueOrDefault(card)?.Remove(modifier);
        public virtual Task AfterCardPlayed(PlayerChoiceContext context, CardPlay play) => Task.CompletedTask;
        public virtual Task AfterSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants) => Task.CompletedTask;
        public virtual Task AfterCombatEnd(MegaCrit.Sts2.Core.Rooms.CombatRoom room) => Task.CompletedTask;
    }
}
namespace Volibear.Content
{
    public interface INativeLightningSpell { }
    public class CardLoc : List<(string, string)>
    { public CardLoc(string title, string text) { Add((title, text)); } }
    public class VolibearCard : CardModel
    {
        public VolibearCard(int cost, CardType type, CardRarity rarity, TargetType target, string portrait, bool show) : base(cost, type)
        { Rarity = rarity; TargetType = target; }
        public virtual List<(string, string)> Localization => [];
        protected MegaCrit.Sts2.Core.ValueProps.ValueProp Move => MegaCrit.Sts2.Core.ValueProps.ValueProp.Move;
        protected virtual IEnumerable<MegaCrit.Sts2.Core.HoverTips.IHoverTip> ExtraHoverTips => [];
        protected void UpgradeVar(string key, decimal amount) => DynamicVars[key].BaseValue += amount;
    }
    public static class MechanicHoverTips
    { public static IEnumerable<MegaCrit.Sts2.Core.HoverTips.IHoverTip> ForText(string text) => []; }
    public static class DirectEffects
    { public static bool Live(CardModel card) => card.Owner.Creature.IsAlive && card.CombatState is not null && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding; }
}
namespace Volibear.Core
{
    public static class CostPresentationReceipts
    { public static object Capture(CardModel card) => new(); public static void LocalReductionCommitted(object snapshot) { } }
    public static class GameplayPresentationReceipts
    { public static void Publish(string kind, Creature owner, CardModel? source = null, CardModel? card = null, int amount = 0) => Harness.Events.Add(kind); }
    public static class CardPresentationReceipts { public static void Retrieved(CardModel card, CardModel source, PileType from) { } }
    public static class LightningCmd
    { public static Task DealAllEnemies(PlayerChoiceContext context, decimal amount, CardModel card) { Harness.Lightning += (int)amount; return Task.CompletedTask; } }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class CardCmd
    {
        public static async Task Exhaust(PlayerChoiceContext context, CardModel card)
        {
            if (Harness.CancelExhaust) return;
            Harness.Events.Add("exhaust"); Harness.Exhausted.Add(card); Harness.Move(card, PileType.Exhaust);
            CombatManager.Instance.History.Entries.Add(new MegaCrit.Sts2.Core.Combat.History.Entries.CardExhaustedEntry(card));
            if (Harness.OnExhaust is not null) await Harness.OnExhaust(card);
        }
        public static void Upgrade(CardModel card) => card.UpgradeInternal();
        public static void ApplyKeyword(CardModel card, params CardKeyword[] keywords)
        { foreach (var keyword in keywords) card.LocalKeywords.Add(keyword); }
    }
    public static class CardPileCmd
    {
        public static async Task<CardPileAddResult> AddGeneratedCardToCombat(CardModel card, PileType pile, Player creator, CardPilePosition position)
        {
            Harness.Events.Add("generate"); Harness.Generated.Add(card);
            if (Harness.FailGeneration) return new CardPileAddResult { cardAdded = card, success = false };
            if (pile == PileType.Hand && pile.GetPile(card.Owner).Cards.Count >= card.Owner.HandLimit) pile = PileType.Discard;
            Harness.Move(card, pile);
            if (Harness.OnGenerated is not null) await Harness.OnGenerated(card);
            return new CardPileAddResult { cardAdded = card, success = true };
        }
        public static Task Add(CardModel card, PileType pile) { Harness.Move(card, pile); return Task.CompletedTask; }
    }
    public static class CreatureCmd
    {
        public static Task GainBlock(Creature creature, decimal amount, MegaCrit.Sts2.Core.ValueProps.ValueProp prop, CardPlay? play)
        { creature.Block += (int)amount; return Task.CompletedTask; }
    }
    public static class CardSelectCmd
    {
        public static Task<IEnumerable<CardModel>> FromHand(PlayerChoiceContext context, Player owner, MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs, System.Func<CardModel, bool> filter, CardModel source) => Task.FromResult(Harness.Selected.Where(filter));
        public static Task<IEnumerable<CardModel>> FromCombatPile(PlayerChoiceContext context, CardPile pile, Player owner, MegaCrit.Sts2.Core.CardSelection.CardSelectorPrefs prefs, System.Func<CardModel, bool> filter) => Task.FromResult(Harness.Selected.Where(filter));
    }
    public sealed class AttackBuilder(decimal amount)
    {
        private int hits = 1;
        public AttackBuilder FromCard(CardModel card) => this;
        public AttackBuilder Targeting(Creature target) => this;
        public AttackBuilder WithHitCount(int count) { hits = count; return this; }
        public Task Execute(PlayerChoiceContext context) { Harness.Damage += (int)amount * hits; return Task.CompletedTask; }
    }
    public static class DamageCmd { public static AttackBuilder Attack(decimal amount) => new(amount); }
}
public static class Harness
{
    public static readonly List<string> Events = [];
    public static readonly List<CardModel> Exhausted = [];
    public static readonly List<CardModel> Generated = [];
    public static IEnumerable<CardModel> Selected = [];
    public static System.Func<CardModel, Task>? OnExhaust;
    public static System.Func<CardModel, Task>? OnGenerated;
    public static bool FailGeneration;
    public static bool CancelExhaust;
    public static int Damage, Lightning;
    public static void Reset()
    {
        Events.Clear(); Exhausted.Clear(); Generated.Clear(); Selected = [];
        OnExhaust = null; OnGenerated = null; FailGeneration = false; CancelExhaust = false; Damage = 0; Lightning = 0;
        CombatManager.Instance.History.Entries.Clear();
        CombatManager.Instance.IsInProgress = true; CombatManager.Instance.IsOverOrEnding = false;
    }
    public static void Move(CardModel card, PileType pile)
    { card.Pile?.Cards.Remove(card); card.Pile = pile.GetPile(card.Owner); card.Pile.Cards.Add(card); }
}
