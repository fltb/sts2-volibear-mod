#if STS2_BETA
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Nodes.Screens.Timeline;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Timeline;
using MegaCrit.Sts2.Core.Timeline.Epochs;

namespace Volibear.Content;

internal sealed class VolibearStory : StoryModel
{
    protected override string Id => "VOLIBEAR";
    public override EpochModel[] Epochs => [
        new FirstThunder(), new BrokenArmor(), new Freedom(), new Roar(), new Bones(), new Storm()
    ];
}

internal abstract class VolibearEpoch(int chapter, EpochEra era, int position) : EpochModel
{
    public override string Id => $"VOLIBEAR_CHARACTER{chapter}_EPOCH";
    public override EpochEra Era => era;
    public override int EraPosition => position;
    public override string StoryId => "Volibear";
    protected LocString Text(string field) => new("epochs", Id + "." + field);
    public override string UnlockText => Title.GetFormattedText();
    public override void QueueUnlocks() => NTimelineScreen.Instance.QueueMiscUnlock(UnlockText);
}

internal sealed class FirstThunder() : VolibearEpoch(1, EpochEra.Prehistoria0, 1)
{
    public override string UnlockText => Text("unlockText").GetFormattedText();
    public override void QueueUnlocks() => NTimelineScreen.Instance.QueueMiscUnlock(Text("unlock").GetFormattedText());
}
internal sealed class BrokenArmor() : VolibearEpoch(2, EpochEra.Prehistoria1, 1);
internal sealed class Freedom() : VolibearEpoch(3, EpochEra.Prehistoria2, 2);
internal sealed class Roar() : VolibearEpoch(4, EpochEra.Seeds0, 2)
{
    public override string UnlockText
    {
        get
        {
            var hint = Text("unlockText");
            var potions = Ironclad4Epoch.Potions;
            for (int i = 0; i < potions.Count; i++)
                hint.Add($"Potion{i + 1}", potions[i].Title);
            return hint.GetFormattedText();
        }
    }

    public override void QueueUnlocks() => NTimelineScreen.Instance.QueueMiscUnlock(Text("unlock").GetFormattedText());
}
internal sealed class Bones() : VolibearEpoch(5, EpochEra.Blight0, 1);
internal sealed class Storm() : VolibearEpoch(6, EpochEra.Invitation6, 2);

internal static class VolibearEpochs
{
    // The game builds these catalogs from a source-generated list of vanilla types.
    private static T Catalog<T>(Type owner, string field) where T : class =>
        AccessTools.Field(owner, field)?.GetValue(null) as T
            ?? throw new MissingFieldException(owner.FullName, field);

    internal static void Install()
    {
        var catalog = typeof(EpochModel);
        var models = Catalog<Dictionary<string, Type>>(catalog, "_epochTypeDictionary");
        var ids = Catalog<Dictionary<Type, string>>(catalog, "_typeToIdDictionary");
        var types = Catalog<List<Type>>(catalog, "_allEpochs");
        var stories = Catalog<Dictionary<string, Type>>(typeof(StoryModel), "_storyTypeDictionary");
        var story = new VolibearStory();
        foreach (var epoch in story.Epochs)
        {
            models.Add(epoch.Id, epoch.GetType());
            ids.Add(epoch.GetType(), epoch.Id);
            types.Add(epoch.GetType());
        }
        stories.Add("VOLIBEAR", typeof(VolibearStory));
        // Rebuild lazy snapshots even when another mod has already queried the catalog.
        AccessTools.Field(catalog, "_allEpochIds").SetValue(null, null);
        AccessTools.Field(catalog, "_epochIdsHashSet").SetValue(null, null);
        var harmony = new Harmony("Volibear.Epochs");
        harmony.Patch(AccessTools.Method(typeof(NeowEpoch), nameof(NeowEpoch.GetTimelineExpansion)),
            postfix: new HarmonyMethod(typeof(VolibearEpochs), nameof(ExpandTimeline)));
        harmony.Patch(AccessTools.Method(typeof(NTimelineScreen), nameof(NTimelineScreen.OnSubmenuOpened)),
            prefix: new HarmonyMethod(typeof(VolibearEpochs), nameof(SyncOnOpen)));
    }

    private static void ExpandTimeline(ref EpochModel[] __result) =>
        __result = [.. __result, .. new VolibearStory().Epochs];

    private static void SyncOnOpen()
    {
        var manager = SaveManager.Instance;
        var progress = manager.Progress;
        var chapters = new VolibearStory().Epochs;
#if STS2_0_113
        var ironclad = progress.GetStatsForCharacter<Ironclad>();
#else
        var ironclad = progress.GetStatsForCharacter(ModelDb.GetId<Ironclad>());
#endif
        bool[] earned = new bool[chapters.Length];
        earned[0] = ironclad != null && (ironclad.TotalWins > 0 || ironclad.TotalLosses > 0);

        var character = ModelDb.GetId<VolibearCharacter>();
        int Wins(EncounterModel encounter) =>
            progress.EncounterStats.TryGetValue(encounter.Id, out var stats)
                ? stats.FightStats.FirstOrDefault(s => s.Character == character)?.Wins ?? 0 : 0;

        foreach (var act in ModelDb.Acts)
            if (act.Index is >= 0 and <= 2 && act.AllBossEncounters.Any(e => Wins(e) > 0))
                earned[act.Index + 1] = true;
        earned[4] = ModelDb.AllEncounters.Where(e => e.RoomType == RoomType.Elite).Sum(Wins) >= 15;
        earned[5] = ModelDb.AllEncounters.Where(e => e.RoomType == RoomType.Boss).Sum(Wins) >= 15;
        var timelineOpen = progress.IsEpochRevealed(EpochModel.GetId<NeowEpoch>());
        var changed = false;
        for (int i = 0; i < chapters.Length; i++)
        {
            var id = chapters[i].Id;
            var existing = progress.Epochs.FirstOrDefault(e => e.Id == id);
            if (timelineOpen && (existing == null || existing.State == EpochState.ObtainedNoSlot))
            {
                progress.UnlockSlot(id);
                changed = true;
            }
            if (earned[i] && !progress.IsEpochObtained(id))
            {
                progress.ObtainEpoch(id);
                changed = true;
            }
        }
        if (changed) manager.SaveProgressFile();
    }
}
#endif
