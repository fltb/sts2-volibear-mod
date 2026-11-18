using Volibear.Core;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.addons.mega_text;
using Volibear.Content;

namespace Volibear.Presentation;

/// <summary>UI-only grouping. Native lists, model amounts and model subscriptions stay intact.</summary>
internal static class PowerStackVisual
{
    private const string HarmonyId = "Volibear.PowerStackVisual";
    private static bool installed;
    private static readonly Lazy<HashSet<string>> OwnMechanicTipIds = new(() => new(
        MechanicGlossary.Entries.Select(entry =>
#if STS2_BETA
            new HoverTip(new MegaCrit.Sts2.Core.Localization.LocString("static_hover_tips", "VOLIBEAR-" + entry.Key + ".title"),
                new MegaCrit.Sts2.Core.Localization.LocString("static_hover_tips", "VOLIBEAR-" + entry.Key + ".description")).Id
#else
            "VOLIBEAR-" + entry.Key
#endif
        ), StringComparer.Ordinal));
    private static readonly FieldInfo NodesField = AccessTools.DeclaredField(typeof(NPowerContainer), "_powerNodes");
    private static readonly AccessTools.FieldRef<NPowerContainer, List<NPower>> Nodes =
        AccessTools.FieldRefAccess<NPowerContainer, List<NPower>>(NodesField);
    private static readonly AccessTools.FieldRef<NPower, PowerModel?> Model =
        AccessTools.FieldRefAccess<NPower, PowerModel?>("_model");
    private static readonly AccessTools.FieldRef<NPower, MegaLabel?> AmountLabel =
        AccessTools.FieldRefAccess<NPower, MegaLabel?>("_amountLabel");
    private static readonly MethodInfo LayoutMethod = AccessTools.DeclaredMethod(typeof(NPowerContainer), "UpdatePositions");
    private static readonly Action<NPowerContainer> UpdatePositions = AccessTools.MethodDelegate<Action<NPowerContainer>>(LayoutMethod);
    private static readonly MethodInfo HoverRefreshMethod = AccessTools.DeclaredMethod(typeof(NPower), "ShowPowerHoverTips");
    private static readonly ConditionalWeakTable<NPowerContainer, ContainerView> Containers = new();
    private static readonly ConditionalWeakTable<NPower, NodeView> Views = new();

    internal static string DisplayedAmount(NPower node) => AmountLabel(node)?.Text ?? "";
    internal static IReadOnlyList<IHoverTip> DisplayedTips(NPower node)
    {
        var model = Model(node);
        if (model is null || model.IsCanonical) return Array.Empty<IHoverTip>();
        return ProjectTips(model.Owner, model.HoverTips);
    }

    internal static IReadOnlyList<IHoverTip> ProjectTips(Creature? owner, IEnumerable<IHoverTip> original)
    {
        var tips = original.ToArray();
        if (owner is null) return tips;
        var groups = new Dictionary<string, (PowerModel Model, PowerStackProjection Projection)>(StringComparer.Ordinal);
        var ambiguous = new HashSet<string>(StringComparer.Ordinal);
        foreach (var model in owner.Powers)
        {
            if (!PowerStackPresentation.TryDescribe(model, out var projection)) continue;
            string id = model.Id.ToString();
            if (groups.TryGetValue(id, out var existing) && !existing.Projection.Members.Contains(model)) ambiguous.Add(id);
            else groups.TryAdd(id, (model, projection));
        }
        // Remove only our known glossary entry when its exact title is already a
        // supported main tip in this UI request. An owner merely having a power is not enough.
        var mainTitles = new HashSet<string>(tips.OfType<HoverTip>()
            .Where(tip => groups.ContainsKey(tip.Id) && !ambiguous.Contains(tip.Id) && !string.IsNullOrEmpty(tip.Title))
            .Select(tip => tip.Title!), StringComparer.Ordinal);
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var result = new List<IHoverTip>();
        foreach (var tip in tips)
        {
            if (tip is HoverTip keyword && OwnMechanicTipIds.Value.Contains(tip.Id) && !groups.ContainsKey(tip.Id) &&
                keyword.Title is { } title && mainTitles.Contains(title)) continue;
            if (tip is not HoverTip native || ambiguous.Contains(tip.Id) || !groups.TryGetValue(tip.Id, out var group))
            { result.Add(tip); continue; }
            if (!seen.Add(tip.Id)) continue;
            var main = new HoverTip(group.Model, group.Projection.Description, native.IsSmart);
            // The UI replacement must preserve the existing disabled annotation, once.
            result.Add(PowerPresentationDisabled.PowerTips(group.Model, new IHoverTip[] { main }).First());
        }
        return result;
    }

