using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;
using BaseLib.Abstracts;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Volibear.Content;
using Volibear.Presentation;

namespace Volibear;

/// <summary>
/// Finite character integration checks in the existing isolated native suite.
/// Uses the real character getters, mounted textures, BaseLib dialogue/Tome
/// integration and native upgrade/serialization. It does not win a run or add
/// a relic/card to the player's inventory to claim natural event completion.
/// </summary>
internal static class CharacterIntegrationProbe
{
    private static void Need(bool ok, string message)
    {
        if (!ok) throw new InvalidOperationException("Character integration: " + message);
    }

    internal static object Verify(Player player)
    {
        Need(!TestMode.IsOn && player.Character is VolibearCharacter &&
            !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("VOLIBEAR_TEST_TOKEN")),
            "requires the isolated real Volibear run");
        var character = (VolibearCharacter)player.Character;
        var beforeDeck = player.Deck.Cards.ToArray();
        var beforeRelics = player.Relics.ToArray();
        var instances = new Dictionary<object, int>(ReferenceEqualityComparer.Instance);
        var inventoryBefore = Inventory(player, instances);
        // These pivots belong to the native TextureRect's Control coordinates,
        // not the 422 x 1200 PNG pixels. Native hand_image keeps aspect ratio in
        // its long-arm rectangle; do not shorten the source to the pivot bounds.
        var hands = new[]
        {
            Hand("pointing", character.CustomArmPointingTexturePath, character.ArmPointingTexture, 163, 10),
            Hand("rock", character.CustomArmRockTexturePath, character.ArmRockTexture, 197, 600),
            Hand("paper", character.CustomArmPaperTexturePath, character.ArmPaperTexture, 197, 600),
            Hand("scissors", character.CustomArmScissorsTexturePath, character.ArmScissorsTexture, 197, 600)
        };

        string originalLanguage = LocManager.Instance.Language;
        var textRows = new List<object>();
        var dialogueRows = new List<object>();
        try
        {
            foreach (string language in new[] { "zhs", "eng", "zhs" })
            {
                LocManager.Instance.SetLanguage(language);
                foreach (var pair in new[]
                {
                    ("cardsModifierTitle", character.CardsModifierTitle),
                    ("cardsModifierDescription", character.CardsModifierDescription),
                    ("eventDeathPrevention", character.EventDeathPreventionLine),
                    ("aromaPrinciple", new LocString("characters", character.Id.Entry + ".aromaPrinciple")),
                    ("goldMonologue", new LocString("characters", character.Id.Entry + ".goldMonologue")),
                    ("banter.alive.endTurnPing", new LocString("characters", character.Id.Entry + ".banter.alive.endTurnPing")),
                    ("banter.dead.endTurnPing", new LocString("characters", character.Id.Entry + ".banter.dead.endTurnPing"))
                })
                {
                    string key = character.Id.Entry + "." + pair.Item1;
                    string text = pair.Item2.GetFormattedText();
                    Need(LocString.Exists("characters", key) && !string.IsNullOrWhiteSpace(text) &&
                        !text.Contains(key, StringComparison.Ordinal), "unresolved native character key " + key);
                    textRows.Add(new { language, table = "characters", key, text });
                }
                var seaGlass = (SeaGlass)ModelDb.Relic<SeaGlass>().ToMutable();
                seaGlass.CharacterId = character.Id;
                string seaKey = "SEA_GLASS." + character.Id.Entry + ".title";
                string seaTitle = seaGlass.Title.GetFormattedText();
                Need(LocString.Exists("relics", seaKey) && !string.IsNullOrWhiteSpace(seaTitle) &&
                    !seaTitle.Contains(seaKey, StringComparison.Ordinal), "unresolved native Sea Glass title");
                textRows.Add(new { language, table = "relics", key = seaKey, text = seaTitle });

                // Resolve the registered canonical event; native models prohibit calling
                // their constructors once ModelDb has registered the canonical instance.
                var dialogueSet = ModelDb.Event<TheArchitect>().DialogueSet;
                foreach (int visits in new[] { 0, 1, 25 })
                {
                    var candidates = dialogueSet.GetValidDialogues(character.Id, visits, visits,
                        allowAnyCharacterDialogues: false).ToArray();
                    Need(candidates.Length > 0, "TheArchitect has no dialogue for visit " + visits);
                    var rows = candidates.Select(dialogue =>
                    {
                        var lines = dialogue.Lines.Select(line => new
                        {
                            speaker = line.Speaker.ToString(), text = line.LineText.GetFormattedText()
                        }).ToArray();
                        Need(dialogue.IsRepeating && lines.Length > 0 && lines.All(line =>
                            !string.IsNullOrWhiteSpace(line.text) && !line.text.Contains("THE_ARCHITECT.talk.", StringComparison.Ordinal)),
                            "unresolved or non-repeating final dialogue");
                        return new { repeating = dialogue.IsRepeating, lines };
                    }).ToArray();
                    dialogueRows.Add(new { language, visits, candidates = rows });
                }
            }
        }
        finally { LocManager.Instance.SetLanguage(originalLanguage); }

