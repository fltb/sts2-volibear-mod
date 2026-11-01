// Native data/command boundary doubles only. Production callbacks are inserted unchanged.
using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Afflictions;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace MegaCrit.Sts2.Core.Combat
{
    public interface ICombatState
    {
        IReadOnlyList<Player> Players { get; }
        int RoundNumber { get; }
        bool ContainsCreature(Creature creature);
        T CreateCard<T>(Player owner) where T : CardModel;
        void RemoveCard(CardModel card);
    }
    public sealed class TestCombat : ICombatState
    {
        public List<Player> PlayerList = [];
        public HashSet<Creature> Creatures = [];
        public HashSet<CardModel> Cards = [];
        public IReadOnlyList<Player> Players => PlayerList;
        public int RoundNumber { get; set; } = 1;
        public bool ContainsCreature(Creature creature) => Creatures.Contains(creature);
        public T CreateCard<T>(Player owner) where T : CardModel
        {
            var card = (T)Activator.CreateInstance(typeof(T))!;
            card.Owner = owner; card.CombatState = this; Cards.Add(card); return card;
        }
        public void RemoveCard(CardModel card) => Cards.Remove(card);
    }
    public sealed class CombatManager
    {
        public static CombatManager Instance = new();
        public bool IsInProgress = true, IsOverOrEnding;
        public ICombatState? Current;
        public ICombatState? DebugOnlyGetState() => Current;
    }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{ public sealed class Player { public Creature Creature = null!; public object? Character; } }
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public bool IsPlayer, IsEnemy, Domain, IsAlive = true;
        public bool IsDead => !IsAlive;
        public ICombatState? CombatState;
        public Player? Player, PetOwner;
        public int? CombatId = 1;
        public List<PowerModel> Powers = [];
        private DomainPower? domainInstance;
        public T? GetPower<T>() where T : PowerModel => typeof(T) == typeof(DomainPower)
            ? Domain ? (T)(PowerModel)(domainInstance ??= new DomainPower { Owner = this }) : null
            : Powers.OfType<T>().FirstOrDefault();
    }
    public sealed class DamageResult { }
}
namespace MegaCrit.Sts2.Core.Entities.Cards
{ public enum PileType { Hand, Draw, Discard } public enum CardPilePosition { Top, Bottom } }
namespace MegaCrit.Sts2.Core.Context { public static class LocalContext { public static bool IsMe(Player p) => true; } }
namespace MegaCrit.Sts2.Core.Nodes.CommonUi { public enum CardPreviewStyle { HorizontalLayout, MessyLayout } }
namespace MegaCrit.Sts2.Core.ValueProps { public enum ValueProp { None, Unpowered } }
namespace MegaCrit.Sts2.Core.Localization.DynamicVars
{ public sealed class DamageVar { public decimal BaseValue = 2; public ValueProp Props; } }
namespace MegaCrit.Sts2.Core.Models
{
    public class AbstractModel { }
    public class CardModel : AbstractModel
    {
        public Player Owner = null!;
        public ICombatState? CombatState;
        public CardModel? CloneOf;
        public Vars DynamicVars = new();
        public sealed class Vars { public DamageVar Damage = new(); }
    }
    public class MonsterModel : AbstractModel { public Creature Creature = null!; }
    public class PowerModel : AbstractModel { public Creature Owner = null!; public int Amount; }
    public class AfflictionModel : AbstractModel { }
}
namespace MegaCrit.Sts2.Core.Models.Cards
{
    public sealed class Burn : CardModel { }
    public sealed class Wither : CardModel { public void FakeUpgrade() => DynamicVars.Damage.BaseValue += 3; }
}
namespace MegaCrit.Sts2.Core.Models.Monsters
{ public sealed class Aeonglass : MonsterModel { public int WitherUpgradeCount; } }
namespace MegaCrit.Sts2.Core.Models.Powers
{
    public sealed class VitalSparkPower : PowerModel { }
    public sealed class GalvanicPower : PowerModel { }
    public sealed class PaperCutsPower : PowerModel { }
    public sealed class TaintedPower : PowerModel { }
}
namespace MegaCrit.Sts2.Core.Models.Afflictions { public sealed class Galvanized : AfflictionModel { } }
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer
{
    public sealed class PlayerChoiceContext
    {
        private readonly Stack<AbstractModel> models = new();
        public AbstractModel? LastInvolvedModel => models.TryPeek(out var model) ? model : null;
        public void PushModel(AbstractModel model) => models.Push(model);
        public void PopModel(AbstractModel model) { if (!ReferenceEquals(models.Pop(), model)) throw new Exception("context mismatch"); }
    }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public sealed class CardPileAddResult { public bool success; public CardModel cardAdded = null!; }
    public static class CardPileCmd
    {
        public static readonly List<CardModel> Added = [];
        public static Task<CardPileAddResult> AddGeneratedCardToCombat(CardModel card, PileType pile, Player? creator, CardPilePosition position)
        { Added.Add(card); return Task.FromResult(new CardPileAddResult { success = true, cardAdded = card }); }
    }
    public static class CardCmd
    {
        public static int Afflictions;
        public static void PreviewCardPileAdd(CardPileAddResult[] r, float duration, CardPreviewStyle style) { }
        public static Task<T?> Afflict<T>(CardModel card, decimal amount) where T : AfflictionModel
        { Afflictions++; return Task.FromResult((T?)Activator.CreateInstance(typeof(T))); }
    }
    public static class CreatureCmd
    {
        public static int Damages, MaxHpLosses;
        public static decimal LastDamage;
        public static Task<IEnumerable<DamageResult>> Damage(PlayerChoiceContext c, Creature t, decimal n, ValueProp p, CardModel? card)
        { Damages++; LastDamage = n; return Task.FromResult<IEnumerable<DamageResult>>([new()]); }
        public static Task<IEnumerable<DamageResult>> Damage(PlayerChoiceContext c, Creature t, decimal n, ValueProp p, Creature? dealer, CardModel? card) => Damage(c, t, n, p, card);
        public static Task LoseMaxHp(PlayerChoiceContext c, Creature t, decimal n, bool fromCard)
        { MaxHpLosses++; return Task.CompletedTask; }
    }
    public static class PowerCmd
    { public static Task<T?> Apply<T>(PlayerChoiceContext c, Creature t, decimal n, Creature? applier, CardModel? card, bool silent) where T : PowerModel => Task.FromResult((T?)null); }
    public static class Cmd { public static Task Wait(float n) => Task.CompletedTask; }
}
namespace Volibear.Content
{
    public sealed class VolibearCharacter { }
    public sealed class Volibear_T02 : CardModel { }
}
namespace Volibear.Core
{
    public sealed class DomainPower : PowerModel { public static bool IsActive(Creature owner) => owner.Domain && owner.IsAlive; }
    public static class DomainEnemyEffects
    {
        private static readonly ConditionalWeakTable<PowerModel, ShellWindow> SuppressedShells = new();
        // PRODUCTION_DomainEnemyEffects.cs
    }
    public static class DomainPlayerStatContributions
    {
        // PRODUCTION_DomainPlayerStatContributions.cs
    }
    public static class DomainEnemyStatusContributions
    {
        private static ConditionalWeakTable<CardModel, Origin> _origins = new();
        private static ConditionalWeakTable<CardModel, WitherContribution> _witherContributions = new();
        private static ConditionalWeakTable<PlayerChoiceContext, SparkTicket> _sparkTickets = new();
        private static ConditionalWeakTable<PowerModel, TaintedReceipt> _taintedReceipts = new();
        private static int _generation;
        // PRODUCTION_DomainEnemyStatusContributions.cs
        // PRODUCTION_DomainEnemyStatusContributions.PowerEffects.cs
        // PRODUCTION_DomainEnemyStatusContributions.Wither.cs
    }
}
namespace Volibear.Presentation
{
    internal static class PowerPresentationDomain
    {
        // PRODUCTION_PRESENTATION
    }
    internal static class GameplayPresentationReceipts
    {
        internal static readonly List<Creature> Recipients = [];
        internal static void Publish(string cue, Creature owner, AbstractModel? source, CardModel? card, Creature enemy, decimal amount) => Recipients.Add(owner);
    }
    internal static class PowerPresentationDomainScalars { internal static void Capture(Creature enemy, PowerModel power) { } }
}
internal static class Program
{
    private static int checks;
    private static void Check(bool ok, string message) { checks++; if (!ok) throw new Exception(message); }
    private static object? Call(string method, params object?[] args) =>
        typeof(DomainEnemyStatusContributions).GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, args);
    private static Task CallTask(string method, params object?[] args) => (Task)Call(method, args)!;
    private static async Task Generate<T>(Creature target, AbstractModel source) where T : CardModel
    {
        var method = typeof(DomainEnemyStatusContributions).GetMethod("AddEnemyStatusOne", BindingFlags.NonPublic | BindingFlags.Static)!;
        await (Task)method.MakeGenericMethod(typeof(T)).Invoke(null, [target, PileType.Draw, 1, null, CardPilePosition.Top, source])!;
    }
    private static (TestCombat State, Player Owner, Player Receiver, Aeonglass Enemy) Fixture()
    {
        DomainEnemyStatusContributions.Reset(); CardPileCmd.Added.Clear(); CreatureCmd.Damages = 0;
        CreatureCmd.MaxHpLosses = 0; CardCmd.Afflictions = 0; Volibear.Presentation.GameplayPresentationReceipts.Recipients.Clear();
        var state = new TestCombat();
        Player NewPlayer(bool domain)
        {
            var p = new Player { Character = domain ? new VolibearCharacter() : new object() };
            p.Creature = new Creature { IsPlayer = true, Domain = domain, CombatState = state, Player = p };
            state.PlayerList.Add(p); state.Creatures.Add(p.Creature); return p;
        }
        var owner = NewPlayer(true); var receiver = NewPlayer(false);
        var enemy = new Aeonglass { Creature = new Creature { IsEnemy = true, CombatState = state } };
        state.Creatures.Add(enemy.Creature); CombatManager.Instance = new CombatManager { Current = state };
        return (state, owner, receiver, enemy);
    }
    private static void Scope()
    {
        var (s, owner, receiver, enemy) = Fixture();
        Check(DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "One domain protects a different player");
        Check(!DomainEnemyEffects.ProtectsPlayer(enemy.Creature), "Enemy is not a player beneficiary");
        Check(!DomainEnemyEffects.ProtectsPlayer(null), "Null player rejected");
        owner.Creature.IsAlive = false;
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Dead domain owner cannot sustain field");
        receiver.Creature.Domain = true;
        Check(DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Second living holder sustains field");
        receiver.Creature.Domain = false; owner.Creature.IsAlive = true;
        s.Creatures.Remove(owner.Creature);
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Detached domain owner ignored");
        s.Creatures.Add(owner.Creature); s.Creatures.Remove(receiver.Creature);
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Detached recipient ignored");
        s.Creatures.Add(receiver.Creature); receiver.Creature.IsAlive = false;
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Dead recipient cannot receive new protection");
        receiver.Creature.IsAlive = true; CombatManager.Instance.Current = new TestCombat();
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Old encounter cannot borrow current domain");
        CombatManager.Instance.Current = s; CombatManager.Instance.IsOverOrEnding = true;
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Ending encounter excluded");
        CombatManager.Instance.IsOverOrEnding = false; owner.Creature.Domain = false;
        Check(!DomainEnemyEffects.ProtectsPlayer(receiver.Creature), "Last domain expiration resumes native effects");
    }
    private static async Task Statuses()
    {
        var (s, owner, receiver, enemy) = Fixture();
        await Generate<Burn>(receiver.Creature, enemy);
        Check(CardPileCmd.Added.Count == 0 && s.Cards.Count == 0, "Teammate domain must stop enemy status generation");
        Check(Volibear.Presentation.GameplayPresentationReceipts.Recipients.SequenceEqual([owner.Creature]), "Suppression cue belongs to actual domain holder");
        var direct = s.CreateCard<Burn>(receiver);
        await CallTask("AddEnemyGenerated", direct, PileType.Hand, null, CardPilePosition.Top, enemy);
        Check(!s.Cards.Contains(direct) && CardPileCmd.Added.Count == 0, "Direct generated status is removed before pile admission");
        owner.Creature.Domain = false;
        await Generate<Burn>(receiver.Creature, enemy);
        var enemyBurn = CardPileCmd.Added.Single();
        owner.Creature.Domain = true;
        await CallTask("StatusDamageAmount", new PlayerChoiceContext(), receiver.Creature, 3m, ValueProp.Unpowered, enemyBurn);
        Check(CreatureCmd.Damages == 0, "Previously created enemy status is suppressed by teammate domain");
        var playerBurn = s.CreateCard<Burn>(receiver);
        await CallTask("StatusDamageAmount", new PlayerChoiceContext(), receiver.Creature, 2m, ValueProp.Unpowered, playerBurn);
        Check(CreatureCmd.Damages == 1 && CreatureCmd.LastDamage == 2m, "Unattributed/player-created status damage remains native");
        var playerSource = new PowerModel { Owner = receiver.Creature };
        await Generate<Burn>(receiver.Creature, playerSource);
        Check(CardPileCmd.Added.Count == 2, "Player-owned generation not mislabeled enemy");
        owner.Creature.Domain = false;
        await CallTask("StatusDamageAmount", new PlayerChoiceContext(), receiver.Creature, 3m, ValueProp.Unpowered, enemyBurn);
        Check(CreatureCmd.Damages == 2, "Retained enemy status resumes after last field expires");
        DomainEnemyStatusContributions.Reset(); owner.Creature.Domain = true;
        await CallTask("StatusDamageAmount", new PlayerChoiceContext(), receiver.Creature, 3m, ValueProp.Unpowered, enemyBurn);
        Check(CreatureCmd.Damages == 3, "Old provenance is not reused after reset");
    }
    private static async Task Powers()
    {
        var (s, owner, receiver, enemy) = Fixture(); var context = new PlayerChoiceContext();
        var galvanic = new GalvanicPower { Owner = enemy.Creature };
        await CallTask("GalvanicDamage", context, receiver.Creature, 4m, ValueProp.Unpowered, null, null, galvanic);
        Check(CreatureCmd.Damages == 0, "Teammate domain must stop enemy Galvanic damage");
        await CallTask("PaperCutMaxHp", context, receiver.Creature, 2m, false, new PaperCutsPower { Owner = enemy.Creature });
        Check(CreatureCmd.MaxHpLosses == 0, "Teammate domain blocks enemy maximum HP loss");
        var card = s.CreateCard<Burn>(receiver);
        var afflict = typeof(DomainEnemyStatusContributions).GetMethod("EnemyAfflict", BindingFlags.NonPublic | BindingFlags.Static)!.MakeGenericMethod(typeof(Galvanized));
        await (Task)afflict.Invoke(null, [card, 1m, galvanic])!;
        Check(CardCmd.Afflictions == 0, "Enemy card affliction suppressed for teammate");
        galvanic.Owner = receiver.Creature;
        await CallTask("GalvanicDamage", context, receiver.Creature, 4m, ValueProp.Unpowered, null, null, galvanic);
        await (Task)afflict.Invoke(null, [card, 1m, galvanic])!;
        Check(CreatureCmd.Damages == 1 && CardCmd.Afflictions == 1, "Player-owned power contributions preserved");
        var tainted = new TaintedPower { Owner = receiver.Creature, Amount = 6 }; receiver.Creature.Powers.Add(tainted);
        Check(DomainEnemyStatusContributions.ShouldCancelTainted(tainted, receiver.Creature, 1m, enemy.Creature, null, context), "Enemy Tainted precommit shared protection");
        Check(!DomainEnemyStatusContributions.ShouldCancelTainted(tainted, receiver.Creature, 1m, receiver.Creature, null, context), "Player Tainted precommit preserved");
        owner.Creature.Domain = false;
        DomainEnemyStatusContributions.AppliedTainted(tainted, receiver.Creature, 6m, enemy.Creature, null, context);
        DomainEnemyStatusContributions.TaintedAmountChanged(tainted, 9, receiver.Creature, null, context); tainted.Amount = 9;
        owner.Creature.Domain = true;
        Check((int)Call("EffectiveTaintedAmount", tainted)! == 3, "Mixed Tainted preserves only independent player contribution in shared domain");
        owner.Creature.Domain = false;
        Check((int)Call("EffectiveTaintedAmount", tainted)! == 9, "Tainted reverts to remaining native amount after domain expires");
        owner.Creature.Domain = true; s.Creatures.Remove(enemy.Creature); galvanic.Owner = enemy.Creature;
        await CallTask("GalvanicDamage", context, receiver.Creature, 4m, ValueProp.Unpowered, null, null, galvanic);
        Check(CreatureCmd.Damages == 2, "Detached source is not assigned active enemy provenance");
    }
    private static void Wither()
    {
        var (s, owner, receiver, enemy) = Fixture(); var card = s.CreateCard<Wither>(receiver);
        Call("EnemyWitherUpgrade", card, enemy);
        Check(card.DynamicVars.Damage.BaseValue == 2m, "Teammate domain must stop hostile Wither upgrades");
        Call("SetWitherUpgradeCount", enemy, 1);
        Check(enemy.WitherUpgradeCount == 0, "Canceled hostile upgrade is not banked for future cards");
        owner.Creature.Domain = false;
        Call("EnemyWitherUpgrade", card, enemy); Call("SetWitherUpgradeCount", enemy, 1);
        Check(card.DynamicVars.Damage.BaseValue == 5m && enemy.WitherUpgradeCount == 1, "New upgrade after domain expiration executes normally");
        owner.Creature.Domain = true;
        Check((decimal)Call("WitherDamageWithoutEnemyContribution", card, receiver.Creature, 5m)! == 2m, "Shared domain suppresses enemy upgrade only, preserving player Wither base damage");
        var beast = s.CreateCard<Volibear_T02>(receiver);
        Check((decimal)Call("WitherDamageWithoutEnemyContribution", beast, receiver.Creature, 5m)! == 5m, "New native beast does not inherit the material's status damage contribution");
        Check((decimal)Call("WitherDamageWithoutEnemyContribution", card, receiver.Creature, 5m)! == 2m, "Original Wither retains its own identity and contribution after a separate beast exists");
        s.Creatures.Remove(enemy.Creature);
        Call("SetWitherUpgradeCount", enemy, 2);
        Check(enemy.WitherUpgradeCount == 2, "Detached enemy does not borrow live encounter policy");
    }
    private static void Scalars()
    {
        var (_, owner, receiver, enemy) = Fixture(); var power = new PowerModel { Owner = enemy.Creature };
        decimal Read(string name, decimal result, decimal? input = null)
        {
            object?[] args = input is null ? [power, enemy.Creature, result] : [power, enemy.Creature, input.Value, result];
            typeof(DomainEnemyEffects).GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic)!.Invoke(null, args);
            return (decimal)args[^1]!;
        }
        Check(Read("NeutralMultiplier", 1.5m) == 1.5m, "Independent damage increase must survive domain");
        Check(Read("NeutralMultiplier", 0.5m) == 1m, "Native reduction is suppressed");
        Check(Read("NeutralMultiplier", 1m) == 1m, "Neutral multiplier unchanged");
        foreach (string name in new[] { "NeutralHpLoss", "NeutralShell" })
        {
            Check(Read(name, 24m, 17m) == 24m, "Independent HP loss increase must survive domain: " + name);
            Check(Read(name, 1m, 17m) == 17m, "Native HP loss protection is suppressed: " + name);
            Check(Read(name, 0m, 0m) == 0m, "Zero input stays zero: " + name);
        }
        owner.Creature.Domain = false;
        Check(Read("NeutralMultiplier", 0.5m) == 0.5m && Read("NeutralHpLoss", 1m, 17m) == 1m,
              "Inactive domain leaves original contributions untouched");
    }
    private static void Holder()
    {
        var (s, owner, receiver, _) = Fixture(); receiver.Creature.Domain = true;
        var first = owner.Creature.GetPower<DomainPower>()!; var second = receiver.Creature.GetPower<DomainPower>()!;
        bool Contributes(DomainPower power) => (bool)typeof(DomainPlayerStatContributions).GetMethod("Contributes", BindingFlags.Static | BindingFlags.NonPublic)!.Invoke(null, [power])!;
        Check(Contributes(first) && !Contributes(second), "Two domains contribute stat compensation once");
        s.Creatures.Remove(owner.Creature);
        Check(Contributes(second) && !Contributes(first), "Detached first holder must not block live holder compensation");
        s.Creatures.Add(owner.Creature); owner.Creature.CombatState = new TestCombat();
        Check(Contributes(second) && !Contributes(first), "Stale combat pointer cannot claim stat compensation");
        owner.Creature.CombatState = s; owner.Creature.IsAlive = false;
        Check(Contributes(second) && !Contributes(first), "Dead first holder does not duplicate or block compensation");
        receiver.Creature.Domain = false;
        Check(!Contributes(second), "No compensation after last field expires");
    }
    public static async Task Main(string[] args)
    {
        string test = args.Single();
        switch (test) { case "scope": Scope(); break; case "statuses": await Statuses(); break; case "powers": await Powers(); break; case "wither": Wither(); break; case "scalars": Scalars(); break; case "holder": Holder(); break; default: throw new Exception("Unknown case"); }
        Console.WriteLine($"DOMAIN_TEAM_PROTECTION_PASS {test} checks={checks} engine=STUBBED native-network=NOT_RUN");
    }
}
