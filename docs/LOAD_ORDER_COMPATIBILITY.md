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

The game already sorts declared dependencies when the saved mod order violates
them. A `BaseLib` dependency means “after BaseLib”, not “first after BaseLib”.
Load Order Manager changes the saved list for the next launch; it cannot resolve
two transpilers which replace the same native operation. Unsupported shared-call replacements are reported with their concrete target and
patch owners. Volibear does not maintain per-mod replacement bridges or a name-based
compatibility allowlist.

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
3. The subsequent community audit found a concrete shared-call conflict with
   RitsuLib 0.6.14. Both frameworks replaced the `CreatureCmd.Damage` call inside
   `AttackCommand.Execute.MoveNext`. RitsuLib requires its own exact awaited
   producer and uses `Priority.Last`. Raising Volibear's priority merely made
   RitsuLib lose that anchor instead. This requires cooperation at the callsite,
   not a different whole-mod order.

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

### Preserve shared observation points

Attack history now inserts observations around `Hook.BeforeCardPlayed` and
`Hook.AfterCardPlayed` while retaining the actual native calls. Arguments are
evaluated once; the native after-hook Task is awaited before refreshing hand
costs. Branch labels and exception boundaries are preserved. These observers use
explicit normal priority rather than the default ordering for strict adapters.
They do not claim compatibility with an unknown replacement that removes the
underlying operation entirely.

The status-stack UI adapter activates only for containers/nodes with powers that
Volibear actually projects. A purely native or foreign container keeps its original
list and receives no Volibear layout/state subscription. Mixed containers keep
foreign nodes native. Removing the last relevant power releases Volibear's active
subscriptions and hidden-node state. Its layout IL keeps the `_powerNodes` field
read so another UI transpiler can still find that shared anchor, and projects the
list actually produced there rather than rereading a separate list.

This scope reduction applies to `PowerStackVisual`; it is not a claim that every
presentation hook in the mod has become conditional. In particular, the separate
domain-suppression badge still observes native state changes so it can become
visible when a domain is acquired later in combat.

### Capability detection, not per-mod exceptions

The community audit is used to identify general failure modes, not to add
third-party-specific execution paths. No RitsuLib adapter is installed. The attack
replacement conflict described above remains an unsupported combination until the
shared native operation can be composed without changing either mod's semantics.
A mod's name or presence alone is not sufficient to declare it incompatible.

At the post-mod localization stage, a read-only snapshot lists methods patched by
both Volibear and another assembly, with patch kinds, owners, method signatures,
assembly versions, priorities and before/after declarations. These entries are
`shared_unverified`, not incompatibility verdicts. The snapshot reads committed
Harmony metadata only: it neither rewrites foreign patches nor reruns transpilers.
Failure to collect the snapshot is logged as `COMPAT_SCAN_ERROR` without turning
the reporting feature into a new game-loading dependency.

The complete-log report includes errors from mods loaded after Volibear. This
matters because a transpiler that fails during IL generation is not committed to
Harmony's patch metadata; inspecting only the surviving chain would miss the
rejected patch. Generic optional/critical patch failure blocks retain their
description, original error and stack context. There is no framework-name filter.

Read an existing log without launching or modifying the game:

```bash
python tools/compat_report.py --log /path/to/godot.log --json compatibility.json
```

Or run the existing isolated diagnostic boot against an installed game:

```bash
python tools/compat_report.py --game-dir /path/to/SlayTheSpire2 --json compatibility.json
```

| Report status | Meaning |
| --- | --- |
| `unsupported` | The supplied startup log reports a concrete patch/load/API/dependency failure. `failure_details` retains the target, owner, other transpilers and original cause when the log contains them. |
| `initialization_passed` | Required startup markers and a complete closing `COMPAT_SCAN` are present, and no recognized initialization/patch failures appear in that log. This does not certify gameplay or every foreign feature. |
| `inconclusive` | Required evidence is absent, the log is truncated, metadata collection/installation failed, or startup sessions cannot be separated reliably. |

`LOAD_OK` is evidence only of Volibear's entrypoint. A shared target is not itself
a failure, and a foreign mod may catch or silently suppress its own patch error.
No log parser can infer such an unreported failure. The report therefore keeps
startup evidence, shared metadata, and gameplay acceptance as separate facts.
When a file contains several Godot process banners, only its latest startup is
evaluated. Multiple Volibear starts without a reliable process boundary remain
inconclusive; an old `LOAD_OK` cannot complete a later interrupted launch. Zero
patch-failure summaries and ordinary UI state changes are not treated as errors.

