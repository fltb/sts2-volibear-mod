// Projection policy is tested separately; this fixture validates the native UI ABI.
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.HoverTips;
namespace Volibear.Presentation;
internal sealed record PowerStackProjection(IReadOnlyList<PowerModel> Members, string AmountText, string Description);
internal static class PowerStackPresentation
{
    internal static bool TryDescribe(PowerModel power, out PowerStackProjection projection)
    { projection = null!; return false; }
}
internal static class PowerPresentationDisabled
{
    internal static IEnumerable<IHoverTip> PowerTips(PowerModel model, IEnumerable<IHoverTip> tips) => tips;
}
