using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;
using Volibear.Core;

// Compiles production orchestration/definitions against explicit command boundaries.
// Every generated/exhausted card below is a test boundary object, not native evidence.
var checks = 0;
var context = new PlayerChoiceContext();
var cases = new Dictionary<string, Func<Task>>
{
    ["identity-and-native-events"] = IdentityAndEvents,
    ["reentry-repeated-and-piles"] = ReentryAndPiles,
    ["exhaust-responses-and-overflow"] = ExhaustResponses,
    ["terminal-owner-and-failure"] = TerminalAndOwner,
    ["cost-lifetime-and-clones"] = CostLifetime,
    ["coupon-retain-and-expiry"] = CouponAndRetain,
    ["frozen-selection-and-new-identity"] = Selection,
    ["native-token-values-and-replay"] = TokenValues
};
foreach (var (name, run) in cases)
{
    Harness.Reset();
    await run();
    Console.WriteLine($"BEAST_PRODUCTION_CASE_PASS name={name}");
}
Console.WriteLine($"BEAST_NATIVE_REPLACEMENT_OK assertions={checks}; native-gameplay=NOT_RUN");

void Check(bool value, string message)
{
    checks++;
    if (!value) throw new InvalidOperationException(message);
}
Player Player(CombatState? combat = null) => new(combat ?? new CombatState());
CardModel Material(Player owner, CardType type = CardType.Skill, int cost = 3, PileType pile = PileType.Hand)
{
    var card = new CardModel(cost, type) { Owner = owner, State = owner.Creature.CombatState };
    Harness.Move(card, pile); return card;
}
int Cost(CardModel card) => card.EnergyCost.GetWithModifiers(CostModifiers.Local);

async Task IdentityAndEvents()
{
    foreach (var type in Enum.GetValues<CardType>())
    {
        Harness.Reset();
        var owner = Player();
        var material = Material(owner, type);
        var master = new CardModel(3, type); material.DeckVersion = master;
        material.CloneOf = new CardModel(); material.Enchantment = new(); material.Affliction = new();
        var neighbor = Material(owner);
        var observed = 0;
        Task Converted(PlayerChoiceContext choices, BeastChange change)
        {
            Check(ReferenceEquals(choices, context) && ReferenceEquals(change.Combat, owner.Creature.CombatState), "conversion retains native choice/combat context");
            Check(change.Card.Pile == PileType.Hand.GetPile(owner) && !ReferenceEquals(change.Card, material), "observer receives generated identity after pile insertion");
            Harness.Events.Add("converted"); observed++; return Task.CompletedTask;
        }
        BeastForms.Converted += Converted;
        CardModel replacement;
        try { replacement = (await BeastForms.Convert(context, material))!; }
        finally { BeastForms.Converted -= Converted; }
        Check(replacement is not null && replacement.Owner == owner && !ReferenceEquals(replacement, material), "replacement is a new owner-local entity");
        Check(BeastForms.Shape(replacement!) == (type == CardType.Attack ? BeastShape.Claw : BeastShape.Body), "attack maps to native claw and other types to body");
        Check(BeastForms.Shape(material) == BeastShape.None && material.Type == type && material.EnergyCost.Canonical == 3, "material keeps its own native definition");
        Check(material.Pile == PileType.Exhaust.GetPile(owner) && Harness.Exhausted.SequenceEqual(new[] { material }), "native material exhaust occurs once including status/curse");
        Check(Harness.Generated.SequenceEqual(new[] { replacement }) && observed == 1, "native generation and conversion occur once");
        Check(Harness.Events.SequenceEqual(new[] { "exhaust", "create", "generate", "feral_target_confirmed", "converted" }), "exhaust reactions precede creation and generated reactions precede conversion");
        Check(PileType.Hand.GetPile(owner).Cards.SequenceEqual(new[] { neighbor, replacement }), "same pile uses native bottom insertion");
        Check(replacement!.DeckVersion is null && replacement.CloneOf is null && replacement.Enchantment is null && replacement.Affliction is null, "new identity does not inherit deck, clone or harmful material provenance");
        Check(ReferenceEquals(material.DeckVersion, master) && material.Enchantment is not null && material.Affliction is not null, "native exhaustion does not clear the original material's state");
    }
}

