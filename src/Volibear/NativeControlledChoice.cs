using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.ControllerInput;
using MegaCrit.Sts2.Core.Entities.Actions;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Runs;

namespace Volibear;

/// <summary>Staged controlled-choice support, NOT mouse/OS input acceptance.
/// Observes real requests and successful native sync; never supplies a selector or completes a choice task.
/// Separate future probes must assert actual UI availability, effects, history and candidate rejection.</summary>
internal sealed class NativeControlledChoice : IDisposable
{
    internal sealed class Request
    {
        internal required Player Player;
        internal required PlayCardAction Action;
        internal required CardModel Source;
        internal required CardPile Pile;
        internal required CardSelectorPrefs Prefs;
        internal required Func<CardModel, bool> Filter;
        internal required CardModel[] Available;
        internal required CardModel[] Eligible;
        internal uint? ChoiceId;
        internal readonly List<object> Synced = [];
        internal readonly List<object> Inputs = [];
        internal object CardIdentity(CardModel card)
        {
            var net = NetCombatCard.FromModel(card);
            return new { modelId = card.Id.Entry, combatCardIndex = net.CombatCardIndex,
                sameObject = ReferenceEquals(net.ToCardModel(), card), ownerId = card.Owner.Creature.CombatId,
                masterIndex = Array.FindIndex(card.Owner.Deck.Cards.ToArray(), c => ReferenceEquals(c, card.DeckVersion)),
                pile = card.Pile?.Type.ToString() };
        }
        internal object Describe() => new { actionId = Action.Id, actionState = Action.State.ToString(), choiceId = ChoiceId,
            source = CardIdentity(Source), pile = Pile.Type.ToString(), min = Prefs.MinSelect, max = Prefs.MaxSelect,
            manualConfirmation = Prefs.RequireManualConfirmation,
            available = Available.Select(CardIdentity).ToArray(), eligible = Eligible.Select(CardIdentity).ToArray(),
            ineligible = Available.Where(c => !Filter(c)).Select(CardIdentity).ToArray(), synced = Synced.ToArray() };
        internal void RequireWaiting()
        {
            if (ChoiceId is null || Action.State != GameActionState.GatheringPlayerChoice || Action.CompletionTask.IsCompleted ||
                ProbeGameCompat.HasSelector(Player) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("No genuine pending native controlled choice");
        }
    }
    private static NativeControlledChoice? active;
    private readonly Harmony observer = new("Volibear.NativeControlledChoiceObserver");
    private readonly Player owner;
    internal readonly List<Request> Requests = [];
    internal NativeControlledChoice(Player player)
    {
        if (active is not null || ProbeGameCompat.HasSelector(player)) throw new InvalidOperationException("Conflicting choice observer or bypass selector");
        owner = player;
        active = this;
        observer.CreateClassProcessor(typeof(ObserveHand)).Patch();
        observer.CreateClassProcessor(typeof(ObservePile)).Patch();
        observer.CreateClassProcessor(typeof(ObserveReserve)).Patch();
        observer.CreateClassProcessor(typeof(ObserveSync)).Patch();
    }
    public void Dispose()
    {
        observer.UnpatchAll(observer.Id);
        if (ReferenceEquals(active, this)) active = null;
    }
    private static readonly System.Reflection.FieldInfo? BranchingOriginal =
        typeof(BranchingPlayerChoiceContext).GetField("_originalContext",
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);

