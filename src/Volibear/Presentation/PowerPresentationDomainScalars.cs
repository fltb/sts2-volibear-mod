using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Presentation;

/// <summary>Only actual native Damage/GainBlock calls can admit a scalar receipt.
/// Nested Hook queries are barriers; previews never acquire an admitted frame.</summary>
internal static class PowerPresentationDomainScalars
{
    private sealed record Entry(Creature Enemy, AbstractModel Source, decimal? Cap = null,
        MegaCrit.Sts2.Core.Combat.ICombatState? Combat = null);
    private sealed class Frame(string hook, Frame? previous)
    {
        internal readonly string Hook = hook;
        internal readonly Frame? Previous = previous;
        internal readonly List<Entry> Entries = [];
        internal bool Claimed;
    }
    private sealed record NativeSite(MethodInfo Target, int Count);
    private sealed record NativeManifest(string Label, NativeSite[] Sites);
    private static readonly Dictionary<MethodBase, NativeManifest> Manifests = [];
    private static readonly HashSet<MethodBase> KeywordBodies = [];
    [ThreadStatic] private static Frame? pending;
    [ThreadStatic] private static Frame? active;
    internal static void Install(Harmony h)
    {
        foreach (var name in new[] { nameof(Hook.ModifyDamage), nameof(Hook.ModifyHpLost), nameof(Hook.ModifyBlock),
            nameof(Hook.ModifyPowerAmountReceived), nameof(Hook.ShouldClearBlock), nameof(Hook.ShouldPlay),
            nameof(Hook.ModifyEnergyCostInCombat), nameof(Hook.ModifyKeywordsInCombat) })
            h.Patch(AccessTools.Method(typeof(Hook), name), prefix: new(typeof(PowerPresentationDomainScalars), nameof(EnterHook)),
                finalizer: new(typeof(PowerPresentationDomainScalars), nameof(LeaveHook)));
        var damage = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            [typeof(PlayerChoiceContext), typeof(IEnumerable<Creature>), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]);
        var block = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.GainBlock),
            [typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(CardPlay), typeof(bool)]);
        var apply = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Apply),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)]);
        var modify = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)]);
        var clear = AccessTools.Method(typeof(Creature), "ClearBlock");
        var auto = AccessTools.Method(typeof(CardCmd), nameof(CardCmd.AutoPlay));
        var play = AccessTools.Method(typeof(MegaCrit.Sts2.Core.GameActions.PlayCardAction), "ExecuteAction");
        var spend = AccessTools.Method(typeof(CardModel), nameof(CardModel.SpendResources));
        var turnEndCard = AccessTools.Method(typeof(CardModel), nameof(CardModel.OnTurnEndInHandWrapper));
        var turnEnd = AccessTools.Method(typeof(MegaCrit.Sts2.Core.Combat.CombatManager), "DoTurnEnd");
        // Exact locked-game manifest: every admitted scalar receipt site, in native order.
        // AutoPlay has two distinct real sites (ShouldPlay then GetAmountToSpend); Damage
        // has one damage query and three independent hp-loss queries. A new, removed,
        // reordered or substituted call must fail rather than be counted loosely.
        var hookDamage = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyDamage));
        var hookHpLost = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyHpLost));
        var hookBlock = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyBlock));
        var hookPower = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyPowerAmountReceived));
        var hookClear = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldClearBlock));
        var hookPlay = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldPlay));
        var canPlay = AccessTools.Method(typeof(CardModel), nameof(CardModel.CanPlay),
            [typeof(UnplayableReason).MakeByRefType(), typeof(AbstractModel).MakeByRefType()]);
        var energyToSpend = AccessTools.Method(typeof(CardEnergyCost), nameof(CardEnergyCost.GetAmountToSpend));
        var keywords = AccessTools.PropertyGetter(typeof(CardModel), nameof(CardModel.Keywords));
        foreach (var (method, label, sites) in new (MethodInfo Method, string Label, NativeSite[] Sites)[]
        {
            (damage, "CreatureCmd.Damage", [new(hookDamage, 1), new(hookHpLost, 3)]),
            (block, "CreatureCmd.GainBlock", [new(hookBlock, 1)]),
            (apply, "PowerCmd.Apply", [new(hookPower, 1)]),
            (modify, "PowerCmd.ModifyAmount", [new(hookPower, 1)]),
            (clear, "Creature.ClearBlock", [new(hookClear, 1)]),
            (auto, "CardCmd.AutoPlay", [new(hookPlay, 1), new(energyToSpend, 1)]),
            (play, "PlayCardAction.ExecuteAction", [new(canPlay, 1)]),
            (spend, "CardModel.SpendResources", [new(energyToSpend, 1)]),
            (turnEndCard, "CardModel.OnTurnEndInHandWrapper", [new(keywords, 1)]),
            (turnEnd, "CombatManager.DoTurnEnd", [new(keywords, 1)]),
        })
        {
            var body = AccessTools.Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
            if (method == turnEndCard || method == turnEnd) KeywordBodies.Add(body);
            Manifests[body] = new(label, sites);
            // Bind the native call before TargetCosts replaces it with its resolved-target
            // wrapper. The receipt remains after the replacement call in the final body.
            h.Patch(body, transpiler: new(typeof(PowerPresentationDomainScalars), nameof(NativeCalls))
                { before = ["Volibear.TargetCosts"] });
        }
    }
    private static Frame Begin(string hook)
    {
        var frame = new Frame(hook, pending);
        pending = frame;
        return frame;
    }
    private static void EnterHook(MethodBase __originalMethod, out Frame? __state)
    {
        __state = active;
        active = null;
        if (pending is { Claimed: false } frame && frame.Hook == __originalMethod.Name)
        { frame.Claimed = true; active = frame; }
    }
    private static void LeaveHook(Exception? __exception, Frame? __state)
    {
        if (__exception is not null && active is { } failed && ReferenceEquals(pending, failed)) pending = failed.Previous;
        active = __state;
    }
    internal static bool IsCapturing => active is not null;
    internal static void Capture(Creature? enemy, AbstractModel source, MegaCrit.Sts2.Core.Combat.ICombatState? sourceCombat = null)
    {
        try
        {
            if (active is { } frame && enemy is { IsEnemy: true, IsPlayer: false } &&
                !frame.Entries.Any(e => ReferenceEquals(e.Enemy, enemy) && ReferenceEquals(e.Source, source)))
                frame.Entries.Add(new(enemy, source, Combat: sourceCombat ?? enemy.CombatState ?? (source as PowerModel)?.Owner.CombatState));
        }
        catch { }
    }
    internal static void CaptureCap(Creature? enemy, AbstractModel source, decimal cap)
    {
        try { if (active is { } frame && enemy is { IsEnemy: true, IsPlayer: false }) frame.Entries.Add(new(enemy, source, cap)); }
        catch { }
    }
    private static void Consumed(decimal actual, Frame frame)
    {
        try
        {
            foreach (var entry in frame.Entries)
                if (entry.Cap is null || actual > entry.Cap.Value)
                    PowerPresentationDomain.Suppressed(entry.Enemy, entry.Source, sourceCombat: entry.Combat);
        }
        catch { }
        finally { pending = frame.Previous; }
    }
    private static void ConsumedBoolean(bool accepted, Frame frame)
    {
        if (accepted) Consumed(1m, frame);
        else pending = frame.Previous;
    }
    private static void ConsumedInteger(int actual, Frame frame) => Consumed(actual, frame);
    private static void ConsumedKeywords(IReadOnlySet<CardKeyword> keywords, Frame frame)
    {
        try { if (!keywords.Contains(CardKeyword.Ethereal)) Consumed(1m, frame); }
        catch { }
        finally { pending = frame.Previous; }
    }
    private static void ValidateSites(MethodBase original, List<MethodInfo> actual)
    {
        if (!Manifests.TryGetValue(original, out var manifest))
            throw new InvalidOperationException($"Unpinned native domain scalar method: {original.DeclaringType?.FullName}.{original.Name}");
        var expected = manifest.Sites.SelectMany(site => Enumerable.Repeat(site.Target, site.Count)).ToArray();
        if (!actual.SequenceEqual(expected))
            throw new InvalidOperationException(
                $"Native domain scalar consumption sites drifted: {manifest.Label}; expected [{Describe(expected)}], actual [{Describe(actual)}]");
    }
    private static string Describe(IEnumerable<MethodInfo> methods) =>
        string.Join(", ", methods.Select(m => $"{m.DeclaringType?.Name}.{m.Name}"));
    private static IEnumerable<CodeInstruction> NativeCalls(IEnumerable<CodeInstruction> instructions, ILGenerator generator, MethodBase __originalMethod)
    {
        var frame = generator.DeclareLocal(typeof(Frame));
        var actual = new List<MethodInfo>();
        foreach (var old in instructions)
        {
            var instruction = new CodeInstruction(old);
            if (instruction.operand is not MethodInfo method)
            { yield return instruction; continue; }
            bool canPlay = method.DeclaringType == typeof(CardModel) && method.Name == nameof(CardModel.CanPlay);
            bool spend = method.DeclaringType == typeof(CardEnergyCost) && method.Name == nameof(CardEnergyCost.GetAmountToSpend);
            bool keywords = KeywordBodies.Contains(__originalMethod) && method == AccessTools.PropertyGetter(typeof(CardModel), nameof(CardModel.Keywords));
            if (!canPlay && !spend && !keywords && (method.DeclaringType != typeof(Hook) ||
                method.Name is not (nameof(Hook.ModifyDamage) or nameof(Hook.ModifyHpLost) or nameof(Hook.ModifyBlock) or
                    nameof(Hook.ModifyPowerAmountReceived) or nameof(Hook.ShouldClearBlock) or nameof(Hook.ShouldPlay))))
            { yield return instruction; continue; }
            actual.Add(method);
            var begin = new CodeInstruction(OpCodes.Ldstr, canPlay ? nameof(Hook.ShouldPlay) : spend ? nameof(Hook.ModifyEnergyCostInCombat) :
                keywords ? nameof(Hook.ModifyKeywordsInCombat) : method.Name);
            begin.labels.AddRange(instruction.labels); instruction.labels.Clear();
            begin.blocks.AddRange(instruction.blocks); instruction.blocks.Clear();
            yield return begin;
            yield return new(OpCodes.Call, AccessTools.Method(typeof(PowerPresentationDomainScalars), nameof(Begin)));
            yield return new(OpCodes.Stloc, frame);
            yield return instruction;
            yield return new(OpCodes.Dup);
            yield return new(OpCodes.Ldloc, frame);
            yield return new(OpCodes.Call, AccessTools.Method(typeof(PowerPresentationDomainScalars),
                keywords ? nameof(ConsumedKeywords) : spend ? nameof(ConsumedInteger) :
                method.ReturnType == typeof(bool) ? nameof(ConsumedBoolean) : nameof(Consumed)));
        }
        ValidateSites(__originalMethod, actual);
    }
}
