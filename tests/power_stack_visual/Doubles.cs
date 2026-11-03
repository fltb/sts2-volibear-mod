using System.Runtime.CompilerServices;
namespace Godot {
public class GodotObject { public static bool IsInstanceValid(object? value)=>value is not null; }
public readonly record struct Vector2(float X,float Y) {
 public static Vector2 One=>new(1,1); public static Vector2 Left=>new(-1,0);
 public static Vector2 operator +(Vector2 a,Vector2 b)=>new(a.X+b.X,a.Y+b.Y);
 public static Vector2 operator *(Vector2 a,float n)=>new(a.X*n,a.Y*n);
 public static Vector2 operator /(Vector2 a,float n)=>new(a.X/n,a.Y/n);
}
public static class Mathf { public static int CeilToInt(float n)=>(int)MathF.Ceiling(n); public static float Floor(float n)=>MathF.Floor(n); public static float Max(float a,float b)=>MathF.Max(a,b); public static float Min(float a,float b)=>MathF.Min(a,b); }
public class Control:GodotObject {
 public bool Visible=true; public Vector2 Size=new(32,32),Position,Scale=Vector2.One;
 private bool inside,ready; public List<Control> Children=[];
 public event Action? TreeEntered,TreeExiting;
 public virtual void _EnterTree(){} public virtual void _Ready(){} public virtual void _ExitTree(){}
 public bool IsInsideTree()=>inside; public bool IsNodeReady()=>ready;
 public void Enter(){inside=true;_EnterTree();TreeEntered?.Invoke();foreach(var c in Children)c.Enter();if(!ready){ready=true;_Ready();}}
 public void Exit(){foreach(var c in Children)c.Exit();TreeExiting?.Invoke();_ExitTree();inside=false;}
 public void AddChild(Control c){Children.Add(c);if(inside)c.Enter();}
 public void RemoveChild(Control c){if(c.IsInsideTree())c.Exit();Children.Remove(c);}
 public virtual T? GetNodeOrNull<T>(string path) where T:class=>null;
}
public class TextureRect:Control{}
}
namespace MegaCrit.Sts2.addons.mega_text {public class MegaLabel {public string Text="";public void SetTextAutoSize(string text)=>Text=text;}}
namespace MegaCrit.Sts2.Core.HoverTips {
using MegaCrit.Sts2.Core.Models;
public interface IHoverTip {string Id{get;}}
public struct HoverTip:IHoverTip {public string Id{get;set;}="";public string? Title{get;set;}public string Description;public bool IsSmart;
 public HoverTip(PowerModel model,string description,bool smart=false){Id=model.Id;Title=model.Title;Description=description;IsSmart=smart;}
}
}
namespace MegaCrit.Sts2.Core.Entities.Creatures {
using MegaCrit.Sts2.Core.Models;using MegaCrit.Sts2.Core.Nodes.Combat;
public class Creature {public readonly List<PowerModel> Powers=[]; public NCreature Node=null!;}
}
namespace MegaCrit.Sts2.Core.Models {
using MegaCrit.Sts2.Core.Entities.Creatures;using MegaCrit.Sts2.Core.HoverTips;
public class PowerModel {
 public string Id="MOD_A",Title="state";public Creature Owner=null!;public bool IsCanonical,Supported=true,IsVisible=true,Suppressed;public int Amount;
 public IEnumerable<IHoverTip> HoverTips=>new IHoverTip[]{new HoverTip(this,"native "+Amount)};
}
}
namespace MegaCrit.Sts2.Core.Combat {
public class CombatState{}
public class Tracker {public event Action<CombatState>? CombatStateChanged;public int Count=>CombatStateChanged?.GetInvocationList().Length??0;public void Notify()=>CombatStateChanged?.Invoke(new());}
public class CombatManager {public static CombatManager Instance{get;}=new();public Tracker StateTracker=new();}
}
namespace MegaCrit.Sts2.Core.Nodes.Rooms {
using MegaCrit.Sts2.Core.Entities.Creatures;using MegaCrit.Sts2.Core.Nodes.Combat;
public class NCombatRoom {public static NCombatRoom? Instance{get;}=new();public NCreature GetCreatureNode(Creature c)=>c.Node;}
}
namespace MegaCrit.Sts2.Core.Nodes.Combat {
using Godot;using MegaCrit.Sts2.Core.Models;using MegaCrit.Sts2.Core.Entities.Creatures;using MegaCrit.Sts2.Core.HoverTips;using MegaCrit.Sts2.Core.Combat;using MegaCrit.Sts2.addons.mega_text;
public class NCreature:Control {public Creature Entity=new();public IHoverTip[] Shown=[];public NCreature(){Entity.Node=this;}
 [MethodImpl(MethodImplOptions.NoInlining)] public void ShowHoverTips(IEnumerable<IHoverTip> hoverTips)=>Shown=hoverTips.ToArray();public void HideHoverTips()=>Shown=[];
}
public class NPower:Control {
 private PowerModel? _model;private MegaLabel? _amountLabel;private readonly TextureRect icon=new();public NPowerContainer? Container;public int GetterReads;
 public PowerModel Model{get{GetterReads++;return _model??throw new InvalidOperationException("unbound getter");}[MethodImpl(MethodImplOptions.NoInlining)]set{if(value.IsCanonical)throw new InvalidOperationException("canonical");_model=value;if(IsNodeReady())RefreshAmount();}}
 [MethodImpl(MethodImplOptions.NoInlining)] public override void _Ready(){_amountLabel=new();RefreshAmount();}
 [MethodImpl(MethodImplOptions.NoInlining)] private void RefreshAmount(){if(_amountLabel is not null)_amountLabel.SetTextAutoSize(_model?.Amount.ToString()??"");}
 public void AmountChanged()=>RefreshAmount();
 public override T? GetNodeOrNull<T>(string path) where T:class=>icon as T;
 [MethodImpl(MethodImplOptions.NoInlining)] private void OnHovered(){Model.Owner.Node.ShowHoverTips(Model.HoverTips);icon.Scale=new(1.1f,1.1f);CombatManager.Instance.StateTracker.CombatStateChanged+=ShowPowerHoverTips;}
 [MethodImpl(MethodImplOptions.NoInlining)] private void OnUnhovered(){Model.Owner.Node.HideHoverTips();icon.Scale=Vector2.One;CombatManager.Instance.StateTracker.CombatStateChanged-=ShowPowerHoverTips;}
 [MethodImpl(MethodImplOptions.NoInlining)] private void ShowPowerHoverTips(CombatState _)=>Model.Owner.Node.ShowHoverTips(Model.HoverTips);
 public void Hover()=>OnHovered();public void Unhover()=>OnUnhovered();
}
public class NPowerContainer:Control {
 private readonly List<NPower> _powerNodes=[];private Vector2? _originalPosition=new(0,0);
 public IReadOnlyList<NPower> All=>_powerNodes;
 [MethodImpl(MethodImplOptions.NoInlining)] public override void _EnterTree(){}
 public NPower Add(PowerModel p){var n=new NPower{Model=p,Container=this};_powerNodes.Add(n);AddChild(n);UpdatePositions();return n;}
 public void Remove(PowerModel p){var n=_powerNodes.First(n=>n.Model==p);_powerNodes.Remove(n);UpdatePositions();RemoveChild(n);}
 [MethodImpl(MethodImplOptions.NoInlining)] private void UpdatePositions(){
 if(_powerNodes.Count!=0){float x=_powerNodes[0].Size.X;float b=Mathf.CeilToInt(Size.X/x);b=Mathf.Max(Mathf.CeilToInt((float)_powerNodes.Count/2f),b);
 for(int i=0;i<_powerNodes.Count;i++)_powerNodes[i].Position=new Vector2(x*((float)i%b),Mathf.Floor((float)i/b)*x);
 float num=x*Mathf.Min(b,_powerNodes.Count);Position=(_originalPosition??Position)+Vector2.Left*Mathf.Max(0f,num-Size.X)/2f;}}
}
}
namespace Volibear.Presentation {
using MegaCrit.Sts2.Core.Models;using MegaCrit.Sts2.Core.HoverTips;
internal sealed record PowerStackProjection(IReadOnlyList<PowerModel> Members,string AmountText,string Description);
internal static class PowerStackPresentation {internal static bool TryDescribe(PowerModel p,out PowerStackProjection projection){
 projection=null!;if(p.IsCanonical||!p.Supported||p.Owner is null||!p.Owner.Powers.Contains(p))return false;
 var members=p.Owner.Powers.Where(n=>n.Supported&&!n.IsCanonical&&n.IsVisible&&n.Id==p.Id&&n.GetType()==p.GetType()).ToArray();
 projection=new(members,members.Sum(n=>n.Amount).ToString(),"aggregate "+members.Sum(n=>n.Amount));return true;}}
internal static class PowerPresentationDisabled {internal static IEnumerable<IHoverTip> PowerTips(PowerModel p,IEnumerable<IHoverTip> tips){foreach(var t in tips){if(p.Suppressed&&t is HoverTip h)yield return new HoverTip(p,h.Description+" 已被领域禁用",h.IsSmart);else yield return t;}}}
}
