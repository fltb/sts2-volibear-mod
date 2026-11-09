// Synthetic API boundaries. Default mode dispatches production callbacks explicitly;
// REAL_HARMONY installs actual patches on these types. Neither mode is the native game/network.
using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using Volibear.Core;

internal static class NativeHooks
{
    private const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic |
        BindingFlags.Instance | BindingFlags.Static;
    private static Type Patch(string name) => typeof(EngageCmd).GetNestedType(name, Flags)!;
    internal static object? Start(MonsterModel monster, bool runOriginal)
    {
        var bodyEntry = Patch("ObserveActionStart").GetMethod("BodyEntered", Flags);
        if (bodyEntry is not null)
        {
            if (runOriginal) bodyEntry.Invoke(null, [-1, monster]);
            return null;
        }
        var machine = typeof(MonsterModel).GetMethod(nameof(MonsterModel.PerformMove))!
            .GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType;
        var instance = Activator.CreateInstance(machine)!;
        machine.GetField("<>1__state", Flags)!.SetValue(instance, -1);
        machine.GetField("<>4__this", Flags)!.SetValue(instance, monster);
        var prefix = Patch("ObserveActionStart").GetMethod("Prefix", Flags)!;
        // Supports the pre-fix source as well, to demonstrate the regression before the fix.
        object?[] args = prefix.GetParameters().Length == 1 ? [instance] : [instance, runOriginal, null];
        prefix.Invoke(null, args);
        return args.Length == 1 ? null : args[2];
    }
    internal static void FinishStart(object? observation, bool runOriginal) =>
        Patch("ObserveActionStart").GetMethod("Postfix", Flags)?.Invoke(null, [runOriginal, observation]);
    internal static void Absorbed(Creature receiver, decimal amount) =>
        Patch("ObserveAbsorption").GetMethod("Postfix", Flags)!.Invoke(null, [receiver, amount]);
    internal static bool AllowTakeTurn(Creature creature)
    {
        object?[] args = [creature, null];
        bool allowed = (bool)Patch("SkipConsumedAction").GetMethod("Prefix", Flags)!.Invoke(null, args)!;
        if (!allowed && args[1] is not Task { IsCompletedSuccessfully: true })
            throw new Exception("Skipped action must return a completed task");
        return allowed;
    }
    internal static bool AllowIntent(MegaCrit.Sts2.Core.Nodes.Combat.NCreature creature)
    {
        object?[] args = [creature, null];
        return (bool)Patch("SkipConsumedIntent").GetMethod("Prefix", Flags)!.Invoke(null, args)!;
    }
}

#if !REAL_HARMONY
namespace HarmonyLib
{
    public sealed class CodeInstruction
    { public CodeInstruction(System.Reflection.Emit.OpCode opcode, object? operand = null) { } }
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
    public sealed class HarmonyPatch : Attribute
    {
        public HarmonyPatch() { }
        public HarmonyPatch(Type type, string name) { }
        public HarmonyPatch(Type type, string name, Type[] arguments) { }
    }
    public sealed class Harmony(string id)
    {
        public ClassProcessor CreateClassProcessor(Type type) => new(id, type);
    }
    public sealed class ClassProcessor(string id, Type type)
    {
        public void Patch() { _ = id; _ = type; }
    }
    public static class AccessTools
    {
        private const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic |
            BindingFlags.Instance | BindingFlags.Static;
        public static MethodInfo Method(Type type, string name) => type.GetMethod(name, Flags)!;
        public static FieldInfo Field(Type type, string name) => type.GetField(name, Flags)!;
    }
}
#endif
namespace MegaCrit.Sts2.Core.Combat
{
    public enum CombatSide { Player, Enemy }
    public interface ICombatState
    {
        CombatSide CurrentSide { get; }
        int RoundNumber { get; }
        IEnumerable<Creature> Enemies { get; }
        bool ContainsCreature(Creature creature);
    }
    public sealed class CombatState : ICombatState
    {
        public CombatSide CurrentSide { get; set; } = CombatSide.Player;
        public int RoundNumber { get; set; } = 1;
        public List<Creature> Members { get; } = [];
        public IEnumerable<Creature> Enemies => Members.Where(c => c.IsEnemy);
        public bool ContainsCreature(Creature creature) => Members.Contains(creature);
    }
    public sealed class CombatManager
    {
        public static CombatManager Instance { get; } = new();
        public bool IsInProgress { get; set; }
        public bool IsEnding { get; set; }
        public event Action<ICombatState>? CombatSetUp;
        public event Action<ICombatState>? CombatEnded;
        private ICombatState? state;
        public ICombatState? DebugOnlyGetState() => state;
        public void Setup(ICombatState value)
        { state = value; IsInProgress = true; IsEnding = false; CombatSetUp?.Invoke(value); }
        public void Reset(bool ignored)
        { if (state is not null) CombatEnded?.Invoke(state); state = null; IsInProgress = false; }
    }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public sealed class Creature
    {
        public ICombatState? CombatState { get; set; }
        public bool IsDead { get; set; }
        public bool IsEnemy { get; set; }
        public decimal CurrentHp { get; set; } = 80m;
        public MonsterModel? Monster { get; set; }
        public Player? Player { get; set; }
        public List<object> Powers { get; } = [];
        public MegaCrit.Sts2.Core.Nodes.Combat.NCreature? Node { get; set; }
        public MegaCrit.Sts2.Core.Nodes.Combat.NCreature? GetCreatureNode() => Node;
        [MethodImpl(MethodImplOptions.NoInlining)]
        public decimal DamageBlockInternal(decimal absorbed)
        {
#if !REAL_HARMONY
            NativeHooks.Absorbed(this, absorbed);
#endif
            return absorbed;
        }
        public Task TakeTurn() => Task.CompletedTask;
    }
}
namespace MegaCrit.Sts2.Core.GameActions.Multiplayer { public sealed class PlayerChoiceContext { } }
namespace MegaCrit.Sts2.Core.Models
{
    public sealed class Player
    {
        public required Creature Creature { get; init; }
        public List<object> Relics { get; } = [];
    }
    public sealed class CardModel { public required Player Owner { get; init; } }
    public sealed class MonsterModel
    {
        public required Creature Creature { get; init; }
        public List<Creature> Targets { get; } = [];
        public Func<MonsterModel, Task> Body { get; set; } = _ => Task.CompletedTask;
        public bool SkipEntry { get; set; }
        public bool SkipMoveNext { get; set; }
        public int BodyCalls { get; private set; }
        [MethodImpl(MethodImplOptions.NoInlining)]
        public async Task PerformMove()
        {
#if REAL_HARMONY
            BodyCalls++;
            await Body(this);
#else
            if (SkipEntry) return;
            var observation = NativeHooks.Start(this, !SkipMoveNext);
            try { if (!SkipMoveNext) { BodyCalls++; await Body(this); } }
            finally { NativeHooks.FinishStart(observation, !SkipMoveNext); }
#endif
        }
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Combat
{
    public sealed class NCreature
    {
        public required Creature Entity { get; init; }
        public Func<Task> Intent { get; set; } = () => Task.CompletedTask;
        public Task PerformIntent() => Intent();
    }
}
