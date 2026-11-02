using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using Volibear.Presentation;

// Actual locked-game IL metadata for the scalar receipt sites. This is independent of
// the production manifest: it pins the exact native call ordinal, signature and consume
// overload for every method, then proves missing/substituted/duplicated calls still fail.
internal static class PowerScalarMetadataTests
{
    private const BindingFlags Flags = BindingFlags.Static | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    private sealed record Site(MethodInfo Target, int Index, string Consume, string Frame);
    private static readonly (string Label, MethodInfo Entry, Site[] Sites)[] Manifest = Build();

    private static (string Label, MethodInfo Entry, Site[] Sites)[] Build()
    {
        var damage = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.Damage),
            [typeof(PlayerChoiceContext), typeof(IEnumerable<Creature>), typeof(decimal), typeof(ValueProp), typeof(Creature), typeof(CardModel)]);
        var block = AccessTools.Method(typeof(CreatureCmd), nameof(CreatureCmd.GainBlock),
            [typeof(Creature), typeof(decimal), typeof(ValueProp), typeof(CardPlay), typeof(bool)]);
        var apply = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.Apply),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(Creature), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)]);
        var modify = AccessTools.Method(typeof(PowerCmd), nameof(PowerCmd.ModifyAmount),
            [typeof(PlayerChoiceContext), typeof(PowerModel), typeof(decimal), typeof(Creature), typeof(CardModel), typeof(bool)]);
        var clear = AccessTools.Method(typeof(Creature), "ClearBlock");
        var auto = AccessTools.Method(typeof(CardCmd), nameof(CardCmd.AutoPlay));
        var play = AccessTools.Method(typeof(MegaCrit.Sts2.Core.GameActions.PlayCardAction), "ExecuteAction");
        var spend = AccessTools.Method(typeof(CardModel), nameof(CardModel.SpendResources));
        var turnEndCard = AccessTools.Method(typeof(CardModel), nameof(CardModel.OnTurnEndInHandWrapper));
        var turnEnd = AccessTools.Method(typeof(CombatManager), "DoTurnEnd");
        var damageHook = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyDamage));
        var hpLostHook = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyHpLost));
        var blockHook = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyBlock));
        var powerHook = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyPowerAmountReceived));
        var clearHook = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldClearBlock));
        var playHook = AccessTools.Method(typeof(Hook), nameof(Hook.ShouldPlay));
        var canPlay = AccessTools.Method(typeof(CardModel), nameof(CardModel.CanPlay),
            [typeof(UnplayableReason).MakeByRefType(), typeof(AbstractModel).MakeByRefType()]);
        var energy = AccessTools.Method(typeof(CardEnergyCost), nameof(CardEnergyCost.GetAmountToSpend));
        var keywords = AccessTools.PropertyGetter(typeof(CardModel), nameof(CardModel.Keywords));
        return
        [
            ("CreatureCmd.Damage", damage,
            [
                new(damageHook, 99, "Consumed", nameof(Hook.ModifyDamage)),
                new(hpLostHook, 238, "Consumed", nameof(Hook.ModifyHpLost)),
                new(hpLostHook, 318, "Consumed", nameof(Hook.ModifyHpLost)),
                new(hpLostHook, 458, "Consumed", nameof(Hook.ModifyHpLost)),
            ]),
            ("CreatureCmd.GainBlock", block,
                [new(blockHook, 89, "Consumed", nameof(Hook.ModifyBlock))]),
            ("PowerCmd.Apply", apply,
                [new(powerHook, 183, "Consumed", nameof(Hook.ModifyPowerAmountReceived))]),
            ("PowerCmd.ModifyAmount", modify,
                [new(powerHook, 116, "Consumed", nameof(Hook.ModifyPowerAmountReceived))]),
            ("Creature.ClearBlock", clear,
                [new(clearHook, 12, "ConsumedBoolean", nameof(Hook.ShouldClearBlock))]),
            // Two real sites, in native order: the ShouldPlay predicate and the paid cost read.
            ("CardCmd.AutoPlay", auto,
            [
                new(playHook, 95, "ConsumedBoolean", nameof(Hook.ShouldPlay)),
                new(energy, 456, "ConsumedInteger", nameof(Hook.ModifyEnergyCostInCombat)),
            ]),
            ("PlayCardAction.ExecuteAction", play,
                [new(canPlay, 138, "ConsumedBoolean", nameof(Hook.ShouldPlay))]),
            ("CardModel.SpendResources", spend,
                [new(energy, 19, "ConsumedInteger", nameof(Hook.ModifyEnergyCostInCombat))]),
            ("CardModel.OnTurnEndInHandWrapper", turnEndCard,
                [new(keywords, 127, "ConsumedKeywords", nameof(Hook.ModifyKeywordsInCombat))]),
            ("CombatManager.DoTurnEnd", turnEnd,
                [new(keywords, 83, "ConsumedKeywords", nameof(Hook.ModifyKeywordsInCombat))]),
        ];
    }

    internal static void Run()
    {
        int checks = 0;
        void Need(bool condition, string message) { checks++; if (!condition) throw new Exception("Power scalar native metadata: " + message); }
        static MethodBase Body(MethodInfo entry) => AccessTools.Method(
            entry.GetCustomAttribute<AsyncStateMachineAttribute>()!.StateMachineType, "MoveNext");
        var keywords = AccessTools.PropertyGetter(typeof(CardModel), nameof(CardModel.Keywords));
        var allTargets = Manifest.SelectMany(row => row.Sites.Select(site => site.Target)).Where(target => target != keywords).ToHashSet();
        var keywordBodies = Manifest.Where(row => row.Sites.Any(site => site.Consume == "ConsumedKeywords"))
            .Select(row => Body(row.Entry)).ToHashSet();
        var nativeCalls = AccessTools.Method(typeof(PowerPresentationDomainScalars), "NativeCalls");
        var begin = AccessTools.Method(typeof(PowerPresentationDomainScalars), "Begin");
        var consume = Manifest.SelectMany(row => row.Sites.Select(site => site.Consume)).Distinct()
            .ToDictionary(name => name, name => AccessTools.Method(typeof(PowerPresentationDomainScalars), name));
        var harmony = new Harmony("Volibear.Tests.PowerScalarNativeMetadata");
        Need(!harmony.GetPatchedMethods().Any(), "metadata fixture requires a fresh Harmony owner");
        static List<CodeInstruction> Copy(IEnumerable<CodeInstruction> code) => code.Select(instruction => new CodeInstruction(instruction)).ToList();
        static string Dump(IEnumerable<CodeInstruction> code) => string.Join(", ", code.Select(c => c.operand is MethodInfo m ? m.Name : c.opcode.Name));
        void ExpectDrift(string label, string mutation, Func<List<CodeInstruction>, List<CodeInstruction>> transform)
        {
            var (_, entry, _) = Manifest.Single(row => row.Label == label);
            var body = Body(entry);
            var mutated = transform(Copy(PatchProcessor.GetOriginalInstructions(body)));
            try
            {
                _ = ((IEnumerable<CodeInstruction>)nativeCalls.Invoke(null, [mutated, new DynamicMethod(mutation, typeof(void), Type.EmptyTypes).GetILGenerator(), body])!).ToList();
                Need(false, "drift accepted: " + mutation);
            }
            catch (InvalidOperationException error)
            {
                Need(error.Message.Contains("drifted", StringComparison.Ordinal) && error.Message.Contains(label, StringComparison.Ordinal),
                    "drift diagnostic names " + label + ": " + error.Message);
            }
        }

        try
        {
            var original = new Dictionary<MethodBase, List<CodeInstruction>>();
            int total = 0;
            foreach (var (label, entry, sites) in Manifest)
            {
                var body = Body(entry);
                var code = PatchProcessor.GetOriginalInstructions(body).ToList();
                original[body] = code;
                bool keywordBody = keywordBodies.Contains(body);
                var admitted = code.Select((instruction, index) => (instruction, index)).Where(pair =>
                    pair.instruction.operand is MethodInfo method && (allTargets.Contains(method) ||
                        (keywordBody && method == keywords))).ToArray();
                Need(admitted.Length == sites.Length, label + " admitted site count " + admitted.Length + " != " + sites.Length);
                Need(admitted.Select(pair => (MethodInfo)pair.instruction.operand!).SequenceEqual(sites.Select(site => site.Target)),
                    label + " exact target sequence: " + Dump(admitted.Select(pair => pair.instruction)));
                for (int i = 0; i < sites.Length; i++)
                {
                    var site = sites[i];
                    Need(admitted[i].index == site.Index, label + " exact native ordinal " + site.Index + " for " + site.Target.Name + " (actual " + admitted[i].index + ")");
                    Need(code[site.Index].Calls(site.Target), label + " actual call at pinned ordinal " + site.Index);
                }
                total += sites.Length;
            }
            Need(total == 14, "locked game exposes exactly fourteen admitted scalar sites, found " + total);

            // Production install must accept this exact manifest and wire one narrow pair per site.
            PowerPresentationDomainScalars.Install(harmony);
            foreach (var (label, entry, sites) in Manifest)
            {
                var body = Body(entry);
                var info = Harmony.GetPatchInfo(body);
                Need(info is not null && info.Transpilers.Count(patch => patch.owner == harmony.Id) == 1, label + " owns exactly one transpiler");
            }
            foreach (var (label, entry, sites) in Manifest)
            {
                var body = Body(entry);
                var transformed = ((IEnumerable<CodeInstruction>)nativeCalls.Invoke(null,
                    [Copy(original[body]), new DynamicMethod("PowerScalarEmission", typeof(void), Type.EmptyTypes).GetILGenerator(), body])!).ToList();
                Need(transformed.Count(instruction => instruction.Calls(begin)) == sites.Length, label + " one Begin per exact site");
                foreach (var site in sites)
                {
                    var positions = transformed.Select((instruction, index) => (instruction, index))
                        .Where(pair => pair.instruction.Calls(site.Target)).Select(pair => pair.index).ToArray();
                    Need(positions.Length == sites.Count(candidate => candidate.Target == site.Target),
                        label + " emitted pair count for " + site.Target.Name);
                    foreach (int at in positions)
                    {
                        Need(at >= 3 && transformed[at - 1].opcode == OpCodes.Stloc &&
                            transformed[at - 2].Calls(begin) && transformed[at - 3].opcode == OpCodes.Ldstr &&
                            (string)transformed[at - 3].operand! == site.Frame, label + " frame begins immediately before " + site.Target.Name);
                        Need(at + 3 < transformed.Count && transformed[at + 1].opcode == OpCodes.Dup &&
                            transformed[at + 2].opcode == OpCodes.Ldloc && transformed[at + 3].Calls(consume[site.Consume]),
                            label + " " + site.Consume + " follows " + site.Target.Name);
                    }
                }
            }

            // The old loose count guard must never be reintroduced: each mutation still fails.
            ExpectDrift("CreatureCmd.Damage", "remove-hp-loss", code => { code.RemoveAt(code.FindIndex(instruction => instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.ModifyHpLost))))); return code; });
            ExpectDrift("CardCmd.AutoPlay", "substitute-shouldplay", code => { code[code.FindIndex(instruction => instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.ShouldPlay))))].operand = AccessTools.Method(typeof(Hook), nameof(Hook.ModifyDamage)); return code; });
            ExpectDrift("CardCmd.AutoPlay", "duplicate-shouldplay", code => { int at = code.FindIndex(instruction => instruction.Calls(AccessTools.Method(typeof(Hook), nameof(Hook.ShouldPlay)))); code.Insert(at + 1, new CodeInstruction(OpCodes.Call, AccessTools.Method(typeof(Hook), nameof(Hook.ShouldPlay)))); return code; });
            Console.WriteLine($"POWER_SCALAR_NATIVE_METADATA_PASS methods={Manifest.Length} sites={total} guards=3 checks={checks} native-gameplay=NOT_RUN");
        }
        finally
        {
            try { harmony.UnpatchAll(harmony.Id); }
            finally
            {
                if (harmony.GetPatchedMethods().Any()) throw new InvalidOperationException("Power scalar metadata fixture left patches installed");
            }
        }
    }
}
