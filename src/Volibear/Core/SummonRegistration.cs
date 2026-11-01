using System;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
namespace Volibear.Core;

internal interface ISummonRegistration { void BindBeforeSchedule(Task actual); }

// Summon A: actual CLR box transport only. No source-dispatch/history/observer authority.
internal static class SummonRegistration
{
    private struct BoundAwaiter<TAwaiter,TMachine>(TAwaiter native,ISummonRegistration receipt):ICriticalNotifyCompletion
        where TAwaiter:ICriticalNotifyCompletion where TMachine:IAsyncStateMachine
    {
        private TAwaiter native=native;
        private void Bind(Action continuation)
        {
            if(continuation.Target is not Task actual||Array.IndexOf(actual.GetType().GenericTypeArguments,typeof(TMachine))<0)
                throw new InvalidOperationException("Summon exact CLR state-machine Task box mismatch");
            receipt.BindBeforeSchedule(actual);
        }
        public void OnCompleted(Action continuation){Bind(continuation);native.OnCompleted(continuation);}
        public void UnsafeOnCompleted(Action continuation){Bind(continuation);native.UnsafeOnCompleted(continuation);}
    }
    internal static void Await<TAwaiter,TMachine>(ref AsyncTaskMethodBuilder builder,ref TAwaiter native,ref TMachine machine,ISummonRegistration? receipt)
        where TAwaiter:ICriticalNotifyCompletion where TMachine:IAsyncStateMachine
    {
        if(receipt is null){builder.AwaitUnsafeOnCompleted(ref native,ref machine);return;}
        var bound=new BoundAwaiter<TAwaiter,TMachine>(native,receipt);
        builder.AwaitUnsafeOnCompleted(ref bound,ref machine);
    }
}

internal sealed class SummonLifetime<T> where T:class
{
    readonly object sync=new();
    readonly ConditionalWeakTable<Task,Binding> tasks=new();
    internal sealed class Binding(SummonLifetime<T> store,T? payload,long epoch,bool ownsBatch):ISummonRegistration
    {
        internal T? Payload=payload;
        internal readonly long Epoch=epoch;
        internal readonly bool OwnsBatch=ownsBatch;
        internal bool Closed;
        internal WeakReference<Task>? Actual;
        internal WeakReference<object>? Subject;
        internal int Kind=-1;
        public void BindBeforeSchedule(Task actual)=>store.Bind(this,actual);
    }
    // Birth is an explicit local; neither provisional nor cached returned Tasks allocate identities.
    internal Binding Begin(T payload,long epoch,bool ownsBatch,object? subject=null,int kind=-1)=>new(this,payload,epoch,ownsBatch){Subject=subject is null?null:new(subject),Kind=kind};
    internal Binding Retired(long epoch,object? subject=null,int kind=-1)=>new(this,null,epoch,false){Closed=true,Subject=subject is null?null:new(subject),Kind=kind};
    internal Binding? Find(Task actual,object? subject=null,int kind=-1)
    {
        lock(sync)
        {
            if(!tasks.TryGetValue(actual,out var binding))return null;
            if(subject is not null&&(binding.Kind!=kind||binding.Subject is not {} weak||!weak.TryGetTarget(out var original)||!ReferenceEquals(original,subject)))throw new InvalidOperationException("Summon actual box source/kind mismatch");
            return binding;
        }
    }
    void Bind(Binding binding,Task actual)
    {
        lock(sync)
        {
            if(binding.Actual is {} weak&&(!weak.TryGetTarget(out var prior)||!ReferenceEquals(prior,actual)))throw new InvalidOperationException("Summon actual box changed");
            if(tasks.TryGetValue(actual,out var old)){if(!ReferenceEquals(old,binding))throw new InvalidOperationException("Summon actual box collision");}
            else tasks.Add(actual,binding);
            binding.Actual??=new(actual); // A closed binding stays a detached tombstone, never reopens.
        }
    }
    internal void VerifyReturn(Binding? binding,ref AsyncTaskMethodBuilder builder,int state)
    {
        // Inline completion can clear the boxed machine before its outer registration call returns.
        // A closed receipt needs no new Task getter or return-time authorization.
        if(binding is null||binding.Closed)return;
        VerifyReturn(binding,builder.Task,state);
    }
    internal void VerifyReturn(Binding? binding,Task actual,int state)
    {
        if(binding is null)return;
        lock(sync)
        {
            if(state>=0&&(!tasks.TryGetValue(actual,out var bound)||!ReferenceEquals(bound,binding)))throw new InvalidOperationException("Missing Summon pre-schedule actual-box binding");
            if(state==-2&&!binding.Closed)throw new InvalidOperationException("Summon terminal signal did not close ownership");
        }
    }
    internal void Close(Binding? binding,Action<T> closeBatch)
    {
        if(binding is null)return;
        lock(sync)
        {
            if(binding.Closed)return;
            binding.Closed=true;var payload=binding.Payload;binding.Payload=null;
            if(binding.OwnsBatch&&payload is not null)closeBatch(payload);
        }
    }
}

internal sealed class SummonTicket<T>(T? payload,int kind,object subject) where T:class
{
    int claimed;
    internal bool TryClaim(int requestedKind,object requestedSubject,out T? value)
    {
        value=null;
        if(payload is null||requestedKind!=kind||!ReferenceEquals(subject,requestedSubject)||Interlocked.Exchange(ref claimed,1)!=0)return false;
        value=payload;return true;
    }
}
