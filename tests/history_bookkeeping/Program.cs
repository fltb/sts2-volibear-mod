using Volibear.Core;

var checks = 0;
void Equal<T>(T expected, T actual, string name)
{
    if (!EqualityComparer<T>.Default.Equals(expected, actual)) throw new Exception($"{name}: expected {expected}, actual {actual}");
    checks++;
}
void True(bool value, string name) => Equal(true, value, name);

var a = new object(); var b = new object();
var history = new PlayHistoryLedger<int, object>();
var first = history.Record(101, 1, 0, true, true, a);
Equal(0, first.PriorAttacks, "first attack has zero prior");
Equal(1, first.AttackOrdinal, "pending actual first attack counted before effects");
Equal<int?>(null, first.PreviousType, "first previous type absent");
Equal(1, first.TargetOrdinal, "first single target");
Equal(0, first.PriorTargetAttacks, "self excluded prior target");
True(!first.Completed, "before effect not complete");
for (var replayOrHit = 0; replayOrHit < 8; replayOrHit++)
    True(ReferenceEquals(first, history.Record(101, 1, 0, true, true, a)), "same actual identity idempotent");
Equal(1, history.AttackCount(1), "replays and multihit do not count");
history.Complete(101);
True(first.Completed, "whole actual play completion");
var second = history.Record(102, 1, 0, true, true, a);
Equal(2, second.AttackOrdinal, "U26 pending second attack ordinal");
Equal(2, second.TargetOrdinal, "U25 second same enemy ordinal");
Equal(1, history.BeforeTargetCount(1, a, 102), "U07 excludes own newest target play");
Equal(2, history.BeforeTargetCount(1, a, null), "U07 preview includes all prior actual plays");
Equal(1, second.PriorAttacks, "C20 sees one prior");
Equal<int?>(0, second.PreviousType, "U20 sees previous attack");
var aoe = history.Record(103, 1, 0, true, false, a);
Equal(3, aoe.AttackOrdinal, "AoE counts as actual attack");
Equal(0, aoe.TargetOrdinal, "AoE hits never imply single target");
Equal(2, history.TargetCount(1, a), "AoE does not increment target");
var random = history.Record(104, 1, 0, true, false, b);
Equal(0, history.TargetCount(1, b), "random chosen hit target not card target metadata");
var skill = history.Record(105, 1, 1, false, true, a);
Equal(4, skill.AttackOrdinal, "skill not counted as attack");
Equal(0, skill.TargetOrdinal, "targeted skill no attack target ordinal");
Equal(2, history.TargetCount(1, a), "skill no target count");
var afterSkill = history.Record(106, 1, 0, true, true, b);
Equal<int?>(1, afterSkill.PreviousType, "U20 false after skill");
Equal(4, afterSkill.PriorAttacks, "C20 still sees prior attacks after skill");
// Nested actual plays change live totals but do not mutate their parent's snapshot.
var nested = history.Record(107, 1, 1, false, false, null);
Equal<int?>(1, afterSkill.PreviousType, "parent previous snapshot stable through nested play");
Equal(4, afterSkill.PriorAttacks, "parent count snapshot stable through nested play");
Equal(1, history.BeforeTargetCount(1, b, 106), "frozen beforeTarget live query changes after nested actual play");
Equal(1, afterSkill.TargetOrdinal, "captured target ordinal does not change");
var nestedTarget = history.Record(110, 1, 0, true, true, b);
Equal(2, history.TargetCount(1, b), "U25 finished condition sees live nested target count");
Equal(1, afterSkill.TargetOrdinal, "U25 must not substitute captured ordinal for live count");
var lastAttack = history.Record(108, 1, 0, true, true, a);
Equal(0, history.AttackCount(2), "new turn query reset without recording");
Equal(0, history.TargetCount(2, a), "target reset before new turn first play");
var newTurn = history.Record(109, 2, 0, true, true, a);
Equal(0, newTurn.PriorAttacks, "C20 resets new turn");
Equal<int?>(0, newTurn.PreviousType, "frozen TS U20 previous attack survives turn");
Equal(1, newTurn.AttackOrdinal, "turn ordinal resets");
Equal(1, newTurn.TargetOrdinal, "target ordinal resets");
var independent = new PlayHistoryLedger<int, object>();
Equal(0, independent.AttackCount(2), "other owner/combat has no history");
Equal<int?>(null, independent.PreviousType, "other owner previous absent");
var sameValueTarget = new object();
Equal(0, history.TargetCount(2, sameValueTarget), "target identity not slot or display name");

var hunt = new TargetDiscountLedger<object>();
Equal(0, hunt.Read(1, a), "new R14 does not backfill historical attacks");
hunt.Record(1, 201, a, 1);
Equal(0, hunt.Read(1, a, 201), "own grant excluded during current play");
Equal(1, hunt.Read(1, a), "later play sees one discount");
hunt.Record(1, 201, a, 1);
Equal(1, hunt.Read(1, a), "replay not grant twice");
hunt.Record(1, 202, b, 1);
Equal(1, hunt.Read(1, a), "other target untouched");
Equal(1, hunt.Read(1, b), "new target independent");
// Another deployment increases native power amount; older grants are not multiplied.
hunt.Record(1, 203, a, 2);
Equal(1, hunt.Read(1, a, 203), "new stack own grant excluded");
Equal(3, hunt.Read(1, a), "old one + new two, not historical count times new level");
Equal(0, hunt.Read(2, a), "R14 turn reset queried before event");
hunt.Record(2, 204, a, 2);
Equal(2, hunt.Read(2, a), "new turn retains power level but new ledger");
Equal(0, hunt.Read(2, a, 204), "new turn own grant excluded");
var secondHunt = new TargetDiscountLedger<object>();
Equal(0, secondHunt.Read(2, a), "independent native power instance ledger");
Console.WriteLine($"HISTORY_BOOKKEEPING_PASS checks={checks}; production ledgers, not native UI/payment acceptance");
if (args.Contains("--native-il"))
    Console.WriteLine($"NATIVE_CALLSITE_INSPECTION_PASS checks={NativeCallsiteChecks.Run()}; IL only, no installed patches or game execution");
