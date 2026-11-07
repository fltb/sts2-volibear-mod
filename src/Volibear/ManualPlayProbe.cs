using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using Volibear.Content;

namespace Volibear;

/// <summary>Isolated fixture and read-only evidence collector. The external owned-window
/// runner supplies real Windows mouse input; this probe never plays a card or pays a cost.</summary>
internal static class ManualPlayProbe
{
    private static bool _installed;
    private static bool _started;
    public static void Install()
    {
        if (_installed) return;
        if (System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_SCENARIO") != "manual-play")
            throw new InvalidOperationException("Manual fixture requires explicit isolated scenario");
        _installed = true;
        CombatManager.Instance.TurnStarted += OnTurn;
    }
    private static void OnTurn(CombatState state)
    {
        if (_started) return;
        _started = true;
        _ = Run(state);
    }
    private static async Task Pause(double seconds)
    {
        var game = NGame.Instance!;
        await game.ToSignal(game.GetTree().CreateTimer(seconds), SceneTreeTimer.SignalName.Timeout);
    }
    private static async Task Until(Func<bool> condition, double seconds, string label)
    {
        var clock = Stopwatch.StartNew();
        while (!condition())
        {
            if (clock.Elapsed.TotalSeconds >= seconds) throw new TimeoutException(label);
            await Pause(0.05);
        }
    }
    private static uint Id(CardModel card) => NetCombatCardDb.Instance.TryGetCardId(card, out var id)
        ? id : throw new InvalidOperationException("No native combat-card ID");
    private static uint Id(Creature creature) => creature.CombatId
        ?? throw new InvalidOperationException("No native creature ID");
    private static float[] Point(Vector2 vector) => [vector.X, vector.Y];
    private static int[] Point(Vector2I vector) => [vector.X, vector.Y];
    private static float[] Rect(Rect2 rect) => [rect.Position.X, rect.Position.Y, rect.Size.X, rect.Size.Y];
    private static bool SameGeometry(Rect2 a, Rect2 b) =>
        a.Position.DistanceSquaredTo(b.Position) < 0.25f && a.Size.DistanceSquaredTo(b.Size) < 0.25f;
    private static Rect2 ViewportBounds(Control node)
    {
        var transform = node.GetGlobalTransformWithCanvas();
        var corners = new[] { transform * Vector2.Zero, transform * new Vector2(node.Size.X, 0),
            transform * node.Size, transform * new Vector2(0, node.Size.Y) };
        var low = new Vector2(corners.Min(p => p.X), corners.Min(p => p.Y));
        var high = new Vector2(corners.Max(p => p.X), corners.Max(p => p.Y));
        return new Rect2(low, high - low);
    }
    private static bool TryInputPoint(Control? node, out Vector2 local, out Rect2 visible)
    {
        local = Vector2.Zero;
        visible = default;
        if (node is null || !GodotObject.IsInstanceValid(node) || !node.IsInsideTree() ||
            !node.IsVisibleInTree() || node.Size.X <= 0 || node.Size.Y <= 0 ||
            node.MouseFilter == Control.MouseFilterEnum.Ignore ||
            node is NClickableControl { IsEnabled: false }) return false;
        // A hand card can extend below the viewport. Click the actual visible input region,
        // never the visual Body's (possibly zero-sized) layout origin or offscreen center.
        visible = ViewportBounds(node).Intersection(node.GetViewport().GetVisibleRect().Grow(-8));
        var clips = new List<Control>();
        for (Node? parent = node.GetParent(); parent is not null; parent = parent.GetParent())
            if (parent is Control { ClipContents: true } clip)
            {
                clips.Add(clip);
                visible = visible.Intersection(ViewportBounds(clip));
            }
        if (visible.Size.X < 8 || visible.Size.Y < 8) return false;
        var viewportPoint = visible.GetCenter();
        local = node.GetGlobalTransformWithCanvas().AffineInverse() * viewportPoint;
        if (!new Rect2(Vector2.Zero, node.Size).HasPoint(local)) return false;
        // Bounding rectangles alone are insufficient for rotated/clipped controls.
        return clips.All(clip => new Rect2(Vector2.Zero, clip.Size).HasPoint(
            clip.GetGlobalTransformWithCanvas().AffineInverse() * viewportPoint));
    }
    private static object Anchor(Control node, string role, string source)
    {
        if (!TryInputPoint(node, out var local, out var visible))
            throw new InvalidOperationException("Native input anchor unavailable: " + role);
        return new { nodeId = node.GetInstanceId(), role, source, local = Point(local),
            visibleRect = Rect(visible), viewport = Point(node.GetGlobalTransformWithCanvas() * local),
            screen = Point(node.GetScreenTransform() * local) };
    }
    private static object DescribeNode(Control? node, string role)
    {
        if (node is null || !GodotObject.IsInstanceValid(node)) return new { role, valid = false };
        if (!node.IsInsideTree()) return new { role, valid = true, inTree = false,
            name = node.Name.ToString(), type = node.GetType().Name, visible = node.Visible,
            size = Point(node.Size), rect = Rect(node.GetRect()) };
        var ancestors = new List<object>();
        for (Node? parent = node.GetParent(); parent is not null && ancestors.Count < 16; parent = parent.GetParent())
            ancestors.Add(new { path = parent.GetPath().ToString(), type = parent.GetType().Name,
                visible = parent is CanvasItem canvas ? (bool?)canvas.IsVisibleInTree() : null,
                clip = parent is Control control ? (bool?)control.ClipContents : null });
        return new { role, valid = true, path = node.GetPath().ToString(), type = node.GetType().Name,
            nodeId = node.GetInstanceId(), inTree = node.IsInsideTree(), visible = node.Visible,
            visibleInTree = node.IsVisibleInTree(), size = Point(node.Size), rect = Rect(node.GetRect()),
            globalRect = Rect(node.GetGlobalRect()), viewportRect = Rect(ViewportBounds(node)),
            mouseFilter = node.MouseFilter.ToString(), clipContents = node.ClipContents,
            enabled = node is NClickableControl clickable ? (bool?)clickable.IsEnabled : null,
            ancestors };
    }
    private static void DiagnoseAnchors(string token, string phase, NCard card,
        NHandCardHolder? holder, Control target)
    {
        GD.Print("[Volibear] MANUAL_ANCHOR_DIAGNOSTIC " + JsonSerializer.Serialize(new
        {
            token, phase, processId = System.Environment.ProcessId,
            tickMs = System.Environment.TickCount64,
            holderMatchesCard = holder is not null && ReferenceEquals(holder.CardNode, card),
            nodes = new[] { DescribeNode(card.Body, "card-visual-body"), DescribeNode(holder, "card-holder"),
                DescribeNode(holder?.Hitbox, "card-input-hitbox"), DescribeNode(target, "enemy-input-hitbox") }
        }));
    }
    private static async Task<object> Capture(string directory, string filename)
    {
        var game = NGame.Instance!;
        await game.ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
        using var image = game.GetViewport().GetTexture().GetImage();
        if (image.SavePng(Path.Combine(directory, filename)) != Error.Ok)
            throw new InvalidOperationException("Viewport capture failed");
        return new { file = filename, width = image.GetWidth(), height = image.GetHeight(),
            source = "NGame.GetViewport.GetTexture.GetImage" };
    }
    private static object Snapshot(CombatState state, Player player, CardModel card, Creature[] enemies)
    {
        var pcs = player.PlayerCombatState!;
        return new
        {
            energy = pcs.Energy, maxEnergy = pcs.MaxEnergy, phase = pcs.Phase.ToString(),
            round = state.RoundNumber, turn = pcs.TurnNumber,
            playerHp = player.Creature.CurrentHp, playerBlock = player.Creature.Block,
            playerId = Id(player.Creature), playerNetId = player.NetId,
            cardId = Id(card), cardModel = card.GetType().Name, pile = card.Pile?.Type.ToString(),
            upgraded = card.IsUpgraded,
            masterIndex = Array.FindIndex(player.Deck.Cards.ToArray(), c => ReferenceEquals(c, card.DeckVersion)),
            masterModel = card.DeckVersion?.GetType().Name,
            deck = player.Deck.Cards.Select(c => c.GetType().Name).ToArray(),
            piles = pcs.AllPiles.ToDictionary(p => p.Type.ToString(), p => p.Cards.Select(Id).ToArray()),
            enemies = enemies.Select(e => new { id = Id(e), model = e.Monster!.GetType().Name,
                hp = e.CurrentHp, maxHp = e.MaxHp, block = e.Block }).ToArray(),
            actionsDisabled = CombatManager.Instance.PlayerActionsDisabled,
            executingCard = CombatManager.Instance.IsExecutingCardOrPotionEffect(player)
        };
    }
    private static object Play(CardPlay play) => new
    {
        cardId = Id(play.Card), cardModel = play.Card.GetType().Name,
        targetId = play.Target is null ? (uint?)null : Id(play.Target),
        isAutoPlay = play.IsAutoPlay, energySpent = play.Resources.EnergySpent,
        energyValue = play.Resources.EnergyValue, starsSpent = play.Resources.StarsSpent,
        playIndex = play.PlayIndex, playCount = play.PlayCount, resultPile = play.ResultPile.ToString()
    };
    private static object Hit(DamageResult result) => new
    {
        targetId = Id(result.Receiver), unblocked = result.UnblockedDamage,
        blocked = result.BlockedDamage, overkill = result.OverkillDamage,
        killed = result.WasTargetKilled
    };
    private static object? Observe(CombatHistoryEntry entry, int index)
    {
        object? data = entry switch
        {
            CardPlayStartedEntry start => Play(start.CardPlay),
            CardPlayFinishedEntry finish => Play(finish.CardPlay),
            EnergySpentEntry energy => new { amount = energy.Amount, playerId = Id(energy.Actor) },
            CreatureAttackedEntry attack => new { attackerId = Id(attack.Actor), hits = attack.DamageResults.Select(Hit).ToArray() },
            DamageReceivedEntry damage => new { receiverId = Id(damage.Receiver),
                cardId = damage.CardSource is null ? (uint?)null : Id(damage.CardSource), hit = Hit(damage.Result) },
            _ => null
        };
        return data is null ? null : new { index, kind = entry.GetType().Name,
            tickMs = System.Environment.TickCount64, data };
    }
    private static async Task Run(CombatState state)
    {
        Action? historyObserver = null;
        Action<string>? diagnose = null;
        string? captureDirectory = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var nonce = System.Environment.GetEnvironmentVariable("VOLIBEAR_MANUAL_INPUT_NONCE");
            var directory = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_ARTIFACT_DIR");
            if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(nonce) || nonce.Length != 48 ||
                string.IsNullOrWhiteSpace(directory) || Path.GetFileName(Path.GetFullPath(directory)) != token)
                throw new InvalidOperationException("Missing fresh isolated input handshake");
            captureDirectory = directory;
            if (OS.GetName() != "Windows" || DisplayServer.GetName() == "headless" ||
                MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn ||
                MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized)
                throw new InvalidOperationException("Requires offline native Windows window, not TestMode");
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No release metadata");
            if (release.Version != global::Volibear.Core.SupportedGameBuild.Version || release.Commit != global::Volibear.Core.SupportedGameBuild.Commit)
                throw new InvalidOperationException("Unexpected game version");
            var player = state.Players.Single();
            var pcs = player.PlayerCombatState ?? throw new InvalidOperationException("Missing combat player");
            await Until(() => pcs.Phase == PlayerTurnPhase.Play && !CombatManager.Instance.PlayerActionsDisabled &&
                !CombatManager.Instance.IsExecutingCardOrPotionEffect(player), 15, "Native manual play phase unavailable");
            var enemies = state.Enemies.ToArray();
            if (player.Character is not VolibearCharacter || state.Encounter?.GetType().Name != "SlimesWeak" ||
                enemies.Length != 3 || enemies.Any(e => e.Block != 0 || !e.IsAlive) ||
                pcs.Energy != 3 || state.RoundNumber != 1 || pcs.TurnNumber != 1 || player.Creature.CurrentHp != 80)
                throw new InvalidOperationException("Expected fresh native Volibear/SlimesWeak first turn");
            var originals = pcs.AllPiles.SelectMany(p => p.Cards).ToArray();
            var card = originals.OfType<Volibear_B01>().First();
            if (originals.Length != 10 || card.IsUpgraded || card.DeckVersion is null ||
                !player.Deck.Cards.Any(c => ReferenceEquals(c, card.DeckVersion)))
                throw new InvalidOperationException("B01 must be an original unupgraded starting-deck combat entity");
            // Fixture only: move existing cards; never create/play replacements or set player energy.
            foreach (var other in pcs.Hand.Cards.Where(c => !ReferenceEquals(c, card)).ToArray())
                await CardPileCmd.Add(other, PileType.Discard);
            if (!pcs.Hand.Cards.Contains(card)) await CardPileCmd.Add(card, pcs.Hand);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy, 50m);
            var room = NCombatRoom.Instance ?? throw new InvalidOperationException("No native combat room");
            var cardNode = NCard.FindOnTable(card) ?? throw new InvalidOperationException("No native NCard");
            var target = enemies.Last();
            var targetNode = room.GetCreatureNode(target) ?? throw new InvalidOperationException("No native enemy node");
            diagnose = phase => DiagnoseAnchors(token, phase, cardNode,
                room.Ui.Hand.GetCardHolder(card) as NHandCardHolder, targetNode.Hitbox);
            diagnose("before-layout");
            NHandCardHolder? inputHolder = null;
            Vector2? previousCard = null, previousTarget = null;
            Rect2 previousCardRect = default, previousTargetRect = default;
            int stableSamples = 0;
            await Until(() =>
            {
                inputHolder = room.Ui.Hand.GetCardHolder(card) as NHandCardHolder;
                if (inputHolder is null || !ReferenceEquals(inputHolder.CardNode, cardNode) ||
                    !ReferenceEquals(inputHolder.CardModel, card) ||
                    !TryInputPoint(inputHolder.Hitbox, out var cardLocal, out var cardRect) ||
                    !TryInputPoint(targetNode.Hitbox, out var targetLocal, out var targetRect))
                { stableSamples = 0; return false; }
                var cardScreen = inputHolder.Hitbox.GetScreenTransform() * cardLocal;
                var targetScreen = targetNode.Hitbox.GetScreenTransform() * targetLocal;
                bool unchanged = previousCard is { } lastCard && previousTarget is { } lastTarget &&
                    lastCard.DistanceSquaredTo(cardScreen) < 0.25f && lastTarget.DistanceSquaredTo(targetScreen) < 0.25f &&
                    SameGeometry(previousCardRect, cardRect) && SameGeometry(previousTargetRect, targetRect);
                stableSamples = unchanged ? stableSamples + 1 : 1;
                previousCard = cardScreen; previousTarget = targetScreen;
                previousCardRect = cardRect; previousTargetRect = targetRect;
                return stableSamples >= 3;
            }, 8, "Native hand/enemy input regions did not become visible, enabled and geometrically stable");
            diagnose("layout-stable");
            var history = CombatManager.Instance.History;
            int cursor = history.Entries.Count();
            var records = new List<object>();
            historyObserver = () =>
            {
                var appended = history.Entries.Skip(cursor).ToArray();
                foreach (var entry in appended)
                {
                    var record = Observe(entry, cursor++);
                    if (record is not null) records.Add(record);
                }
            };
            history.Changed += historyObserver;
            int historyStart = cursor;
            var before = Snapshot(state, player, card, enemies);
            var beforeCapture = await Capture(directory, "manual-before.png");
            var game = NGame.Instance ?? throw new InvalidOperationException("No native game viewport");
            var viewport = game.GetViewport();
            var transform = viewport.GetScreenTransform();
            int windowId = game.GetWindow().GetWindowId();
            var ready = new
            {
                schema = 1, token, nonce, scenario = "manual-play", variant = "b01",
                gameVersion = release.Version, gameCommit = release.Commit,
                os = OS.GetName(), display = DisplayServer.GetName(),
                processId = System.Environment.ProcessId, godotProcessId = OS.GetProcessId(),
                pidSource = "System.Environment.ProcessId", readyTickMs = System.Environment.TickCount64,
                testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                steamInitialized = MegaCrit.Sts2.Core.Platform.Steam.SteamInitializer.Initialized,
                window = new { id = windowId,
                    hwnd = DisplayServer.WindowGetNativeHandle(DisplayServer.HandleType.WindowHandle, windowId),
                    position = Point(DisplayServer.WindowGetPosition(windowId)),
                    size = Point(DisplayServer.WindowGetSize(windowId)),
                    viewportSize = Point(viewport.GetVisibleRect().Size),
                    screenTransform = new[] { Point(transform.X), Point(transform.Y), Point(transform.Origin) } },
                anchors = new
                {
                    card = Anchor(inputHolder!.Hitbox, "card", "NHandCardHolder.Hitbox.MousePressed"),
                    target = Anchor(targetNode.Hitbox, "target", "NCreature.Hitbox.MouseEntered")
                },
                cardId = Id(card), targetId = Id(target), originalCardIds = originals.Select(Id).ToArray(),
                fixtureApi = "CardPileCmd.Add;CreatureCmd.SetMaxAndCurrentHp", encounter = state.Encounter.GetType().Name,
                before, beforeCapture
            };
            string json = JsonSerializer.Serialize(ready);
            string temporary = Path.Combine(directory, "manual-ready.json.tmp");
            File.WriteAllText(temporary, json);
            File.Move(temporary, Path.Combine(directory, "manual-ready.json"));
            GD.Print("[Volibear] MANUAL_PLAY_READY " + json);
            // Only observe the normal engine path reached by external Windows input.
            await Until(() => history.Entries.Skip(historyStart).OfType<CardPlayFinishedEntry>().Any() &&
                card.Pile?.Type == PileType.Discard && !CombatManager.Instance.IsExecutingCardOrPotionEffect(player),
                25, "No completed ordinary input-driven play");
            await Pause(0.35);
            var after = Snapshot(state, player, card, enemies);
            var afterCapture = await Capture(directory, "manual-after.png");
            var result = new { schema = 1, token, nonce, scenario = "manual-play", variant = "b01",
                gameVersion = release.Version, gameCommit = release.Commit,
                processId = System.Environment.ProcessId, api = "Windows.SendInput.mouse_drag",
                acceptance = "ordinary-input-and-native-payment", before, after,
                history = records.ToArray(), beforeCapture, afterCapture };
            GD.Print("[Volibear] MANUAL_PLAY_RESULT " + JsonSerializer.Serialize(result));
            GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
            NGame.Instance!.Quit();
            ((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] MANUAL_PLAY_ERROR " + error);
            try { diagnose?.Invoke("failure"); }
            catch (Exception diagnosticError) { GD.PrintErr("[Volibear] MANUAL_ANCHOR_DIAGNOSTIC_ERROR " + diagnosticError); }
            if (captureDirectory is not null && DisplayServer.GetName() != "headless")
            {
                try
                {
                    var capture = await Capture(captureDirectory, "manual-failure.png");
                    GD.Print("[Volibear] MANUAL_FAILURE_CAPTURE " + JsonSerializer.Serialize(capture));
                }
                catch (Exception captureError) { GD.PrintErr("[Volibear] MANUAL_FAILURE_CAPTURE_ERROR " + captureError); }
            }
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally
        {
            if (historyObserver is not null) CombatManager.Instance.History.Changed -= historyObserver;
            CombatManager.Instance.TurnStarted -= OnTurn;
        }
    }
}
