using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;

#if STS2_0_113
using AttackTarget = MegaCrit.Sts2.Core.Entities.Creatures.DamageTargetData;
#else
using AttackTarget = MegaCrit.Sts2.Core.Entities.Creatures.Creature;
#endif

namespace Volibear.Core;

/// <summary>
/// Narrow adapters around verified native boundaries, not a second card executor.
/// Install during Mod initialization BEFORE the first card is played: a domain may
/// be acquired halfway through the first play, or only during one of its replays.
/// No generic Unpowered listener and no enemy power suppression live here.
/// </summary>
public static partial class CardResolutionHooks
{
    internal sealed class PlayScope(CardModel card, PlayScope? previous, long id, PlayerChoiceContext choices)
    {
        internal readonly CardModel Card = card;
        internal readonly PlayerChoiceContext Choices = choices;
        internal readonly PlayScope? Previous = previous;
        internal readonly long Id = id;
        internal readonly int PriorLightning = LightningBatches.GetTurnCount(card.Owner.Creature);
        internal readonly CardResolutionPlayGate Gate = new();
    }

    internal sealed class PlayMoveFrame(PlayScope? scope, PlayScope? previous, Task native)
    {
        internal readonly PlayScope? Scope = scope;
        internal readonly PlayScope? Previous = previous;
        internal readonly Task Native = native;
    }

    private sealed class Purification(DomainPower domain)
    {
        internal readonly DomainPower Domain = domain;
        internal bool Started;
    }

    private static readonly AsyncLocal<PlayScope?> Current = new();
    private static readonly HashSet<PlayScope> ActivePlays = [];
    private static ConditionalWeakTable<CardModel, Purification> _purifications = new();
    private static ConditionalWeakTable<Task, PlayScope> _playTasks = new();
    private static long _nextPlay;
    private static bool _installed;

    public static long? CurrentPlayId(CardModel card) => Current.Value is { } scope &&
        !scope.Gate.Closed && ReferenceEquals(scope.Card, card) ? scope.Id : null;

    /// <summary>Pre-play lightning count, captured once before the actual wrapper;
    /// native replay indices and nested plays never overwrite this snapshot.</summary>
    public static int PriorLightningCount(CardModel card)
    {
        for (var scope = Current.Value; scope is not null; scope = scope.Previous)
            if (!scope.Gate.Closed && ReferenceEquals(scope.Card, card)) return scope.PriorLightning;
        throw new InvalidOperationException("PriorLightningCount requires this card's active native play scope.");
    }

    /// <summary>Exact native wrapper context, never a replacement throwing context.</summary>
    public static PlayerChoiceContext CurrentChoices(CardModel card)
    {
        for (var scope = Current.Value; scope is not null; scope = scope.Previous)
            if (!scope.Gate.Closed && ReferenceEquals(scope.Card, card)) return scope.Choices;
        throw new InvalidOperationException("CurrentChoices requires this card's active native play scope.");
    }

