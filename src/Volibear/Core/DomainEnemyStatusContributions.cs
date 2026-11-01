using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Core;

/// <summary>
/// Finite native enemy status contributions. Explicit generation callsites establish
/// provenance, never current side, null creator or a global status-type heuristic.
/// Native pile/exhaust/draw and player-owned generation remain untouched.
/// </summary>
public static partial class DomainEnemyStatusContributions
{
    private const string HarmonyId = "Volibear.DomainEnemyStatusContributions";
    private sealed record Origin(ICombatState Combat, Creature Receiver, Creature Enemy, int Generation);
    private sealed record Site(Type Owner, string Method, Type Card, bool Direct = false, int Count = 1);
    private static readonly Site[] Sites =
    [
        new(typeof(MechaKnight), "FlamethrowerMove", typeof(Burn)),
        new(typeof(TestSubject), "BurningGrowlMove", typeof(Burn)),
        new(typeof(Aeonglass), "IncreasingIntensityMove", typeof(Wither)),
        new(typeof(Chomper), "ScreechMove", typeof(Dazed)),
        new(typeof(EyeWithTeeth), "DistractMove", typeof(Dazed)),
        new(typeof(HauntedShip), "HauntMove", typeof(Dazed)),
        new(typeof(LeafSlimeS), "GoopMove", typeof(Slimed)),
        new(typeof(LeafSlimeM), "StickyShotMove", typeof(Slimed)),
        new(typeof(TwigSlimeM), "StickyShotMove", typeof(Slimed)),
        new(typeof(SlimedBerserker), "VomitIchorMove", typeof(Slimed)),
        new(typeof(Myte), "ToxicMove", typeof(Toxic)),
        new(typeof(PhrogParasite), "InfectMove", typeof(Infection)),
        new(typeof(Wriggler), "WriggleMove", typeof(Infection)),
        new(typeof(Vantom), "DismemberMove", typeof(Wound)),
        new(typeof(WitheringPresencePower), "AfterCardPlayed", typeof(Wither)),
        new(typeof(PainfulStabsPower), "AfterAttack", typeof(Wound)),
        new(typeof(Noisebot), "NoiseMove", typeof(Dazed), true, 2),
        new(typeof(SoulFysh), "BeckonMove", typeof(Beckon), true, 2),
        new(typeof(SoulFysh), "GazeMove", typeof(Beckon), true),
        new(typeof(PersonalHivePower), "AfterDamageReceived", typeof(Dazed), true)
    ];
    private static readonly Dictionary<MethodBase, Site> BoundSites = new();
    private static ConditionalWeakTable<CardModel, Origin> _origins = new();
    private static int _generation;
    private static bool _installed;

    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony(HarmonyId);
        try
        {
            foreach (var site in Sites)
            {
                var method = MoveNext(Required(site.Owner, site.Method));
                BoundSites[method] = site;
                harmony.Patch(method, transpiler: Handler(nameof(EnemyCreationSite)));
            }
            foreach (var type in new[] { typeof(Burn), typeof(Wither), typeof(Toxic), typeof(Infection), typeof(Beckon) })
                harmony.Patch(MoveNext(Required(type, "OnTurnEndInHand")), transpiler: Handler(nameof(StatusDamageSite)));
            InstallWitherContributions(harmony);
            InstallStatusPowerEffects(harmony);
            harmony.Patch(AccessTools.Method(typeof(CombatManager), nameof(CombatManager.Reset), new[] { typeof(bool) })!,
                prefix: Handler(nameof(Reset)));
            CombatManager.Instance.CombatSetUp += _ => Reset();
            CombatManager.Instance.CombatEnded += _ => Reset();
            _installed = true;
        }
        catch { harmony.UnpatchAll(HarmonyId); BoundSites.Clear(); throw; }
    }

    private static HarmonyMethod Handler(string name) => new(typeof(DomainEnemyStatusContributions), name);
    private static MethodInfo Required(Type type, string name) => AccessTools.Method(type, name)
        ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo MoveNext(MethodInfo method) => Required(
        method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException($"Missing native state machine: {method}"), "MoveNext");

    private static IEnumerable<CodeInstruction> EnemyCreationSite(IEnumerable<CodeInstruction> instructions, MethodBase __originalMethod)
    {
        var site = BoundSites[__originalMethod];
        var source = __originalMethod.DeclaringType!.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Single(field => field.Name == "<>4__this" && field.FieldType == site.Owner);
        int matches = 0;
        foreach (var instruction in instructions)
        {
            MethodInfo? replacement = null;
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(CardPileCmd))
            {
                if (!site.Direct && method.Name == nameof(CardPileCmd.AddToCombatAndPreview) && method.IsGenericMethod &&
                    method.GetGenericArguments().SequenceEqual(new[] { site.Card }))
                {
                    var name = method.GetParameters()[0].ParameterType == typeof(Creature) ? nameof(AddEnemyStatusOne) : nameof(AddEnemyStatuses);
                    replacement = Required(typeof(DomainEnemyStatusContributions), name).MakeGenericMethod(site.Card);
                }
                else if (site.Direct && method.Name == nameof(CardPileCmd.AddGeneratedCardToCombat))
                    replacement = Required(typeof(DomainEnemyStatusContributions), nameof(AddEnemyGenerated));
            }
            if (replacement is null) { yield return instruction; continue; }
            matches++;
            var load = new CodeInstruction(OpCodes.Ldarg_0);
            load.labels.AddRange(instruction.labels);
            load.blocks.AddRange(instruction.blocks);
            yield return load;
            yield return new CodeInstruction(OpCodes.Ldfld, source);
            yield return new CodeInstruction(OpCodes.Call, replacement);
        }
        if (matches != site.Count) throw new InvalidOperationException($"Status generation site drift: {site.Owner.Name}.{site.Method}: {matches}/{site.Count}");
    }

    private static Creature SourceCreature(AbstractModel source) => source switch
    { MonsterModel monster => monster.Creature, PowerModel power => power.Owner, _ => throw new InvalidOperationException("Unregistered status source") };
    private static bool EnemySource(AbstractModel source, Creature receiver, out Creature enemy)
    {
        enemy = SourceCreature(source);
        return enemy.IsEnemy && !enemy.IsPlayer && receiver.IsPlayer && receiver.CombatState is { } combat &&
            ReferenceEquals(enemy.CombatState, combat) && combat.ContainsCreature(enemy);
    }

    private static Task AddEnemyStatusOne<T>(Creature target, PileType pile, int count, Player? creator,
        CardPilePosition position, AbstractModel source) where T : CardModel =>
        AddEnemyStatuses<T>(new[] { target }, pile, count, creator, position, source);

    // Native AddToCombatAndPreview's small creation/preview sequence, with provenance
    // recorded before AddGenerated's history and hooks. No ambient tagging scope.
    private static async Task AddEnemyStatuses<T>(IEnumerable<Creature> targets, PileType pile, int count,
        Player? creator, CardPilePosition position, AbstractModel source) where T : CardModel
    {
        foreach (var target in targets)
        {
            Player player = target.Player ?? target.PetOwner!;
            if (player.Creature.IsDead) continue;
            if (EnemySource(source, player.Creature, out _) && DomainPower.IsActive(player.Creature)) continue;
            var results = new CardPileAddResult[count];
            for (int i = 0; i < count; i++)
            {
                var card = target.CombatState?.CreateCard<T>(player);
                if (card is not null) results[i] = await AddEnemyGenerated(card, pile, creator, position, source);
            }
            if (!LocalContext.IsMe(player)) continue;
            if (pile == PileType.Hand) await Cmd.Wait(0.1f);
            else
            {
                CardCmd.PreviewCardPileAdd(results, 1.2f,
                    results.Length <= 5 ? CardPreviewStyle.HorizontalLayout : CardPreviewStyle.MessyLayout);
                await Cmd.Wait(1f);
            }
        }
    }

    private static Task<CardPileAddResult> AddEnemyGenerated(CardModel card, PileType pile, Player? creator,
        CardPilePosition position, AbstractModel source)
    {
        // Only called at the enumerated native sites above. Player-owned copies of
        // these powers are deliberately native, not assumed hostile by class name.
        var receiver = card.Owner.Creature;
        if (EnemySource(source, receiver, out var enemy))
        {
            var combat = receiver.CombatState!;
            if (DomainPower.IsActive(receiver))
            {
                // Direct native sites already created the card. Undo that registration
                // before it can enter a pile/history; unsuccessful previews are ignored.
                combat.RemoveCard(card);
                return Task.FromResult(new CardPileAddResult { success = false, cardAdded = card });
            }
            _origins.Remove(card);
            _origins.Add(card, new Origin(combat, receiver, enemy, _generation));
        }
        return CardPileCmd.AddGeneratedCardToCombat(card, pile, creator, position);
    }

    private static bool Suppress(CardModel card, Creature receiver)
    {
        if (BeastForms.Shape(card) != BeastShape.None || !DomainPower.IsActive(receiver)) return false;
        var seen = new HashSet<CardModel>(ReferenceEqualityComparer.Instance);
        for (CardModel? current = card; current is not null && seen.Add(current); current = current.CloneOf)
        {
            if (!_origins.TryGetValue(current, out var origin)) continue;
            return origin.Generation == _generation && ReferenceEquals(origin.Receiver, receiver) &&
                ReferenceEquals(origin.Combat, receiver.CombatState) && ReferenceEquals(card.Owner.Creature, receiver) &&
                ReferenceEquals(card.CombatState, origin.Combat);
        }
        return false;
    }

    private static IEnumerable<CodeInstruction> StatusDamageSite(IEnumerable<CodeInstruction> instructions)
    {
        var variable = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            new[] { typeof(PlayerChoiceContext), typeof(Creature), typeof(DamageVar), typeof(CardModel) })!;
        var amount = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            new[] { typeof(PlayerChoiceContext), typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(CardModel) })!;
        int matches = 0;
        foreach (var instruction in instructions)
        {
            bool isVariable = instruction.Calls(variable);
            if (isVariable || instruction.Calls(amount))
            {
                matches++;
                instruction.opcode = OpCodes.Call;
                instruction.operand = Required(typeof(DomainEnemyStatusContributions), isVariable ? nameof(StatusDamageVar) : nameof(StatusDamageAmount));
            }
            yield return instruction;
        }
        if (matches != 1) throw new InvalidOperationException($"Expected one native status damage contribution; found {matches}.");
    }
    private static Task<IEnumerable<DamageResult>> StatusDamageVar(PlayerChoiceContext context, Creature receiver,
        DamageVar damage, CardModel card) => Suppress(card, receiver)
            ? Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>())
            : CreatureCmd.Damage(context, receiver, WitherDamageWithoutEnemyContribution(card, receiver, damage.BaseValue), damage.Props, card);
    private static Task<IEnumerable<DamageResult>> StatusDamageAmount(PlayerChoiceContext context, Creature receiver,
        decimal amount, ValueProp props, CardModel card) => Suppress(card, receiver)
            ? Task.FromResult<IEnumerable<DamageResult>>(Array.Empty<DamageResult>())
            : CreatureCmd.Damage(context, receiver, amount, props, card);

    // Dazed ethereal cleanup, Wound's lack of effects, Slimed's beneficial Draw and
    // exhaust, and all FranticEscape generation/play/cost rules are intentionally
    // untouched. FranticEscape aids the player and is NOT an enemy status attack.
    public static void Reset()
    {
        _generation++;
        _origins = new ConditionalWeakTable<CardModel, Origin>();
        _witherContributions = new ConditionalWeakTable<CardModel, WitherContribution>();
        ResetStatusPowerEffects();
    }
}
