using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Entities.Creatures;

namespace Volibear;

internal sealed partial class DomainSteamNativeObservation
{
    private readonly CombatHistory _history;
    private readonly CombatHistoryEntry[] _initialHistory;
    private sealed record CapturedEntry(CombatHistoryEntry Entry,int Index,int StageId,int Cursor,object Data);
    private readonly List<CapturedEntry> _entries = [];
    private readonly List<object> _externalHistoryGates = [];
    private T Appended<T>(CombatHistory history, CombatHistoryEntry[] before) where T : CombatHistoryEntry
    {
        var after=history.Entries.ToArray();
        if(!ReferenceEquals(history,_history) || after.Length!=before.Length+1 ||
            !before.Select((entry,index)=>ReferenceEquals(entry,after[index])).All(value=>value) ||
            after[^1].GetType()!=typeof(T) || !ReferenceEquals(after[^1].History,history))
            throw new InvalidOperationException("Native history append/type/reference drift.");
        var actual=(T)after[^1];
        _entries.Add(new(actual,after.Length-1,CurrentStageId,_changes.Count,EntryData(actual)));
        return actual;
    }
    private object EntryData(CombatHistoryEntry entry) => entry switch
    {
        MonsterPerformedMoveEntry move => new { type=entry.GetType().Name,actor=Role(entry.Actor),move=move.Move.Id,targets=move.Targets?.Select(Role).ToArray() },
        CreatureAttackedEntry attack => new { type=entry.GetType().Name,actor=Role(entry.Actor),results=attack.DamageResults.Select(Result).ToArray() },
        DamageReceivedEntry damage => new { type=entry.GetType().Name,actor=Role(entry.Actor),dealer=damage.Dealer is null?null:Role(damage.Dealer),cardSource=damage.CardSource?.GetType().Name,result=Result(damage.Result) },
        _ => throw new InvalidOperationException("Unexpected captured history entry type.")
    };
    private bool Relevant(CombatHistoryEntry entry) => entry switch
    {
        MonsterPerformedMoveEntry move => ReferenceEquals(move.Monster,_boss.Monster),
        CreatureAttackedEntry attack => ReferenceEquals(attack.Actor,_boss),
        DamageReceivedEntry damage => ReferenceEquals(damage.Dealer,_boss) || ReferenceEquals(damage.Dealer,_player)&&ReferenceEquals(damage.Receiver,_boss),
        _ => false
    };
    private object HistorySnapshot()
    {
        var final=_history.Entries.ToArray();
        var identities=new Dictionary<CombatHistoryEntry,int>(ReferenceEqualityComparer.Instance);
        int Identity(CombatHistoryEntry entry)
        { if(!identities.TryGetValue(entry,out var id)) identities.Add(entry,id=identities.Count+1); return id; }
        object ReferenceRow(CombatHistoryEntry entry,int index) => new {index,referenceId=Identity(entry),type=entry.GetType().Name,sameHistory=ReferenceEquals(entry.History,_history)};
        var initialReferences=_initialHistory.Select(ReferenceRow).ToArray();
        var allFinalReferences=final.Select(ReferenceRow).ToArray();
        return new {
            initialReferences, allFinalReferences, finalContentScope="related-move-attack-damage-subset;all-kinds-reference-inventory-only",
            initialCount=_initialHistory.Length, finalCount=final.Length,
            initialReferencesIntact=final.Length>=_initialHistory.Length && _initialHistory.Select((entry,index)=>ReferenceEquals(entry,final[index])).All(value=>value),
            captured=_entries.Select(row=>new { index=row.Index,referenceId=Identity(row.Entry),stageId=row.StageId,changeCursor=row.Cursor,data=row.Data,
                sameReferenceAtEnd=row.Index<final.Length&&ReferenceEquals(final[row.Index],row.Entry),
                sameHistoryAtEnd=ReferenceEquals(row.Entry.History,_history),finalData=EntryData(row.Entry) }).ToArray(),
            actualFinal=final.Select((entry,index)=>(entry,index)).Where(row=>row.index>=_initialHistory.Length&&Relevant(row.entry)).Select(row=>new {index=row.index,data=EntryData(row.entry)}).ToArray(),
            externalPlayerToBoss=final.Skip(_initialHistory.Length).OfType<DamageReceivedEntry>().Where(entry=>ReferenceEquals(entry.Dealer,_player)&&ReferenceEquals(entry.Receiver,_boss)).Select(EntryData).ToArray(),
            externalHistoryGates=_externalHistoryGates.ToArray()
        };
    }
    private static bool ObserveHistoryEnding(bool original, Creature? dealer, IEnumerable<Creature> targets)
    {
        if(Active is { } active && ReferenceEquals(dealer,active._player) && targets is IReadOnlyList<Creature> list && list.Count==1 && ReferenceEquals(list[0],active._boss))
            active._externalHistoryGates.Add(new { isEnding=original,bossHp=active._boss.CurrentHp,stageId=active.CurrentStageId,changeCursor=active._changes.Count });
        return original; // Observe the existing native getter; never query ending recursively or alter the branch.
    }
    private static IEnumerable<CodeInstruction> DamageHistoryBranch(IEnumerable<CodeInstruction> input, MethodBase __originalMethod)
    {
        var ending=AccessTools.PropertyGetter(typeof(CombatManager),nameof(CombatManager.IsEnding));
        var fields=__originalMethod.DeclaringType!.GetFields(BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic);
        var dealer=fields.Single(field=>field.Name=="dealer"); var targets=fields.Single(field=>field.Name=="targets");
        var result=new List<CodeInstruction>(); var count=0;
        foreach(var instruction in input)
        {
            result.Add(instruction);
            if(!instruction.Calls(ending)) continue;
            result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld,dealer));
            result.Add(new(OpCodes.Ldarg_0)); result.Add(new(OpCodes.Ldfld,targets));
            result.Add(new(OpCodes.Call,AccessTools.Method(typeof(DomainSteamNativeObservation),nameof(ObserveHistoryEnding)))); count++;
        }
        if(count!=1) throw new InvalidOperationException("Native Damage history-ending branch drift.");
        return result;
    }
}
