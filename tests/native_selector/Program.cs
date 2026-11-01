using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Volibear;

int assertions=0;
void Check(bool condition) { assertions++;if(!condition)throw new Exception("Assertion "+assertions); }
void Reject(Action action) { assertions++;try { action(); } catch(InvalidOperationException) { return; } throw new Exception("Missing rejection "+assertions); }
var player=new Player();var source=new CardModel(player);var first=new CardModel(player);var second=new CardModel(player);
var paid=new PlayCardAction(source);RunManager.Instance.ActionExecutor.CurrentlyRunningAction=paid;
var observations=0;
using(var selector=new NativeAutomationSelector(player, request => [request.Options[1]],(request,selected)=> {
    Check(ReferenceEquals(request.Action,paid));Check(selected.Length==1&&ReferenceEquals(selected[0],second));observations++;
}))
{
    Check(ReferenceEquals(CardSelectCmd.Selector,selector));
    var selected=(await selector.GetSelectedCards([first,second],1,1)).ToArray();
    Check(ReferenceEquals(selected[0],second)&&selector.Count==1&&observations==1);
    Reject(()=>new NativeAutomationSelector(player, _=>[]));
    Reject(()=>selector.GetSelectedCards([first,first],1,1));
    Reject(()=>selector.GetSelectedCards([first,new CardModel(new Player())],1,1));
    first.NetworkResolution=second;Reject(()=>selector.GetSelectedCards([first,second],1,1));first.NetworkResolution=null;
    Reject(()=>selector.GetSelectedCards([first,second],2,1));
    Reject(()=>selector.GetSelectedCards([first],2,2));
    RunManager.Instance.ActionExecutor.CurrentlyRunningAction=new PlayCardAction(new CardModel(new Player()));
    Reject(()=>selector.GetSelectedCards([first,second],1,1));RunManager.Instance.ActionExecutor.CurrentlyRunningAction=paid;
    paid.CompletionTask=Task.CompletedTask;Reject(()=>selector.GetSelectedCards([first,second],1,1));
    paid.CompletionTask=new TaskCompletionSource().Task;
}
Check(CardSelectCmd.Selector is null);
foreach(var choose in new Func<NativeAutomationSelector.Selection,IEnumerable<CardModel>>[] {
    _=>[], _=>[first,first], _=>[new CardModel(player)], _=>[first,second]
})
{
    using var selector=new NativeAutomationSelector(player,choose);
    Reject(()=>selector.GetSelectedCards([first,second],1,1));Check(selector.Count==0);
}
RunManager.Instance.ActionExecutor.CurrentlyRunningAction=null;
using(var selector=new NativeAutomationSelector(player,_=>[])) Reject(()=>selector.GetSelectedCards([first],0,1));
using(var selector=new NativeAutomationSelector(player,_=>[],allowTurnChoice:true))
{
    Check(!(await selector.GetSelectedCards([first],0,1)).Any());Check(selector.Count==1);
    Reject(()=>selector.GetSelectedCardReward([],[]));
}
TestMode.IsOn=true;Reject(()=>new NativeAutomationSelector(player,_=>[]));TestMode.IsOn=false;
var lost=new NativeAutomationSelector(player,_=>[]);CardSelectCmd.Selector=null;
Reject(()=>lost.GetSelectedCards([first],0,1));Reject(lost.Dispose);Check(CardSelectCmd.Selector is null);
Console.WriteLine($"NATIVE_SELECTOR_PASS assertions={assertions} native-gameplay=NOT_RUN network-transport=NOT_RUN");