    private static bool IsProjected(NPower node) => Model(node) is { } model &&
        PowerStackPresentation.TryDescribe(model, out _);
    private static bool HasProjection(NPowerContainer container) => HasProjection(Nodes(container));
    private static bool HasProjection(IEnumerable<NPower> nodes) => nodes.Any(node =>
        GodotObject.IsInstanceValid(node) && IsProjected(node));
    private static NodeView View(NPower node)
    {
        var view = Views.GetValue(node, n => new NodeView(n));
        view.Activate();
        return view;
    }
    private static ContainerView Container(NPowerContainer node) => Containers.GetValue(node, n => new ContainerView(n));
    private static void ApplyAmount(NPower node)
    {
        if (AmountLabel(node) is { } label && Model(node) is { } model &&
            PowerStackPresentation.TryDescribe(model, out var projection)) label.SetTextAutoSize(projection.AmountText);
    }
    private static void Refresh(NPower node)
    {
        if (!node.IsInsideTree()) return;
        if (!IsProjected(node))
        {
            if (Views.TryGetValue(node, out var previous) && previous.Active)
            {
                previous.Release();
                if (node.Container is { } oldContainer && oldContainer.IsInsideTree() &&
                    Containers.TryGetValue(oldContainer, out _)) UpdatePositions(oldContainer);
            }
            return;
        }
        var view = View(node);
        if (node.Container is { } container && container.IsInsideTree()) UpdatePositions(container);
        else ApplyAmount(node);
        view.RefreshHover();
    }

    private sealed class ContainerView
    {
        private readonly NPowerContainer container;
        internal readonly List<NPower> Display = new();
        internal bool Active { get; private set; }
        private NPower[] source = [];
        private bool refreshRequired = true;
        private Action? unsubscribe;
        internal ContainerView(NPowerContainer container)
        {
            this.container = container;
            container.TreeEntered += () =>
            {
                if (HasProjection(container)) UpdatePositions(container);
                else Release();
            };
            container.TreeExiting += Exit;
        }
        private void Enter()
        {
            if (unsubscribe is not null || !Active || !container.IsInsideTree()) return;
            var tracker = CombatManager.Instance.StateTracker;
            void Changed(CombatState _) => UpdatePositions(container);
            tracker.CombatStateChanged += Changed;
            unsubscribe = () => tracker.CombatStateChanged -= Changed;
        }
        private void Exit()
        {
            unsubscribe?.Invoke(); unsubscribe = null;
            Active = false;
            foreach (var node in source.Concat(Nodes(container)).Distinct())
                if (GodotObject.IsInstanceValid(node) && Views.TryGetValue(node, out var view)) view.SetHidden(false);
            source = [];
            refreshRequired = true;
            Display.Clear();
        }
        internal void Release()
        {
            Exit();
            // Removed native children still need their own TreeExiting hover cleanup.
            foreach (var node in Nodes(container))
                if (GodotObject.IsInstanceValid(node) && Views.TryGetValue(node, out var view)) view.Release();
        }
        internal void Invalidate() => refreshRequired = true;
        internal bool Matches(List<NPower> nodes) => Active && !refreshRequired && source.SequenceEqual(nodes);
        internal List<NPower> Project(List<NPower> nodes)
        {
            // A neighbouring adapter may filter/reorder the loaded value without changing
            // _powerNodes. Cache only identical node sequences within this layout call.
            var next = nodes.ToArray();
            foreach (var node in source.Except(next))
                if (GodotObject.IsInstanceValid(node) && Views.TryGetValue(node, out var previous))
                {
                    if (Nodes(container).Contains(node)) previous.Release();
                    else previous.SetHidden(false);
                }
            source = next;
            Active = true;
            Enter();
            Display.Clear();
            var represented = new HashSet<PowerModel>(ReferenceEqualityComparer.Instance);
            foreach (var node in source)
            {
                if (!GodotObject.IsInstanceValid(node)) continue;
                bool hidden = false;
                if (Model(node) is { } model && PowerStackPresentation.TryDescribe(model, out var projection))
                {
                    hidden = projection.Members.Any(represented.Contains);
                    if (!hidden) represented.UnionWith(projection.Members);
                    View(node).SetHidden(hidden);
                    ApplyAmount(node);
                }
                else if (Views.TryGetValue(node, out var previous)) previous.Release();
                if (!hidden) Display.Add(node);
            }
            foreach (var node in Display)
                if (Views.TryGetValue(node, out var view) && view.Active) view.RefreshHover();
            refreshRequired = false;
            return Display;
        }
    }

