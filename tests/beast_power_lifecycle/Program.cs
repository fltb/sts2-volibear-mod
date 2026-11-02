using Volibear.Core;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

// Production BearSpiritPower with explicit command boundaries, not native gameplay.
var checks=0;
foreach(var amount in new[]{1,2}) {
 var player=new Player(); player.Creature=new Creature{Player=player};
 var context=new PlayerChoiceContext();
 var fixtureSource=new CardModel{Owner=player,Pile=new object()};
 var paidSource=new CardModel{Owner=player};
 var material=new CardModel{Owner=player,Pile=player.Hand}; player.Hand.Cards.Add(material);
 var first=new BearSpiritPower{Owner=player.Creature,Amount=amount};
 var second=new BearSpiritPower{Owner=player.Creature,Amount=amount};
 player.Creature.Powers.AddRange([first,second]);
 await first.AfterApplied(player.Creature,fixtureSource); await second.AfterApplied(player.Creature,paidSource);
 Need(fixtureSource.CombatState is not null && paidSource.CombatState is null,"fixture versus resolved native source lifetime");
 CardSelectCmd.Count=0; CardSelectCmd.Choose=_=>[];
 await first.AfterPlayerTurnStart(context,player); await second.AfterPlayerTurnStart(context,player);
 Need(CardSelectCmd.Count==2,"two independent optional-zero decisions, including pileless paid source");
 CardSelectCmd.Choose=options=>options.Take(1); BeastForms.Converts=0;
 await second.AfterPlayerTurnStart(context,player);
 Need(BeastForms.Converts==1 && ReferenceEquals(BeastForms.LastSource,paidSource),"accepted selection converts with exact pileless source attribution");
 CardSelectCmd.Choose=options=> { player.Creature.Powers.Remove(second); return options.Take(1); };
 await second.AfterPlayerTurnStart(context,player);
 Need(BeastForms.Converts==1,"removed power cannot commit pending choice");
 player.Creature.Powers.Add(second);
 CardSelectCmd.Choose=options=> { material.Pile=null; return options.Take(1); };
 await second.AfterPlayerTurnStart(context,player);
 Need(BeastForms.Converts==1,"moved card cannot commit pending choice");
 var count=CardSelectCmd.Count; player.Hand.Cards.Clear();
 await first.AfterPlayerTurnStart(context,player);
 Need(CardSelectCmd.Count==count,"empty hand needs no selector");
}
Console.WriteLine($"BEAST_POWER_LIFECYCLE_OK checks={checks}; native-gameplay=NOT_RUN");
void Need(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
