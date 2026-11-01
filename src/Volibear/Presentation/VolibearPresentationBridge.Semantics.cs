using System;
using System.Collections.Generic;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Volibear.Core;

namespace Volibear.Presentation;

public static partial class VolibearPresentationBridge
{
    private static void InstallSemanticHooks()
    {
        var push = AccessTools.Method(typeof(NOverlayStack), nameof(NOverlayStack.Push), [typeof(IOverlayScreen)])
            ?? throw new MissingMethodException("Native overlay Push");
        new Harmony("Volibear.Presentation.CommittedSemantics").Patch(push,
            postfix: new HarmonyMethod(typeof(VolibearPresentationBridge), nameof(SelectionPushed)));
    }

    private static void SelectionPushed(IOverlayScreen screen) => Safe("scry_opened", () =>
    {
        if (screen is not NSimpleCardSelectScreen selection || !selection.IsInsideTree() ||
            ScryPresentationScope.CurrentScry is not { } scope || Owner(scope.Source.Owner.Creature) is not { } owner) return;
        foreach (var card in scope.Looked)
        {
            // Publish only cards actually mounted in this native selection screen.
            var view = FindSelectionCard(selection, card);
            if (view is null) continue;
            owner.RememberSelectionCard(card, view);
            GameplayPresentationReceipts.Publish("scry_selection_opened", scope.Source.Owner.Creature,
                scope.Source, card);
        }
    });
    private static NCard? FindSelectionCard(Node root, CardModel model)
    {
        foreach (var child in root.GetChildren())
        {
            if (child is NCard card && Valid(card) && card.IsVisibleInTree() && ReferenceEquals(card.Model, model)) return card;
            if (FindSelectionCard(child, model) is { } found) return found;
        }
        return null;
    }
    private static void GameplayCommitted(GameplayPresentationReceipt receipt) => Dispatch("gameplay_receipt", () =>
    {
        if (_room is { } room && ReferenceEquals(room.Combat, receipt.Combat))
            Owner(receipt.Owner)?.Gameplay(receipt);
    });

    private sealed partial class OwnerScope
    {
        private readonly Dictionary<Creature, string> _markTargets = new(ReferenceEqualityComparer.Instance);
        private readonly List<WeakReference<NCard>> _selectionCards = [];

        internal void RememberSelectionCard(CardModel card, NCard view)
        {
            CaptureVisibleCard(card, view);
            _selectionCards.Add(new(view));
        }
        private void CaptureVisibleCard(CardModel card, NCard view)
        {
            if (!Live || !Valid(view) || !view.IsVisibleInTree() || !ReferenceEquals(card.Owner.Creature, _owner)) return;
            var cost = view.GetNodeOrNull<Control>("%EnergyLabel");
            Vector2? costPoint = Valid(cost) && cost!.IsVisibleInTree()
                ? cost.GetGlobalTransformWithCanvas() * (cost.Size * 0.5f) : null;
            _cardAnchors[card] = new(view.GetGlobalTransformWithCanvas() * (view.Size * 0.5f),
                costPoint, view.GetInstanceId(), Time.GetTicksMsec());
        }

