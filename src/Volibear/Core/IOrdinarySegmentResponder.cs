using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>One callback per completed ordinary attack-card segment (AOE once,
/// multihit each), after Domain's first-segment attachment. Responders are captured
/// from the owner's native power order at that segment-finished boundary.
/// Results are native observations and must not be mutated.</summary>
public interface IOrdinarySegmentResponder
{
    Task AfterOrdinarySegment(PlayerChoiceContext context, CardModel card,
        IReadOnlyList<DamageResult> results);
}
