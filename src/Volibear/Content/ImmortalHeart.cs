using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.HoverTips;
using Volibear.Core;

namespace Volibear.Content;

/// <summary>
/// The native BlackBlood-equivalent starter upgrade. Orobas offers TouchOfOrobas;
/// BaseLib's GetUpgradeReplacement extension resolves this model, and native
/// RelicCmd.Replace removes HuntersHeart before obtaining this at its inventory slot.
/// Starter rarity deliberately keeps it out of ordinary chest/shop reward pools.
/// </summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_IMMORTAL_HEART")]
[BaseLib.Utils.Pool(typeof(VolibearRelicPool))]
public sealed class ImmortalHeart : CustomRelicModel, IEngageResponder
{
    public override RelicRarity Rarity => RelicRarity.Starter;
    public override string PackedIconPath => Presentation.VolibearIcons.StormCrown;
    protected override string PackedIconOutlinePath => Presentation.VolibearIcons.StormCrownOutline;
    protected override string BigIconPath => Presentation.VolibearIcons.StormCrownBig;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => base.ExtraHoverTips.Concat(MechanicHoverTips.ForText("迎战"));
    public override List<(string, string)> Localization => new RelicLoc(
        "万古不灭", "每次完成迎战后，获得1能量并抽1张牌。", "表面布满焦痕，拿在手中仍然发烫。");

    public override async Task AfterObtained()
    {
        // Normal TouchOfOrobas acquisition already removed the starter. Keep the
        // frozen replaces:HuntersHeart invariant even for direct native obtain paths.
        foreach (var starter in Owner.Relics.OfType<HuntersHeart>().ToArray())
            await RelicCmd.Remove(starter);
    }

    public async Task AfterEngageCompleted(EngageCmd.Completion completion)
    {
        if (Owner != completion.Receiver.Player || IsMelted || !Owner.Relics.Contains(this)) return;
        await PlayerCmd.GainEnergy(1m, Owner);
        await CardPileCmd.Draw(completion.Choices, 1m, Owner, false);
    }

}
