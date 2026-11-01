using System.Linq;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models.Monsters;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    internal static object? Observation(WaterfallGiant monster, Creature player)
    {
        var episode = LatestFor(monster);
        if (episode is null) return null;
        string Role(object receiver) => ReferenceEquals(receiver, player) ? "player" : ReferenceEquals(receiver, episode.Owner) ? "boss" :
            receiver is Creature creature && creature.Monster is Osty && ReferenceEquals(creature.PetOwner?.Creature, player) ? "osty" : "foreign";
        return new
        {
            generation = episode.Decision.Generation, epoch = episode.Decision.Epoch, currentEpoch = _epoch,
            ownerDeathActive = (episode.OwnerRegistry ?? OwnerDeaths).TryGetValue(episode.Owner, out var lease) ? lease.Active : 0,
            ownerDeathAttempts = lease?.Serial ?? 0, unconfirmedDeathHold = lease?.UnconfirmedHold ?? false,
            ownerHpCommandsActive = lease?.HpCommandsActive ?? 0,
            terminalAttemptCount = episode.Decision.TerminalAttemptCount, terminalDeathConfirmed = episode.Decision.TerminalDeathConfirmed,
            sourceType = episode.Source.GetType().Name, monsterType = episode.Monster.GetType().Name,
            initialDeaths = episode.InitialDeaths, terminalDeaths = episode.TerminalDeaths,
            confirmed = episode.Decision.DeathConfirmed, cancelled = episode.Decision.Cancelled,
            terminalRequested = episode.Decision.TerminalRequested, terminalStarted = episode.Decision.TerminalStarted,
            terminalKillCommitted = episode.Decision.TerminalKillCommitted, retired = episode.Decision.Retired,
            deathDepth = episode.DeathDepth, phaseDepth = episode.PhaseDepth, moveDepth = episode.MoveDepth,
            attackDepth = episode.AttackDepth, damageDepth = episode.DamageDepth,
            writes = episode.Decision.Writes.Select(write => new { part = write.Part, receiver = Role(write.Receiver), before = write.Before, after = write.After, delta = write.Delta }).ToArray(),
            attackCommands = episode.Commands.Count,
            damageResults = episode.Commands.SelectMany(command => command.Results).SelectMany(results => results).Select(result => new
            {
                receiver = Role(result.Receiver), blocked = result.BlockedDamage, hp = result.UnblockedDamage,
                overkill = result.OverkillDamage, killed = result.WasTargetKilled,
                blockBroken = result.WasBlockBroken, fullyBlocked = result.WasFullyBlocked,
            }).ToArray(),
        };
    }
}