    private void Capture(PlayerChoiceContext context, CardPile pile, Player player, CardSelectorPrefs prefs, Func<CardModel, bool>? filter)
    {
        if (!ReferenceEquals(player, owner)) return;
        // PBE wraps the queued PlayCardAction context in a BranchingPlayerChoiceContext for
        // card selects; unwrap it so the request still binds to the real queued action.
        if (context is BranchingPlayerChoiceContext branching && BranchingOriginal?.GetValue(branching) is PlayerChoiceContext inner)
            context = inner;
        if (context is not GameActionPlayerChoiceContext { Action: PlayCardAction action })
            throw new InvalidOperationException("Choice must originate in the real queued card action");
        var predicate = filter ?? (_ => true);
        var cards = pile.Cards.ToArray();
        var eligible = cards.Where(predicate).ToArray();
        if (eligible.Length <= prefs.MinSelect || ProbeGameCompat.HasSelector(player))
            throw new InvalidOperationException("Fixture would bypass native UI/choice synchronization");
        Requests.Add(new Request { Player = player, Action = action, Source = action.NetCombatCard.ToCardModel(),
            Pile = pile, Prefs = prefs, Filter = predicate, Available = cards, Eligible = eligible });
    }
    [HarmonyPatch(typeof(CardSelectCmd), nameof(CardSelectCmd.FromHand))]
    private static class ObserveHand
    {
        private static void Prefix(PlayerChoiceContext context, Player player, CardSelectorPrefs prefs, Func<CardModel, bool>? filter) =>
            active?.Capture(context, PileType.Hand.GetPile(player), player, prefs, filter);
    }
    [HarmonyPatch(typeof(CardSelectCmd), nameof(CardSelectCmd.FromCombatPile), new[] {
        typeof(PlayerChoiceContext), typeof(CardPile), typeof(Player), typeof(CardSelectorPrefs), typeof(Func<CardModel, bool>) })]
    private static class ObservePile
    {
        private static void Prefix(PlayerChoiceContext context, CardPile pile, Player player, CardSelectorPrefs prefs, Func<CardModel, bool> filter) =>
            active?.Capture(context, pile, player, prefs, filter);
    }
    [HarmonyPatch(typeof(PlayerChoiceSynchronizer), nameof(PlayerChoiceSynchronizer.ReserveChoiceId))]
    private static class ObserveReserve
    {
        private static void Postfix(Player player, uint __result)
        {
            if (active is null || !ReferenceEquals(player, active.owner)) return;
            var request = active.Requests.LastOrDefault() ?? throw new InvalidOperationException("Choice reservation without native request");
            if (request.ChoiceId is not null) throw new InvalidOperationException("Duplicate reservation for one request");
            request.ChoiceId = __result;
        }
    }
    [HarmonyPatch(typeof(PlayerChoiceSynchronizer), nameof(PlayerChoiceSynchronizer.SyncLocalChoice))]
    private static class ObserveSync
    {
        private static void Postfix(Player player, uint choiceId, PlayerChoiceResult result)
        {
            if (active is null || !ReferenceEquals(player, active.owner)) return;
            var request = active.Requests.Single(r => r.ChoiceId == choiceId);
            var selected = result.AsCombatCards().ToArray();
            request.Synced.Add(new { choiceId, actionId = request.Action.Id, actionState = request.Action.State.ToString(),
                selected = selected.Select(request.CardIdentity).ToArray(),
                selectedSameObjects = selected.Select(c => request.Eligible.Any(e => ReferenceEquals(e, c))).ToArray() });
        }
    }
    internal static object ProbeFutureIdRejection(Request request)
    {
        request.RequireWaiting();
        int syncBefore = request.Synced.Count;
        var synchronizer = RunManager.Instance.PlayerChoiceSynchronizer;
        var counterMethod = AccessTools.Method(typeof(PlayerChoiceSynchronizer), "GetChoiceId");
        uint counterBefore = (uint)counterMethod.Invoke(synchronizer, new object[] { request.Player })!;
        uint future = checked(request.ChoiceId!.Value + 1);
        string? exception = null;
        try
        {
            // Valid candidate, invalid UNRESERVED FUTURE ID. This tests transport identity, NOT candidate filtering.
            RunManager.Instance.PlayerChoiceSynchronizer.SyncLocalChoice(request.Player, future,
                PlayerChoiceResult.FromMutableCombatCards(new[] { request.Eligible[0] }));
        }
        catch (InvalidOperationException error) { exception = error.GetType().Name; }
        if (exception is null) throw new InvalidOperationException("Native transport accepted unreserved future choice ID");
        request.RequireWaiting();
        return new { kind = "unreserved-future-choice-id-not-card-eligibility", requested = request.ChoiceId,
            attempted = future, exception, syncBefore, syncAfter = request.Synced.Count, counterBefore,
            counterAfter = (uint)counterMethod.Invoke(synchronizer, new object[] { request.Player })!, actionState = request.Action.State.ToString() };
    }
    private static async Task Frame()
    {
        var tree = (SceneTree)Engine.GetMainLoop();
        await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame);
    }
    private static async Task<object> ControllerSelect(Control control)
    {
        if (!control.IsVisibleInTree()) throw new InvalidOperationException("Cannot route native GUI input to a hidden control");
        control.GrabFocus();
        await Frame();
        var viewport = control.GetViewport();
        if (!ReferenceEquals(viewport.GuiGetFocusOwner(), control)) throw new InvalidOperationException("Native focus did not reach intended control");
        var controlType = control.GetType().Name;
        var visible = control.IsVisibleInTree();
        var focusMatched = ReferenceEquals(viewport.GuiGetFocusOwner(), control);
        // Engine GUI input routing, never direct _GuiInput/OnCardClicked/Pressed signal or selection task completion.
        viewport.PushInput(new InputEventAction { Action = MegaInput.select, Pressed = true });
        await Frame();
        viewport.PushInput(new InputEventAction { Action = MegaInput.select, Pressed = false });
        await Frame();
        return new { api = "Viewport.PushInput", action = MegaInput.select.ToString(), controlType, visible, focusMatched, pressed = new[] { true, false } };
    }
    internal static async Task SelectVisibleCandidate(Request request, NCardHolder holder)
    {
        request.RequireWaiting();
        var card = holder.CardNode?.Model ?? throw new InvalidOperationException("No model on native card holder");
        if (!request.Eligible.Any(c => ReferenceEquals(c, card)) || !request.Filter(card) || !ReferenceEquals(card.Pile, request.Pile))
            throw new InvalidOperationException("Driver refuses candidate outside the observed native eligible set; not a native rejection claim");
        request.Inputs.Add(await ControllerSelect(holder));
    }
    // Read-only failure context, not an input fallback or acceptance receipt.
    private static void PointerDiagnostics(Request request,NClickableControl confirm,Vector2 point,int stableFrames,string phase)
    {
        float[] V(Vector2 v) => new[] { v.X,v.Y };
        float[] R(Rect2 r) => new[] { r.Position.X,r.Position.Y,r.Size.X,r.Size.Y };
        float[] T(Transform2D t) => new[] { t.X.X,t.X.Y,t.Y.X,t.Y.Y,t.Origin.X,t.Origin.Y };
        object? ControlInfo(Control? control)
        {
            if (control is null) return null;
            return new { id = control.GetInstanceId(),type = control.GetType().Name,path = control.GetPath().ToString(),
                insideTree = control.IsInsideTree(),visible = control.IsVisibleInTree(),canProcess = control.CanProcess(),
                rect = R(control.GetRect()),globalRect = R(control.GetGlobalRect()),canvasTransform = T(control.GetGlobalTransformWithCanvas()),
                screenTransform = T(control.GetScreenTransform()),mouseFilter = control.MouseFilter.ToString(),focusMode = control.FocusMode.ToString(),
                mouseBehaviorRecursive = control.Get("mouse_behavior_recursive").AsInt32(),focusBehaviorRecursive = control.Get("focus_behavior_recursive").AsInt32(),
                clipContents = control.ClipContents,zIndex = control.ZIndex };
        }
        var viewport = confirm.GetViewport(); var root = confirm.GetTree().Root; var window = confirm.GetWindow();
        var ancestors = new List<object?>();
        for (Node? node = confirm.GetParent(); node is not null; node = node.GetParent())
            if (node is Control parent) ancestors.Add(ControlInfo(parent));
        bool NativeField(string name) => (bool)AccessTools.Field(typeof(NClickableControl),name).GetValue(confirm)!;
        GD.Print("[Volibear] PREPARED_CHOICE_POINTER_DIAGNOSTIC " + System.Text.Json.JsonSerializer.Serialize(new {
            token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"),phase,actionId = request.Action.Id,choiceId = request.ChoiceId,
            point = V(point),currentCenter = V(confirm.GetGlobalTransformWithCanvas() * (confirm.Size * 0.5f)),stableFrames,
            target = ControlInfo(confirm),hovered = ControlInfo(viewport.GuiGetHoveredControl()),focusOwner = ControlInfo(viewport.GuiGetFocusOwner()),
            children = confirm.GetChildren().OfType<Control>().Select(ControlInfo).ToArray(),ancestors,
            nativeFocused = (bool)AccessTools.Property(typeof(NClickableControl),"IsFocused").GetValue(confirm)!,
            nativeHovered = NativeField("_isHovered"),nativeControllerFocused = NativeField("_isControllerFocused"),enabled = confirm.IsEnabled,
            treePaused = confirm.GetTree().Paused,viewportType = viewport.GetType().Name,viewportPath = viewport.GetPath().ToString(),
            viewportRect = R(viewport.GetVisibleRect()),viewportMouse = V(viewport.GetMousePosition()),inputHandled = viewport.IsInputHandled(),
            viewportInputDisabled = viewport.GuiDisableInput,rootEmbedSubwindows = root.GuiEmbedSubwindows,viewportEmbedSubwindows = viewport.GuiEmbedSubwindows,
            windowId = window.GetWindowId(),windowPosition = new[] { window.Position.X,window.Position.Y },windowSize = new[] { window.Size.X,window.Size.Y },
            osMouse = new[] { DisplayServer.MouseGetPosition().X,DisplayServer.MouseGetPosition().Y },
            osWindowFocused = DisplayServer.WindowIsFocused(window.GetWindowId()),gameFocused = MegaCrit.Sts2.Core.Nodes.NGame.IsGameFocusedWindow()
        }));
    }
    internal static async Task ConfirmIfRequired(Request request, NClickableControl confirm)
    {
        if (request.Synced.Count != 0) return;
        request.RequireWaiting();
        if (!confirm.IsEnabled) throw new InvalidOperationException("Native confirmation is still disabled");
        // NConfirmButton is not controller-focusable; its hotkey also requires OS focus.
        // Neither is overridden: pointer input uses the real viewport GUI hit-test pipeline.
        var watch = System.Diagnostics.Stopwatch.StartNew();
        Vector2 Center() => confirm.GetGlobalTransformWithCanvas() * (confirm.Size * 0.5f);
        Vector2 center = Center();
        int stableFrames = 0;
        while (stableFrames < 3)
        {
            if (!GodotObject.IsInstanceValid(confirm) || !confirm.IsInsideTree() || !confirm.IsVisibleInTree() || !confirm.IsEnabled)
                throw new InvalidOperationException("Native confirm is not ready in its actual tree");
            if (watch.Elapsed > TimeSpan.FromSeconds(5)) throw new TimeoutException("Native confirmation geometry did not settle");
            await Frame();
            Vector2 next = Center();
            stableFrames = center.DistanceTo(next) <= 0.1f ? stableFrames + 1 : 0;
            center = next;
        }
        var viewport = confirm.GetViewport();
        if (!viewport.GetVisibleRect().HasPoint(center)) throw new InvalidOperationException("Native confirmation is outside the viewport");
        var focusModeBefore = confirm.FocusMode.ToString();
        PointerDiagnostics(request,confirm,center,stableFrames,"before-motion");
        // PBE animates the confirm control's scale when it appears, so the pointer may need a
        // couple of re-targets before hover and native focus match the final geometry.
        bool hoverMatched = false, nativeFocused = false;
        for (int attempt = 0; attempt < 6; attempt++)
        {
            center = Center();
            viewport.PushInput(new InputEventMouseMotion { Position = center,GlobalPosition = center },true);
            if (attempt == 0) PointerDiagnostics(request,confirm,center,stableFrames,"after-motion-dispatch");
            await Frame();
            if (attempt == 0) PointerDiagnostics(request,confirm,center,stableFrames,"after-motion-frame");
            var hovered = viewport.GuiGetHoveredControl();
            hoverMatched = ReferenceEquals(hovered,confirm);
            nativeFocused = (bool)AccessTools.Property(typeof(NClickableControl),"IsFocused").GetValue(confirm)!;
            if (hoverMatched && nativeFocused && Center().DistanceTo(center) <= 0.1f) break;
            await Frame();
        }
        if (!hoverMatched || !nativeFocused || !confirm.IsInsideTree() || !confirm.IsVisibleInTree() || !confirm.IsEnabled || Center().DistanceTo(center) > 0.1f)
            throw new InvalidOperationException("Native pointer did not settle on the enabled confirmation control");
        center = Center();
        bool insideTree = confirm.IsInsideTree(),visible = confirm.IsVisibleInTree(),enabled = confirm.IsEnabled;
        string controlType = confirm.GetType().Name;
        viewport.PushInput(new InputEventMouseButton { Position = center,GlobalPosition = center,ButtonIndex = MouseButton.Left,ButtonMask = MouseButtonMask.Left,Pressed = true },true);
        await Frame();
        if (!ReferenceEquals(viewport.GuiGetHoveredControl(),confirm) || !confirm.IsInsideTree() || !confirm.IsVisibleInTree() || !confirm.IsEnabled)
        {
            PointerDiagnostics(request,confirm,center,stableFrames,"lost-press-target");
            throw new InvalidOperationException("Native confirmation lost its pointer press target before release");
        }
        var focusModeAfter = confirm.FocusMode.ToString();
        viewport.PushInput(new InputEventMouseButton { Position = center,GlobalPosition = center,ButtonIndex = MouseButton.Left,Pressed = false },true);
        await Frame();
        request.Inputs.Add(new { api = "Viewport.PushInput",action = "viewport-left-pointer-confirm",controlType,insideTree,visible,enabled,
            stableFrames,hoverMatched,nativeFocused,focusModeBefore,focusModeAfter,position = new[] { center.X,center.Y },
            viewportSize = new[] { viewport.GetVisibleRect().Size.X,viewport.GetVisibleRect().Size.Y },pressed = new[] { true,false } });
    }
}