    private sealed class NodeView
    {
        private readonly NPower node;
        private readonly Action<CombatState> nativeHoverRefresh;
        private Action? unsubscribe;
        private Action? removeHover;
        private bool hiddenByStack;
        private bool originalVisible;
        internal bool Active { get; private set; }
        internal NodeView(NPower node)
        {
            this.node = node;
            nativeHoverRefresh = AccessTools.MethodDelegate<Action<CombatState>>(HoverRefreshMethod, node);
            node.TreeEntered += () =>
            {
                if (IsProjected(node)) Refresh(node);
                else Release();
            };
            node.TreeExiting += Exit;
        }
        internal void Activate()
        {
            Active = true;
            Enter();
        }
        private void Enter()
        {
            if (unsubscribe is not null || !node.IsInsideTree() || node.Container is not null) return;
            var tracker = CombatManager.Instance.StateTracker;
            void Changed(CombatState _) => Refresh(node);
            tracker.CombatStateChanged += Changed;
            unsubscribe = () => tracker.CombatStateChanged -= Changed;
        }
        private void Exit()
        {
            if (!Active) return;
            EndHover(true);
            unsubscribe?.Invoke(); unsubscribe = null;
            SetHidden(false);
            Active = false;
        }
        internal void Release()
        {
            if (!Active) return;
            unsubscribe?.Invoke(); unsubscribe = null;
            SetHidden(false);
            // On a rebind to a foreign power, its already-open native hover remains native.
            // Forget our cleanup lease without removing the game's subscription or tooltip.
            removeHover = null;
            Active = false;
        }
        internal void SetHidden(bool hide)
        {
            if (hide == hiddenByStack) return;
            if (hide)
            {
                originalVisible = node.Visible;
                EndHover(true);
                node.Visible = false;
            }
            // If another UI adapter has already shown the node, its newer value wins.
            else if (!node.Visible) node.Visible = originalVisible;
            hiddenByStack = hide;
        }
        internal void BeginHover()
        {
            EndHover(false);
            var tracker = CombatManager.Instance.StateTracker;
            // Native OnHovered performs += after this prefix; retain its exact removal target.
            tracker.CombatStateChanged -= nativeHoverRefresh;
            removeHover = () => tracker.CombatStateChanged -= nativeHoverRefresh;
        }
        internal void EndHover(bool hide)
        {
            if (removeHover is null) return;
            removeHover(); removeHover = null;
            if (!hide) return;
            if (node.GetNodeOrNull<TextureRect>("%Icon") is { } icon) icon.Scale = Vector2.One;
            if (Model(node) is { IsCanonical: false } model && model.Owner is { } owner)
                NCombatRoom.Instance?.GetCreatureNode(owner)?.HideHoverTips();
        }
        internal void RefreshHover()
        {
            if (removeHover is not null && node.IsInsideTree() && !hiddenByStack && Model(node) is not null)
                nativeHoverRefresh(null!);
        }
    }

