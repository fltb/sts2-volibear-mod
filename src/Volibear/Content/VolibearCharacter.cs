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
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_CHARACTER")]
public sealed class VolibearCharacter : BaseLib.Abstracts.CustomCharacterModel
{
    public VolibearCharacter()
    {
        Colors = new Color(0.29f, 0.55f, 0.95f);
        // All scene paths are now initialized. Bootstrap and restored-run routes can
        // instantiate the character without passing through ModelDb.Preload first.
        RegisterSceneConversions();
    }

    public Color Colors { get; }

    public override int StartingHp => 80;

    public override int StartingGold => 99;

    public override CharacterGender Gender => CharacterGender.Masculine;

    public override Color NameColor => new(0.42f, 0.66f, 0.98f);

    public override string CustomVisualPath => Presentation.VolibearPresentation.CombatScenePath;
    public override MegaCrit.Sts2.Core.Nodes.Combat.NCreatureVisuals CreateCustomVisuals() =>
        Presentation.VolibearPresentation.CreateCombatVisuals();
    public override string CustomCharacterSelectBg => Presentation.VolibearPresentation.SelectionScenePath;
    public override float DeathAnimTime => Presentation.VolibearPresentation.DeathAnimationSeconds;
    public override string CustomIconTexturePath => "res://VolibearArt/ui/images/character_icon_volibear.png";
    public override string CustomIconOutlineTexturePath => "res://VolibearArt/ui/images/character_icon_volibear_outline.png";
    public override string CustomCharacterSelectIconPath => "res://VolibearArt/ui/images/char_select_volibear.png";
    public override string CustomCharacterSelectLockedIconPath => "res://VolibearArt/ui/images/char_select_volibear_locked.png";
    public override string CustomMapMarkerPath => "res://VolibearArt/ui/images/map_marker_volibear.png";

    // Native treasure sharing / rock-paper-scissors uses these four distinct
    // textures. Leaving the BaseLib overrides null would invent missing paths.
    public override string CustomArmPointingTexturePath => "res://VolibearArt/ui/images/multiplayer_hand_volibear_pointing.png";
    public override string CustomArmRockTexturePath => "res://VolibearArt/ui/images/multiplayer_hand_volibear_rock.png";
    public override string CustomArmPaperTexturePath => "res://VolibearArt/ui/images/multiplayer_hand_volibear_paper.png";
    public override string CustomArmScissorsTexturePath => "res://VolibearArt/ui/images/multiplayer_hand_volibear_scissors.png";

    public override string CustomIconPath => Presentation.VolibearPresentation.IconScenePath;
    public override string CustomEnergyCounterPath => Presentation.VolibearPresentation.EnergyScenePath;
    public override string CustomRestSiteAnimPath => Presentation.VolibearPresentation.RestScenePath;
    public override string CustomMerchantAnimPath => Presentation.VolibearPresentation.MerchantScenePath;
    public override string CustomTrailPath => Presentation.VolibearPresentation.TrailScenePath;
    public override string CustomCharacterSelectTransitionPath => Presentation.VolibearPresentation.TransitionMaterialPath;

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
