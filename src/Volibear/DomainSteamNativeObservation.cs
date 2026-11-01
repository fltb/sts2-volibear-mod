using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.ValueProps;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Volibear;

/// <summary>Probe-only independent native observers, not adapter decisions or planned calls.</summary>
internal sealed partial class DomainSteamNativeObservation : IDisposable
{
    private const string Ambient = "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_ambient";
    private static DomainSteamNativeObservation? Active;
    private const string ObserverHarmonyId = "Volibear.SteamProbe.NativeObservation";
    private readonly Harmony _harmony = new(ObserverHarmonyId);
    private readonly Creature _boss, _player;
    private readonly Creature? _pet;
    private readonly NCreature _node;
    private readonly List<object> _changes = [], _moves = [], _attacks = [], _damage = [], _stops = [], _externalDamageResults = [];
    private readonly List<float> _music = [], _ambient = [];
    private readonly List<(Creature creature, Action<int,int> hp, Action<int,int> block, Action<int,int> max)> _subscriptions = [];
    private readonly bool _initialLoop;
    internal PowerModel? Source;
    internal int RemovedStarted, RemovedCompleted;
    internal Func<Task>? AfterRemovedBoundary;
    internal string Stage => _stage.Value?.Name ?? "unscoped";
    private static bool HasLoop(NCreature node) => ((IDictionary)(AccessTools.Field(typeof(NCreature), "_sfxLoops").GetValue(node) ?? throw new InvalidOperationException("Missing native loop registry."))).Contains(Ambient);
    internal DomainSteamNativeObservation(Creature boss, Creature player, Creature? pet)
    {
        _boss = boss; _player = player; _pet = pet;
        _history = CombatManager.Instance.History; _initialHistory = _history.Entries.ToArray();
        _node = NCombatRoom.Instance?.GetCreatureNode(boss) ?? throw new InvalidOperationException("Missing actual boss node.");
        _initialLoop = HasLoop(_node);
        if (Active is not null) throw new InvalidOperationException("Concurrent Steam observation.");
        Active = this;
        try { InstallPatches(_harmony); }
        catch { _harmony.UnpatchAll(_harmony.Id); Active = null; throw; }
        foreach (var creature in new[] { boss, player, pet }.Where(value => value is not null).Cast<Creature>())
        {
            Action<int,int> hp = (before, after) => Change(creature, "hp", before, after);
            Action<int,int> block = (before, after) => Change(creature, "block", before, after);
            Action<int,int> max = (before, after) => Change(creature, "maxHp", before, after);
            creature.CurrentHpChanged += hp; creature.BlockChanged += block; creature.MaxHpChanged += max;
            _subscriptions.Add((creature, hp, block, max));
        }
    }
    private string Role(Creature creature) => ReferenceEquals(creature, _boss) ? "boss" : ReferenceEquals(creature, _player) ? "player" : ReferenceEquals(creature, _pet) ? "osty" : "foreign";
    private void Change(Creature creature, string field, int before, int after) => _changes.Add(new { receiver = Role(creature), field, before, after, stage = Stage, stageId = CurrentStageId, index = _changes.Count });
    private object Result(DamageResult result) => new { receiver = Role(result.Receiver), blocked = result.BlockedDamage, hp = result.UnblockedDamage,
        overkill = result.OverkillDamage, killed = result.WasTargetKilled, blockBroken = result.WasBlockBroken, fullyBlocked = result.WasFullyBlocked };
    private static void HistoryBefore(CombatHistory __instance, out CombatHistoryEntry[] __state) => __state = __instance.Entries.ToArray();
    private static void MoveAfter(CombatHistory __instance, MonsterModel monster, MoveState move, CombatHistoryEntry[] __state)
    {
        if (Active is not { } active || !ReferenceEquals(monster, active._boss.Monster)) return;
        var entry = active.Appended<MonsterPerformedMoveEntry>(__instance, __state);
        if (!ReferenceEquals(entry.Monster, monster) || !ReferenceEquals(entry.Move, move) || !ReferenceEquals(entry.Actor, active._boss))
            throw new InvalidOperationException("Native move entry identity mismatch.");
        active._moves.Add(new { id = entry.Move.Id, historyAdded = true });
    }
    private static void AttackAfter(CombatHistory __instance, Creature attacker, IReadOnlyList<DamageResult> damageResults, CombatHistoryEntry[] __state)
    {
        if (Active is not { } active || !ReferenceEquals(attacker, active._boss)) return;
        var entry = active.Appended<CreatureAttackedEntry>(__instance, __state);
        if (!ReferenceEquals(entry.Actor, attacker) || !ReferenceEquals(entry.DamageResults, damageResults))
            throw new InvalidOperationException("Native attack entry identity mismatch.");
        active._attacks.Add(new { historyAdded = true, results = entry.DamageResults.Select(active.Result).ToArray() });
    }
    private static void DamageAfter(CombatHistory __instance, Creature receiver, Creature? dealer, DamageResult result, CombatHistoryEntry[] __state)
    {
        if (Active is not { } active || (!ReferenceEquals(dealer, active._boss) && !(ReferenceEquals(dealer, active._player) && ReferenceEquals(receiver, active._boss)))) return;
        var entry = active.Appended<DamageReceivedEntry>(__instance, __state);
        if (!ReferenceEquals(entry.Actor, receiver) || !ReferenceEquals(entry.Result, result) || !ReferenceEquals(entry.Dealer, dealer) || !ReferenceEquals(entry.Result.Receiver, receiver))
            throw new InvalidOperationException("Native damage entry identity mismatch.");
        if (ReferenceEquals(entry.Dealer, active._boss)) active._damage.Add(new { historyAdded = true, result = active.Result(entry.Result) });
    }
    private static void DirectDamageAfter(Creature? dealer, ref Task<IEnumerable<DamageResult>> __result)
    { if (Active is { } active && ReferenceEquals(dealer, active._player)) __result = active.CaptureExternal(__result); }
    private async Task<IEnumerable<DamageResult>> CaptureExternal(Task<IEnumerable<DamageResult>> original)
    {
        var results = await original;
        foreach (var result in results.Where(result => ReferenceEquals(result.Receiver, _boss))) _externalDamageResults.Add(Result(result));
        return results;
    }
    private static void StopBefore(NCreature __instance, string sfxName, out bool __state) => __state =
        Active is { } active && ReferenceEquals(__instance, active._node) && sfxName == Ambient && HasLoop(__instance);
    private static void StopAfter(NCreature __instance, string sfxName, bool __state)
    {
        if (Active is { } active && ReferenceEquals(__instance, active._node) && sfxName == Ambient)
            active._stops.Add(new { before = __state, after = HasLoop(__instance), nodeStillInRoom = ReferenceEquals(NCombatRoom.Instance?.GetCreatureNode(active._boss), __instance) });
    }
    private static void MusicAfter(string label, float trackIndex)
    { if (Active is { } active && label == "waterfall_giant_progress") active._music.Add(trackIndex); }
    private static void AmbientAfter(string sfx, string param, float value)
    { if (Active is { } active && sfx == Ambient && param == "waterfall_giant_sfx") active._ambient.Add(value); }
    private static async Task RemovedCompletion(Task original, PowerModel power)
    {
        var active = Active;
        var owned = active is not null && ReferenceEquals(power, active.Source);
        if (owned) active!.RemovedStarted++;
        await original;
        if (!owned) return;
        if (active!.AfterRemovedBoundary is not null) await active.AfterRemovedBoundary();
        active.RemovedCompleted++;
    }
    private static IEnumerable<CodeInstruction> RemovalBody(IEnumerable<CodeInstruction> input, ILGenerator generator)
    {
        var source = generator.DeclareLocal(typeof(PowerModel)); var owner = generator.DeclareLocal(typeof(Creature));
        var method = AccessTools.Method(typeof(PowerModel), nameof(PowerModel.AfterRemoved));
        var result = new List<CodeInstruction>(); var count = 0;
        foreach (var instruction in input)
        {
            if (!instruction.Calls(method)) { result.Add(instruction); continue; }
            var first = new CodeInstruction(OpCodes.Stloc, owner); first.labels.AddRange(instruction.labels); instruction.labels.Clear(); first.blocks.AddRange(instruction.blocks); instruction.blocks.Clear();
            result.Add(first); result.Add(new(OpCodes.Stloc, source)); result.Add(new(OpCodes.Ldloc, source)); result.Add(new(OpCodes.Ldloc, owner));
            result.Add(instruction); // Original actual virtual AfterRemoved invocation is retained.
            result.Add(new(OpCodes.Ldloc, source)); result.Add(new(OpCodes.Call, AccessTools.Method(typeof(DomainSteamNativeObservation), nameof(RemovedCompletion)))); count++;
        }
        if (count != 1) throw new InvalidOperationException("Probe native AfterRemoved callsite drift.");
        return result;
    }
    // Prepare only the three small native audio API observers before gameplay
    // adapters can JIT callers that inline those APIs. This does not activate a
    // recording session or move the other six observer patches earlier.
    internal static void PrepareForTestScenario()
    {
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DATA_ROOT")) &&
            Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") == "domain-steam")
            InstallAudioPatches(new Harmony(ObserverHarmonyId));
    }
    private static void InstallAudioPatches(Harmony harmony)
    {
        MethodInfo Own(string name) => AccessTools.Method(typeof(DomainSteamNativeObservation), name);
        foreach (var (type, name, prefixName, postfixName) in new[]
        {
            // Patch the leaf before compiling its caller: StopSfxLoop itself calls
            // SetParam and must not inline an as-yet-unobserved leaf during patching.
            (typeof(SfxCmd), nameof(SfxCmd.SetParam), (string?)null, nameof(AmbientAfter)),
            (typeof(NRunMusicController), nameof(NRunMusicController.UpdateMusicParameter), (string?)null, nameof(MusicAfter)),
            (typeof(NCreature), nameof(NCreature.StopSfxLoop), nameof(StopBefore), nameof(StopAfter)),
        })
        {
            var method = AccessTools.Method(type, name);
            var prefix = prefixName is null ? null : Own(prefixName);
            var postfix = Own(postfixName);
            var info = Harmony.GetPatchInfo(method);
            var prefixes = info?.Prefixes.Where(patch => patch.owner == harmony.Id).ToArray() ?? [];
            var postfixes = info?.Postfixes.Where(patch => patch.owner == harmony.Id).ToArray() ?? [];
            var others = info is not null && (info.Transpilers.Any(patch => patch.owner == harmony.Id) || info.Finalizers.Any(patch => patch.owner == harmony.Id));
            if (prefixes.Length == 0 && postfixes.Length == 0 && !others)
                harmony.Patch(method, prefix: prefix is null ? null : new HarmonyMethod(prefix), postfix: new HarmonyMethod(postfix));
            else if (others || postfixes.Length != 1 || postfixes[0].PatchMethod != postfix ||
                prefixes.Length != (prefix is null ? 0 : 1) || prefix is not null && prefixes[0].PatchMethod != prefix)
                throw new InvalidOperationException($"Steam audio observer owner/handler shape drift at {type.FullName}.{name}.");
        }
    }
    internal static void InstallPatches(Harmony harmony)
    {
        HarmonyMethod Own(string name) => new(typeof(DomainSteamNativeObservation), name);
        foreach (var pair in new[] { ("MonsterPerformedMove", nameof(MoveAfter)), ("CreatureAttacked", nameof(AttackAfter)), ("DamageReceived", nameof(DamageAfter)) })
            harmony.Patch(AccessTools.Method(typeof(CombatHistory), pair.Item1), prefix: Own(nameof(HistoryBefore)), postfix: Own(pair.Item2));
        InstallAudioPatches(harmony);
        harmony.Patch(AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            [typeof(PlayerChoiceContext), typeof(IEnumerable<Creature>), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]), postfix: Own(nameof(DirectDamageAfter)));
        var damageEntry = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            [typeof(PlayerChoiceContext), typeof(IEnumerable<Creature>), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]);
        harmony.Patch(AccessTools.Method(damageEntry.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext"), transpiler: Own(nameof(DamageHistoryBranch)));
        var remove = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Remove), [typeof(PowerModel)]);
        var body = AccessTools.Method(remove.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        harmony.Patch(body, transpiler: Own(nameof(RemovalBody)));
    }
    internal object Snapshot() => new { changes = _changes.ToArray(), completedMoves = _moves.ToArray(), attacks = _attacks.ToArray(), damage = _damage.ToArray(),
        historyEvidence = HistorySnapshot(), stageEvents = _stageEvents.ToArray(), externalDamageResults = _externalDamageResults.ToArray(), afterRemovedStarted = RemovedStarted, afterRemovedCompleted = RemovedCompleted,
        initialAmbientRegistered = _initialLoop, finalAmbientRegistered = HasLoop(_node), stops = _stops.ToArray(),
        musicParameterCalls = _music.ToArray(), ambientParameterCalls = _ambient.ToArray(), audioScope = "native-loop-registration-and-parameter-calls-not-listening" };
    public void Dispose()
    {
        foreach (var (creature, hp, block, max) in _subscriptions)
        { creature.CurrentHpChanged -= hp; creature.BlockChanged -= block; creature.MaxHpChanged -= max; }
        _subscriptions.Clear(); _harmony.UnpatchAll(_harmony.Id);
        if (ReferenceEquals(Active, this)) Active = null;
    }
}
