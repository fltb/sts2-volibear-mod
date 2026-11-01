using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;

namespace Volibear.Core;

/// <summary>Native-owned lifetime. Mutable state is reset by native DeepCloneFields,
/// never shared between canonical models, deployments, owners or battles.</summary>
public abstract class PersistentPower : CustomPowerModel
{
    protected sealed class State
    {
        internal int UsedRound = -1;
        internal int UsedTurn = -1;
        internal int DeployedTurn = -1;
        internal IDisposable? Subscription;
        internal readonly HashSet<long> BlockPlays = [];
    }
    protected State Data => GetInternalData<State>();
    protected override object InitInternalData() => new State();
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    // Reuse a shipped rune until per-power artwork is wired; never request a missing vanilla asset.
    public override string CustomPackedIconPath => Presentation.VolibearIcons.ThunderForce;
    public override string CustomBigIconPath => Presentation.VolibearIcons.ThunderForceBig;
    protected bool Live => Owner.IsAlive && Owner.CombatState is not null &&
        CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsOverOrEnding &&
        Owner.Powers.Contains(this);
    protected bool Own(CardModel card) => ReferenceEquals(card.Owner.Creature, Owner);
    protected bool TryFirstThisTurn()
    {
        if (!Live) return false;
        int round = CombatState.RoundNumber, turn = Owner.Player!.PlayerCombatState!.TurnNumber;
        if (Data.UsedRound == round && Data.UsedTurn == turn) return false;
        Data.UsedRound = round;
        Data.UsedTurn = turn;
        return true;
    }
    public override Task AfterRemoved(Creature oldOwner)
    {
        Data.Subscription?.Dispose();
        Data.Subscription = null;
        Data.BlockPlays.Clear();
        return Task.CompletedTask;
    }
}

