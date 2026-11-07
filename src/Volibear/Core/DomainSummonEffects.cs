using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;

namespace Volibear.Core;

/// <summary>Exact native summon batches. Guards precede creation, not the post-creation Add await.
/// Original attack, committed child initialization, death cleanup and move advancement stay native.</summary>
public static partial class DomainSummonEffects
{
    private const string HarmonyId = "Volibear.DomainSummonEffects";
    private static readonly object InstallLock = new();
    private static bool _installed;
    private static long _generation;
    private static ConditionalWeakTable<InfestedPower, DeathAttempt> Attempts = new();
    private static readonly SummonLifetime<Batch> Tasks = new();
    private static readonly AsyncLocal<SummonTicket<SummonLifetime<Batch>.Binding>?> Pending = new();
    private static readonly Dictionary<MethodBase, int> Bodies = new();
    private static Func<Fabricator, Task>? Aggro, Defensive;

    private class Batch(Creature owner, ICombatState combat, bool entryDomain)
    {
        internal readonly Creature Owner = owner;
        internal readonly ICombatState Combat = combat;
        internal readonly long Generation = _generation;
        internal readonly DeathDecision Decision = new(entryDomain);
        internal bool Closed;
    }
    private sealed class DeathAttempt(Creature owner, ICombatState combat, bool entryDomain) : Batch(owner, combat, entryDomain);
    private sealed record Frame(SummonLifetime<Batch>.Binding? Binding, Task Native, long Generation, object? Subject = null);

