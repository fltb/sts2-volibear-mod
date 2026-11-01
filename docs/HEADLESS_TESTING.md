# Isolated real-game automation

Current route: [local build, packaging and controlled verification](LOCAL_WORKFLOW.md).
The current native-beast candidate has not been compiled or run against the pinned game in
this environment: its game assemblies are unavailable. Historical assertions and resource
renders below are not evidence that this revision passes. The runner still compares native
renderer/text teardown errors with a stock control rather than silently waiving new errors.

## Current acceptance execution policy

Full suites use **one Mod process for all stages**, native room exit/main-menu cleanup and
a fresh run between independent cases. One separate no-Mod process establishes exit noise.
The current route uses no OS input, viewport input, synthetic clicks, keyboard events or
button-signal shortcuts. Selection decisions use `CardSelectCmd.UseSelector`; paid cards
still use `PlayCardAction` and the real action queue. Same-process native checkpoint restore
is included; a real process restart and two network peers are separate, unexecuted gates.

On Windows, `--display background` creates a private, unselected Windows desktop and launches the native-rendered game there. The runner never switches the operator's desktop and sends no OS input. The process job and desktop handle are owned and released together. Merely starting minimized was tested and did not prevent focus changes; it is not the isolation mechanism. Background mode uses Dummy audio by default, so it is not listening evidence.

Gameplay acceptance uses the real `PlayCardAction`/`RequestEnqueue` path with payment, target validation and native choice handling; it does not replace those steps with direct `OnPlay` or AutoPlay. Runtime errors remain failures even when a semantic receipt passes. In particular, native-renderer runs replace unreliable Dummy-renderer runs rather than waiving texture errors.

## Unified current entrypoint

Use `tools/local_delivery.py --verify-native` to build, check, deploy, execute and package
the same candidate. Configure paths as documented in LOCAL_WORKFLOW on the first run.
For an already built and deployed candidate, this entrypoint runs only the one finite suite:

Windows private-desktop examples (use `--display xvfb` on Linux):

```sh
python -B tools/native_suite.py --execute-native --use-deployed --display background
```

The default finite scope is 410 card-face cases (178 faces plus explicit branches),
48 lifecycle cases, 356 rendered normal/Inspect card views, and S2 native checkpoint
save/restore. The suite validates stage order, one process ID, cleanup, the run token,
independent per-stage receipts, the on-disk checkpoint and one final shutdown. A failure
stops the command and prevents the delivery entrypoint from packaging it as a passed run.
This is not the complete enemy interaction matrix or live multiplayer verification.

`--card-face-cases` and `--card-lifecycle-cases` accept `all` or explicit comma-separated
names. Unknown, duplicate or empty choices fail before launch. The whole suite defaults
to 3,600 seconds / 216,000 frames; limits are 60–14,400 seconds / 3,600–864,000 frames.
There is no per-case restart or repeat option. Smaller subsets are failure diagnostics,
not substitutes for a completed default batch.

The older `native-run`, `native_run_pair.py` and UI catalog drivers retain historical
interface automation. They are excluded from this no-input suite and are not the current
recommended acceptance flow. Their historical restart evidence does not validate the
new beast identities or the current candidate. The new save/load stage uses native
SaveManager, RunState/RunManager restoration and NGame loading without clicking Continue.

Presentation `cards` captures rendered card/Inspect views without an audio claim.
`actions` and `all` require an explicit non-Dummy Godot audio driver, for example
`--audio-driver WASAPI` on Windows or an available `PulseAudio`/`ALSA` driver on Linux.
The stock control uses the same driver. Captures remain in the game's private desktop
or virtual display, record only the game bus, and do not establish human visual or
listening approval. Runtime errors and unmatched teardown errors still fail the run.

## Focused historical diagnostics

With the pinned SDK and local game configured for `tools/dev.py`:

```sh
python3 tools/headless.py --scenario baseline --repeat 1 --timeout 180 --frames 5000
```

Runs Python contract tests, builds the probe, deploys owned mod files, then launches the
installed **StS2 game executable** with its shipped engine; no separate MegaDot editor is
required. Ordinary Godot 4.5.1 Mono builds the resources. Each iteration gets a unique
`artifacts/headless/<run-id>/` with stdout, engine log, and JSON report. Reports record game
version, source commit/dirty state, process status and individual checks. Iterations are
bounded (1–10), timeout is bounded (5–300 seconds), and only a newly created ownership
boundary is terminated on timeout — a POSIX session group, or a Windows job object.

The default remains pure `--headless`. `--display xvfb` is a POSIX route only; on Windows the
runner refuses it rather than silently substituting something else. No mode launches
interactive Steam.

`--scenario baseline --frames 5000 --timeout 180` executes `DamageCmd.Attack(6)` from a real
monster, checks the actual damage result and player HP delta, auto-plays Strike, then calls
`PlayerCmd.EndTurn` and waits for the next player round. Both assertions passed in native
headless processes on Linux (2026-10-31) and Windows (2026-10-31). This is an attack-command,
card and native turn-scheduler test, not a full original-card play test.

## Acceptance gate

A zero exit code alone is never success. Two classes of log output are separated:

- **Runtime errors** (`ERROR:`, `SCRIPT ERROR:`, `[ERROR]`) outside Godot's teardown report
  must be absent. This is strict and unchanged.
