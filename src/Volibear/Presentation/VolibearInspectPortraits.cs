using System;
using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using Volibear.Content;

namespace Volibear.Presentation;

/// <summary>Normal native Inspect only: replace the visible portrait texture after native
/// clone/text/upgrade rendering. Never alter a CardModel, BetaArt preference, hand view or other mod.</summary>
public static class VolibearInspectPortraits
{
    private const string Owner="Volibear.Presentation.InspectPortraits";
    private static readonly FieldInfo Card=AccessTools.Field(typeof(NInspectCardScreen),"_card")??throw new MissingFieldException("NInspectCardScreen._card");
    private static readonly FieldInfo Portrait=AccessTools.Field(typeof(NCard),"_portrait")??throw new MissingFieldException("NCard._portrait");
    private static bool installed;
    public static void Install()
    {
        if(installed)return;
        if(Card.FieldType!=typeof(NCard)||Portrait.FieldType!=typeof(TextureRect))throw new InvalidOperationException("Pinned native Inspect portrait fields changed");
        var target=AccessTools.DeclaredMethod(typeof(NInspectCardScreen),"UpdateCardDisplay",Type.EmptyTypes)
            ??throw new MissingMethodException("NInspectCardScreen.UpdateCardDisplay");
        if(target.ReturnType!=typeof(void))throw new InvalidOperationException("Pinned native Inspect return changed");
        var harmony=new Harmony(Owner);
        try { harmony.Patch(target,postfix:new HarmonyMethod(typeof(VolibearInspectPortraits),nameof(AfterDisplay)));installed=true; }
        catch { harmony.UnpatchAll(Owner);throw; }
    }
    private static void AfterDisplay(NInspectCardScreen __instance)
    {
        if(Card.GetValue(__instance) is not NCard view||view.Model is not VolibearCard card)return;
        // Explicit approved large portrait directory, NOT the user's beta-art setting.
        string path=$"{VolibearCard.BigPortraitRoot}/{card.Key}.png";
        var texture=ResourceLoader.Load<Texture2D>(path)??throw new InvalidOperationException("Missing approved Inspect portrait: "+path);
        if(Portrait.GetValue(view) is not TextureRect portrait)throw new InvalidOperationException("Native Inspect portrait node missing");
        portrait.Texture=texture;
    }
}
