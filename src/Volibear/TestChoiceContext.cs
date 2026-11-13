using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

namespace Volibear;

/// <summary>Probe-only choice context: native power application on PBE signals the chooser, and
/// BaseLib's ThrowingPlayerChoiceContext does not implement that member, so probes that apply
/// powers without a real choice use this silent context instead.</summary>
internal sealed class SilentPlayerChoiceContext : PlayerChoiceContext
{
#if STS2_BETA
    public override GameActionType? GameActionType => null;
    public override ulong? OwnerId => null;
    public override Task SignalPlayerChoiceBegun(Player chooser, PlayerChoiceOptions options) => Task.CompletedTask;
#else
    public override Task SignalPlayerChoiceBegun(PlayerChoiceOptions options) => Task.CompletedTask;
#endif
    public override Task SignalPlayerChoiceEnded() => Task.CompletedTask;
}
