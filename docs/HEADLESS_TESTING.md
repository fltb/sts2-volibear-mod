# Isolated real-game automation

Status: development checkpoint; see [current handoff](HANDOFF.md) for latest evidence and resume instructions. Real native attack, Strike AutoPlay and optional in-card Engage prototype assertions pass. Overall acceptance remains FAILED on engine teardown errors; the opt-in audio adapter fixes the earlier FMOD startup errors. Sections below describe earlier milestones as well as the runner.

## Run

With the pinned SDK and local game configured for `tools/dev.py`:

```sh
python3 tools/headless.py --repeat 2 --timeout 45
```

Runs Python contract tests, builds the probe, deploys owned mod files, then launches the installed **MegaDot game executable**, not a reimplementation. Each iteration gets a unique `artifacts/headless/<run-id>/` with stdout, engine log, and JSON report. Reports record game version, source commit/dirty state, process status and individual checks. Iterations are bounded (1–10), timeout is bounded (5–300 seconds), and only a newly created process group is terminated on timeout.

The default remains pure `--headless`. Explicit `--display xvfb` starts a private virtual X server through xvfb-run and records `mode: real-game-xvfb`; it never silently substitutes this mode or launches interactive Steam. Xvfb compatibility is still under investigation and is not an accepted fallback yet.

The current `--scenario baseline --frames 2400 --timeout 90` driver executes `DamageCmd.Attack(6)` from a real monster, checks the actual damage result and player HP delta, then calls `PlayerCmd.EndTurn` and waits for the next player round. Both assertions passed in a native headless process; strict overall acceptance still fails on engine errors. This is an attack-command and native turn-scheduler test, not a full original-card play test.

## Isolation evidence (0.107.1 / 59260271)

Local inspection of the installed assembly established:

- `NGame.InitializePlatform` recognizes `--force-steam=off` and returns before calling `SteamInitializer.Initialize`.
- `SaveManager.ConstructDefault` constructs a Steam cloud backend only when `SteamInitializer.Initialized` is true.
- Command-line arguments must reach `OS.GetCmdlineArgs`, so the option is passed as a normal engine argument, not after `--`.
- The discovery launch actually wrote settings under the overridden `XDG_DATA_HOME/SlayTheSpire2/default/1`, not the operator's Steam account directory.

Every invocation overrides HOME and XDG data/config/cache directories. A minimal fresh test settings file opts into mod loading only in that isolated offline profile. No normal settings, cloud saves, or current runs are read or modified by the runner. The installed game and mod directory are shared: mod deployment changes only the development-owned files. This is profile isolation, not an OS security sandbox.

## Acceptance boundaries

A zero exit code alone is never success. The runner requires the Steam-disabled log, no cloud backend announcement, no engine error, and the actual mod initializer marker. Even a passing discovery report explicitly says `combat_tests: not_run`.

Still required for integration acceptance:

1. Runtime assertion of the resolved user-data directory and Steam-disabled state is implemented and passed in a real headless launch (2026-10-31). The overall launch still failed its engine-error check.
2. Structured scenario output from a real game driver, with scenario ID and per-run token, is implemented for the damage-command baseline. The runner rejects missing, stale, malformed or duplicate records and checks HP arithmetic independently.
3. Original attack baseline, then lightning, block, Engage multi-hit/duplicate/skip/advancement/death cases.
4. Two consecutive successful fresh-process runs.
5. Reject missing or stale scenario reports and clean up on failure.

## Audio diagnostic (Linux)

`VOLIBEAR_TEST_AUDIO_ADAPTER=1` compiles a test-only shared object and preloads it alongside the existing FMOD extension. It changes only FMOD Studio initialization to `FMOD_OUTPUTTYPE_NOSOUND` (2), leaving bank loading, game commands and combat unchanged. The runner requires an activation marker when this option is enabled. No original library is overwritten. A local directory symlink avoids ld.so's inability to represent spaces in LD_PRELOAD entries.

Verified 2026-10-31: the adapter activated and eliminated the FMOD initialization/bank/listener errors in a real headless baseline. Native attack and next-round assertions still passed. Overall acceptance remains failed on renderer/text/resource leaks at exit, including when using the game's `NGame.Quit()` cleanup path. This option is still diagnostic, not evidence of a completely clean run.

## Initial environment observations

The first headless discovery process exited zero, reported Steam disabled, and created isolated settings. It did not load Volibear until its fresh test profile opted into mods. Missing host libcurl caused Sentry extension/GDScript errors. A concurrent system `apt-get full-upgrade` was observed; no package-manager or system-library changes were made by this project. Such launches are **failed** discovery tests, not accepted baselines.

Proprietary decompiled material, game assemblies, test profiles and logs stay local/ignored. Only independently authored code and concise API findings belong in Git.
