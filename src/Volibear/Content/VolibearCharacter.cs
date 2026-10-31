using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Characters;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.PotionPools;

namespace Volibear.Content;

/// <summary>
/// Volibear character definition. Starting deck and relic follow the pinned design:
/// 4x B01, 4x B02, 1x B03, 1x B04, 80 HP, starting relic 不灭狂雷.
/// </summary>
public sealed class VolibearCharacter : CharacterModel
{
    public VolibearCharacter()
    {
        Colors = new Color(0.29f, 0.55f, 0.95f);
    }

    public Color Colors { get; }

    public override int StartingHp => 80;

    public override int StartingGold => 99;

    public override CharacterGender Gender => CharacterGender.Masculine;

    public override Color NameColor => new(0.42f, 0.66f, 0.98f);

    public override float AttackAnimDelay => 0.15f;

    public override float CastAnimDelay => 0.25f;

    public override CardPoolModel CardPool => ModelDb.CardPool<VolibearCardPool>();

    public override RelicPoolModel RelicPool => ModelDb.RelicPool<VolibearRelicPool>();

    public override PotionPoolModel PotionPool => ModelDb.PotionPool<IroncladPotionPool>();

    protected override CharacterModel UnlocksAfterRunAs => null!;

    public override IEnumerable<CardModel> StartingDeck =>
    [
        ModelDb.Card<Volibear_B01>(),
        ModelDb.Card<Volibear_B01>(),
        ModelDb.Card<Volibear_B01>(),
        ModelDb.Card<Volibear_B01>(),
        ModelDb.Card<Volibear_B02>(),
        ModelDb.Card<Volibear_B02>(),
        ModelDb.Card<Volibear_B02>(),
        ModelDb.Card<Volibear_B02>(),
        ModelDb.Card<Volibear_B03>(),
        ModelDb.Card<Volibear_B04>(),
    ];

    public override IReadOnlyList<RelicModel> StartingRelics =>
        [ModelDb.Relic<HuntersHeart>()];

    public override List<string> GetArchitectAttackVfx() => ["vfx/vfx_attack_slash"];
}
