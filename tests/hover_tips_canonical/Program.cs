// Focused regression for the canonical-preview fix in MechanicHoverTips.ForCard:
// static glossary tips are yielded first, then a canonical card must stop before
// card.Owner is read. The native suite hit this through DustyTome.SetupForPlayer ->
// BaseLib's DustyTome custom-tome path -> canonical Volibear_R18.HoverTips, which
// threw CanonicalModelException before this guard existed.
//
// Fixture scope (honest labels, printed by the PASS line):
//   * REAL pinned sts2.dll and BaseLib.dll; no stubs for CardModel, LocManager,
//     LocTable, LocString or the CanonicalModelException guard.
//   * REAL production sources compiled from src/Volibear (hover-tip composition,
//     VolibearCard getter, glossary, card/relic localization tables).
//   * The native guard itself proves the fixture: card.Owner on this card throws
//     MegaCrit.Sts2.Core.Models.Exceptions.CanonicalModelException.
//   * NOT RUN: ModelDb registration, DustyTome.SetupForPlayer, BaseLib's tome
//     dictionary, Godot rendering, and every gameplay path. Those belong to the
//     Lead-owned native suite; this test never claims them.
using System.Reflection;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Exceptions;
using Volibear.Content;
using Volibear.Core;

/// <summary>Production VolibearCard surface; only the stable model id is supplied by the fixture.</summary>
sealed class CanonicalPreviewCard : VolibearCard
{
    public CanonicalPreviewCard() : base(1, CardType.Attack, CardRarity.Basic, TargetType.Self, "b04") { }
}

static class Fields
{
    internal static void Set(object target, string name, object? value)
    {
        for (var type = target.GetType(); type is not null; type = type.BaseType)
        {
            var field = type.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic |
                                                   BindingFlags.Public | BindingFlags.DeclaredOnly);
            if (field is null) continue;
            field.SetValue(target, value);
            return;
        }
        throw new MissingFieldException(target.GetType().FullName, name);
    }

    internal static void SetStatic(Type type, string name, object? value)
    {
        var field = type.GetField(name, BindingFlags.Static | BindingFlags.NonPublic) ?? throw new MissingFieldException(type.FullName, name);
        field.SetValue(null, value);
    }
}

/// <summary>
/// Real native localization without Godot: an uninitialized LocManager gets the
/// native SmartFormat formatter stack and the production tables. LocString then
/// resolves exactly as in game because that is the game's own code path.
/// </summary>
static class NativeLoc
{
    internal static LocManager Install()
    {
        var manager = (LocManager)RuntimeHelpers.GetUninitializedObject(typeof(LocManager));
        typeof(LocManager).GetMethod("LoadLocFormatters", BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(manager, null);
        var tables = new Dictionary<string, LocTable>(StringComparer.Ordinal);
        foreach (var (name, entries) in VolibearLoc.Tables)
            tables[name] = new LocTable(name, new Dictionary<string, string>(entries, StringComparer.Ordinal), null!);
        Fields.Set(manager, "_tables", tables);
        Fields.SetStatic(typeof(LocManager), "<Instance>k__BackingField", manager);
        return manager;
    }

    internal static void Restore(LocManager? previous) =>
        Fields.SetStatic(typeof(LocManager), "<Instance>k__BackingField", previous);
}

static class Program
{
    const string CardCategory = "cards";
    const string CardEntry = "VOLIBEAR_B04";
    static int checks;

    static void Need(bool condition, string message)
    {
        checks++;
        if (!condition) throw new Exception("HOVER_TIPS_CANONICAL_FAILED: " + message);
    }

    static string[] Ids(IEnumerable<IHoverTip> tips) => tips.Select(tip => tip.Id).ToArray();

    static Exception? Thrown(Action action)
    {
        try { action(); return null; }
        catch (Exception error) { return error; }
    }

    static CanonicalPreviewCard Card()
    {
        var card = new CanonicalPreviewCard();
        // Fixture plumbing only: ModelDb registration is NOT RUN here, so the stable
        // production localization id is assigned directly instead of via InitId()
        // (which would require the native model-id serialization cache).
        Fields.Set(card, "<Id>k__BackingField", new ModelId(CardCategory, CardEntry));
        return card;
    }

