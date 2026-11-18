# Mod compatibility and load order

## Player-facing behavior

Volibear declares BaseLib as a normal dependency. BaseLib must be available before
Volibear initializes; unrelated mods may appear between them. Current source builds
do not require Load Order Manager or an “immediately after BaseLib” position.

This source change does not replace an already downloaded release or update a Steam
Workshop subscription. Builds published before this change can still contain the
old ordering behavior. The PBE dependency remains BaseLib 3.4.8, including the
BaseLibCompatibilityHelper files distributed by BaseLib itself. That helper is an
API compatibility bridge, not a mod sorter.

No mod-list settings, other mods' manifests, framework model caches, save files, or
foreign Harmony patches are rewritten by this change.

## What was wrong

The previous README prescribed a global load-order workaround. Inspection of
`bb06bb1` found two independent problems in Volibear:

1. Most native IL adapters used Harmony's default ordering. When an unrelated
   transpiler was registered first, these adapters saw already modified input.
   Several matchers also required exact adjacent instruction positions: even an
   unlabelled `nop` could make an otherwise valid summon or debuff method fail
   initialization. A failure in an essential gameplay module stopped initialization.
2. `VolibearTrailFactory` inherited `NodeFactory<NCardTrailVfx>`. Constructing this
   generic BaseLib factory replaced the shared factory for that native node type,
   even though Volibear intended to adapt only its own scene. Another character
   mod and Volibear could overwrite each other's factory in either load order.

These are confirmed source-level coexistence defects. The original user's failing
mod set and game log were not available for this change, so no particular foreign
mod is identified as the unique trigger of that report.

## Implementation

### Local Harmony ordering

Production transpiler installations go through `Core/NativeTranspiler.cs`.
Unspecified priorities use `Priority.High`, and the adapters declare that they run
after the `BaseLib` Harmony owner. Existing explicit priorities and `before` / `after`
constraints remain intact, including the internal `Priority.Last` chains and the
minimum-priority async entry wrapper. Prefixes, postfixes, and finalizers retain
their original metadata.

For an unspecified-priority adapter, ordinary-priority foreign owners already
registered on that same method are added to its local `before` constraint. This
also handles an unrelated mod registering before BaseLib. Owners explicitly named
in `after`, Volibear's own owners, and owners with non-normal priorities or a
contrary declared dependency are excluded; cycle-producing constraints are not added. No foreign priority is changed,
and the game's mod discovery order is untouched.

The fixed-position summon, Hopper, Dampen, passive, and debuff commit matchers
ignore only `nop` instructions with neither branch labels nor exception markers.
They clone retained instructions, keep labelled/exception-bearing nodes in place,
and still reject missing or ambiguous gameplay operations. A genuinely conflicting
replacement is reported; it is not silently accepted as a working gameplay hook.

Failed installations report the target method, Volibear Harmony owner, existing
transpiler owners/priorities, and the original exception. Normal initialization
logs also identify the failing module. Diagnostic mode can collect all module
failures, but it must throw after the summary instead of printing a false `LOAD_OK`.

### Scene-scoped trail conversion

The trail adapter no longer creates or registers a BaseLib factory. A postfix on
the non-generic `PackedScene.Instantiate(GenEditState)` overload checks the exact
Volibear trail resource path. It leaves every foreign scene and every result that
is already an `NCardTrailVfx` unchanged.

Before replacing its own scene root, it validates the `Node2D` / `Sprites` contract.
It preserves the original child instances and ownership, visual transforms and
properties, internal-node order, metadata, and groups. The native trail class
continues to own following, fading, and cleanup. No animation clips, textures,
audio, card balance, or combat rules are changed here.

## Verification

Focused regression on 2026-11-18: **42 Python tests, 40 passed, 2 skipped**.
The new tests include **13 independent real-Harmony processes** and **two real
Godot processes** (foreign-first and Volibear-first). The three registration orders
that satisfy the BaseLib dependency — BaseLib/Volibear/foreign,
BaseLib/foreign/Volibear, and foreign/BaseLib/Volibear — produced the same result
and preserved both mods' observable effects.

The skipped checks were the native UI ABI/patch-installation fixture and native
history/IL fixture; both require the unavailable installed game assemblies.
Full production compilation and actual game acceptance remain **NOT_RUN**.

The focused checks distinguish actual engine/library execution from missing game
validation:

| Check | Execution boundary |
| --- | --- |
| Native transpiler ordering | Real Harmony 2.4.2 detours and generated IL, production compatibility helper; no simulated game assembly |
| Trail coexistence | Real Godot 4.5.1 Mono and Harmony; the game's `NCardTrailVfx` is an explicitly identified test double |
| Existing interoperability and UI tests | Existing production-linked fixtures, preserving their original test-double/native boundaries |
| Full PBE mod compilation | Requires the installed `sts2.dll` and related game assemblies |
| Actual multi-mod game boot, combat, save/load, multiplayer | Requires the installed game and the real mod combination |

With the SDK, Harmony, and Godot configured through the repository's existing local
runtime settings, run the focused regression:

```bash
python -m unittest tests.test_native_transpiler tests.test_trail_compatibility \
  tests.test_domain_interop tests.test_power_stack_visual \
  tests.test_supported_game tests.test_history_contracts \
  tests.test_runtime_test tests.test_dependencies -q
```

Missing native prerequisites are reported as skipped, not passed. Build the actual
PBE package with `python tools/build_pbe_release.py` after configuring the installed
game as described in the README. The game-level matrix should cover:

- BaseLib + Volibear, without a sorting mod.
- BaseLib + ordinary gameplay/UI mods + Volibear.
- BaseLib + Volibear + the same gameplay/UI mods.
- An unrelated mod before BaseLib, followed by Volibear.
- A second character with its own card-trail factory, in both relative orders.
- Character selection, card play, summon/debuff suppression, save/continue, and
  multiplayer with matching mod versions.

For a remaining real collision, `VOLIBEAR_COMPAT_DIAG=1` prints all initialization
failures in one launch. It does not bypass a failed gameplay hook. The normal log
already contains the method and owner information needed to investigate a conflict.

## Upstream evidence

- [Harmony priorities](https://harmony.pardeike.net/v2/articles/priorities.html):
  patch execution order is independent of whole-mod load order.
- [Harmony transpilers](https://harmony.pardeike.net/v2/articles/patching-transpiler.html):
  transpilers are recomposed when other patches are added; fixed counts and rigid
  structures make coexistence brittle.
- [BaseLib v3.4.8 NodeFactory](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Utils/NodeFactories/NodeFactory.cs):
  the generic constructor writes the shared factory slot for its target type.
- [BaseLib v3.4.8 initialization](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Patches/PostModInitPatch.cs):
  the historic first-gameplay-mod early-exit bug is already fixed. The official
  release DLL was checked as well; this change does not patch that obsolete bug.
- [BaseLib v3.4.8 release](https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.8):
  documents the framework's separate compatibility helper and five-file package.

The BaseLib release archive used for inspection matched the repository's pinned
SHA-256 `ad30d8aa4dee8e5d31150ab75eae6e6b927fa83ce30af93f4b2a144c3b09f82f`.
