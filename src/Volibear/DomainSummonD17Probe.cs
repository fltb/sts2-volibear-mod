using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;
namespace Volibear;

/// <summary>Controlled windows inside actual native move/death awaits. No direct source callback or adapter invocation.</summary>
internal static class DomainSummonD17Probe
{
    internal static readonly string[] Variants = ["fabricator-attack-open", "fabricator-attack-close", "fabricator-partial-open", "fabricator-cancel-close",
        "ovicopter-animation-open", "ovicopter-partial-open", "ovicopter-post-open", "ovicopter-cancel-close",
        "infested-wait-open", "infested-partial-open", "infested-post-open"];
    private static readonly Harmony Observer = new("Volibear.DomainSummonD17Probe");
    private static readonly BindingFlags Flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    private static readonly List<object> Gates = [], Windows = [], Births = [], DeathCallbacks = [], Died = [], Creates = [];
    private static readonly List<Creature> Children = [];
    private static bool _started, _armed, _windowUsed;
    private static int _musicCalls;
    private static string _variant = "";
    private static Creature? _parent, _owner;
    private static CombatState? _combat;
    private static object? _firstBatch;
    private static Task? _removal;
    public static void Install()
    {
        InstallObservers(Observer);
        CombatManager.Instance.TurnStarted += OnTurnStarted;
    }
    internal static void InstallObservers(Harmony observer)
    {
        foreach (var (type,name) in new[] { (typeof(Fabricator),"FabricatingStrikeMove"),(typeof(Ovicopter),"LayEggsMove"),(typeof(InfestedPower),"AfterDeath") })
            observer.Patch(MoveNext(AccessTools.Method(type,name)), transpiler: new HarmonyMethod(typeof(DomainSummonD17Probe),nameof(AwaitCalls)) { priority = Priority.Last });
        var add = typeof(CreatureCmd).GetMethod(nameof(CreatureCmd.Add), [typeof(Creature)])!;
        observer.Patch(MoveNext(add), transpiler: new HarmonyMethod(typeof(DomainSummonD17Probe),nameof(AddPostCommit)) { priority = Priority.Last });
        foreach (var creator in typeof(CreatureCmd).GetMethods(BindingFlags.Public|BindingFlags.Static).Where(m=>m.Name==nameof(CreatureCmd.Add)&&!m.IsGenericMethod&&m.ReturnType==typeof(Task<Creature>)))
            observer.Patch(MoveNext(creator.IsGenericMethodDefinition?creator.MakeGenericMethod(typeof(ToughEgg)):creator),
                transpiler:new HarmonyMethod(typeof(DomainSummonD17Probe),nameof(CreateCall)){priority=Priority.Last});
        observer.Patch(MoveNext(AccessTools.Method(typeof(InfestedPower),nameof(InfestedPower.AfterDeath))), prefix: new HarmonyMethod(typeof(DomainSummonD17Probe),nameof(ObserveDeathEntry)));
        observer.Patch(typeof(DomainSummonEffects).GetMethod("CancelAtGate",BindingFlags.Static|BindingFlags.NonPublic)!, postfix: new HarmonyMethod(typeof(DomainSummonD17Probe),nameof(ObserveGate)));
    }
    private static MethodInfo MoveNext(MethodInfo method)
    {
        var machine=method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
        if(machine.ContainsGenericParameters)machine=machine.MakeGenericType(method.GetGenericArguments());
        return AccessTools.Method(machine,"MoveNext");
    }
    private static IEnumerable<CodeInstruction> CreateCall(IEnumerable<CodeInstruction> input)
    {
        var code=input.Select(i=>new CodeInstruction(i)).ToArray();int count=0;
        foreach(var i in code)if(i.operand is MethodInfo m&&m.DeclaringType==typeof(ICombatState)&&m.Name==nameof(ICombatState.CreateCreature))
        {i.opcode=OpCodes.Call;i.operand=typeof(DomainSummonD17Probe).GetMethod(nameof(Create),BindingFlags.NonPublic|BindingFlags.Static)!;count++;}
        if(count!=1)throw new InvalidOperationException("Native CreateCreature observation anchor missing");return code;
    }
    private static uint NextId()=>(uint)AccessTools.Field(typeof(CombatState),"_nextCreatureId").GetValue(_combat)!;
    private static Creature Create(ICombatState state,MonsterModel monster,CombatSide side,string? slot)
    {
        bool observe=_armed&&ReferenceEquals(state,_combat)&&side==CombatSide.Enemy;
        uint before=observe?NextId():0;
        var creature=state.CreateCreature(monster,side,slot);
        if(observe)RecordCreate(creature,before,"CreateCreature.return-before-Add");
        return creature;
    }
    private static Task<Creature> Egg(ICombatState state,string? slot)
    {
        // The pinned generic MoveNext has no patchable entrypoint. Observe its REAL source call instead.
        bool observe=_armed&&ReferenceEquals(state,_combat);uint before=observe?NextId():0;
        var native=CreatureCmd.Add<ToughEgg>(state,slot); // synchronous Create+membership precede its first await
        if(observe)RecordCreate(state.Enemies.Single(c=>c.CombatId==before),before,"Add<ToughEgg>.return-after-sync-attach");
        return native; // exact native Task and Creature, no substitute or replay
    }
    private static void RecordCreate(Creature creature,uint before,string point)
    {
        Creates.Add(new {point,id=Id(creature),type=creature.Monster!.GetType().Name,slot=creature.SlotName,side=creature.Side.ToString(),hp=creature.CurrentHp,maxHp=creature.MaxHp,
            combatAssigned=ReferenceEquals(creature.CombatState,_combat),inRoster=_combat!.ContainsCreature(creature),domain=_owner!.GetPowerAmount<DomainPower>(),counterBefore=before,counterAfter=NextId()});
    }
    private static IEnumerable<CodeInstruction> AwaitCalls(IEnumerable<CodeInstruction> input,MethodBase __originalMethod)
    {
        var code=input.Select(i=>new CodeInstruction(i)).ToArray(); int count=0;
        var owner=__originalMethod.DeclaringType!.DeclaringType!;
        foreach(var instruction in code)
            if(instruction.operand is MethodInfo m)
            {
                string? wrapper = owner==typeof(Fabricator) && m.DeclaringType==typeof(AttackCommand) && m.Name=="Execute" ? nameof(Attack)
                    : owner==typeof(Ovicopter) && m.DeclaringType==typeof(CreatureCmd) && m.Name=="TriggerAnim" ? nameof(Animation)
                    : owner==typeof(Ovicopter) && m.DeclaringType==typeof(CreatureCmd) && m.Name=="Add" && m.IsGenericMethod && m.GetGenericArguments().SequenceEqual([typeof(ToughEgg)]) ? nameof(Egg)
                    : owner==typeof(InfestedPower) && m.DeclaringType==typeof(Cmd) && m.Name=="CustomScaledWait" ? nameof(DeathWait)
                    : owner==typeof(InfestedPower) && m.DeclaringType==typeof(NRunMusicController) && m.Name==nameof(NRunMusicController.TriggerEliteSecondPhase) ? nameof(Music) : null;
                if(wrapper is null)continue;
                var target=typeof(DomainSummonD17Probe).GetMethod(wrapper,BindingFlags.Static|BindingFlags.NonPublic)!;
                var args=m.GetParameters().Select(p=>p.ParameterType);if(!m.IsStatic)args=args.Prepend(m.DeclaringType!);
                if(!args.SequenceEqual(target.GetParameters().Select(p=>p.ParameterType))||m.ReturnType!=target.ReturnType)throw new InvalidOperationException("Native D17 forwarding shape changed");
                instruction.opcode=OpCodes.Call;instruction.operand=target;count++;
            }
        if(count!=(owner==typeof(Fabricator)?1:2))throw new InvalidOperationException("Native D17 wait/music call missing");return code;
    }
    private static IEnumerable<CodeInstruction> AddPostCommit(IEnumerable<CodeInstruction> input)
    {
        var code=input.Select(i=>new CodeInstruction(i)).ToArray();int count=0;
        foreach(var i in code)if(i.operand is MethodInfo m&&m.DeclaringType==typeof(CombatManager)&&m.Name==nameof(CombatManager.AfterCreatureAdded))
        {i.opcode=OpCodes.Call;i.operand=typeof(DomainSummonD17Probe).GetMethod(nameof(AfterAdded),BindingFlags.Static|BindingFlags.NonPublic)!;count++;}
        if(count!=1)throw new InvalidOperationException("Native post-attachment await missing");return code;
    }
    private static async Task<AttackCommand> Attack(AttackCommand command,PlayerChoiceContext? choices)
    {
        var result=await command.Execute(choices);
        if(_armed&&ReferenceEquals(command.Attacker,_parent)&&_variant.StartsWith("fabricator-attack-",StringComparison.Ordinal))
            await ChangeDomain("native-attack-completed-before-first-SpawnBot",_variant.EndsWith("-open",StringComparison.Ordinal));
        return result;
    }
    private static async Task Animation(Creature creature,string trigger,float wait)
    {
        await CreatureCmd.TriggerAnim(creature,trigger,wait);
        if(_armed&&ReferenceEquals(creature,_parent)&&_variant=="ovicopter-animation-open")await ChangeDomain("native-animation-before-first-create",true);
    }
    private static async Task DeathWait(float fast,float standard,bool ignore,System.Threading.CancellationToken cancellation)
    {
        await Cmd.CustomScaledWait(fast,standard,ignore,cancellation);
        if(_armed&&_variant=="infested-wait-open")await ChangeDomain("native-death-wait-before-music-create",true);
    }
    private static void Music(NRunMusicController controller)
    {
        if(_armed)_musicCalls++;
        controller.TriggerEliteSecondPhase();
    }
    private static async Task AfterAdded(CombatManager manager,Creature creature)
    {
        await manager.AfterCreatureAdded(creature);
        if(!_armed||ReferenceEquals(creature,_parent)||!creature.IsEnemy||!ReferenceEquals(creature.CombatState,_combat))return;
        Children.Add(creature);
        var before=Enemy(creature);
        if(_variant.EndsWith("-partial-open",StringComparison.Ordinal)&&Children.Count==1 ||
            _variant=="ovicopter-post-open"&&Children.Count==3 || _variant=="infested-post-open"&&Children.Count==4)
            await ChangeDomain("native-child-attached-before-Add-return",true);
        Births.Add(new { ordinal=Children.Count,before,after=Enemy(creature),domain=_owner!.GetPowerAmount<DomainPower>(),
            attached=_combat!.ContainsCreature(creature),sameCombat=ReferenceEquals(creature.CombatState,_combat) });
    }
    private static async Task ChangeDomain(string point,bool open)
    {
        if(_windowUsed)throw new InvalidOperationException("D17 window repeated");_windowUsed=true;
        var before=Snapshot();
        var tree=(SceneTree)Engine.GetMainLoop();await tree.ToSignal(tree,SceneTree.SignalName.ProcessFrame);
        if(open)await DomainPower.Open(new ThrowingPlayerChoiceContext(),_owner!,5);
        else await PowerCmd.Remove<DomainPower>(_owner!);
        Windows.Add(new { point,open,suspended=true,before,after=Snapshot() });
    }
    private static void ObserveGate(object __0,string __1,bool __result)
    {
        if(!_armed)return;
        var binding=__0.GetType().GetProperty("Binding",Flags)!.GetValue(__0);
        if(binding is null)return;
        var bindingType=binding.GetType();
        var batch=bindingType.GetField("Payload",Flags)!.GetValue(binding);
        var epoch=(long)bindingType.GetField("Epoch",Flags)!.GetValue(binding)!;
        var closed=(bool)bindingType.GetField("Closed",Flags)!.GetValue(binding)!;
        var frameEpoch=(long)__0.GetType().GetProperty("Generation",Flags)!.GetValue(__0)!;
        var currentEpoch=(long)typeof(DomainSummonEffects).GetField("_generation",BindingFlags.Static|BindingFlags.NonPublic)!.GetValue(null)!;
        if(batch is null||closed||epoch!=currentEpoch||frameEpoch!=currentEpoch||
            (bool)batch.GetType().GetField("Closed",Flags)!.GetValue(batch)!)
        {
            // A detached/retired receipt has no authority to read a current world or
            // remove Domain. Do not invent an owner or label this a Domain cancellation.
            // The unchanged strict D17 oracle rejects this metadata-only row if it
            // unexpectedly appears in a normal live-cancellation acceptance case.
            Gates.Add(new { boundary=__1,scope="retired-or-closed-summon",known=true,closed,
                epoch,frameEpoch,currentEpoch,hasPayload=batch is not null,blocked=__result });
            return;
        }
        var owner=(Creature)batch.GetType().GetField("Owner",Flags)!.GetValue(batch)!;
        if(!ReferenceEquals(owner,_parent))return;
        _firstBatch??=batch;
        int before=_owner!.GetPowerAmount<DomainPower>();
        var snapshot=Snapshot();
        if(__result&&_variant.EndsWith("-cancel-close",StringComparison.Ordinal)&&!_windowUsed)
        {
            _windowUsed=true;_removal=PowerCmd.Remove<DomainPower>(_owner);
            Windows.Add(new { point="actual-consumed-cancellation-before-source-return",open=false,suspended=false,before=snapshot,after=Snapshot() });
        }
        Gates.Add(new { boundary=__1,cancelled=__result,sameBatch=ReferenceEquals(batch,_firstBatch),domainBefore=before,
            domainAfter=_owner.GetPowerAmount<DomainPower>(),snapshot });
    }
    private static void ObserveDeathEntry(object __instance)
    {
        if(!_armed)return;var type=__instance.GetType();
        if((int)type.GetField("<>1__state",Flags)!.GetValue(__instance)! != -1)return;
        var source=(InfestedPower)type.GetField("<>4__this",Flags)!.GetValue(__instance)!;
        var target=(Creature)type.GetField("target",Flags)!.GetValue(__instance)!;
        if(!ReferenceEquals(source.Owner,_parent))return;
        DeathCallbacks.Add(new { ownerId=Id(source.Owner),targetId=Id(target),prevented=(bool)type.GetField("wasRemovalPrevented",Flags)!.GetValue(__instance)!,sourceAmount=source.Amount,snapshot=Snapshot() });
    }
    private static string Id(Creature c)=>c.CombatId?.ToString()??throw new InvalidOperationException("Missing native combat ID");
    private static object Enemy(Creature c)=>new { id=Id(c),type=c.Monster!.GetType().Name,slot=c.SlotName,hp=c.CurrentHp,maxHp=c.MaxHp,block=c.Block,
        minion=c.GetPowerAmount<MinionPower>(),infested=c.GetPowerAmount<InfestedPower>(),hatch=c.GetPowerAmount<HatchPower>(),
        nextMove=c.Monster.NextMove.Id,startStunned=c.Monster is Wriggler w?(bool?)w.StartStunned:null };
    private static object Snapshot()=>new { parentId=Id(_parent!),playerId=Id(_owner!),parentHp=_parent!.CurrentHp,parentAttached=_combat!.ContainsCreature(_parent),
        parentInfested=_parent.GetPowerAmount<InfestedPower>(),playerHp=_owner!.CurrentHp,playerBlock=_owner.Block,domain=_owner.GetPowerAmount<DomainPower>(),
        inProgress=CombatManager.Instance.IsInProgress,isEnding=CombatManager.Instance.IsEnding,round=_combat.RoundNumber,side=_combat.CurrentSide.ToString(),
        nextCreatureId=(uint)AccessTools.Field(typeof(CombatState),"_nextCreatureId").GetValue(_combat)!,enemies=_combat.Enemies.Select(Enemy).ToArray() };
    private static object[] Damage(int start)=>CombatManager.Instance.History.Entries.Skip(start).OfType<DamageReceivedEntry>().Select(e=>(object)new {
        sourceId=e.Dealer is null?null:Id(e.Dealer),receiverId=Id(e.Receiver),hpLost=e.Result.UnblockedDamage,blocked=e.Result.BlockedDamage,overkill=e.Result.OverkillDamage,cardSource=e.CardSource?.GetType().Name }).ToArray();
    private static object[] Moves(int start)=>CombatManager.Instance.History.Entries.Skip(start).OfType<MonsterPerformedMoveEntry>().Select(e=>(object)new {
        sourceId=Id(e.Monster.Creature),move=e.Move.Id,targets=e.Targets?.Select(Id).ToArray() }).ToArray();
    private static void OnTurnStarted(CombatState state){if(!_started){_started=true;_ = Run(state);}}
    private static async Task Run(CombatState state)
    {
        Action<Creature>? died=null;Action<CombatRoom>? won=null,ended=null;
        try
        {
            var token=System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            _variant=System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_SUMMON_CASE")??"";
            var release=ReleaseInfoManager.Instance.ReleaseInfo;
            if(string.IsNullOrWhiteSpace(token)||!Variants.Contains(_variant)||MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn||release is null||release.Version!=global::Volibear.Core.SupportedGameBuild.Version||release.Commit!=global::Volibear.Core.SupportedGameBuild.Commit)throw new InvalidOperationException("Invalid D17 token/case/native release");
            _combat=state;_parent=state.Enemies.Single();_owner=state.Players.Single().Creature;
            string family=_variant.Split('-')[0];
            string expected=family=="fabricator"?"FabricatorNormal":family=="ovicopter"?"OvicopterNormal":"PhrogParasiteElite";
            if(state.Encounter?.GetType().Name!=expected||_parent.Monster!.GetType().Name!=(family=="fabricator"?"Fabricator":family=="ovicopter"?"Ovicopter":"PhrogParasite")||
                state.RoundNumber!=1||state.CurrentSide!=CombatSide.Player||state.RunState.AscensionLevel!=0||_owner.CurrentHp!=80||_owner.Block!=0||_parent.Block!=0||
                _owner.GetPowerAmount<DomainPower>()!=0||_parent.GetPowerAmount<InfestedPower>()!=(family=="infested"?4:0))throw new InvalidOperationException("Expected fresh native D17 fixture");
            await CreatureCmd.SetMaxAndCurrentHp(_parent,100m);
            if(_variant=="fabricator-attack-close"||_variant.EndsWith("-cancel-close",StringComparison.Ordinal))await DomainPower.Open(new ThrowingPlayerChoiceContext(),_owner,5);
            var before=Snapshot();int historyStart=CombatManager.Instance.History.Entries.Count();
            _armed=true;object action;object[] damageRows,movesRows;
            if(family!="infested")
            {
                var monster=_parent.Monster;var machine=monster.MoveStateMachine!;
                string initialMove=monster.NextMove.Id;
                string requested=family=="ovicopter"?"LAY_EGGS_MOVE":_variant.StartsWith("fabricator-attack-",StringComparison.Ordinal)?"FABRICATING_STRIKE_MOVE":"FABRICATE_MOVE";
                if(family=="fabricator")monster.SetMoveImmediate((MoveState)machine.States[requested],forceTransition:true);
                if(monster.NextMove.Id!=requested)throw new InvalidOperationException("Wrong actual selected move");
                var logsBefore=machine.StateLog.Select(s=>s.Id).ToArray();bool performingBefore=monster.IsPerformingMove;
                var lastField=family=="fabricator"?AccessTools.Field(typeof(Fabricator),"_lastSpawned"):null;
                var lastBefore=(lastField?.GetValue(monster) as MonsterModel)?.GetType().Name;
                await monster.PerformMove().WaitAsync(TimeSpan.FromSeconds(40));
                if(_removal is not null)await _removal.WaitAsync(TimeSpan.FromSeconds(10));
                var afterMove=Snapshot();bool performingAfter=monster.IsPerformingMove;
                damageRows=Damage(historyStart);movesRows=Moves(historyStart);
                var lastAfter=(lastField?.GetValue(monster) as MonsterModel)?.GetType().Name;
                monster.RollMove(state.PlayerCreatures);
                action=new { api="MonsterModel.PerformMove+MonsterModel.RollMove",initialMove,selected=requested,performingBefore,performingAfter,
                    stateLogBefore=logsBefore,stateLogAfter=machine.StateLog.Select(s=>s.Id).ToArray(),nextMove=monster.NextMove.Id,lastSpawnedBefore=lastBefore,lastSpawnedAfter=lastAfter,afterMove };
            }
            else
            {
                int wonCount=0,endedCount=0;won=_=>wonCount++;ended=_=>endedCount++;
                CombatManager.Instance.CombatWon+=won;CombatManager.Instance.CombatEnded+=ended;
                died=c=>Died.Add(new { targetId=Id(c),hp=c.CurrentHp,sameParent=ReferenceEquals(c,_parent),domain=_owner.GetPowerAmount<DomainPower>() });_parent.Died+=died;
                var results=(await NativeCompat.Damage(new ThrowingPlayerChoiceContext(),_parent,100m,ValueProp.Unpowered|ValueProp.Unblockable,_owner,null).WaitAsync(TimeSpan.FromSeconds(40)))
                    .Select(r=>new {receiverId=Id(r.Receiver),hpLost=r.UnblockedDamage,blocked=r.BlockedDamage,overkill=r.OverkillDamage}).ToArray();
                var afterDeath=Snapshot();damageRows=Damage(historyStart);movesRows=Moves(historyStart);
                var winResult=await CombatManager.Instance.CheckWinCondition().WaitAsync(TimeSpan.FromSeconds(40));
                action=new { api="CreatureCmd.Damage+native-Kill/AfterDeath+CombatManager.CheckWinCondition",input=new {amount=100,props=6,sourceId=Id(_owner),targetId=Id(_parent)},results,afterDeath,winResult,wonCount,endedCount };
            }
            GD.Print("[Volibear] DOMAIN_SUMMON_D17_RESULT "+JsonSerializer.Serialize(new { schema=1,token,scenario="domain-summon-contract",variant=_variant,
                acceptance="native-async-window-probe-not-natural-input-or-full-enemy-coverage",testMode=false,version=release.Version,commit=release.Commit,
                encounter=expected,parentType=_parent.Monster.GetType().Name,fixtureHp=100,ascension=state.RunState.AscensionLevel,
                before,action,final=Snapshot(),damage=damageRows,moves=movesRows,gates=Gates.ToArray(),windows=Windows.ToArray(),
                births=Births.ToArray(),creates=Creates.ToArray(),childrenFinal=Children.Select(Enemy).ToArray(),deathCallbacks=DeathCallbacks.ToArray(),died=Died.ToArray(),musicCalls=_musicCalls,windowUsed=_windowUsed }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN "+token);MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch(Exception error){GD.PrintErr("[Volibear] DOMAIN_SUMMON_D17_ERROR "+error);((SceneTree)Engine.GetMainLoop()).Quit(2);}
        finally
        {
            _armed=false;if(_parent is not null&&died is not null)_parent.Died-=died;
            if(won is not null)CombatManager.Instance.CombatWon-=won;if(ended is not null)CombatManager.Instance.CombatEnded-=ended;
            _parent=null;_owner=null;_combat=null;_firstBatch=null;_removal=null;Children.Clear();
            Observer.UnpatchAll(Observer.Id);CombatManager.Instance.TurnStarted-=OnTurnStarted;
        }
    }
}
