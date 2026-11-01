using Volibear.Core;

// Executes the actual production counter class, not a rewritten Python model.
// No engine dependencies, damage simulation, engine pass claims or test branches.
var checks = 0;
void Check(bool condition, string message)
{
    checks++;
    if (!condition) throw new InvalidOperationException(message);
}

var counter = new LightningCounter();
Check(counter.Read(1, 1) == 0, "Fresh combat is empty.");
var first = counter.Begin(1, 1);
Check(counter.Read(1, 1) == 0, "Starting a batch does not count it.");
Check(counter.Complete(first, out var count) && count == 1, "One completion counts once.");
Check(!counter.Complete(first, out _) && counter.Read(1, 1) == 1, "Duplicate completion rejected.");

var interrupted = counter.Begin(1, 1);
counter.Abort(interrupted);
Check(!counter.Complete(interrupted, out _), "Partial/aborted work cannot complete.");
Check(counter.Read(1, 1) == 1, "Aborting preserves prior completed count.");

var nestedOuter = counter.Begin(1, 1);
var nestedInner = counter.Begin(1, 1);
Check(nestedOuter.Id != nestedInner.Id, "Distinct batch identities.");
Check(counter.Complete(nestedInner, out count) && count == 2, "Nested inner counts when settled.");
Check(counter.Complete(nestedOuter, out count) && count == 3, "Outer later counts exactly once.");
Check(counter.Read(1, 1) == 3, "Reading on the enemy side of same epoch does not clear count.");

var staleTurn = counter.Begin(1, 1);
Check(counter.Read(2, 2) == 0, "Next normal round resets turn count.");
Check(!counter.Complete(staleTurn, out _), "Previous turn pending work cannot enter next turn.");
var newTurn = counter.Begin(2, 2);
Check(counter.Complete(newTurn, out count) && count == 1, "New turn counts from one.");
Check(counter.Read(2, 3) == 0, "Extra player turn inside same round resets independently.");

var otherPlayer = new LightningCounter();
var extraTurn = counter.Begin(2, 3);
Check(counter.Complete(extraTurn, out count) && count == 1, "Extra turn completion.");
Check(otherPlayer.Read(2, 3) == 0, "Other owner has independent count.");
var otherBatch = otherPlayer.Begin(2, 3);
Check(otherPlayer.Complete(otherBatch, out count) && count == 1, "Other owner can count independently.");

var pendingAtExit = counter.Begin(2, 3);
counter.Close();
Check(counter.IsClosed && counter.Read(2, 3) == 0, "Combat close clears count.");
Check(!counter.Complete(pendingAtExit, out _), "Late completion after combat exit rejected.");
counter.Abort(pendingAtExit);
counter.Close();
Check(counter.Read(3, 4) == 0, "Closed scope never reopens on another turn.");
var threw = false;
try { counter.Begin(3, 4); }
catch (InvalidOperationException) { threw = true; }
Check(threw, "No new work in a closed scope.");
Check(otherPlayer.Read(2, 3) == 1, "Closing one owner does not mutate another counter.");

var nextCombat = new LightningCounter();
Check(nextCombat.Read(1, 1) == 0, "Fresh combat has no old count.");
var resetGeneration = nextCombat.Begin(1, 1);
nextCombat.Read(1, 2);
nextCombat.Read(1, 1);
Check(!nextCombat.Complete(resetGeneration, out _), "Returning to same numbers does not revive old tickets.");
Console.WriteLine($"PASS {checks} production bookkeeping assertions; gameplay NOT_RUN.");
