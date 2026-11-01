using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Card pool for the Volibear character. Cards are listed explicitly by the generator.</summary>
public sealed class VolibearCardPool : BaseLib.Abstracts.CustomCardPoolModel
{
    public const string ColorName = "volibear";

    public override string Title => "沃利贝尔";

    public override Color ShaderColor => new(0.29f, 0.55f, 0.95f);
    public override string BigEnergyIconPath => "res://VolibearArt/ui/images/big_energy.png";
    public override string TextEnergyIconPath => "res://VolibearArt/ui/images/text_energy.png";

    public override Color DeckEntryCardColor => new(0.42f, 0.66f, 0.98f);

    public override bool IsColorless => false;

    // BaseLib adds attributed CustomCardModel types once; avoid eager model resolution.
    protected override CardModel[] GenerateAllCards() => [];
}
