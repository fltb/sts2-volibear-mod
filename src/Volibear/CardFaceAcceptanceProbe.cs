using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Content;
using Volibear.Core;

namespace Volibear;

/// <summary>Finite native paid-play fixtures. Python owns independent reference expectations.
/// Install ONLY in the isolated card-face-acceptance bootstrap, before the starter combat.
/// This is controlled queue/viewport input, not OS input and not complete G2 acceptance.</summary>
internal static class CardFaceAcceptanceProbe
{
    private static bool started;
    private static Player? player;
    private static readonly Harmony Observer = new("Volibear.CardFaceAcceptanceObserver");
    private static readonly Dictionary<CardModel,string> Cards = new(ReferenceEqualityComparer.Instance);
    private static readonly List<object> Payments = [], Effects = [];
    private static NativeControlledChoice.Request? SimpleRequest;
    private static Action<CardModel,Player?>? Generated;
    internal const string Implemented = "B01 B02 B03 C01 C02 C03 C08 C09 C12 C13 C20 C22 C24 C26 U05 U06 U07 U13 U15 U20 U23 U24 U27 U31 U36 U38 U40 R05 R07 R12 R17 R21 R23 R24 T01 T02 C05 C14 C17 C18 C21 C25 U02 U03 U04 U10 U11 U12 U14 U19 U21 U25 U26 U29 U32 U34 U37 R01 R02 R06 R13 R14 R16 R18 B04 C04 C06 C10 C11 U08 U28 U35 R31 C07 C15 C19 U39 U41 U42 U43 R10 R25 R27 R28 R29 R30 U17 R08 R09";
    private static readonly string[] SelectionIds = "C07 C15 C19 U39 U41 U42 U43 R10 R25 R27 R28 R30".Split(' ');
    internal static string[] Branches(string id) => id switch
    {
        "B01" => ["plain","strength","weak","vulnerable","blocked","lethal","replay"],
        "B02" => ["plain","dexterity","frail"],
        "B03" => ["plain","lethal"],
        "C02" or "U06" => ["plain","lethal","domain","conduction"],
        "C09" or "C22" => ["plain","domain","conduction"],
        "T01" => ["plain","converted","master","domain"],
        "T02" => ["plain","converted","master"],
        "C12" => ["plain","strength","negative-strength","dexterity","frail"],
        "C13" or "U15" => ["plain","material"],
        "U02" or "U29" or "U34" => ["plain","second-instance"],
        "U05" => ["plain","zero-block","strength"],
        "R05" => ["plain","zero-block","dexterity","frail"],
        "R07" => ["plain","zero-block","charge"],
        "U24" => ["plain","blocked","injured","overkill"],
        "R31" => ["plain","blocked"],
        "U12" or "U13" => ["plain","strength","negative-strength"],
        "R13" or "U37" => ["plain","domain"],
        "C24" => ["plain","strength","weak","vulnerable"],
        "U31" => ["x0","x1","x3","x0-replay","x1-replay","x3-replay"],
        "R17" => ["x0","x1","x3"],
        "U21" => ["plain","prior1","prior2","prior5","second-instance"],
        "C26" or "U27" or "U36" or "U38" or "U40" or "R21" or "R24" => ["plain","prior1","prior2","prior5"],
        "R23" => ["plain","blocked"],
        "C07" or "C15" => ["plain","empty","full-hand"],
        "C19" or "U39" or "U41" or "U43" or "R29" or "R30" => ["plain","empty"],
        "U42" => ["plain","empty","status","curse"],
        "R10" or "R25" => ["plain","zero","empty","insufficient","full-hand"],
        "R27" => ["plain","zero","empty","insufficient"],
        "R28" or "U17" => ["plain","zero","empty"],
        "R12" => ["plain","empty","full-hand"],
        _ => ["plain"]
    };
    private static string? Ref(CardModel? card) => card is null ? null : Cards.TryGetValue(card,out var id) ? id : throw new InvalidOperationException("Unbound face fixture identity");
    public static void Install()
    {
        Observer.CreateClassProcessor(typeof(Payment)).Patch();
        Observer.CreateClassProcessor(typeof(Effect)).Patch();
        Observer.CreateClassProcessor(typeof(Generation)).Patch();
        Observer.CreateClassProcessor(typeof(SimpleGrid)).Patch();
        Observer.CreateClassProcessor(typeof(SimpleReserve)).Patch();
        Observer.CreateClassProcessor(typeof(SimpleSync)).Patch();
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state)
    {
        if (started) return;started = true;
        var batch = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_BATCH");
        if (string.IsNullOrWhiteSpace(batch)) _ = Run(state);
        else _ = RunBatch(state,batch);
    }
    private static bool Quiet(CombatState state) => NativeAcceptanceRunHost.IsQuiet(state,1);
    private static async Task RunBatch(CombatState warmup,string selection)
    {
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        var completed = new List<string>();var transitions = new List<object>();
        var cases = selection.Split(',',StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var identities = new Dictionary<object,int>(ReferenceEqualityComparer.Instance);
        int Identity(object value) { if (!identities.TryGetValue(value,out var id)) { id=identities.Count;identities.Add(value,id); } return id; }
        CombatManager.Instance.TurnStarted -= Start;
        try
        {
            var release=ReleaseInfoManager.Instance.ReleaseInfo;
            if (release is null || release.Version!="v0.107.1" || release.Commit!="59260271" || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Pinned native release required for batch");
            var allowed = Implemented.Split(' ').SelectMany(id => new[] { "base","upgrade" }.SelectMany(face => Branches(id).Select(branch => id+"-"+face+"-"+branch))).ToHashSet();
            if (string.IsNullOrWhiteSpace(token) || cases.Length == 0 || cases.Distinct().Count()!=cases.Length || cases.Any(c => !allowed.Contains(c)))
                throw new InvalidOperationException("Batch requires unique explicit finite case selection and token");
            var warmRun = RunManager.Instance.DebugOnlyGetState() ?? throw new InvalidOperationException("Missing native warmup run");
            Identity(warmRun);Identity(warmup.Players.Single());Identity(warmup.Players.Single().Creature);Identity(warmup.Players.Single().Deck);
            await Frame();await Until(() => Quiet(warmup),"Warmup not quiet");
            await NativeAcceptanceRunHost.ExitToMainMenu();
            for (int index=0;index<cases.Length;index++)
            {
                var summon = cases[index] is "R09-base-summon" or "R09-upgrade-summon";
                EncounterModel encounter = summon ? ModelDb.Encounter<OvicopterNormal>() : ModelDb.Encounter<SlimesWeak>();
                var state = await NativeAcceptanceRunHost.StartFresh(encounter,"volibear-card-face-batch");
                var runState = RunManager.Instance.DebugOnlyGetState() ?? throw new InvalidOperationException("Missing fresh run");
                var freshOwner = state.Players.Single();
                if (identities.ContainsKey(runState) || identities.ContainsKey(freshOwner) || identities.ContainsKey(freshOwner.Creature) || identities.ContainsKey(freshOwner.Deck))
                    throw new InvalidOperationException("Native run/player/creature/deck identity reused");
                int runId=Identity(runState),playerIdentity=Identity(freshOwner),creatureIdentity=Identity(freshOwner.Creature),deckIdentity=Identity(freshOwner.Deck);
                Cards.Clear();Payments.Clear();Effects.Clear();
                await Run(state,cases[index],inBatch:true);
                await Until(() => Quiet(state),"Completed case not quiet before native exit");
                var exit = await NativeAcceptanceRunHost.ExitToMainMenu();
                transitions.Add(new { variant=cases[index],runIdentity=runId,playerIdentity,creatureIdentity,deckIdentity,
                    runNull=exit.RunNull,combatNull=exit.CombatNull,inProgress=exit.InProgress,queueEmpty=exit.QueueEmpty,actionNull=exit.ActionNull,historyVisible=exit.HistoryVisible });
                completed.Add(cases[index]);GD.Print("[Volibear] CARD_FACE_BATCH_CASE_COMPLETE "+cases[index]);
            }
            GD.Print("[Volibear] CARD_FACE_BATCH_RESULT "+JsonSerializer.Serialize(new { schema=1,token,cases,completed,transitions,
                lifecycle="EnterRoom(MapRoom)->ReturnToMainMenu->StartNewSingleplayerRun",shouldSave=false }));
            GD.Print("[Volibear] SHUTDOWN_BEGIN "+token);NGame.Instance!.Quit();((SceneTree)Engine.GetMainLoop()).Quit(0);
        }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] CARD_FACE_BATCH_ERROR "+JsonSerializer.Serialize(new { token,cases,completed,error=error.ToString() }));
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
        finally { player=null;Generated=null;SimpleRequest=null;Observer.UnpatchAll(Observer.Id); }
    }
    private static async Task Frame()
    {
        var tree = (SceneTree)Engine.GetMainLoop(); await tree.ToSignal(tree,SceneTree.SignalName.ProcessFrame);
    }
    private static async Task Until(Func<bool> done,string label)
    {
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (!done()) { if (timer.Elapsed > TimeSpan.FromSeconds(30)) throw new TimeoutException(label); await Frame(); }
    }
    private static IEnumerable<Node> Descendants(Node node)
    {
        yield return node;
        foreach (var child in node.GetChildren()) foreach (var nested in Descendants(child)) yield return nested;
    }
    private static CardModel Create(CombatState s,Player p,string id) => id switch
    {
        "SLIMED" => s.CreateCard<Slimed>(p), "INJURY" => s.CreateCard<Injury>(p),
        "B01" => s.CreateCard<Volibear_B01>(p), "B02" => s.CreateCard<Volibear_B02>(p), "B03" => s.CreateCard<Volibear_B03>(p),
        "C01" => s.CreateCard<Volibear_C01>(p), "C02" => s.CreateCard<Volibear_C02>(p), "C03" => s.CreateCard<Volibear_C03>(p),
        "C08" => s.CreateCard<Volibear_C08>(p), "C09" => s.CreateCard<Volibear_C09>(p), "C12" => s.CreateCard<Volibear_C12>(p),
        "C13" => s.CreateCard<Volibear_C13>(p), "C20" => s.CreateCard<Volibear_C20>(p), "C22" => s.CreateCard<Volibear_C22>(p),
        "C24" => s.CreateCard<Volibear_C24>(p), "C26" => s.CreateCard<Volibear_C26>(p), "U05" => s.CreateCard<Volibear_U05>(p),
        "U06" => s.CreateCard<Volibear_U06>(p), "U07" => s.CreateCard<Volibear_U07>(p), "U13" => s.CreateCard<Volibear_U13>(p),
        "U15" => s.CreateCard<Volibear_U15>(p), "U20" => s.CreateCard<Volibear_U20>(p), "U23" => s.CreateCard<Volibear_U23>(p),
        "U24" => s.CreateCard<Volibear_U24>(p), "U27" => s.CreateCard<Volibear_U27>(p), "U31" => s.CreateCard<Volibear_U31>(p),
        "U36" => s.CreateCard<Volibear_U36>(p), "U38" => s.CreateCard<Volibear_U38>(p), "U40" => s.CreateCard<Volibear_U40>(p),
        "R05" => s.CreateCard<Volibear_R05>(p), "R07" => s.CreateCard<Volibear_R07>(p), "R12" => s.CreateCard<Volibear_R12>(p),
        "R17" => s.CreateCard<Volibear_R17>(p), "R21" => s.CreateCard<Volibear_R21>(p), "R23" => s.CreateCard<Volibear_R23>(p),
        "R24" => s.CreateCard<Volibear_R24>(p), "T01" => s.CreateCard<Volibear_T01>(p), "T02" => s.CreateCard<Volibear_T02>(p),
        "C05" => s.CreateCard<Volibear_C05>(p), "C14" => s.CreateCard<Volibear_C14>(p), "C17" => s.CreateCard<Volibear_C17>(p),
        "C18" => s.CreateCard<Volibear_C18>(p), "C21" => s.CreateCard<Volibear_C21>(p), "C25" => s.CreateCard<Volibear_C25>(p),
        "U02" => s.CreateCard<Volibear_U02>(p), "U03" => s.CreateCard<Volibear_U03>(p), "U04" => s.CreateCard<Volibear_U04>(p),
        "U10" => s.CreateCard<Volibear_U10>(p), "U11" => s.CreateCard<Volibear_U11>(p), "U12" => s.CreateCard<Volibear_U12>(p),
        "U14" => s.CreateCard<Volibear_U14>(p), "U19" => s.CreateCard<Volibear_U19>(p), "U21" => s.CreateCard<Volibear_U21>(p),
        "U25" => s.CreateCard<Volibear_U25>(p), "U26" => s.CreateCard<Volibear_U26>(p), "U29" => s.CreateCard<Volibear_U29>(p),
        "U32" => s.CreateCard<Volibear_U32>(p), "U34" => s.CreateCard<Volibear_U34>(p), "U37" => s.CreateCard<Volibear_U37>(p),
        "R01" => s.CreateCard<Volibear_R01>(p), "R02" => s.CreateCard<Volibear_R02>(p), "R06" => s.CreateCard<Volibear_R06>(p),
        "R13" => s.CreateCard<Volibear_R13>(p), "R14" => s.CreateCard<Volibear_R14>(p), "R16" => s.CreateCard<Volibear_R16>(p), "R18" => s.CreateCard<Volibear_R18>(p),
        "B04" => s.CreateCard<Volibear_B04>(p), "C04" => s.CreateCard<Volibear_C04>(p), "C06" => s.CreateCard<Volibear_C06>(p),
        "C10" => s.CreateCard<Volibear_C10>(p), "C11" => s.CreateCard<Volibear_C11>(p), "U08" => s.CreateCard<Volibear_U08>(p),
        "U28" => s.CreateCard<Volibear_U28>(p), "U35" => s.CreateCard<Volibear_U35>(p), "R31" => s.CreateCard<Volibear_R31>(p),
        "C07" => s.CreateCard<Volibear_C07>(p), "C15" => s.CreateCard<Volibear_C15>(p), "C19" => s.CreateCard<Volibear_C19>(p),
        "U39" => s.CreateCard<Volibear_U39>(p), "U41" => s.CreateCard<Volibear_U41>(p), "U42" => s.CreateCard<Volibear_U42>(p),
        "U43" => s.CreateCard<Volibear_U43>(p), "R10" => s.CreateCard<Volibear_R10>(p), "R25" => s.CreateCard<Volibear_R25>(p),
        "R27" => s.CreateCard<Volibear_R27>(p), "R28" => s.CreateCard<Volibear_R28>(p), "R29" => s.CreateCard<Volibear_R29>(p), "R30" => s.CreateCard<Volibear_R30>(p),
        "U17" => s.CreateCard<Volibear_U17>(p), "R08" => s.CreateCard<Volibear_R08>(p), "R09" => s.CreateCard<Volibear_R09>(p),
        _ => throw new InvalidOperationException("Unimplemented face; not counted as coverage")
    };
    private static async Task Run(CombatState state,string? caseOverride=null,bool inBatch=false)
    {
        NativeControlledChoice? choices = null;
        try
        {
            var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
            var variant = caseOverride ?? System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_CARD_FACE_CASE") ?? "";
            var parts = variant.Split('-',3);
            if (string.IsNullOrWhiteSpace(token) || parts.Length != 3 || !Implemented.Split(' ').Contains(parts[0]) ||
                parts[1] is not ("base" or "upgrade") || !Branches(parts[0]).Contains(parts[2]))
                throw new InvalidOperationException("Missing token or unknown finite face case");
            var id = parts[0]; bool upgraded = parts[1] == "upgrade"; var branch = parts[2];
            var release = ReleaseInfoManager.Instance.ReleaseInfo ?? throw new InvalidOperationException("No release metadata");
            if (release.Version != "v0.107.1" || release.Commit != "59260271" || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
                throw new InvalidOperationException("Pinned native release required, TestMode forbidden");
            player = state.Players.Single(); var p = player; var owner = p.Creature;
            var pcs = p.PlayerCombatState ?? throw new InvalidOperationException("No combat state");
            var enemies = state.Enemies.OrderBy(e => e.Monster is LeafSlimeS ? 0 : e.Monster is TwigSlimeS ? 1 : 2).ToArray();
            if (state.RoundNumber != 1 || pcs.TurnNumber != 1 || owner.CurrentHp != 80 || owner.Block != 0 || owner.Powers.Any() ||
                p.Relics.Count != 1 || p.Relics[0] is not HuntersHeart || enemies.Length != 3 || enemies[0].Monster is not LeafSlimeS ||
                enemies[1].Monster is not TwigSlimeS || enemies[2].Monster is not (LeafSlimeM or TwigSlimeM) || enemies.Any(e => e.Block != 0 || e.Powers.Any()))
                throw new InvalidOperationException("Expected untouched three-slime starter fixture");
            var leafMonster = enemies[0].Monster ?? throw new InvalidOperationException("Fixture leaf has no native monster");
            if ((id is "B04" or "C04" or "C06" or "C10" or "C11" or "U28" or "U35") &&
                (leafMonster.NextMove.Id != "TACKLE_MOVE" || !leafMonster.IntendsToAttack))
                throw new InvalidOperationException("Expected native LeafSlimeS first TACKLE_MOVE");
            foreach (var c in pcs.AllPiles.SelectMany(pile => pile.Cards).Distinct()) Cards.Add(c,"starter-"+Cards.Count);
            if (Cards.Count != 10) throw new InvalidOperationException("Expected ten original cards");
            foreach (var c in pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(c,PileType.Draw);
            var starterDrawOrder = pcs.DrawPile.Cards.Select(Ref).ToArray();
            if (branch == "empty" && (id is "C07" or "U43" or "R25" or "U17" or "R12") || branch == "insufficient" && id == "R25")
                foreach (var card in pcs.DrawPile.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Exhaust);
            foreach (var enemy in enemies) await CreatureCmd.SetMaxAndCurrentHp(enemy,500m);
            var fixtureContext = new ThrowingPlayerChoiceContext();
            int prior = branch.StartsWith("prior") ? int.Parse(branch[5..]) : 0;
            for (int i = 0; i < prior; i++) await LightningCmd.DealAllEnemies(fixtureContext,owner,1m);
            if (branch == "lethal") await CreatureCmd.SetMaxAndCurrentHp(enemies[0],id switch { "B01" => upgraded ? 9 : 6, "B03" => upgraded ? 11 : 8, "C02" => upgraded ? 7 : 5, _ => upgraded ? 11 : 8 });
            if (branch == "blocked") await CreatureCmd.GainBlock(enemies[0],100m,ValueProp.Unpowered,null);
            if ((id is "U05" or "R05" or "R07") && branch != "zero-block") await CreatureCmd.GainBlock(owner,10m,ValueProp.Unpowered,null);
            if (branch == "strength") await PowerCmd.Apply<StrengthPower>(fixtureContext,owner,3m,owner,null);
            if (branch == "negative-strength") await PowerCmd.Apply<StrengthPower>(fixtureContext,owner,-3m,owner,null);
            if (branch == "weak") await PowerCmd.Apply<WeakPower>(fixtureContext,owner,1m,owner,null);
            if (branch == "vulnerable") await PowerCmd.Apply<VulnerablePower>(fixtureContext,enemies[0],1m,owner,null);
            if (branch == "dexterity") await PowerCmd.Apply<DexterityPower>(fixtureContext,owner,3m,owner,null);
            if (branch == "frail") await PowerCmd.Apply<FrailPower>(fixtureContext,owner,1m,owner,null);
            if (branch == "second-instance")
            {
                if (id == "U02") await PowerCmd.Apply<StormConductionPower>(fixtureContext,owner,upgraded ? 4m : 3m,owner,null);
                else if (id == "U21") await PowerCmd.Apply<ThunderAftershockPower>(fixtureContext,owner,1m,owner,null);
                else if (id == "U34") await PowerCmd.Apply<ThunderArmorPower>(fixtureContext,owner,upgraded ? 4m : 3m,owner,null);
                else await StormChargePower.Gain(fixtureContext,owner,upgraded ? 3 : 2);
            }
            if (branch == "conduction") await PowerCmd.Apply<StormConductionPower>(fixtureContext,owner,3m,owner,null);
            if (branch.EndsWith("replay")) await PowerCmd.Apply<NextAttackReplayPower>(fixtureContext,owner,1m,owner,null);
            if (branch == "charge") await StormChargePower.Gain(fixtureContext,owner,2);
            if (branch == "domain") await DomainPower.Open(fixtureContext,owner,2);
            if (branch is "injured" or "overkill") await CreatureCmd.SetCurrentHp(owner,70m);
            if (branch == "overkill") await CreatureCmd.SetMaxAndCurrentHp(enemies[0],upgraded ? 29m : 22m);
            // Fixtures set initial state only; the queued production card owns damage and healing.
            await PlayerCmd.SetEnergy(id == "C01" ? 0 : branch.StartsWith('x') ? int.Parse(branch.Split('-')[0][1..]) : 10,p);
            CardModel source;
            if (branch == "master")
            {
                source = Cards.Keys.First(c => id == "T01" ? c is Volibear_B01 : c is Volibear_B02);
                var oldRef = Cards[source]; Cards[source] = "source";
                starterDrawOrder = starterDrawOrder.Select(r => r == oldRef ? "source" : r).ToArray();
                if (source.DeckVersion is null || !p.Deck.Cards.Any(c => ReferenceEquals(c,source.DeckVersion)))
                    throw new InvalidOperationException("Missing real starter master link");
            }
            else { source = Create(state,p,branch == "converted" ? id == "T01" ? "B01" : "B02" : id); Cards.Add(source,"source"); }
            var sourceMasterBefore = source.DeckVersion;
            var sourceMasterUpgradedBefore = sourceMasterBefore?.IsUpgraded;
            if (upgraded) CardCmd.Upgrade(source);
            await CardPileCmd.Add(source,PileType.Hand);
            // Native NetCombatCardDb assigns ids on pile insertion, not CreateCard.
            var sourceIndexBefore = NetCombatCard.FromModel(source).CombatCardIndex;
            if (branch is "converted" or "master") { await BeastForms.Convert(fixtureContext,source); NextPlayDiscount.Grant(source); }
            if (branch == "full-hand")
                foreach (var card in pcs.DrawPile.Cards.Take(9).ToArray()) await CardPileCmd.Add(card,PileType.Hand);
            CardModel? material = null;
            if (branch == "material")
            {
                material = state.CreateCard<Volibear_B01>(p); Cards.Add(material,"material"); await CardPileCmd.Add(material,PileType.Hand);
                var alternate = state.CreateCard<Volibear_B02>(p); Cards.Add(alternate,"alternate"); await CardPileCmd.Add(alternate,PileType.Hand);
                choices = new NativeControlledChoice(p);
            }
            var tracked = new List<CardModel>();
            async Task AddSelection(string label,string code,PileType pile)
            {
                var card = Create(state,p,code); Cards.Add(card,label); tracked.Add(card); await CardPileCmd.Add(card,pile);
            }
            if ((SelectionIds.Contains(id) || id == "R29") && branch != "empty")
            {
                if (id == "U42" && branch is "status" or "curse")
                {
                    await AddSelection("selected",branch == "status" ? "SLIMED" : "INJURY",PileType.Hand);
                    await AddSelection("alternate",branch == "status" ? "INJURY" : "SLIMED",PileType.Hand);
                }
                else if (branch == "insufficient")
                    await AddSelection("selected",id == "R25" ? "B02" : "B01",id == "R10" ? PileType.Discard : id == "R25" ? PileType.Draw : PileType.Hand);
                else switch (id)
                {
                    case "C07": await AddSelection("selected","B01",PileType.Draw); await AddSelection("alternate","B01",PileType.Draw); break;
                    case "C15": await AddSelection("selected","B01",PileType.Discard); await AddSelection("alternate","R07",PileType.Discard); break;
                    case "U39": await AddSelection("selected","R07",PileType.Draw); await AddSelection("alternate","R23",PileType.Draw); break;
                    case "U43": await AddSelection("selected","B01",PileType.Draw); await AddSelection("alternate","B02",PileType.Hand); await AddSelection("third","B02",PileType.Draw); break;
                    case "R10":
                        foreach (var label in new[] { "selected","alternate","third","fourth","fifth" }) await AddSelection(label,"B01",PileType.Discard);
                        break;
                    case "R25": await AddSelection("selected","B02",PileType.Draw); await AddSelection("alternate","B02",PileType.Draw); break;
                    case "R27":
                        await AddSelection("selected","B01",PileType.Hand); await AddSelection("alternate","B02",PileType.Hand);
                        await AddSelection("third","B01",PileType.Hand); await AddSelection("fourth","B02",PileType.Hand); break;
                    default:
                        await AddSelection("selected",id == "U42" ? "B02" : "B01",PileType.Hand);
                        await AddSelection("alternate",id is "C19" or "U41" ? "B01" : "B02",PileType.Hand); break;
                }
                if (id != "R29") choices = new NativeControlledChoice(p);
            }
            object Snapshot() => new { round = state.RoundNumber,turn = pcs.TurnNumber,energy = pcs.Energy,hp = owner.CurrentHp,block = owner.Block,
                enemyHp = enemies.Select(e => e.CurrentHp).ToArray(),enemyBlock = enemies.Select(e => e.Block).ToArray(),
                powers = owner.Powers.GroupBy(pow => pow.GetType().Name).ToDictionary(g => g.Key,g => g.Sum(pow => pow.Amount)),
                powerInstances = owner.Powers.GroupBy(pow => pow.GetType().Name).ToDictionary(g => g.Key,g => g.Distinct(ReferenceEqualityComparer.Instance).Count()),
                enemyPowers = enemies.Select(e => e.Powers.ToDictionary(pow => pow.GetType().Name,pow => pow.Amount)).ToArray(),
                lightningCount = LightningBatches.GetTurnCount(owner),sourceShape = BeastForms.Shape(source).ToString(),
                selectedCards = tracked.Select(c => new { cardRef = Ref(c),shape = BeastForms.Shape(c).ToString(),type = c.Type.ToString(),upgraded = c.IsUpgraded,
                    cost = c.EnergyCost.GetWithModifiers(CostModifiers.All),prepared = CardModifier.Modifiers(c).OfType<PreparedAttackBonus>().Sum(m => m.Amount),
                    retain = c.ShouldRetainThisTurn,discount = CardModifier.Modifiers(c).OfType<NextPlayDiscount>().Count(),pile = c.Pile?.Type.ToString() }).ToArray(),
                hand = pcs.Hand.Cards.Select(Ref).ToArray(),draw = pcs.DrawPile.Cards.Select(Ref).ToArray(),
                discard = pcs.DiscardPile.Cards.Select(Ref).ToArray(),play = pcs.PlayPile.Cards.Select(Ref).ToArray(),exhaust = pcs.ExhaustPile.Cards.Select(Ref).ToArray() };
            object History(IEnumerable<MegaCrit.Sts2.Core.Combat.History.CombatHistoryEntry> nativeEntries)
            {
                var history = nativeEntries.ToArray();
                return new {
                    plays = history.OfType<CardPlayStartedEntry>().Select(e => new { cardRef = Ref(e.CardPlay.Card),index = e.CardPlay.PlayIndex,count = e.CardPlay.PlayCount }).ToArray(),
                    sequence = history.Where(e => e is DamageReceivedEntry or CardDrawnEntry or CardExhaustedEntry or BlockGainedEntry ||
                        e is PowerReceivedEntry pe && pe.Power is DomainPower or WeakPower or VulnerablePower or BiteMarkPower).Select(e => e switch
                        {
                            DamageReceivedEntry d => (object)new { kind = "damage",target = Array.IndexOf(enemies,d.Receiver),cardRef = Ref(d.CardSource),hpLost = d.Result.UnblockedDamage,blocked = d.Result.BlockedDamage,props = (int)d.Result.Props },
                            CardDrawnEntry d => new { kind = "draw",cardRef = Ref(d.Card) },
                            CardExhaustedEntry x => new { kind = "exhaust",cardRef = Ref(x.Card) },
                            BlockGainedEntry b => new { kind = "block",target = Array.IndexOf(enemies,b.Receiver),cardRef = Ref(b.CardPlay?.Card),amount = b.Amount,props = (int)b.Props },
                            PowerReceivedEntry pe => new { kind = "power",target = Array.IndexOf(enemies,pe.Power.Owner),type = pe.Power.GetType().Name,amount = pe.Amount },
                            _ => throw new InvalidOperationException("Unexpected filtered native history entry")
                        }).ToArray(),
                    generated = history.OfType<CardGeneratedEntry>().Select(e => new { cardRef = Ref(e.Card),creatorId = e.Creator?.Creature.CombatId }).ToArray(),
                    draws = history.OfType<CardDrawnEntry>().Select(e => Ref(e.Card)).ToArray(),moves = history.OfType<MonsterPerformedMoveEntry>().Select(e => e.Move.Id).ToArray(),
                    damage = history.OfType<DamageReceivedEntry>().Select(e => new { target = Array.IndexOf(enemies,e.Receiver),cardRef = Ref(e.CardSource),hpLost = e.Result.UnblockedDamage,blocked = e.Result.BlockedDamage,props = (int)e.Result.Props }).ToArray()
                };
            }
            int generatedCount = 0;
            Generated = (card,creator) =>
            {
                var monster = state.Enemies.Select(e => e.Monster).SingleOrDefault(m => m is { IsPerformingMove:true });
                if (id != "R09" || card is not Slimed || !ReferenceEquals(card.Owner,p) || creator is not null || card.DeckVersion is not null ||
                    card.Pile?.Type != PileType.Discard || monster is not (LeafSlimeM or TwigSlimeM) ||
                    monster.NextMove.Id is not ("STICKY_SHOT" or "STICKY_SHOT_MOVE")) throw new InvalidOperationException("Unexpected generated native face fixture card");
                Cards.Add(card,"generated-"+generatedCount++);
            };
            var enemyOrder = state.Enemies.Select(e => Array.IndexOf(enemies,e)).ToArray();
            var before = Snapshot(); int boundary = CombatManager.Instance.History.Entries.Count();
            var batches = new List<object>();
            using var subscription = LightningBatches.Subscribe(owner,(context,batch) =>
            {
                batches.Add(new { cardRef = Ref(batch.Card),baseDamage = batch.BaseDamage,amount = batch.Amount,count = batch.CountThisTurn,
                    targets = batch.Targets.Select(e => Array.IndexOf(enemies,e)).ToArray(),
                    hits = batch.Results.Select(r => new { target = Array.IndexOf(enemies,r.Receiver),hpLost = r.HpLost,blocked = r.Blocked,overkill = r.Overkill }).ToArray() });
                return Task.CompletedTask;
            });
            var target = source.TargetType == TargetType.AnyEnemy ? enemies[0] : null;
            var action = new PlayCardAction(source,target); var events = new List<object>();
            void Event(string name,GameAction a) => events.Add(new { name,state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
            action.BeforeExecuted += a => Event("before-executed",a); action.AfterFinished += a => Event("after-finished",a); action.BeforeCancelled += a => Event("cancelled",a);
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
            object? choice = null; var selections = new List<object>();
            if (choices is not null)
            {
                int count = id == "U43" ? 2 : 1;
                for (int n = 0; n < count; n++)
                {
                    int index = n;
                    await Until(() => choices.Requests.Count > index && choices.Requests[index].ChoiceId is not null,"Face choice was not reserved");
                    var request = choices.Requests[index]; request.RequireWaiting();
                    if (!ReferenceEquals(request.Action,action)) throw new InvalidOperationException("Wrong native action owns choice");
                    bool handChoice = request.Pile.Type == PileType.Hand;
                    Control? Ui() => handChoice ? NPlayerHand.Instance : NOverlayStack.Instance?.Peek() as NCombatPileCardSelectScreen;
                    var selected = branch == "zero" ? Array.Empty<CardModel>() : material is not null ? new[] { material } : id == "R10" ? tracked.Take(Math.Min(upgraded ? 4 : 3,request.Prefs.MaxSelect)).ToArray() :
                        id == "R27" ? tracked.Take(upgraded ? 3 : 2).ToArray() : id == "R25" ? tracked.Take(Math.Min(2,request.Prefs.MaxSelect)).ToArray() : new[] { tracked[0] };
                    await Until(() => Ui() is { } ui && selected.All(c => Descendants(ui).OfType<NCardHolder>().Any(h => h.IsVisibleInTree() && ReferenceEquals(h.CardNode?.Model,c))),"Face choice UI not ready");
                    var ui = Ui()!;
                    var holders = Descendants(ui).OfType<NCardHolder>().Where(h => h.IsVisibleInTree() && request.Eligible.Any(c => ReferenceEquals(c,h.CardNode?.Model))).ToArray();
                    var pending = Snapshot(); var description = request.Describe(); var visible = holders.Select(h => Ref(h.CardNode!.Model)).ToArray();
                    foreach (var card in selected)
                        await NativeControlledChoice.SelectVisibleCandidate(request,holders.Single(h => ReferenceEquals(h.CardNode?.Model,card)));
                    if (request.Synced.Count == 0 && (handChoice || request.Prefs.RequireManualConfirmation))
                    {
                        var confirm = ui.GetNode<NClickableControl>(handChoice ? "%SelectModeConfirmButton" : "%Confirm");
                        await Until(() => confirm.IsEnabled,"Face confirm did not enable"); await NativeControlledChoice.ConfirmIfRequired(request,confirm);
                    }
                    await Until(() => request.Synced.Count == 1,"Face choice never synchronized");
                    var receipt = new { request = description,pending,visible,inputs = request.Inputs.ToArray(),sync = request.Synced.ToArray() };
                    if (material is not null) choice = receipt; else selections.Add(receipt);
                }
                if (choices.Requests.Count != count) throw new InvalidOperationException("Unexpected native selection count");
            }
            if (id == "U17" && branch != "empty")
            {
                await Until(() => SimpleRequest?.ChoiceId is not null && NOverlayStack.Instance?.Peek() is NSimpleCardSelectScreen,"Native scry grid not ready");
                var request = SimpleRequest!; request.RequireWaiting();
                if (!ReferenceEquals(request.Action,action)) throw new InvalidOperationException("Wrong action owns scry");
                var ui = (NSimpleCardSelectScreen)NOverlayStack.Instance!.Peek()!;
                await Until(() => request.Eligible.All(c => Descendants(ui).OfType<NCardHolder>().Any(h => h.IsVisibleInTree() && ReferenceEquals(h.CardNode?.Model,c))),"Scry candidates not visible");
                var holders = Descendants(ui).OfType<NCardHolder>().Where(h => h.IsVisibleInTree() && request.Eligible.Any(c => ReferenceEquals(c,h.CardNode?.Model))).ToArray();
                var pending = Snapshot(); var description = request.Describe(); var visible = holders.Select(h => Ref(h.CardNode!.Model)).ToArray();
                foreach (var card in request.Eligible.Take(branch == "zero" ? 0 : 2)) await NativeControlledChoice.SelectVisibleCandidate(request,holders.Single(h => ReferenceEquals(h.CardNode?.Model,card)));
                var confirm = ui.GetNode<NClickableControl>("%Confirm");
                await Until(() => confirm.IsEnabled,"Scry confirmation not enabled"); await NativeControlledChoice.ConfirmIfRequired(request,confirm);
                await Until(() => request.Synced.Count == 1,"Scry indices never synchronized");
                selections.Add(new { request = description,pending,visible,inputs = request.Inputs.ToArray(),sync = request.Synced.ToArray() });
            }
            await Until(() => action.CompletionTask.IsCompleted,"Native face action did not finish"); await action.CompletionTask;
            if (action.Exception is not null) throw new InvalidOperationException("Native face action fault",action.Exception);
            var entries = CombatManager.Instance.History.Entries.Skip(boundary).ToArray();
            var sourceAfter = Snapshot();var sourcePayments = Payments.ToArray();var sourceEffects = Effects.ToArray();var sourceBatches = batches.ToArray();
            object? response = null;
            if (branch == "second-instance" || id == "U42" && (branch is "status" or "curse"))
            {
                var follow = id == "U42" ? tracked[0] : Create(state,p,id == "U02" ? "C02" : id == "U21" ? "R23" : "C24");
                if (id != "U42") { Cards.Add(follow,"response-card");await CardPileCmd.Add(follow,PileType.Hand); }
                var responseBefore = Snapshot();int h = CombatManager.Instance.History.Entries.Count(),pi = Payments.Count,ei = Effects.Count,bi = batches.Count;
                var followAction = new PlayCardAction(follow,follow.TargetType == TargetType.AnyEnemy ? enemies[0] : null);
                var followEvents = new List<object>();
                void FollowEvent(string name,GameAction a) => followEvents.Add(new { name,state = a.State.ToString(),id = a.Id,energy = pcs.Energy });
                followAction.BeforeExecuted += a => FollowEvent("before-executed",a);followAction.AfterFinished += a => FollowEvent("after-finished",a);followAction.BeforeCancelled += a => FollowEvent("cancelled",a);
                RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(followAction);
                await Until(() => followAction.CompletionTask.IsCompleted,"Native response action did not finish");await followAction.CompletionTask;
                if (followAction.Exception is not null) throw new InvalidOperationException("Native response action fault",followAction.Exception);
                response = new { before = responseBefore,after = Snapshot(),
                    action = new { id = followAction.Id,state = followAction.State.ToString(),type = followAction.GetType().Name,context = followAction.PlayerChoiceContext?.GetType().Name,
                        actionType = followAction.ActionType.ToString(),target = followAction.TargetId,sameCard = ReferenceEquals(followAction.NetCombatCard.ToCardModel(),follow),events = followEvents },
                    payments = Payments.Skip(pi).ToArray(),effects = Effects.Skip(ei).ToArray(),batches = batches.Skip(bi).ToArray(),history = History(CombatManager.Instance.History.Entries.Skip(h)) };
            }
            GD.Print("[Volibear] CARD_FACE_RESULT " + JsonSerializer.Serialize(new {
                schema = 1,token,variant,scenario = "card-face-acceptance",acceptance = "controlled-native-queue-viewport-not-OS-input",
                version = release.Version,commit = release.Commit,testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
                character = p.Character.GetType().Name,enemyTypes = enemies.Select(e => e.Monster!.GetType().Name).ToArray(),
                playerId = owner.CombatId,enemyIds = enemies.Select(e => e.CombatId).ToArray(),enemyOrder,
                cards = Cards.Select(kv => new { cardRef = kv.Value,modelId = kv.Key.Id.Entry,upgraded = kv.Key.IsUpgraded,
                    combatCardIndex = NetCombatCard.FromModel(kv.Key).CombatCardIndex,sameObject = ReferenceEquals(NetCombatCard.FromModel(kv.Key).ToCardModel(),kv.Key),
                    ownerId = kv.Key.Owner.Creature.CombatId,masterIndex = Array.FindIndex(p.Deck.Cards.ToArray(),c => ReferenceEquals(c,kv.Key.DeckVersion)),masterModelId = kv.Key.DeckVersion?.Id.Entry }).ToArray(),
                sourceIdentity = new { indexBefore = sourceIndexBefore,masterIndexBefore = Array.FindIndex(p.Deck.Cards.ToArray(),c => ReferenceEquals(c,sourceMasterBefore)),
                    sameMaster = ReferenceEquals(source.DeckVersion,sourceMasterBefore),masterUpgradedBefore = sourceMasterUpgradedBefore,masterUpgradedAfter = source.DeckVersion?.IsUpgraded },
                starterDrawOrder,before,after = sourceAfter,choice,selections,
                action = new { id = action.Id,state = action.State.ToString(),type = action.GetType().Name,context = action.PlayerChoiceContext?.GetType().Name,
                    actionType = action.ActionType.ToString(),target = action.TargetId,sameCard = ReferenceEquals(action.NetCombatCard.ToCardModel(),source),events },
                payments = sourcePayments,effects = sourceEffects,batches = sourceBatches,
                history = History(entries),response
            }));
            if (!inBatch) { GD.Print("[Volibear] SHUTDOWN_BEGIN " + token); NGame.Instance!.Quit(); ((SceneTree)Engine.GetMainLoop()).Quit(0); }
        }
        catch (Exception error) { GD.PrintErr("[Volibear] CARD_FACE_ERROR " + error); if (inBatch) throw; ((SceneTree)Engine.GetMainLoop()).Quit(2); }
        finally { choices?.Dispose(); SimpleRequest = null; Generated = null; player = null; CombatManager.Instance.TurnStarted -= Start; if (!inBatch) Observer.UnpatchAll(Observer.Id); }
    }
    // U17 alone uses the game's index-valued SimpleGrid protocol, not combat-card transport.
    // Reuse the native request/input driver; these observers never complete or replace a choice task.
    [HarmonyPatch(typeof(CardSelectCmd),nameof(CardSelectCmd.FromSimpleGrid))]
    private static class SimpleGrid
    {
        private static void Prefix(PlayerChoiceContext context,IReadOnlyList<CardModel> cardsIn,Player player,CardSelectorPrefs prefs)
        {
            if (!ReferenceEquals(player,CardFaceAcceptanceProbe.player)) return;
            if (context is not GameActionPlayerChoiceContext { Action: PlayCardAction action } || action.NetCombatCard.ToCardModel() is not Volibear_U17 ||
                SimpleRequest is not null || CardSelectCmd.Selector is not null) throw new InvalidOperationException("Unexpected scry selection path");
            var cards = cardsIn.ToArray();
            SimpleRequest = new NativeControlledChoice.Request { Player = player,Action = action,Source = action.NetCombatCard.ToCardModel(),
                Pile = PileType.Draw.GetPile(player),Prefs = prefs,Filter = c => cards.Any(x => ReferenceEquals(x,c)),Available = cards,Eligible = cards };
        }
    }
    [HarmonyPatch(typeof(PlayerChoiceSynchronizer),nameof(PlayerChoiceSynchronizer.ReserveChoiceId))]
    private static class SimpleReserve
    {
        private static void Postfix(Player player,uint __result)
        {
            if (SimpleRequest is not { } request || !ReferenceEquals(player,request.Player)) return;
            if (request.ChoiceId is not null) throw new InvalidOperationException("Duplicate scry reservation");
            request.ChoiceId = __result;
        }
    }
    [HarmonyPatch(typeof(PlayerChoiceSynchronizer),nameof(PlayerChoiceSynchronizer.SyncLocalChoice))]
    private static class SimpleSync
    {
        private static void Postfix(Player player,uint choiceId,PlayerChoiceResult result)
        {
            if (SimpleRequest is not { } request || !ReferenceEquals(player,request.Player)) return;
            if (request.ChoiceId != choiceId) throw new InvalidOperationException("Wrong scry reservation");
            var indices = result.AsIndexes().ToArray(); var selected = indices.Select(i => request.Available[i]).ToArray();
            request.Synced.Add(new { choiceId,actionId = request.Action.Id,actionState = request.Action.State.ToString(),indices,
                selected = selected.Select(request.CardIdentity).ToArray(),selectedSameObjects = selected.Select(c => request.Eligible.Any(e => ReferenceEquals(e,c))).ToArray() });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterCardGeneratedForCombat))]
    private static class Generation { private static void Prefix(CardModel card,Player? creator) => Generated?.Invoke(card,creator); }
    [HarmonyPatch(typeof(Hook),nameof(Hook.AfterEnergySpent))]
    private static class Payment
    {
        private static void Prefix(CardModel card,int amount)
        {
            if (player is not null && ReferenceEquals(card.Owner,player)) Payments.Add(new { cardRef = Ref(card),amount,energy = player.PlayerCombatState!.Energy });
        }
    }
    [HarmonyPatch(typeof(Hook),nameof(Hook.BeforeCardPlayed))]
    private static class Effect
    {
        private static void Postfix(CardPlay cardPlay,ref Task __result) => __result = Observe(__result,cardPlay);
        private static async Task Observe(Task original,CardPlay play)
        {
            await original;
            if (player is null || !ReferenceEquals(play.Card.Owner,player)) return;
            Effects.Add(new { cardRef = Ref(play.Card),index = play.PlayIndex,count = play.PlayCount,autoPlay = play.IsAutoPlay,
                energy = player.PlayerCombatState!.Energy,spent = play.Resources.EnergySpent });
        }
    }
}