    static int Main()
    {
        var previous = LocManager.Instance;
        try
        {
            var manager = NativeLoc.Install();
            Need(ReferenceEquals(LocManager.Instance, manager), "real LocManager must be installed, not a stub");

            var card = Card();
            Need(card.Id.Category == CardCategory && card.Id.Entry == CardEntry, "fixture card carries the real production localization entry");
            // Native canonical state, not a reflection-written approximation: the model
            // default in sts2 is IsMutable=false, which is what ModelDb canonical cards hold.
            Need(card.IsCanonical && !card.IsMutable, "fixture card must start canonical (IsMutable=false)");

            var ownerThrow = Thrown(() => _ = card.Owner);
            Need(ownerThrow is CanonicalModelException,
                "native CardModel.Owner must throw CanonicalModelException for the fixture, got " +
                (ownerThrow?.GetType().FullName ?? "no exception"));
            Need(ownerThrow!.Message.Contains("Canonical model", StringComparison.Ordinal),
                "fixture must exercise the real native canonical guard message");

            var raw = card.Description.GetRawText();
            Need(raw.Contains("迎战", StringComparison.Ordinal), "production card text must still request the engage mechanic");

            var expected = Ids(MechanicHoverTips.ForText(raw));
            Need(expected.Contains("VOLIBEAR-ENGAGE"), "the card text resolves the static engage glossary tip");
            Need(!expected.Contains("VOLIBEAR-ENGAGE_STATE"), "static text alone never carries live engagement state");

            // The regression: this used to throw CanonicalModelException after the
            // static tips because ForCard read card.Owner for canonical models.
            var viaCard = Ids(card.HoverTips);
            Need(viaCard.SequenceEqual(expected),
                "canonical card.HoverTips must equal the static glossary tips exactly, got " + string.Join(",", viaCard));
            Need(!viaCard.Contains("VOLIBEAR-ENGAGE_STATE"), "canonical preview must not yield the live engagement-state tip");
            Need(Ids(card.HoverTips).SequenceEqual(expected), "repeated canonical preview enumeration stays stable");

            var viaForCard = Ids(MechanicHoverTips.ForCard(card));
            Need(viaForCard.SequenceEqual(expected), "ForCard(canonical) yields the same static tips directly");
            Need(EngageCmd.Queries == 0, "canonical preview must not query the shared engagement ledger");

            // Control: the guard is canonical-only. A mutable preview with no owner keeps
            // the previous static-tip behaviour and still evaluates the owner branch.
            var mutable = Card();
            // Test-only mutability write. Production mutates through MutableClone(); the
            // native setter is gated by TestMode, which must never be enabled for this run.
            Fields.Set(mutable, "<IsMutable>k__BackingField", true);
            Need(!mutable.IsCanonical, "control card must be mutable");
            Need(Thrown(() => _ = mutable.Owner) is null, "mutable card may read Owner");
            Need(mutable.Owner is null, "control card has no assigned owner");
            Need(Ids(mutable.HoverTips).SequenceEqual(expected), "ownerless mutable preview keeps the same static tips");
            Need(EngageCmd.Queries == 0, "ownerless mutable preview still stops before the ledger");

            Console.WriteLine(
                "HOVER_TIPS_CANONICAL_PASS checks=" + checks +
                " fixture=real-sts2+BaseLib+real-LocManager/LocTable" +
                " production-sources=MechanicHoverTips+VolibearCard+glossary+loc" +
                " canonical-owner-throws=CanonicalModelException" +
                " static-tips=preserved" +
                " live-state-tip=absent" +
                " ledger-queries=" + EngageCmd.Queries +
                " engagement-ledger=TEST-DOUBLE-NOT-GAMEPLAY" +
                " modeldb-and-dustytome-setup=NOT_RUN" +
                " godot-render=NOT_RUN" +
                " native-gameplay=NOT_RUN");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
        finally
        {
            NativeLoc.Restore(previous);
        }
    }
}