    public static void Install()
    {
        lock (InstallLock)
        {
            if (_installed) return;
            var harmony = new Harmony(HarmonyId);
            try
            {
                InstallPatches(harmony);
                CombatManager.Instance.CombatSetUp += _ => Reset();
                CombatManager.Instance.CombatEnded += _ => Reset();
                _installed = true;
            }
            catch { harmony.UnpatchAll(HarmonyId); throw; }
        }
    }
    public static void Reset()
    {
        Interlocked.Increment(ref _generation);
        // Retain weak actual-box tombstones; death capture/veto reset semantics are unchanged.
        Attempts = new(); Pending.Value = null;
    }
    // Isolated tests emit real native bodies without invoking game singletons or installing combat listeners.
    internal static void InstallPatches(Harmony harmony)
    {
        Prepare();
        foreach (var entry in Bodies)
        {
            try { harmony.Patch(entry.Key, transpiler: new HarmonyMethod(typeof(DomainSummonEffects), nameof(Rewrite))); }
            catch (Exception error)
            {
                throw new InvalidOperationException("Summon transpiler failed for " +
                    entry.Key.DeclaringType?.Name + "." + entry.Key.Name + " (kind " + entry.Value + ")", error);
            }
        }
        harmony.Patch(Required(typeof(InfestedPower), nameof(InfestedPower.ShouldStopCombatFromEnding), typeof(bool), []),
            postfix: new HarmonyMethod(typeof(DomainSummonEffects), nameof(NeutralizeCancelledVeto)));
        harmony.Patch(Required(typeof(CombatManager), nameof(CombatManager.Reset), typeof(void), [typeof(bool)]),
            prefix: new HarmonyMethod(typeof(DomainSummonEffects), nameof(Reset)));
    }
    private static void Prepare()
    {
        Bodies.Clear();
        void Add(Type type, string method, int kind, Type[] args) => Bodies.Add(MoveNext(Required(type, method, typeof(Task), args)), kind);
        Add(typeof(Fabricator), "SpawnBot", 0, [typeof(IEnumerable<MonsterModel>)]);
        Add(typeof(Ovicopter), "LayEggsMove", 1, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(InfestedPower), nameof(InfestedPower.AfterDeath), 2, [typeof(PlayerChoiceContext), typeof(Creature), typeof(bool), typeof(float)]);
        Add(typeof(CreatureCmd), "KillWithoutCheckingWinCondition", 3, [typeof(Creature), typeof(bool), typeof(int)]);
        Add(typeof(Fabricator), "FabricateMove", 4, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(Fabricator), "FabricatingStrikeMove", 5, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(LivingFog), "BloatMove", 6, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(TwoTailedRat), "CallForBackup", 7, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(Fogmog), "IllusionMove", 8, [typeof(IReadOnlyList<Creature>)]);
        Add(typeof(TheObscura), "IllusionMove", 9, [typeof(IReadOnlyList<Creature>)]);
        Aggro = Required(typeof(Fabricator), "SpawnAggroBot", typeof(Task), []).CreateDelegate<Func<Fabricator, Task>>();
        Defensive = Required(typeof(Fabricator), "SpawnDefensiveBot", typeof(Task), []).CreateDelegate<Func<Fabricator, Task>>();
        ValidateCreationTiming();
        ValidateForwardHelpers();
    }
    private static bool DomainAtDeathEntry(ICombatState combat)
    {
        var manager = CombatManager.Instance;
        return manager.IsInProgress && !manager.IsAboutToLose &&
            ReferenceEquals(combat, manager.DebugOnlyGetState()) && combat.Players.Any(player =>
                player.Creature is { IsPlayer: true, IsAlive: true } owner &&
                ReferenceEquals(owner.CombatState, combat) && combat.ContainsCreature(owner) &&
                owner.GetPowerAmount<DomainPower>() > 0);
    }
    private static DeathAttempt? CaptureDeath(Creature owner)
    {
        var combat = owner.CombatState;
        if (combat is null || !owner.IsEnemy || owner.IsPlayer || !combat.ContainsCreature(owner) ||
            !ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) || !CombatManager.Instance.IsInProgress) return null;
        var powers = owner.Powers.OfType<InfestedPower>().ToArray();
        if (powers.Length == 0) return null;
        var attempt = new DeathAttempt(owner, combat, DomainAtDeathEntry(combat));
        foreach (var power in powers) { Attempts.Remove(power); Attempts.Add(power, attempt); }
        return attempt;
    }
    private static DeathAttempt? MatchingEvent(InfestedPower power, Creature target)
    {
        if (!Attempts.TryGetValue(power, out var attempt) || attempt.Generation != _generation ||
            !ReferenceEquals(power.Owner, target) || !ReferenceEquals(attempt.Owner, target) ||
            !target.IsEnemy || target.IsPlayer || target.IsAlive ||
            !ReferenceEquals(attempt.Combat, CombatManager.Instance.DebugOnlyGetState()) ||
            (target.CombatState is not null && !ReferenceEquals(target.CombatState, attempt.Combat))) return null;
        return attempt;
    }
    private static void NeutralizeCancelledVeto(InfestedPower __instance, ref bool __result)
    {
        // Never discover/consume a new cancellation from an ending query while the source is still awaiting.
        if (MatchingEvent(__instance, __instance.Owner)?.Decision.Cancelled == true) __result = false;
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static Frame Enter(Task native, int state, object source, int kind, Creature? target, bool prevented)
    {
        // Native initial entry creates an explicit local, never a returned/cached Task identity.
        var binding = state == -1 ? null : Tasks.Find(native, source, kind);
        if (state == -1)
        {
            Batch? batch = null; bool close = true;
            if (kind == 3) batch = CaptureDeath((Creature)source);
            else if (kind == 2)
            {
                if (!prevented && target is not null) batch = MatchingEvent((InfestedPower)source, target);
                if (batch is not null && !CanAttachDeathBirth(batch.Closed, batch.Decision.Cancelled)) batch = null;
                close = false;
            }
            else if (kind == 0 && Pending.Value is { } ticket)
            {
                // Exact handoff precedes ANY owner/world dereference, including for an old epoch.
                // A mismatched/consumed ticket is a barrier, not permission to mint a current batch.
                if (ticket.TryClaim(kind, source, out var parent))
                {
                    if (parent!.Closed || parent.Payload is null) binding = Tasks.Retired(parent.Epoch, source, kind);
                    else batch = parent.Payload;
                }
                close = false;
            }
            else
            {
                var owner = ((MonsterModel)source).Creature;
                if (owner.IsEnemy && !owner.IsPlayer && owner.CombatState is { } combat && combat.ContainsCreature(owner) &&
                    ReferenceEquals(combat, CombatManager.Instance.DebugOnlyGetState()) && CombatManager.Instance.IsInProgress)
                    batch = new Batch(owner, combat, false); // Existing A-scope fresh-source policy; no Outer ownership claim.
            }
            if (batch is not null) binding = Tasks.Begin(batch, batch.Generation, close, source, kind);
        }
        return new Frame(binding, native, _generation, source);
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void Leave(Frame frame, ref AsyncTaskMethodBuilder builder, int state)
    { Tasks.VerifyReturn(frame.Binding, ref builder, state); }
    private static ISummonRegistration? Registration(Frame frame) => frame.Binding;
    private static void Close(Frame frame) => Tasks.Close(frame.Binding, static batch => { batch.Closed = true; batch.Decision.Close(); });
    private static bool RetiredGate(Frame frame, string boundary) => frame.Binding is { } binding &&
        (binding.Closed || binding.Epoch != Volatile.Read(ref _generation) || binding.Payload?.Closed == true);
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static bool CancelAtGate(Frame frame, string boundary)
    {
        if (RetiredGate(frame, boundary)) return true;
        var batch = frame.Binding?.Payload;
        var ownership = ClassifyGate(batch is not null, frame.Generation, batch?.Generation ?? 0, _generation);
        if (ownership == GateOwnership.Unknown) return false;
        if (ownership == GateOwnership.StaleKnown) return true;
        // Already consumed cancellation is sticky even if Domain expires. Nothing here mutates an existing child.
        bool cancelled = batch!.Decision.AtBoundary(false, batch is DeathAttempt ? DomainAtDeathEntry(batch.Combat) : DomainEnemyEffects.ActiveFor(batch.Owner));
        if (cancelled) Volibear.Presentation.PowerPresentationDomain.Once(batch, batch.Owner, frame.Subject as AbstractModel, sourceCombat: batch.Combat);
        return cancelled;
    }
    private static Task ForwardAggro(Fabricator source, Frame frame) => Forward(source, frame, Aggro!);
    private static Task ForwardDefensive(Fabricator source, Frame frame) => Forward(source, frame, Defensive!);
    private static Task Forward(Fabricator source, Frame frame, Func<Fabricator, Task> native)
    {
        var previous = Pending.Value;
        // Even an unknown/mismatched scope installs a barrier; never borrow an ancestor's ticket.
        Pending.Value = new SummonTicket<SummonLifetime<Batch>.Binding>(ReferenceEquals(frame.Subject, source) ? frame.Binding : null, 0, source);
        try { return native(source); }
        finally { Pending.Value = previous; }
    }

    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        int kind = Bodies[__originalMethod];
        var sm = __originalMethod.DeclaringType!;
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        static MethodInfo[] Registrations(IEnumerable<CodeInstruction> stream) => stream.Where(i=>i.operand is MethodInfo m&&m.DeclaringType==typeof(AsyncTaskMethodBuilder)&&m.Name.StartsWith("Await",StringComparison.Ordinal)).Select(i=>(MethodInfo)i.operand).ToArray();
        var expectedRegistrations=Registrations(PatchProcessor.GetOriginalInstructions(__originalMethod));
        var inputRegistrations=Registrations(code);
        Require(expectedRegistrations.Length>0&&inputRegistrations.Length==expectedRegistrations.Length&&expectedRegistrations.All(m=>inputRegistrations.Count(x=>x==m)==expectedRegistrations.Count(x=>x==m)),"Summon original registration count/type multiset changed before emission");
        var builder = Field(sm, "<>t__builder", typeof(AsyncTaskMethodBuilder));
        var state = Field(sm, "<>1__state", typeof(int));
        var sourceType = kind switch
        {
            1 => typeof(Ovicopter), 2 => typeof(InfestedPower), 3 => typeof(Creature),
            6 => typeof(LivingFog), 7 => typeof(TwoTailedRat), 8 => typeof(Fogmog),
            9 => typeof(TheObscura), _ => typeof(Fabricator)
        };
        var source = Field(sm, kind == 3 ? "creature" : "<>4__this", sourceType);
        var frame = generator.DeclareLocal(typeof(Frame));
        var getTask = AccessTools.PropertyGetter(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.Task));
        Unique(code, Required(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetResult), typeof(void), []));
        Unique(code, Required(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetException), typeof(void), [typeof(Exception)]));
        if (kind == 3)
        {
            Require(code.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(MegaCrit.Sts2.Core.Hooks.Hook) && m.Name == "AfterDeath") == 2 &&
                code.Count(i => i.operand is MethodInfo m && m.DeclaringType == typeof(MegaCrit.Sts2.Core.Hooks.Hook) && m.Name == "ShouldCreatureBeRemovedFromCombatAfterDeath") == 1,
                "Native Kill death/removal anchors changed");
        }
        if (kind <= 2)
        {
            int finish = Unique(code, Required(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetResult), typeof(void), []));
            int end = code.FindLastIndex(i => i.blocks.Any(b => b.blockType == ExceptionBlockType.EndExceptionBlock));
            Require(end >= 0 && end + 3 < finish && code[end + 1].opcode == OpCodes.Ldarg_0 && code[end + 2].LoadsConstant(-2) &&
                code[end + 3].opcode == OpCodes.Stfld && Equals(code[end + 3].operand, state), "Native successful summon epilogue changed");
            Require(code.Count(i => i.blocks.Any(b => b.blockType == ExceptionBlockType.BeginFinallyBlock)) == 0, "New summon finally requires explicit cleanup design");
            var complete = generator.DefineLabel(); code[end + 1].labels.Add(complete);
            var guards = new List<(int Index, string Boundary)>();
            int add = UniqueAdd(code, kind == 1);
            if (kind is 1 or 2)
            {
                var indexField=Field(sm,"<i>5__2",typeof(int));
                var loop=code.Select((i,n)=>(i,n)).Where(x => x.n>0 && x.n+1<code.Count && x.i.LoadsConstant(kind==1?3:4) &&
                    code[x.n-1].opcode==OpCodes.Ldfld && Equals(code[x.n-1].operand,indexField) &&
                    (code[x.n+1].opcode==OpCodes.Blt || code[x.n+1].opcode==OpCodes.Blt_S)).ToArray();
                Require(loop.Length==1 && loop[0].n>add,"Native summon loop bound changed");
            }
            if (kind < 2)
            {
                int result = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(TaskAwaiter<Creature>) && m.Name == "GetResult").n;
                int minion = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(PowerCmd) && m.Name == nameof(PowerCmd.Apply) &&
                    m.IsGenericMethod && m.GetGenericArguments().SequenceEqual([typeof(MinionPower)]) && m.GetParameters()[1].ParameterType == typeof(Creature)).n;
                Require(add < result && result < minion && code[result + 1].IsStloc(), "Committed child result/Minion continuation changed");
            }
            if (kind == 0)
            {
                var options = Field(sm, "options", typeof(IEnumerable<MonsterModel>));
                int load = code.Select((i,n)=>(i,n)).Single(x => x.i.opcode == OpCodes.Ldfld && Equals(x.i.operand, options)).n;
                int write = code.FindIndex(i => i.opcode == OpCodes.Stfld && i.operand is FieldInfo f && f.Name == "_lastSpawned" && f.DeclaringType == typeof(Fabricator));
                Require(code[load-1].opcode == OpCodes.Ldarg_0 && load < write && write < add, "Fabricator selection/creation order changed");
                Require(!code.Skip(load).Take(add-load).Any(AwaitInstruction), "New await before Fabricator creation");
                int combatRead=code.FindIndex(i=>i.Calls(AccessTools.PropertyGetter(typeof(MonsterModel),nameof(MonsterModel.CombatState))));
                Require(combatRead>0&&code[combatRead-1].opcode==OpCodes.Ldloc_1&&combatRead<load,"Fabricator pre-combat stack drift");
                guards.Add((combatRead-1,"Retired.SpawnBot.pre-combat"));
                guards.Add((load-1,"SpawnBot.entry-pre-selection"));
            }
            else if (kind == 1)
            {
                int sfx = code.FindIndex(i => i.opcode == OpCodes.Ldstr && Equals(i.operand,"event:/sfx/enemy/enemy_attacks/egg_layer/egg_layer_lay"));
                Require(sfx >= 0 && code[add-3].opcode == OpCodes.Ldloc_1 && code[add-2].operand is MethodInfo getter &&
                    getter == AccessTools.PropertyGetter(typeof(MonsterModel), nameof(MonsterModel.CombatState)) && code[add-1].opcode == OpCodes.Ldloc_3 &&
                    __originalMethod.GetMethodBody()!.LocalVariables[3].LocalType == typeof(string), "Egg exact pre-creation stack changed");
                int combatRead=code.FindIndex(i=>i.Calls(AccessTools.PropertyGetter(typeof(MonsterModel),nameof(MonsterModel.CombatState))));
                Require(combatRead>0&&code[combatRead-1].opcode==OpCodes.Ldloc_1&&combatRead<add,"Ovicopter pre-slot stack drift");
                guards.Add((combatRead-1,"Retired.LayEggs.pre-slot"));
                guards.Add((sfx,"LayEggs.entry")); guards.Add((add-3,"LayEggs.pre-create"));
            }
            else
            {
                var wait = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(Cmd) && m.Name == nameof(Cmd.CustomScaledWait)).n;
                var length = Field(sm,"deathAnimLength",typeof(float));
                int first = code.FindIndex(i => i.opcode == OpCodes.Ldfld && Equals(i.operand,length));
                int beforeMusic = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(MegaCrit.Sts2.Core.TestSupport.TestMode) && m.Name == "get_IsOff").n;
                int model = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(ModelDb) && m.Name == nameof(ModelDb.Monster) && m.IsGenericMethod && m.GetGenericArguments().SequenceEqual([typeof(Wriggler)])).n;
                Require(first > 0 && code[first-1].opcode == OpCodes.Ldarg_0 && first < wait && wait < beforeMusic && beforeMusic < model && model < add &&
                    code[beforeMusic-1].operand is MethodInfo result && result.Name == "GetResult" && result.DeclaringType == typeof(TaskAwaiter), "Infested wait/music/creation boundaries changed");
                int stunned = Unique(code, AccessTools.PropertySetter(typeof(Wriggler), nameof(Wriggler.StartStunned)));
                Require(model < stunned && stunned < add && code[stunned - 1].LoadsConstant(1), "Native Wriggler StartStunned initializer changed");
                Require(!code.Skip(model).Take(add-model).Any(AwaitInstruction), "New await before Wriggler creation");
                guards.Add((first-1,"Infested.confirmed-entry")); guards.Add((beforeMusic,"Infested.post-wait-pre-music")); guards.Add((model,"Infested.pre-create"));
            }
            foreach (var (index,boundary) in guards.OrderByDescending(g=>g.Index))
            {
                var allow = generator.DefineLabel();
                var guard = new List<CodeInstruction> { new(OpCodes.Ldloc,frame), new(OpCodes.Ldstr,boundary), new(OpCodes.Call,Handler(boundary.StartsWith("Retired.",StringComparison.Ordinal)?nameof(RetiredGate):nameof(CancelAtGate))), new(OpCodes.Brfalse,allow), new(OpCodes.Leave,complete) };
                Transfer(code[index],guard[0]); code[index].labels.Add(allow); code.InsertRange(index,guard);
            }
        }
        else if (kind >= 6)
        {
            RewriteAdditionalBirth(code, frame, kind);
        }
        else if (kind >= 4)
        {
            if (kind == 5)
            {
                int attack = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(MegaCrit.Sts2.Core.Commands.Builders.AttackCommand) && m.Name == "Execute").n;
                int result = code.Select((i,n)=>(i,n)).Single(x => x.i.operand is MethodInfo m && m.DeclaringType == typeof(TaskAwaiter<MegaCrit.Sts2.Core.Commands.Builders.AttackCommand>) && m.Name == "GetResult").n;
                Require(attack < result && code[result+1].opcode == OpCodes.Pop && result < Unique(code,Required(typeof(Fabricator),"SpawnAggroBot",typeof(Task),[])), "Mixed move actual attack/await/continuation changed");
            }
            foreach (var (method,wrapper) in (kind == 4 ? new[]{("SpawnDefensiveBot",nameof(ForwardDefensive)),("SpawnAggroBot",nameof(ForwardAggro))} : new[]{("SpawnAggroBot",nameof(ForwardAggro))}))
            {
                int index = Unique(code,Required(typeof(Fabricator),method,typeof(Task),[]));
                var load = new CodeInstruction(OpCodes.Ldloc,frame); Transfer(code[index],load); code.Insert(index,load);
                code[index+1].opcode=OpCodes.Call; code[index+1].operand=Handler(wrapper);
            }
        }
        // Kill adds only its own lifecycle/registration. Revival dispatch/removal/cleanup stays untouched.
        int registrations=0;
        for(int index=code.Count-1;index>=0;index--)
        {
            if(code[index].operand is not MethodInfo call||call.DeclaringType!=typeof(AsyncTaskMethodBuilder)||!call.Name.StartsWith("Await",StringComparison.Ordinal))continue;
            Require(call.Name=="AwaitUnsafeOnCompleted"&&call.IsGenericMethod,"Native Summon await registration drift");
            var args=call.GetGenericArguments();
            Require(args.Length==2&&args[1]==sm&&(args[0]==typeof(TaskAwaiter)||(args[0].IsGenericType&&args[0].GetGenericTypeDefinition()==typeof(TaskAwaiter<>))),"Summon exact awaiter/machine drift");
            var load=new CodeInstruction(OpCodes.Ldloc,frame);Transfer(code[index],load);
            code.InsertRange(index,new[]{load,new CodeInstruction(OpCodes.Call,Handler(nameof(Registration)))});
            code[index+2].opcode=OpCodes.Call;code[index+2].operand=typeof(SummonRegistration).GetMethod(nameof(SummonRegistration.Await),BindingFlags.Static|BindingFlags.NonPublic)!.MakeGenericMethod(args);registrations++;
        }
        Require(registrations==expectedRegistrations.Length,"Summon registration anchors missing or already rewritten");
        var output = new List<CodeInstruction> { new(OpCodes.Ldarg_0),new(OpCodes.Ldflda,builder),new(OpCodes.Call,getTask),new(OpCodes.Ldarg_0),new(OpCodes.Ldfld,state),new(OpCodes.Ldarg_0),new(OpCodes.Ldfld,source),new(OpCodes.Ldc_I4,kind) };
        if (kind==2) output.AddRange([new(OpCodes.Ldarg_0),new(OpCodes.Ldfld,Field(sm,"target",typeof(Creature))),new(OpCodes.Ldarg_0),new(OpCodes.Ldfld,Field(sm,"wasRemovalPrevented",typeof(bool)))]);
        else output.AddRange([new(OpCodes.Ldnull),new(OpCodes.Ldc_I4_0)]);
        output.AddRange([new(OpCodes.Call,Handler(nameof(Enter))),new(OpCodes.Stloc,frame)]);
        int returns=0;
        foreach(var instruction in code)
        {
            if(instruction.opcode==OpCodes.Ret)
            {
                var load=new CodeInstruction(OpCodes.Ldloc,frame); Transfer(instruction,load);
                output.AddRange([load,new(OpCodes.Ldarg_0),new(OpCodes.Ldflda,builder),new(OpCodes.Ldarg_0),new(OpCodes.Ldfld,state),new(OpCodes.Call,Handler(nameof(Leave)))]); returns++;
            }
            if(instruction.operand is MethodInfo signal&&signal.DeclaringType==typeof(AsyncTaskMethodBuilder)&&signal.Name is "SetResult" or "SetException")
            {
                var load=new CodeInstruction(OpCodes.Ldloc,frame);Transfer(instruction,load);output.Add(load);output.Add(new(OpCodes.Call,Handler(nameof(Close))));
            }
            output.Add(instruction);
        }
        Require(returns==1,"Native async return shape changed"); return output;
    }
    private static void ValidateForwardHelpers()
    {
        var spawn=Required(typeof(Fabricator),"SpawnBot",typeof(Task),[typeof(IEnumerable<MonsterModel>)]);
        foreach(var (name,fieldName) in new[]{("SpawnAggroBot","aggroSpawns"),("SpawnDefensiveBot","defenseSpawns")})
        {
            var machine=MoveNext(Required(typeof(Fabricator),name,typeof(Task),[]));
            var field=typeof(Fabricator).GetField(fieldName,BindingFlags.Public|BindingFlags.Static)!;
            ValidateForwardHelper(PatchProcessor.GetOriginalInstructions(machine).ToList(),machine,spawn,field);
        }
    }
    private static void ValidateForwardHelper(List<CodeInstruction> code,MethodBase machine,MethodInfo spawn,FieldInfo options)
    {
        int at=Unique(code,spawn);
        Require(at>=2&&code[at-2].opcode==OpCodes.Ldloc_1&&code[at-1].opcode==OpCodes.Ldsfld&&Equals(code[at-1].operand,options)&&
            machine.GetMethodBody()!.LocalVariables[1].LocalType==typeof(Fabricator),"Exact Fabricator helper field-load/SpawnBot call drift");
        Require(!code.Take(at).Any(i=>i.opcode==OpCodes.Call||i.opcode==OpCodes.Callvirt||i.opcode==OpCodes.Calli||i.opcode==OpCodes.Newobj),"New helper pre-child call may dereference retired world");
        Require(!code.Take(at).Any(i=>i.operand is FieldInfo f&&f.DeclaringType!=machine.DeclaringType&&!Equals(f,options)),"New helper pre-child field dependency");
    }
    private static void ValidateCreationTiming()
    {
        foreach(var method in typeof(CreatureCmd).GetMethods(BindingFlags.Public|BindingFlags.Static).Where(m=>m.Name==nameof(CreatureCmd.Add) && m.ReturnType==typeof(Task<Creature>) || m.Name==nameof(CreatureCmd.Add) && m.IsGenericMethodDefinition))
        {
            var native=method.IsGenericMethodDefinition?method.MakeGenericMethod(typeof(ToughEgg)):method;
            var code=PatchProcessor.GetOriginalInstructions(MoveNext(native)).ToList();
            int create=code.Select((i,n)=>(i,n)).Single(x=>x.i.operand is MethodInfo m && m.Name==nameof(ICombatState.CreateCreature)).n;
            int add=code.Select((i,n)=>(i,n)).Single(x=>x.i.Calls(Required(typeof(CreatureCmd),nameof(CreatureCmd.Add),typeof(Task),[typeof(Creature)]))).n;
            Require(create<add && !code.Take(add).Any(AwaitInstruction),"Native Create/Add gained a precommit await");
        }
        var body=PatchProcessor.GetOriginalInstructions(MoveNext(Required(typeof(CreatureCmd),nameof(CreatureCmd.Add),typeof(Task),[typeof(Creature)]))).ToList();
        int attach=body.Select((i,n)=>(i,n)).Single(x=>x.i.operand is MethodInfo m && m.DeclaringType==typeof(ICombatState) && m.Name==nameof(ICombatState.AddCreature)).n;
        int post=body.Select((i,n)=>(i,n)).Single(x=>x.i.operand is MethodInfo m && m.DeclaringType==typeof(CombatManager) && m.Name==nameof(CombatManager.AfterCreatureAdded)).n;
        Require(attach<post && !body.Take(post).Any(AwaitInstruction),"Native creature attachment gained a precommit await");
    }
    private static bool AwaitInstruction(CodeInstruction i) => i.operand is MethodInfo m && m.Name is "AwaitUnsafeOnCompleted" or "AwaitOnCompleted";
    private static int UniqueAdd(List<CodeInstruction> code,bool generic) => code.Select((i,n)=>(i,n)).Single(x=>x.i.operand is MethodInfo m && m.DeclaringType==typeof(CreatureCmd) && m.Name==nameof(CreatureCmd.Add) && m.IsGenericMethod==generic && m.ReturnType==typeof(Task<Creature>) && (!generic || m.GetGenericArguments().SequenceEqual([typeof(ToughEgg)]))).n;
    private static MethodInfo MoveNext(MethodInfo method)
    {
        var machine=method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType ?? throw new InvalidOperationException("Native async state machine missing: "+method);
        if(machine.ContainsGenericParameters) machine=machine.MakeGenericType(method.GetGenericArguments());
        return Required(machine,"MoveNext",typeof(void),[]);
    }
    private static MethodInfo Required(Type owner,string name,Type result,Type[] args)
    {
        var method=owner.GetMethod(name,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly,null,args,null);
        Require(method is not null && method.ReturnType==result && !method.ContainsGenericParameters,"Native summon signature changed: "+owner+"."+name); return method!;
    }
    private static FieldInfo Field(Type owner,string name,Type type)
    {
        const BindingFlags flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
        var field=owner.GetField(name,flags);
        if (field is null && name.StartsWith("<i>5__",StringComparison.Ordinal))
        {
            // PBE renumbers compiler-generated loop fields; match by shape, not by index.
            var matches=owner.GetFields(flags).Where(f=>f.FieldType==type &&
                f.Name.StartsWith("<i>5__",StringComparison.Ordinal)).ToArray();
            if (matches.Length==1) field=matches[0];
        }
        Require(field is not null && field.FieldType==type,"Native summon field changed: "+owner+"."+name); return field!;
    }
    private static MethodInfo Handler(string name)=>typeof(DomainSummonEffects).GetMethod(name,BindingFlags.Static|BindingFlags.NonPublic)!;
    private static int Unique(List<CodeInstruction> code,MethodInfo method)=>code.Select((i,n)=>(i,n)).Single(x=>x.i.Calls(method)).n;
    private static void Transfer(CodeInstruction from,CodeInstruction to)
    {
        Require(from.blocks.Count==0,"Unexpected summon EH insertion boundary"); to.labels.AddRange(from.labels); from.labels.Clear();
    }
    private static void Require(bool valid,string message){if(!valid)throw new InvalidOperationException(message);}
}
