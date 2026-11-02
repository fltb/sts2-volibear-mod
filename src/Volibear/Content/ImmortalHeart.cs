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
    private ICombatState? lastCombat;
    private int lastTurn = -1;
    public override RelicRarity Rarity => RelicRarity.Starter;
    public override string PackedIconPath => Presentation.VolibearIcons.StormCrown;
    protected override string PackedIconOutlinePath => Presentation.VolibearIcons.StormCrownOutline;
    protected override string BigIconPath => Presentation.VolibearIcons.StormCrownBig;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => base.ExtraHoverTips.Concat(MechanicHoverTips.ForText("迎战"));
    public override List<(string, string)> Localization => new RelicLoc(
        "万古不灭", "每回合首次完成迎战后，抽2张牌。", "表面布满焦痕，拿在手中仍然发烫。");

    public override async Task AfterObtained()
    {
        // Normal TouchOfOrobas acquisition already removed the starter. Keep the
        // frozen replaces:HuntersHeart invariant even for direct native obtain paths.
        foreach (var starter in Owner.Relics.OfType<HuntersHeart>().ToArray())
            await RelicCmd.Remove(starter);
    }

    public async Task AfterEngageCompleted(EngageCmd.Completion completion)
    {
        // Engage captures a responder array; a preceding response may remove/melt us.
        if (Owner != completion.Receiver.Player || IsMelted || !Owner.Relics.Contains(this)) return;
        var turn = Owner.PlayerCombatState?.TurnNumber ?? throw new InvalidOperationException("Missing combat player");
        if (ReferenceEquals(lastCombat, completion.Combat) && lastTurn == turn) return;
        // Commit before draw responses can recursively complete another engage.
        lastCombat = completion.Combat;
        lastTurn = turn;
        await CardPileCmd.Draw(completion.Choices, 2m, Owner, false);
    }

    public override Task AfterRemoved()
    {
        lastCombat = null;
        lastTurn = -1;
        return Task.CompletedTask;
    }
}