        var canonical = ModelDb.Card<Volibear_R18>();
        Need(ReferenceEquals(((ITomeCard)canonical).TomeCharacter, ModelDb.Character<VolibearCharacter>()),
            "Tome interface is not scoped to this character");
        var tome = (DustyTome)ModelDb.Relic<DustyTome>().ToMutable();
        tome.SetupForPlayer(player);
        Need(tome.AncientCard?.Equals(canonical.Id) == true, "native Dusty Tome did not select the existing Thunder Pool");
        var savedTome = tome.ToSerializable();
        var relicJson = JsonSerializer.SerializeToElement(savedTome, JsonSerializationUtility.GetTypeInfo<SerializableRelic>());
        var restoredTome = (DustyTome)RelicModel.FromSerializable(
            relicJson.Deserialize(JsonSerializationUtility.GetTypeInfo<SerializableRelic>())!);
        Need(restoredTome.AncientCard?.Equals(canonical.Id) == true, "native Tome reward identity did not survive serialization");
        var reward = player.RunState.CreateCard(ModelDb.GetById<CardModel>(tome.AncientCard), player);
        CardCmd.Upgrade(reward);
        var savedCard = reward.ToSerializable();
        var cardJson = JsonSerializer.SerializeToElement(savedCard, JsonSerializationUtility.GetTypeInfo<SerializableCard>());
        var restoredCard = CardModel.FromSerializable(
            cardJson.Deserialize(JsonSerializationUtility.GetTypeInfo<SerializableCard>())!);
        Need(reward is Volibear_R18 && reward.Rarity == CardRarity.Rare && reward.CurrentUpgradeLevel == 1 &&
            restoredCard is Volibear_R18 && restoredCard.CurrentUpgradeLevel == 1 &&
            restoredCard.DynamicVars["Lightning"].BaseValue == 9 && restoredCard.DynamicVars["Pool"].BaseValue == 6,
            "existing Tome reward upgrade or native card persistence drifted");
        var tomeRow = new
        {
            selected = tome.AncientCard!.Entry, rarity = reward.Rarity.ToString(), upgrade = reward.CurrentUpgradeLevel,
            restored = restoredCard.Id.Entry, restoredUpgrade = restoredCard.CurrentUpgradeLevel,
            restoredRelicCard = restoredTome.AncientCard!.Entry,
            lightning = restoredCard.DynamicVars["Lightning"].BaseValue, pool = restoredCard.DynamicVars["Pool"].BaseValue,
            relic = relicJson, card = cardJson
        };
        player.RunState.RemoveCard(reward);
        Need(!player.RunState.ContainsCard(reward), "transient Tome reward leaked into run card state");

        var nativeAudio = new[] { character.CharacterSelectSfx, character.AttackSfx, character.CastSfx,
            character.DeathSfx, character.CharacterTransitionSfx };
        Need(nativeAudio.Length == nativeAudio.Distinct(StringComparer.Ordinal).Count() &&
            nativeAudio.All(path => !VolibearNativeAudio.BeforeNativeOneShot(path)), "native fabricated audio keys changed");
        Need(Harmony.GetPatchInfo(VolibearNativeAudio.NativeOneShot())?.Prefixes.Any(p =>
            p.owner == VolibearNativeAudio.HarmonyId) == true, "native audio filter was not installed");
        Need(beforeDeck.SequenceEqual(player.Deck.Cards, ReferenceEqualityComparer.Instance) &&
            beforeRelics.SequenceEqual(player.Relics, ReferenceEqualityComparer.Instance), "probe mutated player inventory");
        var inventoryAfter = Inventory(player, instances);
        Need(JsonSerializer.Serialize(inventoryBefore) == JsonSerializer.Serialize(inventoryAfter),
            "probe changed an inventory item identity or upgrade");
        return new { schema = 1, character = character.Id.Entry, hands, textRows, dialogueRows, tome = tomeRow,
            suppressedNativeAudio = nativeAudio, inventoryBefore, inventoryAfter, inventoryUnchanged = true,
            scope = "native-character-resource-localization-ancient-reward-contracts" };
    }

    private static object Inventory(Player player, Dictionary<object, int> instances)
    {
        int Instance(object item)
        {
            if (!instances.TryGetValue(item, out int identity))
            {
                identity = instances.Count + 1;
                instances.Add(item, identity);
            }
            return identity;
        }
        return new
        {
            deck = player.Deck.Cards.Select(card => new
            {
                instance = Instance(card), id = card.Id.Entry, upgrade = card.CurrentUpgradeLevel
            }).ToArray(),
            relics = player.Relics.Select(relic => new { instance = Instance(relic), id = relic.Id.Entry }).ToArray()
        };
    }

    private static object Hand(string gesture, string path, Texture2D texture, int pivotX, int pivotY)
    {
        Need(ResourceLoader.Exists(path) && texture is not null && GodotObject.IsInstanceValid(texture),
            "missing native hand texture " + gesture);
        using var image = texture.GetImage();
        Need(image is not null && !image.IsEmpty() && image.GetData().Length > 0 &&
            image.GetWidth() == 422 && image.GetHeight() == 1200, "undecodable or wrong-canvas native hand " + gesture);
        return new { gesture, path, width = image.GetWidth(), height = image.GetHeight(), pivotX, pivotY, decoded = true,
            sha256 = Convert.ToHexString(SHA256.HashData(image.GetData())).ToLowerInvariant() };
    }
}
