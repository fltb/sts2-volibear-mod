using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Runtime.ExceptionServices;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

namespace Volibear.Core;

public enum BeastShape { None = 0, Claw = 1, Body = 2 }
public sealed record BeastChange(CardModel Card, BeastShape Shape, ICombatState Combat);

/// <summary>
/// Combat-scoped behavior overlay on the SAME native card entity. No replacement card,
/// owner change, master-deck edit, duplicate payment, or second replay executor.
/// </summary>
public static class BeastForms
{
    private sealed class Form
    {
        internal required BeastShape Shape;
        internal required ICombatState Combat;
        internal required DynamicVarSet Vars;
        internal required HashSet<CardKeyword> Keywords;
        internal required BeastCostLedger<LocalCostModifier> Costs;
        internal required int OriginalCanonicalCost;
        internal required bool OriginalCostsX;
        internal required BeastCardMetadata Metadata;
        internal EnchantmentModel? OldEnchantment;
        internal AfflictionModel? OldAffliction;
    }

    private static ConditionalWeakTable<CardModel, Form> forms = new();
    private static readonly FieldInfo CostOwner = Field(typeof(CardEnergyCost), "_card");
    private static readonly FieldInfo CostBase = Field(typeof(CardEnergyCost), "_base");
    private static readonly FieldInfo CostLocals = Field(typeof(CardEnergyCost), "_localModifiers");
    private static readonly FieldInfo NativeCanonical = Field(typeof(CardEnergyCost), "<Canonical>k__BackingField");
    private static readonly FieldInfo NativeCostsX = Field(typeof(CardEnergyCost), "<CostsX>k__BackingField");
    private static readonly Dictionary<Type, MethodInfo> NativePlays = new();
    private static readonly Dictionary<Type, MethodInfo> NativeUpgrades = new();
    private static bool installed;

    /// <summary>Raised once, after conversion is fully observable; subscribers run serially.</summary>
    public static event Func<PlayerChoiceContext, BeastChange, Task>? Converted;

    public static BeastShape Shape(CardModel card)
    {
        if (forms.TryGetValue(card, out var form)) return form.Shape;
        return card is Volibear_T01 ? BeastShape.Claw : card is Volibear_T02 ? BeastShape.Body : BeastShape.None;
    }

    public static bool IsConverted(CardModel card) => forms.TryGetValue(card, out _);

