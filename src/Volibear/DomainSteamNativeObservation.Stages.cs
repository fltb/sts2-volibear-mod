using System;
using System.Collections.Generic;
using System.Threading;

namespace Volibear;

internal sealed partial class DomainSteamNativeObservation
{
    private sealed record NativeStage(int Id,string Name,NativeStage? Parent);
    private readonly AsyncLocal<NativeStage?> _stage = new();
    private readonly List<object> _stageEvents = [];
    private int _stageSerial;
    private int CurrentStageId => _stage.Value?.Id ?? 0;
    internal static int EventCursor => Active?._changes.Count ?? 0;
    internal static int StageIdentity => Active?.CurrentStageId ?? 0;
    internal IDisposable BeginStage(string name)
    {
        var stage=new NativeStage(++_stageSerial,name,_stage.Value); _stage.Value=stage;
        _stageEvents.Add(new { kind="begin",id=stage.Id,parent=stage.Parent?.Id??0,name,changeCursor=_changes.Count });
        return new StageLease(this,stage);
    }
    internal static IDisposable BeginFixtureStage(string name) => Active?.BeginStage(name) ?? throw new InvalidOperationException("No active native observation.");
    private sealed class StageLease(DomainSteamNativeObservation observer,NativeStage stage) : IDisposable
    {
        public void Dispose()
        {
            if(!ReferenceEquals(observer._stage.Value,stage)) throw new InvalidOperationException("Native observation stage ancestry mismatch.");
            observer._stageEvents.Add(new {kind="end",id=stage.Id,parent=stage.Parent?.Id??0,name=stage.Name,changeCursor=observer._changes.Count});
            observer._stage.Value=stage.Parent;
        }
    }
}