async Task ReentryAndPiles()
{
    var owner = Player();
    foreach (var pile in new[] { PileType.Hand, PileType.Draw, PileType.Discard })
    {
        var material = Material(owner, pile: pile);
        var result = await BeastForms.Convert(context, material);
        Check(result!.Pile!.Type == pile, "generated beast returns to the material's original pile");
        var exhausts = Harness.Exhausted.Count; var generated = Harness.Generated.Count;
        Check(ReferenceEquals(await BeastForms.Convert(context, result), result), "converting a beast is idempotent");
        Check(await BeastForms.Convert(context, material) is null, "an already exhausted material cannot grant another form");
        Check(Harness.Exhausted.Count == exhausts && Harness.Generated.Count == generated, "no extra consume/create for existing beast or exhausted material");
    }
    var returned = Material(owner);
    Harness.OnExhaust = async card =>
    {
        Harness.Move(card, PileType.Hand);
        Check(await BeastForms.Convert(context, card) is null, "same material cannot reenter during its native exhaust response");
    };
    var first = await BeastForms.Convert(context, returned);
    Check(first is not null && returned.Pile!.Type == PileType.Hand, "native response moving material is preserved");
    Harness.OnExhaust = null;
    var second = await BeastForms.Convert(context, returned);
    Check(second is not null && !ReferenceEquals(first, second), "retrieved material can be consumed again in a later transaction");
    Check(await BeastForms.Convert(context, Material(owner, pile: PileType.Play)) is null, "a currently resolving card cannot be replaced underneath its queued play");
}

async Task ExhaustResponses()
{
    var vetoOwner = Player(); var vetoMaterial = Material(vetoOwner);
    Harness.CancelExhaust = true;
    Check(await BeastForms.Convert(context, vetoMaterial) is null && Harness.Generated.Count == 0, "cancelled native exhaust cannot duplicate the material into a new beast");
    CombatManager.Instance.History.Entries.Add(new MegaCrit.Sts2.Core.Combat.History.Entries.CardExhaustedEntry(vetoMaterial));
    Check(await BeastForms.Convert(context, vetoMaterial) is null && Harness.Generated.Count == 0, "an old exhaust entry cannot satisfy the current consume/create transaction");
    Check(vetoMaterial.Pile!.Type == PileType.Hand, "vetoed native consumption leaves material untouched");
    Harness.Reset();
    var owner = Player(); owner.HandLimit = 2;
    var material = Material(owner);
    Material(owner);
    Harness.OnExhaust = card => { Material(owner); return Task.CompletedTask; };
    var beast = await BeastForms.Convert(context, material);
    Check(beast!.Pile!.Type == PileType.Discard && PileType.Hand.GetPile(owner).Cards.Count == 2, "native response fills hand and generated card obeys normal overflow");
    Check(material.Pile!.Type == PileType.Exhaust, "overflow never rolls material exhaustion back");
    Harness.Reset(); owner = Player(); material = Material(owner);
    Harness.OnExhaust = card => { Harness.Move(card, PileType.Discard); return Task.CompletedTask; };
    beast = await BeastForms.Convert(context, material);
    Check(material.Pile!.Type == PileType.Discard && beast!.Pile!.Type == PileType.Hand, "native exhaust response may move material without redirecting new form's captured destination");
    Harness.Reset(); owner = Player(); material = Material(owner);
    Harness.OnGenerated = card => { Harness.Move(card, PileType.Exhaust); return Task.CompletedTask; };
    beast = await BeastForms.Convert(context, material);
    Check(beast!.Pile!.Type == PileType.Exhaust && Harness.Generated.Count == 1, "normal generated-card response may consume the beast; no forced return");
}

async Task TerminalAndOwner()
{
    foreach (var effect in new Action<Player>[]
    {
        p => p.Creature.IsAlive = false,
        p => CombatManager.Instance.IsOverOrEnding = true,
        p => p.Creature.CombatState = new CombatState(),
        p => p.PlayerCombatState = null
    })
    {
        Harness.Reset(); var owner = Player(); var material = Material(owner);
        Harness.OnExhaust = card => { effect(owner); return Task.CompletedTask; };
        Check(await BeastForms.Convert(context, material) is null, "exhaust response terminal boundary prevents generation");
        Check(Harness.Exhausted.Count == 1 && Harness.Generated.Count == 0 && !Harness.Events.Contains("create"), "committed native exhaust survives terminal stop without orphan card");
    }
    Harness.Reset(); var local = Player(); var foreign = Player((CombatState)local.Creature.CombatState!);
    var own = Material(local); var foreignSource = Material(foreign);
    Check(await BeastForms.Convert(context, own, foreignSource) is null && Harness.Exhausted.Count == 0, "foreign player's source cannot mutate local material");
    Harness.OnExhaust = card => { card.Owner = foreign; return Task.CompletedTask; };
    Check(await BeastForms.Convert(context, own) is null && Harness.Generated.Count == 0, "owner change across await cannot create a cross-player replacement");
    Harness.Reset(); local = Player(); own = Material(local); Harness.FailGeneration = true;
    Check(await BeastForms.Convert(context, own) is null && ((CombatState)local.Creature.CombatState!).Registered.Count == 0, "failed native generation removes unpiled registration without restoring consumed material");
    Harness.Reset(); local = Player(); own = Material(local); var observed = 0;
    Task Observed(PlayerChoiceContext c, BeastChange change) { observed++; return Task.CompletedTask; }
    BeastForms.Converted += Observed;
    Harness.OnGenerated = card => { CombatManager.Instance.IsOverOrEnding = true; return Task.CompletedTask; };
    try { Check(await BeastForms.Convert(context, own) is not null && observed == 0, "generation finishing combat creates no later conversion-trigger draw"); }
    finally { BeastForms.Converted -= Observed; }
}