    private static void LayoutPrefix(NPowerContainer __instance)
    {
        if (Containers.TryGetValue(__instance, out var view)) view.Invalidate();
    }
    private static List<NPower> LayoutNodes(NPowerContainer container, List<NPower> nativeNodes)
    {
        Containers.TryGetValue(container, out var view);
        if (view is not null && view.Matches(nativeNodes)) return view.Display;
        if (HasProjection(nativeNodes)) return Container(container).Project(nativeNodes);
        if (view is not null && view.Active) view.Release();
        // Return the actual loaded value, including any previous adapter's changes.
        return nativeNodes;
    }
    private static IEnumerable<CodeInstruction> LayoutTranspiler(IEnumerable<CodeInstruction> instructions)
    {
        int replaced = 0;
        OpCode previous = default;
        foreach (var instruction in instructions)
        {
            if (instruction.opcode == OpCodes.Ldfld && Equals(instruction.operand, NodesField))
            {
                if (previous.OpCodeType == OpCodeType.Prefix)
                    throw new InvalidOperationException("Power stack layout cannot wrap a prefixed _powerNodes load");
                // Preserve the native field anchor for other UI transpilers. The retained
                // receiver and the loaded (possibly adapted) value feed our projection.
                var duplicate = new CodeInstruction(OpCodes.Dup);
                var load = new CodeInstruction(instruction);
                var project = new CodeInstruction(OpCodes.Call,
                    AccessTools.DeclaredMethod(typeof(PowerStackVisual), nameof(LayoutNodes)));
                duplicate.labels.AddRange(load.labels);
                load.labels.Clear();
                foreach (var block in load.blocks)
                    if (block.blockType == ExceptionBlockType.EndExceptionBlock) project.blocks.Add(block);
                    else duplicate.blocks.Add(block);
                load.blocks.Clear();
                yield return duplicate;
                yield return load;
                yield return project;
                replaced++;
            }
            else yield return new CodeInstruction(instruction);
            previous = instruction.opcode;
        }
        if (replaced == 0) throw new InvalidOperationException("Pinned NPowerContainer layout no longer reads _powerNodes");
    }
    private static void ContainerEnter(NPowerContainer __instance)
    {
        if (HasProjection(__instance)) UpdatePositions(__instance);
    }
    private static void PowerReady(NPower __instance) => Refresh(__instance);
    private static void PowerChanged(NPower __instance) => Refresh(__instance);
    private static bool PowerHovered(NPower __instance)
    {
        if (Model(__instance) is null or { IsCanonical: true }) return false;
        if (IsProjected(__instance)) View(__instance).BeginHover();
        return true;
    }
    private static bool PowerUnhovered(NPower __instance)
    {
        if (Views.TryGetValue(__instance, out var view) && view.Active) view.EndHover(false);
        return Model(__instance) is { IsCanonical: false };
    }
    private static void CreatureHover(NCreature __instance, ref IEnumerable<IHoverTip> hoverTips)
    {
        if (__instance.Entity.Powers.Any(power => PowerStackPresentation.TryDescribe(power, out _)))
            hoverTips = ProjectTips(__instance.Entity, hoverTips);
    }

    internal static void Install()
    {
        if (installed) return;
        var harmony = new Harmony(HarmonyId);
        HarmonyMethod Hook(string name) => new(typeof(PowerStackVisual), name);
        try
        {
            NativeTranspiler.Patch(harmony, LayoutMethod, prefix: Hook(nameof(LayoutPrefix)),
                transpiler: new HarmonyMethod(typeof(PowerStackVisual), nameof(LayoutTranspiler)) { priority = Priority.Normal });
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPowerContainer), nameof(NPowerContainer._EnterTree)), postfix: Hook(nameof(ContainerEnter)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPower), nameof(NPower._Ready)), postfix: Hook(nameof(PowerReady)));
            harmony.Patch(AccessTools.PropertySetter(typeof(NPower), nameof(NPower.Model)), postfix: Hook(nameof(PowerChanged)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPower), "RefreshAmount"), postfix: Hook(nameof(PowerChanged)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPower), "OnHovered"), prefix: Hook(nameof(PowerHovered)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPower), "OnUnhovered"), prefix: Hook(nameof(PowerUnhovered)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NCreature), nameof(NCreature.ShowHoverTips)), prefix: Hook(nameof(CreatureHover)));
            installed = true;
        }
        catch { harmony.UnpatchAll(HarmonyId); throw; }
    }
}
