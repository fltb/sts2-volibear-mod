using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Hooks;

// Inspect pinned native semantics without booting Godot or launching the game.
var getter = AccessTools.PropertyGetter(typeof(CardModel), "CombatState");
var il = PatchProcessor.GetOriginalInstructions(getter).ToArray();
Need(il.Any(i => i.operand is MethodInfo m && m.Name == "get_Pile"), "CardModel.CombatState consults source pile");
Need(il.Any(i => i.operand is MethodInfo m && m.Name == "get_IsCombatPile"), "CardModel.CombatState requires combat pile");
Need(il[^2].opcode == System.Reflection.Emit.OpCodes.Ldnull && il[^1].opcode == System.Reflection.Emit.OpCodes.Ret, "noncombat source returns null");
var hook = AccessTools.Method(typeof(Hook), "AfterPlayerTurnStart");
var body = hook.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType.GetMethod("MoveNext", BindingFlags.NonPublic | BindingFlags.Instance)!;
var calls = PatchProcessor.GetOriginalInstructions(body).Select(i => i.operand).OfType<MethodInfo>().ToArray();
Need(calls.Count(m => m.Name == "AfterPlayerTurnStart") == 1, "native hook invokes each enumerated listener");
Need(calls.Any(m => m.Name == "IterateCombatHookListeners") && calls.Any(m => m.Name == "MoveNext"), "native hook iterates listeners");
Console.WriteLine("BEAST_NATIVE_LIFETIME_IL_OK checks=5; native-gameplay=NOT_RUN");
static void Need(bool value, string message) { if (!value) throw new Exception(message); }