/// <summary>Each deployment is a native separate power instance. Amount is its
/// configured response value, not a sum standing in for several responders.</summary>
public abstract class InstancedPersistentPower : PersistentPower
{
    public override PowerInstanceType InstanceType => PowerInstanceType.Instanced;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_STORM_CONDUCTION")]
public sealed class StormConductionPower : InstancedPersistentPower, IOrdinarySegmentResponder
{
    public override List<(string, string)> Localization => new PowerLoc("狂雷渐起",
        "每段普通攻击结算后，对全体造成{Amount}雷伤。每次部署独立结算。",
        "每段普通攻击结算后，对全体造成{Amount}雷伤。各部署独立结算，多段与重演逐段触发，全体一段只触发一次。");
    public Task AfterOrdinarySegment(PlayerChoiceContext context, CardModel source, IReadOnlyList<DamageResult> results) =>
        Live && Own(source) ? LightningCmd.DealAllEnemies(context, Owner, Amount, null) : Task.CompletedTask;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_STANDING")]
public sealed class StandingPower : PersistentPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/retain_armor.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/retain_armor.png";
    public override List<(string, string)> Localization => new PowerLoc("留甲",
        "回合开始时，格挡只减少{Amount}。重复获得取较小损耗。",
        "回合开始时，格挡只减少{Amount}。重复获得取较小损耗；不是获得格挡，不受敏捷或脆弱影响。");
    public static async Task Deploy(PlayerChoiceContext context, Creature owner, int decay, CardModel source)
    {
        if (decay <= 0) throw new ArgumentOutOfRangeException(nameof(decay));
        if (owner.GetPower<StandingPower>() is { } existing)
        {
            int delta = Math.Min(existing.Amount, decay) - existing.Amount;
            if (delta != 0) await PowerCmd.ModifyAmount(context, existing, delta, owner, source);
        }
        else await PowerCmd.Apply<StandingPower>(context, owner, decay, owner, source);
    }
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        Data.DeployedTurn = Owner.Player!.PlayerCombatState!.TurnNumber;
        PersistentBlockHooks.Install();
        return Task.CompletedTask;
    }
    internal int RetainedAfterNativeClear(int nativeValue) => Live && Owner.Player!.PlayerCombatState!.TurnNumber > Data.DeployedTurn
        ? Math.Max(0, Owner.Block - Amount) : nativeValue;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_BATTLE_SCARS")]
public sealed class BattleScarsPower : InstancedPersistentPower, IEngageResponder
{
    public override List<(string, string)> Localization => new PowerLoc("战痕",
        "每回合首次完成迎战后，获得{Amount}力量和1雷势。每次部署独立计次。",
        "每回合首次完成迎战后，获得{Amount}力量和1雷势。每次部署独立计次。");
    public async Task AfterEngageCompleted(EngageCmd.Completion completion)
    {
        if (!ReferenceEquals(completion.Receiver, Owner) || !TryFirstThisTurn()) return;
        await PowerCmd.Apply<StrengthPower>(completion.Choices, Owner, Amount, Owner, null);
        await StormChargePower.Gain(completion.Choices, Owner, 1);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_LINGERING_STORM")]
public sealed class LingeringStormPower : InstancedPersistentPower, IEngageResponder
{
    public override List<(string, string)> Localization => new PowerLoc("风暴不散",
        "每次完成迎战后，抽1张牌并获得领域1。每次部署独立结算。",
        "每次完成迎战后，先抽1张牌，再获得领域1。每次部署独立结算。");
    public async Task AfterEngageCompleted(EngageCmd.Completion completion)
    {
        if (!Live || !ReferenceEquals(completion.Receiver, Owner)) return;
        await CardPileCmd.Draw(completion.Choices, 1m, Owner.Player!);
        await DomainPower.Open(completion.Choices, Owner, 1);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_THUNDER_AFTERSHOCK")]
public sealed class ThunderAftershockPower : InstancedPersistentPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/energy.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/energy.png";
    public override List<(string, string)> Localization => new PowerLoc("雷霆余威",
        "本回合第2、4、6…次雷伤后获得1能量。部署时已有至少2次雷伤，立即获得1能量。",
        "本回合第2、4、6…次雷伤后获得1能量。部署时已有至少2次雷伤，立即获得1能量。各部署独立响应，不补发历史次数。");
    public override async Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        Data.Subscription = LightningBatches.Subscribe(Owner, AfterBatch);
        if (LightningBatches.GetTurnCount(Owner) >= 2 && Live)
            await PlayerCmd.GainEnergy(1m, Owner.Player!);
    }
    private Task AfterBatch(PlayerChoiceContext context, LightningBatch receipt) =>
        Live && ReferenceEquals(receipt.Owner, Owner) && receipt.CountThisTurn > 0 && receipt.CountThisTurn % 2 == 0
            ? PlayerCmd.GainEnergy(1m, Owner.Player!) : Task.CompletedTask;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_PREY_STILL_STANDS")]
public sealed class PreyStillStandsPower : InstancedPersistentPower
{
    public override List<(string, string)> Localization => new PowerLoc("猎物未倒",
        "每回合首次对同一目标打出第2张单体攻击后，抽{Amount}张牌，其中的攻击本回合减费1。",
        "每回合首次对同一目标打出第2张单体攻击后，抽{Amount}张牌，其中的攻击本回合减费1。各部署独立计次，重演不另计实际出牌。");
    public override async Task AfterCardPlayed(PlayerChoiceContext context, CardPlay play)
    {
        if (!Live || !Own(play.Card) || !play.IsLastInSeries) return;
        var snapshot = AttackHistory.Snapshot(play);
        // s2.ts queries the LIVE count at finished, not the count captured at play start:
        // a nested actual play may advance this target beyond two before the outer finishes.
        if (!snapshot.IsSingleTargetAttack || play.Target is null ||
            AttackHistory.TargetAttackCount(play.Card.Owner, play.Target) != 2 || !TryFirstThisTurn()) return;
        await CardResolutionHooks.DrawObserved(context, Amount, Owner.Player!, card =>
        {
            if (card.Type == CardType.Attack) NextPlayDiscount.Grant(card);
            return Task.CompletedTask;
        });
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_GROWING_FURY")]
public sealed class GrowingFuryPower : InstancedPersistentPower
{
    public override List<(string, string)> Localization => new PowerLoc("愈战愈烈",
        "每回合第2张实际攻击支付后、牌效前，获得{Amount}力量和{Amount}雷势。",
        "每回合第2张实际攻击支付后、牌效前，获得{Amount}力量和{Amount}雷势。各部署独立计次，重演不另计实际出牌。");
    public override async Task BeforeCardPlayed(CardPlay play)
    {
        if (!Live || !Own(play.Card) || !play.IsFirstInSeries ||
            AttackHistory.Snapshot(play).CardType != CardType.Attack ||
            AttackHistory.CurrentAttackOrdinal(play) != 2 || !TryFirstThisTurn()) return;
        var context = CardResolutionHooks.CurrentChoices(play.Card);
        await PowerCmd.Apply<StrengthPower>(context, Owner, Amount, Owner, null);
        await StormChargePower.Gain(context, Owner, Amount);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_WELCOME_THUNDER")]
public sealed class WelcomeThunderPower : InstancedPersistentPower, IEngageResponder
{
    public override List<(string, string)> Localization => new PowerLoc("迎雷",
        "每回合首次完成迎战后，本回合下一张攻击减费{Amount}。每次部署独立计次。",
        "每回合首次完成迎战后，本回合下一张攻击减费{Amount}。各部署独立计次，同类待用减费取最大值，不相加，使用后消费。");
    public static Task Prepare(PlayerChoiceContext context, Creature owner, int amount, CardModel? source) =>
        NextAttackDiscount.Grant(context, owner, amount);
    public Task AfterEngageCompleted(EngageCmd.Completion completion) =>
        ReferenceEquals(completion.Receiver, Owner) && TryFirstThisTurn()
            ? Prepare(completion.Choices, Owner, Amount, null) : Task.CompletedTask;
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_THUNDER_ARMOR")]
public sealed class ThunderArmorPower : InstancedPersistentPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/thunder_armor.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/thunder_armor.png";
    public override List<(string, string)> Localization => new PowerLoc("雷甲",
        "每次雷伤后获得{Amount}格挡。每次部署独立结算。",
        "每次雷伤后获得{Amount}格挡。各部署独立结算，全体雷伤一批只触发一次，完全格挡的雷伤也触发。");
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        Data.Subscription = LightningBatches.Subscribe(Owner, AfterBatch);
        return Task.CompletedTask;
    }
    private async Task AfterBatch(PlayerChoiceContext context, LightningBatch receipt)
    {
        if (!Live || !ReferenceEquals(receipt.Owner, Owner)) return;
        var before = Owner.Block;
        var granted = await CreatureCmd.GainBlock(Owner, Amount, ValueProp.Move, null);
        var added = Math.Min(granted, Owner.Block - before);
        if (added > 0)
            GameplayPresentationReceipts.Publish("thunder_armor_block_committed", Owner, this, amount: added);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_IMMOVABLE_BODY")]
public sealed class ImmovableBodyPower : PersistentPower
{
    public override string CustomPackedIconPath => "res://VolibearArt/vfx/icons/64/iron_armor.png";
    public override string CustomBigIconPath => "res://VolibearArt/vfx/icons/256/iron_armor.png";
    public static async Task Deploy(PlayerChoiceContext context, Creature owner, CardModel source)
    {
        // Frozen flag policy reapplication remains level one, not an accumulating counter.
        if (owner.GetPower<ImmovableBodyPower>() is { } existing)
            await PowerCmd.ModifyAmount(context, existing, 1 - existing.Amount, owner, source);
        else await PowerCmd.Apply<ImmovableBodyPower>(context, owner, 1, owner, source);
    }
    public override PowerStackType StackType => PowerStackType.Single;
    public override List<(string, string)> Localization => new PowerLoc("坚甲",
        "承受攻击时不消耗格挡，溢出伤害仍扣生命。不会阻止回合开始的格挡清除。",
        "承受攻击时不消耗格挡，溢出伤害仍扣生命。不会阻止回合开始的格挡清除。");
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        PersistentBlockHooks.Install();
        return Task.CompletedTask;
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_BATTLE_BODY")]
public sealed class BattleBodyPower : PersistentPower
{
    public override List<(string, string)> Localization => new PowerLoc("愈战神躯",
        "每张实际攻击结算后获得{Amount}力量；该牌曾提供正数格挡时，再获得{Amount}敏捷。",
        "每张实际攻击结算后获得{Amount}力量；该牌曾提供正数格挡时，再获得{Amount}敏捷。重演共享一次实际出牌，被动雷甲不算本牌格挡。");
    public override Task AfterBlockGained(Creature creature, decimal amount, ValueProp props, CardModel? cardSource)
    {
        if (Live && ReferenceEquals(creature, Owner) && amount > 0 && cardSource is not null && Own(cardSource) &&
            CardResolutionHooks.CurrentPlayId(cardSource) is { } id) Data.BlockPlays.Add(id);
        return Task.CompletedTask;
    }
    public override async Task AfterCardPlayed(PlayerChoiceContext context, CardPlay play)
    {
        if (!Live || !Own(play.Card) || !play.IsLastInSeries) return;
        var id = CardResolutionHooks.CurrentPlayId(play.Card);
        bool blocked = id is not null && Data.BlockPlays.Remove(id.Value);
        if (play.Card.Type != CardType.Attack) return;
        await PowerCmd.Apply<StrengthPower>(context, Owner, Amount, Owner, null);
        if (blocked && Live) await PowerCmd.Apply<DexterityPower>(context, Owner, Amount, Owner, null);
    }
}

[BaseLib.Utils.Attributes.CustomID("VOLIBEAR_THUNDER_POOL")]
public sealed class ThunderPoolPower : InstancedPersistentPower, IEngageResponder
{
    public override List<(string, string)> Localization => new PowerLoc("雷池",
        "回合结束及每回合首次完成迎战后，对全体造成{Amount}雷伤。每次部署独立结算。",
        "回合结束及每回合首次完成迎战后，对全体造成{Amount}雷伤。各部署独立结算，回合结束不会消费首次迎战机会。");
    public Task AfterEngageCompleted(EngageCmd.Completion completion) =>
        ReferenceEquals(completion.Receiver, Owner) && TryFirstThisTurn()
            ? LightningCmd.DealAllEnemies(completion.Choices, Owner, Amount, null) : Task.CompletedTask;
    public override Task BeforeSideTurnEnd(PlayerChoiceContext context, CombatSide side, IEnumerable<Creature> participants) =>
        Live && side == CombatSide.Player && participants.Contains(Owner)
            ? LightningCmd.DealAllEnemies(context, Owner, Amount, null) : Task.CompletedTask;
}

/// <summary>Only changes the two native block assignments. Native absorption,
/// damage/death hooks, ShouldClearBlock and other sources' retention remain intact.</summary>
internal static class PersistentBlockHooks
{
    private static bool _installed;
    private static readonly MethodInfo Setter = AccessTools.PropertySetter(typeof(Creature), nameof(Creature.Block))
        ?? throw new MissingMethodException("Creature.Block setter");
    private static readonly Action<Creature, int> SetBlock =
        (Action<Creature, int>)Setter.CreateDelegate(typeof(Action<Creature, int>));

    internal static void Install()
    {
        if (_installed) return;
        var harmony = new Harmony("Volibear.PersistentBlock");
        try
        {
            var clear = AccessTools.Method(typeof(Creature), "ClearBlock", Type.EmptyTypes)
                ?? throw new MissingMethodException("Creature.ClearBlock()");
            var machine = clear.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
                ?? throw new MissingMemberException("ClearBlock async state machine");
            var moveNext = AccessTools.Method(machine, "MoveNext")
                ?? throw new MissingMethodException("ClearBlock.MoveNext");
            harmony.Patch(moveNext, transpiler: new HarmonyMethod(typeof(PersistentBlockHooks), nameof(ClearAssignment)));
            var damage = AccessTools.Method(typeof(Creature), nameof(Creature.DamageBlockInternal), [typeof(decimal), typeof(ValueProp)])
                ?? throw new MissingMethodException("Creature.DamageBlockInternal(decimal,ValueProp)");
            harmony.Patch(damage, transpiler: new HarmonyMethod(typeof(PersistentBlockHooks), nameof(DamageAssignment)));
            _installed = true;
        }
        catch
        {
            harmony.UnpatchAll(harmony.Id);
            throw;
        }
    }

    private static IEnumerable<CodeInstruction> ClearAssignment(IEnumerable<CodeInstruction> instructions)
    {
        int matched = 0;
        foreach (var instruction in instructions)
        {
            if (instruction.Calls(Setter))
            {
                matched++;
                var replacement = new CodeInstruction(OpCodes.Call, AccessTools.Method(typeof(PersistentBlockHooks), nameof(SetClearedBlock)));
                replacement.labels.AddRange(instruction.labels);
                replacement.blocks.AddRange(instruction.blocks);
                yield return replacement;
            }
            else yield return instruction;
        }
        if (matched != 1) throw new InvalidOperationException($"Expected one native ClearBlock setter; found {matched}");
    }

    private static IEnumerable<CodeInstruction> DamageAssignment(IEnumerable<CodeInstruction> instructions)
    {
        int matched = 0;
        foreach (var instruction in instructions)
        {
            if (instruction.Calls(Setter))
            {
                matched++;
                var load = new CodeInstruction(OpCodes.Ldarg_2);
                load.labels.AddRange(instruction.labels);
                load.blocks.AddRange(instruction.blocks);
                yield return load;
                yield return new CodeInstruction(OpCodes.Call, AccessTools.Method(typeof(PersistentBlockHooks), nameof(SetDamagedBlock)));
            }
            else yield return instruction;
        }
        if (matched != 1) throw new InvalidOperationException($"Expected one native DamageBlockInternal setter; found {matched}");
    }

    private static void SetClearedBlock(Creature creature, int nativeValue) =>
        SetBlock(creature, creature.GetPower<StandingPower>()?.RetainedAfterNativeClear(nativeValue) ?? nativeValue);

    private static void SetDamagedBlock(Creature creature, int nativeValue, ValueProp props)
    {
        // Preserve the native calculated/returned absorption; suppress only consumption
        // for attacks, not arbitrary unpowered damage or explicit LoseBlock commands.
        if (props.HasFlag(ValueProp.Move) && creature.HasPower<ImmovableBodyPower>()) return;
        SetBlock(creature, nativeValue);
    }
}
