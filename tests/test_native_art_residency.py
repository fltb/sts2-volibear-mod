"""Read-only resource lease: linked-source doubles + actual GodotSharp API compile, not gameplay."""
from pathlib import Path
import json
import re
import struct
import subprocess
import tempfile
import unittest
from xml.sax.saxutils import escape

from tools.runtime_test import fixture_runtime

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/Volibear/NativeAcceptanceArtResidency.cs'

DOUBLES = r'''
using System;
using System.Collections.Generic;
using System.Linq;
namespace Godot {
 public class GodotObject {
  static ulong next; public ulong Id = ++next; public bool Valid = true;
  public ulong GetInstanceId() => Id;
  public static bool IsInstanceValid(GodotObject obj) => obj != null && obj.Valid;
 }
 public class Resource : GodotObject {
  private string path = ""; public int PathReads;
  public string ResourcePath { get { PathReads++; return path; } set { path = value; } }
 }
 public sealed class StringName(string value) : IDisposable {
  public override string ToString() => value; public void Dispose() {}
 }
 public readonly record struct Vector2(float X, float Y);
 public readonly record struct Rect2(Vector2 Position, Vector2 Size);
 public readonly record struct Rid(ulong Id);
 public class Texture2D : Resource {}
 public class CompressedTexture2D : Texture2D {
  public int Width = 512, Height = 512; public ulong RidId = 1;
  public int WidthReads, HeightReads, RidReads;
  public int GetWidth() { WidthReads++; return Width; }
  public int GetHeight() { HeightReads++; return Height; }
  public Rid GetRid() { RidReads++; return new(RidId); }
 }
 public class AtlasTexture : Texture2D {
  private Texture2D? atlas; private Rect2 region, margin; private bool filter = true;
  public int AtlasReads, RegionReads, MarginReads, FilterReads;
  public Texture2D? Atlas { get { AtlasReads++; return atlas; } set { atlas = value; } }
  public Rect2 Region { get { RegionReads++; return region; } set { region = value; } }
  public Rect2 Margin { get { MarginReads++; return margin; } set { margin = value; } }
  public bool FilterClip { get { FilterReads++; return filter; } set { filter = value; } }
 }
 public class SpriteFrames : Resource {
  public string[] Names = ["idle_loop"]; public bool Loop = true; public double Speed = 24, Duration = 1;
  public List<Texture2D> Textures = new();
  public Dictionary<string, List<Texture2D>> ByAnimation = new();
  public Dictionary<(string, int), double> Durations = new();
  public int DurationReads, TextureReads;
  private List<Texture2D> For(StringName name) => ByAnimation.GetValueOrDefault(name.ToString(), Textures);
  public string[] GetAnimationNames() => (string[])Names.Clone();
  public int GetFrameCount(StringName name) => For(name).Count;
  public bool GetAnimationLoop(StringName name) => Loop;
  public double GetAnimationSpeed(StringName name) => Speed;
  public double GetFrameDuration(StringName name, int index) { DurationReads++; return Durations.GetValueOrDefault((name.ToString(), index), Duration); }
  public Texture2D GetFrameTexture(StringName name, int index) { TextureReads++; return For(name)[index]; }
 }
 public static class ResourceLoader {
  public static Resource? Cached, EffectsCached; public static int Calls;
  public static Resource? GetCachedRef(string path) {
   Calls++;
   if (path == Volibear.NativeAcceptanceArtResidency.FramesPath) return Cached;
   if (path == Volibear.NativeAcceptanceArtResidency.EffectsFramesPath) return EffectsCached;
   throw new Exception("unexpected lookup");
  }
 }
 public static class GD { public static List<string> Messages = new(); public static void Print(string text) => Messages.Add(text); }
}
namespace Godot.Collections {
 public sealed class Array<T> {
  public static Array<T>? Last; public Array() { Last = this; }
  private readonly List<T> values = new(); public int Count => values.Count;
  public T this[int index] => values[index]; public void Add(T value) => values.Add(value);
  public void Clear() => values.Clear();
 }
}
'''
PROGRAM = r'''
internal static class Program {
 static int checks;
 static void Check(bool value) { checks++; if (!value) throw new Exception("assertion " + checks); }
 static Godot.SpriteFrames Fresh(bool effects = false) {
  var atlas = new Godot.CompressedTexture2D { ResourcePath = "res://VolibearArt/animations/atlases/idle_loop.png" };
  var frames = new Godot.SpriteFrames { ResourcePath = Volibear.NativeAcceptanceArtResidency.FramesPath };
  frames.Textures.Add(new Godot.AtlasTexture { Atlas = atlas }); Godot.ResourceLoader.Cached = frames;
  var fx = new Godot.SpriteFrames { ResourcePath = Volibear.NativeAcceptanceArtResidency.EffectsFramesPath };
  fx.Textures.Add(new Godot.AtlasTexture { Atlas = new Godot.CompressedTexture2D {
   ResourcePath = "res://VolibearArt/vfx/atlases/claw_slash.png" } });
  Godot.ResourceLoader.EffectsCached = fx;
  return effects ? fx : frames;
 }
 static void SetCached(Godot.SpriteFrames frames, Godot.Resource? value) {
  if (frames.ResourcePath == Volibear.NativeAcceptanceArtResidency.EffectsFramesPath) Godot.ResourceLoader.EffectsCached = value;
  else Godot.ResourceLoader.Cached = value;
 }
 static bool Rejected(Action action) { try { action(); return false; } catch (InvalidOperationException) { return true; } }
 static void Bound(Action<Godot.SpriteFrames> mutate, bool effects = false) {
  var frames = Fresh(effects); mutate(frames);
  Check(Rejected(() => new Volibear.NativeAcceptanceArtResidency()));
  Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 0);
 }
 static void Main() {
  var unchanged = Fresh(); var unchangedEffects = Godot.ResourceLoader.EffectsCached;
  int before = Godot.ResourceLoader.Calls;
  var good = new Volibear.NativeAcceptanceArtResidency();
  Check(Godot.ResourceLoader.Calls == before + 2);
  Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 2);
  good.Validate(); good.Validate(); good.Dispose(); good.Dispose();
  Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 0);
  Check(Rejected(good.Validate)); Check(Godot.ResourceLoader.Cached == unchanged);
  Check(Godot.GD.Messages.Any(m => m.Contains("estimateNotGpuMeasurement=true")));
  Check(Godot.GD.Messages.Last().Contains("released held=0"));
  Check(Godot.GD.Messages.Last().Contains("captureCalls=4"));
  Check(Godot.GD.Messages.Last().Contains("captureTotalMs=") && Godot.GD.Messages.Last().Contains("captureMaxMs="));
  Check(Godot.ResourceLoader.EffectsCached == unchangedEffects);
  Check(Godot.GD.Messages.Any(m => m.Contains("acquired template=effects")));
  Check(Godot.GD.Messages.Any(m => m.Contains("released held=0 template=actor")));
  Action<Godot.SpriteFrames>[] mutations = [
   f => f.Id++, f => f.ResourcePath += "changed", f => f.Valid = false,
   f => f.Names = ["changed"], f => f.Loop = false, f => f.Speed++, f => f.Duration++,
   f => f.Textures.Add(f.Textures[0]), f => f.Textures[0].Id++, f => f.Textures[0].ResourcePath += "changed",
   f => ((Godot.AtlasTexture)f.Textures[0]).Region = new(new(1, 2), new(3, 4)),
   f => ((Godot.AtlasTexture)f.Textures[0]).Margin = new(new(1, 2), new(3, 4)),
   f => ((Godot.AtlasTexture)f.Textures[0]).FilterClip = false,
   f => ((Godot.AtlasTexture)f.Textures[0]).Atlas!.Id++,
   f => ((Godot.AtlasTexture)f.Textures[0]).Atlas!.ResourcePath = f.ResourcePath == Volibear.NativeAcceptanceArtResidency.EffectsFramesPath ?
     "res://VolibearArt/vfx/atlases/guard_hit.png" : "res://VolibearArt/animations/atlases/attack.png",
   f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Width++,
   f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Height++,
   f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).RidId++,
   f => SetCached(f, new Godot.SpriteFrames { ResourcePath = f.ResourcePath }),
   f => SetCached(f, null),
   f => ((Godot.AtlasTexture)f.Textures[0]).Atlas = new Godot.Texture2D(),
  ];
  foreach (bool effects in new[] { false, true })
  foreach (var mutate in mutations) {
   var frames = Fresh(effects); var scope = new Volibear.NativeAcceptanceArtResidency(); mutate(frames);
   Check(Rejected(scope.Validate)); Check(Rejected(scope.Dispose));
   Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 0); scope.Dispose();
  }
  Bound(f => Godot.ResourceLoader.Cached = null);
  Bound(f => f.Names = Enumerable.Range(0, 65).Select(n => n.ToString()).ToArray());
  Bound(f => f.Names = []);
  Bound(f => f.Names = ["same", "same"]);
  Bound(f => f.Textures.Clear());
  Bound(f => { var texture = f.Textures[0]; f.Textures = Enumerable.Repeat(texture, 2049).ToList(); });
  Bound(f => { var atlas = ((Godot.AtlasTexture)f.Textures[0]).Atlas;
   f.Textures = Enumerable.Range(0, 1025).Select(_ => (Godot.Texture2D)new Godot.AtlasTexture { Atlas = atlas }).ToList(); });
  Bound(f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Width = 4097);
  Bound(f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Height = 0);
  Bound(f => ((Godot.AtlasTexture)f.Textures[0]).Atlas!.ResourcePath = "res://foreign.png");
  Bound(f => { f.Textures.Clear(); for (int i = 0; i < 33; i++) f.Textures.Add(new Godot.AtlasTexture {
   Atlas = new Godot.CompressedTexture2D { ResourcePath = "res://VolibearArt/animations/atlases/idle_loop.png" }}); });
  Bound(f => { f.Textures.Clear(); for (int i = 0; i < 22; i++) f.Textures.Add(new Godot.AtlasTexture {
   Atlas = new Godot.CompressedTexture2D { Width = 4096, Height = 4096,
    ResourcePath = "res://VolibearArt/animations/atlases/idle_loop.png" }}); });
  Bound(f => Godot.ResourceLoader.EffectsCached = null, true);
  Bound(f => Godot.ResourceLoader.EffectsCached = new Godot.Texture2D(), true);
  Bound(f => f.ResourcePath = Volibear.NativeAcceptanceArtResidency.FramesPath, true);
  Bound(f => f.Names = Enumerable.Range(0, 65).Select(n => n.ToString()).ToArray(), true);
  Bound(f => f.Textures = Enumerable.Repeat(f.Textures[0], 2049).ToList(), true);
  Bound(f => { var atlas = ((Godot.AtlasTexture)f.Textures[0]).Atlas;
   f.Textures = Enumerable.Range(0, 1537).Select(_ => (Godot.Texture2D)new Godot.AtlasTexture { Atlas = atlas }).ToList(); }, true);
  Bound(f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Width = 2049, true);
  Bound(f => ((Godot.CompressedTexture2D)((Godot.AtlasTexture)f.Textures[0]).Atlas!).Height = 0, true);
  Bound(f => ((Godot.AtlasTexture)f.Textures[0]).Atlas!.ResourcePath = "res://foreign.png", true);
  Bound(f => { f.Textures.Clear(); for (int i = 0; i < 49; i++) f.Textures.Add(new Godot.AtlasTexture {
   Atlas = new Godot.CompressedTexture2D { ResourcePath = "res://VolibearArt/vfx/atlases/claw_slash.png" }}); }, true);
  Bound(f => { f.Textures.Clear(); for (int i = 0; i < 22; i++) f.Textures.Add(new Godot.AtlasTexture {
   Atlas = new Godot.CompressedTexture2D { Width = 2048, Height = 2048,
    ResourcePath = "res://VolibearArt/vfx/atlases/claw_slash.png" }}); }, true);
  // Each template fits its own budget, but together they exceed the unchanged 2GiB ceiling.
  Bound(f => {
   f.Textures = Enumerable.Range(0, 20).Select(_ => (Godot.Texture2D)new Godot.AtlasTexture {
    Atlas = new Godot.CompressedTexture2D { Width = 4096, Height = 4096,
     ResourcePath = "res://VolibearArt/animations/atlases/idle_loop.png" }}).ToList();
   var fx = (Godot.SpriteFrames)Godot.ResourceLoader.EffectsCached!;
   fx.Textures = Enumerable.Range(0, 10).Select(_ => (Godot.Texture2D)new Godot.AtlasTexture {
    Atlas = new Godot.CompressedTexture2D { Width = 2048, Height = 2048,
     ResourcePath = "res://VolibearArt/vfx/atlases/claw_slash.png" }}).ToList();
  });
  foreach (bool effects in new[] { false, true }) {
  var shared = Fresh(effects); shared.Names = ["idle_loop", "alias"];
  var first = (Godot.AtlasTexture)shared.Textures[0];
  var baseAtlas = (Godot.CompressedTexture2D)first.Atlas!; first.AtlasReads = 0;
  var second = new Godot.AtlasTexture { Atlas = baseAtlas }; shared.Textures.Add(second);
  var sharedScope = new Volibear.NativeAcceptanceArtResidency();
  for (int captures = 1; captures <= 3; captures++) {
   Check(shared.DurationReads == captures * 4 && shared.TextureReads == captures * 4);
   foreach (var texture in new[] { first, second }) {
    Check(texture.PathReads == captures);
    Check(texture.AtlasReads == captures && texture.RegionReads == captures &&
          texture.MarginReads == captures && texture.FilterReads == captures);
   }
   Check(baseAtlas.PathReads == captures && baseAtlas.WidthReads == captures &&
         baseAtlas.HeightReads == captures && baseAtlas.RidReads == captures);
   if (captures < 3) sharedScope.Validate();
  }
  sharedScope.Dispose();
  Check(Godot.GD.Messages.Last().Contains("captureCalls=4"));
  Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 0);
  }
  foreach (bool effects in new[] { false, true })
  foreach (bool changeDuration in new[] { true, false }) {
   var aliased = Fresh(effects); aliased.Names = ["idle_loop", "alias"];
   aliased.Textures.Add(new Godot.AtlasTexture { Atlas = ((Godot.AtlasTexture)aliased.Textures[0]).Atlas });
   var aliasScope = new Volibear.NativeAcceptanceArtResidency();
   if (changeDuration) aliased.Durations[("idle_loop", 1)] = 2;
   else aliased.ByAnimation["idle_loop"] = aliased.Textures.AsEnumerable().Reverse().ToList();
   Check(Rejected(aliasScope.Validate)); Check(Rejected(aliasScope.Dispose));
   Check(Godot.Collections.Array<Godot.SpriteFrames>.Last!.Count == 0);
  }
  Console.WriteLine($"NATIVE_ART_RESIDENCY_DOUBLES_PASS assertions={checks} native-gameplay=NOT_RUN");
 }
}
'''


