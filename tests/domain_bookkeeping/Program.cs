using Volibear.Core;

// Direct production state classes only. Native Harmony adapters, draw/exhaust, enemy
// suppression and gameplay are NOT executed by this standalone bookkeeping test.
var checks = 0;
void Check(bool condition, string message)
{
    checks++;
    if (!condition) throw new InvalidOperationException(message);
}
void Reject(Action action, string message)
{
    var rejected = false;
    try { action(); }
    catch (ArgumentOutOfRangeException) { rejected = true; }
    catch (OverflowException) { rejected = true; }
    Check(rejected, message);
}

var play = new CardResolutionPlayGate();
Check(!play.TryAttach(false) && !play.Attached, "Outside domain a segment must not consume attachment.");
Check(play.TryAttach(true), "First eligible segment inside domain attaches.");
Check(!play.TryAttach(true), "Second hit of same multihit play cannot attach again.");
Check(!play.TryAttach(true), "Replay shares same real-play opportunity.");
var secondCard = new CardResolutionPlayGate();
Check(secondCard.TryAttach(true), "A second actual card play gets its own opportunity.");
var reusedCard = new CardResolutionPlayGate();
Check(reusedCard.TryAttach(true), "Reusing the same card entity as a new actual play gets a fresh gate.");

var lateDomain = new CardResolutionPlayGate();
Check(!lateDomain.TryAttach(false), "Original resolution outside domain doesn't reserve attachment.");
Check(!lateDomain.Attached, "Late deployment remains eligible.");
Check(lateDomain.TryAttach(true), "First eligible segment during replay after domain entry attaches.");
Check(!lateDomain.TryAttach(true), "Further replay segments cannot reattach.");
var recursive = new CardResolutionPlayGate();
Check(recursive.TryAttach(true), "Reserve before any awaited response.");
Check(!recursive.TryAttach(true), "Reentrant response observes already reserved opportunity.");
var aborted = new CardResolutionPlayGate();
aborted.Close();
Check(!aborted.TryAttach(true), "Closed or cancelled actual plays cannot emit late attachment.");
play.Close();
Check(play.Closed && !play.TryAttach(true), "Closing a completed play preserves terminal state.");

var clock = new CardResolutionDrawClock(1);
Check(!clock.TryConsumeNormalDraw(1), "Domain opened during current normal draw doesn't expire on that draw.");
Check(!clock.TryConsumeNormalDraw(1), "Same round / extra-turn boundary doesn't spend a normal round.");
Check(clock.TryConsumeNormalDraw(2), "The NEXT normal initial draw spends one round after it finishes.");
Check(!clock.TryConsumeNormalDraw(2), "Boundary is idempotent.");
Check(clock.TryConsumeNormalDraw(3), "Following normal initial draw spends next round.");
Check(!clock.TryConsumeNormalDraw(2), "Stale boundary cannot tick duration backwards.");
var freshDomain = new CardResolutionDrawClock(3);
Check(!freshDomain.TryConsumeNormalDraw(3), "Newly applied domain gets independent boundary.");
Check(freshDomain.TryConsumeNormalDraw(4), "New domain ticks on its own next normal draw.");

Check(CardResolutionDuration.Extend(0, 1) == 1, "Open domain1.");
Check(CardResolutionDuration.Extend(1, 2) == 3, "Finite duration stacks additively1+2.");
Check(CardResolutionDuration.Extend(3, 1) == 4, "Extend adds, does not replace.");
Check(CardResolutionDuration.Extend(CardResolutionDuration.Permanent, 2) == CardResolutionDuration.Permanent,
    "Finite application cannot downgrade permanent domain.");
Reject(() => CardResolutionDuration.Extend(1, 0), "Zero duration rejected.");
Reject(() => CardResolutionDuration.Extend(1, -1), "Negative duration rejected.");
Reject(() => CardResolutionDuration.Extend(1, CardResolutionDuration.Permanent), "Permanent is explicit, not finite input.");
Reject(() => CardResolutionDuration.Extend(CardResolutionDuration.Permanent - 1, 1), "Finite sum cannot create sentinel.");
Reject(() => CardResolutionDuration.Extend(CardResolutionDuration.Permanent - 1, 3), "Finite overflow rejected.");
Console.WriteLine($"PASS {checks} production domain bookkeeping assertions; gameplay/Harmony NOT_RUN.");
