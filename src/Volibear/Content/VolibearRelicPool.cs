using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Volibear's starter heart and its native Orobas starter upgrade.</summary>
public sealed class VolibearRelicPool : BaseLib.Abstracts.CustomRelicPoolModel
{
    public override string BigEnergyIconPath => "res://VolibearArt/ui/images/big_energy.png";
    public override string TextEnergyIconPath => "res://VolibearArt/ui/images/text_energy.png";

    public override Color LabOutlineColor => new(0.42f, 0.66f, 0.98f);

    // BaseLib Pool attributes populate the pool once; no duplicate direct entries.
    protected override IEnumerable<RelicModel> GenerateAllRelics() => [];
}

/// <summary>不灭狂雷 · the first completed engage each player turn draws one card.</summary>
[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_HUNTERS_HEART")]
[BaseLib.Utils.Pool(typeof(VolibearRelicPool))]
public sealed class HuntersHeart : BaseLib.Abstracts.CustomRelicModel, Core.IEngageResponder
{
    private MegaCrit.Sts2.Core.Combat.ICombatState? lastCombat;
    private int lastTurn = -1;
    public override RelicRarity Rarity => RelicRarity.Starter;
    public override string PackedIconPath => Presentation.VolibearIcons.LightningHeart;
    protected override string PackedIconOutlinePath => Presentation.VolibearIcons.LightningHeartOutline;
    protected override string BigIconPath => Presentation.VolibearIcons.LightningHeartBig;
    // BaseLib StarterUpgradePatches feeds the native TouchOfOrobas offer/replace chain.
    public override RelicModel? GetUpgradeReplacement() => ModelDb.Relic<ImmortalHeart>();
    protected override IEnumerable<IHoverTip> ExtraHoverTips => base.ExtraHoverTips.Concat(MechanicHoverTips.ForText("迎战"));

    public async System.Threading.Tasks.Task AfterEngageCompleted(Core.EngageCmd.Completion completion)
    {
        if (Owner != completion.Receiver.Player || IsMelted || !Owner.Relics.Contains(this)) return;
        var turn = Owner.PlayerCombatState?.TurnNumber ?? throw new System.InvalidOperationException("Missing combat player");
        bool firstThisTurn = !(ReferenceEquals(lastCombat, completion.Combat) && lastTurn == turn);
        if (firstThisTurn)
        {
            lastCombat = completion.Combat;
            lastTurn = turn;
        }
        // Every engage draws; only the first engage of each player turn pays energy.
        await MegaCrit.Sts2.Core.Commands.CardPileCmd.Draw(completion.Choices, 1m, Owner, false);
        if (firstThisTurn) await MegaCrit.Sts2.Core.Commands.PlayerCmd.GainEnergy(1m, Owner);
    }
}
