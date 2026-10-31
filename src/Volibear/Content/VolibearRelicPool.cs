using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Relic pool for Volibear; only the starter heart is defined so far.</summary>
public sealed class VolibearRelicPool : RelicPoolModel
{
    public override string EnergyColorName => VolibearCardPool.ColorName;

    public override Color LabOutlineColor => new(0.42f, 0.66f, 0.98f);

    protected override IEnumerable<RelicModel> GenerateAllRelics() =>
        [ModelDb.Relic<HuntersHeart>()];
}

/// <summary>不灭狂雷 · starter relic. Draws a card on the first engage of each combat.</summary>
public sealed class HuntersHeart : RelicModel
{
    public override RelicRarity Rarity => RelicRarity.Starter;
}
