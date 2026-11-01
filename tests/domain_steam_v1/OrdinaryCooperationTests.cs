using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

internal static class SteamOrdinaryCooperationTests
{
    const BindingFlags F=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance;
    static readonly Type Adapter=typeof(DomainSteamEruptionEffects);
    static object? ExpectedEpisode,ExpectedCommand;
    static int Checks,NativeCalls;
    static void Need(bool value,string message){Checks++;if(!value)throw new Exception(message);}
    static object? Call(string name,params object?[] args)=>Adapter.GetMethod(name,F)!.Invoke(null,args);
    static object Field(object instance,string name)=>instance.GetType().GetField(name,F)!.GetValue(instance)!;
    static object? Ambient(string name)=>Adapter.GetField(name,F)!.GetValue(null)!.GetType().GetProperty("Value")!.GetValue(Adapter.GetField(name,F)!.GetValue(null));
    static void Ambient(string name,object? value){var slot=Adapter.GetField(name,F)!.GetValue(null)!;slot.GetType().GetProperty("Value")!.SetValue(slot,value);}
    static IEnumerable<CodeInstruction> StubDispatch(IEnumerable<CodeInstruction> input)
    {
        var native=(MethodInfo)Adapter.GetField("NativeDamage",F)!.GetValue(null)!;int found=0;
        foreach(var c in input){if(c.Calls(native)){c.operand=typeof(SteamOrdinaryCooperationTests).GetMethod(nameof(ManagedNativeStub),F)!;found++;}yield return c;}
        if(found!=1)throw new Exception("Dispatcher must retain exactly one native call.");
    }
    // Explicit managed stub: exercises the real handoff/Enter bookkeeping, not native
    // damage or Godot. Never report this as a native task/box or gameplay proof.
    [MethodImpl(MethodImplOptions.NoInlining)]
    static async Task<IEnumerable<DamageResult>> ManagedNativeStub(PlayerChoiceContext context,IEnumerable<Creature> targets,decimal amount,ValueProp props,Creature? dealer,CardModel? card)
    {
        NativeCalls++; var flow=Enum.Parse(Adapter.GetNestedType("Flow",F)!,"Damage");
        var done=new TaskCompletionSource<IEnumerable<DamageResult>>();
        var step=Call("Enter",done.Task,dealer,-1,flow)!;var frame=step.GetType().GetProperty("Frame")!.GetValue(step)!;
        Need(ReferenceEquals(Field(frame,"Episode"),ExpectedEpisode),"actual dispatched frame has only expected ownership");
        if(ExpectedEpisode is not null)Need(ReferenceEquals(Field(Field(frame,"Damage"),"Command"),ExpectedCommand),"handoff belongs to exact AttackCommand");
        var nested=new TaskCompletionSource();var child=Call("Enter",nested.Task,dealer,-1,flow)!;
        Need(Field(child.GetType().GetProperty("Frame")!.GetValue(child)!,"Episode") is null,"nested same-dealer native entry cannot reuse consumed ticket");
        Call("BeforeSignal",child,true);nested.SetResult();
        var result=new DamageResult(dealer!,props);
        Call("BeforeSignal",step,true);done.SetResult(new[]{result});return await done.Task;
    }
    static readonly List<string> PaidTrace=[];
    static Task PaidDomainTask=Task.CompletedTask;
    static bool DomainStub(ref Task __result){PaidTrace.Add("domain");__result=PaidDomainTask;return false;}
    static bool InProgressStub(ref bool __result){__result=false;return false;}
    sealed class ManagedResponder(string id):PowerModel,IOrdinarySegmentResponder
    {
        public override MegaCrit.Sts2.Core.Entities.Powers.PowerType Type=>MegaCrit.Sts2.Core.Entities.Powers.PowerType.Buff;
        public override MegaCrit.Sts2.Core.Entities.Powers.PowerStackType StackType=>MegaCrit.Sts2.Core.Entities.Powers.PowerStackType.Counter;
        public Task AfterOrdinarySegment(PlayerChoiceContext context,CardModel card,IReadOnlyList<DamageResult> results){PaidTrace.Add(id);return Task.CompletedTask;}
    }
    static void PaidPipelineChecks(object slot,PropertyInfo value)
    {
        var harmony=new Harmony("Volibear.SteamStage.PaidPipeline");
        var saved=value.GetValue(slot);
        try
        {
            harmony.Patch(AccessTools.Method(typeof(DomainPower),"AttachAfterOrdinarySegment"),prefix:new HarmonyMethod(typeof(SteamOrdinaryCooperationTests),nameof(DomainStub)));
            harmony.Patch(AccessTools.PropertyGetter(typeof(MegaCrit.Sts2.Core.Combat.CombatManager),"IsOverOrEnding"),prefix:new HarmonyMethod(typeof(SteamOrdinaryCooperationTests),nameof(InProgressStub)));
            var player=RuntimeHelpers.GetUninitializedObject(typeof(MegaCrit.Sts2.Core.Entities.Players.Player));
            var owner=(Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));
            typeof(MegaCrit.Sts2.Core.Entities.Players.Player).GetField("<Creature>k__BackingField",F)!.SetValue(player,owner);
            typeof(Creature).GetField("_currentHp",F)!.SetValue(owner,100);
            var powers=new List<PowerModel>();typeof(Creature).GetField("_powers",F)!.SetValue(owner,powers);
            var card=(CardModel)RuntimeHelpers.GetUninitializedObject(Volibear.Content.VolibearCard.AllCardTypes.First());
            typeof(AbstractModel).GetField("<IsMutable>k__BackingField",F)!.SetValue(card,true);
            typeof(CardModel).GetField("_owner",F)!.SetValue(card,player);
            typeof(CardModel).GetField("<Type>k__BackingField",F)!.SetValue(card,MegaCrit.Sts2.Core.Entities.Cards.CardType.Attack);
            var scopeType=typeof(CardResolutionHooks).GetNestedType("PlayScope",F)!;
            var scope=RuntimeHelpers.GetUninitializedObject(scopeType);scopeType.GetField("Card",F)!.SetValue(scope,card);
            var gate=new CardResolutionPlayGate();scopeType.GetField("Gate",F)!.SetValue(scope,gate);value.SetValue(slot,scope);
            var result=new DamageResult(owner,ValueProp.Move);var domainDone=new TaskCompletionSource();PaidDomainTask=domainDone.Task;PaidTrace.Clear();
            var task=CardResolutionHooks.OrdinaryAttackPipelineV1(null!,ValueProp.Move,owner,card,()=>{PaidTrace.Add("native");return Task.FromResult<IEnumerable<DamageResult>>(new[]{result});});
            Need(PaidTrace.SequenceEqual(new[]{"native","domain"})&&!task.IsCompleted,"paid player waits for Domain before capturing responders");
            powers.Add(new ManagedResponder("first"));powers.Add(new ManagedResponder("second"));domainDone.SetResult();
            Need(ReferenceEquals(task.GetAwaiter().GetResult().Single(),result)&&PaidTrace.SequenceEqual(new[]{"native","domain","first","second"}),"paid player pipeline retains results and post-Domain responder order");
            PaidDomainTask=Task.CompletedTask;
            foreach(var invalid in new[]{"wrong-card","wrong-dealer","non-move","empty-results","closed-paid-scope"})
            {
                PaidTrace.Clear();if(invalid=="closed-paid-scope")gate.Close();
                var results=invalid=="empty-results"?Array.Empty<DamageResult>():new[]{result};
                CardResolutionHooks.OrdinaryAttackPipelineV1(null!,invalid=="non-move"?ValueProp.Unpowered:ValueProp.Move,invalid=="wrong-dealer"?null:owner,invalid=="wrong-card"?null:card,()=>{PaidTrace.Add("native");return Task.FromResult<IEnumerable<DamageResult>>(results);}).GetAwaiter().GetResult();
                Need(PaidTrace.SequenceEqual(new[]{"native"}),"ordinary paid-scope qualifier retained: "+invalid);
            }
        }
        finally{harmony.UnpatchAll(harmony.Id);value.SetValue(slot,saved);PaidDomainTask=Task.CompletedTask;PaidTrace.Clear();}
    }
    internal static void Run()
    {
        var cards=typeof(CardResolutionHooks);var slot=cards.GetField("Current",F)!.GetValue(null)!;var value=slot.GetType().GetProperty("Value")!;
        var oldScope=value.GetValue(slot);var current=Ambient("Current");var origin=Ambient("Origin");
        var handoff=(SteamNativeEntryBinding)Adapter.GetField("DamageHandoff",F)!.GetValue(null)!;
        var harmony=new Harmony("Volibear.SteamStage.OrdinaryCooperation");
        try
        {
            value.SetValue(slot,null);
            PaidPipelineChecks(slot,value);
            var receiver=(Creature)RuntimeHelpers.GetUninitializedObject(typeof(Creature));var result=new DamageResult(receiver,ValueProp.Unpowered);
            var completion=new TaskCompletionSource<IEnumerable<DamageResult>>();int calls=0;
            var pipeline=CardResolutionHooks.OrdinaryAttackPipelineV1(null!,ValueProp.Unpowered,null,null,()=>{calls++;return completion.Task;});
            Need(calls==1&&!pipeline.IsCompleted,"ordinary dispatcher called once and awaited");
            completion.SetResult(new[]{result});Need(ReferenceEquals(pipeline.GetAwaiter().GetResult().Single(),result),"actual result identity survives ordinary pipeline");
            var error=new InvalidOperationException("managed-dispatch-fault");
            try{CardResolutionHooks.OrdinaryAttackPipelineV1(null!,ValueProp.Unpowered,null,null,()=>Task.FromException<IEnumerable<DamageResult>>(error)).GetAwaiter().GetResult();throw new Exception("lost native fault");}
            catch(InvalidOperationException caught){Need(ReferenceEquals(caught,error),"native fault preserved without ordinary tail");}
            var cancel=new CancellationToken(true);
            try{CardResolutionHooks.OrdinaryAttackPipelineV1(null!,ValueProp.Unpowered,null,null,()=>Task.FromCanceled<IEnumerable<DamageResult>>(cancel)).GetAwaiter().GetResult();throw new Exception("lost native cancellation");}
            catch(OperationCanceledException){Checks++;}
            handoff.Install(harmony,typeof(SteamOrdinaryCooperationTests).GetMethod(nameof(ManagedNativeStub),F)!);
            harmony.Patch(Adapter.GetMethod("DispatchNativeDamage",F)!,transpiler:new HarmonyMethod(typeof(SteamOrdinaryCooperationTests),nameof(StubDispatch)));
            foreach(var tagged in new[]{false,true})
            {
                var episodeType=Adapter.GetNestedType("Episode",F)!;var ep=RuntimeHelpers.GetUninitializedObject(episodeType);
                episodeType.GetField("Owner",F)!.SetValue(ep,receiver);
                episodeType.GetField("Decision",F)!.SetValue(ep,new SteamEruptionDecision(new object(),new object(),new object(),1,(long)Adapter.GetField("_epoch",F)!.GetValue(null)!));
                var command=(AttackCommand)RuntimeHelpers.GetUninitializedObject(typeof(AttackCommand));
                ExpectedEpisode=tagged?ep:null;ExpectedCommand=command;
                var flow=Enum.Parse(Adapter.GetNestedType("Flow",F)!,"Attack");
                var root=Activator.CreateInstance(Adapter.GetNestedType("Frame",F)!,F,null,new object?[]{Task.CompletedTask,flow,command,ExpectedEpisode,null},null)!;
                Ambient("Current",root);
                var invocation=Activator.CreateInstance(Adapter.GetNestedType("DamageInvocation",F)!,F,null,new object?[]{ep,RuntimeHelpers.GetUninitializedObject(typeof(AttackCommand))},null)!;
                using(handoff.Dispatch(invocation))
                {
                    var results=((Task<IEnumerable<DamageResult>>)Call("DamageFromCommand",null,new[]{receiver},2m,ValueProp.Unpowered,receiver,null,command)!).GetAwaiter().GetResult();
                    Need(results.Count()==1,"untagged/tagged ordinary pipeline returns actual result");
                    ExpectedEpisode=ep;ExpectedCommand=Field(invocation,"Command");
                    var outer=ManagedNativeStub(null!,new[]{receiver},2m,ValueProp.Unpowered,receiver,null).GetAwaiter().GetResult();
                    Need(outer.Count()==1,"outer ticket remains consumable after nested dispatch masking");
                }
                Ambient("Current",current);Ambient("Origin",origin);
            }
            Need(NativeCalls==4,"one exact native dispatch per ordinary invocation");
            var attack=AccessTools.Method(AccessTools.Method(typeof(AttackCommand),nameof(AttackCommand.Execute)).GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType,"MoveNext");
            foreach(var mutation in new[]{"missing","duplicate-native","duplicate-v1","opaque-helper","mixed-v1-native"})
            {
                var il=new DynamicMethod("CooperationDrift",typeof(void),Type.EmptyTypes).GetILGenerator();
                var native=(MethodInfo)Adapter.GetField("NativeDamage",F)!.GetValue(null)!;
                var code=PatchProcessor.GetOriginalInstructions(attack,il).ToList();
                if(mutation=="missing")code.RemoveAll(c=>c.Calls(native));
                else if(mutation=="duplicate-native")code.Add(new CodeInstruction(OpCodes.Call,native));
                else if(mutation=="opaque-helper")code.Single(c=>c.Calls(native)).operand=typeof(SteamOrdinaryCooperationTests).GetMethod(nameof(ManagedNativeStub),F)!;
                else
                {
                    if(mutation=="duplicate-v1")code.Single(c=>c.Calls(native)).operand=CardResolutionHooks.OrdinaryAttackCallsiteV1;
                    code.Add(new CodeInstruction(OpCodes.Call,CardResolutionHooks.OrdinaryAttackCallsiteV1));
                }
                try{_=((IEnumerable<CodeInstruction>)Call("AttackMachine",code,il,attack)!).ToArray();throw new Exception("ordinary anchor drift accepted");}
                catch(TargetInvocationException caught)when(caught.InnerException is InvalidOperationException){Checks++;}
            }
        }
        finally{harmony.UnpatchAll(harmony.Id);value.SetValue(slot,oldScope);Ambient("Current",current);Ambient("Origin",origin);handoff.Reset();ExpectedEpisode=ExpectedCommand=null;}
        Console.WriteLine($"STEAM_ORDINARY_COOPERATION_PASS checks={Checks} managed-dispatch-domain-combat-stubs=true native-gameplay=NOT_RUN");
    }
}
