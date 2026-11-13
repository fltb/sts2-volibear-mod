using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    private static readonly Action<WaterfallGiant> StopAmbient = AccessTools.MethodDelegate<Action<WaterfallGiant>>(
        AccessTools.Method(typeof(WaterfallGiant), "StopAmbientSfx"));
    private static void ConfirmDeath(Creature owner)
    {
        var frame = ActiveFrame;
        if (frame is null || frame.Flow != Flow.Death || frame.Closed || frame.DeathConfirmed ||
            !ReferenceEquals(frame.Subject, owner)) return;
        frame.DeathConfirmed = true;
        if (frame.DeathLease is { } lease)
        { lease.LastConfirmed = Math.Max(lease.LastConfirmed, frame.DeathAttempt); lease.UnconfirmedHold = false; }
        if (frame.Episode is not { } episode) return;
        if (frame.TerminalDeath)
        {
            episode.TerminalDeaths++;
            episode.Decision.ObserveExternalTerminalDeath();
            Observed?.Invoke(owner, "terminal-death-confirmed");
        }
        else
        {
            episode.InitialDeaths++; episode.Decision.ConfirmDeath(false); episode.Decision.ObserveDomain(RawDomain(episode));
            PublishConfirmed(episode);
            Observed?.Invoke(owner, "initial-death-confirmed");
        }
    }
    private static bool RemovalVote(bool original, AbstractModel model, Creature target)
    {
        if (model is not SteamEruptionPower source || target.Monster is not WaterfallGiant monster || LatestFor(monster) is not { } episode ||
            !ReferenceEquals(episode.Source, source) || !ReferenceEquals(episode.Owner, target) || !IsCurrent(episode)) return original;
        episode.Decision.ObserveDomain(RawDomain(episode));
        return episode.Decision.Cancelled || original;
    }
    private static bool EndingVote(SteamEruptionPower __instance, ref bool __result)
    {
        if (__instance.Owner.Monster is not WaterfallGiant monster || LatestFor(monster) is not { } episode ||
            !ReferenceEquals(episode.Source, __instance) || !IsCurrent(episode)) return true;
        episode.Decision.ObserveDomain(RawDomain(episode)); // Raw predicate never calls ending getters.
        if (!episode.Decision.Cancelled) return true;
        __result = false; return false;
    }
    private static bool RecordRemoval(bool remove, Creature owner)
    {
        if (ActiveFrame is { Flow: Flow.Death, Episode: { } episode } frame && ReferenceEquals(frame.Subject, owner))
        {
            episode.NativeRemoval = remove; frame.NativeRemoval = remove;
            // Stop the creature-owned loop while its node still exists. Calling
            // StopAmbient only after native node removal would be a silent no-op.
            if (remove && episode.Decision.Cancelled && owner.IsDead) StopAmbient(episode.Monster);
        }
        return remove;
    }
    private static void RetireNode(Episode episode)
    {
        if (episode.NodeRemoved) return;
        episode.NodeRemoved = true;
        var node = NCombatRoom.Instance?.GetCreatureNode(episode.Owner);
        if (node is not null) { StopAmbient(episode.Monster); node.StartDeathAnim(true); NCombatRoom.Instance?.RemoveCreatureNode(node); }
    }
    private static void RepairRemoval(ref bool cached, Creature owner)
    {
        if (ActiveFrame is not { Flow: Flow.Death, Episode: { } episode } frame || !ReferenceEquals(frame.Subject, owner) ||
            !frame.DeathConfirmed || !IsCurrent(episode) || owner.IsAlive || !episode.Decision.Cancelled) return;
        if (!cached && Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(episode.Combat, owner))
        { cached = true; RetireNode(episode); Observed?.Invoke(owner, "steam-cached-removal-repaired"); }
        episode.NativeRemoval = cached; frame.NativeRemoval = cached;
    }
    private static Task RemoveSource(Episode episode)
    {
        if (episode.SourceRemovalStarted) return OwnCleanup(episode) ? Task.CompletedTask : episode.SourceRemoval ?? Task.CompletedTask;
        episode.SourceRemovalStarted = true;
        return episode.SourceRemoval = RemoveSourceBody(episode);
    }
    private static async Task RemoveSourceBody(Episode episode)
    {
        if (episode.Owner.Powers.Any(power => ReferenceEquals(power, episode.Source)))
        { await PowerCmd.Remove(episode.Source); Observed?.Invoke(episode.Owner, "steam-source-removed"); }
    }
    public static async Task AfterDomainOpened(Creature player)
    {
        foreach (var episode in Episodes.ToArray())
        {
            if (!IsCurrent(episode) || !ReferenceEquals(player.CombatState, episode.Combat) || !RawDomain(episode)) continue;
            episode.Decision.ObserveDomain(true);
            await Drain(episode);
        }
    }
    private static Task Drain(Episode episode, bool originalExplodeTail = false)
    {
        if (!IsCurrent(episode) || episode.Decision.Retired || !episode.Decision.TerminalRequested || OwnCleanup(episode)) return Task.CompletedTask;
        if (DeathBlocksDrain(episode, originalExplodeTail)) return Task.CompletedTask;
        if (!originalExplodeTail && (HasAncestor(episode) || episode.Owner.Monster?.IsPerformingMove == true)) return Task.CompletedTask;
        if (episode.DeathDepth != 0 || episode.PhaseDepth != 0 || episode.AttackDepth != 0 || episode.DamageDepth != 0 ||
            (!originalExplodeTail && episode.MoveDepth != 0)) return Task.CompletedTask;
        if (episode.CleanupStarted) return episode.Cleanup ?? Task.CompletedTask;
        if (episode.Owner.IsDead && episode.Owner.CombatState is not null &&
            !Hook.ShouldCreatureBeRemovedFromCombatAfterDeath(episode.Combat, episode.Owner)) return Task.CompletedTask;
        if (!episode.Decision.TryBeginTerminal(false, false, episode.MoveDepth != 0, originalExplodeTail)) return Task.CompletedTask;
        episode.CleanupStarted = true; // Before invoking any synchronous native callback.
        return episode.Cleanup = Cleanup(episode, originalExplodeTail);
    }
    private static async Task Cleanup(Episode episode, bool originalExplodeTail)
    {
        var previous = CleanupOwner.Value; CleanupOwner.Value = new(episode, previous);
        try
        {
            await RemoveSource(episode);
            if (!IsCurrent(episode)) return;
            if (!originalExplodeTail) StopAmbient(episode.Monster);
            if (episode.Owner.IsAlive)
            {
                await CreatureCmd.Kill(episode.Owner);
                episode.Decision.RecordTerminalKill(true, episode.Owner.IsDead);
            }
            else if (!episode.NativeDeathCleanup && ReferenceEquals(episode.Owner.CombatState, episode.Combat))
            {
                // Only an already completed zero-HP death may need retirement here.
                // No synthetic second death, reward event, or ShouldDie invocation.
                RetireNode(episode);
                if (!episode.ManagerRemoved) { CombatManager.Instance.RemoveCreature(episode.Owner); episode.ManagerRemoved = true; }
                var companions = episode.Combat.GetTeammatesOf(episode.Owner).Where(other => other.IsAlive && !ReferenceEquals(other, episode.Owner)).ToArray();
                var primary = episode.Owner.IsPrimaryEnemy;
                episode.Combat.RemoveCreature(episode.Owner);
                foreach (var power in episode.Owner.RemoveAllPowersAfterDeath()) await power.AfterRemoved(episode.Owner);
                episode.NativeDeathCleanup = true;
                if (primary && companions.Length > 0 && companions.All(other => other.IsSecondaryEnemy)) await CreatureCmd.Kill(companions);
            }
            if (!originalExplodeTail) NRunMusicController.Instance?.UpdateMusicParameter("waterfall_giant_progress", 5f);
            if (!episode.Combat.ContainsCreature(episode.Owner)) episode.Decision.MarkRetired(false);
            Observed?.Invoke(episode.Owner, "steam-terminal-cleanup-finished");
        }
        finally { CleanupOwner.Value = previous; }
    }
    private static async Task ExplodeTerminal(Creature owner, bool force, WaterfallGiant monster)
    {
        var episode = CurrentEpisode(Flow.Explode, monster);
        if (episode is null) { await CreatureCmd.Kill(owner, force); return; }
        if (!IsCurrent(episode)) return; // An older continuation never kills a newer death generation.
        episode.Decision.RequestNaturalTerminal();
        await Drain(episode, originalExplodeTail: true);
    }
    private static async Task AwaitNativeThenDrain(Task native, Creature owner)
    {
        DeathRoots.TryGetValue(native, out var root);
        await native;
        if (root?.Episode is not { } episode || !ReferenceEquals(root.Subject, owner) || !IsCurrent(episode)) return;
        if (root.TerminalDeath && root.DeathConfirmed && owner.IsDead && !episode.Combat.ContainsCreature(owner)) episode.Decision.MarkRetired(false);
        await Drain(episode);
    }
    private static IEnumerable<CodeInstruction> DeathMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var machine = __originalMethod.DeclaringType!; var owner = Subject(machine, Flow.Death);
        var cached = Field(machine, field => field.FieldType == typeof(bool) && field.Name.Contains("shouldRemoveFromCombat", StringComparison.Ordinal));
        var died = AccessTools.Method(typeof(Creature), nameof(Creature.InvokeDiedEvent));
        var vote = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath));
        var teammates = AccessTools.Method(typeof(ICombatState), nameof(ICombatState.GetTeammatesOf));
        var result = new List<CodeInstruction>(); var deaths = 0; var votes = 0; var repairs = 0;
        foreach (var instruction in input)
        {
            if (instruction.Calls(teammates))
            {
                var before = new CodeInstruction(OpCodes.Ldarg_0); Metadata(instruction, before); result.Add(before);
                result.Add(new(OpCodes.Ldflda, cached)); result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, owner));
                result.Add(new(OpCodes.Call, Own(nameof(RepairRemoval)))); repairs++;
            }
            result.Add(instruction);
            if (instruction.Calls(died) || instruction.Calls(vote))
            {
                result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, owner));
                result.Add(new(OpCodes.Call, Own(instruction.Calls(died) ? nameof(ConfirmDeath) : nameof(RecordRemoval))));
                if (instruction.Calls(died)) deaths++; else votes++;
            }
        }
        if (deaths != 1 || votes != 1 || repairs != 1) throw new InvalidOperationException($"Steam death anchors drifted {deaths}/{votes}/{repairs}");
        return Scope(result, generator, __originalMethod, Flow.Death);
    }
    private static IEnumerable<CodeInstruction> PublicKill(IEnumerable<CodeInstruction> input, ILGenerator generator)
    {
        var native = AccessTools.Method(typeof(CreatureCmd), "KillWithoutCheckingWinCondition");
        var owner = generator.DeclareLocal(typeof(Creature)); var force = generator.DeclareLocal(typeof(bool)); var recursion = generator.DeclareLocal(typeof(int));
        var result = new List<CodeInstruction>(); var count = 0;
        foreach (var instruction in input)
        {
            if (!instruction.Calls(native)) { result.Add(instruction); continue; }
            var save = new CodeInstruction(OpCodes.Stloc, recursion); Metadata(instruction, save); result.Add(save);
            result.Add(new(OpCodes.Stloc, force));
#if STS2_BETA
            var card = generator.DeclareLocal(typeof(CardModel));
            result.Add(new(OpCodes.Stloc, card));
#endif
            result.Add(new(OpCodes.Stloc, owner));
            result.Add(new(OpCodes.Ldloc, owner));
#if STS2_BETA
            result.Add(new(OpCodes.Ldloc, card));
#endif
            result.Add(new(OpCodes.Ldloc, force)); result.Add(new(OpCodes.Ldloc, recursion));
            result.Add(instruction); // Preserve the native call for other adapters.
            result.Add(new(OpCodes.Ldloc, owner)); result.Add(new(OpCodes.Call, Own(nameof(AwaitNativeThenDrain)))); count++;
        }
        if (count != 1) throw new InvalidOperationException("Public native kill root drifted: " + count);
        return result;
    }
    private static IEnumerable<CodeInstruction> RemovalContributions(IEnumerable<CodeInstruction> input, ILGenerator generator)
    {
        var native = AccessTools.Method(typeof(AbstractModel), nameof(AbstractModel.ShouldCreatureBeRemovedFromCombatAfterDeath));
        var model = generator.DeclareLocal(typeof(AbstractModel)); var target = generator.DeclareLocal(typeof(Creature));
        var result = new List<CodeInstruction>(); var count = 0;
        foreach (var instruction in input)
        {
            var knownRevival = instruction.operand is MethodInfo method && method.DeclaringType?.FullName == "Volibear.Core.DomainRevivalEffects" &&
                method.Name == "RemovalVote" && method.ReturnType == typeof(bool) &&
                method.GetParameters().Select(parameter => parameter.ParameterType).SequenceEqual(new[] { typeof(AbstractModel), typeof(Creature) });
            if (!instruction.Calls(native) && !knownRevival) { result.Add(instruction); continue; }
            var save = new CodeInstruction(OpCodes.Stloc, target); Metadata(instruction, save); result.Add(save);
            result.Add(new(OpCodes.Stloc, model)); result.Add(new(OpCodes.Ldloc, model)); result.Add(new(OpCodes.Ldloc, target));
            result.Add(instruction); // Critically retain Revival.RemovalVote, not its raw/native substitute.
            result.Add(new(OpCodes.Ldloc, model)); result.Add(new(OpCodes.Ldloc, target)); result.Add(new(OpCodes.Call, Own(nameof(RemovalVote)))); count++;
        }
        if (count != 1) throw new InvalidOperationException("Steam removal contribution drifted: " + count);
        return result;
    }
    private static IEnumerable<CodeInstruction> MoveTail(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var code = input.ToList();
        var native = AccessTools.Method(typeof(Cmd), nameof(Cmd.CustomScaledWait));
        var indexes = code.Select((instruction, index) => (instruction, index)).Where(pair => pair.instruction.Calls(native) ||
            pair.instruction.operand is MethodInfo method && method.DeclaringType?.FullName == "Volibear.Core.DomainRevivalEffects" && method.Name == "FinishMoveWait").ToArray();
        if (indexes.Length != 2) throw new InvalidOperationException("Steam move tail drifted.");
        var last = indexes[1].index;
        // Preserve the existing wait/wrapper Task, then drain via a separate continuation.
        var monster = Field(__originalMethod.DeclaringType!, field => field.FieldType == typeof(MonsterModel));
        var result = code.Take(last + 1).ToList();
        result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld, monster)); result.Add(new(OpCodes.Call, Own(nameof(AfterMoveTask))));
        result.AddRange(code.Skip(last + 1)); return Scope(result, generator, __originalMethod, Flow.NativeMove);
    }
    private static async Task AfterMoveTask(Task native, MonsterModel monster)
    {
        var commandEpoch = ActiveFrame?.Epoch ?? _epoch;
        await native;
        if (commandEpoch != _epoch || monster is not WaterfallGiant giant || LatestFor(giant) is not { } episode) return;
        if (IsCurrent(episode) && OwnerScopesClosed(episode)
            && episode.Decision.FinishNativeMoveAfterVeto(episode.Owner.IsAlive,
            episode.MoveDepth == 0 && episode.AttackDepth == 0 && episode.DamageDepth == 0 && episode.DeathDepth == 0 && episode.PhaseDepth == 0))
        {
            episode.CleanupStarted = false; episode.Cleanup = null;
            Observed?.Invoke(episode.Owner, "uncancelled-native-veto-move-finished");
        }
        if (episode.TerminalDeaths > 0 && episode.Owner.IsDead && !episode.Combat.ContainsCreature(episode.Owner)) episode.Decision.MarkRetired(false);
        await Drain(episode);
    }
}
