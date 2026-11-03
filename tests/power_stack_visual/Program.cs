using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using Volibear.Presentation;
static class Program {
 static int checks;static void Need(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static PowerModel Make(NCreature creature,int amount,string id="MOD_A",bool supported=true){var p=new PowerModel{Owner=creature.Entity,Amount=amount,Id=id,Supported=supported};creature.Entity.Powers.Add(p);return p;}
 static string Description(NCreature c)=>string.Join("|",c.Shown.OfType<HoverTip>().Select(t=>t.Description));
 static void OwnKeywordChecks(){
 foreach(var (key,title) in new[]{("UNBREAKABLE","坚甲"),("DOMAIN","领域"),("THUNDER_ARMOR","雷甲")}){
  var creature=new NCreature();var model=Make(creature,3,"MOD_"+key);model.Title=title;model.Suppressed=true;
  var main=new HoverTip(model,"original main",true);
  var own=new HoverTip(model,"own glossary"){Id="VOLIBEAR-"+key};
  var lightning=new HoverTip(model,"lightning glossary"){Id="VOLIBEAR-LIGHTNING",Title="雷伤"};
  var suppression=new HoverTip(model,"suppression glossary"){Id="VOLIBEAR-SUPPRESSION",Title="领域压制"};
  var foreign=new HoverTip(model,"foreign glossary"){Id="THIRD_PARTY_HINT"};
  var unknown=new HoverTip(model,"unknown glossary"){Id="VOLIBEAR-NOT_A_KNOWN_MECHANIC"};
  var near=new HoverTip(model,"near title"){Id="VOLIBEAR-"+key,Title=title+" "};
  creature.ShowHoverTips(new IHoverTip[]{own,lightning,main,suppression,foreign,unknown,near});
  var shown=creature.Shown.OfType<HoverTip>().ToArray();
  Need(shown.Length==6&&!shown.Any(t=>t.Id==own.Id&&t.Title==title),key+": only own exact-title glossary removed regardless of order");
  Need(shown.Any(t=>t.Id==lightning.Id)&&shown.Any(t=>t.Id==suppression.Id)&&shown.Any(t=>t.Title==title+" "),key+": distinct titles and exact-match boundary preserved");
  Need(shown.Any(t=>t.Id==foreign.Id)&&shown.Any(t=>t.Id==unknown.Id),key+": third-party and unregistered prefix entries retained");
  Need(shown.Single(t=>t.Id==model.Id).Description=="aggregate 3 已被领域禁用"&&shown.Single(t=>t.Id==model.Id).IsSmart,key+": aggregate main keeps disabled badge and smart flag");
  creature.ShowHoverTips(creature.Shown);
  Need(shown.SequenceEqual(creature.Shown.OfType<HoverTip>()),key+": self-keyword cleanup is idempotent");
  creature.ShowHoverTips(new IHoverTip[]{own,lightning});
  Need(creature.Shown.Length==2,key+": owner possessing a power alone does not remove glossary without its main tip");
 }
 }
 static void Main(){
 PowerStackVisual.Install();PowerStackVisual.Install();OwnKeywordChecks();
 Need(Harmony.GetPatchInfo(AccessTools.PropertyGetter(typeof(PowerModel),nameof(PowerModel.HoverTips))) is null,"No global model hover patch");
 var creature=new NCreature();var container=new NPowerContainer{Size=new(128,32)};container.Enter();
 var tracker=CombatManager.Instance.StateTracker;
 Need(tracker.Count==1,"One container state subscription");
 var a=Make(creature,3);var na=container.Add(a);var b=Make(creature,4);var nb=container.Add(b);
 var foreign=Make(creature,9,"FOREIGN",false);var nf=container.Add(foreign);
 Need(container.All.Count==3&&creature.Entity.Powers.Count==3&&a.Amount==3&&b.Amount==4,"All native nodes and model amounts retained");
 Need(na.Visible&&!nb.Visible&&nf.Visible,"One representative plus unchanged third-party node");
 Need(PowerStackVisual.DisplayedAmount(na)=="7"&&PowerStackVisual.DisplayedAmount(nb)=="7","Aggregate labels on representative and reusable hidden node");
 Need(na.Position.X==0&&nf.Position.X==32,"Hidden duplicate consumes no native layout slot");
 Need(PowerStackVisual.DisplayedAmount(nf)=="9"&&foreign.HoverTips.OfType<HoverTip>().Single().Description=="native 9","Third-party label and model hover untouched");
 a.Suppressed=true;
 creature.ShowHoverTips(a.HoverTips.Concat(b.HoverTips).Concat(foreign.HoverTips));
 Need(creature.Shown.Count()==2&&Description(creature)=="aggregate 7 已被领域禁用|native 9","Only supported main tips coalesce, disabled badge and foreign tip retained");
 creature.ShowHoverTips(creature.Shown);
 Need(creature.Shown.Count()==2&&Description(creature)=="aggregate 7 已被领域禁用|native 9","UI projection is idempotent");
 Need(a.HoverTips.OfType<HoverTip>().Single().Description=="native 3","Outside-UI native model text unchanged");
 Need(PowerStackVisual.DisplayedTips(na).OfType<HoverTip>().Single().Description=="aggregate 7 已被领域禁用","Probe helper matches displayed main tip");
 na.Hover();Need(tracker.Count==2,"Native hovered callback kept");na.Hover();Need(tracker.Count==2,"Repeated hover does not duplicate native callback");
 b.Amount=6;nb.AmountChanged();
 Need(PowerStackVisual.DisplayedAmount(na)=="9"&&Description(creature)=="aggregate 9 已被领域禁用","Hidden member amount event refreshes visible amount and open tip immediately");
 creature.Entity.Powers.Remove(a);container.Remove(a);
 Need(nb.Visible&&container.All.Count==2&&nb.Position.X==0&&nf.Position.X==32,"Representative removal promotes next node and compacts layout");
 Need(PowerStackVisual.DisplayedAmount(nb)=="6"&&tracker.Count==1,"Removed hovered representative unsubscribes");
 creature.Entity.Powers.Remove(b);container.Remove(b);
 Need(container.All.Count==1&&nf.Visible&&nf.Position.X==0,"Last member removal leaves no phantom representative");
 var c=Make(creature,2);var nc=container.Add(c);var d=Make(creature,5);var nd=container.Add(d);
 container.Exit();Need(tracker.Count==0&&nd.Visible,"Exit unsubscribes and releases only our hidden visibility");
 container.Enter();Need(tracker.Count==1&&nc.Visible&&!nd.Visible&&PowerStackVisual.DisplayedAmount(nc)=="7","Tree reentry groups again without Ready replay");
 nd.Model=foreign;Need(nd.Visible&&PowerStackVisual.DisplayedAmount(nd)=="9","Container model rebind restores previously hidden native node");
 nd.Model=d;Need(!nd.Visible&&PowerStackVisual.DisplayedAmount(nc)=="7","Container rebind back recomputes group immediately");
 nf.Visible=false;tracker.Notify();Need(!nf.Visible,"Unrelated native visibility is never reset");nf.Visible=true;
 var otherCreature=new NCreature();var other=Make(otherCreature,100);var otherContainer=new NPowerContainer();otherContainer.Enter();var otherNode=otherContainer.Add(other);
 Need(PowerStackVisual.DisplayedAmount(nc)=="7"&&PowerStackVisual.DisplayedAmount(otherNode)=="100","Same ID from another owner never coalesces");
 var intent=new NPower();intent.Enter();Need(intent.GetterReads==0&&PowerStackVisual.DisplayedAmount(intent)=="","Unbound multiplayer Ready is safe");
 intent.Hover();intent.Unhover();Need(intent.GetterReads==0,"Unbound hover never touches throwing getter");
 intent.Model=c;Need(PowerStackVisual.DisplayedAmount(intent)=="7","Late model setter updates immediately");
 intent.Model=foreign;Need(PowerStackVisual.DisplayedAmount(intent)=="9","Rebind to foreign model restores native amount");
 intent.Model=c;intent.Hover();int beforeExit=tracker.Count;intent.Exit();Need(tracker.Count==beforeExit-2,"Intent exit removes both our state callback and native hover callback");
 intent.Enter();Need(PowerStackVisual.DisplayedAmount(intent)=="7","Intent reentry resumes projection");intent.Exit();
 otherContainer.Exit();container.Exit();Need(tracker.Count==0,"All event subscriptions released");
 Console.WriteLine($"POWER_STACK_VISUAL_PASS checks={checks} production-ui=LINKED tree-and-projection=TEST-DOUBLES");
 }
}