Task CostLifetime()
{
    // Cost order: initial, after play, after turn, after both. These independently
    // authored expectations include a masked combat discount and mixed lifetimes.
    var fixtures = new (Action<CardEnergyCost> Setup, int[] Expected)[]
    {
        (c => c.SetUntilPlayed(2), new[] { 0, 1, 0, 1 }),
        (c => c.SetThisTurn(2), new[] { 0, 0, 1, 1 }),
        (c => c.SetThisTurnOrUntilPlayed(2), new[] { 0, 1, 1, 1 }),
        (c => c.SetThisCombat(2), new[] { 0, 0, 0, 0 }),
        (c => c.AddThisCombat(2), new[] { 1, 1, 1, 1 }),
        (c => { c.AddThisCombat(-1); c.AddThisTurn(1); }, new[] { 1, 1, 0, 0 }),
        (c => { c.SetThisCombat(2); c.SetUntilPlayed(3); c.AddThisTurn(-1); }, new[] { 0, 0, 1, 0 }),
        (c => { c.AddUntilPlayed(-1); c.SetThisTurn(3); }, new[] { 1, 1, 0, 1 })
    };
    foreach (var (setup, expected) in fixtures)
    for (var state = 0; state < 4; state++)
    {
        var owner = Player(); var material = Material(owner); setup(material.EnergyCost);
        var replacement = new Volibear_T01 { Owner = owner, State = owner.Creature.CombatState };
        BeastNativeCosts.Capture(material).ApplyTo(replacement);
        if ((state & 1) != 0) replacement.EnergyCost.AfterCardPlayedCleanup();
        if ((state & 2) != 0) replacement.EnergyCost.EndOfTurnCleanup();
        Check(Cost(replacement) == expected[state], $"native transferred discount lifetime fixture state {state}");
        Check(replacement.EnergyCost.Canonical == 1 && !replacement.EnergyCost.CostsX, "generated card retains native canonical non-X cost");
    }
    var p = Player(); var old = Material(p); old.EnergyCost.SetThisTurnOrUntilPlayed(2);
    var form = new Volibear_T01 { Owner = p, State = p.Creature.CombatState };
    BeastNativeCosts.Capture(old).ApplyTo(form);
    form.EnergyCost.SetCustomBaseCost(3);
    Check(Cost(form) == 2, "subsequent native base cost changes retain the inherited discount instead of a permanent cap");
    form.EnergyCost.SetUntilPlayed(1);
    Check(Cost(form) == 1, "a new native absolute modifier refers to the generated beast");
    var clone = new Volibear_T01 { Owner = p, State = p.Creature.CombatState };
    clone.EnergyCost = form.EnergyCost.Clone(clone);
    clone.EnergyCost.AfterCardPlayedCleanup();
    Check(Cost(clone) == 3 && Cost(form) == 1, "native clone cleanup does not require a custom beast ledger or mutate source cost");
    var pending = BeastNativeCosts.Capture(old); old.EnergyCost.EndOfTurnCleanup();
    var late = new Volibear_T01 { Owner = p, State = p.Creature.CombatState };
    pending.ApplyTo(late);
    Check(Cost(late) == 1, "expired modifier during exhaustion is not resurrected by saved snapshot");
    return Task.CompletedTask;
}

