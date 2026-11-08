using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Content;
using Volibear.Core;
using Volibear.Presentation;

namespace Volibear;

/// <summary>Opt-in native command/production move-helper fixture. Not ordinary card
/// deployment acceptance, not listening evidence. Observers never invoke receipt factories.</summary>
internal static partial class AudioReceiptProbe
{
    private const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
    private static readonly Harmony Observer = new("Volibear.AudioReceiptProbe.Observer");
    private static readonly Dictionary<object, int> Ids = new(ReferenceEqualityComparer.Instance);
    private static readonly List<StepRow> Rows = [];
    private static readonly List<string> Errors = [];
    private static CombatState? Combat;
    private static Creature? Owner;
    private static StepRow? Active;
    private static CardModel? Replacement;
    private static bool started;
    private static bool installed;
    private static long sequence;
    private static int Id(object? value)
    { if (value is null) return 0; if (!Ids.TryGetValue(value, out var id)) Ids.Add(value, id = Ids.Count + 1); return id; }
    private sealed class StepRow(string id)
    {
        public string id { get; } = id;
        public int powerRef { get; set; }
        public int cardRef { get; set; }
        public int sourceRef { get; set; }
        public int replacementRef { get; set; }
        public int? beforeAmount { get; set; }
        public int? afterAmount { get; set; }
        public string? beforePile { get; set; }
        public string? afterPile { get; set; }
        public string? replacementAfter { get; set; }
        public decimal beforeHp { get; set; }
        public decimal afterHp { get; set; }
        public bool nativeTaskCompleted { get; set; }
        public List<object> receipts { get; } = [];
        public List<object> dispatches { get; } = [];
        public List<object> frames { get; } = [];
    }
    internal static void Install()
    {
        if (installed || System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_AUDIO_RECEIPTS") != "1") return;
        if (string.IsNullOrWhiteSpace(System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN")))
            throw new InvalidOperationException("Audio receipt probe requires a unique run token");
        try { InstallObservers(Observer); }
        catch { Observer.UnpatchAll(Observer.Id); throw; }
        installed = true;
        GD.Print("[Volibear] AUDIO_RECEIPT_INSTALLED");
        CombatManager.Instance.TurnStarted += Start;
        // The bootstrap can start combat before this subscription lands; retry once on the
        // next timer tick instead of idling forever with no evidence.
        var tree = (SceneTree)Engine.GetMainLoop();
        tree.CreateTimer(0.25).Timeout += () => { if (!started && CombatManager.Instance.DebugOnlyGetState() is CombatState current) Start(current); };
    }
    private static void Start(CombatState combat)
    {
        if (started) return;
        started = true;
        CombatManager.Instance.TurnStarted -= Start;
        _ = Run(combat);
    }
    private static async Task Frame()
    { var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree, SceneTree.SignalName.ProcessFrame); }
    private static async Task Pause()
    {
        // Fixture pacing only; never awaited by a presentation observer or gameplay command.
        var watch = System.Diagnostics.Stopwatch.StartNew();
        while (watch.Elapsed.TotalSeconds < 0.3) await Frame();
    }
    private static async Task Run(CombatState combat)
    {
        string? token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        try
        {
            if (MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn) throw new InvalidOperationException("TestMode forbidden");
            Combat = combat; var player = combat.Players.Single(); Owner = player.Creature;
            if (Owner.Powers.Any() || combat.RoundNumber != 1) throw new InvalidOperationException("Expected untouched first-turn owner");
            var watch = System.Diagnostics.Stopwatch.StartNew();
            while (!OwnerAttached()) { if (watch.Elapsed.TotalSeconds > 20) throw new TimeoutException("Presentation owner not attached"); await Frame(); }
            var il = InspectRuntimeBoundaries();
            var context = new ThrowingPlayerChoiceContext();
            foreach (var card in PileType.Hand.GetPile(player).Cards.ToArray()) await CardPileCmd.Add(card, PileType.Discard);
            var source = combat.CreateCard<Volibear_U39>(player); await CardPileCmd.Add(source, PileType.Hand);
            foreach (var canonical in new PowerModel[] { ModelDb.Power<StandingPower>(), ModelDb.Power<ImmovableBodyPower>(),
                ModelDb.Power<ThunderArmorPower>(), ModelDb.Power<NextAttackDiscount>(), ModelDb.Power<StrengthPower>() })
            {
                string name = canonical.GetType().Name;
                var power = canonical.ToMutable();
                await Step(name + ":new", () => PowerCmd.Apply(context, power, Owner, 2, Owner, source), power, source);
                await Step(name + ":increase", () => PowerCmd.ModifyAmount(context, power, 1, Owner, source), power, source);
                await Step(name + ":silent", () => PowerCmd.ModifyAmount(context, power, 1, Owner, source, silent: true), power, source);
                await Step(name + ":zero", () => PowerCmd.ModifyAmount(context, power, 0, Owner, source), power, source);
                await Step(name + ":negative", () => PowerCmd.ModifyAmount(context, power, -1, Owner, source), power, source);
                await PowerCmd.Remove(power);
                var silent = canonical.ToMutable();
                await Step(name + ":silent-new", () => PowerCmd.Apply(context, silent, Owner, 2, Owner, source, silent: true), silent, source);
                await PowerCmd.Remove(silent);
            }
            // GENERIC Apply<T> finds the existing instance and forwards silent:true to ModifyAmount.
            // TemporaryStrength.BeforeApplied uses this path: a genuine nested increase, with NO cue.
            var strength = ModelDb.Power<StrengthPower>().ToMutable();
            await PowerCmd.Apply(context, strength, Owner, 2, Owner, source, silent: true);
            await Step("nested-silent-strength", () => PowerCmd.Apply<VolibearChargeStrengthPower>(context, Owner, 1, Owner, source), strength, source);
            // NON-generic Apply instead enters its own native frame, then delegates existing
            // stacking to ModifyAmount. Both real frames need independent tickets; only the
            // inner native mutation may publish a receipt. No synthetic event or callback.
            await Step("nested-existing-strength", () => PowerCmd.Apply(context, strength, Owner, 1, Owner, source), strength, source);
            foreach (var power in Owner.Powers.ToArray()) await PowerCmd.Remove(power);

            // A real Status exhaust WITHOUT domain purification must not invent a purify receipt.
            var generic = combat.CreateCard<Wound>(player); await CardPileCmd.Add(generic, PileType.Hand);
            await Step("generic-exhaust", () => CardCmd.Exhaust(context, generic), null, source, generic);
            var drawn = combat.CreateCard<Volibear_B02>(player); await CardPileCmd.Add(drawn, PileType.Draw, CardPilePosition.Top);
            await Step("generic-draw", () => CardPileCmd.Draw(context, 1m, player, fromHandDraw: false), null, source, drawn);
            await CardPileCmd.Add(drawn, PileType.Discard);
            await Step("retrieve-discard", () => Retrieve(context, source, PileType.Discard,
                c => ReferenceEquals(c, drawn), 1, false, false, new LocString("cards", source.Id.Entry + ".selectionScreenPrompt")), null, source, drawn);
            await CardPileCmd.Add(drawn, PileType.Draw);
            await Step("retrieve-draw", () => Retrieve(context, source, PileType.Draw,
                c => ReferenceEquals(c, drawn), 1, false, false, new LocString("cards", source.Id.Entry + ".selectionScreenPrompt")), null, source, drawn);
            await Step("retrieve-no-candidate", () => Retrieve(context, source, PileType.Discard,
                _ => false, 1, false, false, new LocString("cards", source.Id.Entry + ".selectionScreenPrompt")), null, source, drawn);
            var domain = await DomainPower.Open(context, Owner, 2, source) ?? throw new InvalidOperationException("Domain not opened");
            Replacement = combat.CreateCard<Volibear_B02>(player); await CardPileCmd.Add(Replacement, PileType.Draw, CardPilePosition.Top);
            var wound = combat.CreateCard<Wound>(player); await CardPileCmd.Add(wound, PileType.Draw, CardPilePosition.Top);
            await Step("purify", () => CardPileCmd.Draw(context, 1m, player, fromHandDraw: false), null, source, wound);
            await PowerCmd.Remove(domain);
            if (Errors.Count != 0) throw new InvalidOperationException(string.Join(" | ", Errors));
            GD.Print("[Volibear] AUDIO_RECEIPT_RESULT " + JsonSerializer.Serialize(new
            {
                schema = 1, token, acceptance = "native-receipt/bridge/stream-not-listening",
                fixture = "native-PowerCmd-and-production-move-helpers-not-card-deployment", testMode = false,
                forcedUnmute = false, heard = false, runtimeBoundaries = il, rows = Rows
            }));
            Observer.UnpatchAll(Observer.Id);
            ((SceneTree)Engine.GetMainLoop()).Quit();
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] AUDIO_RECEIPT_FAILED " + token + " " + error);
            Observer.UnpatchAll(Observer.Id);
            ((SceneTree)Engine.GetMainLoop()).Quit(1);
        }
    }
    private static async Task Step(string id, Func<Task> execute, PowerModel? power, CardModel source, CardModel? card = null)
    {
        await Pause();
        var row = new StepRow(id) { powerRef = Id(power), cardRef = Id(card), sourceRef = Id(source),
            replacementRef = id == "purify" ? Id(Replacement) : 0, beforeAmount = power?.Amount,
            beforePile = card?.Pile?.Type.ToString(), beforeHp = Owner!.CurrentHp };
        Active = row; Rows.Add(row);
        var original = execute();
        await original; // The fixture awaits the EXACT original mechanics task, never a presentation task.
        row.nativeTaskCompleted = original.IsCompletedSuccessfully;
        await Frame(); await Frame();
        row.afterAmount = power?.Amount; row.afterPile = card?.Pile?.Type.ToString(); row.afterHp = Owner.CurrentHp;
        row.replacementAfter = id == "purify" ? Replacement?.Pile?.Type.ToString() : null;
        Active = null;
    }
    private static Type BridgeType => typeof(VolibearEffects).Assembly.GetType("Volibear.Presentation.VolibearPresentationBridge", true)!;
    private static Task Retrieve(PlayerChoiceContext context, CardModel source, PileType from,
        Func<CardModel, bool> eligible, int maximum, bool optional, bool discount, LocString prompt)
    {
        // Invoke the actual production helper; keep its original Task. Reflection lets
        // the independent emission project link only probe/adapter sources, not a second card catalog.
        var type = typeof(Volibear_U39).Assembly.GetType("Volibear.Content.ControlledEffects", true)!;
        var method = type.GetMethod("Retrieve", Flags)!;
        if (method.ReturnType != typeof(Task)) throw new InvalidOperationException("Retrieve task boundary drifted");
        return (Task)method.Invoke(null, [context, source, from, eligible, maximum, optional, discount, prompt])!;
    }
    private static bool OwnerAttached()
    {
        var room = BridgeType.GetField("_room", Flags)!.GetValue(null);
        return room is not null && room.GetType().GetField("_owners", Flags)!.GetValue(room) is IDictionary owners && owners.Contains(Owner!);
    }
}