    public static async Task<BeastShape> Convert(PlayerChoiceContext context, CardModel card)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(card);
        if (!installed) throw new InvalidOperationException("BeastForms.Install must run before conversion.");
        card.AssertMutable();
        var previous = Shape(card);
        if (previous != BeastShape.None) return previous;
        var combat = card.CombatState;
        if (combat is null || card.Owner?.PlayerCombatState is null || card.Pile?.IsCombatPile != true ||
            card.Pile.Type == PileType.Deck || ReferenceEquals(card, card.DeckVersion))
            throw new InvalidOperationException("Beast conversion requires a combat card, never a master-deck entity.");
        // Capture before installing the overlay. None of these identities are replaced.
        var shape = card.Type == CardType.Attack ? BeastShape.Claw : BeastShape.Body;
        var keywords = new HashSet<CardKeyword> { CardKeyword.Exhaust };
        if (card.GetKeywordsWithSources(KeywordSources.Local).Contains(CardKeyword.Retain)) keywords.Add(CardKeyword.Retain);
        var form = new Form
        {
            Shape = shape, Combat = combat, Vars = NewVars(shape), Keywords = keywords,
            Costs = new BeastCostLedger<LocalCostModifier>((int)CostBase.GetValue(card.EnergyCost)!, Locals(card.EnergyCost)),
            OriginalCanonicalCost = (int)NativeCanonical.GetValue(card.EnergyCost)!,
            OriginalCostsX = (bool)NativeCostsX.GetValue(card.EnergyCost)!,
            Metadata = BeastCardMetadata.Capture(card),
            OldEnchantment = card.Enchantment, OldAffliction = card.Affliction
        };
        forms.Add(card, form);
        // Native callers can inline the two trivial auto-getters before Harmony patches
        // them (observed in CardCmd.AutoPlay). Keep the SAME cost object but update its
        // real metadata so inlined and patched reads agree. Do not replace/rewrite the
        // native modifier list or material _base used by the inherited discount ledger.
        SetNativeFormMetadata(card.EnergyCost);
        form.Metadata.Apply(card, shape == BeastShape.Claw);
        form.Vars.InitializeWithOwner(card);
        if (card.IsUpgraded) UpgradeVars(form);
        Refresh(card);
        var listeners = Converted;
        if (listeners is not null)
            foreach (Func<PlayerChoiceContext, BeastChange, Task> listener in listeners.GetInvocationList())
                await listener(context, new BeastChange(card, shape, combat));
        return shape;
    }

    /// <summary>The six text-only overrides still use native temporary cost lifetime.</summary>
    public static void SetZeroThisTurnOrUntilPlayed(CardModel card)
    {
        if (Shape(card) == BeastShape.None) throw new InvalidOperationException("Expected a beast form.");
        card.EnergyCost.SetThisTurnOrUntilPlayed(0, reduceOnly: true);
        card.InvokeEnergyCostChanged();
    }

    public static async Task PlayShape(PlayerChoiceContext context, CardModel card, CardPlay play, BeastShape shape)
    {
        if (!Live(card)) return;
        if (shape == BeastShape.Claw)
        {
            if (play.Target is { IsHittable: true } target)
                await DamageCmd.Attack(card.DynamicVars["Damage"].BaseValue).FromCard(card)
                    .Targeting(target).WithHitCount(2).Execute(context);
        }
        else if (shape == BeastShape.Body)
        {
            await CreatureCmd.GainBlock(card.Owner.Creature, card.DynamicVars["Block"].BaseValue, ValueProp.Move, play);
            if (Live(card)) await LightningCmd.DealAllEnemies(context, card.DynamicVars["Lightning"].BaseValue, card);
        }
        else throw new ArgumentOutOfRangeException(nameof(shape));
    }

    private static bool Live(CardModel card) => card.Owner.Creature.IsAlive &&
        card.CombatState is not null && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding;

    internal static DynamicVarSet NewVars(BeastShape shape) => new(shape == BeastShape.Claw
        ? new DynamicVar[] { new DamageVar(7m, ValueProp.Move), new DynamicVar("Hits", 2m) }
        : new DynamicVar[] { new BlockVar(9m, ValueProp.Move), new DynamicVar("Lightning", 2m) });

    private static void UpgradeVars(Form form)
    {
        if (form.Shape == BeastShape.Claw) form.Vars["Damage"].UpgradeValueBy(4m);
        else { form.Vars["Block"].UpgradeValueBy(3m); form.Vars["Lightning"].UpgradeValueBy(1m); }
    }

    private static void Refresh(CardModel card)
    {
        card.InvokeEnergyCostChanged();
        if (NCard.FindOnTable(card) is { } node)
        {
            // UpdateVisuals alone updates text/cost, NOT the portrait/frame/type plaque.
            Required(typeof(NCard), "Reload").Invoke(node, null);
            node.UpdateVisuals(card.Pile?.Type ?? PileType.Hand, CardPreviewMode.Normal);
        }
    }

    private static void SetNativeFormMetadata(CardEnergyCost cost)
    {
        NativeCanonical.SetValue(cost, 1);
        NativeCostsX.SetValue(cost, false);
        if ((int)NativeCanonical.GetValue(cost)! != 1 || (bool)NativeCostsX.GetValue(cost)!)
            throw new InvalidOperationException("Native beast cost metadata did not update.");
    }

    public static void Reset()
    {
        foreach (var entry in forms)
        {
            NativeCanonical.SetValue(entry.Key.EnergyCost, entry.Value.OriginalCanonicalCost);
            NativeCostsX.SetValue(entry.Key.EnergyCost, entry.Value.OriginalCostsX);
            entry.Value.Metadata.Restore(entry.Key);
        }
        forms = new ConditionalWeakTable<CardModel, Form>();
    }

    public static void Install()
    {
        if (installed) return;
        var harmony = new Harmony("Volibear.BeastForms");
        try
        {
            // Include concrete overrides. Patching only CardModel.get_Type, for example,
            // silently misses native cards whose type/playability/portrait is overridden.
            var types = new[] { typeof(CardModel).Assembly, typeof(BeastForms).Assembly,
                typeof(BaseLib.Abstracts.CustomCardModel).Assembly }.Distinct()
                .SelectMany(a => a.GetTypes()).Where(t => typeof(CardModel).IsAssignableFrom(t)).ToArray();
            PatchProperties(harmony, types, new[] { "Title", "PortraitPath", "BetaPortraitPath", "PortraitPngPath", "BetaPortraitPngPath" }, nameof(StringProperty));
            PatchProperties(harmony, types, new[] { "TitleLocString", "Description" }, nameof(LocalizedProperty));
            PatchProperties(harmony, types, new[] { "Type" }, nameof(TypeProperty));
            PatchProperties(harmony, types, new[] { "Rarity" }, nameof(RarityProperty));
            PatchProperties(harmony, types, new[] { "VisualCardPool" }, nameof(VisualPoolProperty));
            PatchProperties(harmony, types, new[] { "OrbEvokeType" }, nameof(OrbProperty));
            PatchProperties(harmony, types, new[] { "TargetType" }, nameof(TargetProperty));
            PatchProperties(harmony, types, new[] { "DynamicVars" }, nameof(VarsProperty));
            PatchProperties(harmony, types, new[] { "LocalKeywords" }, nameof(LocalKeywordsProperty));
            PatchProperties(harmony, types, new[] { "CanonicalKeywords" }, nameof(CanonicalKeywordsProperty));
            PatchProperties(harmony, types, new[] { "CanonicalVars" }, nameof(CanonicalVarsProperty));
            PatchProperties(harmony, types, new[] { "IsPlayable", "HasTurnEndInHandEffect", "GainsBlock", "HasStarCostX", "HasEnergyCostX", "HasBuiltInOverlay", "IsBasicStrikeOrDefend", "ShouldGlowGoldInternal", "ShouldGlowRedInternal" }, nameof(BoolProperty));
            PatchProperties(harmony, types, new[] { "CanonicalEnergyCost", "CanonicalStarCost", "CurrentStarCost", "BaseStarCost", "MaxUpgradeLevel" }, nameof(IntProperty));
            PatchProperties(harmony, types, new[] { "Tags" }, nameof(TagsProperty));
            PatchProperties(harmony, types, new[] { "ExtraHoverTips" }, nameof(HoverProperty));
            PatchProperties(harmony, types, new[] { "Enchantment" }, nameof(EnchantmentProperty), postfix: true);
            PatchProperties(harmony, types, new[] { "Affliction" }, nameof(AfflictionProperty), postfix: true);
            // Final texture replacement also wins over the pre-existing Volibear portrait bridge.
            var portraitPatch = Handler(nameof(PortraitProperty));
            portraitPatch.priority = Priority.Last;
            portraitPatch.after = new[] { "Volibear.Portraits", "BaseLib" };
            harmony.Patch(AccessTools.PropertyGetter(typeof(CardModel), nameof(CardModel.Portrait)), postfix: portraitPatch);
            PatchMethods(harmony, types, "AddExtraArgsToDescription", nameof(SkipOriginal));
            PatchMethods(harmony, types, "OnEnqueuePlayVfx", nameof(SkipOriginalTask));
            PatchMethods(harmony, types, "OnTurnEndInHand", nameof(SkipOriginalTask));
            PatchMethods(harmony, types, "AfterDowngraded", nameof(SkipOriginal));
            PatchMethods(harmony, types, "GetResultPileTypeForCardPlay", nameof(ResultPile));

            harmony.Patch(MoveNext(Required(typeof(CardModel), nameof(CardModel.OnPlayWrapper))), transpiler: Handler(nameof(PlayCallsite)));
            harmony.Patch(Required(typeof(CardModel), nameof(CardModel.UpgradeInternal)), transpiler: Handler(nameof(UpgradeCallsite)));
            harmony.Patch(Required(typeof(CardModel), nameof(CardModel.DowngradeInternal)), postfix: Handler(nameof(AfterDowngrade)));
            harmony.Patch(Required(typeof(AbstractModel), nameof(AbstractModel.MutableClone)), postfix: Handler(nameof(AfterClone)));
            harmony.Patch(Required(typeof(CombatState), nameof(CombatState.IterateHookListeners)), postfix: Handler(nameof(FilterOriginalHooks)));

            harmony.Patch(AccessTools.PropertyGetter(typeof(CardEnergyCost), nameof(CardEnergyCost.Canonical)), prefix: Handler(nameof(CostCanonical)));
            harmony.Patch(AccessTools.PropertyGetter(typeof(CardEnergyCost), nameof(CardEnergyCost.CostsX)), prefix: Handler(nameof(CostsX)));
            harmony.Patch(Required(typeof(CardEnergyCost), nameof(CardEnergyCost.GetWithModifiers)), prefix: Handler(nameof(CostValue)));
            harmony.Patch(Required(typeof(CardEnergyCost), nameof(CardEnergyCost.SetCustomBaseCost)), prefix: Handler(nameof(SetCostBase)));
            harmony.Patch(Required(typeof(CardEnergyCost), nameof(CardEnergyCost.ResetForDowngrade)), prefix: Handler(nameof(ResetCostForDowngrade)));
            harmony.Patch(Required(typeof(CombatManager), nameof(CombatManager.Reset)), prefix: Handler(nameof(Reset)));
            CombatManager.Instance.CombatEnded += _ => Reset();
            CombatManager.Instance.CombatSetUp += _ => Reset();
            installed = true;
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }

    private static void PatchProperties(Harmony h, Type[] types, string[] names, string handler, bool postfix = false)
    {
        foreach (var name in names)
        {
            var root = AccessTools.PropertyGetter(typeof(CardModel), name)
                ?? throw new MissingMemberException(typeof(CardModel).FullName, name);
            var methods = new HashSet<MethodInfo> { root };
            foreach (var type in types)
            {
                var method = AccessTools.DeclaredPropertyGetter(type, name);
                if (method is not null && !method.IsAbstract) methods.Add(method);
            }
            foreach (var method in methods)
                h.Patch(method, prefix: postfix ? null : Handler(handler), postfix: postfix ? Handler(handler) : null);
        }
    }

    private static void PatchMethods(Harmony h, Type[] types, string name, string handler)
    {
        var methods = new HashSet<MethodInfo> { Required(typeof(CardModel), name) };
        foreach (var type in types)
            foreach (var method in type.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                if (method.Name == name && !method.IsAbstract) methods.Add(method);
        foreach (var method in methods) h.Patch(method, prefix: Handler(handler));
    }

    private static FieldInfo Field(Type type, string name) => AccessTools.Field(type, name)
        ?? throw new MissingFieldException(type.FullName, name);
    private static MethodInfo Required(Type type, string name) => AccessTools.Method(type, name)
        ?? throw new MissingMethodException(type.FullName, name);
    private static HarmonyMethod Handler(string name) => new(typeof(BeastForms), name);
    private static MethodInfo MoveNext(MethodInfo method) => Required(method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        ?? throw new InvalidOperationException($"{method} lost its async state machine."), "MoveNext");
    private static List<LocalCostModifier> Locals(CardEnergyCost cost) => (List<LocalCostModifier>)CostLocals.GetValue(cost)!;
    private static bool TryCost(CardEnergyCost cost, out CardModel card, out Form form)
    {
        card = (CardModel)CostOwner.GetValue(cost)!;
        return forms.TryGetValue(card, out form!);
    }

    private static bool CostCanonical(CardEnergyCost __instance, ref int __result)
    { if (!TryCost(__instance, out _, out _)) return true; __result = 1; return false; }
    private static bool CostsX(CardEnergyCost __instance, ref bool __result)
    { if (!TryCost(__instance, out _, out _)) return true; __result = false; return false; }
    private static bool CostValue(CardEnergyCost __instance, CostModifiers modifiers, ref int __result)
    {
        if (!TryCost(__instance, out var card, out var form)) return true;
        var cost = modifiers.HasFlag(CostModifiers.Local)
            ? form.Costs.Evaluate(Locals(__instance), (m, value) => m.Modify(value)) : form.Costs.FormBase;
        if (modifiers.HasFlag(CostModifiers.Global) && card.CombatState is { } combat)
            cost = (int)Hook.ModifyEnergyCostInCombat(combat, card, cost);
        __result = Math.Max(0, cost);
        return false;
    }
    private static bool SetCostBase(CardEnergyCost __instance, int newBaseCost)
    {
        if (!TryCost(__instance, out var card, out var form)) return true;
        card.AssertMutable();
        if (newBaseCost < 0) throw new InvalidOperationException("A beast form cannot have a negative/unplayable base cost.");
        form.Costs.FormBase = newBaseCost;
        card.InvokeEnergyCostChanged();
        return false;
    }
    private static bool ResetCostForDowngrade(CardEnergyCost __instance)
    {
        if (!TryCost(__instance, out var card, out var form)) return true;
        form.Costs.FormBase = 1;
        card.InvokeEnergyCostChanged();
        return false;
    }

    private static string TokenId(Form form) => form.Shape == BeastShape.Claw ? "VOLIBEAR_T01" : "VOLIBEAR_T02";
    private static string AssetKey(Form form) => form.Shape == BeastShape.Claw ? "t01" : "t02";
    private static bool StringProperty(CardModel __instance, MethodBase __originalMethod, ref string __result)
    {
        if (!forms.TryGetValue(__instance, out var form)) return true;
        __result = __originalMethod.Name switch
        {
            "get_Title" => (form.Shape == BeastShape.Claw ? "裂骨之爪" : "风暴之躯") + (__instance.IsUpgraded ? "+" : ""),
            "get_BetaPortraitPath" or "get_BetaPortraitPngPath" => $"{VolibearCard.BigPortraitRoot}/{AssetKey(form)}.png",
            _ => $"{VolibearCard.PortraitRoot}/{AssetKey(form)}.png"
        };
        return false;
    }
    private static bool LocalizedProperty(CardModel __instance, MethodBase __originalMethod, ref LocString __result)
    {
        if (!forms.TryGetValue(__instance, out var form)) return true;
        __result = new LocString("cards", TokenId(form) + (__originalMethod.Name == "get_Description" ? ".description" : ".title"));
        return false;
    }
    private static bool TypeProperty(CardModel __instance, ref CardType __result)
    { if (!forms.TryGetValue(__instance, out var f)) return true; __result = f.Shape == BeastShape.Claw ? CardType.Attack : CardType.Skill; return false; }
    private static bool RarityProperty(CardModel __instance, ref CardRarity __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = CardRarity.Token; return false; }
    private static bool VisualPoolProperty(CardModel __instance, ref CardPoolModel __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = ModelDb.CardPool<VolibearCardPool>(); return false; }
    private static bool OrbProperty(CardModel __instance, ref OrbEvokeType __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = OrbEvokeType.None; return false; }
    private static bool TargetProperty(CardModel __instance, ref TargetType __result)
    { if (!forms.TryGetValue(__instance, out var f)) return true; __result = f.Shape == BeastShape.Claw ? TargetType.AnyEnemy : TargetType.AllEnemies; return false; }
    private static bool VarsProperty(CardModel __instance, ref DynamicVarSet __result)
    { if (!forms.TryGetValue(__instance, out var f)) return true; __result = f.Vars; return false; }
    private static bool LocalKeywordsProperty(CardModel __instance, ref HashSet<CardKeyword> __result)
    { if (!forms.TryGetValue(__instance, out var f)) return true; __result = f.Keywords; return false; }
    private static bool CanonicalKeywordsProperty(CardModel __instance, ref IEnumerable<CardKeyword> __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = new[] { CardKeyword.Exhaust }; return false; }
    private static bool CanonicalVarsProperty(CardModel __instance, ref IEnumerable<DynamicVar> __result)
    { if (!forms.TryGetValue(__instance, out var f)) return true; __result = NewVars(f.Shape).Values; return false; }
    private static bool BoolProperty(CardModel __instance, MethodBase __originalMethod, ref bool __result)
    {
        if (!forms.TryGetValue(__instance, out var f)) return true;
        __result = __originalMethod.Name == "get_IsPlayable" || (__originalMethod.Name == "get_GainsBlock" && f.Shape == BeastShape.Body);
        return false;
    }
    private static bool IntProperty(CardModel __instance, MethodBase __originalMethod, ref int __result)
    {
        if (!forms.TryGetValue(__instance, out _)) return true;
        __result = __originalMethod.Name switch
        {
            "get_CanonicalEnergyCost" => 1,
            "get_MaxUpgradeLevel" => Math.Max(1, __instance.CurrentUpgradeLevel),
            _ => -1
        };
        return false;
    }
    private static bool TagsProperty(CardModel __instance, ref IEnumerable<CardTag> __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = Array.Empty<CardTag>(); return false; }
    private static bool HoverProperty(CardModel __instance, ref IEnumerable<IHoverTip> __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = Array.Empty<IHoverTip>(); return false; }
    private static void EnchantmentProperty(CardModel __instance, ref EnchantmentModel? __result)
    { if (forms.TryGetValue(__instance, out var f) && ReferenceEquals(__result, f.OldEnchantment)) __result = null; }
    private static void AfflictionProperty(CardModel __instance, ref AfflictionModel? __result)
    { if (forms.TryGetValue(__instance, out var f) && ReferenceEquals(__result, f.OldAffliction)) __result = null; }
    private static void PortraitProperty(CardModel __instance, ref Texture2D __result)
    {
        if (forms.TryGetValue(__instance, out var f))
            __result = ResourceLoader.Load<Texture2D>($"{VolibearCard.PortraitRoot}/{AssetKey(f)}.png")
                ?? throw new InvalidOperationException("Missing beast portrait resource.");
    }
    private static bool SkipOriginal(CardModel __instance) => !forms.TryGetValue(__instance, out _);
    private static bool SkipOriginalTask(CardModel __instance, ref Task __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = Task.CompletedTask; return false; }
    private static bool ResultPile(CardModel __instance, ref PileType __result)
    { if (!forms.TryGetValue(__instance, out _)) return true; __result = PileType.Exhaust; return false; }

    private static IEnumerable<CodeInstruction> ReplaceOne(IEnumerable<CodeInstruction> source, MethodInfo old, MethodInfo replacement)
    {
        var code = source.ToList();
        var count = 0;
        foreach (var instruction in code)
            if ((instruction.opcode == OpCodes.Call || instruction.opcode == OpCodes.Callvirt) && Equals(instruction.operand, old))
            { instruction.opcode = OpCodes.Call; instruction.operand = replacement; count++; }
        if (count != 1) throw new InvalidOperationException($"Beast adapter expected one {old} callsite; found {count}.");
        return code;
    }
    private static IEnumerable<CodeInstruction> PlayCallsite(IEnumerable<CodeInstruction> instructions) =>
        ReplaceOne(instructions, Required(typeof(CardModel), "OnPlay"), Required(typeof(BeastForms), nameof(DispatchPlay)));
    private static IEnumerable<CodeInstruction> UpgradeCallsite(IEnumerable<CodeInstruction> instructions) =>
        ReplaceOne(instructions, Required(typeof(CardModel), "OnUpgrade"), Required(typeof(BeastForms), nameof(DispatchUpgrade)));

    private static object? InvokeConcrete(CardModel card, string name, Dictionary<Type, MethodInfo> cache, params object[] args)
    {
        if (!cache.TryGetValue(card.GetType(), out var method))
            cache.Add(card.GetType(), method = Required(card.GetType(), name));
        try { return method.Invoke(card, args); }
        catch (TargetInvocationException error) when (error.InnerException is not null)
        { ExceptionDispatchInfo.Capture(error.InnerException).Throw(); throw; }
    }
    private static Task DispatchPlay(CardModel card, PlayerChoiceContext context, CardPlay play) =>
        forms.TryGetValue(card, out var form) ? PlayShape(context, card, play, form.Shape)
            : (Task)InvokeConcrete(card, "OnPlay", NativePlays, context, play)!;
    private static void DispatchUpgrade(CardModel card)
    {
        if (forms.TryGetValue(card, out var form)) UpgradeVars(form);
        else InvokeConcrete(card, "OnUpgrade", NativeUpgrades);
    }
    private static void AfterDowngrade(CardModel __instance)
    {
        if (!forms.TryGetValue(__instance, out var form)) return;
        form.Vars = NewVars(form.Shape);
        form.Vars.InitializeWithOwner(__instance);
        Refresh(__instance);
    }

    private static void FilterOriginalHooks(ref IEnumerable<AbstractModel> __result) => __result = WithoutOriginalHooks(__result);
    private static IEnumerable<AbstractModel> WithoutOriginalHooks(IEnumerable<AbstractModel> listeners)
    {
        foreach (var listener in listeners)
        {
            if (listener is CardModel card && forms.TryGetValue(card, out _)) continue;
            if (listener is EnchantmentModel enchant && enchant.HasCard && forms.TryGetValue(enchant.Card, out var a) && ReferenceEquals(enchant, a.OldEnchantment)) continue;
            if (listener is AfflictionModel affliction && affliction.HasCard && forms.TryGetValue(affliction.Card, out var b) && ReferenceEquals(affliction, b.OldAffliction)) continue;
            yield return listener;
        }
    }

    private static void AfterClone(AbstractModel __instance, AbstractModel __result)
    {
        if (__instance is not CardModel original || __result is not CardModel clone || !forms.TryGetValue(original, out var source)) return;
        var form = new Form
        {
            Shape = source.Shape, Combat = source.Combat, Vars = source.Vars.Clone(clone),
            Keywords = new HashSet<CardKeyword>(source.Keywords),
            Costs = source.Costs.CloneFor(Locals(original.EnergyCost), Locals(clone.EnergyCost)),
            OriginalCanonicalCost = source.OriginalCanonicalCost, OriginalCostsX = source.OriginalCostsX,
            Metadata = source.Metadata, // Immutable pre-conversion metadata, not the clone's already-transformed fields.
            OldEnchantment = clone.Enchantment, OldAffliction = clone.Affliction
        };
        forms.Add(clone, form);
        SetNativeFormMetadata(clone.EnergyCost);
        form.Metadata.Apply(clone, form.Shape == BeastShape.Claw);
    }
}
