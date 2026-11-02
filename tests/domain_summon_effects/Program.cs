using System.Collections;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear;
using Volibear.Core;

// Real assembly IL + production decisions/adapter calls. Uninitialized monster instances are identity-only
// handoff markers with no usable world; no native monster method or gameplay is executed.
internal static class Program
{
    private static int checks;
    private const BindingFlags Flags=BindingFlags.Static|BindingFlags.NonPublic;
    private static void Check(bool valid,string message){if(!valid)throw new Exception(message);checks++;}
    private static void Decisions()
    {
        var off=new DomainSummonEffects.DeathDecision(false);
        Check(!off.TryCancel(false),"Outside-domain native");Check(!off.Cancelled,"Native ending veto");off.Close();Check(!off.TryCancel(false),"No retroactive capture");
        var prevented=new DomainSummonEffects.DeathDecision(true);
        Check(!prevented.TryCancel(true),"Prevented death does not consume");Check(!prevented.Cancelled,"Prevented death retains veto");prevented.Close();Check(!prevented.TryCancel(false),"Aborted event cannot replay");
        var active=new DomainSummonEffects.DeathDecision(true);
        Check(!active.Cancelled,"Observation alone is not cancellation");Check(active.TryCancel(false),"Confirmed entry-on consumes");Check(active.Cancelled,"Veto released only after consumption");active.Close();
        Check(active.TryCancel(false),"Completed cancelled event remains cancelled");Check(active.TryCancel(false),"Reentry cannot replay");Check(!active.TryCancel(true),"Unrelated prevented callback native");Check(active.Cancelled,"Prevented callback cannot undo consumption");
        var abandoned=new DomainSummonEffects.DeathDecision(true);abandoned.Close();Check(!abandoned.TryCancel(false),"Abandon closes unconsumed capture");
        var retry=new DomainSummonEffects.DeathDecision(false);Check(!retry.TryCancel(false),"Retry is independent");Check(active.Cancelled,"Retry does not alter old event");
        var late=new DomainSummonEffects.DeathDecision(false);Check(!late.AtBoundary(false,false),"First item may commit");Check(late.AtBoundary(false,true),"Open before remaining item consumes cancellation");Check(late.AtBoundary(false,false),"Expiry cannot replay remaining item");
        var move=new DomainSummonEffects.DeathDecision(false);Check(!move.Cancelled,"Move identity never reserves benefit");Check(!move.AtBoundary(false,false),"Domain expired during attack before first helper permits summon");move.Close();Check(!move.AtBoundary(false,true),"Last committed child not retroactively cancelled");
        var epoch=typeof(DomainSummonEffects).GetField("_generation",Flags)!;long before=(long)epoch.GetValue(null)!;
        var tasks=typeof(DomainSummonEffects).GetField("Tasks",Flags)!;var attempts=typeof(DomainSummonEffects).GetField("Attempts",Flags)!;
        var oldTasks=tasks.GetValue(null);var oldAttempts=attempts.GetValue(null);
        DomainSummonEffects.Reset();Check((long)epoch.GetValue(null)! == before+1,"Reset invalidates captured epochs");
        Check(ReferenceEquals(oldTasks,tasks.GetValue(null))&&!ReferenceEquals(oldAttempts,attempts.GetValue(null)),"Reset retains weak actual-task ownership but preserves death-attempt reset policy");
        Check(typeof(DomainSummonEffects).GetNestedType("DeathAttempt",BindingFlags.NonPublic)!.GetField("Owner",BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance) is not null,"Observer uses actual inherited owner metadata");
    }
    private static List<CodeInstruction> Rewrite(MethodBase method,List<CodeInstruction> input)
    {
        var generator=new DynamicMethod("Inspect"+checks,typeof(void),Type.EmptyTypes,typeof(Program),true).GetILGenerator();
        return ((IEnumerable<CodeInstruction>)typeof(DomainSummonEffects).GetMethod("Rewrite",Flags)!.Invoke(null,[input,generator,method])!).ToList();
    }
    private static void Reject(MethodBase method,Action<List<CodeInstruction>> mutation,string description)
    {
        var input=PatchProcessor.GetOriginalInstructions(method).Select(i=>new CodeInstruction(i)).ToList();mutation(input);
        try{Rewrite(method,input);}catch(TargetInvocationException error) when(error.InnerException is InvalidOperationException or ArgumentException){checks++;return;}
        throw new Exception("Drift accepted: "+description);
    }
    private static bool Call(CodeInstruction i,Type type,string name)=>i.operand is MethodInfo m&&m.DeclaringType==type&&m.Name==name;
    private static void Shapes()
    {
        var type=typeof(DomainSummonEffects);type.GetMethod("Prepare",Flags)!.Invoke(null,null);
        var bodies=(IDictionary)type.GetField("Bodies",Flags)!.GetValue(null)!;
        Check(bodies.Count==10,"Exact ten async native bodies");
        DomainDampenTransactions.VerifyNativeIl();
        var dampen=(IDictionary)typeof(DomainDampenTransactions).GetField("Sites",Flags)!.GetValue(null)!;
        Check(!bodies.Keys.Cast<MethodBase>().Intersect(dampen.Keys.Cast<MethodBase>()).Any(),"ten Summon registration targets do not overlap existing Dampen rewriter");
        foreach(DictionaryEntry pair in bodies)
        {
            var method=(MethodBase)pair.Key;int kind=(int)pair.Value!;
            var input=PatchProcessor.GetOriginalInstructions(method).ToList();var output=Rewrite(method,input);
            Check(output.Count(i=>Call(i,type,"CancelAtGate"))==(kind==0?1:kind==1?2:kind==2?3:0),"Exact guard count "+kind);
            int nativeRegistrations=input.Count(i=>Call(i,typeof(AsyncTaskMethodBuilder),"AwaitUnsafeOnCompleted"));
            Check(output.Count(i=>Call(i,typeof(SummonRegistration),"Await"))==nativeRegistrations&&!output.Any(i=>Call(i,typeof(AsyncTaskMethodBuilder),"AwaitUnsafeOnCompleted")),"one production pre-schedule bridge per original registration "+kind);
            Check(output.Count(i=>Call(i,type,"Close"))==2,"both native terminal signals close ownership "+kind);
            foreach(var (instruction,index) in output.Select((instruction,index)=>(instruction,index)).Where(x=>Call(x.instruction,typeof(AsyncTaskMethodBuilder),"SetResult")||Call(x.instruction,typeof(AsyncTaskMethodBuilder),"SetException")))
                Check(index>0&&Call(output[index-1],type,"Close"),"close immediately before original signal "+kind);
            Check(output.Count(i=>Call(i,type,"RetiredGate"))==(kind is 0 or 1?1:0),"only pinned pre-dereference retired guards "+kind);
            Check(output.Count(i=>Call(i,type,"Enter"))==1&&output.Count(i=>Call(i,type,"Leave"))==1,"Native task enter/leave "+kind);
            if(kind<=3)
                Check(output.Count(i=>Call(i,typeof(CreatureCmd),"Add"))==input.Count(i=>Call(i,typeof(CreatureCmd),"Add")),"Original Add call retained "+kind);
            else if(kind>=6)
                Check(output.Count(i=>Call(i,typeof(CreatureCmd),"Add"))==0&&output.Count(i=>i.operand is MethodInfo m&&m.Name=="AdditionalBirth")==1,"Discarded child Add replaced by the additional-birth bridge "+kind);
            else if(kind==4)
                Check(output.Count(i=>i.operand is MethodInfo m&&m.Name=="ForwardDefensive")==1&&output.Count(i=>i.operand is MethodInfo m&&m.Name=="ForwardAggro")==1,"Both Fabricator helpers forward through the actual summon bridge "+kind);
            else
                Check(output.Count(i=>i.operand is MethodInfo m&&m.Name=="ForwardAggro")==1,"Fabricator helper forwards through the actual summon bridge "+kind);
            foreach(var name in new[]{"GetAwaiter","GetResult"})
                Check(input.Where(i=>i.operand is MethodInfo m&&m.Name==name).Select(i=>i.operand).SequenceEqual(output.Where(i=>i.operand is MethodInfo m&&m.Name==name).Select(i=>i.operand)),"original await/result calls remain once and ordered "+kind+" "+name);
            Reject(method,c=>c.RemoveAll(i=>Call(i,typeof(AsyncTaskMethodBuilder),"SetResult")),"missing native success epilogue "+kind);
            Reject(method,c=>c.RemoveAt(c.FindIndex(i=>Call(i,typeof(AsyncTaskMethodBuilder),"AwaitUnsafeOnCompleted"))),"one missing original registration "+kind);
            Reject(method,c=>c.Add(new CodeInstruction(c.First(i=>Call(i,typeof(AsyncTaskMethodBuilder),"AwaitUnsafeOnCompleted")))),"extra original registration "+kind);
            Reject(method,c=>{var at=c.FindIndex(i=>Call(i,typeof(AsyncTaskMethodBuilder),"AwaitUnsafeOnCompleted"));var m=(MethodInfo)c[at].operand;c[at].operand=m.GetGenericMethodDefinition().MakeGenericMethod(typeof(ValueTaskAwaiter),m.GetGenericArguments()[1]);},"changed registration awaiter type "+kind);
            if(kind<=2)
            {
                Reject(method,c=>c.RemoveAll(i=>Call(i,typeof(CreatureCmd),"Add")),"missing actual creator "+kind);
                Reject(method,c=>c.Add(new CodeInstruction(c.First(i=>Call(i,typeof(CreatureCmd),"Add")))),"duplicate actual creator "+kind);
                if(kind is 1 or 2)Reject(method,c=>{var at=c.FindIndex(i=>i.LoadsConstant(kind==1?3:4));c[at].opcode=OpCodes.Ldc_I4;c[at].operand=9;},"changed native loop bound");
                if(kind<2)Reject(method,c=>c.RemoveAll(i=>i.operand is MethodInfo m&&m.DeclaringType==typeof(PowerCmd)&&m.IsGenericMethod&&m.GetGenericArguments().Contains(typeof(MinionPower))),"missing committed child Minion continuation");
                else Reject(method,c=>c.RemoveAll(i=>Call(i,typeof(MegaCrit.Sts2.Core.Models.Monsters.Wriggler),"set_StartStunned")),"missing native StartStunned");
            }
            else if(kind==3)
            {
                Reject(method,c=>c.RemoveAt(c.FindIndex(i=>Call(i,typeof(MegaCrit.Sts2.Core.Hooks.Hook),"AfterDeath"))),"missing native death dispatcher");
                var nativeCalls=input.Where(i=>i.operand is MethodInfo).Select(i=>i.operand).ToArray();var actualCalls=output.Where(i=>i.operand is MethodInfo m&&m.DeclaringType!=type&&m.Name!="get_Task").Select(i=>i.operand is MethodInfo m&&m.DeclaringType==typeof(SummonRegistration)?typeof(AsyncTaskMethodBuilder).GetMethods().Single(x=>x.Name=="AwaitUnsafeOnCompleted").MakeGenericMethod(m.GetGenericArguments()):(MethodInfo)i.operand).ToArray();
                Check(nativeCalls.SequenceEqual(actualCalls),"Kill native calls remain identical and ordered");
            }
            else if(kind==5)Reject(method,c=>c.RemoveAll(i=>Call(i,typeof(MegaCrit.Sts2.Core.Commands.Builders.AttackCommand),"Execute")),"missing mixed move actual attack");
        }
        var guard=type.GetMethod("CancelAtGate",Flags)!;Check((guard.MethodImplementationFlags&MethodImplAttributes.NoInlining)!=0,"Real guard observation cannot be inlined");
    }
    private static void ActualHandoffAdapter()
    {
        // Identity-only uninitialized sources: no native monster method/gameplay executes.
        // Their Creature/world getters would fail, exposing any pre-gate dereference regression.
        var type=typeof(DomainSummonEffects);var source=(MegaCrit.Sts2.Core.Models.Monsters.Fabricator)RuntimeHelpers.GetUninitializedObject(typeof(MegaCrit.Sts2.Core.Models.Monsters.Fabricator));
        var foreign=(MegaCrit.Sts2.Core.Models.Monsters.Fabricator)RuntimeHelpers.GetUninitializedObject(source.GetType());
        var batchType=type.GetNestedType("Batch",BindingFlags.NonPublic)!;var frameType=type.GetNestedType("Frame",BindingFlags.NonPublic)!;
        var batch=Activator.CreateInstance(batchType,BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic,null,[null,null,false],null)!;
        var store=type.GetField("Tasks",Flags)!.GetValue(null)!;var flags=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
        long epoch=(long)batchType.GetField("Generation",flags)!.GetValue(batch)!;
        var binding=store.GetType().GetMethod("Begin",flags)!.Invoke(store,[batch,epoch,true,source,4])!;
        object Frame(object? b,object subject)=>Activator.CreateInstance(frameType,flags,null,[b,Task.CompletedTask,epoch,subject],null)!;
        var frame=Frame(binding,source);var unknown=Frame(null,source);var marker=Task.FromResult(47);int calls=0;
        object Enter(object subject)=>type.GetMethod("Enter",Flags)!.Invoke(null,[Task.CompletedTask,-1,subject,0,null,false])!;
        object? Binding(object f)=>frameType.GetProperty("Binding",flags)!.GetValue(f);
        Task Forward(object f,Func<MegaCrit.Sts2.Core.Models.Monsters.Fabricator,Task> native)=>(Task)type.GetMethod("Forward",Flags)!.Invoke(null,[source,f,native])!;
        DomainSummonEffects.Reset();
        var returned=Forward(frame,s=>
        {
            calls++;
            var nested=Forward(unknown,_=>{Check(Binding(Enter(source)) is null,"unknown nested Forward shadows ancestor ticket, no world fallback");return marker;});
            Check(ReferenceEquals(nested,marker),"unknown Forward original Task returned once");
            Check(Binding(Enter(foreign)) is null,"wrong subject cannot claim ticket or dereference world");
            var child=Enter(source);var childBinding=Binding(child)!;
            Check(ReferenceEquals(childBinding.GetType().GetField("Payload",flags)!.GetValue(childBinding),batch),"stale exact handoff carries original batch");
            Check((long)childBinding.GetType().GetField("Epoch",flags)!.GetValue(childBinding)! == epoch,"stale handoff never restamps current epoch");
            Check((bool)type.GetMethod("RetiredGate",Flags)!.Invoke(null,[child,"test"])!,"stale child reaches pre-world retirement decision");
            Check(Binding(Enter(source)) is null,"claimed ticket cannot mint current fallback");return marker;
        });
        Check(calls==1&&ReferenceEquals(returned,marker),"actual Forward preserves exactly one helper call/original returned Task");
        type.GetMethod("Close",Flags)!.Invoke(null,[frame]);
        Forward(frame,_=>{var child=Enter(source);var b=Binding(child)!;Check((bool)b.GetType().GetField("Closed",flags)!.GetValue(b)!&&b.GetType().GetField("Payload",flags)!.GetValue(b) is null,"closed handoff remains known detached retirement, not Unknown/new current");return marker;});
        var decision=batchType.GetField("Decision",flags)!.GetValue(batch)!;Check(!(bool)decision.GetType().GetProperty("Cancelled",flags)!.GetValue(decision)!,"retirement and close do not invent domain cancellation");
    }
    private static void ForwardHelpers()
    {
        var owner=typeof(MegaCrit.Sts2.Core.Models.Monsters.Fabricator);var spawn=AccessTools.Method(owner,"SpawnBot");
        var validate=typeof(DomainSummonEffects).GetMethod("ValidateForwardHelper",Flags)!;
        foreach(var (name,fieldName) in new[]{("SpawnAggroBot","aggroSpawns"),("SpawnDefensiveBot","defenseSpawns")})
        {
            var helper=AccessTools.Method(owner,name);var method=helper.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType.GetMethod("MoveNext",BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic)!;
            var field=owner.GetField(fieldName,BindingFlags.Static|BindingFlags.Public)!;var code=PatchProcessor.GetOriginalInstructions(method).ToList();
            validate.Invoke(null,[code,method,spawn,field]);Check(true,"native helper has only pinned static options load before child");
            int at=code.FindIndex(i=>i.Calls(spawn));code.Insert(at-2,new CodeInstruction(OpCodes.Call,AccessTools.PropertyGetter(typeof(MegaCrit.Sts2.Core.Models.MonsterModel),"CombatState")));
            try{validate.Invoke(null,[code,method,spawn,field]);throw new Exception("unsafe pre-child helper call accepted");}catch(TargetInvocationException e) when(e.InnerException is InvalidOperationException){checks++;}
        }
    }
    private static void Combined()
    {
        foreach(bool reverse in new[]{false,true})
        {
            var summon=new Harmony("SummonD17.Combination."+reverse);var revival=new Harmony("RevivalD17.Combination."+reverse);var observer=new Harmony("SummonD17.Observers."+reverse);
            try
            {
                if(reverse){DomainRevivalEffects.InstallPatches(revival);DomainSummonEffects.InstallPatches(summon);}
                else{DomainSummonEffects.InstallPatches(summon);DomainRevivalEffects.InstallPatches(revival);}
                DomainSummonD17Probe.InstallObservers(observer);Check(true,"Actual native both-order combination emission");
                Console.WriteLine("PASS actual combined "+(reverse?"Revival->Summon":"Summon->Revival")+" + independent D17 observers");
            }
            finally{observer.UnpatchAll(observer.Id);summon.UnpatchAll(summon.Id);revival.UnpatchAll(revival.Id);}
        }
    }
    private static void Main(){Decisions();ActualHandoffAdapter();Shapes();ForwardHelpers();Combined();Console.WriteLine($"PASS {checks} summon D17 decision/native IL/mutation/combined checks; native gameplay NOT RUN");}
}
