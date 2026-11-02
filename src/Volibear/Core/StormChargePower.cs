using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>
/// Persistent per-creature thunder force. Native PowerModel owns Amount, stacking,
/// combat lifetime and serialization. No turn tick and no consumption on lightning.
/// It does not modify ordinary attacks or arbitrary Unpowered damage.
/// </summary>
public sealed class StormChargePower : CustomPowerModel
{
    public override string CustomPackedIconPath => Presentation.VolibearIcons.ThunderForce;
    public override string CustomBigIconPath => Presentation.VolibearIcons.ThunderForceBig;
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override List<(string, string)> Localization => new PowerLoc(
        "雷势", "每层使每段雷伤增加1。",
        "每层使每段雷伤增加1。");

    public static int Current(Creature owner) => Math.Max(0, owner.GetPowerAmount<StormChargePower>());

    public static Task<StormChargePower?> Gain(PlayerChoiceContext context, Creature owner,
                                               int amount, CardModel? card = null)
    {
        if (amount < 0) throw new ArgumentOutOfRangeException(nameof(amount));
        if (!LightningBatches.CanUse(owner, out _)) return Task.FromResult<StormChargePower?>(null);
        if (amount == 0) return Task.FromResult(owner.GetPower<StormChargePower>());
        return PowerCmd.Apply<StormChargePower>(context, owner, amount, owner, card);
    }
}
