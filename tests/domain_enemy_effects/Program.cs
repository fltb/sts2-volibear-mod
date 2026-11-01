using System.Reflection;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

// Tests production callbacks and registration/predicate contracts through controlled API doubles.
// Does NOT prove native damage pipeline, real detours, visuals, or game compatibility.
internal static class Program
{
    private static int checks;
    private static void Check(bool condition, string message)
    {
        checks++;
        if (!condition) throw new Exception("FAIL: " + message);
    }
    private static object? Call(string method, params object?[] args) =>
        typeof(DomainEnemyEffects).GetMethod(method, BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, args);
    private static decimal Scalar(string method, PowerModel owner, Creature? target, decimal original, decimal? incoming = null)
    {
        object?[] args = incoming is null ? [owner, target, original] : [owner, target, incoming.Value, original];
        Call(method, args);
        return (decimal)args[^1]!;
    }
    private static (TestCombat Combat, Creature Player, Creature Enemy) Fixture()
    {
        var state = new TestCombat();
        var player = new Creature { IsPlayer = true, Domain = true, CombatState = state };
        var enemy = new Creature { IsEnemy = true, CombatState = state };
        state.Creatures.UnionWith([player, enemy]);
        state.PlayerList.Add(new TestPlayer { Creature = player });
        CombatManager.Instance = new() { Current = state };
        return (state, player, enemy);
    }
    public static void Main()
    {
        InstallContracts();
        ActiveContracts();
        ScalarContracts();
        ArtifactContracts();
        RetaliationAndHealContracts();
        ShellWindowContracts();
        Console.WriteLine($"PASS {checks} isolated production-callback/registration assertions; native engine integration NOT RUN.");
    }
    private static void InstallContracts()
    {
        var foreignTarget = typeof(CreatureCmd).GetMethod("Heal")!;
        Harmony.Patches.Add(new("OtherMod", foreignTarget, null, null));
        Harmony.FailAt = 3;
        try { DomainEnemyEffects.Install(); Check(false, "injected install must throw"); }
        catch (InvalidOperationException) { Check(true, "installation failure propagated"); }
        Check(Harmony.Patches.Count == 1 && Harmony.Patches[0].Id == "OtherMod", "failed installation rolls back only own patches");
        Harmony.FailAt = 0;
        DomainEnemyEffects.Install();
        Check(Harmony.Patches.Count == 13, "12 narrow registrations plus foreign patch");
        var calls = Harmony.Calls;
        DomainEnemyEffects.Install();
        Check(Harmony.Calls == calls && Harmony.Patches.Count == 13, "idempotent install");
        var expected = new HashSet<string>
        {
            "FlutterPower.ModifyDamageMultiplicative", "SoarPower.ModifyDamageMultiplicative",
            "IntangiblePower.ModifyHpLostAfterOsty", "IntangiblePower.ModifyDamageCap",
            "SlipperyPower.ModifyHpLostAfterOsty", "HardToKillPower.ModifyDamageCap",
            "HardenedShellPower.ModifyHpLostBeforeOstyLate", "HardenedShellPower.BeforeSideTurnStart",
            "ArtifactPower.TryModifyPowerAmountReceived", "ThornsPower.BeforeDamageReceived",
            "ReflectPower.AfterDamageReceived", "CreatureCmd.Heal"
        };
        var ours = Harmony.Patches.Where(p => p.Id != "OtherMod").ToArray();
        Check(expected.SetEquals(ours.Select(p => p.Target.DeclaringType!.Name + "." + p.Target.Name)), "exact allowlist, no Apply/Add/whole callback filter");
        foreach (var p in ours)
        {
            Check((p.Prefix is null) != (p.Postfix is null), "one patch stage per method");
            if (p.Target.Name == "BeforeSideTurnStart")
                Check(p.Prefix is null && p.Postfix!.Method.Name == "ClearShellWindow", "native shell reset must execute before sidecar clear");
        }
        foreach (var untouched in new[] { "FlutterPower.AfterDamageReceived", "SlipperyPower.AfterDamageReceived",
                    "IntangiblePower.AfterSideTurnEnd", "ReflectPower.AfterSideTurnStart",
                    "HardenedShellPower.AfterDamageReceived", "ArtifactPower.AfterModifyingPowerAmountReceived" })
            Check(!ours.Any(p => p.Target.DeclaringType!.Name + "." + p.Target.Name == untouched), "lifecycle not patched: " + untouched);
        var specType = typeof(DomainEnemyEffects).GetNestedType("PatchSpec", BindingFlags.NonPublic)!;
        foreach (var (name, result) in new[] { ("MissingNativeMethod", typeof(decimal)), ("ModifyDamageMultiplicative", typeof(bool)) })
        {
            Type[] args = [typeof(Creature), typeof(decimal), typeof(MegaCrit.Sts2.Core.ValueProps.ValueProp), typeof(Creature), typeof(CardModel)];
            var spec = Activator.CreateInstance(specType, [typeof(FlutterPower), name, result, args, "Unused", false, false]);
            try { Call("Resolve", spec); Check(false, "signature drift must fail"); }
            catch (TargetInvocationException ex) { Check(ex.InnerException is MissingMethodException, "exact missing/return drift error"); }
        }
    }
    private static void ActiveContracts()
    {
        var (state, player, enemy) = Fixture();
        Check(DomainEnemyEffects.ActiveFor(state) && DomainEnemyEffects.ActiveFor(enemy), "live player domain affects current enemy");
        Check(!DomainEnemyEffects.ActiveFor(player), "player not enemy recipient");
        Check(!DomainEnemyEffects.ActiveFor((Creature?)null) && !DomainEnemyEffects.ActiveFor((ICombatState?)null), "null predicates false");
        player.Domain = false;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "power removal reflected live");
        player.Domain = true; player.IsAlive = false;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "dead domain owner excluded");
        player.IsAlive = true;
        state.Creatures.Remove(player);
        Check(!DomainEnemyEffects.ActiveFor(enemy), "detached domain owner excluded");
        state.Creatures.Add(player); state.Creatures.Remove(enemy);
        Check(!DomainEnemyEffects.ActiveFor(enemy), "escaped enemy excluded");
        state.Creatures.Add(enemy);
        player.CombatState = new TestCombat();
        Check(!DomainEnemyEffects.ActiveFor(enemy), "stale player combat pointer excluded");
        player.CombatState = state;
        CombatManager.Instance.Current = new TestCombat();
        Check(!DomainEnemyEffects.ActiveFor(state), "old encounter excluded");
        CombatManager.Instance.Current = state; CombatManager.Instance.IsInProgress = false;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "outside combat excluded");
        CombatManager.Instance.IsInProgress = true; CombatManager.Instance.IsOverOrEnding = true;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "ending combat excluded");
        CombatManager.Instance.IsOverOrEnding = false;
        var pet = new Creature { CombatState = state, Domain = true };
        state.Creatures.Add(pet);
        Check(!DomainEnemyEffects.ActiveFor(pet), "allied monster/pet excluded");
        player.Domain = false;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "pet's domain cannot activate player domain policy");
        var secondPlayer = new Creature { IsPlayer = true, Domain = true, CombatState = state };
        state.PlayerList.Add(new TestPlayer { Creature = secondPlayer }); state.Creatures.Add(secondPlayer);
        Check(DomainEnemyEffects.ActiveFor(enemy), "another live player's domain keeps effect active");
        secondPlayer.Domain = false;
        Check(!DomainEnemyEffects.ActiveFor(enemy), "last domain expires without cached flag");
    }
    private static void ScalarContracts()
    {
        var (state, player, enemy) = Fixture();
        foreach (PowerModel power in new PowerModel[] { new FlutterPower(), new SoarPower(), new IntangiblePower(), new SlipperyPower(), new HardToKillPower() })
        {
            power.Owner = enemy;
            var multiplier = power is FlutterPower or SoarPower;
            var hp = power is SlipperyPower;
            string method = multiplier ? "NeutralMultiplier" : hp ? "NeutralHpLoss" : "NeutralCap";
            decimal? incoming = hp ? 17m : null;
            decimal neutral = multiplier ? 1m : hp ? 17m : decimal.MaxValue;
            Check(Scalar(method, power, enemy, 0.5m, incoming) == neutral, power.GetType().Name + " own benefit neutral");
            Check(Scalar(method, power, player, 0.5m, incoming) == 0.5m, "different target preserved");
            Check(Scalar(method, power, null, 0.5m, incoming) == 0.5m, "null target preserved");
            player.Domain = false;
            Check(Scalar(method, power, enemy, 0.5m, incoming) == 0.5m, "inactive vanilla exact");
            player.Domain = true; power.Owner = player;
            Check(Scalar(method, power, player, 0.5m, incoming) == 0.5m, "player protection preserved");
        }
        var intangible = new IntangiblePower { Owner = enemy };
        foreach (var amount in new[] { 0m, 0.5m, 1m, 20m })
            Check(Scalar("NeutralHpLoss", intangible, enemy, 1m, amount) == amount, "HP modifier passes exact incoming amount");
    }
    private static void ArtifactContracts()
    {
        var (_, player, enemy) = Fixture();
        var power = new ArtifactPower { Owner = enemy };
        object?[] args = [power, enemy, -2m, 99m, true];
        Check(Call("AllowArtifactDebuff", args) is false && (decimal)args[3]! == -2m && args[4] is false,
            "artifact veto neutral: unchanged amount, no modified-listener consumption");
        foreach (var target in new[] { player, new Creature { IsEnemy = true } })
        {
            args = [power, target, 2m, 99m, true];
            Check(Call("AllowArtifactDebuff", args) is true && (decimal)args[3]! == 99m && args[4] is true,
                "unrelated artifact target untouched");
        }
        power.Owner = player; args = [power, player, 2m, 99m, true];
        Check(Call("AllowArtifactDebuff", args) is true, "player Artifact remains active");
        power.Owner = enemy; player.Domain = false; args = [power, enemy, 2m, 99m, true];
        Check(Call("AllowArtifactDebuff", args) is true, "Artifact resumes when domain expires");
    }
    private static void RetaliationAndHealContracts()
    {
        var (_, player, enemy) = Fixture();
        foreach (var power in new PowerModel[] { new ThornsPower { Owner = enemy }, new ReflectPower { Owner = enemy } })
        {
            object?[] args = [power, enemy, null];
            Check(Call("SuppressRetaliation", args) is false && args[2] is Task { IsCompletedSuccessfully: true }, "pure enemy retaliation suppressed with nonnull Task");
            args = [power, player, null];
            Check(Call("SuppressRetaliation", args) is true && args[2] is null, "retaliation target identity checked");
            power.Owner = player; args = [power, player, null];
            Check(Call("SuppressRetaliation", args) is true, "player retaliation preserved regardless of combat phase");
        }
        object?[] heal = [enemy, 5m, null];
        Check(Call("SuppressEnemyHeal", heal) is false && heal[2] is Task { IsCompletedSuccessfully: true }, "positive enemy heal suppressed");
        foreach (var amount in new[] { 0m, -3m })
        {
            heal = [enemy, amount, null];
            Check(Call("SuppressEnemyHeal", heal) is true && heal[2] is null, "nonpositive heal not suppressed");
        }
        heal = [player, 10m, null];
        Check(Call("SuppressEnemyHeal", heal) is true, "player healing unchanged");
        enemy.IsAlive = false; heal = [enemy, 10m, null];
        Check(Call("SuppressEnemyHeal", heal) is true, "dead-target resurrection explicitly outside slice");
        enemy.IsAlive = true; player.Domain = false; heal = [enemy, 10m, null];
        Check(Call("SuppressEnemyHeal", heal) is true, "enemy heal restored after domain");
    }
    private static void ShellWindowContracts()
    {
        var (state, player, enemy) = Fixture();
        var shell = new HardenedShellPower { Owner = enemy };
        player.Domain = false;
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "never-participating vanilla shell unchanged even if negative");
        player.Domain = true;
        Check(Scalar("NeutralShell", shell, enemy, 2m, 10m) == 10m, "active shell neutral and window stamped");
        player.Domain = false;
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == 0m, "participating overflow cap clamps only within current window");
        Check(Scalar("NeutralShell", shell, enemy, 3m, 10m) == 3m, "normal positive remaining quota preserved");
        Check(Scalar("NeutralShell", shell, enemy, -5m, 0m) == -5m, "nonpositive incoming unchanged");
        var other = new HardenedShellPower { Owner = enemy };
        Check(Scalar("NeutralShell", other, enemy, -5m, 10m) == -5m, "same owner another power not stamped");
        Check(Scalar("NeutralShell", shell, player, -5m, 10m) == -5m, "wrong target not clamped");
        state.RoundNumber++;
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "new round vanilla exact");
        state.RoundNumber--; Call("ClearShellWindow", shell);
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "native same-round reset clears participation");
        player.Domain = true; Scalar("NeutralShell", shell, enemy, 2m, 10m); player.Domain = false;
        CombatManager.Instance.Current = new TestCombat();
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "stale combat no clamp");
        CombatManager.Instance.Current = state;
        state.Creatures.Remove(enemy);
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "removed enemy no clamp");
        state.Creatures.Add(enemy); CombatManager.Instance.IsOverOrEnding = true;
        Check(Scalar("NeutralShell", shell, enemy, -5m, 10m) == -5m, "ended combat no clamp");
    }
}
