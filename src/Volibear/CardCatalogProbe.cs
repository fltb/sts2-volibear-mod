using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;

namespace Volibear;

/// <summary>Raw native catalog observations, not a gameplay/payment acceptance test.
/// Expected IDs/text/numbers are deliberately absent; the external independent fixture
/// comparator owns the verdict. This probe must be opt-in through the isolated runner.</summary>
internal static class CardCatalogProbe
{
    private static bool _started;
    public static void Install() => CombatManager.Instance.TurnStarted += OnTurnStarted;

    private static void OnTurnStarted(CombatState combat)
    {
        if (_started) return;
        _started = true;
        CombatManager.Instance.TurnStarted -= OnTurnStarted;
        try { Run(combat); }
        catch (Exception error)
        {
            GD.PrintErr("[Volibear] CATALOG_PROBE_ERROR " + error);
            ((SceneTree)Engine.GetMainLoop()).Quit(2);
        }
    }

    private static object Portrait(string path)
    {
        var exists = ResourceLoader.Exists(path);
        if (!exists) return new { path, exists, decoded = false, width = 0, height = 0, error = "ResourceLoader.Exists=false" };
        try
        {
            // GetImage forces the mounted/imported texture to provide decoded pixels.
            // Do not alter source images or trust paths/manifest dimensions as evidence.
            var texture = ResourceLoader.Load<Texture2D>(path);
            if (texture is null) throw new InvalidOperationException("Resource is not a Texture2D");
            using var image = texture.GetImage();
            var width = image?.GetWidth() ?? 0;
            var height = image?.GetHeight() ?? 0;
            var decoded = image is not null && !image.IsEmpty() && image.GetData().Length > 0;
            return new { path, exists, decoded, width, height, error = (string?)null };
        }
        catch (Exception error) { return new { path, exists, decoded = false, width = 0, height = 0, error = error.ToString() }; }
    }

    private static object Text(CardModel card) => new
    {
        titleKey = card.Id.Entry + ".title", descriptionKey = card.Id.Entry + ".description",
        titleExists = LocString.Exists("cards", card.Id.Entry + ".title"),
        descriptionExists = LocString.Exists("cards", card.Id.Entry + ".description"),
        rawTitle = card.TitleLocString.GetRawText(), rawDescription = card.Description.GetRawText(),
        title = card.Title, description = card.GetDescriptionForPile(PileType.None),
    };

    private static object Face(CardModel card, Player owner, string[] initialKeywords) => new
    {
        modelId = card.Id.Entry, nativeType = card.GetType().FullName,
        cardRef = RuntimeHelpers.GetHashCode(card), ownerRef = RuntimeHelpers.GetHashCode(card.Owner),
        ownerMatches = ReferenceEquals(card.Owner, owner), mutable = card.IsMutable,
        upgrade = card.IsUpgraded, upgradeLevel = card.CurrentUpgradeLevel,
        type = card.Type.ToString(), rarity = card.Rarity.ToString(), target = card.TargetType.ToString(),
        initialKeywords, keywords = card.Keywords.Select(x => x.ToString()).Order().ToArray(),
        costsX = card.EnergyCost.CostsX, canonicalCost = card.EnergyCost.Canonical,
        localCost = card.EnergyCost.GetWithModifiers(CostModifiers.Local),
        allCost = card.EnergyCost.GetWithModifiers(CostModifiers.All),
        vars = card.DynamicVars.ToDictionary(pair => pair.Key, pair => new
        {
            kind = pair.Value.GetType().Name, baseValue = pair.Value.BaseValue,
            enchantedValue = pair.Value.EnchantedValue, previewValue = pair.Value.PreviewValue,
        }),
        text = Text(card),
    };