class NativeArtResidencyTests(unittest.TestCase):
    def build(self, runtime, *, run):
        (ROOT / '.local').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='art-lease-', dir=ROOT / '.local') as directory:
            folder = Path(directory)
            references = '' if run else ('<Reference Include="GodotSharp"><HintPath>' +
                                         escape(str(runtime.data / 'GodotSharp.dll')) + '</HintPath></Reference>')
            (folder / 'Lease.csproj').write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
                f'<OutputType>{"Exe" if run else "Library"}</OutputType>'
                '<TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable><NuGetAudit>false</NuGetAudit>'
                '</PropertyGroup><ItemGroup>' + references + '<Compile Include="' + escape(str(SOURCE)) +
                '" Link="NativeAcceptanceArtResidency.cs" /></ItemGroup></Project>', encoding='utf-8')
            if run:
                (folder / 'Program.cs').write_text(DOUBLES + PROGRAM, encoding='utf-8')
            result = subprocess.run([str(runtime.dotnet), 'run' if run else 'build',
                                     '--project' if run else str(folder / 'Lease.csproj'),
                                     *([str(folder / 'Lease.csproj')] if run else []), '-c', 'Release', '--nologo'],
                                    cwd=ROOT, env=runtime.environment(), capture_output=True,
                                    text=True, encoding='utf-8', timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_all_resource_fields_mutations_bounds_and_finally_clear(self):
        runtime = fixture_runtime(self, 'sdk', root=ROOT)
        output = self.build(runtime, run=True)
        self.assertIn('NATIVE_ART_RESIDENCY_DOUBLES_PASS assertions=238 native-gameplay=NOT_RUN', output)

    def test_complete_source_compiles_against_real_godotsharp(self):
        runtime = fixture_runtime(self, 'sdk', 'native', root=ROOT)
        self.build(runtime, run=False)

    def test_exact_cache_only_scope_and_no_native_resource_mutations(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('Godot.Collections.Array<SpriteFrames> held', source)
        self.assertEqual(source.count('ResourceLoader.GetCachedRef(FramesPath)'), 2)
        self.assertEqual(source.count('ResourceLoader.GetCachedRef(EffectsFramesPath)'), 2)
        self.assertIn('held.Count != 2', source)
        for forbidden in ('ResourceLoader.Load', 'GetDependencies', '.Instantiate(', '.Dispose();',
                          'AssetCache', 'SetFrame', 'SetAnimation', 'AddFrame', 'Image.Create', 'GetImage('):
            self.assertNotIn(forbidden, source)
        self.assertIn('finally\n        {\n            held.Clear();', source)
        self.assertIn('2L * 1024 * 1024 * 1024', source)

    def test_fixed_effects_allowlist_and_budgets_match_approved_inputs(self):
        source = SOURCE.read_text(encoding='utf-8')
        block = source.split('EffectsAtlasPaths = new(new[] {', 1)[1].split('}.Select', 1)[0]
        allowed = set(re.findall(r'"([a-z_]+)"', block))
        effects = json.loads((ROOT / 'assets/animation/vfx/manifest.json').read_text(encoding='utf-8'))['effects']
        self.assertEqual(len(effects), 40)
        self.assertEqual(sum(effect['frame_count'] for effect in effects), 1070)
        self.assertEqual({effect['atlas']['image'] for effect in effects},
                         {'atlases/' + name + '.png' for name in allowed})
        estimates = []
        for effect in effects:
            with (ROOT / 'assets/animation/vfx' / effect['atlas']['image']).open('rb') as stream:
                header = stream.read(24)
            self.assertEqual(header[:8], b'\x89PNG\r\n\x1a\n')
            width, height = struct.unpack('>II', header[16:24])
            self.assertEqual(width, 2048)
            self.assertLessEqual(height, 1536)
            estimates.append(width * height * 6)
        self.assertEqual(sum(estimates), 459276288)
        self.assertLess(sum(estimates), 512 * 1024 * 1024)
        self.assertLess(1522532352 + sum(estimates), 2 * 1024 * 1024 * 1024)
        script = (ROOT / 'src/Volibear/Presentation/effects.gd').read_text(encoding='utf-8')
        uses = [line.strip() for line in script.splitlines() if re.search(r'\b_frames\b', line)]
        self.assertEqual(uses, ['var _frames: SpriteFrames',
                              '_frames = load("res://VolibearArt/scenes/volibear_effect_frames.tres")',
                              'sprite.sprite_frames = _frames'])


if __name__ == '__main__':
    unittest.main()
