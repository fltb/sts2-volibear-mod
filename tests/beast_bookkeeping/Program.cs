using Volibear.Core;

// No game execution is claimed here. These tests link the production cost ledger and
// independently exercise native-style live modifier identity/expiration semantics.
var assertions = 0;
void Equal(int expected, int actual, string name)
{
    assertions++;
    if (expected != actual) throw new Exception($"{name}: expected={expected}, actual={actual}");
}
int Evaluate(BeastCostLedger<Modifier> ledger, params Modifier[] live) => ledger.Evaluate(live, (m, n) => m.Apply(n));

var oldSetTwo = new Modifier(2, true);
var oldRelative = new Modifier(-1, false);
var oldSurcharge = new Modifier(5, true);
Equal(1, Evaluate(new(3, [])), "plain base rebased to one");
Equal(0, Evaluate(new(3, [oldSetTwo]), oldSetTwo), "absolute old3->2 retains discount1");
Equal(0, Evaluate(new(3, [oldRelative]), oldRelative), "relative discount preserved");
Equal(1, Evaluate(new(3, [oldSurcharge]), oldSurcharge), "material surcharge not inherited");
var ledger = new BeastCostLedger<Modifier>(3, [oldSetTwo]);
Equal(1, Evaluate(ledger), "old modifier expires by disappearing from live list");
var newSetOne = new Modifier(1, true);
Equal(1, Evaluate(ledger, oldSetTwo, newSetOne), "new Set1 means form1, not old-base discount2");
var zero = new Modifier(0, true);
Equal(0, Evaluate(ledger, oldSetTwo, zero), "new zero overrides inherited cost");
Equal(1, Evaluate(ledger), "both expired restores one");
var newPlusOne = new Modifier(1, false);
Equal(1, Evaluate(ledger, oldSetTwo, newPlusOne), "new modifier follows rebasing");
Equal(2, Evaluate(ledger, newPlusOne), "inherited discount expiry reveals later surcharge");
var reduceOnly = new Modifier(1, true, true);
Equal(0, Evaluate(ledger, oldSetTwo, reduceOnly), "new reduce-only Set1 does not raise zero");
var olderCombat = new Modifier(2, true);
var olderTurn = new Modifier(0, true);
var mixed = new BeastCostLedger<Modifier>(3, [olderCombat, olderTurn]);
Equal(0, Evaluate(mixed, olderCombat, olderTurn), "two inherited lifetimes coexist");
Equal(0, Evaluate(mixed, olderCombat), "turn expiry retains combat discount");
Equal(1, Evaluate(mixed), "combat expiry restores base");
Equal(1, Evaluate(new(0, [])), "X or zero material has form base1");
Equal(1, Evaluate(new(-1, [])), "unplayable material has form base1");
var clonedOld = new Modifier(2, true);
var clonedNew = new Modifier(1, true);
var copy = ledger.CloneFor([oldSetTwo, newSetOne], [clonedOld, clonedNew]);
Equal(1, Evaluate(copy, clonedOld, clonedNew), "clone remaps old identity without reclassifying new modifiers");
Equal(0, Evaluate(copy, clonedOld), "clone inherited discount expires independently");
Equal(1, Evaluate(copy), "clone lifetime independent");
var untouched = new BeastCostLedger<Modifier>(3, [oldSetTwo]);
untouched.FormBase = 2;
Equal(1, Evaluate(untouched, oldSetTwo), "postconversion base updates retain relative inherited discount");
var changed = new Modifier(2, true);
var mutableAmount = new BeastCostLedger<Modifier>(3, [changed]);
changed.Amount = 3;
Equal(1, Evaluate(mutableAmount, changed), "native modifier amount mutation stays live");
var rejected = false;
try { ledger.CloneFor([oldSetTwo], []); }
catch (InvalidOperationException) { rejected = true; }
Equal(1, rejected ? 1 : 0, "clone shape drift fails loudly");
Console.WriteLine($"BEAST_BOOKKEEPING_OK assertions={assertions}; engine_cases=NOT_RUN");

sealed class Modifier(int amount, bool absolute, bool reduceOnly = false)
{
    internal int Amount = amount;
    internal int Apply(int current)
    {
        var proposed = absolute ? Amount : current + Amount;
        return reduceOnly ? Math.Min(current, proposed) : proposed;
    }
}
