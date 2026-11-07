using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>
/// Isolated real-engine MECHANISM PROBE: native powers placed on a starting LeafSlimeS.
/// Not native enemy compatibility, input/payment, or full Domain acceptance. It uses only
/// native commands for effects and records raw state/results; the external gate owns expectations.
/// </summary>
internal static class DomainEnemyContractProbe
{
    private static bool _started;
    public static void Install() => CombatManager.Instance.TurnStarted += OnTurnStarted;
    private static void OnTurnStarted(CombatState state)
    {
        if (_started) return;
        _started = true;
        _ = Run(state);
    }

    private sealed record Snapshot(string EnemyId, string PlayerId, int EnemyHp, int EnemyMaxHp,
        decimal EnemyBlock, int EnemyPower, int EnemyPowerDisplay, int EnemyWeak, int EnemyArtifact,
        int PlayerHp, int PlayerMaxHp, decimal PlayerBlock, int PlayerPower, int PlayerWeak,
        int PlayerArtifact, int Domain, int Round, int Turn, bool Active, bool EnemyAttached,
        bool PlayerAttached, bool SamePowerInstance);
    private sealed record Hit(string ReceiverId, int HpLost, int Blocked, int Overkill);
    private sealed record Step(string Id, string Api, decimal Amount, int Props, string? SourceId,
        string TargetId, Snapshot Before, Snapshot After, Hit[] Results);

    private sealed class Fixture(CombatState state, Player player, Creature enemy)
    {
        public readonly List<Step> Steps = [];
        public readonly PlayerChoiceContext Choices = new ThrowingPlayerChoiceContext();
        public Creature Owner => player.Creature;
        public Creature Enemy => enemy;
        private PowerModel? _power;
        private Type? _powerType;
        public static string Id(Creature creature) => creature.CombatId?.ToString() ??
            throw new InvalidOperationException("Missing live combat identity");
        public Snapshot Read()
        {
            var current = enemy.Powers.FirstOrDefault(p => p.GetType() == _powerType);
            return new(Id(enemy), Id(Owner), enemy.CurrentHp, enemy.MaxHp, enemy.Block,
                current?.Amount ?? 0, current?.DisplayAmount ?? 0,
                enemy.GetPowerAmount<WeakPower>(), enemy.GetPowerAmount<ArtifactPower>(),
                Owner.CurrentHp, Owner.MaxHp, Owner.Block,
                Owner.Powers.FirstOrDefault(p => p.GetType() == _powerType)?.Amount ?? 0,
                Owner.GetPowerAmount<WeakPower>(), Owner.GetPowerAmount<ArtifactPower>(),
                Owner.GetPowerAmount<DomainPower>(), state.RoundNumber, player.PlayerCombatState!.TurnNumber,
                DomainEnemyEffects.ActiveFor(enemy), state.ContainsCreature(enemy), state.ContainsCreature(Owner),
                _power is null ? current is null : ReferenceEquals(_power, current));
        }
        public async Task Apply<T>(int amount) where T : PowerModel
        {
            _powerType = typeof(T);
            _power = await PowerCmd.Apply<T>(Choices, enemy, amount, enemy, null) ??
                throw new InvalidOperationException("Native fixture power was not applied: " + typeof(T).Name);
        }
        public Task On() => DomainPower.Open(Choices, Owner, 2);
        public Task Off() => PowerCmd.Remove<DomainPower>(Owner);
        public async Task Block(Creature target, int amount)
        {
            if (target.Block != 0) await NativeCompat.LoseBlock(target, target.Block);
            if (amount > 0) await CreatureCmd.GainBlock(target, amount, ValueProp.Unpowered, null);
        }
        private async Task Measure(string id, string api, decimal amount, int props, Creature? source,
                                   Creature target, Func<Task<Hit[]>> action)
        {
            var before = Read();
            var result = await action();
            Steps.Add(new(id, api, amount, props, source is null ? null : Id(source), Id(target), before, Read(), result));
        }
        public Task Damage(string id, Creature target, int amount, ValueProp props, Creature source) =>
            Measure(id, "CreatureCmd.Damage", amount, (int)props, source, target, async () =>
                (await NativeCompat.Damage(Choices, target, amount, props, source, null))
                    .Select(r => new Hit(Id(r.Receiver), r.UnblockedDamage, r.BlockedDamage, r.OverkillDamage)).ToArray());
        public Task Heal(string id, Creature target, int amount) =>
            Measure(id, "CreatureCmd.Heal", amount, 0, null, target, async () =>
            { await CreatureCmd.Heal(target, amount, playAnim: false); return []; });
        public Task Weak(string id, Creature target, int amount, Creature source) =>
            Measure(id, "PowerCmd.Apply:WeakPower", amount, 0, source, target, async () =>
            { await PowerCmd.Apply<WeakPower>(Choices, target, amount, source, null); return []; });
        public async Task NextTurn()
        {
            // Only fixture setup, not a replacement enemy action: prevent unrelated fixture death.
            await Block(Owner, 100);
            await Measure("next-turn", "PlayerCmd.EndTurn", 0, 0, Owner, Owner, async () =>
            {
                var before = state.RoundNumber;
                PlayerCmd.EndTurn(player, canBackOut: false);
                var elapsed = System.Diagnostics.Stopwatch.StartNew();
                while (state.RoundNumber <= before || state.CurrentSide != CombatSide.Player ||
                       player.PlayerCombatState!.Phase != PlayerTurnPhase.Play)
                {
                    if (elapsed.Elapsed > TimeSpan.FromSeconds(25)) throw new TimeoutException("Native next turn timed out");
                    var tree = (SceneTree)Engine.GetMainLoop();
                    await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
                }
                return [];
            });
        }
    }

