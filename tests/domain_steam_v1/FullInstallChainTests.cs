using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

internal static class SteamFullInstallChainTests
{
    internal static void Run()
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static;
        Type[] expectedInstallers =
        [
            typeof(EngageCmd), typeof(CardResolutionHooks), typeof(DomainEnemyEffects),
            typeof(DomainHopperEffects), typeof(BeastForms), typeof(AttackHistory),
            typeof(TargetCosts), typeof(PersistentBlockHooks), typeof(DomainSummonEffects),
            typeof(DomainRevivalEffects), typeof(DomainPassiveEffects), typeof(DomainCardContributions),
            typeof(DomainDampenTransactions), typeof(DomainSteamEruptionEffects),
            typeof(DomainPlayerStatContributions), typeof(DomainPlayerDebuffContributions),
            typeof(DomainEnemyStatusContributions), typeof(DomainEnemySpecialContributions),
            typeof(DomainAdditionalRevivalEffects), typeof(Volibear.Presentation.VolibearPresentationBridge),
            typeof(Volibear.Presentation.VolibearInspectPortraits),
        ];
        var main=typeof(Volibear.ModEntry).GetMethod("Initialize")!;
        // Derive the actual main Install calls, including dynamic Beast discovery and
        // Presentation's nested Audio installation. Do not manufacture a subset list.
        var startup=PatchProcessor.GetOriginalInstructions(main).TakeWhile(c=>c.operand is not MethodInfo m ||
            m.DeclaringType!=typeof(Environment) || m.Name!=nameof(Environment.GetEnvironmentVariable)).ToArray();
        var installs=startup.Select(c=>c.operand).OfType<MethodInfo>().Where(m=>m.IsStatic&&m.Name=="Install"&&m.GetParameters().Length==0).ToArray();
        int checks=0;
        void Need(bool value,string message){checks++;if(!value)throw new Exception(message);}
        MethodInfo Method(Type type,string name)=>AccessTools.Method(type,name);
        MethodInfo Machine(MethodInfo method)=>Method(method.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType,"MoveNext");
        var attack=Machine(Method(typeof(AttackCommand),nameof(AttackCommand.Execute)));
        var steam=typeof(DomainSteamEruptionEffects); var cards=typeof(CardResolutionHooks);
        var baseline=Harmony.GetAllPatchedMethods().SelectMany(m=>Harmony.GetPatchInfo(m)!.Owners).ToHashSet();
        void Check()
        {
            var code=PatchProcessor.GetCurrentInstructions(attack).ToArray();
            Need(code.Count(c=>c.Calls(Method(steam,"DamageFromCommand")))==1,"one cooperative AttackCommand callsite");
            Need(!code.Any(c=>c.Calls(CardResolutionHooks.OrdinaryAttackCallsiteV1)),"canonical ordinary call replaced exactly once");
            Need(!code.Any(c=>c.Calls((MethodInfo)steam.GetField("NativeDamage",flags)!.GetValue(null)!)),"no parallel raw damage path");
            var info=Harmony.GetPatchInfo(attack)!;
            Need(info.Transpilers.Single(p=>p.owner==DomainSteamEruptionEffects.HarmonyId).after.Contains(CardResolutionHooks.OrdinaryAttackOwnerV1),"explicit real CardResolution owner ordering");
            Need(info.Transpilers.Count(p=>p.owner==CardResolutionHooks.OrdinaryAttackOwnerV1)==1,"CardResolution callsite remains installed");
            var play=Machine(Method(typeof(CardModel),nameof(CardModel.OnPlayWrapper)));
            var playCode=PatchProcessor.GetCurrentInstructions(play).ToArray();
            Need(playCode.Count(c=>c.Calls(Method(cards,"EnterPlayMove")))==1 && playCode.Any(c=>c.Calls(Method(cards,"LeavePlayMove"))),"paid play lifecycle retained with all owners");
            var pipeline=PatchProcessor.GetOriginalInstructions(Machine(Method(cards,"OrdinaryAttackPipelineV1"))).ToList();
            var dispatch=pipeline.FindIndex(c=>c.operand is MethodInfo m&&m.Name=="Invoke"&&m.DeclaringType?.Name.StartsWith("Func`")==true);
            var domain=pipeline.FindIndex(c=>c.Calls(Method(typeof(DomainPower),"AttachAfterOrdinarySegment")));
            var responders=pipeline.FindIndex(c=>c.operand is MethodInfo m&&m.DeclaringType==typeof(IOrdinarySegmentResponder)&&m.Name=="AfterOrdinarySegment");
            Need(dispatch>=0&&domain>dispatch&&responders>domain,"native dispatch then complete Domain/ordinary responder pipeline");
            var wrapper=PatchProcessor.GetOriginalInstructions(Method(steam,"DamageFromCommand")).ToArray();
            Need(wrapper.Count(c=>c.Calls(Method(cards,"OrdinaryAttackPipelineV1")))==1,"Steam always enters complete ordinary pipeline");
            Need(!wrapper.Any(c=>c.operand is FieldInfo field&&field.Name=="PendingDamage"),"no handoff ticket spans ordinary pipeline");
            var draw=typeof(MegaCrit.Sts2.Core.Commands.CardPileCmd).GetMethods().Single(m=>m.Name=="Draw"&&m.GetParameters().Length==4);
            var drawCode=PatchProcessor.GetCurrentInstructions(Machine(draw)).ToArray();
            Need(drawCode.Count(c=>c.Calls(Method(cards,"AddDrawnCard")))==1&&drawCode.Count(c=>c.Calls(Method(cards,"DispatchDrawHooks")))==1,"draw and purification wrappers retained");
            var audio=typeof(Volibear.Presentation.PowerAudioReceipts);
            var bodies=(IEnumerable<MethodInfo>)audio.GetMethod("NativeBodies",flags)!.Invoke(null,null)!;
            foreach(var body in bodies)
            {
                var il=PatchProcessor.GetCurrentInstructions(body).ToList();
                var signals=il.Select((c,i)=>(c,i)).Where(x=>x.c.operand is MethodInfo m&&m.DeclaringType?.Name.StartsWith("AsyncTaskMethodBuilder")==true&&m.Name is "SetResult" or "SetException").Select(x=>x.i).ToArray();
                var closes=il.Select((c,i)=>(c,i)).Where(x=>x.c.Calls(Method(audio,"Close"))).Select(x=>x.i).ToArray();
                Need(signals.Length==2&&closes.Length==2,"one audio Close per terminal signal branch");
                int previous=-1;
                foreach(var signal in signals)
                {
                    var own=closes.Where(i=>i>previous&&i<signal).ToArray();
                    Need(own.Length==1,"audio close precedes its signal, not required adjacent");
                    var dampen=il.Select((c,i)=>(c,i)).Where(x=>x.i>previous&&x.i<signal&&x.c.Calls(Method(typeof(DomainDampenTransactions),"CloseApply"))).ToArray();
                    if(dampen.Length>0) Need(dampen.Length==1&&dampen[0].i>own[0],"Audio Close then Dampen CloseApply then signal");
                    previous=signal;
                }
            }
        }
        try
        {
            Need(installs.Select(m=>m.DeclaringType).SequenceEqual(expectedInstallers),"current ModEntry normal Install manifest matches all 21 production adapters in order");
            foreach(var method in installs)
            {
                Console.WriteLine("STEAM_MAIN_INSTALL_EMIT "+method.DeclaringType!.FullName+"."+method.Name);
                method.Invoke(null,null);
            }
            Check();
            // Actual source installed once in its normal sequence. Recompose only this
            // cooperating pair in both relative orders while every other owner stays on.
            foreach(var steamFirst in new[]{true,false})
            {
                new Harmony(DomainSteamEruptionEffects.HarmonyId).UnpatchAll(DomainSteamEruptionEffects.HarmonyId);
                new Harmony(CardResolutionHooks.OrdinaryAttackOwnerV1).UnpatchAll(CardResolutionHooks.OrdinaryAttackOwnerV1);
                steam.GetField("_installed",flags)!.SetValue(null,false); cards.GetField("_installed",flags)!.SetValue(null,false);
                if(steamFirst){DomainSteamEruptionEffects.Install();CardResolutionHooks.Install();}
                else{CardResolutionHooks.Install();DomainSteamEruptionEffects.Install();}
                Check();
            }
            var manifest=Harmony.GetAllPatchedMethods().SelectMany(method=>Harmony.GetPatchInfo(method)!.Owners.Select(owner=>(owner,method))).GroupBy(x=>x.owner).OrderBy(g=>g.Key);
            foreach(var group in manifest) Console.WriteLine($"STEAM_MAIN_OWNER owner={group.Key} methods={group.Select(x=>x.method).Distinct().Count()}");
            Console.WriteLine($"STEAM_FULL_INSTALL_CHAIN_EMISSION_PASS installers={installs.Length} pair-orders=2 checks={checks} registration-and-BaseLib-runtime=NOT_RUN gameplay=NOT_RUN");
        }
        finally
        {
            foreach(var owner in Harmony.GetAllPatchedMethods().SelectMany(m=>Harmony.GetPatchInfo(m)!.Owners).Distinct().Where(owner=>!baseline.Contains(owner)).ToArray())
                new Harmony(owner).UnpatchAll(owner);
        }
    }
}