    public static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony(OrdinaryAttackOwnerV1);
        try
        {
            var play = Required(typeof(CardModel), nameof(CardModel.OnPlayWrapper),
                typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(ResourceInfo), typeof(bool));
            // Native callers can inline the tiny async entry stub and bypass its
            // detour. The actual state machine is the verified lifecycle boundary.
            NativeTranspiler.Patch(harmony, MoveNext(play), transpiler: Handler(nameof(PlayMoveLifecycle)));

            // AttackCommand.Execute calls the native multi-target Damage exactly once
            // per ordinary hit. This callsite, not damage property guesses, defines a
            // segment (AOE is one segment; a three-hit builder is three segments).
            NativeTranspiler.Patch(harmony, MoveNext(Required(typeof(AttackCommand), nameof(AttackCommand.Execute),
                typeof(PlayerChoiceContext))), transpiler: Handler(nameof(AttackDamageCallsite)));

            // Only the Add that belongs to an actual Draw is wrapped. Retrieve/move
            // operations elsewhere are not draws, even inside another draw response.
            // PBE split the public Draw wrapper from its async body; stable keeps the body in Draw.
            NativeTranspiler.Patch(harmony, MoveNext(Required(typeof(CardPileCmd),
#if STS2_BETA
                "DrawInternal",
#else
                nameof(CardPileCmd.Draw),
#endif
                typeof(PlayerChoiceContext), typeof(decimal), typeof(Player), typeof(bool))),
                transpiler: Handler(nameof(DrawAddCallsite)));
            // Filter the native membership predicate, not the tiny iterator entry
            // stub that callers can inline. Only the exact purifying card is muted.
            harmony.Patch(Required(typeof(CombatState), "Contains", typeof(AbstractModel)),
                prefix: Handler(nameof(FilterPurifiedCardHooks)));
            harmony.Patch(Required(typeof(CombatManager), nameof(CombatManager.Reset), typeof(bool)),
                prefix: Handler(nameof(Reset)));
            CombatManager.Instance.CombatEnded += _ => Reset();
            CombatManager.Instance.CombatSetUp += _ => Reset();
            _installed = true;
        }
        catch
        {
            harmony.UnpatchAll(harmony.Id);
            throw; // A changed native callsite is a compatibility failure, not a fallback.
        }
    }

    private static HarmonyMethod Handler(string name) => new(typeof(CardResolutionHooks), name);
    private static MethodInfo Required(Type type, string name, params Type[] parameters) =>
        AccessTools.Method(type, name, parameters) ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo MoveNext(MethodInfo method) =>
        AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException($"{method} has no async state machine."), "MoveNext")
        ?? throw new MissingMethodException(method.Name, "MoveNext");

    private static IEnumerable<CodeInstruction> PlayMoveLifecycle(IEnumerable<CodeInstruction> instructions,
        ILGenerator generator, MethodBase __originalMethod)
    {
        var stateMachine = __originalMethod.DeclaringType!;
        var fields = stateMachine.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
        var builder = fields.Single(field => field.FieldType == typeof(AsyncTaskMethodBuilder));
        var card = fields.Single(field => field.FieldType == typeof(CardModel) && field.Name == "<>4__this");
        var choices = fields.Single(field => field.FieldType == typeof(PlayerChoiceContext) && field.Name == "choiceContext");
        var state = fields.Single(field => field.FieldType == typeof(int) && field.Name == "<>1__state");
        var taskGetter = AccessTools.PropertyGetter(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.Task));
        var frame = generator.DeclareLocal(typeof(PlayMoveFrame));
        var code = instructions.ToList();
        if (!code.Any(instruction => instruction.opcode == OpCodes.Ret))
            throw new InvalidOperationException("Native card-play state machine has no return boundary.");
        // Read Task through the actual builder by address, NEVER a boxed builder copy.
        // The first getter can return a provisional promise. LeavePlayMove reads
        // the builder again and explicitly rebinds this same frame to its real box.
        var patched = new List<CodeInstruction>
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Call, taskGetter),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, card),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, choices),
            new(OpCodes.Call, Required(typeof(CardResolutionHooks), nameof(EnterPlayMove),
                typeof(Task), typeof(CardModel), typeof(int), typeof(PlayerChoiceContext))), new(OpCodes.Stloc, frame)
        };
        foreach (var instruction in code)
        {
            if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame);
                load.labels.AddRange(instruction.labels);
                load.blocks.AddRange(instruction.blocks);
                instruction.labels.Clear();
                instruction.blocks.Clear();
                patched.Add(load);
                patched.Add(new CodeInstruction(OpCodes.Ldarg_0));
                patched.Add(new CodeInstruction(OpCodes.Ldflda, builder));
                patched.Add(new CodeInstruction(OpCodes.Call, taskGetter));
                patched.Add(new CodeInstruction(OpCodes.Ldarg_0));
                patched.Add(new CodeInstruction(OpCodes.Ldfld, state));
                patched.Add(new CodeInstruction(OpCodes.Call,
                    Required(typeof(CardResolutionHooks), nameof(LeavePlayMove),
                        typeof(PlayMoveFrame), typeof(Task), typeof(int))));
            }
            patched.Add(instruction);
        }
        return patched;
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static PlayMoveFrame EnterPlayMove(Task native, CardModel card, int nativeState, PlayerChoiceContext choices)
    {
        var previous = Current.Value;
        if (!_playTasks.TryGetValue(native, out var scope) && nativeState == -1)
        {
            scope = new PlayScope(card, previous, Interlocked.Increment(ref _nextPlay), choices);
            _playTasks.Add(native, scope);
            ActivePlays.Add(scope);
        }
        // A continuation after combat Reset must not manufacture a new actual play.
        Current.Value = scope;
        return new PlayMoveFrame(scope, previous, native);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void LeavePlayMove(PlayMoveFrame frame, Task currentNative, int nativeState)
    {
        if (frame.Scope is { } scope)
        {
            // First AwaitUnsafeOnCompleted can replace the provisional promise with
            // an AsyncStateMachineBox. Rebind using this exact MoveNext frame; never
            // infer identity from a segment/card or invent another scope on resume.
            if (!ReferenceEquals(frame.Native, currentNative))
            {
                _playTasks.Remove(frame.Native);
                if (_playTasks.TryGetValue(currentNative, out var existing))
                {
                    if (!ReferenceEquals(existing, scope))
                        throw new InvalidOperationException("Native play Task is bound to another actual play.");
                }
                else if (!scope.Gate.Closed) _playTasks.Add(currentNative, scope);
            }
            if (currentNative.IsCompleted)
            {
                scope.Gate.Close();
                ActivePlays.Remove(scope);
                _playTasks.Remove(currentNative);
            }
        }
        Current.Value = frame.Previous;
    }

    private static IEnumerable<CodeInstruction> AttackDamageCallsite(IEnumerable<CodeInstruction> instructions, ILGenerator generator)
    {
        var native = DomainSteamEruptionEffects.NativeDamage
            ?? throw new MissingMethodException(typeof(CreatureCmd).FullName, nameof(CreatureCmd.Damage));
        return NativeAwaitedCall.Compose(instructions, generator, native,
            AccessTools.Method(typeof(CardResolutionHooks), nameof(CaptureOrdinaryAttack)),
            AccessTools.Method(typeof(CardResolutionHooks), nameof(ComposeOrdinaryAttackAwaiter)));
    }

    private static IEnumerable<CodeInstruction> DrawAddCallsite(IEnumerable<CodeInstruction> instructions,
        ILGenerator generator, MethodBase __originalMethod)
    {
        var parameters = new[] { typeof(CardModel), typeof(CardPile), typeof(CardPilePosition), typeof(AbstractModel), typeof(bool) };
        var code = ReplaceOneCall(instructions, Required(typeof(CardPileCmd), nameof(CardPileCmd.Add), parameters),
            Required(typeof(CardResolutionHooks), nameof(AddDrawnCard), parameters));
        var hooks = new[] { typeof(ICombatState), typeof(PlayerChoiceContext), typeof(CardModel), typeof(bool) };
        code = ReplaceOneCall(code, Required(typeof(Hook), nameof(Hook.AfterCardDrawn), hooks),
            Required(typeof(CardResolutionHooks), nameof(DispatchDrawHooks), hooks));
        return DrawMoveLifecycle(code, generator, __originalMethod);
    }

    private static IEnumerable<CodeInstruction> ReplaceOneCall(IEnumerable<CodeInstruction> instructions,
                                                               MethodInfo original, MethodInfo replacement)
    {
        var code = instructions.ToList();
        var found = 0;
        foreach (var instruction in code)
        {
            if ((instruction.opcode == OpCodes.Call || instruction.opcode == OpCodes.Callvirt) &&
                Equals(instruction.operand, original))
            {
                instruction.opcode = OpCodes.Call;
                instruction.operand = replacement;
                found++;
            }
        }
        if (found != 1) throw new InvalidOperationException($"Expected one native {original} callsite; found {found}.");
        return code;
    }

    internal const string OrdinaryAttackOwnerV1 = "Volibear.CardResolution";

    // Captured at the verified ordinary-hit callsite, before native/foreign dispatch.
    // A wrapper may suspend or run nested plays before producing its final results;
    // the paid identity belongs to this descriptor, never the later ambient scope.
    internal sealed class OrdinaryAttackObservation(PlayScope? scope, PlayerChoiceContext context,
        ValueProp props, Creature? dealer, CardModel? card)
    {
        internal readonly PlayScope? Scope = scope;
        internal readonly PlayerChoiceContext Context = context;
        internal readonly ValueProp Props = props;
        internal readonly Creature? Dealer = dealer;
        internal readonly CardModel? Card = card;
    }

    private readonly struct ExistingDamageAwaitable(TaskAwaiter<IEnumerable<DamageResult>> awaiter)
    {
        public TaskAwaiter<IEnumerable<DamageResult>> GetAwaiter() => awaiter;
    }

    private static OrdinaryAttackObservation CaptureOrdinaryAttack(PlayerChoiceContext context,
        IEnumerable<AttackTarget> targets, decimal amount, ValueProp props, Creature? dealer, CardModel? cardSource
#if STS2_BETA
        , CardPlay? cardPlay
#endif
#if STS2_0_113
        , ModifyDamageHookType hookType
#endif
        ) => new(Current.Value, context, props, dealer, cardSource);

    private static TaskAwaiter<IEnumerable<DamageResult>> ComposeOrdinaryAttackAwaiter(
        TaskAwaiter<IEnumerable<DamageResult>> native, OrdinaryAttackObservation observation) =>
        CompleteOrdinaryAttack(native, observation).GetAwaiter();

    // Shared by the live native consumer and managed contribution probes. Both retain
    // the exact captured scope and await the complete native/foreign operation before
    // Domain, then snapshot ordinary responders only after Domain has drained.
    [MethodImpl(MethodImplOptions.NoInlining)]
    internal static async Task<IEnumerable<DamageResult>> CompleteOrdinaryAttack(
        TaskAwaiter<IEnumerable<DamageResult>> native, OrdinaryAttackObservation observation)
    {
        var results = (await new ExistingDamageAwaitable(native)).ToArray();
        var scope = observation.Scope;
        if (scope is not null && !scope.Gate.Closed && results.Length > 0 &&
            ReferenceEquals(observation.Card, scope.Card) && ReferenceEquals(observation.Dealer, scope.Card.Owner.Creature) &&
            observation.Props.HasFlag(ValueProp.Move))
        {
            await DomainPower.AttachAfterOrdinarySegment(observation.Context, scope);
            if (scope.Card.Type == CardType.Attack)
            {
                var owner = scope.Card.Owner.Creature;
                var responders = owner.Powers.OfType<IOrdinarySegmentResponder>().ToArray();
                foreach (var responder in responders)
                {
                    if (scope.Gate.Closed || !owner.IsAlive || CombatManager.Instance.IsOverOrEnding) break;
                    await responder.AfterOrdinarySegment(observation.Context, scope.Card, results);
                }
            }
        }
        return results;
    }

    // Managed callers share the same successful-completion implementation. Production
    // no longer substitutes this dispatcher for the native AttackCommand damage call.
    internal static async Task<IEnumerable<DamageResult>> OrdinaryAttackPipelineV1(PlayerChoiceContext context,
        ValueProp props, Creature? dealer, CardModel? cardSource, Func<Task<IEnumerable<DamageResult>>> nativeDamage)
    {
        var observation = new OrdinaryAttackObservation(Current.Value, context, props, dealer, cardSource);
        return await CompleteOrdinaryAttack(nativeDamage().GetAwaiter(), observation);
    }

    private static async Task<CardPileAddResult> AddDrawnCard(CardModel card, CardPile pile,
        CardPilePosition position, AbstractModel? clonedBy, bool skipVisuals)
    {
        var draw = CurrentDraw.Value;
        // Qualify BEFORE Add's pile-change hooks. Suppress only this exact card's own
        // harmful hooks, not powers/relics listening to the draw/exhaust transaction.
        if (card.Type is CardType.Status or CardType.Curse && DomainPower.IsActive(card.Owner.Creature))
        {
            var domain = card.Owner.Creature.GetPower<DomainPower>()!;
            _purifications.Remove(card);
            _purifications.Add(card, new Purification(domain));
        }
        try
        {
            var result = await CardPileCmd.Add(card, pile, position, clonedBy, skipVisuals);
            if (draw is { Closed: false } && draw.Generation == _drawGeneration &&
                !CombatManager.Instance.IsOverOrEnding)
                await draw.Request.Observer(card);
            return result;
        }
        catch
        {
            _purifications.Remove(card);
            throw;
        }
    }

    private static bool FilterPurifiedCardHooks(AbstractModel model, ref bool __result)
    {
        var card = model switch
        {
            CardModel value => value,
            EnchantmentModel value when value.HasCard => value.Card,
            AfflictionModel value when value.HasCard => value.Card,
            _ => null
        };
        if (card is null || !_purifications.TryGetValue(card, out _)) return true;
        __result = false;
        return false;
    }

    internal static bool TryBeginPurification(CardModel card, DomainPower power)
    {
        if (!_purifications.TryGetValue(card, out var mark) || mark.Started ||
            !ReferenceEquals(mark.Domain, power)) return false;
        mark.Started = true;
        return true;
    }

    private static Task DispatchDrawHooks(ICombatState combatState, PlayerChoiceContext choiceContext,
        CardModel card, bool fromHandDraw) => _purifications.TryGetValue(card, out var mark)
            ? PurifyThenDispatch(combatState, choiceContext, card, fromHandDraw, mark)
            : Hook.AfterCardDrawn(combatState, choiceContext, card, fromHandDraw);

    private static async Task PurifyThenDispatch(ICombatState combat, PlayerChoiceContext context,
        CardModel card, bool fromHandDraw, Purification mark)
    {
        try
        {
            // Give purification its required early priority, including when hand-entry
            // responses removed the power. The original native dispatcher remains in
            // charge of every other listener and their ordering; our normal early hook
            // is idempotent when that dispatcher visits the domain power again.
            context.PushModel(mark.Domain);
            try { await mark.Domain.AfterCardDrawnEarly(context, card, fromHandDraw); }
            finally { context.PopModel(mark.Domain); }
            await Hook.AfterCardDrawn(combat, context, card, fromHandDraw);
        }
        finally { _purifications.Remove(card); }
    }

    public static void Reset()
    {
        foreach (var scope in ActivePlays) scope.Gate.Close();
        ActivePlays.Clear();
        Current.Value = null;
        _purifications = new ConditionalWeakTable<CardModel, Purification>();
        _playTasks = new ConditionalWeakTable<Task, PlayScope>();
        ResetObservedDraws();
    }
}
