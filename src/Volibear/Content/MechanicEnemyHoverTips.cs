using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;

namespace Volibear.Content;

/// <summary>Action-body mechanics which have no guaranteed native status icon.
/// Native intent and Power tips remain first; these explain the narrower contribution.</summary>
internal static class MechanicEnemyHoverTips
{
    internal static bool HasMechanics(Creature creature) => creature.Monster is { } monster &&
        monster.GetType().Assembly == typeof(MonsterModel).Assembly &&
        System.Linq.Enumerable.Any(MechanicGlossary.EnemyEntries, entry => Array.IndexOf(entry.Monsters, monster.GetType().Name) >= 0);

    internal static IEnumerable<IHoverTip> ForCreature(Creature creature, bool suppressed)
    {
        if (creature.Monster is not { } monster || monster.GetType().Assembly != typeof(MonsterModel).Assembly) yield break;
        foreach (var entry in MechanicGlossary.EnemyEntries)
        {
            if (Array.IndexOf(entry.Monsters, monster.GetType().Name) < 0) continue;
            var description = new LocString("static_hover_tips", "VOLIBEAR-ENEMY-" + entry.Key + ".description").GetFormattedText();
            if (suppressed) description += "\n\n" + new LocString("static_hover_tips", "VOLIBEAR-DISABLED.description").GetFormattedText();
            yield return new HoverTip(new LocString("static_hover_tips", "VOLIBEAR-ENEMY-" + entry.Key + ".title"), description)
#if !STS2_BETA
                { Id = "VOLIBEAR-ENEMY-" + entry.Key }
#endif
                ;
        }
    }
}