        internal void Gameplay(GameplayPresentationReceipt receipt)
        {
            if (!Live || !ReferenceEquals(receipt.Owner, _owner) || !ReferenceEquals(receipt.Combat, _room.Combat)) return;
            string id = $"gameplay:{receipt.Id}";
            switch (receipt.Kind)
            {
                case "target_block_removed": TargetEffect("guard_break"); break;
                case "counter_thunder_resolved": TargetEffect("counter_release"); break;
                case "domain_suppression_applied": TargetEffect("domain_suppress"); break;
                case "vulnerable_applied": TargetEffect("wound"); break;
                case "weakness_applied": TargetEffect("weakness"); break;
                case "lifesteal_health_recovered": TargetEffect("lifesteal"); break;
                case "feral_target_confirmed": CardEffect("feral_transfer"); break;
                case "feral_batch_committed":
                    _effects.Emit(id, "feral_aura", Anchors(), sound: false);
                    BatchingBeastMotion(receipt.Source as CardModel);
                    break;
                case "bite_mark_added":
                    if (receipt.Target is { } marked)
                    {
                        string key = $"bite:{CreatureId(_owner)}:{CreatureId(marked)}";
                        if (_markTargets.TryAdd(marked, key)) BindMark(marked, key, id, sound: true);
                    }
                    break;
                case "card_charge_changed": CardEffect("charge", onCard: true); break;
                case "card_retain_added": CardEffect("armor_retain", onCard: true); break;
                case "card_enhancement_committed": CardEffect("strength", onCard: true); break;
                case "power_instance_deployed": AtOwner(id, "cast_charge"); break;
                case "thunder_modifier_changed": AtOwner(id, "lightning_growth"); break;
                case "thunder_armor_block_committed": AtOwner(id, "thunder_armor"); break;
                case "dexterity_changed": AtOwner(id, "armor_retain"); break;
                case "scry_selection_opened": CardEffect("card_retrieve", fromDraw: true); break;
                case "selected_card_discarded": CardEffect("card_discard", toDiscard: true); break;
            }
            void TargetEffect(string effect)
            {
                if (receipt.Target is { } target) AtTarget(id, effect, target);
            }
            void CardEffect(string effect, bool onCard = false, bool fromDraw = false, bool toDiscard = false)
            {
                if (receipt.Card is not { } card) return;
                var anchor = CardAnchor(card);
                if (anchor is not null && CardId(card) is { } cardId)
                {
                    var anchors = Anchors(card: anchor);
                    // Generic owner/status textures are intentionally attached to
                    // the actual enhanced/retained card for these card-only events.
                    if (onCard) anchors = anchors with { Owner = anchor, OwnerHand = anchor };
                    if (fromDraw) anchors = anchors with { Source = _room.Room.Ui.DrawPile };
                    if (toDiscard) anchors = anchors with { Target = _room.Room.Ui.DiscardPile };
                    _effects.Emit(id, effect, anchors, cardId);
                }
                _effects.PlaySound(id, "sfx." + effect);
            }
        }

        private void BindMark(Creature target, string key, string id, bool sound)
        {
            if (!target.IsAlive || !BiteMarks.Has(_owner, target) || _room.NodeFor(target) is not { } node || !Valid(node.Visuals)) return;
            _effects.Emit(id, "mark_bite", Anchors(node), CreatureId(target), persistentKey: key, leaseSeconds: 2f, sound: sound);
        }
        internal void TickSemanticVisuals()
        {
            if (!Live) return;
            for (int i = _selectionCards.Count - 1; i >= 0; i--)
            {
                if (!_selectionCards[i].TryGetTarget(out var view) || !Valid(view) || !view.IsInsideTree())
                { _selectionCards.RemoveAt(i); continue; }
                if (view.Model is { } card) CaptureVisibleCard(card, view);
            }
            foreach (var pair in _markTargets)
            {
                if (!pair.Key.IsAlive || !BiteMarks.Has(_owner, pair.Key) || _room.NodeFor(pair.Key) is not { } node || !Valid(node.Visuals))
                { _effects.StopLoop(pair.Value); continue; }
                // The authoritative identity ledger survives same-entity revival.
                // A renewed visual never repeats the original mark-added sound.
                if (!_effects.RenewLoop(pair.Value, 2f)) BindMark(pair.Key, pair.Value, Next("bite_rebind"), sound: false);
            }
        }
        internal void StopSemanticVisuals(bool combatEnded)
        {
            foreach (var key in _markTargets.Values) _effects.StopLoop(key);
            _selectionCards.Clear();
            if (combatEnded) _markTargets.Clear();
        }
    }
}
