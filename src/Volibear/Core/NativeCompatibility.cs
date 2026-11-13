using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace Volibear.Core;

/// <summary>
/// Structural self-check for game builds other than the acceptance-tested one. It resolves the
/// native types and members this mod actually patches or reads at runtime; when the surface is
/// present the mod may load on a newer build with an "unverified" note, otherwise initialization
/// stops before any Harmony patch is applied. Reflection only: no game assembly is referenced here.
/// </summary>
public static class NativeCompatibility
{
    private static readonly (string Type, string[] Members)[] Surface =
    {
        ("PowerModel", new[] { "Amount", "Owner", "HoverTips", "Icon", "Title", "DisplayAmount", "SetAmount", "Flash", "IsVisible" }),
        ("AbstractModel", new[] { "IsMutable", "Id", "AfterDeath", "ModifyBlockMultiplicative", "ModifyDamageMultiplicative", "ShouldCreatureBeRemovedFromCombatAfterDeath" }),
        ("CardModel", new[] { "HoverTips", "Pile", "Keywords", "CanPlay", "CanPlayTargeting", "CurrentUpgradeLevel", "SpendResources", "OnPlayWrapper", "OnTurnEndInHandWrapper" }),
        ("MonsterModel", new[] { "_creature", "NextMove", "MoveStateMachine", "PerformMove", "SetMoveImmediate" }),
        ("Creature", new[] { "Powers", "GetPowerAmount", "GetPower", "HoverTips", "Block", "ClearBlock", "ApplyPowerInternal", "CanReceivePowers", "CurrentHp", "MaxHp" }),
        ("Player", new[] { "Creature", "PlayerCombatState" }),
        ("PlayerCombatState", new[] { "Energy", "MaxEnergy", "Hand", "AllCards", "AllPiles" }),
        ("CombatState", new[] { "Players", "Enemies", "RoundNumber", "CurrentSide" }),
        ("CombatManager", new[] { "Instance", "StateTracker", "IsInProgress", "Reset", "DoTurnEnd" }),
        ("Hook", new[] { "ModifyHandDraw", "ModifyMaxEnergy", "ShouldDraw", "AfterEnergySpent", "ModifyBlock", "ModifyDamageInternal" }),
        ("PowerCmd", new[] { "Apply", "Remove" }),
        ("CardCmd", new[] { "Upgrade", "AutoPlay" }),
        ("CreatureCmd", new[] { "GainBlock", "Heal", "Kill", "SetMaxAndCurrentHp", "SetCurrentHp", "SetMaxHp", "Damage", "KillWithoutCheckingWinCondition" }),
        ("Cmd", new[] { "CustomScaledWait" }),
        ("RunManager", new[] { "Instance", "IsInProgress", "WinRun", "DebugOnlyGetState", "GuaranteeKillAllPlayers" }),
        ("RunState", new[] { "CurrentRoom", "Players" }),
        ("ModelDb", new[] { "_contentById" }),
        ("MoveState", new[] { "_onPerform" }),
        ("AttackCommand", new[] { "_calculatedDamageVar", "Execute" }),
        ("CardEnergyCost", new[] { "_localModifiers", "GetAmountToSpend", "GetWithModifiers", "SetThisCombat" }),
        ("PlayCardAction", new[] { "ExecuteAction", "BeforeExecuted", "AfterFinished", "BeforeCancelled" }),
        ("NPower", new[] { "_model", "Model", "_Ready", "OnHovered", "OnUnhovered", "RefreshAmount", "ShowPowerHoverTips" }),
        ("NPowerContainer", new[] { "_powerNodes", "UpdatePositions" }),
        ("NCreature", new[] { "_Ready", "Hitbox", "IntentContainer", "ShowHoverTips", "HideHoverTips" }),
        ("NCombatRoom", new[] { "Instance", "GetCreatureNode" }),
        ("NInspectCardScreen", new[] { "UpdateCardDisplay", "_card" }),
        ("NCharacterSelectScreen", new[] { "_bgContainer" }),
        ("NCard", new[] { "_portrait", "_previewTarget" }),
        ("WaterfallGiant", new[] { "AboutToBlowMove", "ExplodeMove", "IncrementBuildUpAnimationTrack", "StopAmbientSfx", "PressureBuildupIdx", "SteamEruptionDamage" }),
        ("ReattachPower", new[] { "AreAllOtherSegmentsDead", "IsReviving" }),
        ("IllusionPower", new[] { "ReviveMove" }),
        ("DecimillipedeSegment", new[] { "ChangePhobiaModeTexture", "ReattachMove" }),
        ("ToughEgg", new[] { "Hatch" }),
        ("TestSubject", new[] { "SetColor" }),
        ("MagiKnight", new[] { "DampenMove" }),
        ("AdaptablePower", new[] { "IsReviving" }),
        ("ChainsOfBindingPower", new[] { "ShouldPlay" }),
        ("ConfusedPower", new[] { "AfterCardDrawn" }),
        ("Aeonglass", new[] { "WitherUpgradeCount" }),
        ("BarricadePower", new[] { "ShouldClearBlock" }),
        ("BlurPower", new[] { "ShouldClearBlock" }),
        ("CustomPowerModel", Array.Empty<string>()),
        ("CustomCardModel", Array.Empty<string>()),
    };

