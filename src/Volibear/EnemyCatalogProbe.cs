using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;

namespace Volibear;

/// <summary>
/// Native registered-source discovery, NOT enemy compatibility or action coverage.
/// Never rolls a move, evaluates a transition guard, mutates a monster or executes an action.
/// Only existing mutable monsters in the real bootstrap encounter expose live state evidence.
/// </summary>
public static class EnemyCatalogProbe
{
    private sealed record Origin(string kind, string sourceId, string member, int? ilOffset);
    private sealed class EncounterNode(EncounterModel model)
    {
        internal readonly EncounterModel Model = model;
        internal readonly List<Origin> Origins = [];
    }
    private sealed class Sources
    {
        internal readonly SortedDictionary<string, EncounterNode> Encounters = new(StringComparer.Ordinal);
        internal readonly List<object> Acts = [];
        internal readonly List<object> Events = [];
        internal string[] SharedEvents = [];
        internal string[] SharedAncients = [];
    }
    private static readonly Assembly Native = typeof(ModelDb).Assembly;
    private static readonly Dictionary<short, OpCode> OpCodesByValue = typeof(OpCodes)
        .GetFields(BindingFlags.Public | BindingFlags.Static).Where(f => f.FieldType == typeof(OpCode))
        .Select(f => (OpCode)f.GetValue(null)!).GroupBy(op => op.Value).ToDictionary(group => group.Key, group => group.First());
    private static bool _started;

    public static void Install() => CombatManager.Instance.TurnStarted += OnTurnStarted;

    /// <summary>Bootstrap foundation: exact native registered-source encounter ID only.</summary>
    public static EncounterModel ResolveEncounter(string exactId)
    {
        var sources = DiscoverSources();
        if (!sources.Encounters.TryGetValue(exactId, out var node) || node.Model.IsDebugEncounter)
            throw new InvalidOperationException("Encounter is not a non-debug registered-source encounter: " + exactId);
        return node.Model; // Canonical model, as required by the native bootstrap contract.
    }

    /// <summary>Read-only selector for a later action fixture, never a fake action executor.</summary>
    public static MoveState RequireNativeMove(Creature enemy, string exactMoveId)
    {
        if (enemy.CombatState is null || !ReferenceEquals(enemy.CombatState, CombatManager.Instance.DebugOnlyGetState()) ||
            enemy.Monster?.MoveStateMachine is not { } machine ||
            !machine.States.TryGetValue(exactMoveId, out var state) || state is not MoveState move)
            throw new InvalidOperationException("Requested move does not belong to this live native enemy instance.");
        return move;
    }

    private static bool IsNative(AbstractModel model) => model.GetType().Assembly == Native;
    private static string Id(AbstractModel model) => model.Id.ToString();
    private static string[] Ids<T>(IEnumerable<T> models) where T : AbstractModel =>
        models.Where(IsNative).Select(Id).Distinct().Order(StringComparer.Ordinal).ToArray();

