using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using Volibear.Core;

// Metadata-only native objects with the fields native MutableClone requires. No
// engine/combat/TestMode. Production metadata helper is LINKED, not reimplemented.
if (System.Environment.GetEnvironmentVariable("DOTNET_TieredCompilation") != "0")
    throw new Exception("Run with DOTNET_TieredCompilation=0 so warmed sealed consumers are optimized.");
var assertions = 0;
void Check(bool value, string label) { assertions++; if (!value) throw new Exception(label); }
var power = Fixture<Inflame>(CardType.Power, TargetType.Self);
var x = Fixture<Whirlwind>(CardType.Attack, TargetType.AllEnemies);
var materialMaster = Fixture<Inflame>(CardType.Power, TargetType.Self);
AccessTools.Field(typeof(CardModel), "_deckVersion").SetValue(power, materialMaster);
var powerIdentity = power;
var keywordIdentity = AccessTools.Field(typeof(CardModel), "_keywords").GetValue(power);
var powerMetadata = BeastCardMetadata.Capture(power);
var xMetadata = BeastCardMetadata.Capture(x);
Check(PowerType(power) == CardType.Power && PowerTarget(power) == TargetType.Self, "warm sealed power consumers");
Check(XType(x) == CardType.Attack && XTarget(x) == TargetType.AllEnemies, "warm sealed X consumers");
var h = new Harmony("Volibear.ShapeMetadataRegression");
try
{
    h.Patch(AccessTools.PropertyGetter(typeof(CardModel), "Type"), prefix: new HarmonyMethod(typeof(GetterOverlay), nameof(GetterOverlay.Type)));
    h.Patch(AccessTools.PropertyGetter(typeof(CardModel), "TargetType"), prefix: new HarmonyMethod(typeof(GetterOverlay), nameof(GetterOverlay.Target)));
    Check(PowerType(power) == CardType.Power && PowerTarget(power) == TargetType.Self && XTarget(x) == TargetType.AllEnemies,
        "positive regression control: optimized warmed sealed consumers bypass getter-only overlay");
    powerMetadata.Apply(power, claw: false);
    xMetadata.Apply(x, claw: true);
    Check(PowerType(power) == CardType.Skill && PowerTarget(power) == TargetType.AllEnemies, "same-object power conversion reaches optimized consumers");
    Check(XType(x) == CardType.Attack && XTarget(x) == TargetType.AnyEnemy, "same-object X conversion reaches optimized consumers");
    Check(ReferenceEquals(power, powerIdentity) && ReferenceEquals(power.DeckVersion, materialMaster), "material and master reference unchanged");
    Check(ReferenceEquals(AccessTools.Field(typeof(CardModel), "_keywords").GetValue(power), keywordIdentity), "keyword identity untouched");
    Check(PowerType(materialMaster) == CardType.Power && PowerTarget(materialMaster) == TargetType.Self, "master metadata untouched");

    // Actual native AbstractModel.MutableClone -> CardModel.DeepCloneFields/AfterCloned,
    // not a handcrafted MemberwiseClone stand-in. The sidecar retains immutable ORIGINAL
    // metadata, exactly as BeastForms.AfterClone does; never recapture converted fields.
    var powerClone = (Inflame)power.MutableClone();
    var xClone = (Whirlwind)x.MutableClone();
    powerMetadata.Apply(powerClone, claw: false);
    xMetadata.Apply(xClone, claw: true);
    Check(!ReferenceEquals(powerClone, power) && powerClone.IsMutable && powerClone.DeckVersion is null, "native cloning keeps native preview/deck semantics");
    Check(PowerType(powerClone) == CardType.Skill && PowerTarget(powerClone) == TargetType.AllEnemies, "native power clone consumer sees body");
    Check(XTarget(xClone) == TargetType.AnyEnemy, "native X clone consumer sees claw");
    powerMetadata.Restore(power);
    xMetadata.Restore(x);
    Check(PowerType(power) == CardType.Power && PowerTarget(power) == TargetType.Self, "reset material restores original power metadata through warmed consumers");
    Check(XType(x) == CardType.Attack && XTarget(x) == TargetType.AllEnemies, "reset material restores original X target");
    Check(PowerType(powerClone) == CardType.Skill && XTarget(xClone) == TargetType.AnyEnemy, "restoring source does not prematurely alter clone");
    powerMetadata.Restore(powerClone);
    xMetadata.Restore(xClone);
    Check(PowerType(powerClone) == CardType.Power && PowerTarget(powerClone) == TargetType.Self, "clone reset uses original material metadata");
    Check(XTarget(xClone) == TargetType.AllEnemies, "X clone reset restores original target");
}
finally { h.UnpatchAll(h.Id); }
Console.WriteLine($"BEAST_OPTIMIZED_SHAPE_METADATA_OK assertions={assertions}; nativeClone=EXECUTED; gameplay=NOT_RUN");

static T Fixture<T>(CardType type, TargetType target) where T : CardModel
{
    var card = (T)RuntimeHelpers.GetUninitializedObject(typeof(T));
    void Set(string name, object value) => AccessTools.Field(typeof(CardModel), name).SetValue(card, value);
    Set("<Type>k__BackingField", type); Set("<TargetType>k__BackingField", target);
    Set("_keywords", new HashSet<CardKeyword>());
    Set("_dynamicVars", new DynamicVarSet([]));
    Set("_temporaryStarCosts", new List<TemporaryCardCost>());
    Set("_canonicalInstance", card); // Avoid ModelDb registration; native clone retains this canonical reference.
    return card;
}
[MethodImpl(MethodImplOptions.NoInlining)] static CardType PowerType(Inflame card) => card.Type;
[MethodImpl(MethodImplOptions.NoInlining)] static TargetType PowerTarget(Inflame card) => card.TargetType;
[MethodImpl(MethodImplOptions.NoInlining)] static CardType XType(Whirlwind card) => card.Type;
[MethodImpl(MethodImplOptions.NoInlining)] static TargetType XTarget(Whirlwind card) => card.TargetType;
public static class GetterOverlay
{
    public static bool Type(CardModel __instance, ref CardType __result)
    { __result = __instance is Whirlwind ? CardType.Attack : CardType.Skill; return false; }
    public static bool Target(CardModel __instance, ref TargetType __result)
    { __result = __instance is Whirlwind ? TargetType.AnyEnemy : TargetType.AllEnemies; return false; }
}
