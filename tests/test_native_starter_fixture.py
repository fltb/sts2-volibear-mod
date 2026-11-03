"""Exact starter-only bulk setup: linked guard/probe blocks, locked API compile; no game."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from xml.sax.saxutils import escape
from tools.runtime_test import fixture_runtime

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / 'src/Volibear/NativeAcceptanceStarterFixture.cs'
FACE = ROOT / 'src/Volibear/CardFaceAcceptanceProbe.cs'
LIFE = ROOT / 'src/Volibear/CardLifecycleAcceptanceProbe.cs'

DOUBLES = r'''
using System;
using System.Linq;
using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using Volibear.Content;
using Volibear;
namespace MegaCrit.Sts2.Core.Models {
 public class CardModel { public object? Affliction, Enchantment; }
 public class Pile { public List<CardModel> Cards = new(); }
 public class Creature { public List<object> Powers = new(); }
 public class Pcs {
  public int TurnNumber = 1; public Pile Hand = new(), DrawPile = new(), Other = new();
  public Pile[] AllPiles => [Hand,DrawPile,Other];
 }
 public class Player {
  public Pcs? PlayerCombatState = new(); public Creature Creature = new();
  public List<object> Relics = [new HuntersHeart()]; public Pile Deck = new();
 }
}
namespace MegaCrit.Sts2.Core.Combat {
 public class CombatState {
  public int RoundNumber = 1; public List<Player> Players = [new()];
  public List<Creature> Enemies = [new(),new(),new()];
 }
}
namespace Volibear.Content {
 public sealed class Volibear_B01 : CardModel {} public sealed class Volibear_B02 : CardModel {}
 public sealed class Volibear_B03 : CardModel {} public sealed class Volibear_B04 : CardModel {}
 public sealed class HuntersHeart {}
}
enum PileType { Draw }
enum CardPilePosition { Bottom }
record Move(bool success, CardModel cardAdded);
static class CardPileCmd {
 public static int Calls, Visuals, Hooks, Failure;
 public static Task<List<Move>> Add(IEnumerable<CardModel> cards, PileType target, CardPilePosition position, bool skipVisuals = false) {
  Calls++; if (target != PileType.Draw || position != CardPilePosition.Bottom || skipVisuals) throw new Exception("changed native flags");
  var pcs = Program.Current.Players.Single().PlayerCombatState!;
  var results = new List<Move>();
  foreach (var card in cards) { pcs.Hand.Cards.Remove(card); pcs.DrawPile.Cards.Add(card); Visuals++; results.Add(new(true,card)); }
  foreach (var result in results) Hooks++;
  if (Failure == 1) results[0] = results[0] with { success = false };
  if (Failure == 2) results.Reverse();
  if (Failure == 3) pcs.DrawPile.Cards.Reverse();
  return Task.FromResult(results);
 }
}
static class Program {
 public static CombatState Current = null!;
 static CardModel[] Deck() => [new Volibear_B01(),new Volibear_B02(),new Volibear_B01(),new Volibear_B03(),new Volibear_B02(),new Volibear_B04(),new Volibear_B02(),new Volibear_B01(),new Volibear_B02(),new Volibear_B01()];
 static CombatState Fresh() {
  Current = new(); var p = Current.Players.Single(); var cards = Deck();
  p.PlayerCombatState!.Hand.Cards.AddRange(cards.Take(5)); p.PlayerCombatState.DrawPile.Cards.AddRange(cards.Skip(5));
  p.Deck.Cards.AddRange(Deck()); CardPileCmd.Calls = CardPileCmd.Visuals = CardPileCmd.Hooks = CardPileCmd.Failure = 0;
  return Current;
 }
 static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
 static string Ref(CardModel card) => card.GetHashCode().ToString();
 // SOURCE_BLOCKS
 static async Task Main() {
  var valid = Fresh(); var initial = valid.Players[0].PlayerCombatState!.Hand.Cards.ToArray();
  NativeAcceptanceStarterFixture.Validate(valid);
  Require(initial.SequenceEqual(valid.Players[0].PlayerCombatState!.Hand.Cards), "guard mutated hand");
  Action<CombatState>[] mutations = [
   s => s.RoundNumber = 2,
   s => s.Players[0].PlayerCombatState!.TurnNumber = 2,
   s => s.Players[0].Creature.Powers.Add(new()),
   s => s.Enemies[2].Powers.Add(new()),
   s => s.Players[0].Relics.Clear(),
   s => s.Players[0].Relics.Add(new()),
   s => s.Players[0].Relics[0] = new object(),
   s => s.Players[0].PlayerCombatState!.Hand.Cards.RemoveAt(0),
   s => s.Players[0].PlayerCombatState!.DrawPile.Cards.Add(new Volibear_B01()),
   s => s.Players[0].PlayerCombatState!.Hand.Cards[0] = new CardModel(),
   s => s.Players[0].PlayerCombatState!.Hand.Cards[0] = new Volibear_B03(),
   s => s.Players[0].PlayerCombatState!.Hand.Cards[0] = s.Players[0].PlayerCombatState!.Hand.Cards[2],
   s => s.Players[0].PlayerCombatState!.Hand.Cards[0].Affliction = new(),
   s => s.Players[0].PlayerCombatState!.DrawPile.Cards[0].Enchantment = new(),
   s => s.Players[0].Deck.Cards[0].Affliction = new(),
   s => s.Players[0].Deck.Cards[0].Enchantment = new(),
   s => s.Players[0].Deck.Cards[0] = new Volibear_B04(),
   s => s.Players[0].PlayerCombatState!.Other.Cards.Add(new Volibear_B01()),
   s => s.Players[0].PlayerCombatState = null
  ];
  foreach (var mutate in mutations) {
   var state = Fresh(); mutate(state); bool failed = false;
   try { NativeAcceptanceStarterFixture.Validate(state); } catch (InvalidOperationException) { failed = true; }
   Require(failed && CardPileCmd.Calls == 0, "invalid fixture accepted");
  }
  foreach (var transfer in new Func<CombatState,Task>[] { Face, Life }) {
   var state = Fresh(); var pcs = state.Players[0].PlayerCombatState!;
   var expected = pcs.DrawPile.Cards.Concat(pcs.Hand.Cards).ToArray();
   await transfer(state);
   Require(CardPileCmd.Calls == 1 && CardPileCmd.Visuals == 5 && CardPileCmd.Hooks == 5, "bulk count or flags changed");
   Require(pcs.Hand.Cards.Count == 0 && pcs.DrawPile.Cards.SequenceEqual(expected), "transfer order changed");
   for (int fault = 1; fault <= 3; fault++) {
    state = Fresh(); CardPileCmd.Failure = fault; bool failed = false;
    try { await transfer(state); } catch (InvalidOperationException) { failed = true; }
    Require(failed, "native transfer failure was accepted");
   }
  }
  Console.WriteLine($"STARTER_FIXTURE_PASS guards={mutations.Length} transfers=2 failures=6 native-gameplay=NOT_RUN");
 }
}
'''


class NativeStarterFixtureTests(unittest.TestCase):
    def build(self, runtime, *, run):
        with tempfile.TemporaryDirectory(prefix='starter-fixture-', dir=ROOT / '.local') as directory:
            folder = Path(directory)
            if run:
                face = FACE.read_text(encoding='utf-8').split('            NativeAcceptanceStarterFixture.Validate(state);', 1)[1].split('            var starterDrawOrder', 1)[0]
                life = LIFE.read_text(encoding='utf-8').split('                NativeAcceptanceStarterFixture.Validate(combat);', 1)[1].split('\n            }\n            else', 1)[0]
                blocks = ('static async Task Face(CombatState state) { var pcs = state.Players.Single().PlayerCombatState!; NativeAcceptanceStarterFixture.Validate(state);' + face + '}\n' +
                          'static async Task Life(CombatState combat) { var Pcs = combat.Players.Single().PlayerCombatState!; object? starterSetup; NativeAcceptanceStarterFixture.Validate(combat);' + life + '}')
                (folder / 'Program.cs').write_text(DOUBLES.replace('// SOURCE_BLOCKS', blocks), encoding='utf-8')
                items = '<Compile Include="' + escape(str(GUARD)) + '" />'
            else:
                source = ROOT / 'src/Volibear'
                items = '<Compile Include="' + escape(str(source / '**/*.cs')) + '" Exclude="' + escape(str(source / 'bin/**') + ';' + str(source / 'obj/**')) + '" />'
                for path in (runtime.data / 'sts2.dll', runtime.data / 'GodotSharp.dll', runtime.harmony, runtime.baselib):
                    items += '<Reference Include="' + escape(path.stem) + '"><HintPath>' + escape(str(path)) + '</HintPath></Reference>'
            project = folder / 'Starter.csproj'
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0</TargetFramework>'
                               '<Nullable>enable</Nullable><ImplicitUsings>enable</ImplicitUsings><NuGetAudit>false</NuGetAudit>'
                               f'<OutputType>{"Exe" if run else "Library"}</OutputType></PropertyGroup><ItemGroup>{items}</ItemGroup></Project>', encoding='utf-8')
            command = [str(runtime.dotnet), 'run', '--project', str(project)] if run else [str(runtime.dotnet), 'build', str(project)]
            result = subprocess.run([*command, '-c', 'Release', '--nologo'], cwd=ROOT, env=runtime.environment(),
                                    capture_output=True, text=True, encoding='utf-8', timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_guard_and_exact_probe_transfer_blocks(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        self.assertIn('STARTER_FIXTURE_PASS guards=19 transfers=2 failures=6 native-gameplay=NOT_RUN', self.build(runtime, run=True))

    def test_all_current_sources_compile_against_locked_native_api(self):
        runtime = fixture_runtime(self, 'sdk', 'native', 'harmony', 'baselib', root=ROOT)
        self.build(runtime, run=False)

    def test_only_initial_starters_are_batched_and_tested_paths_remain_native(self):
        face, life = (path.read_text(encoding='utf-8') for path in (FACE, LIFE))
        for source in (face, life):
            self.assertEqual(len(re.findall(r'CardPileCmd.Add\(starterHand\s*,\s*PileType.Draw\s*,\s*CardPilePosition.Bottom\)', source)), 1)
            self.assertIn('SequenceEqual(starterDestination)', source)
            self.assertIn('movedCount = starterMoves.Count', source)
            self.assertIn('skipVisuals = false', source)
            self.assertLess(source.index('NativeAcceptanceStarterFixture.Validate('), source.index('CardPileCmd.Add(starterHand'))
        self.assertIn('starterSetup,starterDrawOrder,before', face)
        self.assertIn('foreach (var card in pcs.DrawPile.Cards.ToArray()) await CardPileCmd.Add(card,PileType.Exhaust,skipVisuals:true);', face)
        self.assertIn('await CardPileCmd.Add(source,PileType.Hand);', face)
        self.assertIn('foreach (var card in pcs.DrawPile.Cards.Take(9).ToArray()) await CardPileCmd.Add(card,PileType.Hand);', face)
        self.assertEqual(life.count('untouchedStarter: true'), 1)
        self.assertIn('PrepareCombat(string label, bool untouchedStarter = false)', life)
        self.assertIn('await PrepareCombat("native-second-combat-isolation-no-power-reset");', life)
        self.assertIn('else\n                foreach (var card in Pcs.Hand.Cards.ToArray()) await CardPileCmd.Add(card, PileType.Draw, CardPilePosition.Bottom);', life)
        self.assertIn('await CardPileCmd.Add(card, pile, CardPilePosition.Top); return card;', life)
        self.assertIn('for (int i = 0; i < 32; i++) await Create(code == "U25" ? "B01" : "B02", pile: PileType.Draw);', life)
        self.assertIn('starterSetup = starterReceipt?.Invoke()', life)


if __name__ == '__main__':
    unittest.main()
