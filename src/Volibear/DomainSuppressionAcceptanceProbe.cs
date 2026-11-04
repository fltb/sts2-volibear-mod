using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>Isolated native mechanism fixture: actual moves, power commands and turn lifecycle.</summary>
internal static class DomainSuppressionAcceptanceProbe
{
    private static bool installed, started;
    private static string? currentFamily;
    public static string RequestedFamily => Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_SUPPRESSION_CASE") ?? "all";
    public static string Family => currentFamily ?? (RequestedFamily == "all" ? "sandpit" : RequestedFamily);
    public static EncounterModel Encounter => Family == "sandpit" ? ModelDb.Encounter<TheInsatiableBoss>() : ModelDb.Encounter<KnightsElite>();
    public static void Install()
    {
        if (installed) return;
        if (Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") != "domain-suppression") throw new InvalidOperationException("Isolated suppression scenario required");
        installed = true;
        CombatManager.Instance.TurnStarted += OnTurn;
    }
    private static void OnTurn(CombatState state) { if (started) return; started = true; _ = Run(state); }
    private static async Task Until(Func<bool> done)
    {
        var timer = System.Diagnostics.Stopwatch.StartNew(); var tree = (SceneTree)Engine.GetMainLoop();
        while (!done())
        {
            if (timer.Elapsed > TimeSpan.FromSeconds(60)) throw new TimeoutException("Suppression native turn timeout");
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    private static IEnumerable<Node> Walk(Node node)
    {
        yield return node;
        foreach (Node child in node.GetChildren())
            foreach (var descendant in Walk(child)) yield return descendant;
    }
    private static async Task<bool> DisabledViews(Creature owner, bool expected)
    {
        var view = NCombatRoom.Instance!.GetCreatureNode(owner)!;
        MegaCrit.Sts2.Core.Nodes.Combat.NPower[] icons = [];
        await Until(() => (icons = Walk(view).OfType<MegaCrit.Sts2.Core.Nodes.Combat.NPower>()
            .Where(n => n.Model is DampenPower or HexPower).ToArray()).Length == 2);
        // Observe a rendered frame after the native state-change event, without input.
        var tree = (SceneTree)Engine.GetMainLoop();
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        var overlays = icons.Select(n => n.GetNode<Control>("VolibearDomainDisabled")).ToArray();
        var badge = view.Hitbox.GetNode<Control>("VolibearDomainDisabled");
        bool tips = icons.All(n => n.Model.HoverTips.OfType<MegaCrit.Sts2.Core.HoverTips.HoverTip>()
            .Any(t => t.Description.Contains("已被领域禁用")) == expected);
        bool creatureTip = owner.HoverTips.Any(t => t.Id == "VOLIBEAR-DISABLED-SELF") == expected;
        // Deliberate visual contract: one packed rune per disabled entry, never a label.
        bool iconOnly = overlays.All(n => n.GetChildCount() == 2 && !Walk(n).OfType<Label>().Any()) &&
            badge.GetChildCount() == 1 && badge.GetChild(0) is TextureRect &&
            !Walk(badge).OfType<Label>().Any() && !Walk(badge).OfType<RichTextLabel>().Any();
        return overlays.All(n => n.IsVisibleInTree() == expected && n.GetChildCount() == 2) &&
            badge.IsVisibleInTree() == expected && iconOnly && tips && creatureTip;
    }
    internal sealed record WeakDurationStep(string Phase, int Amount, bool Skip);
    internal static async Task<WeakDurationStep[]> ObserveWeakDuration(WeakPower weak, Creature owner, ThrowingPlayerChoiceContext choices)
    {
        // Weak ticks only at Enemy-side end. BaseLib 3.4.7's awaited
        // SelfApplyDebuffPatch clears the native skip flag for custom-player
        // self-applied debuffs during the player side; preserve that full chain.
        var rows = new List<WeakDurationStep> { new("applied", weak.Amount, weak.SkipNextDurationTick) };
        await weak.AfterSideTurnEnd(choices, CombatSide.Player, new[] { owner });
        rows.Add(new("player-end", weak.Amount, weak.SkipNextDurationTick));
        await weak.AfterSideTurnEnd(choices, CombatSide.Enemy, new[] { owner });
        rows.Add(new("first-enemy-end", weak.Amount, weak.SkipNextDurationTick));
        await weak.AfterSideTurnEnd(choices, CombatSide.Enemy, new[] { owner });
        rows.Add(new("next-enemy-end", weak.Amount, weak.SkipNextDurationTick));
        return rows.ToArray();
    }
    internal static Task RunManaged() => RunManaged("sandpit");
    internal static async Task RunManaged(string firstFamily)
    {
        if (firstFamily is not ("sandpit" or "self")) throw new ArgumentException("Unknown managed starting family", nameof(firstFamily));
        NativeAcceptanceRunHost.RequireClean();
        currentFamily = firstFamily;
        try
        {
            var initial = await NativeAcceptanceRunHost.StartFresh(Encounter, "volibear-domain-suppression-" + firstFamily);
            await Run(initial, managed: true);
        }
        finally { currentFamily = null; }
    }
    private static async Task Run(CombatState state, bool managed = false)
    {
        var checks = new Dictionary<string, bool>();
        var steps = new List<object>();
        void Check(string name, bool passed) { checks.Add(name, passed); if (!passed) throw new InvalidOperationException("Suppression assertion: " + name); }
        try
        {
            var release = ReleaseInfoManager.Instance.ReleaseInfo!;
            string token = Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
            if (token.Length == 0 || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn || release.Version != "v0.107.1" || release.Commit != "59260271")
                throw new InvalidOperationException("Pinned native fixture required");
            var player = state.Players.Single(); var owner = player.Creature; var choices = new ThrowingPlayerChoiceContext();
            await Until(() => player.PlayerCombatState!.Phase == PlayerTurnPhase.Play);
            Check("fresh-domain-off", owner.GetPower<DomainPower>() is null && state.RoundNumber == 1);
            await CreatureCmd.GainBlock(owner, 10000m, ValueProp.Unpowered, null);
            foreach (var enemy in state.Enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 10000m);
            async Task Move(Creature enemy, string id)
            {
                enemy.Monster!.SetMoveImmediate((MoveState)enemy.Monster.MoveStateMachine!.States[id], forceTransition: true);
                await enemy.Monster.PerformMove();
            }
            async Task Turn()
            {
                int round = state.RoundNumber;
                MegaCrit.Sts2.Core.Runs.RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
                    new MegaCrit.Sts2.Core.GameActions.EndPlayerTurnAction(player, player.PlayerCombatState!.TurnNumber));
                await Until(() => state.RoundNumber > round && state.CurrentSide == CombatSide.Player && player.PlayerCombatState!.Phase == PlayerTurnPhase.Play);
            }
            if (Family == "sandpit")
            {
                var enemy = state.Enemies.Single(e => e.Monster is TheInsatiable);
                await Move(enemy, "LIQUIFY_GROUND_MOVE");
                var pit = enemy.Powers.OfType<SandpitPower>().Single(p => ReferenceEquals(p.Target, owner));
                int initial = pit.Amount;
                await DomainPower.Open(choices, owner, 5);
                float x = NCombatRoom.Instance!.GetCreatureNode(owner)!.GlobalPosition.X;
                steps.Add(new { phase = "baseline", count = initial, x });
                await Turn();
                float during = NCombatRoom.Instance!.GetCreatureNode(owner)!.GlobalPosition.X;
                Check("sandpit-counter-frozen", pit.Amount == initial && enemy.Powers.Contains(pit));
                Check("sandpit-position-frozen", Math.Abs(x - during) <= 1f);
                Check("sandpit-player-alive", owner.IsAlive);
                steps.Add(new { phase = "domain-on", count = pit.Amount, x = during });
                await PowerCmd.Remove<DomainPower>(owner);
                await Turn();
                Check("sandpit-resumes-one-tick", pit.Amount == initial - 1 && enemy.Powers.Contains(pit));
                steps.Add(new { phase = "domain-off", count = pit.Amount, x = NCombatRoom.Instance.GetCreatureNode(owner)!.GlobalPosition.X });
                Check("sandpit-position-resumes", Math.Abs(during - NCombatRoom.Instance.GetCreatureNode(owner)!.GlobalPosition.X) > 1f);
            }
            else if (Family == "knights")
            {
                var card = player.PlayerCombatState!.AllCards.First(c => c.IsUpgradable);
                CardCmd.Upgrade(card);
                int upgraded = card.CurrentUpgradeLevel;
                await Move(state.Enemies.Single(e => e.Monster is MagiKnight), "DAMPEN_MOVE");
                await Move(state.Enemies.Single(e => e.Monster is SpectralKnight), "HEX");
                var dampen = owner.GetPower<DampenPower>()!; var hex = owner.GetPower<HexPower>()!;
                Check("dampen-applied-before-entry", card.CurrentUpgradeLevel == 0 && dampen is not null);
                Check("hex-applied-before-entry", card.GetKeywordsWithSources(KeywordSources.All).Contains(CardKeyword.Ethereal) && hex is not null);
                Check("disabled-ui-before-domain", await DisabledViews(owner, false));
                await DomainPower.Open(choices, owner, 5);
                Check("disabled-ui-during-domain", await DisabledViews(owner, true));
                Check("dampen-entry-restores-upgrade", card.CurrentUpgradeLevel == upgraded);
                Check("hex-entry-restores-retention", !card.GetKeywordsWithSources(KeywordSources.All).Contains(CardKeyword.Ethereal));
                Check("native-debuff-identities-retained", ReferenceEquals(owner.GetPower<DampenPower>(), dampen) && ReferenceEquals(owner.GetPower<HexPower>(), hex));
                card.AddKeyword(CardKeyword.Ethereal);
                Check("independent-ethereal-retained", card.GetKeywordsWithSources(KeywordSources.All).Contains(CardKeyword.Ethereal));
                card.RemoveKeyword(CardKeyword.Ethereal);
                await PowerCmd.Remove<DomainPower>(owner);
                Check("disabled-ui-after-domain", await DisabledViews(owner, false));
                Check("dampen-exit-resumes-downgrade", card.CurrentUpgradeLevel == 0);
                Check("hex-exit-resumes-ethereal", card.GetKeywordsWithSources(KeywordSources.All).Contains(CardKeyword.Ethereal));
                await DomainPower.Open(choices, owner, 5);
                await PowerCmd.Remove(dampen);
                Check("dampen-native-removal-no-double-upgrade", card.CurrentUpgradeLevel == upgraded);
                await PowerCmd.Remove<DomainPower>(owner);
                Check("dampen-removal-survives-domain-exit", card.CurrentUpgradeLevel == upgraded);
            }
            else if (Family == "self")
            {
                var card = player.PlayerCombatState!.AllCards.First();
                await PowerCmd.Apply<MindRotPower>(choices, owner, 2m, owner, card);
                await PowerCmd.Apply<WasteAwayPower>(choices, owner, 1m, owner, card);
                await PowerCmd.Apply<SlothPower>(choices, owner, 1m, owner, card);
                var disintegration = await PowerCmd.Apply<DisintegrationPower>(choices, owner, 3m, owner, card);
                var weak = await PowerCmd.Apply<WeakPower>(choices, owner, 2m, owner, card);
                Check("self-source-mindrot-before", Hook.ModifyHandDraw(state, player, 5m, out _) == 3m);
                Check("self-source-waste-before", Hook.ModifyMaxEnergy(state, player, 3m) == 2m);
                await DomainPower.Open(choices, owner, 5);
                Check("self-source-mindrot-restored", Hook.ModifyHandDraw(state, player, 5m, out _) == 5m);
                Check("self-source-waste-restored", Hook.ModifyMaxEnergy(state, player, 3m) == 3m);
                Check("self-source-sloth-muted", DomainSelfDebuffEffects.IsSuppressed(owner.GetPower<SlothPower>()!));
                decimal hp = owner.CurrentHp, block = owner.Block;
                await disintegration!.AfterSideTurnEndLate(choices, CombatSide.Player, new[] { owner });
                Check("self-disintegration-callback-muted", owner.CurrentHp == hp && owner.Block == block);
                var duration = await ObserveWeakDuration(weak!, owner, choices);
                GD.Print("[Volibear] DOMAIN_WEAK_DURATION " + JsonSerializer.Serialize(new { token, stages = duration }));
                Check("native-weak-duration-ticked", duration.SequenceEqual(new[] {
                    new WeakDurationStep("applied", 2, false), new WeakDurationStep("player-end", 2, false),
                    new WeakDurationStep("first-enemy-end", 1, false), new WeakDurationStep("next-enemy-end", 0, false) }) &&
                    owner.GetPower<WeakPower>() is null);
                await PowerCmd.Apply<NoDrawPower>(choices, owner, 1m, owner, card);
                Check("new-no-draw-committed-muted", owner.GetPower<NoDrawPower>() is not null && Hook.ShouldDraw(state, player, false, out _));
                await PowerCmd.Remove<DomainPower>(owner);
                Check("self-mindrot-resumes", Hook.ModifyHandDraw(state, player, 5m, out _) == 3m);
                Check("self-waste-resumes", Hook.ModifyMaxEnergy(state, player, 3m) == 2m);
                Check("new-no-draw-resumes", !Hook.ShouldDraw(state, player, false, out _));
            }
            else throw new InvalidOperationException("Unknown suppression family " + Family);
            GD.Print("[Volibear] DOMAIN_SUPPRESSION_RESULT " + JsonSerializer.Serialize(new { schema = 1, token, scenario = "domain-suppression", family = Family,
                version = release.Version, commit = release.Commit, testMode = false, checks, steps, passed = true }));
            if ((managed || RequestedFamily == "all") && Family != "self")
            {
                string next = Family == "sandpit" ? "knights" : "self";
                await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);
                currentFamily = next;
                var fresh = await NativeAcceptanceRunHost.StartFresh(Encounter, "volibear-domain-suppression-" + next);
                await Run(fresh, managed);
                return;
            }
            if (managed)
            {
                await NativeAcceptanceRunHost.ExitToMainMenu(enterMapFirst: false);
                NativeAcceptanceRunHost.RequireClean();
                return;
            }
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] DOMAIN_SUPPRESSION_ERROR " + JsonSerializer.Serialize(new { family = Family, checks, steps, error = error.ToString() }));
            if (managed) throw;
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { CombatManager.Instance.TurnStarted -= OnTurn; }
    }
}
