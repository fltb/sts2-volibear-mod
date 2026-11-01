using System;
using System.Threading.Tasks;
using System.Collections.Generic;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;

namespace Volibear;

/// <summary>Explicit probe-only foreign final votes; actual native hooks and commands still run.</summary>
internal sealed class DomainSteamForeignFixture : IDisposable
{
    private static DomainSteamForeignFixture? Active;
    private readonly Harmony _harmony = new("Volibear.SteamProbe.ForeignFixture");
    private readonly Creature _boss;
    internal bool RejectNextDeath, Retain;
    internal Func<Task>? BeforeNextDeath, AfterLethalHp, AfterLethalDamage;
    private readonly List<object> _hookWindows = [];
    private bool _restore;
    internal int BeforeDeathCalls, Vetoes, RestoreCalls, Restorations, RetentionVotes;
    private readonly List<int> _nativeRecursions = [];
    private readonly List<object> _votes = [];
    private static void NativeEntry(Creature creature, int recursion)
    { if (Active is { } active && ReferenceEquals(creature, active._boss)) active._nativeRecursions.Add(recursion); }
    internal DomainSteamForeignFixture(Creature boss)
    {
        if (Active is not null) throw new InvalidOperationException("Concurrent foreign fixture.");
        _boss = boss; Active = this;
        try { InstallPatches(_harmony); }
        catch { Active = null; _harmony.UnpatchAll(_harmony.Id); throw; }
    }
    private static void BeforePost(Creature creature, ref Task __result)
    { if (Active is { } active && ReferenceEquals(creature, active._boss)) __result = active.Before(__result); }
    private async Task Before(Task original)
    {
        await original; BeforeDeathCalls++;
        var callback = BeforeNextDeath; BeforeNextDeath = null;
        if (callback is not null) await callback();
    }
    private static void HpPost(Creature creature, decimal delta, ref Task __result)
    { if(Active is { AfterLethalHp: not null } active && ReferenceEquals(creature,active._boss) && delta<0) __result=active.Window(__result,true); }
    private static void DamagePost(Creature target, ref Task __result)
    { if(Active is { AfterLethalDamage: not null } active && ReferenceEquals(target,active._boss)) __result=active.Window(__result,false); }
    private async Task Window(Task original,bool hp)
    {
        await original;
        if(!_boss.IsDead) return;
        var callback=hp?AfterLethalHp:AfterLethalDamage;
        if(hp) AfterLethalHp=null; else AfterLethalDamage=null;
        _hookWindows.Add(new {point=hp?"AfterCurrentHpChanged":"AfterDamageGiven",bossHp=_boss.CurrentHp,deathEntries=_nativeRecursions.Count,
            nativeEventCursor=DomainSteamNativeObservation.EventCursor,stageId=DomainSteamNativeObservation.StageIdentity});
        if(callback is not null) await callback();
    }
    private static void DeathPost(Creature creature, ref AbstractModel? preventer, ref bool __result)
    {
        if (Active is not { } active || !ReferenceEquals(creature, active._boss)) return;
        active._votes.Add(new { native = __result, final = active.RejectNextDeath ? false : __result, injected = active.RejectNextDeath });
        if (!active.RejectNextDeath) return;
        if (!__result) throw new InvalidOperationException("Unexpected pre-existing native death veto.");
        active.RejectNextDeath = false; active._restore = true; active.Vetoes++;
        // This is a labelled final-vote injection, not a claim that Waterfall's native ShouldDie rejects.
        preventer = creature.Monster; __result = false;
    }
    private static void PreventedPost(Creature creature, ref Task __result)
    { if (Active is { _restore: true } active && ReferenceEquals(creature, active._boss)) __result = active.Restore(__result); }
    private async Task Restore(Task original)
    {
        await original; _restore = false;
        using var stage = DomainSteamNativeObservation.BeginFixtureStage("foreign-native-restoration");
        RestoreCalls++;
        await CreatureCmd.SetCurrentHp(_boss, 999999999m); Restorations++;
    }
    private static void RetentionPost(Creature creature, ref bool __result)
    { if (Active is { Retain: true } active && ReferenceEquals(creature, active._boss)) { active.RetentionVotes++; __result = false; } }
    internal static void InstallPatches(Harmony harmony)
    {
        harmony.Patch(AccessTools.Method(typeof(CreatureCmd), "KillWithoutCheckingWinCondition"), prefix: new HarmonyMethod(typeof(DomainSteamForeignFixture), nameof(NativeEntry)));
        foreach (var pair in new[] { (nameof(Hook.BeforeDeath), nameof(BeforePost)), (nameof(Hook.ShouldDie), nameof(DeathPost)),
            (nameof(Hook.AfterCurrentHpChanged), nameof(HpPost)), (nameof(Hook.AfterDamageGiven), nameof(DamagePost)),
            (nameof(Hook.AfterPreventingDeath), nameof(PreventedPost)), (nameof(Hook.ShouldCreatureBeRemovedFromCombatAfterDeath), nameof(RetentionPost)) })
            harmony.Patch(AccessTools.Method(typeof(Hook), pair.Item1), postfix: new HarmonyMethod(typeof(DomainSteamForeignFixture), pair.Item2) { priority = Priority.Last });
    }
    internal object Snapshot() => new { beforeDeathCalls = BeforeDeathCalls, vetoes = Vetoes, restoreCalls = RestoreCalls, restorations = Restorations, retentionVotes = RetentionVotes,
        hookWindows = _hookWindows.ToArray(), nativeRecursions = _nativeRecursions.ToArray(), votes = _votes.ToArray(),
        instrumentation = "foreign-final-hook-vote-and-native-AfterPreventingDeath-HP-restoration-not-mock-power" };
    public void Dispose() { _harmony.UnpatchAll(_harmony.Id); if (ReferenceEquals(Active, this)) Active = null; }
}
