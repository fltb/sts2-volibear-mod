using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Runs;
using Volibear.Content;
using Volibear.Presentation;

namespace Volibear;

// Opt-in, finite, single-process capture. Never sends OS/viewport input, switches desktops,
// plays cosmetic endpoints directly, changes game volume, or records an OS audio device.
internal static class PresentationAcceptanceProbe
{
    private const BindingFlags Fields = BindingFlags.Instance | BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;
    private static bool started;
    private static string directory = "", token = "", phase = "setup";
    private static readonly List<object> Views = [], Actions = [], Frames = [], Screens = [];
    private static readonly List<float> Pcm = [];
    private static readonly Dictionary<ulong, Voice> Voices = [];
    private static readonly System.Diagnostics.Stopwatch Clock = new();
    private static AudioEffectCapture? capture;
    private static int captureIndex = -1;
    private static bool observing;
    private static Task? sampling;
    private static Exception? samplingError;
    private static long discarded;
    private static double lastScreen;
    private sealed class Voice
    {
        public ulong node { get; set; }
        public string cue { get; set; } = "";
        public string file { get; set; } = "";
        public string phase { get; set; } = "";
        public string bus { get; set; } = "";
        public double first { get; set; }
        public double last { get; set; }
        public double? ended { get; set; }
        public float volume { get; set; }
        public bool playing { get; set; }
    }
    internal static void Install()
    {
        if (Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_ACCEPTANCE") != "1") return;
        CombatManager.Instance.TurnStarted += Start;
    }
    private static void Start(CombatState state)
    {
        if (started) return;
        started = true; CombatManager.Instance.TurnStarted -= Start;
        _ = Run(state);
    }
    private static SceneTree Tree => (SceneTree)Engine.GetMainLoop();
    private static Task Frame() => FrameCore();
    private static async Task FrameCore() => await Tree.ToSignal(Tree, SceneTree.SignalName.ProcessFrame);
    private static async Task Pause(double seconds)
    { var start = Time.GetTicksMsec(); while (Time.GetTicksMsec() - start < seconds * 1000) await Frame(); }
    private static void Need(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
    private static async Task Until(Func<bool> condition, string label)
    { var start=Time.GetTicksMsec(); while(!condition()) { Need(Time.GetTicksMsec()-start<30000,"Timeout: "+label); await Frame(); } }
    private static IEnumerable<Node> Walk(Node node)
    { yield return node; foreach (var child in node.GetChildren()) foreach (var descendant in Walk(child)) yield return descendant; }
    private static object Rect(Control control)
    { var r=control.GetGlobalRect(); return new { x=r.Position.X,y=r.Position.Y,width=r.Size.X,height=r.Size.Y }; }
    private static object Image(string name)
    {
        string relative=name+".png", path=Path.Combine(directory,relative);
        Need(!System.IO.File.Exists(path),"Refuse to overwrite capture "+relative);
        using var image=Tree.Root.GetTexture().GetImage();
        Need(image is not null&&!image.IsEmpty(),"Missing actual viewport image");
        Need(image!.SavePng(path)==Error.Ok,"Viewport PNG write failed");
        return new { path=relative,width=image.GetWidth(),height=image.GetHeight(),at=Clock.Elapsed.TotalSeconds,origin="native-viewport" };
    }
    private static bool TweenFinished(Tween? tween) => tween is null || !tween.IsValid() || !tween.IsRunning();
    private static async Task View(CardModel card, bool upgraded, string kind)
    {
        NCard? node;
        if(kind=="large")
        {
            var inspect=NGame.Instance!.GetInspectCardScreen();inspect.Open([card],0);
            // A singleton inspect hides both navigation arrows. Their delayed 0.35s
            // tween is not visible; observe every visible endpoint and the real
            // card tween instead (0.25s). Never advance or kill native animations.
            var backstop=(CanvasItem)inspect.GetType().GetField("_backstop",Fields)!.GetValue(inspect)!;
            var left=(CanvasItem)inspect.GetType().GetField("_leftButton",Fields)!.GetValue(inspect)!;
            var right=(CanvasItem)inspect.GetType().GetField("_rightButton",Fields)!.GetValue(inspect)!;
            Need(!left.Visible&&!right.Visible,"Singleton inspect navigation must be hidden");
            await Until(()=>inspect.Modulate.A>=.999f&&backstop.Modulate.A>=.8999f&&
                TweenFinished((Tween?)inspect.GetType().GetField("_cardTween",Fields)!.GetValue(inspect)),"native visible inspect animation complete");
            node=Walk(inspect).OfType<NCard>().Single();
        }
        else
        {
            await Until(()=>NCard.FindOnTable(card) is { } current&&current.IsVisibleInTree()&&
                current.Modulate.A>=.999f&&TweenFinished(current.PlayPileTween),"native hand card ready");
            node=NCard.FindOnTable(card);
        }
        Need(node is not null&&node.IsVisibleInTree(),"Native card is not visible");
        await Tree.ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
        var textures=Walk(node!).OfType<TextureRect>().Where(n=>n.Texture is not null).Select(n=>new {
            node=n.GetPath().ToString(),resource=n.Texture!.ResourcePath,width=n.Texture.GetWidth(),height=n.Texture.GetHeight(),visible=n.IsVisibleInTree(),rect=Rect(n) }).ToArray();
        var labels=Walk(node!).OfType<RichTextLabel>().Select(n=>new {node=n.GetPath().ToString(),text=n.Text,visible=n.IsVisibleInTree(),rect=Rect(n)}).ToArray();
        var big=ResourceLoader.Load<Texture2D>(card.BetaPortraitPath)??throw new InvalidOperationException("Missing big portrait resource");
        Views.Add(new {code=card.GetType().Name.Replace("Volibear_",""),upgraded,kind,model=card.Id.Entry,
            bigResource=new {path=card.BetaPortraitPath,width=big.GetWidth(),height=big.GetHeight(),usedByNativeView=textures.Any(t=>t.visible&&t.resource==card.BetaPortraitPath)},
            level=card.CurrentUpgradeLevel,view=node!.GetPath().ToString(),sameModel=ReferenceEquals(node.Model,card),viewModel=node.Model?.Id.Entry,viewLevel=node.Model?.CurrentUpgradeLevel,textures,labels,
            screenshot=Image($"card-{card.GetType().Name}-{(upgraded?1:0)}-{kind}")});
        if(kind=="large")
        {
            var inspect=NGame.Instance!.GetInspectCardScreen();inspect.Close();
            await Until(()=>!inspect.Visible,"native inspect close complete");
        }
    }
    private static object? OwnerPresentation(Creature owner)
    {
        var room=typeof(VolibearPresentationBridge).GetField("_room",Fields)!.GetValue(null);
        if(room is null)return null;
        var owners=(IDictionary)room.GetType().GetField("_owners",Fields)!.GetValue(room)!;
        return owners[owner];
    }
    private static VolibearEffects? Effects(Creature owner)
    {
        var scope=OwnerPresentation(owner);
        return scope is null?null:(VolibearEffects)scope.GetType().GetField("_effects",Fields)!.GetValue(scope)!;
    }
    private static async Task CaptureDomainSpirit(Creature owner)
    {
        var scope=OwnerPresentation(owner)??throw new InvalidOperationException("Missing domain owner view");
        var type=scope.GetType();
        var visuals=type.GetField("_spiritVisuals",Fields)!.GetValue(scope) as Node2D;
        var sprite=type.GetField("_spiritSprite",Fields)!.GetValue(scope) as AnimatedSprite2D;
        var ring=type.GetField("_stormRing",Fields)!.GetValue(scope) as Node2D;
        var original=(Vector2)type.GetField("_spiritScale",Fields)!.GetValue(scope)!;
        Need(visuals is not null&&visuals.Scale.IsEqualApprox(original*1.22f),"Domain must enlarge authored foot-origin visuals");
        Need(sprite?.Material is ShaderMaterial material&&material.Shader.Code.Contains("tex.a * 0.84"),"Domain must use transparent spirit shader");
        Need(ring is not null&&ring.IsInsideTree()&&ring.GetChildren().OfType<Line2D>().Count()==6,"Domain must display six lightning arcs");
        var arc=ring!.GetChildren().OfType<Line2D>().Last();var before=arc.Points.ToArray();
        // Production geometry advances on its 0.2s timer, after ProcessFrame.
        // Observe an actual change rather than assuming a 0.25s wall-clock pause crossed that timer.
        ulong observationStart=Time.GetTicksMsec();int observedFrames=0;
        while(before.SequenceEqual(arc.Points)&&observedFrames<180&&Time.GetTicksMsec()-observationStart<5000)
        { await Frame();observedFrames++; }
        Need(!before.SequenceEqual(arc.Points),"Domain lightning must animate while active");
        Screens.Add(new {phase="domain-spirit",enlarged=true,transparentBlue=true,animatedRing=true,
            observedFrames,observationMs=Time.GetTicksMsec()-observationStart,screenshot=Image("domain-spirit-"+Tree.Root.Size.X)});
    }
    private static Node? EffectRoot(Creature owner)
    { var effects=Effects(owner);return effects is null?null:(Node)typeof(VolibearEffects).GetField("_root",Fields)!.GetValue(effects)!; }
    private static object? Anchor(Variant value)
    {
        var node=value.AsGodotObject() as CanvasItem;
        if(node is null||!GodotObject.IsInstanceValid(node))return null;
        NCard? card=null;for(Node? parent=node;parent is not null;parent=parent.GetParent())if(parent is NCard found){card=found;break;}
        return new {id=node.GetInstanceId(),path=node.GetPath().ToString(),visible=node.IsVisibleInTree(),x=node.GetGlobalTransformWithCanvas().Origin.X,y=node.GetGlobalTransformWithCanvas().Origin.Y,
            cardModel=card?.Model?.Id.Entry,cardLevel=card?.Model?.CurrentUpgradeLevel,cardCost=card?.Model?.EnergyCost.GetWithModifiers(CostModifiers.Local)};
    }
    private static void Drain()
    {
        if(capture is null)return;
        int available=capture.GetFramesAvailable();
        if(available>0)foreach(var sample in capture.GetBuffer(available)) { Pcm.Add(sample.X);Pcm.Add(sample.Y); }
        discarded=(long)capture.GetDiscardedFrames();
        Need(Pcm.Count < AudioServer.GetMixRate()*2*180,"Audio capture exceeded finite 180 second budget");
    }
    // Observe immediately after the production call returns as well as on frames.
    // On llvmpipe a short source can finish between two rendered frames; sampling
    // only then records a stopped node, not whether its original play succeeded.
    private static void ObserveEmission(VolibearEffects __instance)
    {
        if (!observing) return;
        try
        {
            var root=(Node)typeof(VolibearEffects).GetField("_root",Fields)!.GetValue(__instance)!;
            if(GodotObject.IsInstanceValid(root)&&root.IsInsideTree()) ObserveVoices(root);
        }
        catch(Exception error) { samplingError=error; }
    }
    private static HashSet<ulong> ObserveVoices(Node root)
    {
        var live=new HashSet<ulong>();
        foreach(var item in root.Get("_voices").AsGodotDictionary().Values)
        {
            var record=item.AsGodotDictionary();var player=record["node"].AsGodotObject() as AudioStreamPlayer;
            if(player is null||!GodotObject.IsInstanceValid(player))continue;
            var cue=record["cue"].AsGodotDictionary();ulong id=player.GetInstanceId();live.Add(id);
            if(!Voices.TryGetValue(id,out var row)) Voices.Add(id,row=new Voice {node=id,cue=cue["id"].AsString(),file=cue["file"].AsString(),phase=phase,first=Clock.Elapsed.TotalSeconds,bus=player.Bus.ToString(),volume=player.VolumeLinear,playing=player.Playing});
            row.last=Clock.Elapsed.TotalSeconds;row.volume=Math.Max(row.volume,player.VolumeLinear);
            row.playing |= player.Playing;
        }
        return live;
    }
    private static async Task Sample(Creature owner)
    {
        try
        {
            while(observing)
            {
                Drain();var live=new HashSet<ulong>();var visual=new List<object>();var root=EffectRoot(owner);
                if(root is not null&&GodotObject.IsInstanceValid(root)&&root.IsInsideTree())
                {
                    live=ObserveVoices(root);
                    foreach(var item in root.Get("_visuals").AsGodotDictionary().Values)
                    {
                        var record=item.AsGodotDictionary();var effect=record["effect"].AsGodotDictionary();var bundle=record["bundle"].AsGodotDictionary();
                        var anchors=bundle.Keys.Where(k=>bundle[k].VariantType==Variant.Type.Object).Select(k=>new {key=k.AsString(),node=Anchor(bundle[k])}).ToArray();
                        var sprite=(AnimatedSprite2D)record["node"].AsGodotObject();
                        visual.Add(new {id=sprite.GetInstanceId(),effect=effect["id"].AsString(),frame=sprite.Frame,animation=sprite.Animation.ToString(),anchors,
                            x=sprite.GlobalPosition.X,y=sprite.GlobalPosition.Y,visible=sprite.IsVisibleInTree()});
                    }
                }
                foreach(var voice in Voices.Values.Where(v=>v.ended is null&&!live.Contains(v.node)))voice.ended=Clock.Elapsed.TotalSeconds;
                var sprites=Walk(Tree.Root).OfType<AnimatedSprite2D>().Where(n=>n.SpriteFrames?.ResourcePath.Contains("VolibearArt",StringComparison.Ordinal)==true)
                    .Select(n=>new {id=n.GetInstanceId(),path=n.GetPath().ToString(),animation=n.Animation.ToString(),frame=n.Frame,playing=n.IsPlaying(),visible=n.IsVisibleInTree(),x=n.GlobalPosition.X,y=n.GlobalPosition.Y}).ToArray();
                Frames.Add(new {at=Clock.Elapsed.TotalSeconds,phase,pcmFrames=Pcm.Count/2,liveVoices=live.OrderBy(x=>x).ToArray(),visual,sprites});
                if(Clock.Elapsed.TotalSeconds-lastScreen>=.5)
                { lastScreen=Clock.Elapsed.TotalSeconds;Screens.Add(new {phase,screenshot=Image($"action-{Screens.Count:D4}")}); }
                await Frame();
            }
            Drain();
        }
        catch(Exception error){samplingError=error;observing=false;}
    }
    private static async Task<CardModel> Create(CombatState state,Player player,string code)
    {
        var card=state.CreateCard(ModelDb.AllCards.Single(c=>c.GetType().Name=="Volibear_"+code),player);
        await CardPileCmd.Add(card,PileType.Hand);return card;
    }
    private static async Task Paid(CardModel card,Creature? target,Player player,string label)
    {
        phase=label;await PlayerCmd.SetEnergy(20,player);await Pause(.3);
        var before=player.PlayerCombatState!.Energy;int cost=card.EnergyCost.GetWithModifiers(CostModifiers.Local);
        var action=new PlayCardAction(card,target);var events=new List<string>();
        action.BeforeExecuted+=_=>events.Add("before-executed");action.BeforeCancelled+=_=>events.Add("cancelled");action.AfterFinished+=_=>events.Add("after-finished");
        double start=Clock.Elapsed.TotalSeconds;
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
        await Until(()=>action.CompletionTask.IsCompleted,"paid "+label);await action.CompletionTask;
        if(action.Exception is not null)throw new InvalidOperationException("Native paid action failed",action.Exception);
        Actions.Add(new {phase=label,code=card.GetType().Name.Replace("Volibear_",""),start,end=Clock.Elapsed.TotalSeconds,cost,before,after=player.PlayerCombatState.Energy,
            type=action.GetType().Name,state=action.State.ToString(),sameCard=ReferenceEquals(action.NetCombatCard.ToCardModel(),card),events,pile=card.Pile?.Type.ToString()});
        await Pause(.9);
    }
    private static void Wav(string path,int rate)
    {
        using var stream=new FileStream(path,FileMode.CreateNew,System.IO.FileAccess.Write);using var writer=new BinaryWriter(stream);
        int bytes=checked(Pcm.Count*2);
        writer.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));writer.Write(36+bytes);writer.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt "));
        writer.Write(16);writer.Write((short)1);writer.Write((short)2);writer.Write(rate);writer.Write(rate*4);writer.Write((short)4);writer.Write((short)16);
        writer.Write(System.Text.Encoding.ASCII.GetBytes("data"));writer.Write(bytes);
        foreach(float sample in Pcm)writer.Write((short)Math.Clamp(Math.Round(sample*32767),short.MinValue,short.MaxValue));
    }
    private static JsonElement Manifest(string path)
    { using var file=Godot.FileAccess.Open(path,Godot.FileAccess.ModeFlags.Read)??throw new InvalidOperationException("Missing authored manifest "+path);using var document=JsonDocument.Parse(file.GetAsText());return document.RootElement.Clone(); }
    internal static void ValidateAudioEnvironment()
    {
        string mode=Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_MODE")??"all";
        if(mode=="cards")return;
        var saves=MegaCrit.Sts2.Core.Saves.SaveManager.Instance;
        var settings=saves.SettingsSave;
        bool focused=DisplayServer.WindowIsFocused();
        bool muteInBackground=saves.PrefsSave.MuteInBackground;
        string driver=AudioServer.GetDriverName();
        bool busMuted=AudioServer.IsBusMute(0);
        GD.Print("[Volibear] PRESENTATION_AUDIO_PREFLIGHT "+JsonSerializer.Serialize(new {
            token=Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN"),driver,
            display=DisplayServer.GetName(),windowFocused=focused,muteInBackground,busMuted,
            master=settings.VolumeMaster,sfx=settings.VolumeSfx,ambience=settings.VolumeAmbience,
            forcedUnmute=false
        }));
        Need(!driver.Contains("Dummy",StringComparison.OrdinalIgnoreCase),"Dummy audio cannot prove playback");
        Need(!busMuted,"Master audio bus muted; probe never forces unmute");
        Need(focused||!muteInBackground,"Background audio muted in isolated profile; configure prefs before launching");
        Need(float.IsFinite(settings.VolumeMaster)&&settings.VolumeMaster>0&&
             float.IsFinite(settings.VolumeSfx)&&settings.VolumeSfx>0&&
             float.IsFinite(settings.VolumeAmbience)&&settings.VolumeAmbience>0,
             "Native audio sliders must permit source playback before acceptance");
    }
    internal static async Task Run(CombatState state, bool managed = false)
    {
        var originalSize=Tree.Root.Size;
        Views.Clear();Actions.Clear();Frames.Clear();Screens.Clear();Pcm.Clear();Voices.Clear();
        sampling=null;samplingError=null;discarded=0;lastScreen=0;capture=null;captureIndex=-1;Clock.Restart();
        try
        {
            token=Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN")??"";
            string mode=Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_MODE")??"all";
            Need(mode is "all" or "cards" or "actions","Unknown presentation mode");
            Need(!string.IsNullOrWhiteSpace(token),"Missing token");
            directory=Path.GetFullPath(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_PRESENTATION_OUTPUT")??throw new InvalidOperationException("Missing isolated artifact directory"));
            Directory.CreateDirectory(directory);
            Need(DisplayServer.GetName()!="headless"&&!MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,"Real rendered viewport required");
            var release=ReleaseInfoManager.Instance.ReleaseInfo!;
            Need(release.Version==global::Volibear.Core.SupportedGameBuild.Version&&release.Commit==global::Volibear.Core.SupportedGameBuild.Commit,"Pinned game version required");
            ValidateAudioEnvironment();
            Clock.Start();var player=state.Players.Single();var owner=player.Creature;
            await Until(()=>player.PlayerCombatState!.Phase==PlayerTurnPhase.Play&&Effects(owner) is not null,"native play/presentation attach");
            foreach(var card in player.PlayerCombatState!.Hand.Cards.ToArray())await CardPileCmd.Add(card,PileType.Discard);
            if(mode is "all" or "cards")
            {
                phase="catalog";var catalog=ModelDb.AllCards.OfType<VolibearCard>().OrderBy(c=>c.Key,StringComparer.Ordinal).ToArray();Need(catalog.Length==89,"Exact 89 canonical cards required");
                foreach(var canonical in catalog)
                {
                    var paths=canonical.RunAssetPaths.Except(PreloadManager.Cache.GetLoadedCacheAssets());
                    Need(await NAssetLoader.Instance.LoadInTheBackground(PreloadManager.Cache.CreateSession("Presentation catalog",paths)),"Card asset preload failed");
                    var card=state.CreateCard(canonical,player);await CardPileCmd.Add(card,PileType.Hand);
                    foreach(bool upgraded in new[]{false,true}) { if(upgraded)CardCmd.Upgrade(card);await View(card,upgraded,"small");await View(card,upgraded,"large"); }
                    await CardPileCmd.Add(card,PileType.Discard);
                }
            }
            string driver=AudioServer.GetDriverName();
            object? audio=null;object? cleanup=null;
            if(mode is "all" or "actions")
            {
                Need(!driver.Contains("Dummy",StringComparison.OrdinalIgnoreCase),"Dummy audio cannot prove playback");
                Need(!AudioServer.IsBusMute(0),"Master audio bus muted; probe never forces unmute");
                capture=new AudioEffectCapture {BufferLength=4};captureIndex=AudioServer.GetBusEffectCount(0);AudioServer.AddBusEffect(0,capture,captureIndex);
                var observer=new Harmony("Volibear.PresentationAcceptance.AudioObserver");
                foreach(string method in new[]{nameof(VolibearEffects.Emit),nameof(VolibearEffects.PlaySound)})
                    observer.Patch(AccessTools.Method(typeof(VolibearEffects),method),postfix:new HarmonyMethod(typeof(PresentationAcceptanceProbe),nameof(ObserveEmission)));
                observing=true;sampling=Sample(owner);
                foreach(var enemy in state.Enemies.ToArray())await CreatureCmd.SetMaxAndCurrentHp(enemy,1000);
                await CreatureCmd.SetMaxAndCurrentHp(owner,1000);
                foreach(var size in new[]{new Vector2I(1280,720),new Vector2I(1920,1080)})
                {
                    Tree.Root.Size=size;phase=$"resolution-{size.X}x{size.Y}";await Pause(.7);
                    Screens.Add(new {phase,screenshot=Image(phase)});
                    foreach(string code in new[]{"B01","B02","B03","B04","C03","C05"})
                    {var card=await Create(state,player,code);await Paid(card,card.TargetType==TargetType.AnyEnemy?state.Enemies.First():null,player,$"{size.X}-{code}");}
                    await CaptureDomainSpirit(owner);
                }
                // R29 converts every eligible hand card, including cards drawn by earlier
                // demonstrations. Isolate the two intended materials using native pile moves.
                foreach(var leftover in player.PlayerCombatState!.Hand.Cards.ToArray())
                    await CardPileCmd.Add(leftover,PileType.Discard);
                var clawMaterial=await Create(state,player,"B01");var bodyMaterial=await Create(state,player,"B02");
                await Paid(await Create(state,player,"R29"),null,player,"beast-convert");
                var claw=player.PlayerCombatState!.Hand.Cards.OfType<Volibear_T01>().Single();
                var body=player.PlayerCombatState.Hand.Cards.OfType<Volibear_T02>().Single();
                Need(clawMaterial.Pile?.Type==PileType.Exhaust&&bodyMaterial.Pile?.Type==PileType.Exhaust&&
                    !ReferenceEquals(clawMaterial,claw)&&!ReferenceEquals(bodyMaterial,body)&&claw.DeckVersion is null&&body.DeckVersion is null,
                    "Beast action must exhaust materials and generate new native token identities");
                await Paid(claw,state.Enemies.First(),player,"converted-claw");await Paid(body,null,player,"converted-body");
                phase="native-combat-end";var effects=Effects(owner);var root=EffectRoot(owner);
                int beforeVisuals=effects?.ActiveVisuals??0,beforeVoices=effects?.ActiveVoices??0;
                var spiritScope=OwnerPresentation(owner)!;
                var spiritType=spiritScope.GetType();
                var spiritVisuals=(Node2D?)spiritType.GetField("_spiritVisuals",Fields)!.GetValue(spiritScope);
                var spiritSprite=(AnimatedSprite2D?)spiritType.GetField("_spiritSprite",Fields)!.GetValue(spiritScope);
                var spiritOriginalScale=(Vector2)spiritType.GetField("_spiritScale",Fields)!.GetValue(spiritScope)!;
                var spiritOriginalMaterial=(Material?)spiritType.GetField("_spiritMaterial",Fields)!.GetValue(spiritScope);
                foreach(var enemy in state.Enemies.ToArray())await CreatureCmd.Kill(enemy,force:true);
                // These fixture kills run outside the action executor. Native Kill
                // does not check victory; invoke its normal completion safe point so
                // the native CombatEnded event (not direct disposal) releases ownership.
                Need(await CombatManager.Instance.CheckWinCondition(),"Native victory after last enemy death");
                await Until(()=>Effects(owner) is null && (root is null || !GodotObject.IsInstanceValid(root) || !root.IsInsideTree()),"native combat-end owned node cleanup");
                Need(spiritType.GetField("_stormRing",Fields)!.GetValue(spiritScope) is null,"Combat end must release domain ring ownership");
                if(spiritVisuals is not null&&GodotObject.IsInstanceValid(spiritVisuals))
                    Need(spiritVisuals.Scale.IsEqualApprox(spiritOriginalScale),"Combat end must restore original actor scale");
                if(spiritSprite is not null&&GodotObject.IsInstanceValid(spiritSprite))
                    Need(spiritSprite.Material==spiritOriginalMaterial,"Combat end must restore original actor material");
                cleanup=new {cause="native-last-enemy-death",beforeVisuals,beforeVoices,afterVisuals=effects?.ActiveVisuals??0,afterVoices=effects?.ActiveVoices??0,
                    oldRootAlive=root is not null&&GodotObject.IsInstanceValid(root)&&root.IsInsideTree(),roomAttached=Effects(owner) is not null};
                observing=false;await sampling;
                if(samplingError is not null)throw new InvalidOperationException("Capture failed",samplingError);
                int rate=(int)AudioServer.GetMixRate();Wav(Path.Combine(directory,"game-bus.wav"),rate);
                audio=new {driver,bus="Master",origin="this-process-Godot-AudioServer",channels=2,sampleRate=rate,frames=Pcm.Count/2,
                    discardedFrames=discarded,wav="game-bus.wav",peak=Pcm.Count==0?0:Pcm.Max(x=>Math.Abs(x)),rms=Pcm.Count==0?0:Math.Sqrt(Pcm.Sum(x=>(double)x*x)/Pcm.Count),
                    forcedUnmute=false,systemCapture=false,heard=false,voices=Voices.Values.ToArray()};
            }
            GD.Print("[Volibear] PRESENTATION_ACCEPTANCE_RESULT "+JsonSerializer.Serialize(new {schema=1,token,mode,version=release.Version,commit=release.Commit,
                acceptance="native-viewport-paid-actions-game-bus-pcm-not-sensory-or-full-G5",osInput=false,syntheticScreenshots=false,directCosmeticPlayback=false,
                display=DisplayServer.GetName(),views=Views,actions=Actions,frames=Frames,screens=Screens,audio,cleanup,
                authoredEffects=Manifest("res://VolibearArt/vfx/manifest.json"),authoredAudio=Manifest("res://VolibearArt/audio/manifest.json"),
                audioProfile=Manifest("res://VolibearArt/audio/profiles/runtime.json"),
                primitiveRoutes=VolibearPresentationBridge.PrimitiveRoutes,
                matrix=Enumerable.Range(1,10).Select(i=>new {id=$"V{i:D2}",status=i==9?"NOTRUN":i==1?(mode=="actions"?"NOTRUN":"captured-awaiting-manual-review"):i==5?"inventory-only":mode=="cards"?"NOTRUN":"partial-evidence-manual-review-required"}).ToArray(),
                manualReviewRequired=new[]{"readability/crop/black-background/occlusion/flicker","animation continuity and aesthetics","heard loudness/mix/synchronization",
                    "remaining animation/VFX/cue routes","selection/map/rest/merchant/trail normal progression","return-to-menu/cancellation"}}));
            if (!managed) { GD.Print("[Volibear] SHUTDOWN_BEGIN "+token);NGame.Instance!.Quit();Tree.Quit(0); }
        }
        catch(Exception error){GD.PrintErr("[Volibear] PRESENTATION_ACCEPTANCE_ERROR "+token+" "+error);if(managed)throw;Tree.Quit(2);}
        finally
        {
            observing=false;
            new Harmony("Volibear.PresentationAcceptance.AudioObserver").UnpatchAll("Volibear.PresentationAcceptance.AudioObserver");
            if(sampling is not null)await sampling;
            if(captureIndex>=0&&capture is not null&&AudioServer.GetBusEffectCount(0)>captureIndex&&AudioServer.GetBusEffect(0,captureIndex)==capture)AudioServer.RemoveBusEffect(0,captureIndex);
            capture?.Dispose();Tree.Root.Size=originalSize;
        }
    }
}