The supported boundary is capability based:

| Situation | Handling |
| --- | --- |
| BaseLib available, with unrelated mods between it and Volibear | Normal manifest dependency and local patch constraints; no required adjacency. |
| Additive observers, foreign prefixes/postfixes, harmless unmarked NOP padding | Preserve native calls/field reads where the adapter is observational; targeted fixtures verify coexistence. |
| Missing native API, lost/ambiguous required callsite, incompatible contribution rewrite | Keep the failure visible, identifying the method and patch chain. Do not silently disable a core mechanic. |
| A different mod reports a failed patch after Volibear initializes | Full-log report rejects the startup even if Volibear emitted `LOAD_OK`. |
| Two mods share a target, but no failure is reported | Record the owners and mark the overlap unverified; do not block by mod name. |

For the inspected RitsuLib 0.6.14 per-hit patch, the collision is specifically the
same awaited `CreatureCmd.Damage` producer. That implementation is presently
unsupported alongside Volibear's attack adapter. This is not a statement that
RitsuLib and BaseLib are intrinsically incompatible, nor a permanent ban on every
version of RitsuLib. No special-case RitsuLib code is shipped.

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

Focused regression on 2026-11-18 after the community audit:
**61 Python tests, 59 passed, 2 skipped** (49.520 seconds).
The transpiler tests run **18 independent real-Harmony processes**; metadata
snapshot tests run **four more independent real-Harmony processes**. The status UI
fixture passed **83 behavioral assertions**, plus **two same-field interoperability
processes with 16 assertions each**. Trail checks use **two real Godot processes**
(foreign-first and Volibear-first). The three registration orders
that satisfy the BaseLib dependency — BaseLib/Volibear/foreign,
BaseLib/foreign/Volibear, and foreign/BaseLib/Volibear — produced the same result
and preserved both mods' observable effects.

The call-observation cases cover actual shared native callsites in both relative
orders, argument evaluation exactly once, asynchronous success/failure/cancellation,
synchronous throws, branch labels and real try/catch/finally execution. The field
tests retain another adapter's list filtering/reordering as well as its anchor.
The metadata cases also reproduce a rejected later transpiler that is absent from
committed metadata, without replaying any foreign transpiler or patch factory.
Seventeen log-report tests cover late optional failures, complete error details,
zero-failure messages, metadata errors, truncation, and multiple startup sessions.

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
| Shared-target metadata | Real Harmony 2.4.2 and a separate foreign fixture assembly; no game API doubles, no transpiler replay |
| Complete-log report | Synthetic startup evidence and actual CLI execution; no game boot is inferred from these parser tests |
| Full PBE mod compilation | Requires the installed `sts2.dll` and related game assemblies |
| Actual multi-mod game boot, combat, save/load, multiplayer | Requires the installed game and the real mod combination |

With the SDK, Harmony, and Godot configured through the repository's existing local
runtime settings, run the focused regression:

