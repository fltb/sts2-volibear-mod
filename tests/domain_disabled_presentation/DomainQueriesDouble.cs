using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
namespace Volibear.Core;
// Gameplay predicates are doubles; native models, localization, Harmony and all
// presentation source are real. This suite does not claim gameplay/render execution.
public static class DomainSelfDebuffEffects
{
    public static readonly HashSet<PowerModel> Muted = [];
    public static bool IsSuppressed(PowerModel power) => Muted.Contains(power);
}
public static class DomainSandpitEffects
{
    public static readonly HashSet<PowerModel> Muted = [];
    public static bool IsSuppressed(PowerModel power) => Muted.Contains(power);
}
public static class DomainEnemyEffects
{
    public static readonly HashSet<Creature> Active = [];
    public static bool ActiveFor(Creature? creature) => creature is not null && Active.Contains(creature);
}
