using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Models;

namespace Volibear;

/// <summary>Small source-level bridges for the two game channels. Production behavior is unchanged;
/// only signatures that moved between the stable and PBE branches are wrapped here.</summary>
internal static class NativeCompat
{
#if STS2_BETA
    /// <summary>PBE <c>AttackCommand.FromCard</c> carries the originating card play; mod attack
    /// segments pass null where the native queue only needs the card for attribution.</summary>
    public static AttackCommand BridgeFromCard(this AttackCommand command, CardModel card) =>
        command.FromCard(card, null);
#endif
}