```bash
python -m unittest tests.test_native_transpiler tests.test_trail_compatibility \
  tests.test_domain_interop tests.test_power_stack_visual \
  tests.test_supported_game tests.test_history_contracts \
  tests.test_runtime_test tests.test_dependencies \
  tests.test_patch_compatibility_snapshot tests.test_compat_report -q
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

### Community source audit, 2026-11-18

These are inspected source revisions, **not a claim that their complete released
packages were tested together in the game**. Some repositories support multiple
game branches; the installed binaries must target the same game API as Volibear.

| Source | Revision inspected | Relevant finding |
| --- | --- | --- |
| [BaseLib](https://github.com/Alchyr/BaseLib-StS2/tree/v3.4.8) | 3.4.8, `6fc4adb` | Content registration runs after mod initializers. The old first-gameplay-mod early-exit defect is already fixed. Generic node-factory registration has one shared slot per native type. |
| [RitsuLib](https://github.com/BAKAOLC/STS2-RitsuLib/tree/12976e831495e505380b924e680dfbcc6f5cca01) | 0.6.14, `12976e8` | Its per-hit attack transpiler replaces the same native damage call. Its card-play lifecycle extensions observe the native hooks; its hand-size extension uses a different draw-method anchor. |
| [Runesmith2](https://github.com/Blizzarre/Runesmith2-StS2/tree/308b9423ac55cedc15304ee5e1dd17713fe7199b) | 0.7.7, `308b942` | Its card-play transpiler inserts element-cost cleanup after the native target setter and retains the original call. Sharing a method does not itself imply a conflict. |
| [Marisa](https://github.com/lf201014/STS2_MarisaMod/tree/7d04b1ba4697c6fa0d6fea8fb1d8c9812ddf159f) | 0.4.2, `7d04b1b` | Charge-up power uses model `BeforeCardPlayed`/`AfterCardPlayed` overrides. These depend on the native hook dispatch remaining intact. |
| [MzmChar](https://github.com/FFTYYY/sts2-MzmChar-mod/tree/435a3a7980af23c9099b0b1ae0564c6e0aa5670f) | manifest 0.2.9, `435a3a7` | Model hooks and per-play weak-table counters handle nested plays without replacing our two native hook callsites. |
| [MeiLin](https://github.com/happyone13/MeiLinMod-sts2/tree/00931da8035cf5b7f1d6cbdd728dd6a88cd4d652) | 0.4.0, `00931da` | RitsuLib-based character; its battle-ready overlay observes `Hook.BeforeCardPlayed` with a prefix. |
| [Load Order Manager](https://github.com/Jianbao233/STS2-LoadOrderManager/tree/52d94eb30b44a993650dd389f178a5a9ddfc95d7) | 0.4.0 | Persists mod-list ordering for the next launch; it is not an implementation-level compatibility bridge. |

The first attack collision is visible in
[RitsuLib's transpiler](https://github.com/BAKAOLC/STS2-RitsuLib/blob/12976e831495e505380b924e680dfbcc6f5cca01/src/Combat/AttackHits/Patches/AttackCommandExecuteHitHookPatch.cs)
and its
[real dispatch implementation](https://github.com/BAKAOLC/STS2-RitsuLib/blob/12976e831495e505380b924e680dfbcc6f5cca01/src/Combat/AttackHits/AttackHitHook.cs).
Its await matcher identifies the nearest Task producer, so simply leaving a native
call and adding another Task-producing call after it is not enough for this case.
The Runesmith example is in
[CardModelPatches.cs](https://github.com/Blizzarre/Runesmith2-StS2/blob/308b9423ac55cedc15304ee5e1dd17713fe7199b/Runesmith2Code/Patches/CardModelPatches.cs).

- [Official game loader changes](https://store.steampowered.com/news/app/2868840/view/502852451136701666):
  manifests declare dependencies; incompatible saved ordering triggers a re-sort.
- [BaseLib author's modding guide](https://github.com/Alchyr/ModTemplate-StS2/wiki/Modding-Basics):
  prefer native commands and model hooks, and match the target game branch.

- [Harmony priorities](https://harmony.pardeike.net/v2/articles/priorities.html):
  patch execution order is independent of whole-mod load order.
- [Harmony transpilers](https://harmony.pardeike.net/v2/articles/patching-transpiler.html):
  transpilers are recomposed when other patches are added; fixed counts and rigid
  structures make coexistence brittle.
- [Harmony 2.4.2 patch installation](https://github.com/pardeike/Harmony/blob/a264a1bf1ce689e4589e8dcc54b1e2818602a90a/Harmony/Public/PatchProcessor.cs)
  and [shared metadata](https://github.com/pardeike/Harmony/blob/a264a1bf1ce689e4589e8dcc54b1e2818602a90a/Harmony/Internal/HarmonySharedState.cs):
  wrapper generation precedes metadata commit, and the old patch info is
  deserialized into a separate object. A rejected transpiler is not recorded there.
- [Harmony instruction inspection](https://github.com/pardeike/Harmony/blob/a264a1bf1ce689e4589e8dcc54b1e2818602a90a/Harmony/Internal/MethodCopier.cs):
  `GetCurrentInstructions` reruns registered transpilers; production metadata
  reporting deliberately avoids that path.
- [BaseLib v3.4.8 NodeFactory](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Utils/NodeFactories/NodeFactory.cs):
  the generic constructor writes the shared factory slot for its target type.
- [BaseLib v3.4.8 initialization](https://github.com/Alchyr/BaseLib-StS2/blob/v3.4.8/Patches/PostModInitPatch.cs):
  the historic first-gameplay-mod early-exit bug is already fixed. The official
  release DLL was checked as well; this change does not patch that obsolete bug.
- [BaseLib v3.4.8 release](https://github.com/Alchyr/BaseLib-StS2/releases/tag/v3.4.8):
  documents the framework's separate compatibility helper and five-file package.

The BaseLib release archive used for inspection matched the repository's pinned
SHA-256 `ad30d8aa4dee8e5d31150ab75eae6e6b927fa83ce30af93f4b2a144c3b09f82f`.