    private static void Run(CombatState combat)
    {
        var token = System.Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN");
        if (string.IsNullOrWhiteSpace(token) || MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn)
            throw new InvalidOperationException("Catalog probe requires a current isolated run token and TestMode=false.");
        var owner = combat.Players.Single();
        var deckBefore = owner.Deck.Cards.Select(card => card.Id.Entry).ToArray();
        var energyBefore = owner.PlayerCombatState!.Energy;
        var registered = AccessTools.Field(typeof(ModelDb), "_contentById").GetValue(null)
            as Dictionary<ModelId, AbstractModel> ?? throw new InvalidOperationException("Native ModelDb registry drifted.");
        var models = registered.Values.OfType<VolibearCard>()
            .Where(card => card.GetType().Assembly == typeof(VolibearCard).Assembly)
            .OrderBy(card => card.Id.Entry).ToArray();
        var pool = ModelDb.CardPool<VolibearCardPool>();
        var poolCards = pool.AllCards.ToArray();
        var registry = models.Select(card => new
        {
            modelId = card.Id.Entry, nativeType = card.GetType().FullName,
            canonical = card.IsCanonical,
            resolvedSame = ReferenceEquals(ModelDb.GetById<CardModel>(card.Id), card),
            inPool = poolCards.Any(candidate => ReferenceEquals(candidate, card)),
            rarity = card.Rarity.ToString(), type = card.Type.ToString(),
        }).ToArray();
        var portraits = models.Select(card => new
        {
            modelId = card.Id.Entry, small = Portrait(card.PortraitPath), big = Portrait(card.BetaPortraitPath),
        }).ToArray();
        var startLanguage = LocManager.Instance.Language;
        LocManager.Instance.SetLanguage("zhs");
        var cards = new List<CardModel>();
        var faces = new List<object>();
        var errors = new List<string>();
        foreach (var canonical in models)
        {
            foreach (var upgraded in new[] { false, true })
            {
                try
                {
                    var card = combat.CreateCard(ModelDb.GetById<CardModel>(canonical.Id), owner);
                    // Required cache regression: read the native Keywords set BEFORE
                    // native upgrade of this same mutable instance (C14/U14 Exhaust).
                    var initialKeywords = card.Keywords.Select(keyword => keyword.ToString()).Order().ToArray();
                    _ = card.Title;
                    _ = card.GetDescriptionForPile(PileType.None);
                    if (upgraded) CardCmd.Upgrade(card);
                    cards.Add(card);
                    faces.Add(Face(card, owner, initialKeywords));
                }
                catch (Exception error) { errors.Add(canonical.Id.Entry + (upgraded ? "+" : "") + ": " + error); }
            }
        }
        // Do not call VolibearLoc.Install/remerge test strings here. Only native
        // language reload + the installed production GetTable patch may repair keys.
        LocManager.Instance.SetLanguage("eng");
        LocManager.Instance.SetLanguage("zhs");
        var reloaded = new List<object>();
        foreach (var card in cards)
        {
            try { reloaded.Add(new { modelId = card.Id.Entry, upgrade = card.IsUpgraded, text = Text(card) }); }
            catch (Exception error) { errors.Add(card.Id.Entry + " reload: " + error); }
        }
        var release = ReleaseInfoManager.Instance.ReleaseInfo
            ?? throw new InvalidOperationException("No actual game release metadata.");
        var result = new
        {
            gameVersion = release.Version, gameCommit = release.Commit,
            schemaVersion = 1, token, scenario = "catalog", acceptance = "catalog-not-gameplay-or-payment",
            completed = errors.Count == 0, testMode = MegaCrit.Sts2.Core.TestSupport.TestMode.IsOn,
            discovery = "ModelDb._contentById;ModelDb.GetById;CustomCardPoolModel.AllCards",
            api = "CombatState.CreateCard;CardModel.Keywords;CardCmd.Upgrade;LocManager.SetLanguage;ResourceLoader.Load<Texture2D>;Texture2D.GetImage",
            startLanguage, language = LocManager.Instance.Language, reloadSequence = new[] { "zhs", "eng", "zhs" },
            ownerRef = RuntimeHelpers.GetHashCode(owner), character = owner.Character.GetType().Name,
            ownerPowerCount = owner.Creature.Powers.Count(), energyBefore, energyAfter = owner.PlayerCombatState!.Energy,
            deckBefore, deckAfter = owner.Deck.Cards.Select(card => card.Id.Entry).ToArray(),
            registry, poolIds = poolCards.Select(card => card.Id.Entry).Order().ToArray(),
            rarityCounts = poolCards.GroupBy(card => card.Rarity.ToString()).ToDictionary(group => group.Key, group => group.Count()),
            faces, portraits, reloaded, errors,
        };
        GD.Print("[Volibear] CATALOG_RESULT " + JsonSerializer.Serialize(result));
        GD.Print("[Volibear] SHUTDOWN_BEGIN " + token);
        MegaCrit.Sts2.Core.Nodes.NGame.Instance!.Quit();
        ((SceneTree)Engine.GetMainLoop()).Quit(errors.Count == 0 ? 0 : 2);
    }
}
