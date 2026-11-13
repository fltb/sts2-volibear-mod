using System;
using System.Linq;
using System.Runtime.CompilerServices;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.CharacterSelect;
using Volibear.Content;

namespace Volibear.Presentation;

/// <summary>Approved noncombat one-shots from actual local selection / CombatWon events.
/// Uses the existing effects/audio controller, game gains and native player lifetime.</summary>
public static class VolibearPresentationCues
{
    private static bool installed;
    private static readonly ConditionalWeakTable<Node, CueScope> Active = new();
    private static readonly ConditionalWeakTable<ICombatState, object> Won = new();
    public static void Install()
    {
        if(installed)return;
        var target=AccessTools.Method(typeof(NCharacterSelectScreen),nameof(NCharacterSelectScreen.SelectCharacter),
            [typeof(NCharacterSelectButton)
#if !STS2_BETA
            , typeof(CharacterModel)
#endif
            ])??throw new MissingMethodException("Native SelectCharacter");
        new Harmony("Volibear.Presentation.NativeStateCues").Patch(target,
            postfix:new HarmonyMethod(typeof(VolibearPresentationCues),nameof(Selected)));
        CombatManager.Instance.CombatWon += endedRoom => Safe(() =>
        {
            var state=CombatManager.Instance.DebugOnlyGetState();
            if(state is null || LocalContext.GetMe(state) is not { Character: VolibearCharacter } player || !player.Creature.IsAlive ||
                NCombatRoom.Instance is not { } room || Won.TryGetValue(state,out _))return;
            Won.Add(state,new object());
            // CombatEnded immediately closes combat effects; this one-shot belongs to the still-visible room.
            Play(room,"voice.victory");
        });
        installed=true;
    }
    private static void Selected(NCharacterSelectScreen __instance,NCharacterSelectButton charSelectButton
#if !STS2_BETA
        , CharacterModel characterModel
#endif
        ) => Safe(() =>
    {
#if STS2_BETA
        var characterModel = charSelectButton.Character;
#endif
        if(characterModel is not VolibearCharacter || charSelectButton.IsLocked || charSelectButton.IsRandom)return;
        var container=(Node?)AccessTools.Field(typeof(NCharacterSelectScreen),"_bgContainer")?.GetValue(__instance);
        var background=container?.GetChildren().SingleOrDefault(n=>n.Name.ToString()==characterModel.Id.Entry+"_bg");
        if(background is not null && background.IsInsideTree())Play(background,"voice.select");
    });
    private static void Safe(Action callback)
    {try{callback();}catch(Exception error){GD.PushWarning("[Volibear presentation:native_state_cue] "+error.Message);}}
    private static void Play(Node parent,string cue)
    {
        if(!GodotObject.IsInstanceValid(parent)||!parent.IsInsideTree()||parent.IsQueuedForDeletion())return;
        if(Active.TryGetValue(parent,out var old))old.Stop();
        var scope=new CueScope(parent);Active.Add(parent,scope);scope.Play(cue);
    }
    private sealed class CueScope
    {
        private readonly Node parent,container;
        private readonly VolibearEffects effects;
        private bool stopped;
        internal CueScope(Node parent)
        {
            this.parent=parent;container=new Node {Name="VolibearNativeStateCue"};parent.AddChild(container);
            effects=VolibearEffects.Attach(container,$"scene:{parent.GetInstanceId()}","local-volibear");
            parent.TreeExiting+=Stop;
        }
        internal void Play(string cue)
        {
            if(!effects.PlaySound($"native:{cue}:{parent.GetInstanceId()}",cue,leaseSeconds:10)){Stop();return;}
            // No settlement timer: actual AudioStreamPlayer completion/removal owns cleanup.
            var players=container.FindChildren("*","AudioStreamPlayer",recursive:true,owned:false).OfType<AudioStreamPlayer>().ToArray();
            if(players.Length==0){Stop();return;}
            foreach(var player in players){player.Finished+=Stop;player.TreeExiting+=Stop;}
        }
        internal void Stop()
        {
            if(stopped)return;stopped=true;
            Active.Remove(parent);
            if(GodotObject.IsInstanceValid(parent))parent.TreeExiting-=Stop;
            effects.Dispose();
            if(GodotObject.IsInstanceValid(container))container.QueueFree();
        }
    }
}
