using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Card pool for the Volibear character. Cards are listed explicitly by the generator.</summary>
public sealed class VolibearCardPool : CardPoolModel
{
    public const string ColorName = "volibear";

    public override string Title => "Volibear";

    public override string EnergyColorName => ColorName;

    public override string CardFrameMaterialPath => "res://images/card_frames/ironclad_frame.tres";

    public override Color DeckEntryCardColor => new(0.42f, 0.66f, 0.98f);

    public override bool IsColorless => false;

    protected override CardModel[] GenerateAllCards() =>
    [
        ModelDb.Card<Volibear_B01>(),
        ModelDb.Card<Volibear_B02>(),
        ModelDb.Card<Volibear_B03>(),
        ModelDb.Card<Volibear_B04>(),
    ];
}
