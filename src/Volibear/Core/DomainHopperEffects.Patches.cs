using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Runs;

namespace Volibear.Core;

public static partial class DomainHopperEffects
{
    private static readonly Dictionary<MethodBase, Kind> Bodies = [];
    internal static MethodInfo Body(MethodInfo method) => method.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
        .GetMethod("MoveNext", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
        ?? throw new InvalidOperationException("Pinned Hopper async body missing: " + method);
    private static MethodInfo Method(Type type, string name, params Type[] args) => AccessTools.Method(type, name, args)
        ?? throw new MissingMethodException(type.FullName, name);
    private static MethodInfo Local(string name) => AccessTools.Method(typeof(DomainHopperEffects), name)
        ?? throw new MissingMethodException(name);
    internal static void InstallPatches(Harmony harmony)
    {
        Bodies.Clear();
        Bodies.Add(Body(Method(typeof(ThievingHopper), "ThieveryMove", typeof(IReadOnlyList<Creature>))), Kind.Root);
        Bodies.Add(Body(Method(typeof(SwipePower), nameof(SwipePower.Steal), typeof(CardModel))), Kind.Steal);
        Bodies.Add(Body(Method(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromDeck), typeof(CardModel), typeof(bool))), Kind.MasterSingle);
        Bodies.Add(Body(Method(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromDeck), typeof(IReadOnlyList<CardModel>), typeof(bool))), Kind.MasterMany);
        ValidateCombatCommit();
        try
        {
            foreach (var body in Bodies.Keys) harmony.Patch(body, transpiler: new HarmonyMethod(typeof(DomainHopperEffects), nameof(Rewrite)));
        }
        catch { harmony.UnpatchAll(harmony.Id); throw; }
    }
    private static int Unique(List<CodeInstruction> code, Func<MethodInfo, bool> predicate)
    {
        var indexes = code.Select((instruction, index) => (instruction, index))
            .Where(x => x.instruction.operand is MethodInfo method && predicate(method)).Select(x => x.index).ToArray();
        if (indexes.Length != 1) throw new InvalidOperationException("Pinned Hopper anchor count=" + indexes.Length);
        return indexes[0];
    }
    private static void ValidateCombatCommit()
    {
        var single = PatchProcessor.GetOriginalInstructions(Body(Method(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromCombat), typeof(CardModel), typeof(bool))));
        Unique(single, method => method.DeclaringType == typeof(CardPileCmd) && method.Name == nameof(CardPileCmd.RemoveFromCombat));
        var bulk = PatchProcessor.GetOriginalInstructions(Body(Method(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromCombat), typeof(IEnumerable<CardModel>), typeof(bool))));
        int physical = Unique(bulk, method => method.DeclaringType == typeof(CardModel) && method.Name == nameof(CardModel.RemoveFromCurrentPile));
        if (bulk.Take(physical).Any(i => i.operand is MethodInfo method && method.Name is "AwaitUnsafeOnCompleted" or "AwaitOnCompleted"))
            throw new InvalidOperationException("Hopper combat removal acquired a precommit await; source gate must be redesigned.");
    }
    private static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> input, ILGenerator generator, MethodBase __originalMethod)
    {
        var code = input.Select(i => new CodeInstruction(i)).ToList();
        static MethodInfo[] Registrations(IEnumerable<CodeInstruction> stream) => stream
            .Where(i => i.operand is MethodInfo m && m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name.StartsWith("Await", StringComparison.Ordinal))
            .Select(i => (MethodInfo)i.operand).ToArray();
        var expectedRegistrations = Registrations(PatchProcessor.GetOriginalInstructions(__originalMethod));
        var inputRegistrations = Registrations(code);
        if (expectedRegistrations.Length == 0 || inputRegistrations.Length != expectedRegistrations.Length ||
            !expectedRegistrations.All(m => inputRegistrations.Count(x => x == m) == expectedRegistrations.Count(x => x == m)))
            throw new InvalidOperationException("Hopper original registration count/type multiset changed before emission.");
        var kind = Bodies[__originalMethod]; var machine = __originalMethod.DeclaringType!;
        var builder = AccessTools.Field(machine, "<>t__builder"); var state = AccessTools.Field(machine, "<>1__state");
        if (builder?.FieldType != typeof(AsyncTaskMethodBuilder) || state?.FieldType != typeof(int))
            throw new InvalidOperationException("Pinned Hopper async fields changed.");
        var subject = AccessTools.Field(machine, kind switch { Kind.Root or Kind.Steal => "<>4__this", Kind.MasterSingle => "card", _ => "cards" })
            ?? throw new InvalidOperationException("Pinned Hopper subject field missing.");
        var frame = generator.DeclareLocal(typeof(Frame));
        Unique(code, m => m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == "SetResult");
        Unique(code, m => m.DeclaringType == typeof(AsyncTaskMethodBuilder) && m.Name == "SetException");
        var replace = new Dictionary<int, MethodInfo>();
        void Replace(Type type, string name, string helper) => replace.Add(Unique(code, m => m.DeclaringType == type && m.Name == name), Local(helper));
        if (kind == Kind.Root)
        {
            Replace(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromCombat), nameof(RemoveCombat));
            Replace(typeof(List<CardModel>), nameof(List<CardModel>.Add), nameof(Enqueue));
            Replace(typeof(SwipePower), nameof(SwipePower.Steal), nameof(Steal));
            Replace(typeof(PowerCmd), nameof(PowerCmd.Apply), nameof(Apply));
            int attack = Unique(code, m => m.DeclaringType == typeof(MegaCrit.Sts2.Core.Commands.Builders.AttackCommand) && m.Name == "Execute");
            if (attack <= replace.Keys.Max()) throw new InvalidOperationException("Hopper mixed action order changed.");
        }
        else if (kind == Kind.Steal)
        {
            Replace(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromDeck), nameof(MasterSingle));
            Replace(typeof(PlayerMapPointHistoryEntry), nameof(PlayerMapPointHistoryEntry.MarkLootStolen), nameof(LootStolen));
        }
        else if (kind == Kind.MasterSingle) Replace(typeof(CardPileCmd), nameof(CardPileCmd.RemoveFromDeck), nameof(MasterMany));
        else
        {
            int hook = Unique(code, m => m.DeclaringType?.FullName == "MegaCrit.Sts2.Core.Hooks.Hook" && m.Name == "BeforeCardRemoved");
            int physical = Unique(code, m => m.DeclaringType == typeof(CardModel) && m.Name == nameof(CardModel.RemoveFromCurrentPile));
            int flag = Unique(code, m => m.DeclaringType == typeof(CardModel) && m.Name == nameof(CardModel.RemoveFromState));
            if (!(hook < physical && physical < flag) || !code.Skip(hook).Take(physical - hook).Any(i => i.operand is MethodInfo m && m.Name == "GetResult"))
                throw new InvalidOperationException("Hopper original BeforeCardRemoved/GetResult/physical/state order changed.");
            Replace(typeof(CardModel), nameof(CardModel.RemoveFromCurrentPile), nameof(MasterPile));
            Replace(typeof(CardModel), nameof(CardModel.RemoveFromState), nameof(MasterState));
        }
        int registrations = 0;
        var output = new List<CodeInstruction> {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder),
            new(OpCodes.Call, AccessTools.PropertyGetter(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.Task))),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, subject),
            new(OpCodes.Ldc_I4, (int)kind), new(OpCodes.Call, Local(nameof(Enter))), new(OpCodes.Stloc, frame)
        };
        for (int index = 0; index < code.Count; index++)
        {
            var instruction = code[index];
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(AsyncTaskMethodBuilder) && method.Name == "AwaitUnsafeOnCompleted")
            {
                if (!method.IsGenericMethod) throw new InvalidOperationException("Hopper await registration shape changed.");
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.Add(load); output.Add(new(OpCodes.Call, Local(nameof(Registration))));
                instruction.opcode = OpCodes.Call;
                instruction.operand = typeof(SummonRegistration).GetMethod(nameof(SummonRegistration.Await), BindingFlags.Static | BindingFlags.NonPublic)!.MakeGenericMethod(method.GetGenericArguments());
                registrations++;
            }
            else if (instruction.operand is MethodInfo signal && signal.DeclaringType == typeof(AsyncTaskMethodBuilder) && signal.Name is "SetResult" or "SetException")
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.Add(load); output.Add(new(OpCodes.Call, Local(nameof(Close))));
            }
            else if (instruction.opcode == OpCodes.Ret)
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.AddRange([load, new(OpCodes.Ldarg_0), new(OpCodes.Ldflda, builder), new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, state), new(OpCodes.Call, Local(nameof(Leave)))]);
            }
            else if (replace.TryGetValue(index, out var target))
            {
                var load = new CodeInstruction(OpCodes.Ldloc, frame); Transfer(instruction, load);
                output.Add(load); instruction.opcode = OpCodes.Call; instruction.operand = target;
            }
            output.Add(instruction);
        }
        if (registrations != expectedRegistrations.Length) throw new InvalidOperationException("Hopper native await anchors missing/already replaced.");
        return output;
    }
    private static void Transfer(CodeInstruction from, CodeInstruction to)
    {
        to.labels.AddRange(from.labels); from.labels.Clear(); to.blocks.AddRange(from.blocks); from.blocks.Clear();
    }
}