async Task CouponAndRetain()
{
    var owner = Player(); var material = Material(owner, CardType.Attack);
    material.UpgradeInternal(); material.LocalKeywords.Add(CardKeyword.Retain); material.GiveSingleTurnRetain();
    NextPlayDiscount.Grant(material); CardModifier.AddModifier<ForeignModifier>(material, 1);
    var result = (await BeastForms.Convert(context, material))!;
    Check(result.IsUpgraded && result.DynamicVars["Damage"].BaseValue == 11, "upgraded material creates upgraded native token");
    Check(BeastNativeRetain.SingleTurn(result) && result.LocalKeywords.Contains(CardKeyword.Retain), "both local retain and single-turn retain transfer");
    Check(CardModifier.Modifiers(result).Count() == 1 && CardModifier.Modifiers(result).Single() is NextPlayDiscount, "only shared coupon marker is copied, not arbitrary material modifiers");
    NextPlayDiscount.Grant(result); result.EnergyCost.SetCustomBaseCost(3);
    Check(Cost(result) == 2 && CardModifier.Modifiers(result).Count() == 1, "converted coupon cannot grant a second -1 reduction");
    result.EnergyCost.AfterCardPlayedCleanup();
    await CardModifier.Modifiers(result).Single().AfterCardPlayed(context, new CardPlay { Card = result });
    Check(Cost(result) == 3 && !CardModifier.Modifiers(result).Any(), "native play expiry and shared coupon marker both clear on new identity");
    Check(CardModifier.Modifiers(material).OfType<NextPlayDiscount>().Count() == 1, "generated card cleanup cannot clear the exhausted material's marker");

    Harness.Reset(); owner = Player(); material = Material(owner); material.GiveSingleTurnRetain(); NextPlayDiscount.Grant(material);
    Harness.OnExhaust = async card =>
    {
        card.EndOfTurnCleanup();
        foreach (var modifier in CardModifier.Modifiers(card).ToArray())
            await modifier.AfterSideTurnEnd(context, CombatSide.Player, new[] { owner.Creature });
    };
    result = (await BeastForms.Convert(context, material))!;
    Check(Cost(result) == 1 && !BeastNativeRetain.SingleTurn(result) && !CardModifier.Modifiers(result).Any(), "exhaust response cleanup cannot resurrect expired coupon or turn retain");
}

async Task Selection()
{
    var owner = Player(); var source = Material(owner, pile: PileType.Play);
    var a = Material(owner, CardType.Attack); var b = Material(owner);
    Harness.Selected = new[] { a, b };
    CardModel? drawn = null;
    Task DrawOnFirst(PlayerChoiceContext choices, BeastChange change)
    {
        drawn ??= Material(owner, CardType.Attack); return Task.CompletedTask;
    }
    BeastForms.Converted += DrawOnFirst;
    try { await BeastSelection.Transform(context, source, 99, all: true); }
    finally { BeastForms.Converted -= DrawOnFirst; }
    Check(Harness.Generated.Count == 2 && drawn!.Pile!.Type == PileType.Hand && BeastForms.Shape(drawn) == BeastShape.None, "conversion-trigger draw cannot enter the frozen material batch");
    Check(Harness.Generated.All(c => Cost(c) == 0) && !CardModifier.Modifiers(a).Any() && !CardModifier.Modifiers(b).Any(), "post-conversion coupon targets new beast identities");
    Check(Harness.Exhausted.SequenceEqual(new[] { a, b }), "batch uses each material once through normal exhaust command");
    Harness.Reset(); owner = Player(); source = Material(owner, pile: PileType.Play);
    a = Material(owner); b = Material(owner); Harness.Selected = new[] { a, b };
    Harness.OnGenerated = generated => { Harness.Move(b, PileType.Discard); return Task.CompletedTask; };
    await BeastSelection.Transform(context, source, 2);
    Check(Harness.Generated.Count == 1 && b.Pile!.Type == PileType.Discard, "later selected material moved by native response is not consumed from stale hand selection");
    Harness.Reset(); owner = Player(); source = Material(owner, pile: PileType.Play);
    a = Material(owner); b = Material(owner); Harness.Selected = new[] { a, a };
    Harness.OnExhaust = material => { Harness.Move(material, PileType.Hand); return Task.CompletedTask; };
    await BeastSelection.Transform(context, source, 2);
    Check(Harness.Exhausted.Count == 1 && Harness.Generated.Count == 1 && ReferenceEquals(a.Pile, PileType.Hand.GetPile(owner)), "duplicate selection cannot consume a material twice when a native exhaust response returns it to hand");
}

async Task TokenValues()
{
    var owner = Player();
    var claw = new Volibear_T01 { Owner = owner, State = owner.Creature.CombatState };
    var target = new Creature();
    await claw.TestPlay(context, new CardPlay { Card = claw, Target = target, PlayCount = 2 });
    await claw.TestPlay(context, new CardPlay { Card = claw, Target = target, PlayIndex = 1, PlayCount = 2 });
    Check(Harness.Damage == 28 && claw.Type == CardType.Attack && claw.Keywords.Contains(CardKeyword.Exhaust), "native claw keeps 7x2 and native replay invokes its own effect twice");
    var body = new Volibear_T02 { Owner = owner, State = owner.Creature.CombatState };
    await body.TestPlay(context, new CardPlay { Card = body });
    Check(owner.Creature.Block == 9 && Harness.Lightning == 2 && body is INativeLightningSpell, "body provides native 9 block, 2 lightning and thunder-spell capability");
    body.UpgradeInternal();
    await body.TestPlay(context, new CardPlay { Card = body });
    Check(owner.Creature.Block == 21 && Harness.Lightning == 5, "upgraded native body keeps 12 block and 3 lightning");
}

sealed class ForeignModifier : CardModifier { }