    private static Sources DiscoverSources()
    {
        var sources = new Sources();
        var acts = ModelDb.Acts.Where(IsNative).OrderBy(Id, StringComparer.Ordinal).ToArray();
        var events = ModelDb.AllEvents.Cast<EventModel>().Concat(ModelDb.AllAncients)
            .Where(IsNative).DistinctBy(Id).OrderBy(Id, StringComparer.Ordinal).ToArray();
        sources.SharedEvents = Ids(ModelDb.AllSharedEvents);
        sources.SharedAncients = Ids(ModelDb.AllSharedAncients);
        var eventOrigins = events.ToDictionary(Id, _ => new List<string>(), StringComparer.Ordinal);
        foreach (var act in acts)
        {
            var encounters = act.AllEncounters.Where(IsNative).ToArray();
            var eventIds = Ids(act.AllEvents);
            var ancientIds = Ids(act.AllAncients);
            foreach (var id in eventIds) eventOrigins[id].Add(Id(act) + ".AllEvents");
            foreach (var id in ancientIds) eventOrigins[id].Add(Id(act) + ".AllAncients");
            sources.Acts.Add(new { id = Id(act), type = act.GetType().FullName,
                encounters = Ids(encounters), events = eventIds, ancients = ancientIds });
            foreach (var encounter in encounters)
                Add(sources, encounter, new Origin("act", Id(act), "ActModel.AllEncounters", null));
        }
        foreach (var id in sources.SharedEvents) eventOrigins[id].Add("ModelDb.AllSharedEvents");
        foreach (var id in sources.SharedAncients) eventOrigins[id].Add("ModelDb.AllSharedAncients");
        foreach (var model in events)
        {
            var references = new List<object>();
            var canonical = model.CanonicalEncounter;
            if (canonical is not null && IsNative(canonical))
            {
                var origin = new Origin("registered-event-canonical", Id(model), "EventModel.CanonicalEncounter", null);
                Add(sources, canonical, origin);
                references.Add(new { encounterId = Id(canonical), origin });
            }
            // This reads IL metadata only. The native event/async methods are NOT invoked.
            foreach (var type in SelfAndNested(model.GetType()))
            foreach (var method in DeclaredMethods(type))
            foreach (var (encounterType, offset, called) in EncounterReferences(method))
            {
                var encounter = ModelDb.GetById<EncounterModel>(ModelDb.GetId(encounterType));
                var member = $"{method.DeclaringType!.FullName}.{method.Name}@0x{method.MetadataToken:X8} -> {called}";
                var origin = new Origin("registered-event-il-reference", Id(model), member, offset);
                Add(sources, encounter, origin);
                references.Add(new { encounterId = Id(encounter), origin });
            }
            sources.Events.Add(new { id = Id(model), type = model.GetType().FullName,
                registrationSources = eventOrigins[Id(model)].Distinct().Order(StringComparer.Ordinal).ToArray(),
                references });
        }
        return sources;
    }

    private static void Add(Sources sources, EncounterModel encounter, Origin origin)
    {
        if (!sources.Encounters.TryGetValue(Id(encounter), out var node))
            sources.Encounters.Add(Id(encounter), node = new EncounterNode(encounter));
        if (!node.Origins.Contains(origin)) node.Origins.Add(origin);
    }

    private static IEnumerable<Type> SelfAndNested(Type root)
    {
        yield return root;
        foreach (var child in root.GetNestedTypes(BindingFlags.Public | BindingFlags.NonPublic))
        foreach (var descendant in SelfAndNested(child)) yield return descendant;
    }

