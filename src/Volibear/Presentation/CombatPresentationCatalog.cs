using System;
using System.Collections.Generic;

namespace Volibear.Presentation;

/// <summary>Authored visual identities only. No damage, targeting, RNG or timing of rules.</summary>
public sealed record CombatPresentationProfile(string Motion, string Contact, string Lightning,
    string? Accent = null, string? DomainMotion = null);

/// <summary>Every card has an explicit entry; base/upgraded faces share the same visual identity.
/// Hit counts and targets always come from committed native results, never this catalog.</summary>
public static class CombatPresentationCatalog
{
    public static CombatPresentationProfile Fallback { get; } = new("attack", "claw", "bolt");
    public static IReadOnlyDictionary<string, CombatPresentationProfile> Cards { get; } =
        new Dictionary<string, CombatPresentationProfile>(StringComparer.OrdinalIgnoreCase)
        {
            ["b01"] = new("attack", "claw", "bolt", DomainMotion: "domain_attack"),
            ["b02"] = new("block", "claw", "bolt", "guard", "domain_block"),
            ["b03"] = new("backhand", "cross_claw", "fork"),
            ["b04"] = new("lunge", "lunge", "bolt", "guard"),
            ["c01"] = new("lunge", "lunge", "bolt"),
            ["c02"] = new("double_claw", "cross_claw", "bolt"),
            ["c03"] = new("ground_slam", "slam", "ground_thunder"),
            ["c04"] = new("uppercut", "uppercut", "bolt"),
            ["c05"] = new("claw_flurry", "cross_claw", "fork"),
            ["c06"] = new("claw_flurry", "rake", "bolt"),
            ["c07"] = new("lunge", "lunge", "bolt"),
            ["c08"] = new("backhand", "rake", "bolt"),
            ["c09"] = new("sweep", "sweep", "fork"),
            ["c10"] = new("counter", "uppercut", "bolt", "guard"),
            ["c11"] = new("iron_guard", "claw", "bolt", "guard"),
            ["c12"] = new("iron_guard", "claw", "bolt", "armor"),
            ["c13"] = new("relaxed_loop", "claw", "bolt"),
            ["c14"] = new("iron_guard", "claw", "chain", "thunder_armor"),
            ["c15"] = new("cast", "claw", "bolt", DomainMotion: "domain_cast"),
            ["c17"] = new("primal_charge", "claw", "bolt", "storm_charge"),
            ["c18"] = new("roar", "claw", "storm", DomainMotion: "domain_roar"),
            ["c19"] = new("primal_charge", "claw", "bolt"),
            ["c20"] = new("backhand", "claw", "bolt"),
            ["c21"] = new("iron_guard", "claw", "bolt", "guard"),
            ["c22"] = new("ground_slam", "slam", "ground_thunder"),
            ["c24"] = new("thunder_call", "claw", "fork"),
            ["c25"] = new("chain_channel", "claw", "chain", "storm_charge"),
            ["c26"] = new("primal_charge", "claw", "ground_thunder"),
            ["u02"] = new("chain_channel", "claw", "chain", "storm_charge"),
            ["u03"] = new("iron_guard", "claw", "bolt", "armor"),
            ["u04"] = new("iron_guard", "claw", "bolt", "armor"),
            ["u05"] = new("ground_slam", "slam", "bolt"),
            ["u06"] = new("claw_flurry", "rake", "bolt"),
            ["u07"] = new("stomp_chain", "stomp", "ground_thunder"),
            ["u08"] = new("bite_rend", "bite", "bolt"),
            ["u10"] = new("primal_charge", "claw", "bolt"),
            ["u11"] = new("chain_channel", "claw", "chain", "replay_echo"),
            ["u12"] = new("thunder_call", "claw", "fork", "storm_charge"),
            ["u13"] = new("primal_charge", "claw", "bolt", "storm_charge"),
            ["u14"] = new("iron_guard", "claw", "bolt", "guard"),
            ["u15"] = new("relaxed_loop", "claw", "bolt"),
            ["u17"] = new("relaxed_loop", "claw", "bolt"),
            ["u19"] = new("storm_channel", "claw", "storm", "domain_echo"),
            ["u20"] = new("lunge", "lunge", "bolt"),
            ["u21"] = new("chain_channel", "claw", "chain", "storm_charge"),
            ["u23"] = new("roar", "claw", "storm", DomainMotion: "domain_roar"),
            ["u24"] = new("bite_rend", "bite_tear", "spear"),
            ["u25"] = new("primal_charge", "claw", "bolt"),
            ["u26"] = new("primal_charge", "claw", "bolt", "storm_charge"),
            ["u27"] = new("backhand", "cross_claw", "bolt"),
            ["u28"] = new("counter", "uppercut", "chain", "guard"),
            ["u29"] = new("thunder_call", "claw", "fork", "storm_charge"),
            ["u31"] = new("stomp_chain", "stomp", "ground_thunder"),
            ["u32"] = new("thunder_call", "claw", "fork", "domain_echo"),
            ["u34"] = new("iron_guard", "claw", "bolt", "thunder_armor"),
            ["u35"] = new("thunder_call", "claw", "fork"),
            ["u36"] = new("chain_channel", "claw", "chain"),
            ["u37"] = new("storm_channel", "claw", "storm"),
            ["u38"] = new("lunge", "lunge", "chain"),
            ["u39"] = new("thunder_call", "claw", "fork", "guard"),
            ["u40"] = new("chain_channel", "claw", "chain"),
            ["u41"] = new("uppercut", "feral_claw", "bolt"),
            ["u42"] = new("iron_guard", "claw", "bolt", "armor"),
            ["u43"] = new("feral_enter", "feral_claw", "bolt"),
            ["r01"] = new("storm_channel", "claw", "storm", "domain_echo"),
            ["r02"] = new("iron_guard", "claw", "bolt", "armor"),
            ["r05"] = new("iron_guard", "claw", "bolt", "armor"),
            ["r06"] = new("primal_charge", "claw", "bolt", "storm_charge"),
            ["r07"] = new("storm_channel", "claw", "eruption"),
            ["r08"] = new("claw_flurry", "cross_claw", "fork"),
            ["r09"] = new("counter", "uppercut", "storm", "guard"),
            ["r10"] = new("cast", "claw", "bolt", DomainMotion: "domain_cast"),
            ["r12"] = new("feral_enter", "feral_claw", "bolt"),
            ["r13"] = new("primal_charge", "claw", "storm"),
            ["r14"] = new("primal_charge", "claw", "bolt"),
            ["r16"] = new("primal_charge", "claw", "bolt", "storm_charge"),
            ["r17"] = new("chain_channel", "claw", "spear"),
            ["r18"] = new("storm_channel", "claw", "ground_thunder", "domain_echo"),
            ["r21"] = new("iron_guard", "claw", "bolt", "thunder_armor"),
            ["r23"] = new("thunder_call", "claw", "eruption"),
            ["r24"] = new("chain_channel", "claw", "chain"),
            ["r25"] = new("storm_channel", "claw", "storm", "domain_echo"),
            ["r27"] = new("feral_enter", "feral_claw", "bolt"),
            ["r28"] = new("feral_enter", "feral_claw", "bolt"),
            ["r29"] = new("feral_enter", "feral_claw", "bolt"),
            ["r30"] = new("feral_enter", "feral_claw", "bolt"),
            ["r31"] = new("storm_leap", "slam", "eruption", DomainMotion: "domain_storm_leap"),
            ["t01"] = new("double_claw", "feral_claw", "bolt"),
            ["t02"] = new("iron_guard", "claw", "ground_thunder", "thunder_armor")
        };

    public static CombatPresentationProfile For(string? key) =>
        key is not null && Cards.TryGetValue(key, out var profile) ? profile : Fallback;

    public static string ContactFor(string? key, CombatPresentationProfile profile, int hitIndex) =>
        string.Equals(key, "u08", StringComparison.OrdinalIgnoreCase) && hitIndex > 0 ? "bite_tear" : profile.Contact;
}
