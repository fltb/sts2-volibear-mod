using System;
using System.Reflection;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Core;

/// <summary>Immutable original native metadata, shared by a form's cloned sidecar.
/// Synchronizing the same entity's backing fields also reaches already-inlined
/// sealed-type consumers. Virtual getter overlays remain for special overrides.</summary>
internal sealed class BeastCardMetadata
{
    private static readonly FieldInfo TypeField = Required("<Type>k__BackingField");
    private static readonly FieldInfo TargetField = Required("<TargetType>k__BackingField");
    private readonly CardType originalType;
    private readonly TargetType originalTarget;

    private BeastCardMetadata(CardModel card)
    {
        originalType = (CardType)TypeField.GetValue(card)!;
        originalTarget = (TargetType)TargetField.GetValue(card)!;
    }

    internal static BeastCardMetadata Capture(CardModel card) => new(card);

    internal void Apply(CardModel card, bool claw)
    {
        var type = claw ? CardType.Attack : CardType.Skill;
        var target = claw ? TargetType.AnyEnemy : TargetType.AllEnemies;
        TypeField.SetValue(card, type);
        TargetField.SetValue(card, target);
        if ((CardType)TypeField.GetValue(card)! != type || (TargetType)TargetField.GetValue(card)! != target)
            throw new InvalidOperationException("Native beast type/target metadata did not update.");
    }

    internal void Restore(CardModel card)
    {
        TypeField.SetValue(card, originalType);
        TargetField.SetValue(card, originalTarget);
    }

    private static FieldInfo Required(string name) => typeof(CardModel).GetField(name,
        BindingFlags.Instance | BindingFlags.NonPublic)
        ?? throw new MissingFieldException(typeof(CardModel).FullName, name);
}
