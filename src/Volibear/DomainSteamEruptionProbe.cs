using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>Formal native mechanism probe; neither normal paid-card nor whole enemy-turn acceptance.
/// Boundary observers are explicitly instrumented. No state forcing or mock monster/power deployment.</summary>
internal static class DomainSteamEruptionProbe
{
    // Only the separately named sole-ending negative measures this native tail.
    // No gameplay method is called: preserve the removed node reference until its
    // own animation queues deletion and _ExitTree stops the creature-owned loop.
    private sealed class SoleAudioTail : IDisposable
    {
        private const string Ambient = "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_ambient";
        private static SoleAudioTail? Active;
        private readonly NCreature node;
        private readonly System.Collections.IDictionary loops;
        private readonly Harmony harmony = new("Volibear.SteamProbe.SoleAudioTail");
        private readonly TaskCompletionSource exited = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly List<string> events = [];
        private readonly ulong nodeId;
        private ulong exitNodeId;
        private bool insideExit;
        internal SoleAudioTail(Creature boss)
        {
            node = NCombatRoom.Instance?.GetCreatureNode(boss) ?? throw new InvalidOperationException("Missing original sole boss node.");
            nodeId = node.GetInstanceId();
            loops = (System.Collections.IDictionary)(AccessTools.Field(typeof(NCreature), "_sfxLoops").GetValue(node)
                ?? throw new InvalidOperationException("Missing original native loop registry."));
            if (Active is not null) throw new InvalidOperationException("Concurrent sole audio tail.");
            Active = this; node.TreeExited += OnExited;
            try
            {
                harmony.Patch(AccessTools.Method(typeof(NCreature), nameof(NCreature._ExitTree)),
                    prefix: new HarmonyMethod(typeof(SoleAudioTail), nameof(ExitBefore)), postfix: new HarmonyMethod(typeof(SoleAudioTail), nameof(ExitAfter)));
                harmony.Patch(AccessTools.Method(typeof(NCreature), nameof(NCreature.StopSfxLoop)),
                    prefix: new HarmonyMethod(typeof(SoleAudioTail), nameof(StopBefore)), postfix: new HarmonyMethod(typeof(SoleAudioTail), nameof(StopAfter)));
            }
            catch { Dispose(); throw; }
        }
        private static void ExitBefore(NCreature __instance)
        {
            if (Active is not { } a || !ReferenceEquals(a.node, __instance)) return;
            a.exitNodeId = __instance.GetInstanceId(); a.insideExit = true; a.events.Add("exit-enter");
        }
        private static void ExitAfter(NCreature __instance)
        {
            if (Active is not { } a || !ReferenceEquals(a.node, __instance)) return;
            a.events.Add("exit-body-finished"); a.insideExit = false;
        }
        private static void StopBefore(NCreature __instance, string sfxName, out bool __state) => __state =
            Active is { } a && ReferenceEquals(a.node, __instance) && sfxName == Ambient && a.loops.Contains(Ambient);
        private static void StopAfter(NCreature __instance, string sfxName, bool __state)
        {
            if (Active is not { } a || !ReferenceEquals(a.node, __instance) || sfxName != Ambient) return;
            a.events.Add(__state && !a.loops.Contains(Ambient) && a.insideExit ? "effective-stop-in-exit" : "unexpected-stop");
        }
        private void OnExited() { events.Add("tree-exited"); exited.TrySetResult(); }
        internal async Task<object> Complete(DomainSteamNativeObservation native, Func<object> world)
        {
            var animation = node.DeathAnimationTask ?? throw new InvalidOperationException("Missing original native death animation task.");
            await Task.WhenAll(animation, exited.Task).WaitAsync(TimeSpan.FromSeconds(15));
            return new { scope = "sole-native-node-exit-after-action-before-wincheck", nodeId, exitNodeId,
                treeExited = exited.Task.IsCompletedSuccessfully, originalAnimationCompleted = animation.IsCompletedSuccessfully,
                finalLoopRegistered = loops.Contains(Ambient), events = events.ToArray(),
                worldAtExit = world(), nativeAtExit = native.Snapshot() };
        }
        public void Dispose()
        {
            if (GodotObject.IsInstanceValid(node)) node.TreeExited -= OnExited;
            harmony.UnpatchAll(harmony.Id); if (ReferenceEquals(Active, this)) Active = null;
        }
    }
    private static bool _started;
    private static Creature? _applicationOwner;
    private static DomainPower? _appliedInstance;
    private static Task? _afterAppliedTask;
    private static int _afterAppliedCalls;
    private static void ObserveAfterApplied(DomainPower __instance, Task __result)
    {
        if (!ReferenceEquals(__instance.Owner, _applicationOwner)) return;
        _afterAppliedCalls++; _appliedInstance = __instance; _afterAppliedTask = __result;
    }
    public static void Install() => CombatManager.Instance.TurnStarted += Start;
    private static void Start(CombatState combat)
    {
        if (_started) return; _started = true; CombatManager.Instance.TurnStarted -= Start; _ = Run(combat);
    }
    private static object Snapshot(Creature boss, Creature player, Creature? pet, CombatState combat) => new
    {
        bossHp = boss.CurrentHp, bossMaxHp = boss.MaxHp, bossAlive = boss.IsAlive,
        attached = ReferenceEquals(boss.CombatState, combat), listed = combat.ContainsCreature(boss),
        nodePresent = NCombatRoom.Instance?.GetCreatureNode(boss) is not null,
        sourcePresent = boss.HasPower<SteamEruptionPower>(), hpDisplay = boss.HpDisplay.ToString(),
        nextMove = boss.Monster!.MoveStateMachine is null ? null : boss.Monster.NextMove.Id,
        playerHp = player.CurrentHp, playerMaxHp = player.MaxHp, playerBlock = player.Block,
        petType = pet?.Monster?.GetType().Name, petHp = pet?.CurrentHp, petMaxHp = pet?.MaxHp,
        domain = player.GetPowerAmount<DomainPower>(),
        nativeEventCursor = DomainSteamNativeObservation.EventCursor, nativeStageId = DomainSteamNativeObservation.StageIdentity,
    };
    private static async Task Run(CombatState combat)
    {
        Func<Creature, string, Task>? boundary = null; Action<Creature, string>? observed = null;
        Harmony? applyObserver = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var requestedVariant = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_VARIANT") ?? "";
            var keeperVariants = new[] { "keeper-external-after-hp", "keeper-veto-after-hp", "keeper-external-after-damage", "keeper-veto-after-damage", "keeper-external-set-hp", "keeper-veto-set-hp" };
            var endingVariants = new[] { "sole-ending-external-after-hp", "sole-ending-external-after-damage", "sole-ending-external-set-hp" };
            bool withKeeper = keeperVariants.Contains(requestedVariant), endingNegative = endingVariants.Contains(requestedVariant);
            bool applicationCase = withKeeper || endingNegative;
            var variant = withKeeper ? requestedVariant[7..] : endingNegative ? requestedVariant[12..] : requestedVariant;
            var variants = new[] { "off", "on", "toggle", "late-phase", "late-powerless", "pre-max", "post-max", "post-protected-hp", "before-block", "after-block", "before-hp", "after-hp", "overflow", "ordinary", "nested-command", "nested-damage", "after-removed-reentry", "veto-source-retained", "veto-powerless", "external-powerless", "foreign-retention", "pending-reset", "external-after-hp", "veto-after-hp", "external-after-damage", "veto-after-damage", "external-set-hp", "veto-set-hp", "off-veto-followup" };
            if (string.IsNullOrEmpty(token) || !variants.Contains(variant) || TestMode.IsOn || combat.Encounter is not WaterfallGiantBoss)
                throw new InvalidOperationException("Steam probe requires token, exact variant, TestMode off and WaterfallGiantBoss.");
            var owner = combat.Players.Single(); var player = owner.Creature;
            var boss = combat.Enemies.Single(); var giant = boss.Monster as WaterfallGiant ?? throw new InvalidOperationException("Wrong native boss.");
            var bossCombatId = boss.CombatId;
            var context = new ThrowingPlayerChoiceContext(); Creature? pet = null;
            if (player.GetPowerAmount<DomainPower>() != 0 || player.Block != 0 || giant.NextMove.Id != "PRESSURIZE_MOVE")
                throw new InvalidOperationException("Expected fresh native first-turn fixture.");
            await CreatureCmd.SetCurrentHp(player, player.MaxHp);
            await CreatureCmd.GainBlock(player, 6m, ValueProp.Unpowered, null);
            if (variant == "overflow")
            {
                await OstyCmd.Summon(context, owner, 5m, null);
                pet = owner.Osty;
                if (pet?.Monster is not Osty || pet.CurrentHp != 5 || pet.MaxHp != 5) throw new InvalidOperationException("Native Osty setup mismatch.");
            }
            Creature? keeper = null; int keeperAddCalls = 0, keeperAddCompleted = 0, keeperDied = 0, keeperCleanupCalls = 0, bossCleanupCalls = 0;
            object KeeperState() => new { present = keeper is not null, combatId = keeper?.CombatId, model = keeper?.Monster?.GetType().Name,
                hp = keeper?.CurrentHp, alive = keeper?.IsAlive ?? false, primary = keeper?.IsPrimaryEnemy ?? false,
                minion = keeper?.HasPower<MinionPower>() ?? false, osty = keeper?.Monster is Osty,
                attached = keeper is not null && ReferenceEquals(keeper.CombatState, combat), listed = keeper is not null && combat.ContainsCreature(keeper),
                nodePresent = keeper is not null && NCombatRoom.Instance?.GetCreatureNode(keeper) is not null };
            if (withKeeper)
            {
                keeperAddCalls++; keeper = await CreatureCmd.Add<Stabbot>(combat); keeperAddCompleted++;
                if (!keeper.IsAlive || !keeper.IsPrimaryEnemy || keeper.HasPower<MinionPower>() || keeper.Monster is Osty ||
                    keeper.CombatId is null || !ReferenceEquals(keeper.CombatState, combat) || !combat.ContainsCreature(keeper))
                    throw new InvalidOperationException("Native keeper must be an attached living primary, not Minion/Osty.");
                keeper.Died += creature => { if (ReferenceEquals(creature, keeper)) keeperDied++; };
            }
            object? keeperAfterAdd = applicationCase ? KeeperState() : null;
            object? keeperBeforeApply = null, keeperAfterApply = null, keeperAfterAction = null, keeperBeforeCleanup = null, keeperAfterCleanup = null;
            object? applyEvidence = null, sourceAfterCleanup = null, bossAfterCleanup = null;
            if (applicationCase)
            {
                _applicationOwner = player; _appliedInstance = null; _afterAppliedTask = null; _afterAppliedCalls = 0;
                applyObserver = new Harmony("Volibear.SteamProbe.NativeDomainApply");
                applyObserver.Patch(AccessTools.Method(typeof(DomainPower), nameof(DomainPower.AfterApplied)),
                    postfix: new HarmonyMethod(typeof(DomainSteamEruptionProbe), nameof(ObserveAfterApplied)));
            }
            using var native = new DomainSteamNativeObservation(boss, player, pet);
            using var soleTail = endingNegative ? new SoleAudioTail(boss) : null;
            using var foreign = new DomainSteamForeignFixture(boss);
            foreign.Retain = variant == "foreign-retention";
            var resets = 0; var nestedCalls = 0; var removalReentries = 0;
            object? beforeChallenge = null; object? afterChallenge = null; object? challengeState = null;
            object? windowBefore = null, windowAfter = null;
            var hookWindow = variant.EndsWith("-after-hp", StringComparison.Ordinal) || variant.EndsWith("-after-damage", StringComparison.Ordinal) || variant.EndsWith("-set-hp", StringComparison.Ordinal);
            var attemptedMoves = new List<string>(); var trace = new List<string>();
            async Task Move()
            {
                attemptedMoves.Add(giant.NextMove.Id);
                using var stage = native.BeginStage("move:" + giant.NextMove.Id);
                await giant.PerformMove();
                if (boss.IsAlive && ReferenceEquals(boss.CombatState, combat)) boss.PrepareForNextTurn(combat.Players.Select(p => p.Creature));
            }
            await Move(); // Actual PRESSURIZE_MOVE creates the actual SteamEruptionPower.
            var source = boss.GetPower<SteamEruptionPower>() ?? throw new InvalidOperationException("Native pressurize did not deploy Steam.");
            native.Source = source;
            var sourceAmount = source.Amount;
            var initial = Snapshot(boss, player, pet, combat);
            var died = 0; var sourceRemoved = 0; var opens = 0; var boundaryHits = 0;
            boss.Died += creature => { if (ReferenceEquals(creature, boss)) died++; };
            boss.PowerRemoved += power => { if (ReferenceEquals(power, source)) sourceRemoved++; };
            object? beforeOpen = null; object? afterOpen = null;
            async Task Open(bool directNativeApply = false)
            {
                using var stage = native.BeginStage("domain-entry:" + variant);
                beforeOpen = Snapshot(boss, player, pet, combat);
                var endingBefore = applicationCase && CombatManager.Instance.IsEnding;
                var primaryBefore = applicationCase ? combat.Enemies.Count(e => e.IsAlive && e.IsPrimaryEnemy) : 0;
                var appliedCallsBefore = _afterAppliedCalls;
                if (applicationCase) keeperBeforeApply = KeeperState();
                DomainPower? applied;
                if (directNativeApply) applied = await PowerCmd.Apply<DomainPower>(context, player, 3m, player, null);
                else applied = await DomainPower.Open(context, player, 3); // Original AfterApplied is awaited by native Apply, never called by this fixture.
                opens++; afterOpen = Snapshot(boss, player, pet, combat);
                if (applicationCase)
                {
                    keeperAfterApply = KeeperState();
                    applyEvidence = new { api = "PowerCmd.Apply<DomainPower>", nativeIsEndingBefore = endingBefore, activePrimaryBefore = primaryBefore,
                        returnedPower = applied?.GetType().Name, returnedMatchesOwnerPower = applied is not null && ReferenceEquals(applied, player.GetPower<DomainPower>()),
                        afterAppliedCalls = _afterAppliedCalls - appliedCallsBefore, afterAppliedInstanceMatches = applied is not null && ReferenceEquals(applied, _appliedInstance),
                        afterAppliedTaskCompleted = _afterAppliedTask?.IsCompletedSuccessfully ?? false, domainAfter = player.GetPowerAmount<DomainPower>() };
                }
            }
            var point = variant switch
            {
                "pre-max" => "before-protected-max-hp:instrumented",
                "post-max" => "after-protected-max-hp:instrumented",
                "post-protected-hp" => "after-protected-current-hp",
                "before-block" or "nested-command" or "nested-damage" or "pending-reset" => "before-block",
                "after-block" => "after-block-before-primary-modifiers",
                "before-hp" => "before-primary-hp",
                "after-hp" => "after-hp-hooks",
                "overflow" => "before-overflow-hp", _ => "none",
            };
            boundary = async (creature, location) =>
            {
                if (!ReferenceEquals(creature, boss) || location != point || boundaryHits != 0) return;
                boundaryHits++;
                if (variant == "pending-reset")
                {
                    beforeChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                    DomainSteamEruptionEffects.Reset(); resets++;
                    await Task.Yield(); // Real native Damage remains suspended; adapter-only reset, not combat teardown.
                    afterChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                    return;
                }
                await Open();
                if (variant == "nested-command")
                { using var stage = native.BeginStage("nested-native-command"); nestedCalls++; await DamageCmd.Attack(2m).FromMonster(giant).Execute(context); }
                if (variant == "nested-damage")
                { using var stage = native.BeginStage("nested-native-damage"); nestedCalls++; await CreatureCmd.Damage(context, new[] { player }, 2m, ValueProp.Move, boss, null); }
            };
            observed = (creature, location) => { if (ReferenceEquals(creature, boss)) trace.Add(location); };
            DomainSteamEruptionEffects.Boundary += boundary; DomainSteamEruptionEffects.Observed += observed;
            if (variant == "after-removed-reentry") native.AfterRemovedBoundary = async () =>
            {
                using var stage = native.BeginStage("after-removed-reentry");
                native.AfterRemovedBoundary = null; removalReentries++;
                beforeChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                await Task.Yield();
                await PowerCmd.Remove<DomainPower>(player);
                await DomainPower.Open(context, player, 3); opens++;
                challengeState = Snapshot(boss, player, pet, combat);
                afterChallenge = DomainSteamEruptionEffects.Observation(giant, player);
            };
            if (variant is "on" or "toggle" or "ordinary" or "foreign-retention") await Open();
            if (variant == "toggle") await PowerCmd.Remove<DomainPower>(player);
            MoveState? captured = null; object? afterDeath = null;
            if (variant == "ordinary") await Move(); // The next native STOMP is an ordinary attack, not Steam provenance.
            else
            {
                using (native.BeginStage("initial-native-kill")) await CreatureCmd.Kill(boss);
                afterDeath = Snapshot(boss, player, pet, combat);
                if (variant == "veto-source-retained")
                {
                    beforeChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                    foreign.RejectNextDeath = true; using (native.BeginStage("veto-native-kill")) await CreatureCmd.Kill(boss);
                    afterChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                    challengeState = Snapshot(boss, player, pet, combat);
                }
                if (variant is "late-phase" or "after-removed-reentry") { captured = giant.NextMove; await Open(); }
                else if (variant is not ("on" or "pre-max" or "post-max" or "post-protected-hp" or "foreign-retention"))
                {
                    await Move(); // Actual ABOUT_TO_BLOW removes Steam, then natural Prepare queues EXPLODE.
                    if (variant == "late-powerless") { captured = giant.NextMove; await Open(); }
                    else if (variant is "veto-powerless" or "external-powerless" || hookWindow)
                    {
                        beforeChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                        foreign.RejectNextDeath = variant.StartsWith("veto-", StringComparison.Ordinal);
                        if (!hookWindow) foreign.BeforeNextDeath = () => Open(true);
                        else
                        {
                            async Task Window()
                            {
                                windowBefore = DomainSteamEruptionEffects.Observation(giant, player);
                                await Task.Yield(); // Hold the actual native post-HP hook await before native Kill begins.
                                await Open(true);
                                windowAfter = DomainSteamEruptionEffects.Observation(giant, player);
                            }
                            if (variant.EndsWith("-after-damage", StringComparison.Ordinal)) foreign.AfterLethalDamage = Window;
                            else foreign.AfterLethalHp = Window;
                        }
                        if (variant.EndsWith("-set-hp", StringComparison.Ordinal))
                        { using var stage = native.BeginStage("external-set-hp"); await CreatureCmd.SetCurrentHp(boss, 0m); }
                        else
                        { using var stage = native.BeginStage("external-native-damage"); await CreatureCmd.Damage(context, new[] { boss }, boss.CurrentHp, ValueProp.Unblockable | ValueProp.Unpowered, player, null); }
                        afterChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                        challengeState = Snapshot(boss, player, pet, combat);
                    }
                    else if (variant == "off-veto-followup")
                    {
                        beforeChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                        foreign.RejectNextDeath = true; await Move();
                        afterChallenge = DomainSteamEruptionEffects.Observation(giant, player);
                        challengeState = Snapshot(boss, player, pet, combat);
                        await Move(); // A second real native EXPLODE self-followup, not a captured callback replay.
                    }
                    else await Move();
                }
            }
            if (captured is not null)
            {
                using var stage = native.BeginStage("captured-reentry:" + captured.Id);
                await PowerCmd.Remove<DomainPower>(player);
                await captured.PerformMove(combat.Players.Select(p => p.Creature)); // Deliberate stale native callback reentry, never delete this assertion path.
            }
            var final = Snapshot(boss, player, pet, combat);
            var observation = DomainSteamEruptionEffects.Observation(giant, player);
            var nativeObservation = native.Snapshot();
            var foreignObservation = foreign.Snapshot(); foreign.Dispose();
            // Keep the action-end snapshots above immutable. This separate receipt
            // cannot be replaced by victory/room cleanup or a later forced stop.
            object? soleAudioTail = soleTail is null ? null : await soleTail.Complete(native, () => Snapshot(boss, player, pet, combat));
            native.Dispose(); // Exclude victory/relic healing and room-exit cleanup from this action window.
            var measuredDied = died; var measuredRemoved = sourceRemoved; var measuredTrace = trace.ToArray();
            if (applicationCase) keeperAfterAction = KeeperState();
            var beforeCleanupInProgress = CombatManager.Instance.IsInProgress;
            var victories = 0; var endings = 0;
            CombatManager.Instance.CombatWon += _ => victories++; CombatManager.Instance.CombatEnded += _ => endings++;
            if (withKeeper)
            {
                var tree = (SceneTree)Engine.GetMainLoop();
                // Measured veto/retirement window is over. Separate native cleanup, never a rescue Apply.
                if (boss.IsAlive) { bossCleanupCalls++; await CreatureCmd.Kill(boss); }
                await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                sourceAfterCleanup = DomainSteamEruptionEffects.Observation(giant, player);
                bossAfterCleanup = Snapshot(boss, player, pet, combat);
                keeperBeforeCleanup = KeeperState();
                keeperCleanupCalls++; await CreatureCmd.Kill(keeper!);
                await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                keeperAfterCleanup = KeeperState();
            }
            var explicitWinCheck = withKeeper || variant is not ("ordinary" or "veto-powerless" or "foreign-retention" or "pending-reset") && !(hookWindow && variant.StartsWith("veto-", StringComparison.Ordinal));
            var checkResult = explicitWinCheck && await CombatManager.Instance.CheckWinCondition();
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing native release metadata.");
            var nativeVersion = release.Version;
            var gameVersion = nativeVersion.StartsWith("v", StringComparison.Ordinal) ? nativeVersion[1..] : nativeVersion;
            var result = new
            {
                token, scenario = "domain-steam", variant = requestedVariant, completed = true, testMode = false,
                fixtureVariant = applicationCase ? variant : null,
                applicationFixture = applicationCase ? new { kind = withKeeper ? "native-primary-keeper" : "sole-primary-ending-negative",
                    keeperAddCalls, keeperAddCompleted, bossCombatId, keeperAfterAdd, keeperBeforeApply, keeperAfterApply, keeperAfterAction,
                    applyEvidence, beforeCleanupInProgress, bossCleanupCalls, bossCleanupDeaths = died - measuredDied,
                    keeperBeforeCleanup, keeperCleanupCalls, keeperDied, keeperAfterCleanup, sourceAfterCleanup, bossAfterCleanup,
                    cleanupTrace = trace.Skip(measuredTrace.Length).ToArray() } : null,
                gameVersion, gameCommit = release.Commit,
                acceptance = "formal-native-steam-mechanism-with-labelled-instrumented-boundaries-not-normal-card-or-enemy-turn",
                fixtureApi = "native PRESSURIZE/ABOUT_TO_BLOW/EXPLODE/STOMP;CreatureCmd.Kill;Creature.PrepareForNextTurn;DomainPower.Open;OstyCmd.Summon(overflow-only)",
                encounter = combat.Encounter.GetType().Name, nativeType = giant.GetType().Name, sourceType = source.GetType().Name, sourceAmount,
                initial, beforeOpen, afterOpen, afterDeath, final, observation, attemptedMoves, nativeObservation, foreignObservation, soleAudioTail, trace = applicationCase ? measuredTrace : trace.ToArray(),
                beforeChallenge, afterChallenge, challengeState, windowBefore, windowAfter, resets, nestedCalls, removalReentries,
                challengeInstrumentation = (variant switch
                {
                    "veto-source-retained" => "foreign-final-vote-native-restoration",
                    "veto-powerless" => "real-lethal-Damage-before-Kill;native-BeforeDeath-direct-PowerCmd.Apply;foreign-final-vote-native-restoration",
                    "external-powerless" => "real-lethal-Damage-before-Kill;native-BeforeDeath-direct-PowerCmd.Apply;native-death-confirmation",
                    "external-after-hp" or "veto-after-hp" => "real-lethal-Damage;native-AfterCurrentHpChanged-completion-await-before-Kill;direct-PowerCmd.Apply;labelled-final-vote",
                    "external-after-damage" or "veto-after-damage" => "real-lethal-Damage;native-AfterDamageGiven-completion-await-before-Kill;direct-PowerCmd.Apply;labelled-final-vote",
                    "external-set-hp" or "veto-set-hp" => "real-lethal-SetCurrentHp;native-AfterCurrentHpChanged-completion-await-before-Kill;direct-PowerCmd.Apply;labelled-final-vote",
                    "off-veto-followup" => "no-Domain;real-EXPLODE-foreign-veto-native-restoration;real-native-self-followup-EXPLODE",
                    "foreign-retention" => "foreign-final-native-removal-vote",
                    "pending-reset" => "adapter-only-reset-at-native-Damage-await-not-full-combat-reset-not-Godot-boxing-proof",
                    "after-removed-reentry" => "instrumented-async-native-AfterRemoved-completion-boundary-Domain-reapply",
                    "nested-command" or "nested-damage" => "real-untagged-native-invocation-inside-tagged-Damage",
                    _ => "none",
                }) + (withKeeper ? ";native-primary-keeper" : endingNegative ? ";sole-primary-ending-negative" : ""),
                boundary = point, boundaryMode = point == "none" ? "none" : "instrumented-domain-open-at-native-command-or-hook-completion",
                opens, boundaryHits, reentry = captured?.Id, died = measuredDied, sourceRemoved = measuredRemoved,
                explicitWinCheck, checkResult, victories, endings, inProgress = CombatManager.Instance.IsInProgress,
            };
            GD.Print("[Volibear] DOMAIN_STEAM_RESULT " + JsonSerializer.Serialize(result));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit();
        }
        catch (Exception error)
        { GD.PrintErr("[Volibear] DOMAIN_STEAM_PROBE_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally
        {
            applyObserver?.UnpatchAll(applyObserver.Id); _applicationOwner = null; _appliedInstance = null; _afterAppliedTask = null;
            if (boundary is not null) DomainSteamEruptionEffects.Boundary -= boundary;
            if (observed is not null) DomainSteamEruptionEffects.Observed -= observed;
        }
    }
}
