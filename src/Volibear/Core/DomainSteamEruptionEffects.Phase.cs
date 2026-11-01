using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;

namespace Volibear.Core;

public static partial class DomainSteamEruptionEffects
{
    private static readonly Action<WaterfallGiant, int> SetSteamDamage = AccessTools.MethodDelegate<Action<WaterfallGiant, int>>(
        AccessTools.PropertySetter(typeof(WaterfallGiant), "SteamEruptionDamage"));
    private static readonly Action<WaterfallGiant, int> SetBuildup = AccessTools.MethodDelegate<Action<WaterfallGiant, int>>(
        AccessTools.PropertySetter(typeof(WaterfallGiant), "PressureBuildupIdx"));
    private static readonly Action<WaterfallGiant> IncrementBuildup = AccessTools.MethodDelegate<Action<WaterfallGiant>>(
        AccessTools.Method(typeof(WaterfallGiant), "IncrementBuildUpAnimationTrack"));
    private static async Task PauseAt(Episode episode, string point)
    {
        Observed?.Invoke(episode.Owner, point);
        if (Boundary is not null)
            foreach (Func<Creature, string, Task> observer in Boundary.GetInvocationList()) await observer(episode.Owner, point);
    }
    private static async Task TriggerPhase(WaterfallGiant monster, SteamEruptionPower source)
    {
        var frame = ActiveFrame;
        var episode = frame?.Flow == Flow.Death && !frame.Closed && ReferenceEquals(frame.Episode?.Source, source) &&
            ReferenceEquals(frame.Episode.Monster, monster) ? frame.Episode : null;
        if (episode is null) { await monster.TriggerAboutToBlowState(); return; }
        if (Allow(episode))
        {
            CheckHandoffPrefixes(AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState)));
            var previous = PendingPhase.Value; PendingPhase.Value = new(episode);
            Task native;
            try { native = monster.TriggerAboutToBlowState(); }
            finally { PendingPhase.Value = previous; }
            await native;
        }
        if (episode.Decision.Cancelled && IsCurrent(episode)) await RemoveSource(episode);
    }
    private static async Task ProtectedHp(Creature owner, decimal amount)
    {
        var episode = ActiveFrame is { Flow: Flow.Phase, Closed: false } frame ? frame.Episode : null;
        if (episode is null || !ReferenceEquals(episode.Owner, owner)) { await CreatureCmd.SetMaxAndCurrentHp(owner, amount); return; }
        await PauseAt(episode, "before-protected-max-hp:instrumented");
        if (!Allow(episode)) return;
        var beforeMax = owner.MaxHp;
        var max = CreatureCmd.SetMaxHp(owner, amount);
        episode.Decision.RecordNativeWrite(new object(), "protected-max-hp", owner, beforeMax, owner.MaxHp);
        await max;
        // Positive SetMaxHp is synchronous in the pinned game. This observer is
        // explicitly instrumented, not a claim of a naturally yielding max/current gap.
        await PauseAt(episode, "after-protected-max-hp:instrumented");
        if (!Allow(episode)) return;
        var beforeHp = owner.CurrentHp;
        var hp = CreatureCmd.SetCurrentHp(owner, amount);
        episode.Decision.RecordNativeWrite(new object(), "protected-current-hp", owner, beforeHp, owner.CurrentHp);
        await hp;
        await PauseAt(episode, "after-protected-current-hp");
    }
    private static bool PhaseAllowed() => ActiveFrame is not { Flow: Flow.Phase, Closed: false, Episode: { } episode } || Allow(episode);
    private static void PhaseDisplay(Creature owner, HpDisplay display) { if (PhaseAllowed()) owner.HpDisplay = display; }
    private static void PhaseQueue(MonsterModel monster, MoveState state, bool force) { if (PhaseAllowed()) monster.SetMoveImmediate(state, force); }
    private static void PhaseMusic(NRunMusicController music, string parameter, float value) { if (PhaseAllowed()) music.UpdateMusicParameter(parameter, value); }
    private static void PhaseAmbient(string path, string parameter, float value) { if (PhaseAllowed()) SfxCmd.SetParam(path, parameter, value); }
    private static void ExplosionMusic(NRunMusicController music, string parameter, float value)
    {
        var episode = ActiveFrame is { Flow: Flow.Explode, Closed: false } frame ? frame.Episode : null;
        // Preserve this event's terminal music, including when it was cancelled.
        // An old scene continuation must not change a newer combat's music.
        if (episode is null || IsCurrent(episode) && ReferenceEquals(episode.Combat, MegaCrit.Sts2.Core.Combat.CombatManager.Instance.DebugOnlyGetState()))
            music.UpdateMusicParameter(parameter, value);
    }
    private static bool AboutAllowed(WaterfallGiant monster) => CurrentEpisode(Flow.About, monster) is not { } episode || Allow(episode);
    private static void AboutDamage(WaterfallGiant monster, int amount) { if (AboutAllowed(monster)) SetSteamDamage(monster, amount); }
    private static void AboutBuildup(WaterfallGiant monster, int index) { if (AboutAllowed(monster)) SetBuildup(monster, index); }
    private static void AboutVisual(WaterfallGiant monster) { if (AboutAllowed(monster)) IncrementBuildup(monster); }
    private static bool CompleteStaleMove(WaterfallGiant monster, ref int state, ref AsyncTaskMethodBuilder builder)
    {
        if (state != -1 || LatestFor(monster) is not { } episode) return false;
        if (IsCurrent(episode) && !episode.Decision.Retired && !episode.Decision.TerminalStarted &&
            !(episode.Decision.Cancelled && episode.NodeRemoved && episode.Owner.IsDead)) return false;
        state = -2; builder.SetResult(); return true;
    }
    private static IEnumerable<CodeInstruction> SteamDeathCallback(IEnumerable<CodeInstruction> input, MethodBase __originalMethod) =>
        Replace(input, AccessTools.Method(typeof(WaterfallGiant), nameof(WaterfallGiant.TriggerAboutToBlowState)), nameof(TriggerPhase),
            subject: Field(__originalMethod.DeclaringType!, field => field.FieldType == typeof(SteamEruptionPower)));
    private static IEnumerable<CodeInstruction> PhaseMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var code = Replace(input, AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.SetMaxAndCurrentHp)), nameof(ProtectedHp));
        code = Replace(code, AccessTools.PropertySetter(typeof(Creature), nameof(Creature.HpDisplay)), nameof(PhaseDisplay));
        code = Replace(code, AccessTools.Method(typeof(MonsterModel), nameof(MonsterModel.SetMoveImmediate)), nameof(PhaseQueue));
        code = Replace(code, AccessTools.Method(typeof(NRunMusicController), nameof(NRunMusicController.UpdateMusicParameter)), nameof(PhaseMusic));
        code = Replace(code, AccessTools.Method(typeof(SfxCmd), nameof(SfxCmd.SetParam)), nameof(PhaseAmbient));
        return Scope(code, generator, __originalMethod, Flow.Phase);
    }
    private static IEnumerable<CodeInstruction> AboutMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var code = Replace(input, AccessTools.PropertySetter(typeof(WaterfallGiant), "SteamEruptionDamage"), nameof(AboutDamage));
        code = Replace(code, AccessTools.PropertySetter(typeof(WaterfallGiant), "PressureBuildupIdx"), nameof(AboutBuildup));
        code = Replace(code, AccessTools.Method(typeof(WaterfallGiant), "IncrementBuildUpAnimationTrack"), nameof(AboutVisual));
        code = Scope(code, generator, __originalMethod, Flow.About);
        return EarlyEntry(code, generator, __originalMethod, Subject(__originalMethod.DeclaringType!, Flow.About), nameof(CompleteStaleMove));
    }
    private static IEnumerable<CodeInstruction> ExplodeMachine(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var source = Subject(__originalMethod.DeclaringType!, Flow.Explode);
        var code = Replace(input, AccessTools.Method(typeof(MegaCrit.Sts2.Core.Commands.Builders.AttackCommand), "Execute"), nameof(ExplodeAttack), subject: source);
        code = Replace(code, AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Kill), [typeof(Creature), typeof(bool)]), nameof(ExplodeTerminal), subject: source);
        code = Replace(code, AccessTools.Method(typeof(NRunMusicController), nameof(NRunMusicController.UpdateMusicParameter)), nameof(ExplosionMusic));
        code = Scope(code, generator, __originalMethod, Flow.Explode);
        return EarlyEntry(code, generator, __originalMethod, source, nameof(CompleteStaleMove));
    }
}
