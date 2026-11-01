using System.Reflection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.CardRewardAlternatives;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.TestSupport;

// This project references the user's actual sts2.dll and GodotSharp.dll. It has
// no copied ICardSelector, reward, room, or synchronizer declarations. Do not
// replace missing game references with fixtures: local release must fail closed.
int checks = 0;
void Need(bool value, string label)
{
    if (!value) throw new InvalidOperationException("Pinned native API mismatch: " + label);
    checks++;
}
MethodInfo Method(Type type, string name, Type result, params Type[] parameters)
{
    var method = type.GetMethod(name, BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic,
        null, parameters, null) ?? throw new MissingMethodException(type.FullName, name);
    Need(method.ReturnType == result, type.Name + "." + name + " result");
    return method;
}

var rewardSelector = typeof(ICardSelector).GetMethod(nameof(ICardSelector.GetSelectedCardReward));
Need(rewardSelector?.ReturnType == typeof(CardRewardSelection), "ICardSelector.GetSelectedCardReward -> CardRewardSelection");
Need(typeof(CardRewardSelection).GetField("card")?.FieldType == typeof(CardModel), "CardRewardSelection.card");
Need(Method(typeof(CardSelectCmd), nameof(CardSelectCmd.UseSelector), typeof(IDisposable), typeof(ICardSelector)).IsPublic,
    "CardSelectCmd.UseSelector public");
Need(typeof(NRewardsScreen).GetField("_isTerminal", BindingFlags.Instance | BindingFlags.NonPublic)?.FieldType == typeof(bool),
    "NRewardsScreen._isTerminal read-only observation");
Need(Method(typeof(NTreasureRoom), "OpenChest", typeof(Task)).IsPrivate, "NTreasureRoom.OpenChest native task entry");
Need(typeof(EventModel).GetProperty(nameof(EventModel.CurrentOptions))?.GetMethod?.IsPublic == true,
    "EventModel.CurrentOptions public membership");
Need(typeof(NEventOptionButton).GetProperty("Index", BindingFlags.Instance | BindingFlags.Public) is null,
    "Do not access the private event button index");
Method(typeof(MerchantEntry), nameof(MerchantEntry.OnTryPurchaseWrapper), typeof(Task<bool>), typeof(MerchantInventory), typeof(bool));
Method(typeof(NMapScreen), nameof(NMapScreen.OnMapPointSelectedLocally), typeof(void), typeof(NMapPoint));
Method(typeof(RestSiteSynchronizer), nameof(RestSiteSynchronizer.ChooseLocalOption), typeof(Task<bool>), typeof(int));
Method(typeof(RewardsSetSynchronizer), nameof(RewardsSetSynchronizer.SelectLocalReward), typeof(Task<bool>), typeof(Reward));
Method(typeof(TreasureRoomRelicSynchronizer), nameof(TreasureRoomRelicSynchronizer.PickRelicLocally), typeof(void), typeof(int?));
Method(typeof(PlayerCmd), nameof(PlayerCmd.EndTurn), typeof(void), typeof(Player), typeof(bool), typeof(Func<Task>));
Method(typeof(NCardRewardSelectionScreen), nameof(NCardRewardSelectionScreen.OptionSelected), typeof(Task<int?>));
Need(typeof(NCardRewardSelectionScreen).GetField("_options", BindingFlags.Instance | BindingFlags.NonPublic)?.FieldType
    == typeof(IReadOnlyList<CardCreationResult>), "native reward candidate field");
Need(typeof(NCardRewardSelectionScreen).GetField("_extraOptions", BindingFlags.Instance | BindingFlags.NonPublic)?.FieldType
    == typeof(IReadOnlyList<CardRewardAlternative>), "native reward alternative field");
Console.WriteLine($"NATIVE_FLOW_CONTRACT_PASS checks={checks} references=actual-game gameplay=NOT_RUN");