    private static async Task Run(CombatState state)
    {
        try
        {
            var token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_ENEMY_CASE") ?? "flutter";
            if (string.IsNullOrWhiteSpace(token) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Mechanism probe requires isolated run token and TestMode=false");
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No runtime release metadata");
            if (release.Version != "v0.107.1" || release.Commit != "59260271") throw new InvalidOperationException("Wrong game version");
            var player = state.Players.Single();
            var enemy = state.Enemies.First(e => e.Monster is LeafSlimeS);
            if (state.RoundNumber != 1 || player.PlayerCombatState!.TurnNumber != 1 || player.Creature.CurrentHp != 80 ||
                player.Creature.Block != 0 || player.Creature.GetPowerAmount<DomainPower>() != 0 || enemy.Block != 0 ||
                !ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState()))
                throw new InvalidOperationException("Expected untouched first-turn native bootstrap fixture");
            await CreatureCmd.SetMaxAndCurrentHp(enemy, 1000m);
            var f = new Fixture(state, player, enemy);
            var start = f.Read();
            switch (variant)
            {
                case "flutter":
                    // Five stacks avoid the native ThievingHopper-only zero-stack stun branch.
                    // This proves damage reduction + decrement, NOT Flutter's native-owner stun.
                    await f.Apply<FlutterPower>(5);
                    await f.Damage("off", enemy, 8, ValueProp.Move, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Move, f.Owner);
                    break;
                case "soar":
                    await f.Apply<SoarPower>(1);
                    await f.Damage("off", enemy, 8, ValueProp.Move, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Move, f.Owner);
                    break;
                case "intangible":
                    await f.Apply<IntangiblePower>(3);
                    await f.Block(enemy, 5);
                    await f.Damage("off-block", enemy, 10, ValueProp.Unpowered, f.Owner);
                    await f.On(); await f.Block(enemy, 5);
                    await f.Damage("on-block", enemy, 10, ValueProp.Unpowered, f.Owner);
                    await f.Off(); await f.Block(enemy, 0);
                    await f.Damage("off-hp", enemy, 10, ValueProp.Unpowered, f.Owner);
                    await f.On();
                    await f.Damage("on-hp", enemy, 10, ValueProp.Unpowered, f.Owner);
                    await f.NextTurn();
                    await PowerCmd.Apply<IntangiblePower>(f.Choices, f.Owner, 2, f.Owner, null);
                    await f.Block(f.Owner, 0);
                    await f.Damage("player-control", f.Owner, 8, ValueProp.Unpowered, enemy);
                    break;
                case "slippery":
                    await f.Apply<SlipperyPower>(5);
                    await f.Damage("off", enemy, 8, ValueProp.Unpowered, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Unpowered, f.Owner);
                    break;
                case "hard-to-kill":
                    await f.Apply<HardToKillPower>(3);
                    await f.Damage("off", enemy, 8, ValueProp.Unpowered, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Unpowered, f.Owner);
                    break;
                case "shell":
                    await f.Apply<HardenedShellPower>(5);
                    await f.Damage("off", enemy, 8, ValueProp.Unpowered, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Unpowered, f.Owner);
                    await f.Off();
                    await f.Damage("expired-quota", enemy, 8, ValueProp.Unpowered, f.Owner);
                    await f.NextTurn();
                    await f.Damage("reset-quota", enemy, 8, ValueProp.Unpowered, f.Owner);
                    break;
                case "artifact":
                    await f.Apply<ArtifactPower>(3);
                    await f.Weak("off", enemy, 2, f.Owner);
                    await f.On();
                    await f.Weak("on", enemy, 2, f.Owner);
                    await PowerCmd.Apply<ArtifactPower>(f.Choices, f.Owner, 3, f.Owner, null);
                    await f.Weak("player-control", f.Owner, 2, enemy);
                    await f.Off(); await PowerCmd.Remove<WeakPower>(enemy);
                    await f.Weak("restored", enemy, 2, f.Owner);
                    break;
                case "thorns":
                    await f.Apply<ThornsPower>(3);
                    await f.Damage("off", enemy, 8, ValueProp.Move, f.Owner);
                    await f.On();
                    await f.Damage("on", enemy, 8, ValueProp.Move, f.Owner);
                    await f.Off();
                    await f.Damage("restored", enemy, 8, ValueProp.Move, f.Owner);
                    break;
                case "reflect":
                    await f.Apply<ReflectPower>(3);
                    await f.Block(enemy, 5);
                    await f.Damage("off", enemy, 8, ValueProp.Move, f.Owner);
                    await f.On(); await f.Block(enemy, 5);
                    await f.Damage("on", enemy, 8, ValueProp.Move, f.Owner);
                    await f.NextTurn();
                    await f.Off(); await f.Block(enemy, 5);
                    await f.Damage("restored", enemy, 8, ValueProp.Move, f.Owner);
                    break;
                case "heal":
                    await CreatureCmd.SetCurrentHp(enemy, 500m);
                    await CreatureCmd.SetCurrentHp(f.Owner, 40m);
                    await f.Heal("enemy-off", enemy, 7);
                    await f.Heal("player-off", f.Owner, 7);
                    await f.On();
                    await f.Heal("enemy-on", enemy, 7);
                    await f.Heal("player-on", f.Owner, 7);
                    break;
                default: throw new InvalidOperationException("Unknown domain-enemy fixture: " + variant);
            }
            GD.Print("[Volibear] DOMAIN_ENEMY_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, scenario = "domain-enemy-contract", variant,
                acceptance = "mechanism-probe-not-native-enemy-coverage", testMode = false,
                version = release.Version, commit = release.Commit,
                enemyType = enemy.Monster!.GetType().Name,
                fixtureApi = "native-PowerCmd+CreatureCmd;starting-LeafSlimeS;no-replaced-actions",
                start, steps = f.Steps
            }, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0); // External checker, never this exit code, decides acceptance.
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_ENEMY_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { CombatManager.Instance.TurnStarted -= OnTurnStarted; }
    }
}