    private static IEnumerable<MethodBase> DeclaredMethods(Type type) => type.GetMethods(
        BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
        .Cast<MethodBase>().Concat(type.GetConstructors(BindingFlags.Instance | BindingFlags.Static |
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly));

    private static IEnumerable<(Type Type, int Offset, string Called)> EncounterReferences(MethodBase method)
    {
        var bytes = method.GetMethodBody()?.GetILAsByteArray();
        if (bytes is null) yield break;
        for (var index = 0; index < bytes.Length;)
        {
            var offset = index;
            short code = bytes[index++] == 0xFE ? unchecked((short)(0xFE00 | bytes[index++])) : bytes[index - 1];
            if (!OpCodesByValue.TryGetValue(code, out var op)) throw new InvalidOperationException("Unknown native IL opcode.");
            if (op.OperandType == OperandType.InlineMethod)
            {
                var token = BitConverter.ToInt32(bytes, index);
                var called = method.Module.ResolveMethod(token, method.DeclaringType?.GetGenericArguments(),
                    method.IsGenericMethod ? method.GetGenericArguments() : null);
                if (called is MethodInfo { IsGenericMethod: true } generic)
                    foreach (var argument in generic.GetGenericArguments())
                        if (!argument.ContainsGenericParameters && argument.Assembly == Native &&
                            argument.IsSubclassOf(typeof(EncounterModel)))
                            yield return (argument, offset, generic.DeclaringType!.FullName + "." + generic.Name);
            }
            index += op.OperandType switch
            {
                OperandType.InlineNone => 0,
                OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar => 1,
                OperandType.InlineVar => 2,
                OperandType.InlineI8 or OperandType.InlineR => 8,
                OperandType.InlineSwitch => checked(4 + 4 * BitConverter.ToInt32(bytes, index)),
                OperandType.InlineBrTarget or OperandType.InlineField or OperandType.InlineI or OperandType.InlineMethod or
                    OperandType.InlineSig or OperandType.InlineString or OperandType.InlineTok or OperandType.InlineType or
                    OperandType.ShortInlineR => 4,
                _ => throw new InvalidOperationException("Unsupported native IL operand: " + op.OperandType)
            };
            if (index > bytes.Length) throw new InvalidOperationException("Native IL operand exceeds method body.");
        }
    }

    private static object DescribeCreature(Creature creature)
    {
        var model = creature.Monster!;
        var machine = model.MoveStateMachine;
        string? ReadState(string field) => machine is null ? null :
            (typeof(MonsterMoveStateMachine).GetField(field, BindingFlags.Instance | BindingFlags.NonPublic)
                ?.GetValue(machine) as MonsterState)?.Id;
        var states = machine?.States.OrderBy(pair => pair.Key, StringComparer.Ordinal).Select(pair =>
        {
            var move = pair.Value as MoveState;
            var action = move is null ? null : typeof(MoveState).GetField("_onPerform",
                BindingFlags.Instance | BindingFlags.NonPublic)?.GetValue(move) as Delegate;
            return new { id = pair.Key, type = pair.Value.GetType().FullName, isMove = pair.Value.IsMove,
                configuredFollowUp = move?.FollowUpState?.Id ?? move?.FollowUpStateId,
                mustPerformOnce = move?.MustPerformOnceBeforeTransitioning,
                actionMethod = action is null ? null : action.Method.DeclaringType?.FullName + "." + action.Method.Name,
                intentTypes = move?.Intents.Select(intent => intent.GetType().FullName).ToArray(),
                guard = "UNKNOWN_NOT_EVALUATED", executionStatus = "NOT_RUN" };
        }).ToArray();
        return new { combatId = creature.CombatId, modelId = Id(model), type = model.GetType().FullName,
            hp = creature.CurrentHp, block = creature.Block, initialState = ReadState("_initialState"),
            currentState = ReadState("_currentState"), nextMove = model.NextMove?.Id,
            states, stateDiscovery = machine is null ? "UNKNOWN" : "OBSERVED_NATIVE_INSTANCE",
            powers = creature.Powers.Select(p => new { id = Id(p), amount = p.Amount }).ToArray(),
            executionStatus = "NOT_RUN", transitionsComplete = false, branchesComplete = false };
    }

    private static void OnTurnStarted(CombatState state)
    {
        if (_started) return;
        _started = true;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var directory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ARTIFACT_DIR");
            if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(directory) ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Native catalog requires isolated artifact directory/token and TestMode=false.");
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No native release metadata.");
            if (release.Version != "v0.107.1" || release.Commit != "59260271")
                throw new InvalidOperationException("Enemy catalog target version mismatch.");
            var requested = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ENCOUNTER_ID");
            if (requested is not null && requested != state.Encounter?.Id.ToString())
                throw new InvalidOperationException("Requested encounter was not actually bootstrapped.");
            var sources = DiscoverSources();
            var formal = sources.Encounters.Values.Where(node => !node.Model.IsDebugEncounter).ToArray();
            var monsters = formal.SelectMany(node => node.Model.AllPossibleMonsters).Where(IsNative)
                .DistinctBy(Id).OrderBy(Id, StringComparer.Ordinal).ToArray();
            var live = state.Enemies.Where(enemy => enemy.Monster is not null).ToArray();
            var monsterIds = monsters.Select(Id).ToHashSet(StringComparer.Ordinal);
            var nativeTypes = Native.GetTypes().Where(type => !type.IsAbstract).ToArray();
            var baseLib = typeof(BaseLib.Abstracts.CustomPowerModel).Assembly;
            var manifest = new
            {
                schema = 1, token, scenario = "enemy-catalog", testMode = false,
                acceptance = "native-source-discovery-only", executionStatus = "NOT_RUN",
                gameVersion = release.Version, gameCommit = release.Commit,
                gameAssemblyMvid = Native.ManifestModule.ModuleVersionId,
                modAssemblyMvid = typeof(EnemyCatalogProbe).Assembly.ManifestModule.ModuleVersionId,
                baseLibAssemblyVersion = baseLib.GetName().Version?.ToString(),
                baseLibInformationalVersion = baseLib.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion,
                godotVersion = Engine.GetVersionInfo()["string"].ToString(),
                seed = state.RunState.Rng.StringSeed, numericSeed = state.RunState.Rng.Seed,
                ascension = state.RunState.AscensionLevel, act = Id(state.RunState.Act), actIndex = state.RunState.CurrentActIndex,
                fixtureEncounter = state.Encounter?.Id.ToString(), round = state.RoundNumber,
                sourcePolicy = "native-registered-acts-plus-registered-event-encounter-references",
                discoveryLimitations = new[] { "IL references do not prove every runtime guard reachable",
                    "indirect or reflection-selected encounter helpers require source review",
                    "live state observations are fixture-specific, not transition or branch execution" },
                acts = sources.Acts, events = sources.Events,
                sharedEventIds = sources.SharedEvents, sharedAncientIds = sources.SharedAncients,
                encounters = sources.Encounters.Values.Select(node => new
                {
                    id = Id(node.Model), type = node.Model.GetType().FullName, registered = ModelDb.Contains(node.Model.GetType()),
                    isDebug = node.Model.IsDebugEncounter, roomType = node.Model.RoomType.ToString(),
                    origins = node.Origins, monsterIds = Ids(node.Model.AllPossibleMonsters),
                    executionStatus = "NOT_RUN", included = !node.Model.IsDebugEncounter,
                    bootstrapMode = node.Origins.Any(o => o.kind == "act") ? "ACT_ENCOUNTER" : "EVENT_SETUP_REQUIRED",
                    exclusionReason = node.Model.IsDebugEncounter ? "native-IsDebugEncounter=true" : null
                }).ToArray(),
                monsters = monsters.Select(model => new
                {
                    id = Id(model), type = model.GetType().FullName, registered = ModelDb.Contains(model.GetType()),
                    encounterIds = formal.Where(node => node.Model.AllPossibleMonsters.Any(m => m.Id == model.Id))
                        .Select(node => Id(node.Model)).Order(StringComparer.Ordinal).ToArray(),
                    liveInstanceIds = live.Where(enemy => enemy.Monster!.Id == model.Id).Select(enemy => enemy.CombatId).ToArray(),
                    stateDiscovery = live.Any(enemy => enemy.Monster!.Id == model.Id) ? "OBSERVED_NATIVE_INSTANCE" : "UNKNOWN",
                    executionStatus = "NOT_RUN", effectBranches = "UNKNOWN", passiveCoverage = "NOT_RUN"
                }).ToArray(),
                liveInstances = live.Select(DescribeCreature).ToArray(),
                unreachedCandidates = nativeTypes.Where(type => type.IsSubclassOf(typeof(MonsterModel)) ||
                    type.IsSubclassOf(typeof(EncounterModel))).Where(type => type.IsSubclassOf(typeof(MonsterModel))
                        ? !monsterIds.Contains(ModelDb.GetId(type).ToString())
                        : !sources.Encounters.ContainsKey(ModelDb.GetId(type).ToString()))
                    .OrderBy(type => type.FullName, StringComparer.Ordinal).Select(type => new
                    {
                        id = ModelDb.GetId(type).ToString(), type = type.FullName,
                        category = type.IsSubclassOf(typeof(MonsterModel)) ? "monster" : "encounter",
                        registered = ModelDb.Contains(type), status = "REACHABILITY_UNRESOLVED",
                        reason = "not-reached-by-enumerated-native-registration-sources;not-an-automatic-exemption"
                    }).ToArray(),
                counts = new { acts = sources.Acts.Count, events = sources.Events.Count,
                    actEncounters = formal.Count(node => node.Origins.Any(o => o.kind == "act")),
                    eventOnlyEncounters = formal.Count(node => node.Origins.All(o => o.kind != "act")),
                    encounters = formal.Length, monsters = monsters.Length, liveInstances = live.Length,
                    executedActions = 0, verifiedTransitions = 0, verifiedBranches = 0 }
            };
            var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }) + "\n");
            Directory.CreateDirectory(directory);
            File.WriteAllBytes(Path.Combine(directory, "enemy-catalog.json"), bytes);
            GD.Print("[Volibear] ENEMY_CATALOG_RESULT " + JsonSerializer.Serialize(new
            {
                token, scenario = "enemy-catalog", acceptance = "native-source-discovery-only", executionStatus = "NOT_RUN",
                manifest = "enemy-catalog.json", sha256 = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                bytes = bytes.Length, counts = manifest.counts, gameVersion = release.Version, gameCommit = release.Commit
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] ENEMY_CATALOG_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { CombatManager.Instance.TurnStarted -= OnTurnStarted; }
    }
}
