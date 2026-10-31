using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;

namespace Volibear.Content;

/// <summary>
/// Common behaviour for every Volibear card: one localization table, one portrait directory and
/// dynamic vars declared once so upgrade previews and in-combat text stay in sync with the code.
/// </summary>
public abstract class VolibearCard : CardModel
{
    public const string LocTable = "cards";
    public const string PortraitRoot = "VolibearArt/cards";
    public const string BigPortraitRoot = "VolibearArt/cards/big";

    protected VolibearCard(int cost, CardType type, CardRarity rarity, TargetType target,
                           string key, bool showInCardLibrary = true)
        : base(cost, type, rarity, target, showInCardLibrary)
    {
        Key = key;
    }

    /// <summary>Stable lowercase asset key ("b01", "c12", "r17").</summary>
    public string Key { get; }

    public bool IsUpgradedCard => this.IsUpgraded;

    public override string PortraitPath => $"{PortraitRoot}/{Key}.png";

    public override string BetaPortraitPath => $"{BigPortraitRoot}/{Key}.png";

    protected override IEnumerable<DynamicVar> CanonicalVars => Array.Empty<DynamicVar>();

    protected T Var<T>(string name) where T : DynamicVar => (T)DynamicVars[name];

    protected decimal Value(string name) => DynamicVars[name].BaseValue;

    /// <summary>Upgrade-time helper: raise a dynamic var and keep the printed text consistent.</summary>
    protected void UpgradeVar(string name, decimal delta)
    {
        DynamicVars[name].UpgradeValueBy(delta);
    }

    protected static ValueProp Unpowered => ValueProp.Unpowered;

    protected static ValueProp Move => ValueProp.Move;

    protected static bool IsMultiTarget(TargetType target) =>
        target is TargetType.AllEnemies or TargetType.AllAllies or TargetType.RandomEnemy;

    internal static IEnumerable<Type> AllCardTypes =>
        typeof(VolibearCard).Assembly.GetTypes()
            .Where(t => typeof(VolibearCard).IsAssignableFrom(t) && !t.IsAbstract);
}