    private static Dictionary<string, Type?>? resolved;

    /// <summary>Throws with the first missing native members when the current build cannot host the mod.</summary>
    public static void Verify() => Verify(typeof(NativeCompatibility).Assembly);

    internal static void Verify(Assembly mod)
    {
        var missing = new List<string>();
        foreach (var (type, members) in Surface)
        {
            var found = Resolve(type);
            if (found is null)
            {
                missing.Add("type " + type);
                continue;
            }
            foreach (var member in members)
                if (!HasMember(found, member)) missing.Add(type + "." + member);
        }
        CheckOverrides(mod, missing);
        if (missing.Count == 0) return;
        throw new InvalidOperationException(string.Join("; ", missing.Take(24)) +
            (missing.Count > 24 ? $"; +{missing.Count - 24} more" : string.Empty));
    }

    private static void CheckOverrides(Assembly mod, List<string> missing)
    {
        try { _ = mod.GetTypes(); }
        catch (ReflectionTypeLoadException error)
        {
            missing.AddRange(error.LoaderExceptions.OfType<Exception>().Select(e => e.Message).Distinct());
        }

        // A method with the same name can change signature. A precompiled virtual method
        // can then load as a new slot without ever receiving the native death event.
        var model = Resolve("AbstractModel");
        var choice = Resolve("PlayerChoiceContext");
        var creature = Resolve("Creature");
        var card = Resolve("CardModel");
        if (model is null || choice is null || creature is null || card is null)
        {
            missing.Add("AfterDeath parameter types");
            return;
        }
        var domain = mod.GetType("Volibear.Core.DomainPower", throwOnError: false);
        var death = domain?.GetMethod("AfterDeath", BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
        var hook = death?.GetBaseDefinition();
        if (death is null || hook?.DeclaringType != model || hook.ReturnType != typeof(System.Threading.Tasks.Task))
            missing.Add("DomainPower.AfterDeath override of AbstractModel.AfterDeath");
        else
        {
            var native = model.GetMethod("AfterDeath", death.GetParameters().Select(p => p.ParameterType).ToArray());
            if (native != hook) missing.Add("AbstractModel.AfterDeath signature");
        }
    }

    private static bool HasMember(Type type, string name)
    {
        const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance |
                                   BindingFlags.Static | BindingFlags.DeclaredOnly;
        for (Type? current = type; current is not null; current = current.BaseType)
        {
            if (current.GetMethods(flags).Any(m => m.Name == name) ||
                current.GetProperties(flags).Any(p => p.Name == name) ||
                current.GetFields(flags).Any(f => f.Name == name) ||
                current.GetEvents(flags).Any(e => e.Name == name)) return true;
        }
        return false;
    }

    private static Type? Resolve(string simpleName)
    {
        resolved ??= BuildIndex();
        return resolved.TryGetValue(simpleName, out var type) ? type : null;
    }

    private static Dictionary<string, Type?> BuildIndex()
    {
        var index = new Dictionary<string, Type?>(StringComparer.Ordinal);
        foreach (var name in new[] { "sts2", "BaseLib" })
        {
            Assembly? assembly;
            try { assembly = Assembly.Load(new AssemblyName(name)); }
            catch (Exception) { continue; }
            Type[] types;
            try { types = assembly.GetTypes(); }
            catch (ReflectionTypeLoadException error) { types = error.Types.Where(t => t is not null).Cast<Type>().ToArray(); }
            catch (Exception) { continue; }
            foreach (var type in types)
            {
                // Metadata of a single broken type must not kill the whole gate.
                try
                {
                    if (type.Namespace is not { } space) continue;
                    if (!space.StartsWith("MegaCrit.Sts2", StringComparison.Ordinal) &&
                        !space.StartsWith("BaseLib", StringComparison.Ordinal)) continue;
                    if (type.IsGenericTypeDefinition || index.ContainsKey(type.Name)) continue;
                    index[type.Name] = type;
                }
                catch (Exception) { }
            }
        }
        return index;
    }
}
