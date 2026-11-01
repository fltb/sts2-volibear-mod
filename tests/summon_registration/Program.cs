using System.Runtime.CompilerServices;
using System.Diagnostics;
using System.Reflection;
using Volibear.Core;
static class Program
{
    sealed class Batch { internal int Closed; }
    sealed class Control
    {
        internal SummonLifetime<Batch> Life=new();
        internal Batch Batch=new();
        internal bool OwnsBatch=true,Known=true;
        internal SummonLifetime<Batch>.Binding? Binding;
        internal Task? Actual;
        internal Action? Next,BeforeSchedule,BeforeSignal,BeforeBind;
        internal bool Inline;
        internal int State,Registrations,Results,Finally;
        internal long Epoch=1;
        internal Exception? Error;
    }
    readonly struct Awaiter(Control c):ICriticalNotifyCompletion
    {
        public bool IsCompleted=>false;
        public void GetResult(){c.Results++;if(c.Error is {} error)throw error;}
        public void OnCompleted(Action next)=>UnsafeOnCompleted(next);
        public void UnsafeOnCompleted(Action next)
        {
            c.Registrations++;c.Actual=(Task)next.Target!;
            Check(ReferenceEquals(c.Life.Find(c.Actual),c.Binding),"actual box bound BEFORE original schedule");
            c.BeforeSchedule?.Invoke();c.Next=next;if(c.Inline)next();
        }
    }
    struct Machine:IAsyncStateMachine
    {
        internal AsyncTaskMethodBuilder Builder;
        internal Control C;
        internal int State;
        public void SetStateMachine(IAsyncStateMachine machine)=>Builder.SetStateMachine(machine);
        public void MoveNext()
        {
            var c=C; // CLR may clear boxed machine fields during an inline terminal continuation.
            var frame=State==-1?(c.Known?c.Life.Begin(c.Batch,c.Epoch,c.OwnsBatch,c,0):null):c.Life.Find(Builder.Task,c,0);
            c.Binding??=frame;
            Exception? error=null;
            try
            {
                if(State==-1){State=0;var a=new Awaiter(c);c.BeforeBind?.Invoke();SummonRegistration.Await(ref Builder,ref a,ref this,frame);c.Life.VerifyReturn(frame,ref Builder,State);return;}
                Check(ReferenceEquals(frame,c.Binding),"resume does not mint/rebind");new Awaiter(c).GetResult();
                // Repeated SAME registration site/state, as in native summon loops.
                if(++c.State<3){State=0;var a=new Awaiter(c);c.BeforeBind?.Invoke();SummonRegistration.Await(ref Builder,ref a,ref this,frame);c.Life.VerifyReturn(frame,ref Builder,State);return;}
            }
            catch(Exception e){error=e;}
            finally{c.Finally++;}
            State=-2;c.Life.Close(frame,b=>b.Closed++);c.BeforeSignal?.Invoke();
            if(error is null)Builder.SetResult();else Builder.SetException(error);
        }
    }
    sealed class TcsControl
    {
        internal readonly SummonLifetime<Batch> Life=new();
        internal readonly TaskCompletionSource Gate=new();
        internal readonly Batch Batch=new();
        internal SummonLifetime<Batch>.Binding? Binding;
        internal int Results;
    }
    struct TcsMachine:IAsyncStateMachine
    {
        internal AsyncTaskMethodBuilder Builder;
        internal TcsControl C;
        internal int State;
        public void SetStateMachine(IAsyncStateMachine machine)=>Builder.SetStateMachine(machine);
        public void MoveNext()
        {
            var c=C;var binding=State==-1?c.Life.Begin(c.Batch,1,true,c,0):c.Life.Find(Builder.Task,c,0);c.Binding??=binding;
            Exception? error=null;
            try
            {
                var awaiter=c.Gate.Task.GetAwaiter();
                if(State==-1&&!awaiter.IsCompleted){State=0;SummonRegistration.Await(ref Builder,ref awaiter,ref this,binding);c.Life.VerifyReturn(binding,ref Builder,State);return;}
                c.Results++;awaiter.GetResult();
            }
            catch(Exception e){error=e;}
            State=-2;c.Life.Close(binding,b=>b.Closed++);if(error is null)Builder.SetResult();else Builder.SetException(error);
        }
    }
    static void RealTcs()
    {
        foreach(int outcome in new[]{0,1,2})
        {
            var c=new TcsControl();var m=new TcsMachine{Builder=AsyncTaskMethodBuilder.Create(),C=c,State=-1};m.Builder.Start(ref m);var task=m.Builder.Task;
            Check(ReferenceEquals(c.Life.Find(task,c,0),c.Binding)&&!task.IsCompleted,"real TCS pending registration bound actual box before producer completes");
            Check(Catch(()=>c.Life.Find(task,new object(),0)) is InvalidOperationException&&Catch(()=>c.Life.Find(task,c,1)) is InvalidOperationException,"actual task cannot lend another source/kind ownership");
            bool closedInCaller=false;task.GetAwaiter().OnCompleted(()=>closedInCaller=c.Binding!.Closed&&c.Binding.Payload is null);
            var error=new InvalidOperationException("TCS native");if(outcome==0)c.Gate.SetResult();else if(outcome==1)c.Gate.SetException(error);else c.Gate.SetCanceled(new CancellationToken(true));
            var seen=Catch(()=>task.GetAwaiter().GetResult());Check(outcome==0?seen is null:outcome==1?ReferenceEquals(seen,error):task.IsCanceled&&seen is OperationCanceledException,"real TCS original fault/cancel/result");
            Check(SpinWait.SpinUntil(()=>closedInCaller,10000)&&c.Results==1&&c.Batch.Closed==1,"terminal closes before inline caller and GetResult remains once");
            Check(ReferenceEquals(c.Life.Find(task,c,0),c.Binding)&&Catch(()=>c.Life.Find(task,new object(),0)) is InvalidOperationException,"closed tombstone retains weak exact identity without payload");
        }
    }
    static void SharedBatch()
    {
        var root=new Control();var one=new Control{Life=root.Life,Batch=root.Batch,OwnsBatch=false};var two=new Control{Life=root.Life,Batch=root.Batch,OwnsBatch=false};
        var r=Start(root);var a=Start(one);var b=Start(two);
        while(!a.IsCompleted)one.Next!();
        Check(one.Binding!.Payload is null&&root.Batch.Closed==0&&!root.Binding!.Closed&&!two.Binding!.Closed,"real child close releases only child authority, keeps root and sibling open");
        while(!r.IsCompleted)root.Next!();
        Check(root.Binding!.Payload is null&&root.Batch.Closed==1&&ReferenceEquals(two.Binding!.Payload,root.Batch),"root close retires shared batch while committed sibling may finish native continuation");
        Check(Catch(()=>root.Life.Find(b,root,0)) is InvalidOperationException&&Catch(()=>root.Life.Find(b,two,1)) is InvalidOperationException,"shared batch does not merge source/kind identities");
        while(!b.IsCompleted)two.Next!();
        Check(two.Binding!.Payload is null&&root.Batch.Closed==1&&one.Results==3&&two.Results==3,"committed children preserve native results and never double-close root");
    }
    [MethodImpl(MethodImplOptions.NoInlining)]
    static (Task Task,SummonLifetime<Batch> Life,WeakReference Batch,WeakReference Subject) Detached()
    {
        var c=new Control{Inline=true};var task=Start(c);return(task,c.Life,new(c.Batch),new(c));
    }
    static int checks;
    static void Check(bool value,string name){checks++;if(!value)throw new Exception(name);}
    static Exception? Catch(Action action){try{action();return null;}catch(Exception e){return e;}}
    static Task Start(Control c){var m=new Machine{Builder=AsyncTaskMethodBuilder.Create(),C=c,State=-1};m.Builder.Start(ref m);return m.Builder.Task;}
    static void Main()
    {
        RealTcs();SharedBatch();
        var detached=Detached();GC.Collect();GC.WaitForPendingFinalizers();GC.Collect();
        Check(!detached.Batch.IsAlive&&!detached.Subject.IsAlive&&detached.Life.Find(detached.Task) is {Closed:true,Payload:null},"retained completed Task tombstone does not root old batch/source world");
        foreach(bool inline in new[]{false,true})foreach(bool suppress in new[]{false,true})foreach(int outcome in new[]{0,1,2})
        {
            var c=new Control{Inline=inline};c.Error=outcome==1?new InvalidOperationException("native"):outcome==2?new OperationCanceledException(new CancellationToken(true)):null;
            c.BeforeBind=()=>c.Epoch++;c.BeforeSchedule=()=>c.Epoch++;c.BeforeSignal=()=>Check(c.Binding!.Closed&&c.Binding.Payload is null,"close/release payload before original signal");
            Task task;if(suppress){using(ExecutionContext.SuppressFlow())task=Start(c);}else task=Start(c);
            if(!inline)while(!task.IsCompleted){if(suppress){using var done=new ManualResetEventSlim();ThreadPool.UnsafeQueueUserWorkItem(_=>{try{c.Next!();}finally{done.Set();}},null);Check(done.Wait(10000),"suppressed flow resume");}else c.Next!();}
            var error=Catch(()=>task.GetAwaiter().GetResult());Check(outcome==0?error is null:ReferenceEquals(error,c.Error),"native result/error object preserved");
            Check(ReferenceEquals(task,c.Actual)&&ReferenceEquals(c.Life.Find(task),c.Binding),"original returned actual Task retains tombstone");
            Check(c.Binding!.Epoch==1&&c.Binding.Closed&&c.Binding.Payload is null&&c.Batch.Closed==1,"old epoch never reminted; closed value releases batch");
            Check(c.Registrations==(outcome==0?3:1)&&c.Results==c.Registrations&&c.Finally==c.Registrations+1,"same-site loops schedule/GetResult/finally once");
            c.Life.VerifyReturn(c.Binding,task,0);Check(Catch(()=>c.Life.VerifyReturn(c.Binding,new TaskCompletionSource().Task,0)) is InvalidOperationException,"ret cannot supply missing pre-schedule binding");
        }
        var unknown=new Control{Known=false};var unknownTask=Start(unknown);unknown.Epoch++;
        while(!unknownTask.IsCompleted)unknown.Next!();
        Check(unknown.Binding is null&&unknown.Life.Find(unknownTask) is null&&unknown.Results==3&&unknown.Batch.Closed==0,"unknown real box stays native through epoch change without invented close/birth");
        var life=new SummonLifetime<Batch>();var a=life.Begin(new(),1,true);var b=life.Begin(new(),1,true);
        Check(!ReferenceEquals(a,b)&&life.Find(Task.CompletedTask) is null,"cached CompletedTask is never a birth identity");
        Check(life.Find(new TaskCompletionSource().Task) is null,"unknown task remains unknown");
        life.Close(a,x=>x.Closed++);life.Close(a,x=>throw new Exception("double close"));Check(a.Payload is null,"terminal idempotent and detached");
        var subject=new object();var batch=new Batch();var ticket=new SummonTicket<Batch>(batch,0,subject);
        Check(!ticket.TryClaim(1,subject,out _)&&!ticket.TryClaim(0,new object(),out _),"wrong kind/subject cannot claim");
        Check(ticket.TryClaim(0,subject,out var claimed)&&ReferenceEquals(claimed,batch)&&!ticket.TryClaim(0,subject,out _),"exact ticket claimed once without epoch rebirth");
        var outer=new Control();Task? nested=null;outer.BeforeSchedule=()=>{if(nested is null){var child=new Control{Inline=true};nested=Start(child);}};
        var parent=Start(outer);while(!parent.IsCompleted)outer.Next!();Check(nested!.IsCompletedSuccessfully&&parent.IsCompletedSuccessfully,"nested registration keeps both actual boxes");
        Console.WriteLine($"PASS {checks} production Summon registration/lifetime CLR checks; game NOT_RUN");
    }
}