- **Engine teardown errors** (`leaked at exit`, `resources still in use at exit`) are compared
  against the signature of a **stock control launch**: `headless.py` runs the same executable
  once with `--nomods` and the same frame budget, and only the resource categories that control
  produces are tolerated. Counts vary per run, so only categories are compared; a new category
  fails the run.

This does not claim a clean exit. It claims the mod introduces no exit error the shipped game
does not already produce by itself, and the control evidence is stored in each report under
`diagnostics.stock_teardown_control`. The 2026-10-31 Windows runs leak `Environment`,
`DummyTexture`, `DummyMesh`, `DummyMaterial`, `DummyShader`, `ShapedTextDataAdvanced`,
`FontAdvanced`, `FontAdvancedLinkedVariation` and the aggregate resource count with no mods
loaded at all.

## Isolation evidence (0.107.1 / 59260271)

Local inspection of the installed assembly established:

- `NGame.InitializePlatform` recognizes `--force-steam=off` and returns before calling
  `SteamInitializer.Initialize`.
- `SaveManager.ConstructDefault` constructs a Steam cloud backend only when
  `SteamInitializer.Initialized` is true.
- Command-line arguments must reach `OS.GetCmdlineArgs`, so the option is passed as a normal
  engine argument, not after `--`.

Every invocation overrides the user-data variables: `HOME`, `XDG_DATA_HOME`,
`XDG_CONFIG_HOME`, `XDG_CACHE_HOME` on POSIX, and `HOME`, `APPDATA`, `LOCALAPPDATA` on Windows,
where Godot resolves `user://` from `APPDATA`. A minimal fresh test settings file opts into mod
loading only in that isolated offline profile. No normal settings, cloud saves, or current runs
are read or modified by the runner. The installed game and mod directory are shared: mod
deployment changes only the development-owned files. This is profile isolation, not an OS
security sandbox.

The resolved user-data directory and the Steam-disabled state are asserted from inside the mod
(`ISOLATION_OK steam=false`) and the run fails if either is wrong.

## Deployment ownership

Deploy writes the owned `Volibear.dll`, `Volibear.json`, and `Volibear.pck`, records SHA-256 ownership under
`.local/deploy/`, and refuses to overwrite unowned files or silently accept hand-edited builds.
The marker deliberately lives **outside** the mod directory: the game scans every JSON file it
finds there as a manifest and reports a missing `id` field as an error. `dev.py undeploy`
removes exactly the files it owns and leaves anything else in place.

## Still required for integration acceptance

1. Run the current candidate's complete normal Harmony installation chain and required
   lightning/block/Engage/domain cases against the pinned game assemblies.
2. Execute the connected paid-card/lifecycle batches and rendered presentation checks in
   the private Windows desktop or Linux virtual display. These routes are implemented;
   their wiring tests do not substitute for native execution.
3. Execute normal progression and the owned-profile save/restart/Continue pair; compare
   native rounds, intents and cleanup. Human visual/listening review remains separate.
4. Keep attributing engine teardown noise against the stock control. This does not
   remove the shipped engine's leak or claim a clean exit.

## Audio diagnostic (Linux)

`VOLIBEAR_TEST_AUDIO_ADAPTER=1` compiles a test-only shared object and preloads it alongside the
existing FMOD extension. It changes only FMOD Studio initialization to `FMOD_OUTPUTTYPE_NOSOUND`
(2), leaving bank loading, game commands and combat unchanged. On Windows the option is refused
with an explicit error: the adapter is an `LD_PRELOAD` mechanism, and Windows headless already
initializes FMOD successfully with `--audio-driver Dummy`. No original library is overwritten.

## Initial environment observations

The first Linux headless discovery process exited zero, reported Steam disabled, and created
isolated settings. It did not load Volibear until its fresh test profile opted into mods.
Missing host libcurl caused Sentry extension/GDScript errors. Such launches are **failed**
discovery tests, not accepted baselines.

On Windows (2026-10-31) the first discovery launch loaded the mod immediately; the only reported
error was the deployment marker inside the mod directory, a real defect in the deploy tool, now
fixed. Proprietary decompiled material, game assemblies, test profiles and logs stay
local/ignored. Only independently authored code and concise API findings belong in Git.

## Catalog persistence (S3 only)

The independent [catalog runner](../tools/save_load_catalog_pair.py) uses a fresh,
owned, short-path offline profile. It never accepts an existing save profile and
never builds or deploys. Deploy the intended candidate first, then run serially:

```powershell
python tools/save_load_catalog_pair.py --execute-native --case S3 --mode same-process --display window --timeout 300
python tools/save_load_catalog_pair.py --execute-native --case S3 --mode restart --display window --timeout 300
```

This explicitly constructs all 89 base/upgraded pairs as 178 native master cards,
checks their distinct combat clones and complete serialized state, performs one
paid B02, and invokes native Pause / Save-and-Quit / Continue UI actions. Continue
reconstructs the **room-entry checkpoint**, not the disturbed midcombat state.
Programmatic native UI is not physical window-input evidence.

The [independent oracle](../tools/save_load_catalog_evidence.py) checks typed
references, full JSON values, reload-only defaults, and actual disk checkpoints.
Restart resumes only after every prepare-phase common check, strict phase
validation, and disk reread succeeds. S4/S5 are rejected before launching or
creating a profile; they are not silently mapped to S3. The existing
[S1/S2 runner](../tools/save_load_pair.py) remains separate.

Do not deploy another candidate while a test process or restart pair is active.
Single-run output under `artifacts/save-catalog/` remains ignored, like the other
native-test artifacts.
