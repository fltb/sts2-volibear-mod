using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Core;

namespace Volibear;

/// <summary>Actual native encounters/moves and native card queries. Not ordinary input acceptance.
/// Mixed/player rows check temporary self-debuff suppression and restoration on exit.</summary>
internal static class DomainCardContributionsProbe
{
    private static bool _started, _installed;
    public static string Family => System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_DOMAIN_CARD_CASE") ?? "";
    public static EncounterModel Encounter => Family switch
    {
        "hex" => ModelDb.Encounter<KnightsElite>(), "tangled" => ModelDb.Encounter<VineShamblerNormal>(),
        "smoggy" => ModelDb.Encounter<LivingFogNormal>(), "ringing" => ModelDb.Encounter<CeremonialBeastBoss>(),
        _ => throw new InvalidOperationException("Unsupported domain-card contribution family")
    };
    private static Type SourceType => Family switch { "hex" => typeof(SpectralKnight), "tangled" => typeof(VineShambler),
        "smoggy" => typeof(LivingFog), "ringing" => typeof(CeremonialBeast), _ => throw new InvalidOperationException() };
    private static Type PowerType => Family switch { "hex" => typeof(HexPower), "tangled" => typeof(TangledPower),
        "smoggy" => typeof(SmoggyPower), "ringing" => typeof(RingingPower), _ => throw new InvalidOperationException() };
    private static string MoveId => Family switch { "hex" => "HEX", "tangled" => "GRASPING_VINES_MOVE",
        "smoggy" => "ADVANCED_GAS_MOVE", "ringing" => "BEAST_CRY_MOVE", _ => throw new InvalidOperationException() };
    public static void Install()
    {
        if (_installed) return;
        if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") != "domain-card-contributions")
            throw new InvalidOperationException("Explicit isolated contribution scenario required");
        DomainCardContributions.Install();
        _installed = true; CombatManager.Instance.TurnStarted += OnTurn;
    }
    private static void OnTurn(CombatState state) { if (_started) return; _started = true; _ = Run(state); }
    private static uint CreatureId(Creature creature) => creature.CombatId ?? throw new InvalidOperationException("Missing native creature ID");
    private static uint CardId(CardModel card) => NetCombatCardDb.Instance.TryGetCardId(card, out var id) ? id
        : throw new InvalidOperationException("Missing native combat card ID");
    private static async Task Until(Func<bool> predicate)
    {
        var watch = System.Diagnostics.Stopwatch.StartNew(); var tree = (SceneTree)Engine.GetMainLoop();
        while (!predicate())
        {
            if (watch.Elapsed > TimeSpan.FromSeconds(60)) throw new TimeoutException("Native contribution fixture timed out");
            await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
        }
    }
    private static async Task Run(CombatState state)
    {
        try
        {
            string token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN") ?? "";
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("Missing release metadata");
            if (string.IsNullOrWhiteSpace(token) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn || release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit)
                throw new InvalidOperationException("Wrong isolated pinned native fixture");
            var player = state.Players.Single(); var owner = player.Creature; var choices = new ThrowingPlayerChoiceContext();
            var source = state.Enemies.Single(e => e.Monster?.GetType() == SourceType);
            if (!ReferenceEquals(state, CombatManager.Instance.DebugOnlyGetState()) || state.RoundNumber != 1 ||
                player.PlayerCombatState!.TurnNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.GetPowerAmount<DomainPower>() != 0)
                throw new InvalidOperationException("Expected untouched first-turn native encounter");
            await Until(() => player.PlayerCombatState.Phase == PlayerTurnPhase.Play);
            uint sourceId = CreatureId(source), ownerId = CreatureId(owner);
            var initialRoster = state.Enemies.Select(e => new { id = CreatureId(e), type = e.Monster!.GetType().Name }).ToArray();
            // Keep a native encounter alive after source escape/death; never revive or fake an enemy.
            bool keeperAdded = state.Enemies.Count == 1;
            // Add fixture assets without replacing/unloading the current native encounter's asset set.
            var paths = ModelDb.Card<StrikeIronclad>().RunAssetPaths.Concat(ModelDb.Card<DefendIronclad>().RunAssetPaths)
                .Concat(keeperAdded ? ModelDb.Monster<LeafSlimeS>().AssetPaths : Array.Empty<string>()).Distinct()
                .Except(PreloadManager.Cache.GetLoadedCacheAssets());
            var assets = PreloadManager.Cache.CreateSession("Volibear contribution probe fixtures", paths);
            if (!await NAssetLoader.Instance.LoadInTheBackground(assets))
                throw new InvalidOperationException("Native fixture asset preload failed");
            if (keeperAdded) await CreatureCmd.Add<LeafSlimeS>(state);
            foreach (var enemy in state.Enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 1000m);
            await CreatureCmd.GainBlock(owner, 1000m, ValueProp.Unpowered, null);
            CardModel subject = Family == "tangled" ? state.CreateCard<StrikeIronclad>(player) : state.CreateCard<DefendIronclad>(player);
            await CardPileCmd.Add(subject, player.PlayerCombatState.Hand);
            var refs = new Dictionary<object, string>(ReferenceEqualityComparer.Instance);
            string? Ref(object? obj)
            {
                if (obj is null) return null;
                if (!refs.TryGetValue(obj, out string? id)) { id = "ref-" + (refs.Count + 1); refs.Add(obj, id); }
                return id;
            }
            var steps = new List<object>(); var plays = new List<object>();
            PowerModel? Power() => owner.Powers.SingleOrDefault(p => p.GetType() == PowerType);
            void Snapshot(string phase)
            {
                var power = Power(); bool canPlay = subject.CanPlay(out var reason, out var preventer);
                steps.Add(new { phase, round = state.RoundNumber, domain = owner.GetPowerAmount<DomainPower>(),
                    sourceAttached = state.ContainsCreature(source), sourceAlive = source.IsAlive, ownerId, sourceId,
                    cardId = CardId(subject), cardType = subject.GetType().Name, cardRef = Ref(subject),
                    pile = subject.Pile?.Type.ToString(), affliction = subject.Affliction?.GetType().Name, afflictionRef = Ref(subject.Affliction),
                    power = power?.GetType().Name, powerRef = Ref(power), amount = power?.Amount ?? 0,
                    applierId = power?.Applier?.CombatId, applierIsPlayer = power?.Applier?.IsPlayer,
                    origin = power is null ? null : DomainCardContributions.Audit(power),
                    ethereal = subject.GetKeywordsWithSources(KeywordSources.All).Contains(CardKeyword.Ethereal),
                    cost = subject.EnergyCost.GetWithModifiers(CostModifiers.All), canPlay, reason = reason.ToString(), preventer = preventer?.GetType().Name,
                    powerPresent = power is not null, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn });
            }
            async Task PlayDefend(string phase)
            {
                var card = state.CreateCard<DefendIronclad>(player);
                await CardPileCmd.Add(card, player.PlayerCombatState.Hand);
                await CardCmd.AutoPlay(choices, card, null);
                int count = CombatManager.Instance.History.Entries.OfType<CardPlayStartedEntry>().Count(e => ReferenceEquals(e.CardPlay.Card, card));
                if (count != 1) throw new InvalidOperationException("Expected one actual native card-play-start history entry");
                plays.Add(new { phase, cardId = CardId(card), cardType = card.GetType().Name, nativeStarts = count, isAutoPlay = true });
            }
            // Repeated actual public card queries warm the native Hook dispatch before switching domain.
            for (int i = 0; i < 16; i++)
            {
                _ = subject.GetKeywordsWithSources(KeywordSources.All); _ = subject.EnergyCost.GetWithModifiers(CostModifiers.All); _ = subject.CanPlay();
            }
            Snapshot("warm");
            source.Monster!.SetMoveImmediate((MoveState)source.Monster.MoveStateMachine!.States[MoveId], forceTransition: true);
            await source.Monster.PerformMove();
            var moves = CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>()
                .Where(e => ReferenceEquals(e.Monster, source.Monster)).Select(e => new { sourceId, type = e.Monster.GetType().Name, move = e.Move.Id }).ToArray();
            if (moves.Length != 1 || moves[0].move != MoveId || Power() is null) throw new InvalidOperationException("Real native source move did not complete");
            var received = CombatManager.Instance.History.Entries.OfType<PowerReceivedEntry>()
                .Where(e => ReferenceEquals(e.Power, Power())).Select(e => new { type = e.Power.GetType().Name, amount = e.Amount,
                    applierId = e.Applier?.CombatId, targetId = CreatureId(e.Power.Owner) }).ToArray();
            if (Family is "smoggy" or "ringing") await PlayDefend("activate-native-restriction");
            Snapshot("off");
            await DomainPower.Open(choices, owner, 5); Snapshot("on");
            if (Family == "hex")
            {
                subject.AddKeyword(CardKeyword.Ethereal); Snapshot("other-source"); subject.RemoveKeyword(CardKeyword.Ethereal);
            }
            else if (Family == "tangled")
            {
                subject.EnergyCost.AddThisCombat(2); Snapshot("other-source"); subject.EnergyCost.AddThisCombat(-2);
            }
            else
            {
                await PowerCmd.Apply<SlothPower>(choices, owner, 1m, owner, null);
                await PlayDefend("activate-other-native-veto"); Snapshot("other-source");
                await PowerCmd.Remove<SlothPower>(owner);
            }
            Snapshot("other-removed"); await PowerCmd.Remove<DomainPower>(owner); Snapshot("off-again");
            await DomainPower.Open(choices, owner, 5);
            // Escape is an actual native removal, distinct from death cleanup. Saved same-combat cause must survive it.
            await CreatureCmd.Escape(source); Snapshot("departed-on");
            await PowerCmd.Remove<DomainPower>(owner); Snapshot("departed-off");
            await DomainPower.Open(choices, owner, 5);
            var original = Power() ?? throw new InvalidOperationException("Native escape unexpectedly removed target power");
            await PowerCmd.ModifyAmount(choices, original, 1m, owner, null); Snapshot("mixed-native");
            // Hex has death cleanup rather than duration expiry; explicitly remove this escaped-caster instance.
            if (Family == "hex") { await PowerCmd.Remove(original); Snapshot("removed-cleanup"); }
            int round = state.RoundNumber;
            MegaCrit.Sts2.Core.Runs.RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
                new MegaCrit.Sts2.Core.GameActions.EndPlayerTurnAction(player, player.PlayerCombatState.TurnNumber));
            await Until(() => state.RoundNumber > round && state.CurrentSide == CombatSide.Player && player.PlayerCombatState.Phase == PlayerTurnPhase.Play);
            Snapshot("native-next-turn");
            // Smoggy persists while its per-turn affliction clears. Remove it before the separate player-applied control.
            if (Power() is { } remaining) await PowerCmd.Remove(remaining);
            await DomainPower.Open(choices, owner, 5);
            uint? deathSourceId = null;
            if (Family == "hex")
            {
                // Separate actual SpectralKnight death proves its own AfterDeath removal/clear remains live.
                var deathSource = await CreatureCmd.Add<SpectralKnight>(state, source.SlotName);
                deathSourceId = CreatureId(deathSource);
                deathSource.Monster!.SetMoveImmediate((MoveState)deathSource.Monster.MoveStateMachine!.States[MoveId], forceTransition: true);
                await deathSource.Monster.PerformMove(); Snapshot("death-before");
                var deathMoves = CombatManager.Instance.History.Entries.OfType<MonsterPerformedMoveEntry>()
                    .Where(e => ReferenceEquals(e.Monster, deathSource.Monster))
                    .Select(e => new { sourceId = CreatureId(e.Monster.Creature), type = e.Monster.GetType().Name, move = e.Move.Id }).ToArray();
                if (deathMoves.Length != 1) throw new InvalidOperationException("Missing actual death-control source move");
                moves = moves.Concat(deathMoves).ToArray();
                await CreatureCmd.Kill(deathSource, force: true); Snapshot("death-after");
            }
            PowerModel control = Family switch { "hex" => ModelDb.Power<HexPower>().ToMutable(), "tangled" => ModelDb.Power<TangledPower>().ToMutable(),
                "smoggy" => ModelDb.Power<SmoggyPower>().ToMutable(), "ringing" => ModelDb.Power<RingingPower>().ToMutable(), _ => throw new InvalidOperationException() };
            await PowerCmd.Apply(choices, control, owner, 1m, owner, null);
            if (Family is "smoggy" or "ringing") await PlayDefend("activate-player-control");
            Snapshot("player-control");
            await PowerCmd.Remove<DomainPower>(owner); Snapshot("player-control-off");
            GD.Print("[Volibear] DOMAIN_CARD_CONTRIBUTIONS_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 3, token, scenario = "domain-card-contributions", family = Family,
                acceptance = "four-native-contributions-not-affliction-writes-or-ordinary-input", testMode = false,
                version = release.Version, commit = release.Commit, encounter = Encounter.GetType().Name,
                sourceType = SourceType.Name, sourceId, ownerId, initialRoster, keeperAdded,
                nativeMoveCalls = moves.Length, deathSourceId, directPowerCallbackCalls = 0, warmupQueriesPerApi = 16,
                ilSites = DomainCardContributions.VerifyNativeIl(), moves, received, plays, steps,
                mixedStackPolicy = "all-player-debuffs-temporarily-muted", insertionCoverage = false,
                afflictionWriteSuppression = false, hexCleanupKind = Family == "hex" ? "native-PowerCmd.Remove-after-escape" : null
            }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error) { GD.PrintErr("[Volibear] DOMAIN_CARD_CONTRIBUTIONS_ERROR " + error); ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { CombatManager.Instance.TurnStarted -= OnTurn; }
    }
}
